# 附录 A · 交互链工具清单（89 个，实测生成）

> 本附录由 `mcp-chain/gen_inventory.py` 从**实测** tools/list 生成，非手抄。
> 字节 = **compact JSON** 序列化长度（真正上线的形态）；
> token = **真实 tokenizer**（Spark2.5, vocab 131072，与本机 4B 模型 GGUF 同 vocab）。标记 ★ 的是「高频必备」清单内工具。

| 服务器 | 工具 | 属性 | 层 | 字节 | tok | 摘要 |
|---|---|---:|---|---:|---:|---|
| `bannerlordhelper` | ★ `bh_translate_module` | 6 | `write` | 1,053 | 247 | Translate an existing in-module translation template into another language and write it into the |
| `bannerlordhelper` | ★ `bh_create_external_translation` | 6 | `write` | 1,032 | 251 | Create an external translation module (a separate "<Module> <Lang>" folder plus XSLT patches), m |
| `bannerlordhelper` | `bh_module_details` | 3 | `ro` | 756 | 182 | Fetch Nexus Mods metadata for an installed module. The Nexus id is read from the local .bh confi |
| `bannerlordhelper` | ★ `bh_generate_template` | 3 | `write` | 705 | 160 | Generate the translation template (Languages/<code>/std_*.xml) for a module from its ModuleData  |
| `bannerlordhelper` | ★ `bh_identifier` | 2 | `write` | 613 | 137 | Fill in and repair the {=identifier} translation keys inside a module's ModuleData XML files, mi |
| `bannerlordhelper` | `bh_run_cli` | 2 | `write` | 510 | 149 | Escape hatch: run the bundled `bh` CLI with raw arguments. Only non-interactive invocations work |
| `bannerlordhelper` | ★ `bh_list_local_modules` | 2 | `ro` | 501 | 108 | Scan the local Bannerlord installation and list installed modules (id, name, version, folder, pa |
| `bannerlordhelper` | `bh_search_nexusmods` | 1 | `ro` | 485 | 122 | Search Nexus Mods for Mount & Blade II: Bannerlord modules by keywords and return matching mods  |
| `bannerlordhelper` | `bh_resolve_language` | 1 | `ro` | 348 | 78 | Resolve a loosely typed language query (code, English name or native name) into the canonical Ba |
| `bannerlordhelper` | ★ `bh_list_languages` | 0 | `ro` | 251 | 53 | List every language supported by Bannerlord.Helper together with its code, English name, native  |
| `bannerlordsage` | ★ `project_memory_write` | 17 | `write` | 2,151 | 543 | Write to the cross-session project memory layer. add: store one memory; capture_session: batch-s |
| `bannerlordsage` | `create_mod_workspace` | 14 | `write` | 1,856 | 487 | Scaffold a local Bannerlord mod workspace: SubModule.xml, English localization, a compilable C#  |
| `bannerlordsage` | ★ `project_memory_read` | 7 | `ro` | 1,161 | 287 | Read the cross-session project memory layer. search: full-text query, use before claiming projec |
| `bannerlordsage` | ★ `search_bannerlord_knowledge` | 3 | `ro` | 977 | 242 | Natural-language entry point: searches official tutorials, community docs, API symbols and decom |
| `bannerlordsage` | ★ `bannerlord_doctor` | 4 | `ro` | 876 | 213 | Scan a real Bannerlord install for module dependency problems, duplicate libraries, missing SubM |
| `bannerlordsage` | `search_bannerlord_api_docs` | 4 | `ro` | 854 | 221 | Search official Bannerlord API Doxygen symbols. Reports version match; prefer decompiled source  |
| `bannerlordsage` | ★ `get_entity` | 2 | `ro` | 771 | 223 | Look up one Bannerlord gameplay entity by id from the precomputed projection tables. Prefer over |
| `bannerlordsage` | `search_mod_source` | 4 | `ro` | 763 | 199 | ripgrep over your local mod source tree (not the imported decompile tree). Fastest for frequentl |
| `bannerlordsage` | ★ `read_mod_file` | 4 | `ro` | 717 | 189 | Read a line slice from your local mod source tree (live files, edits visible immediately). |
| `bannerlordsage` | `search_bannerlord_docs` | 3 | `ro` | 711 | 189 | Search official modding tutorials and BannerlordModding.LT community docs. Best for concepts, wo |
| `bannerlordsage` | `generate_xslt_patch` | 3 | `write` | 700 | 185 | Generate an XSLT patch for Bannerlord XML instead of editing source XML directly. |
| `bannerlordsage` | `read_file` | 3 | `ro` | 678 | 186 | Read a slice of an indexed source or XML file. Read only the relevant region to save context. |
| `bannerlordsage` | `resolve_localization` | 2 | `ro` | 604 | 165 | Resolve a {=token}Fallback string to its localized text (Languages XML + source fallback literal |
| `bannerlordsage` | `read_mod_type` | 2 | `ro` | 587 | 156 | Read a class/struct/interface/enum definition from your local mod source (cache refreshes on cha |
| `bannerlordsage` | ★ `search_source` | 2 | `ro` | 575 | 155 | ripgrep the decompiled C# source tree. Use when the exact type/method location is unknown. |
| `bannerlordsage` | `generate_harmony_patch` | 2 | `write` | 544 | 138 | Generate a Harmony patch scaffold for a known target method. Uses the AST method index, so overl |
| `bannerlordsage` | `list_mod_directory` | 2 | `ro` | 538 | 138 | List files and subdirs under your local mod source workspace. |
| `bannerlordsage` | `index_mod_source` | 1 | `write` | 490 | 127 | Build or refresh the incremental C# index for a local mod source dir (reindexes only changed fil |
| `bannerlordsage` | ★ `read_csharp_type` | 1 | `ro` | 484 | 133 | Get the decompiled definition of a known Bannerlord type. Prefer over text search for classes/st |
| `bannerlordsage` | `mod_source_status` | 1 | `ro` | 482 | 123 | Inspect a local mod source workspace: resolved source root and indexed type/member counts. |
| `bannerlordsage` | `read_gauntlet_ui` | 1 | `ro` | 470 | 128 | Get a ViewModel binding checklist for a Gauntlet UI XML: DataSource fields and click handlers. |
| `bannerlordsage` | `list_directory` | 1 | `ro` | 465 | 119 | Explore what has been imported into dist/games/bannerlord/assets before opening a file. |
| `bannerlordsage` | ★ `search_xml` | 1 | `ro` | 452 | 117 | Full-text lookup across imported XML (ModuleData, Languages). Find which files mention an entity |
| `bannerlordsage` | ★ `bannerlord_index_status` | 0 | `ro` | 413 | 107 | Inspect BannerlordSage runtime state: active scopes, indexed table counts, XML parse failures, m |
| `blbridge` | ★ `bl_start_battle` | 32 | `battle` | 8,096 | 2,237 | ⚡【Agent 调用纪律 · 必读】收到"开一场战斗"类需求时**直接调用本工具**，禁止先去列目录 / 读 XML / 查索引确认兵种 id：troop id 由引擎侧 MBObjectMa |
| `blbridge` | `bl_order` | 10 | `battle` | 3,512 | 924 | 战斗中途改令：对**正在进行**的战斗里某一方的编队改 movement / 移动到指定点 / 冲锋到指定敌方编队 / 攻击指定敌方单位 / 阵列 / 射击纪律 / 骑乘令。⚠️ 只在战斗内有 |
| `blbridge` | `bl_launch_game` | 9 | `launch` | 2,519 | 678 | 无人值守启动 Bannerlord（走 BLSE）并**进到自定义战斗界面**，分两步：① 起游戏、自动应答两个模态弹窗（Safe Mode -> 否；Mod change detected  |
| `blbridge` | ★ `bl_blockade` | 9 | `ro` | 2,301 | 621 | 关隘封锁候选生成（离线、只读，对应 tools/bl_blockade.py）。给 MapBlockade（城池关隘 mod）算「哪座城该封哪几块地图面片」，输出候选 + 有效性证据 + 冲突 |
| `blbridge` | ★ `bl_ipc_replay` | 7 | `ro` | 1,855 | 517 | **IPC 响应缓存检索（宿主侧，只读，不碰游戏）**：从 `<日志目录>\commands\done\` 的 **12991 份历史响应**里按条件捞回**完整响应体**。为什么通用手段不行 |
| `blbridge` | ★ `bl_crash` | 7 | `ro` | 1,780 | 466 | **崩溃取证（宿主侧，进程死后也能用）**：解析 Windows 自动落盘的 minidump，给出「异常代码 + 崩溃模块+偏移 + 访问的目标地址」，并把它接到 BlBridge 的会话上 |
| `blbridge` | `bl_control_agent` | 5 | `battle` | 1,586 | 411 | 接管士兵（**最小版**）：把 `Mission.MainAgent` 换成友方某个 agent 并交给玩家控制器。官方那条路（`CanTakeControlOfAgent`）**只在主角阵亡 |
| `blbridge` | ★ `bl_patches` | 5 | `ro` | 1,553 | 419 | **Harmony 补丁内省（只读）**：回答「**谁补了哪个方法**」。为什么需要它：三合一 MOD（RBM + Warbandlord + RCM）的**核心风险就是「双重叠加」** —— |
| `blbridge` | ★ `bl_exception_detail` | 4 | `ro` | 1,540 | 426 | **异常采集口径说明 + 记录读取（宿主侧，只读，不碰游戏）**：解释 `<日志目录>\exceptions.jsonl` 的**记录口径**并读明细。为什么必需——该文件的口径**多处反直觉 |
| `blbridge` | ★ `bl_concurrency_guide` | 2 | `ro` | 1,469 | 435 | **并发纪律（宿主侧，只读，不碰游戏）**：告诉你**哪些工具能并发、最多几路**。为什么需要：**所有走游戏通道的工具共用同一条串行泵**（`commands/pending/` → 游戏主 |
| `blbridge` | `bl_campaign_time` | 1 | `ro` | 1,435 | 369 | 只读：战役时间/暂停状态诊断。status（默认，也是唯一可用的 mode）回读 timeControlMode / inMenuContext / campaignDays / pauseM |
| `blbridge` | ★ `bl_json_health` | 3 | `ro` | 1,299 | 358 | **IPC 响应完整性体检（宿主侧，只读，不碰游戏）**：全量解析 `<日志目录>\commands\done\*.json`，找出**畸形 JSON** 并给出原始上下文与字节偏移。为什么需 |
| `blbridge` | ★ `bl_ui_extensions` | 3 | `ro` | 1,281 | 331 | **UIExtenderEx 界面扩展（只读）**：列出每个模块通过 UIExtenderEx **改了哪些官方界面**，以及每个界面上挂了哪些扩展类（含 ViewModel mixin 计数 |
| `blbridge` | ★ `bl_mcm_settings` | 4 | `ro` | 1,258 | 341 | **MCM 设置表（只读）**：列出 Mod Configuration Menu 里注册的全部设置块与设置项，含每项的当前值 / 类型 / 值域 / 是否需重启 / 提示文本。为什么需要它： |
| `blbridge` | `bl_camera_speed` | 3 | `write` | 1,234 | 349 | 相机移动速度分三条互不相干的腿，用 mode 指名：`shift` = 引擎自由相机的 Shift 倍率（**不需要作弊模式**，改完按住 Shift 飞就生效）；`base` = 引擎自由相 |
| `blbridge` | `bl_get_viewmodel_property` | 3 | `ro` | 1,147 | 307 | 只读：读当前界面某层 ViewModel 的一个属性；点号路径可穿透嵌套（如 'Smelting.SmeltableItemList'）。列表属性返回 count + items + miss |
| `blbridge` | ★ `bl_lookup_troop` | 5 | `ro` | 1,141 | 309 | 查兵种：校验 id 是否存在、按 id 模糊搜索、按文化筛选。数据来自 BannerlordSage 的索引库（只读，只索引官方 XML）。没装 BannerlordSage 时返回 avai |
| `blbridge` | `bl_open_ui` | 1 | `launch` | 1,122 | 302 | 走官方正门唤起一个游戏内界面（默认 = 官方自定义战斗界面，uiId=CustomBattle）。v0.8.14 起不再有自建面板 —— 官方界面本身就是完整入口（战斗/围攻/村庄/海战/海上 |
| `blbridge` | ★ `bl_exceptions` | 0 | `ro` | 1,089 | 291 | **运行时异常统计（FirstChance 捕获的只读视图）**。BlBridge 在模块加载时订阅 `AppDomain.FirstChanceException`（**.NET 原生事件， |
| `blbridge` | ★ `bl_patch_failures` | 0 | `ro` | 1,067 | 283 | **补丁失败清单**：把 Harmony 的 `HarmonyException` 从「现象」变成「点名」。返回每条失败**想补的目标**（`targetClass` / `targetMet |
| `blbridge` | `bl_dump` | 1 | `other` | 1,003 | 289 | 按需让**游戏进程自己**写一份 minidump（B2 / v0.8.48）。与 WER 的 dump 的关键差别：**显式带 MiniDumpWithFullMemoryInfo(0x80 |
| `blbridge` | `bl_apply_rts_config` | 4 | `write` | 1,001 | 281 | 写 RTSCamera 配置（自动备份 + 写后 XML 校验 + 回读核对）。**实测：改完无需重启，下一场战斗就生效**（RTSCamera 每场读一次配置）；但它运行中会把自己的配置覆写 |
| `blbridge` | `bl_desktop_click` | 4 | `desktop` | 992 | 252 | 按**格子名**点击（如 C5；跨格用 I5+I6；递归用 B2.C1），或按物理像素坐标点击。一条命令完成「移动+点击」。可选先聚焦目标窗口（focus=true，默认 true）。已知边界 |
| `blbridge` | `bl_desktop_screenshot` | 4 | `desktop` | 955 | 257 | 截屏（全屏或某个窗口），可叠加 16x9 的**带标签网格**（每格中心有十字准星），也可放大到某一格看子网格。返回 PNG 路径 —— 用 view_image 读它即可看到画面。为什么用网 |
| `blbridge` | `bl_get_screen` | 1 | `ro` | 923 | 254 | 只读：读当前界面的层 / 影片 / 可点按钮（文本 + 是否可用 + 状态 + id）—— 读界面，不模拟鼠标（合成输入到不了官方界面）。返回 screenType / layerCount  |
| `blbridge` | `bl_crash_test` | 0 | `other` | 880 | 246 | **受控崩溃**：让游戏进程显式崩一次（纯 SEH 0xC0000005），用于验收 B2 的崩溃落盘路径。**游戏会真的崩掉**。★ 双重安全闸门（缺一不可）：① 必须显式调本工具；② 必须 |
| `blbridge` | `bl_cheat_mode` | 1 | `write` | 868 | 235 | 开关**作弊模式**（带回读：写 NativeConfig.CheatMode 再回读验证）。**为什么需要它**：引擎自由相机的倍率热键（Ctrl+↑ ×1.5 / Ctrl+↓ ×2÷3  |
| `blbridge` | ★ `bl_batch_report` | 6 | `battle` | 804 | 213 | A/B 对比报告（阶段 2④）。主指标 = **满编窗口**（第一例击杀之前的双方实际扣血占比，此时双方严格等编）；全程口径会被幸存者偏差污染，仅作对照。强制输出 均值 ± 标准差 + 95% |
| `blbridge` | `bl_list_ui` | 2 | `ro` | 795 | 209 | 列出游戏内所有可进入的入口（初始状态选项）+ 当前激活状态 + **官方自定义战斗场景全表**（合并表 CustomBattleScenes，含模式：战斗/围攻/村庄/领主大厅/海战/海上掠夺 |
| `blbridge` | `bl_load_save` | 1 | `write` | 780 | 206 | **按名字直载存档**（MBSaveLoad.LoadSaveGameData + StartNewGame，不经过存档选择界面）—— 无人值守换档的正门，也是复现读档期弹窗（模组不匹配）的测 |
| `blbridge` | `bl_ghost_camera` | 1 | `write` | 748 | 193 | 开关**引擎自带**的自由观察相机（幽灵模式）。运行时生效、**对任何一场战斗都有效**（包含你自己打的），不像 spectate 只对 AI 场次。做法：设 `MissionScreen.I |
| `blbridge` | ★ `bl_run_batch` | 4 | `battle` | 743 | 192 | 按计划文件批量跑 N 场 AI 对 AI 战斗（阶段 2④「一条命令跑 N 场」）。支持换边双跑：plan 里两个 config 的 attacker/defender 对调即可。dryRun |
| `blbridge` | `bl_get_inventory` | 1 | `ro` | 667 | 177 | 只读：读玩家队伍的库存清单（主队伍 ItemRoster）+ 金币。返回 gold / itemCount / totalElements / items[]（name、id、quantity |
| `blbridge` | `bl_desktop_windows` | 2 | `ro` | 629 | 162 | 列出当前可见的顶层窗口：标题 / 进程号 / **物理像素**坐标与尺寸（本机 3840x2160@150%，已 DPI 校正）。用于判断游戏是否在跑、窗口是否在前台、拿 windowId 给 |
| `blbridge` | ★ `bl_wait_for_state` | 3 | `battle` | 620 | 160 | 轮询等待推演状态（idle/loading/running/ended/error），到点返回当前状态与结果。开战后的 `loading` 段是引擎加载场景（秒级~几十秒），本工具只是盯状态， |
| `blbridge` | `bl_rts_config` | 2 | `ro` | 608 | 154 | 回读 **RTSCamera** 的配置（Documents\...\Configs\RTSCamera\RTSCameraConfig.xml）。只读。用来查'攻城相机高度/自由相机/抬升触 |
| `blbridge` | `bl_desktop_key` | 3 | `desktop` | 576 | 146 | 按键或输入文本：keys 走组合键（enter / ctrl+a / alt+f4），text 走文本输入。Bannerlord 与 BLSE 的对话框用得上（例如 Mod change de |
| `blbridge` | `bl_list_parties` | 1 | `ro` | 561 | 145 | 只读：列出地图上所有队伍（MobileParty）。返回 count / parties[]（name、stringId、isMainParty/isLordParty/isCaravan/i |
| `blbridge` | `bl_fast_forward` | 1 | `battle` | 540 | 131 | 开关战斗加速（10 倍速，引擎官方 Mission.IsFastForward 通道，由 BlBridge 每帧重申）。对**你自己手打的战斗**同样生效（含自定义战斗），不依赖 RTSCam |
| `blbridge` | `bl_list_settlements` | 1 | `ro` | 536 | 143 | 只读：列出所有封地（Settlement）。返回 count / settlements[]（name、stringId、type=town/castle/village/hideout、ow |
| `blbridge` | `bl_close_ui` | 1 | `launch` | 511 | 117 | 从官方自定义战斗界面回主菜单（与官方 CustomBattle 的「返回」同一路径：PopState）。open_ui 进去了就用它出来。白名单**只有** CustomBattleState |
| `blbridge` | `bl_campaign_overview` | 0 | `ro` | 510 | 131 | 只读：战役全局概览（控制面 A 阶段）。返回 inCampaign / clans / kingdoms / settlements / mobileParties 计数，以及玩家 gold  |
| `blbridge` | ★ `bl_analyze` | 2 | `ro` | 498 | 123 | 分析一场战斗日志，输出：血量模型校验（致死总伤害 vs 最大血量偏差）、每击伤害分布（按兵种/伤害类型/部位/武器/远近战）、挨打成本。不传 file 时分析最新一场。 |
| `blbridge` | ★ `bl_build_check` | 0 | `ro` | 481 | 118 | 核对「源码 → 构建产物 → 部署文件 → 进程内 DLL」四段是否一致。用于回答三件事：① 改了代码没重新构建（stale_source）；② 构建了但没部署（stale_deploy）；③ |
| `blbridge` | `bl_list_clans` | 1 | `ro` | 475 | 128 | 只读：列出所有家族（Clan）。返回 count / clans[]（name、stringId、tier、gold、influence、kingdom、leader、isMinor、isEl |
| `blbridge` | `bl_campaign_log` | 1 | `ro` | 474 | 131 | 只读：战役日志快照（最近 N 条 LogEntry）。返回 count / entries[]（text、time）。count 控制条数（默认 20，上限 200）。注意：这是快照而非实时流 |
| `blbridge` | `bl_apply_config` | 2 | `write` | 467 | 124 | 修改 Warbandlord config.xml（自动备份 + 写后 XML 校验）。注意：游戏需要重启后配置才生效。 |
| `blbridge` | `bl_list_kingdoms` | 1 | `ro` | 442 | 117 | 只读：列出所有王国（Kingdom）。返回 count / kingdoms[]（name、stringId、rulingClan、leader、clanCount、gold、isKingdo |
| `blbridge` | ★ `bl_read_events` | 4 | `ro` | 415 | 107 | 读取原始事件行（可按类型过滤与限量），用于细节排查 |
| `blbridge` | `bl_config` | 0 | `ro` | 397 | 89 | 显示 MCP 侧的有效配置与来历（环境变量 / blbridge.json / 默认值分别给了什么），并列出配置文件里的非法项（逐项忽略、附原因）。只读。注意：游戏端另有 blbridge_g |
| `blbridge` | `bl_list_saves` | 0 | `ro` | 372 | 100 | 只读：列出所有存档（MBSaveLoad.GetSaveFiles）。返回 count / saves[]（name、isCorrupted、meta：存档元数据键值包，含模组/版本信息）。n |
| `blbridge` | `bl_skip_video` | 0 | `launch` | 363 | 88 | 跳过开场动画。**不模拟 ESC**，而是先问「当前活动状态是不是 `VideoPlaybackState`」，是就直接调它的 `OnVideoFinished()`。判据硬、无副作用；不是视 |
| `blbridge` | `bl_read_config` | 1 | `ro` | 329 | 87 | 回读 Warbandlord 的 config.xml 配置值（可不传 paths 取全部） |
| `blbridge` | ★ `bl_status` | 0 | `ro` | 304 | 71 | 读取模块状态（是否加载、日志目录、会话内场次、最近一场战斗）+ 构建一致性（源码/构建/部署/进程内）+ 会话诊断（游戏是否真的在跑）。 |
| `blbridge` | ★ `bl_list_battles` | 1 | `ro` | 270 | 67 | 列出已记录的战斗日志文件（名称/大小/时间） |
| `blbridge` | ★ `bl_battle_status` | 0 | `ro` | 240 | 58 | 查询游戏内推演状态机（idle/loading/running/ended/error）、进度（双方存活数）与最近一次结果 |
| `blbridge` | `bl_abort` | 0 | `battle` | 210 | 49 | 中止当前正在进行的推演（调用引擎的 Mission.EndMission，走官方结束路径） |
| `localization-audit` | `la_audit_coverage` | 4 | `ro` | 1,498 | 415 | 汉化**真缺键审计**（只读）：列出 locale 下**真的缺翻译**的键，按模组汇总。回答「哪些 mod 的汉化有缺口、缺多少」。★ 口径已修正四处（这四处都会静默给出错误答案，故显式说明 |
| `localization-audit` | `la_dll_strings` | 4 | `ro` | 1,204 | 344 | 从 .NET 程序集抽取**硬编码字符串**（只读）—— 第 1 类「界面上的英文」的探测端。为什么需要它：`la_audit_coverage` 只做 **XML 侧**（`{=KEY}`） |
| | | | | **87,546** | **23,140** | |

## 每服务器小计

| 服务器 | 工具数 | 字节 | token | 必备工具数 |
|---|---:|---:|---:|---:|
| `blbridge` | 57 | 60,271 | 16,124 | 22 |
| `bannerlordsage` | 24 | 18,319 | 4,770 | 10 |
| `bannerlordhelper` | 10 | 6,254 | 1,487 | 6 |
| `localization-audit` | 2 | 2,702 | 759 | 0 |
| **合计** | **93** | **87,546** | **23,140** | **38** |

## 附录 B · 高频必备清单（38 个）

按用途分组。这些是「mod 测试 / 查 bug / 汉化」日常真正会用的工具。

- **`battle`**（4 个 / 2,802 token）：`bl_start_battle`, `bl_batch_report`, `bl_run_batch`, `bl_wait_for_state`
- **`ro`**（29 个 / 7,168 token）：`bl_blockade`, `bl_ipc_replay`, `bl_crash`, `bl_patches`, `bl_exception_detail`, `bl_concurrency_guide`, `bl_json_health`, `bl_ui_extensions`, `bl_mcm_settings`, `project_memory_read`, `bl_lookup_troop`, `bl_exceptions`, `bl_patch_failures`, `search_bannerlord_knowledge`, `bannerlord_doctor`, `get_entity`, `read_mod_file`, `search_source`, `bh_list_local_modules`, `bl_analyze`, `read_csharp_type`, `bl_build_check`, `search_xml`, `bl_read_events`, `bannerlord_index_status`, `bl_status`, `bl_list_battles`, `bh_list_languages`, `bl_battle_status`
- **`write`**（5 个 / 1,338 token）：`project_memory_write`, `bh_translate_module`, `bh_create_external_translation`, `bh_generate_template`, `bh_identifier`
