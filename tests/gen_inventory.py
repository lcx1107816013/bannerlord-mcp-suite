#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""生成交互链文档的**工具清单附录**（从实测数据生成，避免手抄出错）。

输出：tool_inventory.md —— 89 个工具的全表，含
    服务器 / 工具名 / 属性数 / 分层组 / 字节 / 估算token / 首句摘要
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 伞仓根（bl_chain.py / localization-audit 在这）
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

sys.path.insert(0, HERE)
import bl_chain  # noqa: E402

DIV = bl_chain.DIV
SRC = r"E:\Document\_mcp_probe"

REQUIRED = [
    # 查 bug / 诊断（最高频）
    "bl_status", "bl_crash", "bl_exceptions", "bl_patch_failures",
    "bl_exception_detail", "bl_json_health", "bl_ipc_replay", "bl_build_check",
    "bl_concurrency_guide", "bl_patches", "bl_mcm_settings", "bl_ui_extensions",
    # 战斗 / 遥测
    "bl_list_battles", "bl_analyze", "bl_read_events", "bl_battle_status",
    "bl_start_battle", "bl_wait_for_state", "bl_run_batch", "bl_batch_report",
    "bl_lookup_troop", "bl_blockade",
    # 资料库 / 源码
    "bannerlord_doctor", "bannerlord_index_status", "search_source",
    "read_csharp_type", "search_xml", "get_entity", "search_bannerlord_knowledge",
    "project_memory_read", "project_memory_write", "read_mod_file",
    # 汉化
    "bh_list_local_modules", "bh_identifier", "bh_generate_template",
    "bh_translate_module", "bh_create_external_translation", "bh_list_languages",
]


def main():
    chain = bl_chain.Chain(log_dir=os.path.join(HERE, "_logs")).start()
    try:
        bad = [(u.name, u.error) for u in chain.upstreams if u.error]
        if bad:
            print("!! 上游未连上: %s" % bad)
            return 1
        rows = []
        for u in chain.upstreams:
            for t in u.tools:
                b = bl_chain._jb(t)
                tk, exact = bl_chain.count_tokens(t)
                schema = t.get("inputSchema") or {}
                desc = (t.get("description") or "").replace("\n", " ").strip()
                rows.append({
                    "server": u.name, "name": t["name"],
                    "props": len(schema.get("properties") or {}),
                    "group": chain.group_of(t["name"]),
                    "bytes": b, "tok": tk,
                    "required": REQUIRED.__contains__(t["name"]),
                    "summary": desc[:96],
                })
        rows.sort(key=lambda r: (r["server"], -r["bytes"]))
        total = sum(r["bytes"] for r in rows)
        total_tok = sum(r["tok"] for r in rows)
        tok_exact = bl_chain._tokenizer() is not None

        out = []
        out.append("# 附录 A · 交互链工具清单（89 个，实测生成）\n")
        out.append("> 本附录由 `mcp-chain/gen_inventory.py` 从**实测** tools/list 生成，非手抄。")
        out.append("> 字节 = **compact JSON** 序列化长度（真正上线的形态）；")
        out.append("> token = %s。标记 ★ 的是「高频必备」清单内工具。\n"
                   % ("**真实 tokenizer**（Spark2.5, vocab 131072，与本机 4B 模型 GGUF 同 vocab）"
                      if tok_exact else "bytes/3.80 估算"))
        out.append("| 服务器 | 工具 | 属性 | 层 | 字节 | tok | 摘要 |")
        out.append("|---|---|---:|---|---:|---:|---|")
        for r in rows:
            # 只有用估算时才加 `~` 前缀 —— 真实 tokenizer 算出来的就不该带"约"
            tk = ("~%s" % format(r["tok"], ",")) if not tok_exact else format(r["tok"], ",")
            out.append("| `%s` | %s`%s` | %d | `%s` | %s | %s | %s |"
                       % (r["server"], "★ " if r["required"] else "", r["name"],
                          r["props"], r["group"], format(r["bytes"], ","),
                          tk, r["summary"].replace("|", "\\|")))
        out.append("| | | | | **%s** | **%s** | |"
                   % (format(total, ","), format(total_tok, ",")))

        # 每服务器小计
        out.append("\n## 每服务器小计\n")
        out.append("| 服务器 | 工具数 | 字节 | token | 必备工具数 |")
        out.append("|---|---:|---:|---:|---:|")
        for u in chain.upstreams:
            sel = [r for r in rows if r["server"] == u.name]
            out.append("| `%s` | %d | %s | %s | %d |"
                       % (u.name, len(sel), format(sum(x["bytes"] for x in sel), ","),
                          format(sum(x["tok"] for x in sel), ","),
                          sum(1 for x in sel if x["required"])))
        out.append("| **合计** | **%d** | **%s** | **%s** | **%d** |"
                   % (len(rows), format(total, ","), format(total_tok, ","),
                      sum(1 for r in rows if r["required"])))

        # 必备清单
        out.append("\n## 附录 B · 高频必备清单（%d 个）\n" % sum(1 for r in rows if r["required"]))
        out.append("按用途分组。这些是「mod 测试 / 查 bug / 汉化」日常真正会用的工具。\n")
        by_group = {}
        for r in rows:
            if r["required"]:
                by_group.setdefault(r["group"], []).append(r)
        for g in sorted(by_group):
            names = ", ".join("`%s`" % x["name"] for x in
                              sorted(by_group[g], key=lambda y: -y["bytes"]))
            b = sum(x["bytes"] for x in by_group[g])
            tk = sum(x["tok"] for x in by_group[g])
            out.append("- **`%s`**（%d 个 / %s token）：%s"
                       % (g, len(by_group[g]), format(tk, ","), names))

        missing = [n for n in REQUIRED if n not in {r["name"] for r in rows}]
        if missing:
            out.append("\n> ⚠️ 以下必备工具在实测清单里**不存在**（可能已改名/删除）：%s"
                       % ", ".join("`%s`" % m for m in missing))

        dest = os.path.join(HERE, "tool_inventory.md")
        with io.open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
        print("已生成 %s（%d 个工具，%s 字节）" % (dest, len(rows), format(total, ",")))
        if missing:
            print("!! 缺失必备工具: %s" % missing)
        return 0
    finally:
        chain.stop()


if __name__ == "__main__":
    sys.exit(main())
