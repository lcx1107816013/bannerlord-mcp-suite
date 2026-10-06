# -*- coding: utf-8 -*-
r"""兼容性**边界**实测：客户端报不同 `protocolVersion` 时，我们手写的服务器怎么回应。

## 为什么不用官方 SDK 做这件事

第一版我用 `transport.send()` —— **那个 API 不存在**（`cannot read properties of undefined`），
于是六个版本全"通过"，**但那是假的**（我的 catch 把错误吞成了"✅"）。
⇒ 教训：**探针本身错了，结论就全是假的** ⇒ 换成**裸 stdio JSON-RPC**，
   我自己控制帧格式，每一步都检查响应，不再有"吞错"的余地。

## 我们的线上格式（已核实）

**换行分隔 JSON（NDJSON）**，不是 `Content-Length` 分帧。
三个手写服务器（`bl_chain.py` / `bl_mcp.py` / `la_mcp.py`）都是这个格式。

## 本脚本要回答

1. 客户端报**比我们新**的版本（2025-06-18 等）时，服务器回什么？
2. 客户端报**比我们旧**的版本（2024-10-07 / 2019-01-01）时呢？
3. 回执之后 `tools/list` 还能不能正常用？

★ 已知（读源码得出）：我们的 `initialize` **固定回 `2024-11-05`**，不回声客户端版本。
  本脚本是**验证**这一点，并看客户端侧有没有因此断掉。
"""
import json
import os
import subprocess
import sys
import threading
import time

PY = sys.executable
TARGET = r"E:\Document\bannerlord-mcp-suite\localization-audit\la_mcp.py"
CWD = r"E:\Document\bannerlord-mcp-suite\localization-audit"

CLIENT_VERSIONS = [
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
    "2024-10-07",
    "2019-01-01",
]


def probe(client_version, timeout=20.0):
    """起一次服务器，报指定版本，返回 (回执版本, 工具数, 错误)。

    用**独立进程 + 逐行读**，避免任何"吞错"。
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.Popen(
        [PY, TARGET],
        cwd=CWD, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", bufsize=1,
    )
    lines = []
    done = threading.Event()

    def reader():
        try:
            for ln in p.stdout:
                ln = ln.strip()
                if ln:
                    lines.append(ln)
                    done.set()
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    def send(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def wait_for(idv, extra_timeout=timeout):
        """等到某条 id 的响应出现（通知没有 id，不等）。"""
        deadline = time.time() + extra_timeout
        while time.time() < deadline:
            for ln in list(lines):
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                if o.get("id") == idv:
                    return o
            time.sleep(0.05)
        return None

    try:
        send({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": client_version,
                "capabilities": {},
                "clientInfo": {"name": "version-probe", "version": "1"},
            },
        })
        r1 = wait_for(1)
        if r1 is None:
            return None, None, "initialize 无响应（超时）"
        replied = (r1.get("result") or {}).get("protocolVersion")
        if replied is None:
            return None, None, "initialize 回执里没有 protocolVersion: %s" % json.dumps(r1)[:110]

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        r2 = wait_for(2)
        if r2 is None:
            return replied, None, "tools/list 无响应（超时）"
        tools = ((r2.get("result") or {}).get("tools")) or []
        return replied, len(tools), None
    finally:
        try:
            p.kill()
        except Exception:
            pass


def main():
    print("目标: %s" % TARGET)
    print("线上格式: 换行分隔 JSON (NDJSON)\n")
    print("  %-14s %-14s %-9s %s" % ("客户端报的版本", "服务器回执", "工具数", "错误"))
    print("  " + "-" * 66)

    rows = []
    for v in CLIENT_VERSIONS:
        replied, n, err = probe(v)
        rows.append((v, replied, n, err))
        print("  %-14s %-14s %-9s %s" % (
            v, replied if replied else "-", n if n is not None else "-", err or ""))

    print()
    print("=" * 68)
    ok = [r for r in rows if r[3] is None and r[2] is not None]
    print("可正常 initialize + tools/list：%d / %d" % (len(ok), len(rows)))

    replies = set(r[1] for r in rows if r[1])
    print("服务器实际回执过的版本: %s" % (", ".join(sorted(replies)) or "无"))
    if replies == {"2024-11-05"}:
        print()
        print("★ 结论：**无论客户端报什么版本，我们都固定回 2024-11-05**。")
        print("  这是规范允许的（服务器选它支持的版本）——")
        print("  客户端若不支持该版本，规范要求它断开；实测官方 SDK 1.30.0 **接受了**。")
        print("  ⇒ 对外的说法应是「与官方 SDK 实测互通」，"
              "而不是「支持所有底座」（后者无法证明）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
