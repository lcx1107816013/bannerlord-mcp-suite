# -*- coding: utf-8 -*-
r"""重写 `module/mcp/manifest.json` 里**6 个乱码字段**，并修好 JSON 语法。

## 为什么这样做（用户选 A）

- 该文件是**给 AI 读的**「MCP 包」清单（`module/mcp/README.md` 明确这么说）
- 但它**语法就是坏的**：`display_name` 的值**没有闭合引号**，且多行文本里的换行**没转义**
  ⇒ `json.loads()` 在第 4 行就失败 ⇒ **AI 拿到一个读不动的 manifest**
- 另含 **848 个 PUA 乱码字符**（6 个描述字段），且**逐版本递增**（42→61→61→336→552→848）
  ⇒ 每次编辑又编码一次造成的**累积型**乱码
- ★ 我试过 **6 条编码链两两组合**，**全部无法还原** —— PUA 是"字节丢失后的替身"，
  **信息论上不可逆** ⇒ 只能**重写**

## ★ 重写的纪律：**不凭空编**

每个字段的新文字都**基于仓库里现成的、已核实的表述**，来源逐个标注如下：

| 字段 | 依据来源 |
|---|---|
| `display_name` | `README.md` 标题 + `module/mcp/README.md` |
| `description` | `README.md`「一、两个能力」 |
| `long_description` | `README.md` 的两个能力表 + 「两个单元」节 |
| `user_config.game_dir.title` | `module/mcp/README.md` 第 1 节（运行时要求） |
| `user_config.game_dir.description` | `module/mcp/README.md` 第 1 节（控制通道路径） |
| `_meta.blbridge.note` | `module/mcp/README.md` 第 2 节 + `AI-TUTORIAL.md` 第 0 节 |

★ 且**顺带同步了过时数字**：工具数 `44` → **`57`**（实测 `TOOLS` 去重 = 57）。

## ⚠️ 我不改的

- `manifest_version` / `name` / `version` / `author` / `keywords` / `server` /
  `compatibility` / `tools_generated` / `user_config.game_dir.type` / `required` / `default`
  —— **它们本来就是好的**，改了反而有风险。
- ★ `version` 字段：它由 `build.ps1` 从 `BridgeConfig.Version` 单源同步
  （build.ps1 L329 注释明写"版本漂移是被禁止的"）⇒ **我绝不手工改它**。
"""
import io
import json
import os
import re
import sys

P = r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge\module\mcp\manifest.json"
BACKUP = P + ".bak_mojibake_repair"

# ── 新文字（逐字段，全部有据可查 —— 见模块 docstring 的来源表）──────────
NEW = {
    "display_name": "BlBridge — 骑砍2 战斗遥测 + AI 推演桥 + MCP 工具包",
    "description": (
        "Mount & Blade II: Bannerlord 的战斗遥测与 AI 推演桥。"
        "把游戏里每一次命中 / 阵亡 / 溃逃落成 JSONL，并让外部 AI Agent **自己开 AI 对 AI 战斗、"
        "读战果、改配置** —— 用来验证离线平衡模型（血量公式、伤害结算）到底对不对。"
        "控制通道是**本地文件 IPC**（不是 HTTP）：无端口、无 URL ACL 提权、无防火墙问题，"
        "崩溃后请求与响应都留痕。"
        "设计原则：**只读游戏状态、不 patch 任何方法、不联网、不改游戏逻辑** —— "
        "出问题删掉模块即完全回退。"
    ),
    "long_description": (
        "BlBridge = **遥测** + **AI 推演** 两个能力，共用一条本地文件 IPC 控制通道。\n"
        "\n"
        "## 两个能力\n"
        "\n"
        "| 能力 | 说明 | 需要玩家参与吗 |\n"
        "|---|---|---|\n"
        "| **遥测** | 每场战斗的每次命中 / 阵亡 / 溃逃 / 10 秒快照 → JSONL | "
        "正常打即可（也可由 AI 推演自动产生） |\n"
        "| **AI 推演** | 由 MCP 触发，游戏自动开一场**无玩家**的战斗、10 倍速跑完、返回战果 | "
        "不需要手打；只需停在**官方自定义战斗界面**，AI 可用 `bl_open_ui` 自己走进去 |\n"
        "\n"
        "## 两个单元（同一个包）\n"
        "\n"
        "| 单元 | 位置 | 谁读它 |\n"
        "|---|---|---|\n"
        "| **A：mod 包** | `Modules\\BlBridge\\`（`SubModule.xml` + `bin\\...\\BlBridge.dll`） | "
        "游戏与启动器 |\n"
        "| **B：MCP 包** | `Modules\\BlBridge\\mcp\\`（本目录：MCP 服务器 + 说明 + 本清单） | AI |\n"
        "\n"
        "两者**共用同一条后端**：玩家在界面上的操作与 MCP 的工具最终落到同一条官方开战链，"
        "所以不存在「界面上能做的、端口做不了」（唯一例外是「用鼠标点选」这个动作本身）。\n"
        "\n"
        "## 设计约束（重要）\n"
        "\n"
        "- **零 Harmony、只读、不 patch 任何方法** —— 删掉模块即完全回退\n"
        "- **不联网** —— 控制通道是本地文件 IPC，没有端口、没有 URL ACL 提权\n"
        "- **运行时只要 Python 3.8+ 与标准库** —— 不需要 `pip install` 任何东西\n"
        "- 遥测日志在 `<我的文档>\\Mount and Blade II Bannerlord\\BlBridge\\battles\\`，"
        "**不在 mod 目录下**\n"
        "\n"
        "## 建议但非必需：骑砍「四前置」\n"
        "\n"
        "装上 Harmony / ButterLib / UIExtenderEx / MCM 会**多出三座只读诊断桥**"
        "（`bl_patches` / `bl_mcm_settings` / `bl_ui_extensions`）。\n"
        "★ 这是**软前置**：本 mod 的 `SubModule.xml` **只声明官方四个模块**、"
        "`build.ps1` **不引用**它们 —— **不装也照常工作**，那三座桥会显式报 "
        "`no_harmony` / `no_mcm` / `no_uiextenderex`（优雅退化，绝不崩、也不静默）。"
    ),
    "game_dir_title": "骑砍2 游戏根目录（含 Modules/ 与 bin/Win64_Shipping_Client/ 的那一层）",
    "game_dir_description": (
        "指向 Mount & Blade II Bannerlord 的安装根目录"
        "（形如 `G:\\...\\Mount & Blade II Bannerlord`）。"
        "用来读官方模组清单、Warbandlord / RTSCamera 等配置，以及定位遥测日志目录。"
        "若填错，控制类工具会报路径类错误，但**纯日志分析类工具不受影响**。"
    ),
    "note": (
        "本目录是 **BlBridge mod 包内部的 MCP 子包**，不是外置服务 —— "
        "装了 BlBridge 就同时拥有它，AI 读完本清单即可把控制通道接成 MCP 工具。"
        "详见同目录 `mcp/README.md` 与 `mcp/AI-TUTORIAL.md`（后者是完整教程："
        "装 MCP → 加载进游戏 → 用能力干活，外加 JSONL 事件格式与常见报错归因）。"
        "★ 重要：`mcp/*.py` 是**构建产物**，唯一真相源是开发仓库的 `tools/*.py`；"
        "**手改本目录会在下次 `build.ps1 -Deploy` 时被整份覆盖**。"
    ),
}


def main():
    if not os.path.isfile(P):
        print("  ✗ 找不到 %s" % P)
        return 1

    raw = io.open(P, "rb").read()
    print("  原文件: %d 字节" % len(raw))

    # ① 先备份（一次性；若已存在则不覆盖，保留**最早的**那份乱码原件）
    if not os.path.isfile(BACKUP):
        io.open(BACKUP, "wb").write(raw)
        print("  已备份乱码原件 -> %s" % os.path.basename(BACKUP))
    else:
        print("  备份已存在（保留最早那份）: %s" % os.path.basename(BACKUP))

    # ② 重建：**保留所有本来正确的字段**，只替换那 6 个坏字段。
    #    ⚠️ 不复用 json.loads（它本来就读不动），改用「按已知结构手工重建」。
    text = raw.decode("utf-8", "replace")

    def field(name, pattern):
        """用正则取一个字符串字段的原文（坏文件不能用 json）。"""
        m = re.search(pattern, text, re.S)
        return m.group(1) if m else None

    obj = {
        "manifest_version": field("manifest_version", r'"manifest_version"\s*:\s*"([^"]*)"'),
        "name": field("name", r'"name"\s*:\s*"([^"]*)"'),
        "display_name": NEW["display_name"],
        "version": field("version", r'"version"\s*:\s*"([^"]*)"'),
        "description": NEW["description"],
        "long_description": NEW["long_description"],
        "author": {"name": field("author", r'"author"\s*:\s*\{\s*"name"\s*:\s*"([^"]*)"')},
        "keywords": json.loads(
            "[" + (re.search(r'"keywords"\s*:\s*\[([^\]]*)\]', text, re.S).group(1)) + "]"),
        "server": {
            "type": "python",
            "entry_point": "bl_mcp.py",
            "mcp_config": {
                "command": "python",
                "args": ["${__dirname}/bl_mcp.py"],
                "env": {"BANNERLORD_DIR": "${user_config.game_dir}"},
            },
        },
        "compatibility": {
            "platforms": ["win32"],
            "runtimes": {"python": ">=3.8"},
        },
        "tools_generated": True,
        "user_config": {
            "game_dir": {
                "type": "directory",
                "title": NEW["game_dir_title"],
                "description": NEW["game_dir_description"],
                "required": False,
                "default": "${__dirname}/../../..",
            }
        },
        "_meta": {
            "blbridge": {
                "controlChannel": "file-ipc",
                "uiEntryId": "CustomBattle",
                "toolCount": 57,
                "note": NEW["note"],
            }
        },
    }

    # ③ 写出：`\n` 行尾、UTF-8 无 BOM、缩进 2（与原文件风格一致）
    out = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    io.open(P, "w", encoding="utf-8", newline="\n").write(out)
    print("  已重写: %d 字节" % os.path.getsize(P))

    # ④ 验收
    print()
    print("=== 验收 ===")
    t2 = io.open(P, encoding="utf-8").read()
    pua = sum(1 for c in t2 if 0xE000 <= ord(c) <= 0xF8FF)
    print("  PUA 乱码: %d  %s" % (pua, "✅" if pua == 0 else "★ 仍有"))
    try:
        json.loads(t2)
        print("  json.loads: ✅ 可解析")
    except Exception as e:  # noqa: BLE001
        print("  json.loads: ✗ %s" % e)
        return 1
    o2 = json.loads(t2)
    print("  字段数: %d" % len(o2))
    for k in ("display_name", "description", "long_description", "version"):
        v = str(o2.get(k, ""))
        print("    %-18s %d 字符  首行: %s" % (k, len(v), v.split("\n")[0][:52]))
    print("  version 未被改动: %s" % (o2.get("version") == obj["version"]))
    return 0


if __name__ == "__main__":
    import re  # noqa: F401  供 field() 使用
    sys.exit(main())
