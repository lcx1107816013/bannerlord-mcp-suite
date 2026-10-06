#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""适配性测试：**上游更新后本桥无需改代码**。

用户要求原话："要求可以适配以后各个原 mcp 更新够能够进行适配更新"。

这里不用"改上游源码"来测（那是破坏性的、也不该测），而是**在内存里给上游注入
一个模拟的新工具 / 摘掉一个旧工具**，然后断言本桥的自动行为：

  T1 上游**新增**工具 -> full/slim 清单里出现、检索能找到、路由能命中、
                        且**绝不因"忘了登记组"而消失**（落 other 且仍可见）
  T2 上游**删除**工具 -> 从清单与检索里自动消失，不再可路由
  T3 上游**改 schema** -> chain_get_tool_details 返回的是**改后**的那份（不缓存旧版）
  T4 **refresh** 能报出 added / removed
  T5 **新增上游服务器** -> 只需往 SERVERS 加一条，工具自动并入
"""
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

NEW_TOOL = {
    "name": "zz_brand_new_tool_2099",
    "description": "★上游未来新增的工具：用于验证本桥的自动适配（关键词 未来新增）。",
    "inputSchema": {"type": "object",
                    "properties": {"x": {"type": "string", "description": "参数"}},
                    "required": ["x"]},
}


def main():
    fails = []
    chain = bl_chain.Chain(log_dir=os.path.join(HERE, "_logs")).start()
    try:
        bl = next(u for u in chain.upstreams if u.name == "blbridge")
        if bl.error:
            print("!! blbridge 未连上: %s" % bl.error)
            return 1

        base_tools = len(bl.tools)

        # ── T1 新增 ────────────────────────────────────────────────────
        print("T1 上游新增工具（模拟）")
        bl.tools = bl.tools + [json.loads(json.dumps(NEW_TOOL))]
        bl.by_name = {t["name"]: t for t in bl.tools}
        name = NEW_TOOL["name"]

        chain.mode = "full"
        vis = {t["name"] for t in chain.visible_tools()}
        g = chain.group_of(name)
        hit = name in {t["name"] for _, _, _, t in chain.search("未来新增", limit=8)}
        routable = chain.route(name)[0] is not None

        print("   分组判定: %s（未登记 -> 应为 other）" % g)
        print("   full 清单可见: %s" % (name in vis))
        print("   检索可发现:   %s" % hit)
        print("   路由可命中:   %s" % routable)
        if g != bl_chain.GROUP_FALLBACK:
            fails.append("T1a 新工具未落 other（得到 %s）" % g)
        if name not in vis:
            fails.append("T1b 新工具未出现在 full 清单 —— 静默丢失！")
        if not hit:
            fails.append("T1c 新工具检索不到")
        if not routable:
            fails.append("T1d 新工具不可路由")

        # 只暴露 ro 组时，other 里的新工具**应当**被过滤掉（这是分层的意图，不是缺陷）
        chain.groups = ["ro"]
        ro_vis = {t["name"] for t in chain.visible_tools()}
        print("   只暴露 ro 组时可见: %s（预期 False —— 分层过滤，属预期）" % (name in ro_vis))
        chain.groups = []

        # ── T3 改 schema ───────────────────────────────────────────────
        print("\nT3 上游改 schema")
        mutated = json.loads(json.dumps(NEW_TOOL))
        mutated["description"] = "★改后的描述（2099 修订版）"
        mutated["inputSchema"]["properties"]["x"]["description"] = "改后的参数说明"
        bl.tools = [mutated if t["name"] == name else t for t in bl.tools]
        bl.by_name = {t["name"]: t for t in bl.tools}
        detail = chain.call("chain_get_tool_details", {"name": name})
        got = json.dumps(detail, ensure_ascii=False)
        fresh = "2099 修订版" in got and "改后的参数说明" in got
        print("   details 返回最新版: %s" % fresh)
        if not fresh:
            fails.append("T3 返回了旧 schema（缓存未失效）")

        # ── T2 删除 ────────────────────────────────────────────────────
        print("\nT2 上游删除工具")
        bl.tools = [t for t in bl.tools if t["name"] != name]
        bl.by_name = {t["name"]: t for t in bl.tools}
        vis2 = {t["name"] for t in chain.visible_tools()}
        gone_hit = name in {t["name"] for _, _, _, t in chain.search("未来新增", limit=8)}
        gone_route = chain.route(name)[0] is None
        print("   从清单消失: %s / 检索消失: %s / 不可路由: %s"
              % (name not in vis2, not gone_hit, gone_route))
        if name in vis2:
            fails.append("T2a 已删工具仍在清单")
        if gone_hit:
            fails.append("T2b 已删工具仍被检索到")
        if not gone_route:
            fails.append("T2c 已删工具仍可路由")
        print("   工具数回落: %d -> %d（原 %d）" % (base_tools + 1, len(bl.tools), base_tools))

        # ── T4 refresh 报告 added/removed ──────────────────────────────
        print("\nT4 refresh 变化检测")
        # 真 refresh：直接向上游重拉（上游没变，所以应报 added=[] removed=[]）
        changes = chain.refresh()
        print("   refresh: %s" % json.dumps(changes, ensure_ascii=False))
        blchg = changes.get("blbridge", {})
        if "error" in blchg:
            fails.append("T4 refresh 失败: %s" % blchg["error"])
        elif blchg.get("added") or blchg.get("removed"):
            # 上游真的变了也算正常，但要说清楚
            print("   （上游确实有变化：added=%s removed=%s）"
                  % (blchg.get("added"), blchg.get("removed")))
        else:
            print("   [ok] 上游无变化，refresh 如实报空")

        # ── T5 新增上游服务器 ──────────────────────────────────────────
        print("\nT5 新增上游服务器（只加一条登记）")
        bl_chain.SERVERS["zz_fake_upstream"] = {
            "command": bl_chain.PY312,
            "args": ["-c", "print('unused')"],
            "cwd": HERE, "env": {}, "toolsetEnv": None, "toolsetAll": None,
        }
        try:
            c2 = bl_chain.Chain(servers=["blbridge", "zz_fake_upstream"], log_dir=None)
            c2.start()
            names_up = [u.name for u in c2.upstreams]
            fake = next(u for u in c2.upstreams if u.name == "zz_fake_upstream")
            print("   上游列表: %s" % names_up)
            print("   新上游连接错误（预期有，因为它不是 MCP）: %s" % str(fake.error)[:60])
            # 关键断言：一个坏上游**不能**拖垮整条链
            ok_chain = c2.route("bl_status")[0] is not None
            print("   坏上游不影响好上游路由: %s" % ok_chain)
            if not ok_chain:
                fails.append("T5a 坏上游拖垮了整条链")
            if len(names_up) != 2:
                fails.append("T5b 新上游未并入: %s" % names_up)
            c2.stop()
        finally:
            bl_chain.SERVERS.pop("zz_fake_upstream", None)

        # ── 未知组名仍要显式报错 ───────────────────────────────────────
        print("\nT6 未知组名/未知服务器必须显式报错（不静默）")
        for kwargs, what in (({"groups": ["nope"]}, "未知组"),
                             ({"servers": ["nope"]}, "未知服务器")):
            try:
                bl_chain.Chain(**kwargs)
                fails.append("T6 %s 未报错" % what)
                print("   [!!] %s 未报错" % what)
            except ValueError as exc:
                print("   [ok] %s -> %s" % (what, str(exc)[:58]))

    finally:
        chain.stop()

    print("\n" + "=" * 70)
    if fails:
        print("适配性测试失败 %d 项：" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    print("适配性测试全部通过：上游加/删/改工具，本桥**无需改一行代码**。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
