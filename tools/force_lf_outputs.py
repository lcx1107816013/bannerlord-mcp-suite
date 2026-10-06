# -*- coding: utf-8 -*-
r"""统一把**测试产出**写成 LF（项目纪律：UTF-8 无 BOM + **LF**）。

## 为什么必须改源而不是"事后转换"

这些脚本用 `open(path, "w", encoding="utf-8")` 写文件 ——
在 Windows 上**文本模式默认把 `\n` 转成 `\r\n`** ⇒ 产出物是 CRLF。

⚠️ 若只做"事后转 LF"，**下次跑测试又会变回 CRLF** ⇒ 每次都有脏 diff。
⇒ 正解是**在写的地方加 `newline="\n"`**（Python 3 支持），让产出稳定。

## 改哪些

只改**写文件**的调用（`"w"` 模式），不动读的。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TARGETS = [
    r"tests\gen_inventory.py",
    r"tests\real_tokens.py",
    r"tests\capture_wire.py",
    r"probe\measure_any.py",
]


def main():
    total = 0
    for rel in TARGETS:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            print("  %-28s （不存在，跳过）" % rel)
            continue
        t = io.open(p, encoding="utf-8").read()
        orig = t

        # 只给 "w" 模式的 open 加 newline="\n"（若还没有）
        def fix(m):
            call = m.group(0)
            if "newline=" in call:
                return call
            return call[:-1] + ', newline="\\n")' if call.endswith(")") else call

        t = re.sub(r'open\([^()]*?["\']w["\'][^()]*?\)', fix, t)

        if t != orig:
            io.open(p, "w", encoding="utf-8", newline="\n").write(t)
            n = len(re.findall(r'newline="\\n"', t))
            print("  %-28s 已改（现有 %d 处 newline）" % (rel, n))
            total += 1
        else:
            print("  %-28s （无需改）" % rel)

    print()
    print("改动文件数:", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
