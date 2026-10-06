# bannerlord-mcp-suite

> 把多个《骑马与砍杀 II：霸主》相关的 **MCP 服务器**聚合成**单一入口**的桥，
> 外加一套**只读**的汉化审计工具。

[English](#english) · 中文（本页）

---

## 这个仓库解决什么问题

同时挂多个 MCP 服务器时有两个真实痛点，都是**实测**出来的（不是推测）：

| 痛点 | 实测数字 |
|---|---|
| **① 工具面吃掉上下文** | 三个服务器合计 **91 个工具 / 22,387 token** 常驻 —— 占 32K 上下文的 **66.8%** |
| **② 工具太多找不到** | 91 个工具里，模型经常选错或漏掉该用的那个 |

本仓库的 `bl_chain.py` 用一个**稳定的元工具层**解决两者：

| 模式 | 常驻工具 | 常驻 token | 占全量 |
|---|---:|---:|---:|
| `full` | 91 | 22,383 | 100% |
| `slim` | 91 | 12,955 | 57.9% |
| **`meta`** | **5** | **522** | **2.3%** |

⇒ **`meta` 模式省 97.7% 的常驻 token**，而**能力一个不少**（见下方"无损"）。

---

## 快速开始

```bash
git clone <这个仓库的地址>
cd bannerlord-mcp-suite

# ① 看它现在能连上什么（不需要任何配置，缺的会如实列出）
python bl_chain.py --selftest

# ② 跑全部验证（18 项）
python tests/run_all_tests.py

# ③ 实测各模式的成本
python bl_chain.py --measure

# ④ 当成 MCP 服务器用（stdio）
python bl_chain.py
```

`--selftest` **不需要**上游存在也能跑：连不上的上游会被**点名**，其余照常。

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
| `DSH_CHAIN_GROUPS` | 空（=全部） | 逗号或加号分隔的组名（`ro`/`battle`/`write`/`launch`/`desktop`） |
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

**Problem** (measured): three MCP servers = **91 tools / 22,387 tokens** resident
(**66.8%** of a 32K context).

**Solution**: a stable meta-tool layer. `meta` mode keeps only **5 tools / 522 tokens**
(**2.3%**) while **losing no capability** — hidden tools remain callable by name
(verified: `tools/list` hides them, `tools/call` still works).

**Losslessness is proven by two independent criteria**: `full` is byte-identical to
upstream; `slim` keeps the behavioral contract identical field-by-field
(only `description` is truncated); the wire protocol is validated against the
official SDK's own zod schemas.

Includes `localization-audit`, a **read-only** MCP server for Bannerlord
localization auditing (missing-key audit + hardcoded-string extraction).

**The three upstream MCP servers are NOT vendored here** — on purpose, to keep
upstream-sync possible. See [`docs/why-umbrella-repo.md`](docs/why-umbrella-repo.md).

MIT licensed. See [`NOTICE`](NOTICE) for third-party, trademark and credential notes.
