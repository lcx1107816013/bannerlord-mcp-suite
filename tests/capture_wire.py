#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""抓取 bl_chain.py 的**原始协议线**，供 Node 侧用官方 SDK 的 schema 校验。

为什么这样做：本机沙箱禁止 Node 的管道 stdio（`spawn EPERM`），所以不能让
官方 SDK 的 Client 直接 spawn 我们的服务器。但**SDK 校验的是消息本身**，
所以改成：Python 这边把真实的协议线抓下来 -> Node 那边用官方 SDK 的 zod
schema 逐条校验。这比"能不能握手"更硬 —— 它直接验"我们发的每个字节是否合规"。

输出：wire_<mode>.json，内容是 {"mode":..., "lines_in":[...], "lines_out":[...]}
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 伞仓根（bl_chain.py / localization-audit 在这）
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

CHAIN = os.path.join(ROOT, "bl_chain.py")
PY = r"D:\Program Files\Python312\python.exe"

# 每种模式要跑的请求：(mode, groups, [requests])
SCENARIOS = [
    ("full", None, [
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "bh_list_languages", "arguments": {}}},
    ]),
    ("slim", None, [
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]),
    ("meta", None, [
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "chain_status", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "chain_search_tools", "arguments": {"query": "汉化", "limit": 3}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "chain_get_tool_details", "arguments": {"name": "bl_crash"}}},
        # ★ 隐藏工具照样调：bl_config 不在 meta 模式的 tools/list 里
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "chain_call_tool",
                    "arguments": {"name": "bl_config", "args": {}}}},
        # 未知工具 -> 必须是合法 CallToolResult（isError），不是协议错
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
         "params": {"name": "chain_call_tool",
                    "arguments": {"name": "no_such_tool_zz", "args": {}}}},
    ]),
    ("meta", "ro", [
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]),
]


def capture(mode, groups, requests):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["DSH_CHAIN_MODE"] = mode
    if groups:
        env["DSH_CHAIN_GROUPS"] = groups
    else:
        env.pop("DSH_CHAIN_GROUPS", None)

    proc = subprocess.Popen([PY, CHAIN], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env, cwd=HERE, bufsize=0)
    out_lines = []

    def send(o):
        proc.stdin.write((json.dumps(o, ensure_ascii=False) + "\n").encode("utf-8"))
        proc.stdin.flush()

    def read_one():
        raw = proc.stdout.readline()
        return raw.decode("utf-8", "replace").rstrip("\n") if raw else None

    sent = []
    try:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "wirecap", "version": "1"}}}
        send(init)
        sent.append(init)
        out_lines.append(read_one())
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        sent.append({"jsonrpc": "2.0", "method": "notifications/initialized"})

        # 把 tools/list 与 tools/call 都按 id 顺序跑
        for req in requests:
            send(req)
            sent.append(req)
            got = read_one()
            if got is not None:
                out_lines.append(got)
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()

    return {"mode": mode, "groups": groups, "sent": sent,
            "received": [l for l in out_lines if l is not None]}


def main():
    all_out = {}
    for mode, groups, reqs in SCENARIOS:
        key = mode + ("_" + groups if groups else "")
        cap = capture(mode, groups, reqs)
        all_out[key] = cap
        print("[%-12s] 发出 %d 条，收到 %d 条"
              % (key, len(cap["sent"]), len(cap["received"])))
    dest = os.path.join(HERE, "wire_capture.json")
    with io.open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(all_out, fh, ensure_ascii=False, indent=1)
    print("\n-> %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
