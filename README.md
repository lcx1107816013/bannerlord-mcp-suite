# bannerlord-mcp-suite

> 把多个《骑马与砍杀 II：霸主》相关的 **MCP 服务器**聚合成**单一入口**的桥，
> 外加一套**只读**的汉化审计工具。

[English](#english) · 中文（本页）

---

## ★ 它调用哪些 MCP？（**先看这个**）

本仓库**本身不是游戏工具** —— 它是一座**桥**：把下面这些 MCP 聚合成一个工具面。
**所以你必须一并 clone 它们**（本仓库不内嵌，理由见 [`docs/why-umbrella-repo.md`](docs/why-umbrella-repo.md)）。

| # | MCP 仓库（**要 clone 这些**） | 它给什么 | 工具数 | 语言 |
|---|---|---|---:|---|
| 1 | ★ [`lcx1107816013/Bannerlord-blbridge`](https://github.com/lcx1107816013/Bannerlord-blbridge) | **操控游戏**：开战 / 改令 / 接管士兵 / 遥测 / 存档 / 崩溃取证 | **57** | C# DLL + Python |
| 2 | [`lcx1107816013/BannerlordSage-variant`](https://github.com/lcx1107816013/BannerlordSage-variant) | **查资料**：源码 / XML / C# 类型 / API 文档 / 项目记忆 | **24** | TypeScript + bun |
| 3 | [`lcx1107816013/Bannerlord-Helper-variant`](https://github.com/lcx1107816013/Bannerlord-Helper-variant) | **汉化**：i18n / 生成模板 / 翻译 / Nexus 检索 | **10** | TypeScript + bun |
| 4 | **本仓库自带** | **审计**：`localization-audit`（**只读**，汉化缺键 + DLL 硬编码串） | **2** | Python |

⇒ 合计 **93 个工具**；`meta` 模式下常驻只 **5 个元工具 / 522 token**（省 97.7%）。

```bash
# 一条命令把四个都拉下来（本仓库 + 它要挂的三个）
git clone https://github.com/lcx1107816013/bannerlord-mcp-suite.git
cd bannerlord-mcp-suite
git clone https://github.com/lcx1107816013/Bannerlord-blbridge.git       ../Bannerlord-blbridge
git clone https://github.com/lcx1107816013/BannerlordSage-variant.git    ../BannerlordSage-variant
git clone https://github.com/lcx1107816013/Bannerlord-Helper-variant.git ../Bannerlord-Helper-variant
```

★ **不确定自己缺哪个？** 跑 `pwsh -File bootstrap.ps1 -Check` ——
它会**逐个点名**缺什么，并**直接打印要执行的 `git clone` 命令**。
★ 三个业务 MCP 里只有 **BlBridge 需要先 `build.ps1 -Deploy`**（它是 C#）；
两个 TS 的上游只要装了 `bun` 就能跑。

> 📌 上面第 1–3 个都是**我们自己维护**的仓库（第 2、3 个是**上游变种**，
> 各自 `LICENSE` 保留了上游版权，详见 [`NOTICE`](NOTICE)）。

---

## 这个仓库解决什么问题

同时挂多个 MCP 服务器时有两个真实痛点，都是**实测**出来的（不是推测）：

| 痛点 | 实测数字 |
|---|---|
| **① 工具面吃掉上下文** | 三个业务服务器合计 **91 个工具 / 22,387 token** 常驻 —— 占 32K 上下文的 **68.3%** |
| **② 工具太多找不到** | 91 个工具里，模型经常选错或漏掉该用的那个 |

本仓库的 `bl_chain.py` 用一个**稳定的元工具层**解决两者
（下表是**四个上游**的实测值，含本仓库自带的审计 MCP）：

| 模式 | 常驻工具 | 常驻 token | 占全量 |
|---|---:|---:|---:|
| `full` | 93 | 23,142 | 100% |
| `slim` | 93 | 13,306 | 57.5% |
| **`meta`** | **5** | **522** | **2.3%** |

⇒ **`meta` 模式把常驻从 23,142 token 压到 522（省 97.7%）**，而**能力一个不少**（见下方"无损"）。
⇒ 换算成 32K 上下文：`full` 占 **70.6%**，`meta` 只占 **1.6%**。

---

## 快速开始

### 第 1 步：clone 本仓库 + 它要挂的四个 MCP

★ **本仓库只是「聚合桥 + 审计 MCP」**，它要挂的那几个 MCP **不在本仓库里**
（为什么这样切见 [`docs/why-umbrella-repo.md`](docs/why-umbrella-repo.md)）。
⇒ **必须一并 clone 下面这些，否则桥上没有可调的工具。**

| 仓库 | 是什么 | 语言 | 必须先装吗 |
|---|---|---|---|
| [`bannerlord-mcp-suite`](https://github.com/lcx1107816013/bannerlord-mcp-suite) | ★ **本仓库**（桥 + 审计 MCP） | Python | — |
| [`Bannerlord-blbridge`](https://github.com/lcx1107816013/Bannerlord-blbridge) | 操控游戏：开战 / 改令 / 遥测 / 崩溃取证（**57 个工具**） | C# DLL + Python | 需要 `build.ps1 -Deploy` |
| [`BannerlordSage-variant`](https://github.com/lcx1107816013/BannerlordSage-variant) | 查资料：源码 / XML / API 文档（**24 个工具**） | TypeScript + bun | 需要 bun |
| [`Bannerlord-Helper-variant`](https://github.com/lcx1107816013/Bannerlord-Helper-variant) | 汉化 / i18n / Nexus 检索（**10 个工具**） | TypeScript + bun | 需要 bun |
| （本仓库自带） | 汉化审计（**2 个工具**，**只读**） | Python | 不需要 |

```bash
# 本仓库
git clone https://github.com/lcx1107816013/bannerlord-mcp-suite.git
cd bannerlord-mcp-suite

# 三个业务 MCP（放到你自己惯用的目录即可）
git clone https://github.com/lcx1107816013/Bannerlord-blbridge.git
git clone https://github.com/lcx1107816013/BannerlordSage-variant.git
git clone https://github.com/lcx1107816013/Bannerlord-Helper-variant.git
```

### 第 2 步：让桥知道它们在哪

桥**不硬编码路径** —— 用环境变量告诉它（缺的会**点名**，不会静默）：

```bash
export DSH_CHAIN_BLBRIDGE=<你 clone BlBridge 的路径>
export DSH_CHAIN_SAGE=<你 clone BannerlordSage-variant 的路径>
export DSH_CHAIN_HELPER=<你 clone Bannerlord-Helper-variant 的路径>
export BANNERLORD_DIR="<游戏根目录>"     # 例如 .../Mount & Blade II Bannerlord
export DSH_CHAIN_BUN=<bun 可执行文件>    # 只有挂两个 TS 上游时才需要
```

★ 全部可配置项见下方「环境变量」表。

### 第 3 步：验证

```bash
# ① 环境探测（只读，PowerShell 脚本；★ 会明确告诉你**缺哪一个仓库**、该设哪个变量）
pwsh -File bootstrap.ps1 -Check

# ② 桥自检（连不上的上游会被点名，其余照常）
python bl_chain.py --selftest

# ③ 跑全部验证（18 项）
python tests/run_all_tests.py

# ④ 实测各模式的成本
python bl_chain.py --measure
```

### 第 4 步：接到你的 MCP 客户端

```jsonc
// 以 Claude Desktop / Cursor 之类为例（mcpServers 段）
{
  "mcpServers": {
    "chain": {
      "command": "python",
      "args": ["<你 clone 的路径>/bannerlord-mcp-suite/bl_chain.py"],
      "env": {
        "DSH_CHAIN_MODE": "meta",                      // 省 token 的关键
        "DSH_CHAIN_BLBRIDGE": "<BlBridge 路径>",
        "DSH_CHAIN_SAGE": "<Sage 路径>",
        "DSH_CHAIN_HELPER": "<Helper 路径>",
        "BANNERLORD_DIR": "<游戏根目录>",
        "DSH_CHAIN_BUN": "<bun 路径>"
      }
    }
  }
}
```

★ **只挂 `chain` 一个就够了** —— 它内部会去起那三个
（**不要**把它们与 `chain` **同时**挂进同一个客户端：那会让同一能力出现两个入口，
且每个上游跑两份进程）。

`--selftest` **不需要**上游存在也能跑。

---

## 它由什么组成

```
bannerlord-mcp-suite/
├── bl_chain.py              ★ 链桥本体（把多个 MCP 聚合成一个工具面）
├── localization-audit/      ★ 第 4 个 MCP：汉化审计（只读，零依赖）
│   ├── la_mcp.py
│   └── tools/               两个审计真身 + 各自自测 + 注入故障对照
├── tests/                   18 项验证（含端到端、交叉校验、协议合规）
├── probe/                   独立第二实现（用于交叉校验，防"自己验自己"）
├── tools/                   构建/迁移脚本（把路径改成可配置等）
└── docs/                    设计说明与踩坑记录
```

★ **它挂载的三个业务 MCP 不在本仓库里** —— 那是**刻意的**，理由见
[`docs/why-umbrella-repo.md`](docs/why-umbrella-repo.md)。

---

## ★ "无损"是怎么证明的

这不是一句口号，而是**两条可复现的独立判据**：

| 模式 | 判据 | 在哪验证 |
|---|---|---|
| `full` | 与上游**逐字节相同**（数组级 + 逐工具 deep-compare） | `--selftest` A/B 段 |
| `slim` | **行为契约逐字段不变**：剥掉 `description` 后 schema **完全相等** | `tests/slim_contract_test.py` |
| `meta` | 常驻面只有 5 个元工具；**隐藏的工具仍可直呼调用** | `--selftest` C 段 |
| 协议面 | 每条消息符合**官方 SDK 自己的 zod schema** | `tests/capture_wire.py` + `verify_schema.mjs` |
| 度量口径 | 与**另一份独立实现**算出的字节/token 一致 | `tests/crosscheck_test.py` |

★ 为什么 `slim` 不能只说"逐字节"：它**故意**截断说明文字。
所以改用**行为等价性** —— 决定行为的是 `type`/`enum`/`default`/`required`，
决定可读性的才是 `description`。省下的 41% **全部**是说明文字。

★ 最关键的一条（本项目实测确认）：
**被 `tools/list` 隐藏的工具，`tools/call` 照样能调到。**
⇒ 所以分层**不影响能力**，只影响"能不能被搜到"。

---

## 三种模式怎么选

用环境变量，可叠加：

| 变量 | 默认 | 说明 |
|---|---|---|
| `DSH_CHAIN_MODE` | `full` | `full` / `slim` / `meta` / `slim+meta` |
| `DSH_CHAIN_GROUPS` | 空（=全部） | 逗号或加号分隔的组名（`ro`/`battle`/`write`/`launch`/`desktop`/`other`） |
| `DSH_CHAIN_SERVERS` | 空（=全部） | 只要这些上游（**避免与直连重复**） |
| `DSH_CHAIN_PYTHON` | `sys.executable` | 用哪个解释器起上游 |
| `DSH_CHAIN_BUN` | 本机路径 | Bun 可执行文件（挂 TS 上游时需要） |
| `BANNERLORD_DIR` | 本机 Steam 路径 | 游戏根目录 |
| `DSH_CHAIN_BLBRIDGE` / `_SAGE` / `_HELPER` | 本机路径 | 三个业务 MCP 的位置 |
| `DSH_CHAIN_TOKENIZER` | 空 | 真实 tokenizer（设了才精确计数，否则估算） |

★ **其余环境变量都会「原样继承」给上游** —— 包括 `NEXUS_API_KEY` 之类，
所以上游能读到自己的凭据，而本桥**不打印、不落盘**任何凭据。

### 三种典型用法

```bash
# A. 省最多 token：常驻只 5 个元工具（推荐）
DSH_CHAIN_MODE=meta python bl_chain.py

# B. 只托管一部分上游，其余直连（避免同一工具两个入口）
DSH_CHAIN_SERVERS=bannerlordsage,bannerlordhelper python bl_chain.py

# C. 只要只读工具（安全场景）
DSH_CHAIN_GROUPS=ro python bl_chain.py
```

---

## 三层用法（`meta` 模式）

```
① chain_search_tools       找到工具（支持中文，有同义词表）
② chain_get_tool_details   看它的完整 schema（原样转发，不裁剪）
③ chain_call_tool          调用（参数 {name, args}）
```

★ **也可以直呼原名** —— 不必先检索。工具名**一字不改**。
★ `chain_status` 自检（每个上游连没连上、各多少工具、当前模式成本）。
★ `chain_refresh` 在上游升级后重拉工具表，**无需重启**。

---

## `localization-audit`：第 4 个 MCP

一个**只读**的汉化审计服务器。回答两个**互补**的问题：

| 工具 | 回答 |
|---|---|
| `la_audit_coverage` | **哪些汉化键真的缺**（区分官方/社区，排除无键标记） |
| `la_dll_strings` | **DLL 里有哪些硬编码字符串**（XML 侧看不见的那些） |

★ 两者**不重叠**：XML 侧的 `{=KEY}` 与 DLL 侧的 `#US`/`#Blob` 堆是**两处**，
只查一处会漏掉约一半"界面上的英文"。

★ **只读保证有实测断言**：`tests/` 里比对调用前后的文件快照，
**新建或修改任何一个文件都算失败**。

---

## 边界（如实）

- **不保证**上游工具本身的安全性与正确性 —— 部分上游工具会**写磁盘**或**操控游戏**。
- `meta` 模式下，模型需要**先检索**才能发现工具（多一步，实测约 **1 ms**）。
- **不要**把本桥与它挂载的上游**同时**挂进同一个客户端 ——
  那会让同一能力出现**两个入口**，且每个上游**跑两份进程**。
- 本桥**不是**安全边界：它只是转发。要限制能力请用 `DSH_CHAIN_GROUPS` 或上游自己的开关。
- 本仓库**不含游戏资源**，也不含 TaleWorlds 的代码（见 `NOTICE`）。

---

## 许可

MIT（见 [`LICENSE`](LICENSE)）。
**第三方来源、商标与凭据说明见 [`NOTICE`](NOTICE)** —— 尤其请读它第 0 节
（说明本仓库**只含我们自己的代码**，不重新分发任何上游）。

---

<a id="english"></a>
## English (short)

An **MCP aggregator** for Mount & Blade II: Bannerlord tooling.

### ★ Which MCPs does this bridge call?

This repo is **a bridge, not a game tool** — so you must clone the MCPs it aggregates
(they are **not** vendored here; see [`docs/why-umbrella-repo.md`](docs/why-umbrella-repo.md)):

| # | MCP repository (**clone these**) | What it gives | Tools |
|---|---|---|---:|
| 1 | [`lcx1107816013/Bannerlord-blbridge`](https://github.com/lcx1107816013/Bannerlord-blbridge) | **Drive the game**: battles / orders / telemetry / saves / crash forensics | **57** |
| 2 | [`lcx1107816013/BannerlordSage-variant`](https://github.com/lcx1107816013/BannerlordSage-variant) | **Look things up**: source / XML / C# types / API docs | **24** |
| 3 | [`lcx1107816013/Bannerlord-Helper-variant`](https://github.com/lcx1107816013/Bannerlord-Helper-variant) | **Localization**: i18n / templates / translation / Nexus search | **10** |
| 4 | **bundled in this repo** | **Audit**: `localization-audit` (**read-only**) | **2** |

⇒ **93 tools** total; `meta` mode keeps only **5 meta-tools / 522 tokens** resident (−97.7%).

```bash
git clone https://github.com/lcx1107816013/bannerlord-mcp-suite.git
cd bannerlord-mcp-suite
git clone https://github.com/lcx1107816013/Bannerlord-blbridge.git       ../Bannerlord-blbridge
git clone https://github.com/lcx1107816013/BannerlordSage-variant.git    ../BannerlordSage-variant
git clone https://github.com/lcx1107816013/Bannerlord-Helper-variant.git ../Bannerlord-Helper-variant
```

Not sure what you're missing? Run `pwsh -File bootstrap.ps1 -Check` — it **names each
missing MCP** and prints the exact `git clone` command to fix it.

### The problem it solves

**Problem** (measured): the three business MCP servers = **91 tools / 22,387 tokens** resident
(**68.3%** of a 32K context). With the bundled audit MCP it's **93 tools / 23,148 tokens**
(**70.6%** of 32K).

**Solution**: a stable meta-tool layer. `meta` mode keeps only **5 tools / 522 tokens**
(**2.3%** of the full surface, **1.6%** of 32K) while **losing no capability** — hidden
tools remain callable by name (verified: `tools/list` hides them, `tools/call` still works).

**Losslessness is proven by two independent criteria**: `full` is byte-identical to
upstream; `slim` keeps the behavioral contract identical field-by-field
(only `description` is truncated); the wire protocol is validated against the
official SDK's own zod schemas.

Includes `localization-audit`, a **read-only** MCP server for Bannerlord
localization auditing (missing-key audit + hardcoded-string extraction).

**The three upstream MCP servers are NOT vendored here** — on purpose, to keep
upstream-sync possible. See [`docs/why-umbrella-repo.md`](docs/why-umbrella-repo.md).

MIT licensed. See [`NOTICE`](NOTICE) for third-party, trademark and credential notes.
