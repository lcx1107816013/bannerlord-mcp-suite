#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""`localization-audit` MCP 服务器 —— 汉化审计（**只读**，第 4 个 MCP）。

## 它是什么

把两个本来"孤零零躺在磁盘上"的审计脚本，接成 **MCP 工具**：

| 工具 | 回答的问题 | 真身 |
|---|---|---|
| `la_audit_coverage` | **哪些汉化键真的缺了**（区分官方/社区，排除无键标记） | `tools/la_audit_coverage.py` |
| `la_dll_strings` | **DLL 里有哪些硬编码字符串**（XML 侧看不见的第 1 类） | `tools/la_dll_strings.py` |

两者**互补且不重叠**：
* XML 侧（`{=KEY}`）—— 汉化文件里声明的键；
* DLL 侧（`#US` / `#Blob` 堆）—— **根本没进 XML** 的界面英文
  （Harmony 补丁写进去的、开发者硬编码的）。

## 与 `bannerlordhelper` 的分工（★ 别搞混）

| 服务器 | 定向 | 会不会改磁盘 |
|---|---|---|
| **本服务器** | **读** —— 找出问题 | ❌ **一处都不写** |
| `bannerlordhelper` | **写** —— 把缺的补上 | ✅ 改 `Modules\*.xml` |

⇒ **本服务器是"体检"，Helper 是"手术"。**
⇒ 本服务器**只读**，所以**不需要**任何 key、任何网络、任何游戏在跑。

## 只读保证（可核）

* 全部输出走 stdout（MCP 协议）；**不写任何文件**；
* 实测两个真身的写操作数 = **0 处**（`open(...,'w')` / `writeFile` / `shutil.copy` 皆无）；
* 唯一的"写入"是**读**取 DLL/XML（`open(...,'rb')`）。

## 与 `bl_chain` 的关系

本服务器是 `bl_chain` 的**第 4 个上游**：`SERVERS` 加一条即可聚合。
⇒ 三个业务 MCP（查/造/译）+ 本服务器（审计），由 chain 统一入口。

## 协议

MCP over stdio，**行式 JSON**（不是 Content-Length 帧）。
骨架抄自 `BlBridge/tools/bl_mcp.py`（本项目已验证的形态），
**零第三方依赖**（只用标准库）—— 与两个真身一致。
"""
import io
import json
import os
import sys

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "localization-audit"
SERVER_VERSION = "0.1.0"

# 游戏目录：**先看环境变量**（与 BlBridge / Sage 同口径），再退到真身的内置默认
GAME_DIR_ENV = "BANNERLORD_DIR"


def _game_dir(explicit=None):
    if explicit:
        return explicit
    env = os.environ.get(GAME_DIR_ENV)
    if env:
        return env
    import la_audit_coverage as _a
    return _a.DEFAULT_GAME


# ── 工具表 ────────────────────────────────────────────────────────────────
TOOL_DEFS = [
    {
        "name": "la_audit_coverage",
        "description": (
            "汉化**真缺键审计**（只读）：列出 locale 下**真的缺翻译**的键，按模组汇总。"
            "回答「哪些 mod 的汉化有缺口、缺多少」。"
            "★ 口径已修正四处（这四处都会静默给出错误答案，故显式说明）："
            "① `{=!}`（1686 次）与 `{=*}`（184 次）是**无键标记**，必须排除 —— "
            "否则会把「故意不翻的开发者标识」算成缺翻译；"
            "② 官方 / 社区**分开** —— 官方模组缺中文是「没装官方中文包」，"
            "算进 mod 的账会得出「你的 mod 缺一万条」这种荒谬结论；"
            "③ **UTF-16 BOM 解码** —— 官方中文包是 UTF-16，按 UTF-8 扫会得到「官方翻译 0 条」；"
            "④ 键名区分大小写（`SandBox` 不是 `Sandbox`）。"
            "scope=community 只审社区模组（默认，这才是「你的 mod 缺什么」）；"
            "official 只审官方；all 全审。"
            "**只读，不写任何文件，不需要 key、不需要游戏在跑。**"),
        "inputSchema": {
            "type": "object",
            "properties": {
                "gameDir": {"type": "string",
                            "description": "游戏根目录（含 Modules/）。省略则用 BANNERLORD_DIR 环境变量"},
                "locale": {"type": "string", "default": "CNs",
                           "description": "语言代码，如 CNs（简中）/ CNt（繁中）"},
                "scope": {"type": "string", "enum": ["community", "official", "all"],
                          "default": "community", "description": "审计范围"},
                "module": {"type": "string", "description": "只审这一个模组（精确名，如 RBM）"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "la_dll_strings",
        "description": (
            "从 .NET 程序集抽取**硬编码字符串**（只读）—— 第 1 类「界面上的英文」的探测端。"
            "为什么需要它：`la_audit_coverage` 只做 **XML 侧**（`{=KEY}`），"
            "而**根本没进 XML** 的英文（Harmony 补丁写进去的、开发者硬编码的）"
            "在 XML 侧**永远查不到** —— 那正是「装了汉化界面还是英文」的常见原因。"
            "★ 两个堆都读（少读一个就会漏掉一半）："
            "`#US`（UTF-16LE，编译器字符串字面量）+ `#Blob`（UTF-8，元数据串）。"
            "★ 两种口径都给（避免与别处对不上）：出现次数（不去重）与不同文本数（去重）。"
            "**只读，不执行 DLL、不联网。**"),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dll": {"type": "string", "description": "DLL 绝对路径（与 module 二选一）"},
                "module": {"type": "string",
                           "description": "模组名（自动找 Modules/<名>/bin/Win64_Shipping_Client/*.dll）"},
                "gameDir": {"type": "string", "description": "游戏根目录（配合 module 用）"},
                "includeKeyed": {"type": "boolean", "default": False,
                                 "description": "是否也列出带 {=KEY} 的串（默认只列无键的）"},
            },
            "additionalProperties": False,
        },
    },
]


def _text(s):
    return {"content": [{"type": "text", "text": s}], "isError": False}


def call_tool(name, args):
    args = args or {}
    if name == "la_audit_coverage":
        import la_audit_coverage as A
        rep = A.audit(_game_dir(args.get("gameDir")),
                      locale=args.get("locale") or "CNs",
                      scope=args.get("scope") or "community",
                      only_module=args.get("module"))
        if not rep.get("ok"):
            return {"content": [{"type": "text", "text": "审计失败: %s" % rep.get("error")}],
                    "isError": True}
        return _text(A.fmt(rep))

    if name == "la_dll_strings":
        import la_dll_strings as D
        path = args.get("dll")
        if not path and args.get("module"):
            path = D.find_dll(_game_dir(args.get("gameDir")), args["module"])
            if not path:
                return {"content": [{"type": "text",
                                     "text": "找不到模组 %r 的 DLL（gameDir=%s）"
                                             % (args["module"], _game_dir(args.get("gameDir")))}],
                        "isError": True}
        if not path:
            return {"content": [{"type": "text", "text": "需要 dll 或 module 参数"}],
                    "isError": True}
        if not os.path.isfile(path):
            return {"content": [{"type": "text", "text": "找不到 DLL: %s" % path}],
                    "isError": True}
        r = D.analyze(path, include_keyed=bool(args.get("includeKeyed")))
        if not r.get("ok"):
            return {"content": [{"type": "text", "text": "解析失败: %s" % r.get("error")}],
                    "isError": True}
        return _text(D.fmt(r))

    raise ValueError("unknown tool: %s" % name)


# ── MCP 协议（stdio，行式 JSON）──────────────────────────────────────────
def _send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result(req_id, result):
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code, message):
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def handle(req):
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        _result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
        return
    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return
    if method == "ping":
        _result(req_id, {})
        return
    if method == "tools/list":
        _result(req_id, {"tools": TOOL_DEFS})
        return
    if method == "tools/call":
        try:
            out = call_tool(params.get("name"), params.get("arguments") or {})
            _result(req_id, out)
        except Exception as exc:  # noqa: BLE001
            # 参数类异常直接给消息（调用方要的是"哪儿错了"，不是 Python 类型名）
            if isinstance(exc, (ValueError, IOError, OSError)):
                text = str(exc)
            else:
                text = "工具执行失败: %r" % (exc,)
            _result(req_id, {"content": [{"type": "text", "text": text}], "isError": True})
        return
    _error(req_id, -32601, "method not found: %s" % method)


def _force_utf8_stdio():
    """把 stdio 钉成 UTF-8 —— 协议要求。

    不钉死时 Python 按 locale 编码（中文 Windows = GBK）写 stdout，
    而宿主按 UTF-8 解码 ⇒ 工具描述里的中文全变 U+FFFD 乱码。
    ⚠️ 只在入口调用，**不要**放模块级（自测会 import 本模块）。
    """
    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def main():
    _force_utf8_stdio()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        if isinstance(req, list):
            for r in req:
                handle(r)
        else:
            handle(req)
    return 0


if __name__ == "__main__":
    sys.exit(main())
