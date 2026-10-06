# -*- coding: utf-8 -*-
"""把复制过来的两个审计工具**一致地改名**：`bh_` → `la_`（localization-audit）。

为什么必须改（不是洁癖）：
  它们本来叫 `bh_*`（Bannerlord.**H**elper 的命名域）。现在要独立成
  **第 4 个 MCP**（`localization-audit`），沿用 `bh_` 会**误导**：
  看名字的人会以为它属于 Helper 那个 TS 服务器 —— 而它其实是
  **独立的 Python 服务**，与 Helper 没有代码关系。

改名范围（**实测查出来的，不是猜的**）：
  · `importlib.import_module("bh_audit_coverage")`  ← selftest / inject 里
  · `sys.modules["bh_dll_strings"]`
  · `TOOL = os.path.join(HERE, "bh_audit_coverage.py")`
  · docstring / 用法示例里的文件名

★ 纪律：改完**必须复跑两组自测**（T1–T6 与 S1–S7）+ 注入故障对照 ——
  否则"改名把自测改坏"会静默发生。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "tools")

MAP = [
    ("bh_audit_coverage", "la_audit_coverage"),
    ("bh_dll_strings", "la_dll_strings"),
]

TARGETS = [
    "la_audit_coverage.py",
    "la_dll_strings.py",
    "selftest_audit.py",
    "selftest_dll_strings.py",
    "inject_fault_audit.py",
    "inject_fault_dll.py",
]


def main():
    total = 0
    for name in TARGETS:
        p = os.path.join(TOOLS, name)
        if not os.path.isfile(p):
            print("  ✗ 缺文件:", name)
            continue
        t = io.open(p, encoding="utf-8").read()
        before = t
        n = 0
        for old, new in MAP:
            c = t.count(old)
            if c:
                t = t.replace(old, new)
                n += c
        if t != before:
            # 保持 LF（项目编码纪律）
            t = t.replace("\r\n", "\n")
            io.open(p, "w", encoding="utf-8", newline="\n").write(t)
            print("  %-28s 替换 %d 处" % (name, n))
            total += n
        else:
            print("  %-28s （无需改）" % name)
    print()
    print("合计替换:", total)

    # ── 校验：不该再出现旧名 ──────────────────────────────────────────
    print()
    print("=== 残留检查（应全为 0）===")
    bad = 0
    for name in TARGETS:
        p = os.path.join(TOOLS, name)
        t = io.open(p, encoding="utf-8").read()
        for old, _new in MAP:
            # 排除"说明这是从 bh_ 改来的"这类注释（本脚本自己写的）
            hits = [m for m in re.finditer(re.escape(old), t)]
            if hits:
                print("  ✗ %s 仍含 %s（%d 处）" % (name, old, len(hits)))
                bad += len(hits)
    if not bad:
        print("  ✅ 无残留")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
