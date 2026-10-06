#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""三个 MCP 服务器工具面的**同口径**实测（唯一测量脚本）。

为什么必须同口径：三个服务器分别由不同的人/文档描述过，
"sage 24 工具 13,841 B / helper 10 工具 5,631 B / blbridge 55 工具 59,973 B"
这三个数**不是同一种量**（一个是 desc+schema 之和，一个是含键名的对象序列化）。
本脚本对三者一律用：
    toolBytes = len(json.dumps(tool, ensure_ascii=False).encode('utf-8'))
    arrayBytes = len(json.dumps(tools, ensure_ascii=False).encode('utf-8'))
这两行是**真正进模型上下文**的东西，且与 MCP 无关（纯 JSON）。

用法:
    python measure_any.py                 # 三个都测（默认配置）
    python measure_any.py blbridge         # 只测一个
    python measure_any.py blbridge 4b      # 指定 toolset
"""
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# ★ 伞仓根 = probe/ 的上一级。第 4 个上游（localization-audit）就在它下面，
#   所以用**相对定位**而不是写死绝对路径 —— 否则伞仓一搬家（或别人 clone）
#   这个探针就起不来（实测：旧目录一删，本项立刻失败）。
ROOT = os.path.dirname(HERE)
# 环境变量优先，兜底用「跑本脚本的解释器」—— 与 bl_chain.py 同一口径。
PY = os.environ.get("DSH_CHAIN_PYTHON") or sys.executable
BUN = os.environ.get("DSH_CHAIN_BUN") or (
    r"C:\Users\LCGX\AppData\Local\Microsoft\WinGet\Packages"
    r"\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\bun-windows-x64\bun.exe")
GAME = os.environ.get("BANNERLORD_DIR") or (
    r"G:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")
DIV = 3.80  # 估算回退系数 —— **实测校准值**（真实 tokenizer 测出 bytes/token=3.80）
TOKENIZER_PATH = os.environ.get("DSH_CHAIN_TOKENIZER") or ""

# ★ 字节口径：**compact JSON**（separators=(",", ":")）
#   这是真正上线的形态（MCP 传输不插空格），也是 JS JSON.stringify 的默认。
#   Python json.dumps 默认插 ", " / ": " 空格 ⇒ blbridge 会多算 1,529 字节。
_cached_tok = None
_tried = False


def tokenizer():
    global _cached_tok, _tried
    if _tried:
        return _cached_tok
    _tried = True
    try:
        from tokenizers import Tokenizer
        _cached_tok = Tokenizer.from_file(TOKENIZER_PATH)
    except Exception:
        _cached_tok = None
    return _cached_tok


def count_tokens(obj):
    """(tokens, exact)。exact=True = 真实 tokenizer。"""
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    tok = tokenizer()
    if tok is not None:
        return len(tok.encode(payload, add_special_tokens=False).ids), True
    return int(round(len(payload.encode("utf-8")) / DIV)), False

# ★ 三个业务上游的位置：环境变量优先，兜底本机常见路径。
#   （它们**不在本伞仓里** —— 见 docs/why-umbrella-repo.md。）
BLBRIDGE_DIR = os.environ.get("DSH_CHAIN_BLBRIDGE") or (
    r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge")
BL_MCP = os.path.join(BLBRIDGE_DIR, "tools", "bl_mcp.py")
SAGE_DIR = os.environ.get("DSH_CHAIN_SAGE") or r"F:\Program Files\BannerlordSage"
HELPER_DIR = os.environ.get("DSH_CHAIN_HELPER") or r"F:\Program Files\Bannerlord.Helper"

SERVERS = {
    "blbridge": {
        "cmd": [PY, BL_MCP],
        "cwd": os.path.dirname(BL_MCP),
        "env": {"PYTHONIOENCODING": "utf-8", "BANNERLORD_DIR": GAME},
        "toolsetEnv": "BLBRIDGE_TOOLSET",
    },
    "bannerlordsage": {
        "cmd": [BUN, "run", os.path.join(SAGE_DIR, "src", "entrypoints", "bannerlord-full-stdio.ts")],
        "cwd": SAGE_DIR,
        "env": {"BANNERSAGE_GAME": "bannerlord", "BANNERSAGE_EULA_ACCEPTED": "true",
                "BANNERSAGE_BANNERLORD_GAME_DIR": GAME},
        "toolsetEnv": "BANNERSAGE_TOOLSET",
    },
    "bannerlordhelper": {
        "cmd": [BUN, "run", os.path.join(HELPER_DIR, "mcp", "server.ts")],
        "cwd": HELPER_DIR,
        "env": {"NEXUS_API_KEY": ""},
        "toolsetEnv": None,
    },
    # 第 4 个上游（2026-10-06）：本项目自研的汉化审计（只读）。
    # ⚠️ 探针必须**独立量一遍**，不能从 bl_chain 抄数字 ——
    #    否则"交叉校验"就退化成"自己验自己"，失去独立第二意见的意义。
    # ★ 路径用 ROOT 相对定位：它就住在伞仓里，跟着仓库走。
    "localization-audit": {
        "cmd": [PY, os.path.join(ROOT, "localization-audit", "la_mcp.py")],
        "cwd": os.path.join(ROOT, "localization-audit"),
        "env": {"PYTHONIOENCODING": "utf-8", "BANNERLORD_DIR": GAME},
        "toolsetEnv": None,
    },
}


def probe(server, toolset=None, timeout=90.0):
    cfg = SERVERS[server]
    env = dict(os.environ)
    env.update(cfg["env"])
    if toolset and cfg["toolsetEnv"]:
        env[cfg["toolsetEnv"]] = toolset
    elif cfg["toolsetEnv"]:
        env.pop(cfg["toolsetEnv"], None)

    proc = subprocess.Popen(cfg["cmd"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, cwd=cfg["cwd"])
    lines = []

    def send(obj):
        proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        proc.stdin.flush()

    def readline():
        raw = proc.stdout.readline()
        return json.loads(raw.decode("utf-8")) if raw else None

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2026-07-28", "capabilities": {},
                         "clientInfo": {"name": "probe", "version": "1"}}})
        init_res = readline()
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tl = readline()
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    return init_res, tl


def measure(tl):
    tools = tl["result"]["tools"]
    rows = []
    for t in tools:
        desc = t.get("description") or ""
        schema = t.get("inputSchema") or {}
        rows.append({
            "name": t.get("name"),
            "props": len((schema.get("properties") or {})),
            "descBytes": len(json.dumps(desc, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8")),
            "schemaBytes": len(json.dumps(schema, ensure_ascii=False,
                                          separators=(",", ":")).encode("utf-8")),
            "toolBytes": len(json.dumps(t, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8")),
            "descChars": len(desc),
            "extraKeys": sorted(k for k in t if k not in ("name", "description", "inputSchema")),
        })
    rows.sort(key=lambda r: -r["toolBytes"])
    # ★ 规范口径：tools 数组整体（compact），这是真正进上下文的东西
    array_bytes = len(json.dumps(tools, ensure_ascii=False,
                                 separators=(",", ":")).encode("utf-8"))
    array_tokens, exact = count_tokens(tools)
    return rows, array_bytes, array_tokens, exact, tools


def run_one(server, toolset=None):
    label = server + ("/" + toolset if toolset else "")
    t0 = time.time()
    init_res, tl = probe(server, toolset)
    if tl is None or "result" not in tl:
        print("!! %s 探测失败: %s" % (label, json.dumps(tl)[:300] if tl else "无响应"))
        return None
    rows, array_bytes, array_tokens, exact, raw_tools = measure(tl)
    caps = (init_res or {}).get("result", {}).get("capabilities")
    info = (init_res or {}).get("result", {}).get("serverInfo")
    rec = {"server": server, "toolset": toolset, "label": label,
           "count": len(rows), "arrayBytes": array_bytes,
           "arrayTokens": array_tokens, "tokensExact": exact,
           "bytesPerToken": round(array_bytes / array_tokens, 2) if array_tokens else None,
           "descBytes": sum(r["descBytes"] for r in rows),
           "schemaBytes": sum(r["schemaBytes"] for r in rows),
           "sumToolBytes": sum(r["toolBytes"] for r in rows),
           "capabilities": caps, "serverInfo": info,
           "elapsedSec": round(time.time() - t0, 1),
           "rawTools": raw_tools,
           "rows": rows}
    out = os.path.join(HERE, "measured_%s.json" % label.replace("/", "_").replace("+", "_"))
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    # 原始 tools 单独落一份，供分层模拟用
    raw_out = os.path.join(HERE, "measured_%s_raw.json" % label.replace("/", "_").replace("+", "_"))
    with io.open(raw_out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(raw_tools, fh, ensure_ascii=False, indent=1)
    print("[ok] %-26s tools=%-3d array=%-7d %s=%-7d (%.1fs) caps=%s"
          % (label, len(rows), array_bytes,
             "tokens" if exact else "est_tok", array_tokens, rec["elapsedSec"],
             json.dumps(caps, ensure_ascii=False)))
    return rec


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else None
    toolset = sys.argv[2] if len(sys.argv) > 2 else None
    targets = [which] if which else list(SERVERS)
    for s in targets:
        if s not in SERVERS:
            print("未知服务器 %s（可用: %s）" % (s, ", ".join(SERVERS)))
            return 1
        run_one(s, toolset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
