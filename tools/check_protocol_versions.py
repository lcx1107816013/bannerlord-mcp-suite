# -*- coding: utf-8 -*-
r"""查官方 SDK 支持的 protocolVersion 列表，并判断我方的 `2024-11-05` 在不在里面。

## 为什么这条最重要

四个服务器里，**三个是我们手写的 stdio**，硬编码
`PROTOCOL_VERSION = "2024-11-05"`（这是 MCP 的第一个正式版本）。

而官方 SDK 1.30.0 的 `LATEST` 已经到 `2025-06-18` 一带。
⇒ **关键问题**：SDK 还会不会**向后兼容** `2024-11-05`？

- 若**在** `SUPPORTED_PROTOCOL_VERSIONS` 里 ⇒ 规范上允许协商到它 ⇒ 兼容面宽
- 若**不在** ⇒ 能不能连上就取决于**具体实现**是否宽容（不能断言"支持所有底座"）

★ 前一步实测：官方 SDK 1.30.0 的 Client **确实连上了**我们那三个（4/4 通过）。
  本脚本是用来看**为什么**能连 —— 是"规范允许"还是"实现宽容"。
"""
import io
import os
import re
import sys

CANDIDATES = [
    r"F:\Program Files\Bannerlord.Helper\node_modules\@modelcontextprotocol\sdk\dist\esm\types.js",
    r"F:\Program Files\Bannerlord.Helper\node_modules\@modelcontextprotocol\sdk\dist\cjs\types.js",
]


def main():
    path = next((p for p in CANDIDATES if os.path.isfile(p)), None)
    if not path:
        print("  ✗ 找不到 SDK 的 types.js")
        return 1
    t = io.open(path, encoding="utf-8", errors="replace").read()
    print("  文件: %s" % path)
    print()

    m = re.search(r"SUPPORTED_PROTOCOL_VERSIONS\s*=\s*\[(.*?)\]", t, re.S)
    versions = re.findall(r"'([0-9\-]+)'", m.group(1)) if m else []
    m2 = re.search(r"LATEST_PROTOCOL_VERSION\s*=\s*'([0-9\-]+)'", t)
    latest = m2.group(1) if m2 else "?"
    m3 = re.search(r"DEFAULT_NEGOTIATED_PROTOCOL_VERSION\s*=\s*'([0-9\-]+)'", t)
    default = m3.group(1) if m3 else "?"

    print("=" * 68)
    print("官方 SDK 支持的 protocolVersion")
    print("=" * 68)
    print("  LATEST              = %s" % latest)
    print("  DEFAULT_NEGOTIATED  = %s" % default)
    print("  SUPPORTED 列表:")
    for v in versions:
        print("     ", v)

    print()
    print("=" * 68)
    print("★ 我方的 2024-11-05 在支持列表里吗")
    print("=" * 68)
    ours = "2024-11-05"
    if ours in versions:
        print("  ✅ 在 —— 规范明确允许协商到它 ⇒ 兼容面宽（不依赖实现宽容）")
    else:
        print("  ⚠️ **不在** —— 说明 SDK 1.30.0 已不再把 %s 列为受支持版本。" % ours)
        print("     但前一步实测它**确实连上了**我们那三个 ⇒ 能连是**实现侧的向后兼容**，")
        print("     而不是规范保证。")
        print("     ⇒ 对外的说法应当是：")
        print("        「**与官方 SDK 1.30.0 实测互通**」，")
        print("         而不是「**支持所有底座**」（后者我们无法证明）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
