#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""决定性实验：**被 tools/list 隐藏的工具，tools/call 还能不能调？**

为什么这个实验决定整个方案：
    如果"隐藏 = 不可用"，那任何分层都必然损失功能；
    如果"隐藏只是不可发现"，那就可以安全地把工具移出 tools/list，
    再用检索元工具按需找回 —— 这就是官方 progressive discovery 的前提。

设计（单变量对照，同一进程配置只差一个 call 的目标）：
    BLBRIDGE_TOOLSET=4b      -> tools/list 只有 10 个，**不含** bl_config
    tools/call bl_config     -> 若成功 ⇒ 隐藏不影响可调用性
    tools/call bl_status     -> 对照组（4b 组内，必成功）
"""
import json
import os
import subprocess
import sys

BL_MCP = r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge\tools\bl_mcp.py"
PY = r"D:\Program Files\Python312\python.exe"
GAME = r"G:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"


def main():
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "BANNERLORD_DIR": GAME,
                "BLBRIDGE_TOOLSET": "4b"})
    proc = subprocess.Popen([PY, BL_MCP], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, cwd=os.path.dirname(BL_MCP))

    def send(o):
        proc.stdin.write((json.dumps(o) + "\n").encode("utf-8"))
        proc.stdin.flush()

    def rl():
        raw = proc.stdout.readline()
        return json.loads(raw.decode("utf-8")) if raw else None

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2026-07-28", "capabilities": {},
                     "clientInfo": {"name": "t", "version": "1"}}})
    rl()
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    listed = {t["name"] for t in rl()["result"]["tools"]}

    results = {}
    for i, target in enumerate(["bl_status", "bl_config", "bl_crash", "bl_mcm_settings"], start=10):
        send({"jsonrpc": "2.0", "id": i, "method": "tools/call",
              "params": {"name": target, "arguments": {}}})
        resp = rl()
        if resp is None:
            results[target] = ("NO_RESPONSE", None)
            continue
        if "error" in resp:
            results[target] = ("JSONRPC_ERROR", resp["error"].get("message"))
        else:
            r = resp.get("result", {})
            text = ""
            for c in r.get("content", []):
                if c.get("type") == "text":
                    text += c.get("text", "")
            results[target] = ("isError=%s" % r.get("isError"), text[:220].replace("\n", " "))

    proc.stdin.close()
    proc.wait(timeout=15)

    print("BLBRIDGE_TOOLSET=4b -> tools/list 暴露 %d 个工具" % len(listed))
    print()
    print("| 目标工具 | 在 tools/list 里？ | 调用结果 | 返回前 220 字 |")
    print("|---|---|---|---|")
    for t, (status, text) in results.items():
        print("| `%s` | %s | %s | %s |"
              % (t, "是" if t in listed else "**否（隐藏）**", status,
                 (text or "").replace("|", "\\|")))
    print()
    hidden_ok = [t for t, (s, _) in results.items()
                 if t not in listed and s.startswith("isError=False")]
    print("隐藏但仍可成功调用: %s" % (hidden_ok or "无"))
    if hidden_ok:
        print("=> 结论：**隐藏 != 不可用**。分层只影响可发现性，不影响可调用性。")
    else:
        print("=> 结论：隐藏后的调用被拒 —— 分层会损失功能，不能靠隐藏做的。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
