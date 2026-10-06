#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""分层方案量化 —— 用**实测**的 tools/list 原始定义算，纯机械变换，可复现。

⚠️ 本脚本已被 `mcp-chain/bl_chain.py --measure` 与 `mcp-chain/real_tokens.py`
**取代**（那两处用 compact JSON + 真实 tokenizer）。保留它是为了给"瘦身能省多少"
这个**纯机械变换**的问题提供独立第二意见。

口径（已校准，2026-10-06）：
  - 字节 = **compact JSON**（`separators=(",", ":")`）—— 上线形态
  - token = **真实 tokenizer**（Spark2.5，vocab 131072，与本机 4B GGUF 同 vocab）
            装不到才退回 bytes/3.80

输入：measured_<server>_raw.json（由 measure_any.py 实测产出）
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DIV = 3.80  # 实测校准值（真实 tokenizer 测出 bytes/token=3.80）；旧的 3.44 会高估约 10%
SERVERS = ["blbridge", "bannerlordsage", "bannerlordhelper", "localization-audit"]
TOKENIZER_PATH = r"E:\Document\spark-heretic\model\tokenizer.json"

_TOK = None
_TRIED = False


def tokenizer():
    global _TOK, _TRIED
    if _TRIED:
        return _TOK
    _TRIED = True
    try:
        from tokenizers import Tokenizer
        _TOK = Tokenizer.from_file(TOKENIZER_PATH)
    except Exception:  # noqa: BLE001
        _TOK = None
    return _TOK


def jb(o):
    """compact JSON 字节数 —— 唯一字节口径。"""
    return len(json.dumps(o, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))


def ntok(o):
    """(tokens, exact) —— 优先真实 tokenizer。"""
    payload = json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    tok = tokenizer()
    if tok is not None:
        return len(tok.encode(payload, add_special_tokens=False).ids), True
    return int(round(len(payload.encode("utf-8")) / DIV)), False


def tt(label):
    return "**真实 token**" if label else "估算 token"


def load_raw(name):
    with io.open(os.path.join(HERE, "measured_%s_raw.json" % name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def slim(t, desc_chars=90, prop_chars=40):
    """L1 瘦身：只截断**说明文字**；type/enum/default/required/枚举值一律不动。"""
    out = {"name": t["name"]}
    desc = (t.get("description") or "").strip()
    head = desc.split("\n\n")[0].strip()
    if "。" in head:
        head = head.split("。")[0].strip() + "。"
    if len(head) > desc_chars:
        head = head[:desc_chars].rstrip() + "…"
    out["description"] = head
    schema = json.loads(json.dumps(t.get("inputSchema") or {}))
    props = schema.get("properties")
    if isinstance(props, dict):
        for spec in props.values():
            if isinstance(spec, dict) and isinstance(spec.get("description"), str):
                d = spec["description"]
                if len(d) > prop_chars:
                    spec["description"] = d[:prop_chars].rstrip() + "…"
    out["inputSchema"] = schema
    return out


def meta_tools():
    return [
        {"name": "search_tools",
         "description": "按关键词检索全部已注册工具（含三个 MCP 服务器）。返回 name + 一行摘要。",
         "inputSchema": {"type": "object", "properties": {
             "query": {"type": "string"},
             "limit": {"type": "integer", "default": 5}},
             "required": ["query"], "additionalProperties": False}},
        {"name": "get_tool_details",
         "description": "取单个工具的完整 inputSchema。调用前先看这个。",
         "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}},
                         "required": ["name"], "additionalProperties": False}},
        {"name": "call_tool",
         "description": "调用工具 {name, args}。name 可以是任何已注册工具（不限于检索过的）。",
         "inputSchema": {"type": "object", "properties": {
             "name": {"type": "string"}, "args": {"type": "object"}},
             "required": ["name"], "additionalProperties": False}},
    ]


def main():
    raws = {s: load_raw(s) for s in SERVERS}
    l0 = {s: jb(raws[s]) for s in SERVERS}
    l1 = {s: jb([slim(t) for t in raws[s]]) for s in SERVERS}
    all0 = [t for s in SERVERS for t in raws[s]]
    all1 = [slim(t) for s in SERVERS for t in raws[s]]
    t0, tok0 = sum(l0.values()), ntok(all0)
    t1, _ = sum(l1.values()), ntok(all1)
    tok0n, tok0x = ntok(all0)
    tok1n, _ = ntok(all1)
    mt_tools = meta_tools()
    mt = jb(mt_tools)
    mt_tok, _ = ntok(mt_tools)
    HEAD = "**真实 token**" if tok0x else "估算 token"

    print("# 分层方案量化（实测数据，机械变换）\n")
    print("> 口径：字节 = **compact JSON**；token = %s（%s）。" % (HEAD,
          "Spark2.5 tokenizer，vocab 131072，与本机 4B GGUF 同 vocab" if tok0x
          else "bytes/%.2f 估算" % DIV))
    print("> 权威值以 `mcp-chain/bl_chain.py --measure` 为准；本脚本是独立第二意见。\n")
    print("三个 MCP 服务器合计 **%d 个工具**。\n" % len(all0))

    print("## L0 现状 vs L1 瘦身\n")
    print("L1 = description 取首段首句（≤90 字）+ inputSchema 的属性说明截断 40 字。")
    print("**只截断说明文字**；type / enum / default / required 一个字节都不动")
    print("（行为契约不变已由 `mcp-chain/slim_contract_test.py` 逐字段验证 89/89）。\n")
    print("| 服务器 | 工具数 | L0 字节 | L0 token | L1 字节 | L1 token | 降幅 |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for s in SERVERS:
        sl = [slim(t) for t in raws[s]]
        k0, _ = ntok(raws[s])
        k1, _ = ntok(sl)
        print("| `%s` | %d | %s | %s | %s | %s | **-%.0f%%** |"
              % (s, len(raws[s]), format(l0[s], ","), format(k0, ","),
                 format(l1[s], ","), format(k1, ","),
                 100.0 * (l0[s] - l1[s]) / l0[s]))
    print("| **合计** | **%d** | **%s** | **%s** | **%s** | **%s** | **-%.0f%%** |"
          % (len(all0), format(t0, ","), format(tok0n, ","),
             format(t1, ","), format(tok1n, ","), 100.0 * (t0 - t1) / t0))

    # L3 首轮
    bl = raws["blbridge"]
    heaviest = max(bl, key=jb)
    inspect = jb(heaviest)
    hits = sum(len((t["name"] + " — " + (t.get("description") or "")[:70]).encode()) for t in bl[:3])
    l3 = mt + hits + inspect
    l3_tok, _ = ntok(mt_tools)
    l3_tok += int(round(hits / DIV))
    l3_tok += ntok(heaviest)[0]

    print("\n## L2 分组（blbridge 上游自带的机制）\n")
    print("| 组 | 工具数 | 字节 | %s |" % HEAD)
    print("|---|---:|---:|---:|")
    groups = {
        "core": ["bl_status", "bl_battle_status", "bl_start_battle", "bl_wait_for_state", "bl_abort",
                 "bl_order", "bl_control_agent", "bl_launch_game", "bl_skip_video", "bl_list_ui",
                 "bl_open_ui", "bl_close_ui", "bl_fast_forward", "bl_get_screen",
                 "bl_get_viewmodel_property", "bl_get_inventory", "bl_list_saves", "bl_load_save",
                 "bl_campaign_time", "bl_campaign_overview", "bl_list_kingdoms", "bl_list_clans",
                 "bl_list_settlements", "bl_list_parties", "bl_campaign_log"],
        "config": ["bl_read_config", "bl_apply_config", "bl_rts_config", "bl_apply_rts_config",
                   "bl_ghost_camera", "bl_camera_speed", "bl_cheat_mode"],
        "lab": ["bl_list_battles", "bl_analyze", "bl_read_events", "bl_run_batch", "bl_batch_report",
                "bl_lookup_troop", "bl_blockade", "bl_build_check", "bl_config", "bl_crash",
                "bl_patches", "bl_json_health", "bl_ipc_replay", "bl_exception_detail",
                "bl_concurrency_guide", "bl_mcm_settings", "bl_ui_extensions", "bl_exceptions",
                "bl_patch_failures"],
        "desktop": ["bl_desktop_windows", "bl_desktop_screenshot", "bl_desktop_click", "bl_desktop_key"],
        "4b": ["bl_status", "bl_crash", "bl_exceptions", "bl_patch_failures", "bl_list_battles",
               "bl_analyze", "bl_read_events", "bl_battle_status", "bl_start_battle",
               "bl_wait_for_state"],
    }
    by_name = {t["name"]: t for t in bl}
    for g, names in groups.items():
        sel = [by_name[n] for n in names if n in by_name]
        b = jb(sel)
        k, _ = ntok(sel)
        print("| `%s` | %d | %s | %s |" % (g, len(sel), format(b, ","), format(k, ",")))

    print("\n## 常驻成本对比\n")
    print("| 方案 | 常驻字节 | 常驻 token | 相对现状 | 工具可见性 |")
    print("|---|---:|---:|---:|---|")
    print("| L0 全量 | %s | %s | 100%% | 89 个全部可见 |"
          % (format(t0, ","), format(tok0n, ",")))
    print("| L1 全量瘦身 | %s | %s | %.0f%% | 89 个全部可见，说明变短 |"
          % (format(t1, ","), format(tok1n, ","), 100.0 * tok1n / tok0n))
    print("| L3 元工具（首轮实测口径） | %s | %s | **%.0f%%** | 元工具常驻，其余按需检索 |"
          % (format(l3, ","), format(l3_tok, ","), 100.0 * l3_tok / tok0n))

    print("\n## 各上下文窗口下的工具面占比\n")
    print("| 窗口 | L0 | L1 | L3 |")
    print("|---|---:|---:|---:|")
    for ctx in (32768, 131072, 262144):
        print("| %s | %.1f%% | %.1f%% | %.1f%% |"
              % (format(ctx, ","), 100.0 * tok0n / ctx, 100.0 * tok1n / ctx,
                 100.0 * l3_tok / ctx))

    out = {"divisor": DIV, "tokensExact": tok0x, "tokenizer": TOKENIZER_PATH,
           "convention": "compact JSON (separators=(',',':'))",
           "toolCount": len(all0), "l0": l0, "l1": l1,
           "l0Total": t0, "l1Total": t1, "l0Tokens": tok0n, "l1Tokens": tok1n,
           "metaBytes": mt, "metaTokens": ntok(mt_tools)[0],
           "l3FirstBytes": l3, "l3FirstTokens": l3_tok,
           "l3HeaviestTool": heaviest["name"],
           "l3Breakdown": {"meta": mt, "hits": hits, "inspect": inspect}}
    # ⚠️ `newline="\n"` 是刻意的：Windows 文本模式默认把 \n 转成 \r\n，
    #    而本项目编码纪律是 **LF**（否则每次跑都产生脏 diff）。
    with io.open(os.path.join(HERE, "layering_sim.json"), "w", encoding="utf-8",
                 newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("\n-> layering_sim.json")


if __name__ == "__main__":
    main()
