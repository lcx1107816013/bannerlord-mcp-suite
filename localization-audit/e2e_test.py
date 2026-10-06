# -*- coding: utf-8 -*-
"""端到端：把 `la_mcp.py` **当成一个 MCP 服务器**，用与 DSH 完全相同的协议跟它说话。

验证的是 DSH 真正会做的事：
    initialize -> notifications/initialized -> tools/list -> tools/call

而不只是"在 Python 里直接调函数" —— 那样测不出协议面是否正确。

判据（每条都能指出"哪种输入会红"）：
  E1 initialize 返回合法 capabilities 与 serverInfo
  E2 tools/list 暴露 2 个工具，且 schema 合法（有 inputSchema）
  E3 tools/call la_audit_coverage 真跑通（社区口径，返回缺键数）
  E4 tools/call la_dll_strings 真跑通（按 module 自动找 DLL）
  E5 ★ 只读断言：调用前后**没有任何文件被写过**（本服务器的核心承诺）
  E6 坏参数返回 isError=true 而不是崩（unknown tool / 缺参数）
  E7 中文不乱码（UTF-8 stdio 钉死）
"""
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "la_mcp.py")
PY = sys.executable

FAILED = []


def check(cond, label, extra=""):
    print("  [%s] %s%s" % ("OK" if cond else "FAIL", label,
                           ("  <- " + str(extra)[:150]) if (extra and not cond) else ""))
    if not cond:
        FAILED.append(label)


def rpc(proc, obj, timeout=300.0):
    proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    t0 = time.time()
    while time.time() - t0 < timeout:
        line = proc.stdout.readline()
        if not line:
            return None
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("id") == obj.get("id"):
            return d
    return None


def snapshot(paths):
    """记录一批目录下所有文件的 (路径, 大小, mtime) —— 用于只读断言。"""
    snap = {}
    for base in paths:
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for f in files:
                p = os.path.join(root, f)
                try:
                    st = os.stat(p)
                    snap[p] = (st.st_size, st.st_mtime_ns)
                except OSError:
                    pass
    return snap


def main():
    for n in ("stdout", "stderr"):
        try:
            getattr(sys, n).reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"      # ★ 否则 __pycache__ 会被写 ⇒ 干扰只读断言
    env.setdefault("BANNERLORD_DIR",
                   r"G:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

    game = env["BANNERLORD_DIR"]
    # 只读断言盯这三处：本目录（不该出现 __pycache__ 等）+ 游戏 Modules
    watch = [HERE, os.path.join(game, "Modules")]
    before = snapshot(watch)

    proc = subprocess.Popen([PY, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace", bufsize=1, env=env)
    try:
        # ── E1 initialize ────────────────────────────────────────────
        d = rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                  "clientInfo": {"name": "probe", "version": "1"}}})
        r = (d or {}).get("result") or {}
        check(bool(r.get("capabilities")), "E1 initialize 有 capabilities", r)
        check((r.get("serverInfo") or {}).get("name") == "localization-audit",
              "E1 serverInfo.name 正确", r.get("serverInfo"))
        proc.stdin.write(json.dumps({"jsonrpc": "2.0",
                                     "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()

        # ── E2 tools/list ────────────────────────────────────────────
        d = rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = ((d or {}).get("result") or {}).get("tools") or []
        names = sorted(t["name"] for t in tools)
        check(len(tools) == 2, "E2 暴露 2 个工具", names)
        check(names == ["la_audit_coverage", "la_dll_strings"], "E2 工具名正确", names)
        check(all(t.get("inputSchema", {}).get("type") == "object" for t in tools),
              "E2 每个工具都有 object inputSchema")

        # ── E7 中文不乱码 ────────────────────────────────────────────
        raw = json.dumps(tools, ensure_ascii=False)
        check("\ufffd" not in raw, "E7 工具描述无替换字符（UTF-8 钉死成功）",
              raw.count("\ufffd"))

        # ── E3 la_audit_coverage ─────────────────────────────────────
        d = rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                       "params": {"name": "la_audit_coverage",
                                  "arguments": {"scope": "community"}}}, timeout=600)
        res = (d or {}).get("result") or {}
        txt = (res.get("content") or [{}])[0].get("text", "")
        check(res.get("isError") is False, "E3 audit 未报错", txt[:160])
        check("真缺键" in txt, "E3 输出含「真缺键」", txt[:160])
        check("缺键" in txt, "E3 输出提到缺键", txt[:120])

        # ── E4 la_dll_strings（按 module 自动找 DLL）─────────────────
        d = rpc(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                       "params": {"name": "la_dll_strings",
                                  "arguments": {"module": "RTSCamera"}}}, timeout=300)
        res = (d or {}).get("result") or {}
        txt = (res.get("content") or [{}])[0].get("text", "")
        check(res.get("isError") is False, "E4 dll_strings 未报错", txt[:160])
        check(len(txt) > 50, "E4 有实质输出（%d 字符）" % len(txt))

        # ── E6 坏参数 ────────────────────────────────────────────────
        d = rpc(proc, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                       "params": {"name": "no_such_tool", "arguments": {}}})
        res = (d or {}).get("result") or {}
        check(res.get("isError") is True, "E6 未知工具 ⇒ isError=true（不崩）",
              res.get("isError"))
        d = rpc(proc, {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                       "params": {"name": "la_dll_strings", "arguments": {}}})
        res = (d or {}).get("result") or {}
        check(res.get("isError") is True, "E6 缺 dll/module ⇒ isError=true")
        d = rpc(proc, {"jsonrpc": "2.0", "id": 7, "method": "no/such/method"})
        check((d or {}).get("error", {}).get("code") == -32601,
              "E6 未知 method ⇒ -32601")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass

    # ── E5 只读断言 ──────────────────────────────────────────────────
    after = snapshot(watch)
    new_files = sorted(set(after) - set(before))
    changed = sorted(p for p in set(after) & set(before) if after[p] != before[p])
    check(not new_files, "E5 未新建任何文件（只读承诺）", new_files[:5])
    check(not changed, "E5 未修改任何文件（只读承诺）", changed[:5])

    print()
    if FAILED:
        print("端到端自测**失败** %d 项：%s" % (len(FAILED), FAILED))
        return 1
    print("端到端自测全部通过：协议面正确 + 两个工具真跑通 + **只读承诺已验**。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
