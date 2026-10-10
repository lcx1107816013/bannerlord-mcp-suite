#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bl_chain —— 三个 MCP 服务器的**交互链聚合 / 分层桥**。

## 它解决什么问题

现状（实测，2026-10-06；字节 = compact JSON，token = **真实 tokenizer**）：

    blbridge          55 工具   58,444 B   15,591 tok
    bannerlordsage    24 工具   18,344 B    4,772 tok
    bannerlordhelper  10 工具    6,265 B    1,489 tok
    ─────────────────────────────────────────────────
    合计              89 工具   83,053 B   21,852 tok

在 32K 上下文的模型上，**工具面就吃掉 66.7%**；这是"读一次 token 越来越多"的根因。

## 设计前提（**已实测，不是推断**）

`test_hidden_call.py` 的对照实验证明：**被 `tools/list` 隐藏的工具，`tools/call` 照样能调。**

    BLBRIDGE_TOOLSET=4b   -> tools/list 只有 10 个（不含 bl_config）
    tools/call bl_config  -> isError=False，正常返回

⇒ **隐藏只影响「可发现性」，不影响「可调用性」。**
⇒ 分层因此可以是**无损**的：把工具移出常驻清单，再用检索元工具按需找回。

## 三层模型（对应官方 progressive discovery）

    L1 Catalog   常驻轻量元工具（search / details / call / status）
    L2 Inspect   按需取单个工具的完整 schema（原样转发，不裁剪）
    L3 Execute   调用（chain_call_tool，或直呼原始工具名）

## 与官方最佳实践的对应

官方（MCP Client Best Practices）警告：**中途增删 tools 数组会击穿前缀缓存**，
对策是 "route every call through a single stable `call_tool` meta-tool so the array
never changes"。本桥的 `meta` 模式正是这个形态：常驻工具集**恒定**，永不随对话变化。

## 无损保证（**两条独立判据，都可自测**）

| 模式 | 判据 | 测试 |
|---|---|---|
| `full` | 与上游**逐字节相同**（数组级 + 逐工具 deep-compare） | `--selftest` A/B 段 |
| `slim` | **行为契约逐字段不变**：剥掉 `description` 后 schema **完全相等**（`type`/`enum`/`default`/`required`/`additionalProperties`/嵌套），属性名集合与数量不变 | `slim_contract_test.py`（89/89） |
| `meta` | 常驻面只有元工具；**隐藏的工具仍可调** | `--selftest` C 段 + `e2e_test.py` |
| 协议面 | 每条消息符合**官方 SDK 自己的 zod schema** | `capture_wire.py` + `verify_schema.mjs` |

为什么 `slim` 不能只说"逐字节"：它**故意**截断说明文字。
所以改用**行为等价性** —— 决定行为的是 `type`/`enum`/`default`/`required`，
决定可读性的才是 `description`。省下的 41% **全部**是说明文字。

另外：**任何**模式下，**全部**上游工具都在路由表里，`chain_call_tool` 都调得到；
上游工具名**一律不改**（89 个名字实测无冲突），调用语义与直连完全一致。

## 适配上游更新（用户明确要求）

**不硬编码任何工具名或 schema。** 每次启动、以及 `chain_refresh` 时都现场向上游
`tools/list`，按实际结果建表：

| 上游变化 | 本桥行为 | 验证 |
|---|---|---|
| **加**工具 | 自动进入 `full`/`slim` 清单与检索索引；未登记组 → 落 `other` | `adapt_test` T1 |
| **删**工具 | 自动从清单消失；不再出现在检索结果里 | T2 |
| **改** schema | `chain_get_tool_details` 每次都转发上游**最新**那份，不缓存旧版 | T3 |
| **升级/重装** | `chain_refresh` 返回**新增/消失**名单 | T4 |
| **加**服务器 | 在 `SERVERS` 加一条即可 | T5 |
| 某上游**坏掉** | 只影响它自己，其他照常；响应里点名是哪个 | T5 |

⇒ 升级三个原 MCP 不需要改本文件（**schema 与路由**层面）。

### ⚠️ 但"加工具不必改本文件"只对**默认模式**成立（2026-10-10 修订）

原文写的是"未登记组 → 落 `other` 且**仍可见**" —— 这句**漏了前提**。
`other` 里的工具只在**不筛选**时可见；一旦有人设了 `DSH_CHAIN_GROUPS`，
"未登记"就等于"**从该视图消失**"。2026-10-10 实测（blbridge 一次新增 14 个工具）：

| 视图 | 工具面 | 那 14 个 |
|---|---|---|
| `full`（不筛选）| 115 | 可见 |
| `full` + `GROUPS=ro` | 60 | **全部消失** |

⇒ 所以 `TOOL_GROUPS` **是要跟着上游同步的**，它不是纯粹的"视图糖"。
自测 **I 段**（"自称只读的工具必须已登记"）就是为此立的**漂移守卫**：
上游加了自述"只读"的工具却忘了登记，它会**报红点名**。

## 为什么不用官方 MCP SDK

实测：本机沙箱下 `anyio.open_process` / `asyncio.create_subprocess_*` 会
`PermissionError [WinError 5]`（Windows 上 asyncio 子进程用**命名管道**，
沙箱禁止；同一边界在 Node 侧是 `spawn EPERM`），而朴素 `subprocess.Popen` 正常。
⇒ 本桥用 `subprocess.Popen` + 行式 JSON-RPC **自己实现 stdio 传输**，
**零第三方依赖**（不用 mcp / anyio / httpx），顺带也更抗上游 SDK 版本漂移。

⚠️ 正因为没用官方 SDK，协议面**必须另外证明** —— 见上面的
`capture_wire.py` + `verify_schema.mjs`（用第三方 schema 复核，
因为"自写客户端 + 自写服务端"有可能**一起错**）。

## 一键复现全部验证

    python run_all_tests.py       # 13 项；任何一项失败即非零退出

## 用法

    python bl_chain.py                 # stdio MCP 服务器（给 DSH 用）
    python bl_chain.py --selftest      # 自测：无损 / 完整 / 分层 / 检索 / 分组 / 真调用
    python bl_chain.py --measure       # 各模式实测字节与 token
    python bl_chain.py --stats         # 上游工具面统计（JSON）

## 环境变量

| 变量 | 默认 | 含义 |
|---|---|---|
| `DSH_CHAIN_MODE` | `full` | `full` \| `slim` \| `meta` \| `slim+meta` |
| `DSH_CHAIN_GROUPS` | 空（=全部） | 逗号/加号分隔的组名，见 `TOOL_GROUPS` |
| `DSH_CHAIN_SERVERS` | 空（=全部） | 只要这些上游服务器 |
| `DSH_CHAIN_DESC_CHARS` | `90` | slim 模式 description 截断字数 |
| `DSH_CHAIN_PROP_CHARS` | `40` | slim 模式属性说明截断字数 |
| `DSH_CHAIN_FAIL_ON_UPSTREAM` | `0` | `1` = 任一上游起不来就拒绝启动 |
| `DSH_CHAIN_CALL_TIMEOUT` | `300` | 单次上游调用超时（秒） |

## 口径纪律（★ 别在别处另算）

| 量 | 唯一正确算法 | 为什么 |
|---|---|---|
| 字节 | `_jb(obj)` = `json.dumps(obj, separators=(",", ":"))` 的 UTF-8 长度 | **compact 才是上线形态**（MCP 传输不插空格）。Python 默认插 `", "` 空格，blbridge 单这一项就多算 **1,529 B** |
| token | `count_tokens(obj)` → 真实 tokenizer（Spark2.5，vocab 131072，与本机 4B GGUF 同 vocab） | 实测 `bytes/token=3.80`；用早前的 3.44 会**高估约 10%**。装不到 `tokenizers` 才退回估算，并如实标 `exact=False` |

**别在别处再写 `json.dumps(...)` 或 `len(x)/3.44` 来报字节/token** —— 那两个数
本轮都已被实测纠正过（85,897→83,053、24,970→21,852）。

## 回退

**纯新增**：不启用本桥（把 DSH 配置改回直连三个服务器）即完全回退。
本桥**一个字节都不改上游**（上游全部以只读子进程方式使用）。
"""
import argparse
import difflib
import io
import json
import os
import subprocess
import sys
import threading
import time

# ── 上游服务器登记表 ────────────────────────────────────────────────────────
#
# 新增上游只需在这里加一条 —— 其余全部自动（建表、检索、路由、分层、状态）。

# 本桥自己的目录 —— 第 4 个上游（localization-audit）住在它下面。
# 用 `__file__` 而不是硬编码路径：本桥与那个上游是**同一个交付物**，
# 搬到哪里都该一起走（硬编码会在移动目录后静默失效）。
# ── 路径可配置化（伞仓）────────────────────────────────────────────────────
#
# ★ 为什么有这个块：本文件原来写死了本机绝对路径，别人 clone 后**一个上游都起不来**。
#   这不是"代码对不对"的问题，是**可配置性**问题 ⇒ 全部改成
#   「**环境变量优先，本机默认兜底**」。
#
# 设计取舍：`PY312` 的兜底用 `sys.executable`（跑本脚本的那个解释器）——
# 这最自然：谁跑本桥就用谁去起子进程，不假设 Python 装在哪。
#
# 设不了的环境变量**不静默**：`BUN` 找不到时会由上游启动失败如实报出
# （本桥的 `chain_status` 会点名是哪个上游 `connected: false`）。
_ENV = os.environ.get

PY312 = _ENV("DSH_CHAIN_PYTHON") or sys.executable

BUN = _ENV("DSH_CHAIN_BUN") or (
    r"C:\Users\LCGX\AppData\Local\Microsoft\WinGet\Packages"
    r"\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\bun-windows-x64\bun.exe")

GAME_DIR = _ENV("BANNERLORD_DIR") or (
    r"G:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

BLBRIDGE_DIR = _ENV("DSH_CHAIN_BLBRIDGE") or (
    r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge")

BANNERLORDSAGE_DIR = _ENV("DSH_CHAIN_SAGE") or r"F:\Program Files\BannerlordSage"

BANNERLORDHELPER_DIR = _ENV("DSH_CHAIN_HELPER") or r"F:\Program Files\Bannerlord.Helper"

# 真实 tokenizer（可选）：设了就用它精确计数；没设就退到 bytes/3.80 估算。
# ⚠️ 这是**度量**用的，不是功能依赖 ⇒ 缺了**绝不能报错**。
TOKENIZER_PATH = _ENV("DSH_CHAIN_TOKENIZER") or ""
# ──────────────────────────────────────────────────────────────────────────

CHAIN_DIR = os.path.dirname(os.path.abspath(__file__))

SERVERS = {
    "blbridge": {
        "command": PY312,
        "args": [os.path.join(BLBRIDGE_DIR, "tools", "bl_mcp.py")],
        "cwd": os.path.join(BLBRIDGE_DIR, "tools"),
        "env": {"PYTHONIOENCODING": "utf-8", "BANNERLORD_DIR": GAME_DIR},
        # 上游自带的工具集机制：显式设 all 拿全量，**分层统一由本桥做**。
        # 不设的话上游会用自己的默认值 ⇒ 本桥看到的面就不全 = 静默损失功能。
        "toolsetEnv": "BLBRIDGE_TOOLSET",
        "toolsetAll": "all",
    },
    "bannerlordsage": {
        "command": BUN,
        "args": ["run",
                 os.path.join(BANNERLORDSAGE_DIR, "src", "entrypoints", "bannerlord-full-stdio.ts")],
        "cwd": BANNERLORDSAGE_DIR,
        "env": {"BANNERSAGE_GAME": "bannerlord", "BANNERSAGE_EULA_ACCEPTED": "true",
                "BANNERSAGE_BANNERLORD_GAME_DIR": GAME_DIR},
        # ⚠️ 实测坑：bannerlord-full-stdio.ts 第 2 行是**硬赋值**
        #    `process.env.BANNERSAGE_TOOLSET = 'full'`（不是 `||=`），
        #    所以设环境变量无效，该入口恒为 24 个工具。
        "toolsetEnv": None,
        "toolsetAll": None,
    },
    "bannerlordhelper": {
        "command": BUN,
        "args": ["run", os.path.join(BANNERLORDHELPER_DIR, "mcp", "server.ts")],
        "cwd": BANNERLORDHELPER_DIR,
        # 凭据从宿主环境继承（NEXUS_API_KEY）：本桥**不打印、不落盘**任何凭据。
        "env": {},
        "toolsetEnv": None,
        "toolsetAll": None,
    },
    # ── 第 4 个上游：本项目**自研**的汉化审计（只读）────────────────────
    #
    # 为什么单独一个服务器，而不是塞进 blbridge 或 bannerlordhelper：
    #   · 塞 blbridge ⇒ 它是"操控游戏"，这俩是"审计汉化"，**语义错位**，
    #     且 blbridge 已 57 个工具（正是 chain 要消肿的对象）；
    #   · 塞 helper   ⇒ helper 是 **TypeScript**，这俩是 **Python**
    #     ⇒ 要引入跨语言调用，还要改 752 行的 server.ts；
    #   · 独立 ⇒ **零跨语言、零语义污染、许可完全自研**。
    #   ⚠️ 名字刻意用 `la_`（localization-audit）而**不是** `bh_` ——
    #      后者是 Bannerlord.**H**elper 的命名域，会让看名字的人误以为
    #      它属于那个 TS 服务器（实则毫无代码关系）。
    "localization-audit": {
        "command": PY312,
        "args": [os.path.join(CHAIN_DIR, "localization-audit", "la_mcp.py")],
        "cwd": os.path.join(CHAIN_DIR, "localization-audit"),
        # 只读工具：不需要 key、不需要网络、不需要游戏在跑。
        "env": {"PYTHONIOENCODING": "utf-8", "BANNERLORD_DIR": GAME_DIR},
        "toolsetEnv": None,
        "toolsetAll": None,
    },
}

# ── 分层分组 ────────────────────────────────────────────────────────────────
#
# 组是**视图**，不是权限：任何组里的工具都仍可通过 chain_call_tool 调到。
# 成员按工具名枚举，但**没列到的名字一律落进 GROUP_FALLBACK 且仍然可见** ——
# 所以上游加工具时不会因为"忘了加到组里"而静默消失（这是与上游那份硬编码
# TOOL_GROUPS 最关键的差别：那份漏一个名字，工具就凭空不见了）。
#
# ⚠️ 但"仍然可见"只对**不筛选**的模式成立（`full`/`slim`）。一旦有人设了
#    `DSH_CHAIN_GROUPS`，未登记的工具就**进不了任何被选中的组** ⇒ 在该视图里
#    消失。2026-10-10 实测确认（blbridge v0.8.57 新增 14 个工具全部未登记）：
#        full + DSH_CHAIN_GROUPS=ro                        → 60 个，我的 14 个**全丢**
#        full + DSH_CHAIN_GROUPS=ro,battle,write,launch,desktop → 91 个，仍**全丢**
#    ⇒ 所以"上游加工具不必改本表"这个说法**只在默认模式下成立**。
#    本表因此**需要随上游更新**，并由自测 I 段（对账上游真表）守住漂移。
TOOL_GROUPS = {
    "ro": {
        "desc": ("只读观测：状态 / 崩溃 / 异常 / 补丁 / 日志 / 索引 / 战役与世界读 / "
                 "观察者事件 / 存档与交战现状 / 遭遇选项读"),
        "names": [
            "bl_status", "bl_battle_status", "bl_crash", "bl_exceptions",
            "bl_patch_failures", "bl_list_battles", "bl_analyze", "bl_read_events",
            "bl_read_config", "bl_rts_config", "bl_config", "bl_build_check",
            "bl_json_health", "bl_ipc_replay", "bl_exception_detail",
            "bl_concurrency_guide", "bl_mcm_settings", "bl_ui_extensions",
            "bl_patches", "bl_get_screen", "bl_get_viewmodel_property",
            "bl_get_inventory", "bl_list_saves", "bl_campaign_time",
            "bl_campaign_overview", "bl_list_kingdoms", "bl_list_clans",
            "bl_list_settlements", "bl_list_parties", "bl_campaign_log",
            "bl_list_ui", "bl_lookup_troop", "bl_blockade", "bl_desktop_windows",
            "bannerlord_index_status", "bannerlord_doctor", "mod_source_status",
            "project_memory_read", "read_file", "list_directory", "search_xml",
            "search_source", "search_bannerlord_knowledge", "search_bannerlord_docs",
            "search_bannerlord_api_docs", "get_entity", "read_csharp_type",
            "read_gauntlet_ui", "resolve_localization", "read_mod_file",
            "read_mod_type", "list_mod_directory", "search_mod_source",
            "bh_list_languages", "bh_resolve_language", "bh_list_local_modules",
            "bh_search_nexusmods", "bh_module_details",
            # 第 4 个上游（localization-audit）：**只读**审计。
            # ⚠️ 必须在这里列名，否则会落进 GROUP_FALLBACK（仍可见，但组视图里
            #    "按只读筛选"时会漏掉它 —— 那正是人们找审计工具的方式）。
            "la_audit_coverage", "la_dll_strings",
            # ── v0.8.57 补登（2026-10-10）────────────────────────────────
            # blbridge 本轮新增/此前遗漏的**只读**工具。归类依据 = 各自描述里
            # 声明的语义（"只读"/"只扫描不改"/"读…"），逐条核过：
            "bl_observer_status",   # 观察者状态/计数/丢弃数（只读）
            "bl_observer_events",   # 读最近战役事件（事件驱动，非快照）
            "bl_war_status",        # 列当前交战王国对（造刺激前先看现状）
            "bl_save_status",       # 是否正在存盘 + 存档清单（只读）
            "bl_conversation",      # 读当前遭遇/对话的可选项（★ 只列选项，不替调用方选）
            "bl_get_hero",          # 读英雄运行时血量（只读）
            "bl_get_perk",          # 读 Perk 运行时生效值（只读）
            "bl_scan_bad_data",     # 坏数据**只扫描、不改任何数据**
            "bl_crashguard",        # 读崩溃守卫账本（诊断族，与 bl_crash 同类）
            "bl_source_map",        # 栈帧 → 源码位置（取证）
            "bl_save_diag",         # 存档诊断（宿主侧，只读）
            "bl_report",            # 崩溃报告导出（宿主侧，只读）
            "bl_lexicon",           # 崩溃词典查询（人话解释）
            "bl_dump",              # 让游戏进程写 minidump（**取证动作，不改游戏状态**；
                                    #   与已在本组的 bl_crash 同族）
        ],
    },
    "battle": {
        "desc": "战斗：开战 / 等待 / 改令 / 接管 / 加速 / 中止 / 批量跑",
        "names": [
            "bl_start_battle", "bl_wait_for_state", "bl_abort", "bl_order",
            "bl_control_agent", "bl_fast_forward", "bl_run_batch", "bl_batch_report",
        ],
    },
    "write": {
        "desc": ("写：改配置 / 改相机 / 载入存档 / 汉化产物 / 建工程 / 生成补丁 / "
                 "战役刺激（宣战·议和·时间流速·存档·回主菜单）/ 对话选择 / 受控崩溃"),
        "names": [
            "bl_apply_config", "bl_apply_rts_config", "bl_ghost_camera",
            "bl_camera_speed", "bl_cheat_mode", "bl_load_save",
            "bh_identifier", "bh_generate_template", "bh_translate_module",
            "bh_create_external_translation", "bh_run_cli",
            "create_mod_workspace", "generate_xslt_patch", "generate_harmony_patch",
            "index_mod_source", "project_memory_write",
            # ── v0.8.57 补登（2026-10-10）：**会改状态**的战役工具 ──────────
            # ⚠️ 判据：这些都会真实改变游戏/存档状态，**不能**混进 ro
            #    （否则"只读筛选"会给出一个会改存档的工具面，方向性错误）。
            "bl_declare_war",        # ★ 真实改变外交关系（会改存档）
            "bl_make_peace",         # 真实议和（会改存档）
            "bl_campaign_time_speed",# 改时间流速（等价于点倍速键）
            "bl_save_game",          # 持久化（写盘）
            "bl_return_to_menu",     # 卸载战役（跨帧待办）
            "bl_conversation_choose",# ★ 选项后果**不可逆**（掉钱/开战/损兵）
            "bl_conversation_continue",  # 推进对话（改变对话状态机）
            "bl_observer_config",    # 改观察者运行时开关（与 bl_apply_config 同类）
            "bl_observer_clear",     # 清空观察者缓冲（改运行时状态）
            "bl_crash_test",         # ★ **受控崩溃：游戏会真的崩掉**（破坏性最强）
        ],
    },
    "launch": {
        "desc": "起游戏 / 跳过场 / 进出界面",
        "names": ["bl_launch_game", "bl_skip_video", "bl_open_ui", "bl_close_ui"],
    },
    "desktop": {
        "desc": "桌面自动化：列窗口 / 截图 / 点击 / 按键",
        "names": ["bl_desktop_screenshot", "bl_desktop_click", "bl_desktop_key"],
    },
}
GROUP_FALLBACK = "other"   # 未登记的工具落这里，**仍然可见**（绝不静默隐藏）

# ★ 兜底组必须**可选**（2026-10-10 修的真缺陷）。
#
# ## 缺陷形态
# `stats()` 会把 GROUP_FALLBACK 连同 TOOL_GROUPS 一起**报给用户**
# （`out["groups"] = {... for g in list(TOOL_GROUPS) + [GROUP_FALLBACK]}`）⇒
# 用户在 `chain_status` 里**看得见 `other` 这个组名**。但 `DSH_CHAIN_GROUPS`
# 的校验只认 `TOOL_GROUPS` 的键 ⇒ 用户照着报出来的名字填 `other`，得到：
#     ValueError: DSH_CHAIN_GROUPS 含未知组名: other（可用: battle, desktop, launch, ro, write）
# ⇒ **"报出来的组名"与"能选中的组名"不一致** —— 报了却不给用。
# 而 `other` 恰恰是"未登记工具的落点"，最可能有人想单独看它（"有没有工具漏登记"）。
#
# ## 修法
# 把兜底组升格成 TOOL_GROUPS 里的**真组**（空 names，由 group_of 兜底填充）。
# 这样校验自然放行，且 `names` 为空不会与兜底逻辑冲突（group_of 优先查
# TOOL_GROUPS，`other` 里没有名字 ⇒ 未登记工具仍按 GROUP_FALLBACK 归到它）。
TOOL_GROUPS[GROUP_FALLBACK] = {
    "desc": "未登记的工具（落点兜底）：名字没被上面任何一组列到的工具都在这里",
    "names": [],
}

# ── 检索用的「用户词汇 → 英文词干」同义词表 ─────────────────────────────────
#
# 为什么需要：工具名是英文（bl_start_battle），而用户/模型常用中文提问（"开战"）。
# 实测踩到过：查"开战"时 `bl_start_battle` **排不进前 6** —— 因为它的 description
# 写的是"开一场战斗"，字面上并不含"开战"这个子串。
#
# ⚠️ 这张表映射的是**词汇**，不是工具名 —— 所以它与上游更新无关：
#    上游加/改工具都不需要动它，它只是把一种说法翻译成另一种说法再去做子串匹配。
#    刻意只收高频领域词，不做成穷尽词典（宁可漏，不可乱）。
SYNONYMS = {
    "开战": ["start", "battle"], "战斗": ["battle"], "打一场": ["start", "battle"],
    "推演": ["battle", "mission"], "对局": ["battle"],
    "崩溃": ["crash", "dump"], "闪退": ["crash"],
    "异常": ["exception"], "报错": ["exception", "error"],
    "补丁": ["patch", "harmony"], "汉化": ["translat", "template", "language"],
    "翻译": ["translat"], "本地化": ["localization", "language"],
    "兵种": ["troop"], "部队": ["party", "troop"], "军团": ["troop", "legionary"],
    "存档": ["save"], "读档": ["load", "save"],
    "截图": ["screenshot"], "相机": ["camera"], "视角": ["camera", "ghost"],
    "配置": ["config"], "设置": ["config", "settings"],
    "状态": ["status"], "日志": ["log", "events"],
    "家族": ["clan"], "王国": ["kingdom"], "城": ["settlement", "town"],
    "城镇": ["settlement", "town"], "村庄": ["settlement", "village"],
    "战役": ["campaign"], "地图": ["campaign", "map"],
    "库存": ["inventory"], "物品": ["inventory", "item"],
    "界面": ["ui", "screen"], "菜单": ["ui", "menu"],
    "桌面": ["desktop"], "窗口": ["window", "desktop"],
    "索引": ["index"], "源码": ["source", "csharp"], "反编译": ["csharp", "type"],
    "文档": ["docs", "knowledge"], "资料": ["docs", "knowledge", "entity"],
    "记忆": ["memory"], "工作区": ["workspace"], "模组": ["mod"],
    "关隘": ["blockade"], "并发": ["concurrency"], "超时": ["timeout"],
    "刷新": ["refresh"], "巡检": ["doctor", "health"],
    "数据表": ["xml", "entity"], "技能": ["perk", "skill"], "政策": ["policy"],
    # 第 4 个上游（localization-audit）的领域词。
    # ★ 为什么必须加：这两个工具的名字是 `la_audit_coverage` / `la_dll_strings`
    #   —— **字面上完全不含"汉化""翻译""缺"**。不映射的话，
    #   用中文搜"汉化缺键"会**搜不到审计工具**（实测本项目踩过同类坑：
    #   `开战` 搜不到 `bl_start_battle`，因为它的描述写的是"开一场战斗"）。
    "缺键": ["audit", "coverage", "missing"],
    "缺翻译": ["audit", "coverage"], "缺口": ["audit", "coverage"],
    "硬编码": ["dll", "strings"], "硬编码字符串": ["dll", "strings"],
    "审计": ["audit", "coverage"], "体检": ["doctor", "audit", "health"],
    "英文残留": ["dll", "strings"], "界面英文": ["dll", "strings"],
    "程序集": ["dll", "assembly"], "字符串": ["strings", "dll"],
}

DIV = 3.80                 # 回退用估算系数：**实测校准值**（见下）
#
# ## 关于 token 口径（★ 别再用 3.44）
#
# 本项目此前用 bytes/3.44 估算。本轮用**真实 tokenizer** 校准了：
#   E:\Document\spark-heretic\model\tokenizer.json（Spark2.5，vocab 131072）
# 并验证它与用户 4B 模型的 GGUF **vocab 一致**（都是 131072）⇒ 对该模型的
# token 数**是权威的，不是近似**。
#
# 实测结果（compact JSON 口径）：全量工具面 83,051 B / **21,848 真实 token**
# ⇒ bytes/token = **3.80**。所以 3.44 会**高估约 10%**。
#
# 本模块优先用真实 tokenizer；装不到时退回 bytes/3.80（比 3.44 准）。

_TOKENIZER = None
_TOKENIZER_TRIED = False

def _tokenizer():
    """懒加载真实 tokenizer；失败返回 None（不抛，退回估算）。"""
    global _TOKENIZER, _TOKENIZER_TRIED
    if _TOKENIZER_TRIED:
        return _TOKENIZER
    _TOKENIZER_TRIED = True
    try:
        from tokenizers import Tokenizer
        _TOKENIZER = Tokenizer.from_file(TOKENIZER_PATH)
    except Exception:  # noqa: BLE001
        _TOKENIZER = None
    return _TOKENIZER

def count_tokens(obj):
    """返回 (tokens, exact)。exact=True 表示用了真实 tokenizer。"""
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    tok = _tokenizer()
    if tok is not None:
        return len(tok.encode(payload, add_special_tokens=False).ids), True
    return int(round(len(payload.encode("utf-8")) / DIV)), False

PROTOCOL_VERSION = "2024-11-05"

def _jb(o):
    """字节数 —— 用 **compact JSON**（`separators=(",", ":"")`）。

    为什么必须 compact：这是**真正上线**的形态（MCP 传输不插空格），
    也是 JS `JSON.stringify` 的默认行为。Python `json.dumps` 默认会在
    `", "` / `": "` 插空格 ⇒ 同一份工具面会**多算 1,529 字节**（blbridge 实测）。
    早期版本混用了两种口径（Python 默认 59,973 vs JS compact 58,444），
    本函数是**唯一**字节口径，别在别处再写 json.dumps 算长度。
    """
    return len(json.dumps(o, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))

def _is_cjk(s):
    """是否含中日韩字符（用于决定要不要走同义词展开）。"""
    return any("\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff"
               for ch in s or "")

def _env_list(var, lower=False):
    raw = (os.environ.get(var) or "").strip()
    if not raw:
        return []
    out = []
    for x in raw.replace("+", ",").split(","):
        x = x.strip()
        if x:
            out.append(x.lower() if lower else x)
    return out

# ══════════════════════════════════════════════════════════════════════════
# 上游连接（自实现的 stdio JSON-RPC 传输，零依赖）
# ══════════════════════════════════════════════════════════════════════════

class UpstreamError(Exception):
    pass

class Upstream:
    """一个上游 MCP 服务器：子进程 + 行式 JSON-RPC。

    传输细节（实测三个上游都一样）：**一行一个 JSON**，不是 Content-Length 头。
    stderr 重定向到文件而不是管道 —— 管道写满会让上游阻塞（经典死锁）。
    """

    def __init__(self, name, cfg, log_dir=None):
        self.name = name
        self.cfg = cfg
        self.tools = []
        self.by_name = {}
        self.error = None
        self.server_info = None
        self.capabilities = None
        self.proc = None
        self._id = 0
        self._lock = threading.Lock()
        self._err_path = None
        self._log_dir = log_dir
        self.tools_fingerprint = None

    # ── 环境 ───────────────────────────────────────────────────────────
    def _env(self):
        env = dict(os.environ)
        env.update(self.cfg.get("env") or {})
        te, tall = self.cfg.get("toolsetEnv"), self.cfg.get("toolsetAll")
        if te and tall:
            env[te] = tall
        elif te:
            env.pop(te, None)
        return env

    # ── 生命周期 ───────────────────────────────────────────────────────
    def connect(self, timeout=120.0):
        """起子进程 + initialize + tools/list。失败**不抛**，记在 self.error。"""
        try:
            err_target = subprocess.DEVNULL
            if self._log_dir:
                try:
                    os.makedirs(self._log_dir, exist_ok=True)
                    self._err_path = os.path.join(self._log_dir, "upstream-%s.err.log" % self.name)
                    # 二进制追加，避免编码问题
                    err_target = open(self._err_path, "ab")
                except OSError:
                    err_target = subprocess.DEVNULL
            self.proc = subprocess.Popen(
                [self.cfg["command"]] + list(self.cfg.get("args") or []),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err_target,
                env=self._env(), cwd=self.cfg.get("cwd"), bufsize=0,
            )
        except Exception as exc:  # noqa: BLE001
            self.error = "启动失败 %s: %r" % (type(exc).__name__, exc)
            return self

        try:
            res = self._request("initialize", {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "blchain", "version": "1.0.0"},
            }, timeout=timeout)
            self.server_info = (res or {}).get("serverInfo")
            self.capabilities = (res or {}).get("capabilities")
            self._notify("notifications/initialized")
            listing = self._request("tools/list", {}, timeout=timeout)
            self.tools = list((listing or {}).get("tools") or [])
            self.by_name = {t["name"]: t for t in self.tools}
            self.tools_fingerprint = _fingerprint(self.tools)
        except Exception as exc:  # noqa: BLE001
            self.error = "%s: %s" % (type(exc).__name__, exc)
        return self

    def close(self):
        p = self.proc
        if p is None:
            return
        try:
            if p.stdin:
                p.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            p.wait(timeout=5)
        except Exception:  # noqa: BLE001
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass

    # ── 协议 ───────────────────────────────────────────────────────────
    def _send(self, obj):
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        self.proc.stdin.write(line.encode("utf-8"))
        self.proc.stdin.flush()

    def _notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method,
                    **({"params": params} if params else {})})

    def _read_msg(self):
        raw = self.proc.stdout.readline()
        if not raw:
            raise UpstreamError("上游 %s 关闭了 stdout（进程退出码 %s）"
                                % (self.name, self.proc.poll()))
        try:
            return json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            # 非 JSON 行（部分服务器会往 stdout 打日志）—— 跳过而不是炸掉
            return None

    def _request(self, method, params, timeout=300.0):
        with self._lock:
            self._id += 1
            rid = self._id
            self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.proc.poll() is not None and not self._peek_ready():
                    raise UpstreamError("上游 %s 已退出（exit=%s）"
                                        % (self.name, self.proc.returncode))
                msg = self._read_msg()
                if msg is None:
                    continue
                if msg.get("id") != rid:
                    continue          # 通知或旧响应，丢弃
                if "error" in msg:
                    raise UpstreamError("上游 %s 报错: %s"
                                        % (self.name, msg["error"].get("message")))
                return msg.get("result")
            raise UpstreamError("上游 %s 超时（%ss，method=%s）"
                                % (self.name, timeout, method))

    def _peek_ready(self):
        try:
            return bool(self.proc.stdout.peek(0))
        except Exception:  # noqa: BLE001
            return False

    def call(self, name, args, timeout=300.0):
        return self._request("tools/call", {"name": name, "arguments": args or {}},
                             timeout=timeout)

    def refresh_tools(self):
        """重新拉工具表（上游更新后调用）。返回 (新增, 消失) 名字列表。"""
        old = set(self.by_name)
        listing = self._request("tools/list", {}, timeout=120.0)
        self.tools = list((listing or {}).get("tools") or [])
        self.by_name = {t["name"]: t for t in self.tools}
        self.tools_fingerprint = _fingerprint(self.tools)
        new = set(self.by_name)
        return sorted(new - old), sorted(old - new)

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

def _fingerprint(tools):
    """工具面指纹：只取 name+description+schema 的稳定摘要，用于变化检测。"""
    import hashlib
    h = hashlib.sha256()
    for t in sorted(tools, key=lambda x: x.get("name", "")):
        h.update(json.dumps(t, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return h.hexdigest()[:16]

# ══════════════════════════════════════════════════════════════════════════
# 交互链
# ══════════════════════════════════════════════════════════════════════════

class Chain:
    """三个上游 + 分层视图 + 路由。全部同步（沙箱下 asyncio 子进程不可用）。"""

    def __init__(self, servers=None, mode=None, groups=None, log_dir=None):
        want = servers if servers is not None else _env_list("DSH_CHAIN_SERVERS")
        names = want or list(SERVERS)
        unknown_srv = [n for n in names if n not in SERVERS]
        if unknown_srv:
            raise ValueError("DSH_CHAIN_SERVERS 含未知服务器: %s（可用: %s）"
                             % (", ".join(unknown_srv), ", ".join(sorted(SERVERS))))
        self.upstreams = [Upstream(n, SERVERS[n], log_dir=log_dir) for n in names]
        self.mode = (mode or os.environ.get("DSH_CHAIN_MODE", "full")).strip().lower()
        if self.mode not in ("full", "slim", "meta", "slim+meta"):
            raise ValueError("DSH_CHAIN_MODE 非法: %r（可用: full/slim/meta/slim+meta）"
                             % self.mode)
        g = groups if groups is not None else _env_list("DSH_CHAIN_GROUPS", lower=True)
        unknown = [x for x in g if x not in TOOL_GROUPS]
        if unknown:
            raise ValueError("DSH_CHAIN_GROUPS 含未知组名: %s（可用: %s）"
                             % (", ".join(unknown), ", ".join(sorted(TOOL_GROUPS))))
        self.groups = g
        self.desc_chars = int(os.environ.get("DSH_CHAIN_DESC_CHARS", "90"))
        self.prop_chars = int(os.environ.get("DSH_CHAIN_PROP_CHARS", "40"))
        self.call_timeout = float(os.environ.get("DSH_CHAIN_CALL_TIMEOUT", "300"))

    # ── 连接 ───────────────────────────────────────────────────────────
    def start(self):
        for u in self.upstreams:
            u.connect()
        if os.environ.get("DSH_CHAIN_FAIL_ON_UPSTREAM") == "1":
            bad = [(u.name, u.error) for u in self.upstreams if u.error]
            if bad:
                raise RuntimeError("上游连接失败: %s" % bad)
        return self

    def stop(self):
        for u in reversed(self.upstreams):
            u.close()

    def refresh(self):
        """重新拉所有上游工具表（上游更新后调用）。"""
        out = {}
        for u in self.upstreams:
            if not u.alive():
                u.error = "进程已退出"
                out[u.name] = {"error": u.error}
                continue
            try:
                added, gone = u.refresh_tools()
                u.error = None
                out[u.name] = {"added": added, "removed": gone,
                               "tools": len(u.tools)}
            except Exception as exc:  # noqa: BLE001
                out[u.name] = {"error": "%s: %s" % (type(exc).__name__, exc)}
        return out

    # ── 工具表 ─────────────────────────────────────────────────────────
    def all_tools(self):
        """全部上游工具（**原样**引用），带归属服务器标注。"""
        out = []
        for u in self.upstreams:
            for t in u.tools:
                out.append((u.name, t))
        return out

    def route(self, name):
        for u in self.upstreams:
            if name in u.by_name:
                return u, u.by_name[name]
        return None, None

    def group_of(self, name):
        for g, spec in TOOL_GROUPS.items():
            if name in spec["names"]:
                return g
        return GROUP_FALLBACK

    def active_names(self):
        """当前视图暴露的上游工具名集合；None = 不过滤。"""
        names = {t["name"] for _, t in self.all_tools()}
        if self.groups:
            names = {n for n in names if self.group_of(n) in self.groups}
        if self.mode in ("meta", "slim+meta"):
            return None if False else set()   # meta：上游工具全部移出常驻面
        return names

    # ── 视图变换 ───────────────────────────────────────────────────────
    def _slim(self, t):
        """L1 瘦身：**只截断说明文字**；type/enum/default/required 一律不动。

        刻意的边界：说明文字影响"模型看不看得懂"，type/enum 影响"行为对不对"。
        只动前者 ⇒ 行为等价性可以用逐字段比对证明（见 --selftest 的 A 段）。
        """
        out = {"name": t["name"]}
        desc = (t.get("description") or "").strip()
        head = desc.split("\n\n")[0].strip()
        if "。" in head:
            head = head.split("。")[0].strip() + "。"
        if len(head) > self.desc_chars:
            head = head[:self.desc_chars].rstrip() + "…"
        out["description"] = head

        schema = json.loads(json.dumps(t.get("inputSchema") or {}))
        props = schema.get("properties")
        if isinstance(props, dict):
            for spec in props.values():
                if isinstance(spec, dict) and isinstance(spec.get("description"), str):
                    d = spec["description"]
                    if len(d) > self.prop_chars:
                        spec["description"] = d[:self.prop_chars].rstrip() + "…"
        out["inputSchema"] = schema
        return out

    def visible_tools(self):
        """当前模式下真正进模型上下文的工具定义。"""
        names = self.active_names()
        tools = []
        for _, t in self.all_tools():
            if names is not None and t["name"] not in names:
                continue
            tools.append(self._slim(t) if self.mode in ("slim", "slim+meta") else t)
        if self.mode in ("meta", "slim+meta"):
            tools = self.meta_tools()
        return tools

    # ── 元工具（L1 Catalog）───────────────────────────────────────────
    @staticmethod
    def meta_tools():
        return [
            {
                "name": "chain_search_tools",
                "description": (
                    "按关键词检索**全部**已注册工具（三个 MCP 服务器合计近百个）。"
                    "返回 name + 一行摘要 + 所属层。用它替代「把全部工具定义塞进上下文」。"
                    "命中后先 chain_get_tool_details 看完整参数，再 chain_call_tool 调用。"),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string",
                                  "description": "关键词，如 崩溃/开战/汉化/nexus/兵种/崩溃转储"},
                        "group": {"type": "string",
                                  "description": "可选：只在某一层检索（ro/battle/write/launch/desktop/other）"},
                        "limit": {"type": "integer", "default": 6},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "chain_get_tool_details",
                "description": (
                    "取单个工具的**完整** inputSchema（原样转发上游，不做任何裁剪）。"
                    "调用任何工具前先看这个 —— 尤其属性多、枚举多的（如 bl_start_battle 32 个属性）。"),
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "工具名"}},
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "chain_call_tool",
                "description": (
                    "调用工具：{name, args}。**name 可以是任何已注册工具**，不限于检索过的 —— "
                    "本桥的常驻工具集因此恒定，不会中途变化而击穿前缀缓存。"
                    "参数语义与直连上游完全一致（工具名一字不改）。"),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "工具名（如 bl_start_battle）"},
                        "args": {"type": "object", "description": "该工具的参数对象"},
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "chain_status",
                "description": (
                    "交互链自检：每个上游是否连上、各暴露多少工具、当前分层模式、"
                    "各模式实测字节与 token、以及各上游工具面的**指纹**（用于发现上游更新）。"),
                "inputSchema": {"type": "object", "properties": {},
                                "additionalProperties": False},
            },
            {
                "name": "chain_refresh",
                "description": (
                    "重新向上游拉取工具表，返回**新增/消失**的工具名。"
                    "上游 MCP **新增/删除工具**后调它，无需重启本桥。"
                    "⚠️ 它**只重拉上游工具表**，不重新加载本桥自己的代码 —— "
                    "改了 `bl_chain.py` 自身（如 `TOOL_GROUPS` 分组表）**必须重启本桥**才生效，"
                    "调本工具**不会**让新分组生效（本工具自身读到的是进程启动时载入的那份模块）。"),
                "inputSchema": {"type": "object", "properties": {},
                                "additionalProperties": False},
            },
        ]

    def expand_terms(self, query):
        """把查询拆成检索词，并**额外**加上中文领域词的英文同义词（见 SYNONYMS）。

        为什么**不能**丢掉中文词：三个上游里有大量中文描述（BlBridge 尤其），
        描述里字面含有查询词的命中是**最精确**的信号 —— 早期版本把中文词过滤掉，
        结果"一个描述里明明写着『未来新增』的新工具"检索不到（adapt_test T1c 实测抓到）。
        所以这里保留原词（权重 1.0），同义词只做**补充**（权重 0.6）。
        """
        raw = (query or "").strip().lower()
        for sep in ("，", ",", "、", "/", "|"):
            raw = raw.replace(sep, " ")
        terms = [x for x in raw.split() if x]
        expanded = [(t, 1.0) for t in terms]
        for term in terms:
            for syn in SYNONYMS.get(term, []):
                expanded.append((syn, 0.6))
        # 中文没空格时（"怎么开战"/"未来新增"）做一次子串包含检查
        if terms and all(_is_cjk(t) for t in terms):
            for key, syns in SYNONYMS.items():
                if key in raw and key not in terms:
                    expanded.append((key, 1.0))
                    for syn in syns:
                        expanded.append((syn, 0.6))
        # 去重（保留最高权重）
        best = {}
        for t, w in expanded:
            if t and w > best.get(t, 0.0):
                best[t] = w
        return sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))

    def search(self, query, group=None, limit=6):
        terms = self.expand_terms(query)
        rows = []
        for server, t in self.all_tools():
            name = t["name"]
            g = self.group_of(name)
            if group and g != group:
                continue
            desc = t.get("description") or ""
            hay_name, hay_desc = name.lower(), desc.lower()
            gdesc = TOOL_GROUPS[g]["desc"].lower() if g in TOOL_GROUPS else ""
            score = 0.0
            for term, weight in terms:
                matched = False
                if term in hay_desc:
                    score += 10 * weight
                    matched = True
                if term in hay_name:
                    score += 100 * weight
                    matched = True
                if term in g:
                    score += 25 * weight
                    matched = True
                if term in server.lower():
                    score += 25 * weight
                    matched = True
                if term in gdesc:
                    score += 8 * weight
                    matched = True
                # 中文词命中说明文字时额外加权：中文描述里的字面命中比英文词干更精确
                if matched and _is_cjk(term) and term in hay_desc:
                    score += 30 * weight
            if terms and score == 0:
                continue
            rows.append((score, server, g, t))
        if not rows and terms:
            rows = [(0.0, s, self.group_of(t["name"]), t) for s, t in self.all_tools()]
        rows.sort(key=lambda r: (-r[0], r[3]["name"]))
        return rows[:max(1, int(limit or 6))]

    # ── 统计 ───────────────────────────────────────────────────────────
    def stats(self, with_groups=True):
        per = []
        for u in self.upstreams:
            b = _jb(u.tools)
            t, exact = count_tokens(u.tools)
            per.append({"server": u.name, "connected": u.error is None and u.alive(),
                        "error": u.error, "tools": len(u.tools),
                        "bytes": b, "tokens": t, "tokensExact": exact,
                        "fingerprint": u.tools_fingerprint,
                        "serverInfo": u.server_info, "capabilities": u.capabilities})
        tot_b = sum(p["bytes"] for p in per)
        tot_t = sum(p["tokens"] for p in per)
        saved_mode, saved_groups = self.mode, self.groups
        modes = {}
        for m in ("full", "slim", "meta", "slim+meta"):
            self.mode, self.groups = m, []
            vis = self.visible_tools()
            b = _jb(vis)
            t, exact = count_tokens(vis)
            modes[m] = {"bytes": b, "tokens": t, "tokensExact": exact,
                        "pct": round(100.0 * t / tot_t, 1) if tot_t else 0.0,
                        "visibleTools": len(vis)}
        self.mode, self.groups = saved_mode, saved_groups
        out = {"bytesPerToken": round(tot_b / tot_t, 2) if tot_t else None,
               "tokensExact": all(p["tokensExact"] for p in per),
               "tokenizer": TOKENIZER_PATH if _tokenizer() else "未加载（用 bytes/%.2f 估算）" % DIV,
               "servers": per,
               "totalTools": sum(p["tools"] for p in per),
               "totalBytes": tot_b, "totalTokens": tot_t,
               "currentMode": self.mode, "currentGroups": self.groups,
               "currentVisibleTools": len(self.visible_tools()),
               "modeCost": modes}
        if with_groups:
            allnames = [t["name"] for _, t in self.all_tools()]
            # 去重：GROUP_FALLBACK 现在**已登记进 TOOL_GROUPS**（见其上方注释），
            # 所以 `list(TOOL_GROUPS) + [GROUP_FALLBACK]` 会产生重复键。
            # 保留 `+ [GROUP_FALLBACK]` 是为了**万一有人把它从 TOOL_GROUPS 摘掉**时
            # 这里仍然会报出该组（兜底组的可见性不该依赖登记状态）。
            out["groups"] = {g: sorted(n for n in allnames if self.group_of(n) == g)
                             for g in dict.fromkeys(list(TOOL_GROUPS) + [GROUP_FALLBACK])}
        return out

    # ── 调用 ───────────────────────────────────────────────────────────
    def call(self, name, args):
        """路由到上游。绝不静默改目标（找不到就明确报错 + 给近似名）。"""
        if name in {m["name"] for m in self.meta_tools()}:
            return self._local(name, args or {})
        u, _ = self.route(name)
        if u is None:
            near = difflib.get_close_matches(
                name, [t["name"] for _, t in self.all_tools()], n=5, cutoff=0.5)
            return {"ok": False, "error": "未知工具 %r" % name, "didYouMean": near,
                    "hint": "用 chain_search_tools 检索；或看 chain_status 的上游状态"}
        if u.error:
            return {"ok": False, "error": "上游 %s 不可用：%s" % (u.name, u.error)}
        try:
            res = u.call(name, args, timeout=self.call_timeout)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "调用上游失败: %r" % (exc,), "server": u.name}
        texts = []
        for c in (res or {}).get("content") or []:
            if isinstance(c, dict) and c.get("type") == "text":
                texts.append(c.get("text") or "")
            else:
                texts.append("[%s 内容]" % (c or {}).get("type", "unknown"))
        return {"ok": not (res or {}).get("isError"),
                "server": u.name, "isError": bool((res or {}).get("isError")),
                "text": "\n".join(texts)}

    def _local(self, name, args):
        if name == "chain_status":
            return {"ok": True, "status": self.stats()}
        if name == "chain_refresh":
            return {"ok": True, "changes": self.refresh(), "status": self.stats()}
        if name == "chain_search_tools":
            rows = self.search(args.get("query"), args.get("group"), args.get("limit"))
            return {"ok": True, "query": args.get("query"), "count": len(rows),
                    "results": [
                        {"name": t["name"], "server": s, "group": g,
                         "summary": (t.get("description") or "").split("\n")[0][:110]}
                        for _, s, g, t in rows]}
        if name == "chain_get_tool_details":
            u, t = self.route(args.get("name"))
            if t is None:
                return {"ok": False, "error": "未知工具 %r" % args.get("name")}
            return {"ok": True, "server": u.name, "tool": t}
        if name == "chain_call_tool":
            target = args.get("name")
            if not target:
                return {"ok": False, "error": "缺 name"}
            return self.call(target, args.get("args") or {})
        return {"ok": False, "error": "未知元工具 %r" % name}

# ══════════════════════════════════════════════════════════════════════════
# MCP 服务器面
# ══════════════════════════════════════════════════════════════════════════

def emit(obj):
    """MCP over stdio：一行一个 JSON（与三个上游同样的 framing）。

    用 **compact 序列化**：默认的 `", "` / `": "` 空格是纯粹浪费 ——
    每一条 `tools/list` 会白多上千字节（blbridge 实测 1,529 B），
    且这些空格同样要进模型上下文/传输。JSON 语法上完全等价。
    """
    sys.stdout.write(json.dumps(obj, ensure_ascii=False,
                                separators=(",", ":")) + "\n")
    sys.stdout.flush()

def force_utf8():
    for n in ("stdin", "stdout", "stderr"):
        s = getattr(sys, n, None)
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

def handle(chain, req):
    method, rid = req.get("method"), req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        emit({"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "blchain", "version": "1.0.0"},
            "instructions": (
                "交互链桥：聚合 blbridge / bannerlordsage / bannerlordhelper 三个 MCP。"
                "若工具面上只有 chain_* 元工具，请按 chain_search_tools → "
                "chain_get_tool_details → chain_call_tool 三步使用。"
                "chain_call_tool 的 name 可以是任何已注册工具，不必先检索。"
                "chain_status 随时自检整条链；chain_refresh 在上游升级后刷新工具表。"),
        }})
        return
    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return
    if method == "ping":
        emit({"jsonrpc": "2.0", "id": rid, "result": {}})
        return
    if method == "tools/list":
        try:
            emit({"jsonrpc": "2.0", "id": rid, "result": {"tools": chain.visible_tools()}})
        except ValueError as exc:
            emit({"jsonrpc": "2.0", "id": rid,
                  "error": {"code": -32602, "message": str(exc)}})
        return
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            out = chain.call(name, args)
        except Exception as exc:  # noqa: BLE001
            out = {"ok": False, "error": "工具执行失败: %r" % (exc,)}
        text = out.pop("text", None)
        if text is None:
            text = json.dumps(out, ensure_ascii=False, indent=1)
        emit({"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": text}],
            "isError": bool(out.get("ok") is False or out.get("isError")),
        }})
        return
    emit({"jsonrpc": "2.0", "id": rid,
          "error": {"code": -32601, "message": "method not found: %s" % method}})

def serve():
    chain = Chain(log_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "_logs"))
    chain.start()
    try:
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        while True:
            raw = stream.readline()
            if not raw:
                break
            try:
                req = json.loads(raw.decode("utf-8", "replace")
                                 if isinstance(raw, bytes) else raw)
            except ValueError:
                continue
            for r in (req if isinstance(req, list) else [req]):
                handle(chain, r)
    finally:
        chain.stop()
    return 0

# ══════════════════════════════════════════════════════════════════════════
# 自测 / 度量 / 统计
# ══════════════════════════════════════════════════════════════════════════

def selftest():
    """证明「无损」不是嘴上说的。

    A 无损    full 模式与上游逐字节相同（数组级 + 逐工具 deep-compare）
    B 完整    89 个上游工具 100% 可达
    C 分层    meta 模式常驻面只剩元工具
    D 检索    关键词命中正确工具
    E 分组    未知组名显式报错（不静默）
    F 真调用  经 chain_call_tool 真的打到上游
    G 近似名  未知工具给 didYouMean
    H 分组默认 未登记的工具进 other 且**仍然可见**（防静默丢失）
    """
    fails = []
    chain = Chain(log_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "_logs"))
    chain.start()
    try:
        print("=" * 74)
        bad_up = [(u.name, u.error) for u in chain.upstreams if u.error]
        if bad_up:
            print("上游连接失败：")
            for n, e in bad_up:
                print("  - %s: %s" % (n, e))
            return 1

        print("A. 无损：full 模式逐字节比对上游")
        up_raw = [t for _, t in chain.all_tools()]
        chain.mode = "full"
        vis = chain.visible_tools()
        if _jb(vis) != _jb(up_raw):
            fails.append("A1 full 模式数组字节不一致 %d vs %d" % (_jb(vis), _jb(up_raw)))
        else:
            print("   [ok] full 模式 %d 个工具逐字节相同（%d B）" % (len(vis), _jb(vis)))
        bad = [t.get("name") for t in up_raw
               if json.dumps(chain.route(t["name"])[1], ensure_ascii=False, sort_keys=True)
               != json.dumps(t, ensure_ascii=False, sort_keys=True)]
        if bad:
            fails.append("A2 逐工具不一致: %s" % bad)
        else:
            print("   [ok] 逐工具 deep-compare 全部一致")

        print("\nB. 完整：全部上游工具可达")
        all_tools = chain.all_tools()
        n_tools = len(all_tools)
        miss = [t["name"] for _, t in all_tools if chain.route(t["name"])[0] is None]
        if miss:
            fails.append("B1 不可路由: %s" % miss)
        else:
            print("   [ok] %d 个工具路由命中率 100%%" % n_tools)

        print("\nC. 分层：meta 模式常驻面")
        chain.mode = "meta"
        mv = chain.visible_tools()
        names = [t["name"] for t in mv]
        if any(not n.startswith("chain_") for n in names):
            fails.append("C1 meta 模式混入了上游工具: %s" % names)
        else:
            mt_tok, mt_exact = count_tokens(mv)
            print("   [ok] meta 模式只有 %d 个元工具：%s（%d B / %d %s）"
                  % (len(mv), names, _jb(mv), mt_tok, "真实token" if mt_exact else "估算token"))
        chain.mode = "full"

        print("\nD. 检索")
        for q, want in [("崩溃", "bl_crash"), ("开战", "bl_start_battle"),
                        ("汉化", "bh_translate_module"), ("nexus", "bh_search_nexusmods"),
                        ("兵种", "bl_lookup_troop")]:
            got = [t["name"] for _, _, _, t in chain.search(q, limit=6)]
            if want in got:
                print("   [ok] %-6s -> %s" % (q, got[:4]))
            else:
                fails.append("D1 检索 %r 未命中 %s（得到 %s）" % (q, want, got))
                print("   [!!] %-6s 未命中 %s -> %s" % (q, want, got))

        print("\nE. 分组：未知组名必须显式报错")
        try:
            Chain(servers=["blbridge"], groups=["nosuchgroup"])
            fails.append("E1 未知组名未报错")
            print("   [!!] 未知组名没报错（静默失败）")
        except ValueError as exc:
            print("   [ok] 显式报错: %s" % str(exc)[:66])

        print("\nF. 真调用：chain_call_tool -> bl_status")
        out = chain.call("chain_call_tool", {"name": "bl_status", "args": {}})
        if "未知工具" in str(out.get("error", "")):
            fails.append("F1 元工具路由失败: %s" % out)
            print("   [!!] 路由失败")
        else:
            print("   [ok] 链路通（上游返回 %s 字节）"
                  % len(out.get("text") or out.get("error") or ""))

        print("\nG. 未知工具：明确报错 + 近似名")
        out = chain.call("bl_stats", {})
        if out.get("ok") is False and out.get("didYouMean"):
            print("   [ok] 报错并给出近似名: %s" % out["didYouMean"])
        else:
            fails.append("G1 未知工具未给出近似名: %s" % out)
            print("   [!!] %s" % out)

        print("\nH. 未登记的工具必须仍然可见（防静默丢失）")
        names_all = [t["name"] for _, t in chain.all_tools()]
        other = [n for n in names_all if chain.group_of(n) == GROUP_FALLBACK]
        chain.groups = []
        vis_names = {t["name"] for t in chain.visible_tools()}
        missing_other = [n for n in other if n not in vis_names]
        if missing_other:
            fails.append("H1 other 组被隐藏: %s" % missing_other)
        else:
            print("   [ok] %d 个未登记工具落 `other` 且全部可见%s"
                  % (len(other), ("：" + ", ".join(other)) if other else "（无未登记工具）"))

        print("\nI. 分组过滤**不会让工具消失**（2026-10-10 补的漂移守卫）")
        #
        # ## 为什么立这条（真机踩到）
        # `DSH_CHAIN_GROUPS=ro` 时未登记的工具会**从视图里消失**（H 段只证明了
        # 「不筛选时仍可见」，没证明「筛选时也可见」）。2026-10-10 实测：
        # blbridge 新增 14 个工具全部未登记 ⇒ `ro` 视图里**一个都看不到**。
        #
        # ## ⚠️ 第一版判据是错的（记下来，别再犯）
        # 我最初写的是"描述**前 80 字符**含『只读』的工具必须已登记"。
        # **反向对照当场证伪**：故意把 `bl_observer_status` 从 ro 摘掉，
        # 测试**依然是绿的** —— 因为它的描述是"观察者状态：是否启用 / 已记录条数…"，
        # **前 80 字符根本不含『只读』**。⇒ 那条判据只覆盖"自述里恰好带该词"的工具，
        # 覆盖率纯属偶然（本项目反复记过的"判据绑定形态"）。
        #
        # ⇒ 改成**不依赖描述文字**的两条：
        #    ① **并集完整性**：所有组名并起来必须等于工具全集 —— 有工具落在任何组
        #       之外，它在**任何** `DSH_CHAIN_GROUPS` 视图下都不可见。
        #    ② **显式名单断言**：下列核心只读工具**必须**在 `ro` 里。名单是断言而非
        #       推导 —— 它们就是"想用 ro 找只读"时最该命中的那批。
        allnames = {t["name"] for _, t in chain.all_tools()}
        union = set()
        for _g in TOOL_GROUPS:
            union |= set(TOOL_GROUPS[_g]["names"])
        ungrouped = sorted(allnames - union)
        if ungrouped:
            fails.append("I1 有工具不属于任何组（任何组筛选下都不可见）: %s" % ungrouped)
            print("   [!!] %d 个工具不在任何组: %s" % (len(ungrouped), ungrouped))
        else:
            print("   [ok] %d 个工具**全部**至少属于一个组（任何组筛选都不会凭空消失）"
                  % len(allnames))

        must_be_ro = [
            "bl_observer_status", "bl_observer_events",       # 战役观察者（读事件流）
            "bl_war_status", "bl_save_status",                # 交战现状 / 存档现状
            "bl_conversation",                                # 读遭遇选项（只列不选）
            "bl_crashguard", "bl_lexicon", "bl_source_map",   # 崩溃取证三件套
            "bl_save_diag", "bl_report",                      # 存档诊断 / 报告导出
            "bl_get_hero", "bl_get_perk", "bl_scan_bad_data",  # 运行时只读
        ]
        ro_names = set(TOOL_GROUPS["ro"]["names"])
        not_ro = [n for n in must_be_ro if n in allnames and n not in ro_names]
        if not_ro:
            fails.append("I2 这些工具应归 `ro` 却不在: %s" % not_ro)
            print("   [!!] 应归 ro 却不在: %s" % not_ro)
        else:
            print("   [ok] %d 个核心只读工具全部归 `ro`（ro 筛选能命中）" % len(must_be_ro))


        print("\nJ. 兜底组 `other` 必须**可选**（2026-10-10 修）")
        #
        # `stats()` 会把 `other` 报给用户（它列在 groups 里），但原来的校验只认
        # TOOL_GROUPS 的键 ⇒ 用户照着报出来的名字填 `DSH_CHAIN_GROUPS=other`
        # 会得到 `ValueError: 未知组名` —— **报了却不给用**。
        if GROUP_FALLBACK in TOOL_GROUPS:
            try:
                Chain(servers=["blbridge"], groups=[GROUP_FALLBACK])
                print("   [ok] `%s` 可被 DSH_CHAIN_GROUPS 选中（与 stats 报出的组名一致）"
                      % GROUP_FALLBACK)
            except ValueError as exc:
                fails.append("J1 兜底组 %r 报了却不可选: %s" % (GROUP_FALLBACK, exc))
                print("   [!!] 不可选: %s" % exc)
        else:
            fails.append("J2 兜底组 %r 未登记进 TOOL_GROUPS（stats 会报它但选不中）"
                         % GROUP_FALLBACK)
            print("   [!!] 未登记")

        print("\n" + "=" * 74)
        if fails:
            print("自测失败 %d 项：" % len(fails))
            for f in fails:
                print("  - %s" % f)
            return 1
        print("自测全部通过（%d 个上游 / %d 个工具）。" % (len(chain.upstreams), n_tools))
        return 0
    finally:
        chain.stop()

def measure():
    chain = Chain(log_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "_logs"))
    chain.start()
    try:
        st = chain.stats()
        bad = [(p["server"], p["error"]) for p in st["servers"] if not p["connected"]]
        if bad:
            print("!! 上游连接失败：")
            for n, e in bad:
                print("   - %s: %s" % (n, e))
            print()
        exact = st["tokensExact"]
        print("# 交互链分层实测（本桥，%d 个上游）\n" % len(chain.upstreams))
        print("token 口径：%s\n"
              % ("**真实 tokenizer**（%s）" % st["tokenizer"] if exact
                 else "**估算**（%s）" % st["tokenizer"]))
        print("| 上游 | 连接 | 工具数 | 字节 | %s | 指纹 |"
              % ("真实 token" if exact else "估算 token"))
        print("|---|---|---:|---:|---:|---|")
        for p in st["servers"]:
            print("| `%s` | %s | %d | %s | %s | `%s` |"
                  % (p["server"], "ok" if p["connected"] else "**失败**",
                     p["tools"], format(p["bytes"], ","), format(p["tokens"], ","),
                     p["fingerprint"] or "-"))
        print("| **合计** | | **%d** | **%s** | **%s** | |"
              % (st["totalTools"], format(st["totalBytes"], ","),
                 format(st["totalTokens"], ",")))
        print("\n## 各模式常驻成本（工具面进上下文的部分）\n")
        print("| 模式 | 可见工具 | 常驻字节 | %s | 占全量 |"
              % ("常驻 token" if exact else "估算 token"))
        print("|---|---:|---:|---:|---:|")
        for m, v in st["modeCost"].items():
            print("| `%s` | %d | %s | %s | **%s%%** |"
                  % (m, v["visibleTools"], format(v["bytes"], ","),
                     format(v["tokens"], ","), v["pct"]))
        if st["bytesPerToken"]:
            print("\n> 实测 bytes/token = **%.2f**（早前用 3.44 会高估约 10%%）。"
                  % st["bytesPerToken"])
        print("\n## 分组（视图，不是权限）\n")
        print("| 组 | 工具数 | 工具 |")
        print("|---|---:|---|")
        for g, names in st["groups"].items():
            print("| `%s` | %d | %s |"
                  % (g, len(names), ", ".join("`%s`" % n for n in names) or "—"))
        return 0
    finally:
        chain.stop()

def main(argv=None):
    force_utf8()
    ap = argparse.ArgumentParser(description="三个 MCP 的交互链聚合/分层桥")
    ap.add_argument("--selftest", action="store_true", help="无损与分层自测")
    ap.add_argument("--measure", action="store_true", help="各模式实测字节与 token")
    ap.add_argument("--stats", action="store_true", help="上游统计（JSON）")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.measure:
        return measure()
    if a.stats:
        chain = Chain(log_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "_logs"))
        chain.start()
        try:
            print(json.dumps(chain.stats(), ensure_ascii=False, indent=1))
            return 0
        finally:
            chain.stop()
    return serve()

if __name__ == "__main__":
    sys.exit(main())
