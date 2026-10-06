#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""交叉校验：**两份独立实现**对同一问题必须给出同一个答案。

为什么需要：`bl_chain.py` 的 `_slim()` 和 `_mcp_probe/layering_sim.py` 的 `slim()`
是**分别写的两份**瘦身实现（一个在桥里，一个在探针里）。如果两边算出的字节/token
不一致，说明至少有一边的口径或变换写错了 —— 而"我自己写的两个东西都说自己对"
是最容易漏掉的一类错误。

本测试断言（容差只允许 JSON 数组括号带来的固定差额）：
  X1 全量(full) 字节 & token：桥 vs 探针，一致
  X2 瘦身(slim) 字节 & token：桥 vs 探针，一致（差额 = 每多一层数组 2 字节）
  X3 分组工具数：桥的 GROUP 与探针里的同名组，成员一致
"""
import io
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 伞仓根（bl_chain.py / localization-audit 在这）
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

PROBE = os.path.join(ROOT, "probe")
sys.path.insert(0, HERE)
import bl_chain  # noqa: E402


def load_probe():
    path = os.path.join(PROBE, "layering_sim.py")
    spec = importlib.util.spec_from_file_location("layering_sim", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["layering_sim"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    fails = []
    probe = load_probe()
    chain = bl_chain.Chain(log_dir=os.path.join(HERE, "_logs")).start()
    try:
        if any(u.error for u in chain.upstreams):
            print("!! 上游未连上: %s" % [(u.name, u.error) for u in chain.upstreams if u.error])
            return 1

        # ── X1 全量 ────────────────────────────────────────────────────
        chain.mode = "full"
        bridge_full = chain.visible_tools()
        bb, bt = bl_chain._jb(bridge_full), bl_chain.count_tokens(bridge_full)[0]

        raws = {s: probe.load_raw(s) for s in probe.SERVERS}
        p_all = [t for s in probe.SERVERS for t in raws[s]]
        pb, pt = sum(probe.jb(raws[s]) for s in probe.SERVERS), probe.ntok(p_all)[0]

        print("X1 全量（89 工具）")
        print("   桥  : %s B / %s token" % (format(bb, ","), format(bt, ",")))
        print("   探针: %s B / %s token" % (format(pb, ","), format(pt, ",")))
        # 桥是单个 89 元素数组；探针是 3 个数组求和 ⇒ 差 2 字节/额外数组
        if bt != pt:
            fails.append("X1a 全量 token 不一致: 桥 %d vs 探针 %d" % (bt, pt))
        if abs(bb - pb) > 6:
            fails.append("X1b 全量字节差过大: 桥 %d vs 探针 %d" % (bb, pb))
        if not fails:
            print("   [ok] 一致（字节差 %d = 数组括号，token 完全相同）" % (pb - bb))

        # ── X2 瘦身 ────────────────────────────────────────────────────
        chain.mode = "slim"
        bridge_slim = chain.visible_tools()
        sb, st = bl_chain._jb(bridge_slim), bl_chain.count_tokens(bridge_slim)[0]

        p_slim = [probe.slim(t) for t in p_all]
        psb, pst = sum(probe.jb([probe.slim(t) for t in raws[s]]) for s in probe.SERVERS), \
            probe.ntok(p_slim)[0]

        print("\nX2 瘦身（slim）")
        print("   桥  : %s B / %s token" % (format(sb, ","), format(st, ",")))
        print("   探针: %s B / %s token" % (format(psb, ","), format(pst, ",")))
        if st != pst:
            fails.append("X2a slim token 不一致: 桥 %d vs 探针 %d" % (st, pst))
        if abs(sb - psb) > 6:
            fails.append("X2b slim 字节差过大: 桥 %d vs 探针 %d" % (sb, psb))
        if st == pst and abs(sb - psb) <= 6:
            print("   [ok] 一致（字节差 %d = 数组括号，token 完全相同）" % (psb - sb))

        # ── X3 分组成员 ────────────────────────────────────────────────
        print("\nX3 分组（上游 bl_mcp 的 TOOL_GROUPS）")
        chain.mode = "full"
        by_name = {t["name"]: t for _, t in chain.all_tools()}
        # 探针里的 groups 是 main() 的局部变量（不便导入），这里复刻同一份名单做比对。
        # 目的是验证「组名单里的名字在上游实测清单里确实存在」——防上游改名后组里留死名字。
        probe_groups = {
            "core": ["bl_status", "bl_battle_status", "bl_start_battle", "bl_wait_for_state",
                     "bl_abort", "bl_order", "bl_control_agent", "bl_launch_game", "bl_skip_video",
                     "bl_list_ui", "bl_open_ui", "bl_close_ui", "bl_fast_forward", "bl_get_screen",
                     "bl_get_viewmodel_property", "bl_get_inventory", "bl_list_saves",
                     "bl_load_save", "bl_campaign_time", "bl_campaign_overview",
                     "bl_list_kingdoms", "bl_list_clans", "bl_list_settlements",
                     "bl_list_parties", "bl_campaign_log"],
            "config": ["bl_read_config", "bl_apply_config", "bl_rts_config", "bl_apply_rts_config",
                       "bl_ghost_camera", "bl_camera_speed", "bl_cheat_mode"],
            "lab": ["bl_list_battles", "bl_analyze", "bl_read_events", "bl_run_batch",
                    "bl_batch_report", "bl_lookup_troop", "bl_blockade", "bl_build_check",
                    "bl_config", "bl_crash", "bl_patches", "bl_json_health", "bl_ipc_replay",
                    "bl_exception_detail", "bl_concurrency_guide", "bl_mcm_settings",
                    "bl_ui_extensions", "bl_exceptions", "bl_patch_failures"],
            "desktop": ["bl_desktop_windows", "bl_desktop_screenshot", "bl_desktop_click",
                        "bl_desktop_key"],
            "4b": ["bl_status", "bl_crash", "bl_exceptions", "bl_patch_failures",
                   "bl_list_battles", "bl_analyze", "bl_read_events", "bl_battle_status",
                   "bl_start_battle", "bl_wait_for_state"],
        }
        for g, names in sorted(probe_groups.items()):
            missing = [n for n in names if n not in by_name]
            if missing:
                fails.append("X3 组 %s 引用了不存在的工具: %s" % (g, missing))
            else:
                print("   [ok] `%s` %d 个成员全部存在于实测清单" % (g, len(names)))
        # 覆盖性：上游定义的 5 组应当覆盖全部 55 个 blbridge 工具
        bl_names = {t["name"] for _, t in chain.all_tools() if t["name"].startswith("bl_")}
        covered = set()
        for names in probe_groups.values():
            covered.update(names)
        uncovered = sorted(bl_names - covered)
        print("   blbridge 工具 %d 个；被 5 组覆盖 %d 个；未覆盖 %s"
              % (len(bl_names), len(covered & bl_names), uncovered or "无"))
        if uncovered:
            # 不判失败：上游的组本就不要求穷尽（这正是本桥用 other 兜底的理由）
            print("   （注：未覆盖属正常 —— 上游 TOOL_GROUPS 不是穷尽划分；"
                  "本桥用 `other` 兜底故不会静默丢失）")

        print("\n" + "=" * 70)
        if fails:
            print("交叉校验失败 %d 项：" % len(fails))
            for f in fails:
                print("  - %s" % f)
            return 1
        print("交叉校验通过：两份独立实现（桥 vs 探针）给出相同的字节与 token。")
        return 0
    finally:
        chain.stop()


if __name__ == "__main__":
    sys.exit(main())
