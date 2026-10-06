# -*- coding: utf-8 -*-
r"""把 `tests/` 里的路径锚点改成"伞仓布局"可用。

## 为什么需要

上游原布局：**所有脚本与 `bl_chain.py` 同目录**，所以每个脚本都写
`HERE = os.path.dirname(os.path.abspath(__file__))` 然后 `import bl_chain`。

伞仓新布局：脚本进了 `tests/`，而 `bl_chain.py` 在**上一级** ⇒
`import bl_chain` 立刻 `ModuleNotFoundError`（实测 13/18 项失败全是这一个根因）。

## 改法（两处，都是机械的）

① `ROOT = os.path.dirname(HERE)` 并把它加进 `sys.path`，同时 `bl_chain.py` 的路径
   从 `os.path.join(HERE, "bl_chain.py")` 改成 `os.path.join(ROOT, "bl_chain.py")`。
② `PROBE = r"E:\Document\_mcp_probe"` → 相对伞仓的 `ROOT/probe`（它已经被抄进来了）。

★ 纪律：改完**必须复跑全套**，不能只看"import 不报错"。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TESTS = os.path.join(ROOT, "tests")

# 要在 sys.path 里加 ROOT 的锚点（紧随 HERE 定义之后插入）
SYS_PATH_INS = (
    'ROOT = os.path.dirname(HERE)          # 伞仓根（bl_chain.py / localization-audit 在这）\n'
    'if ROOT not in sys.path:\n'
    '    sys.path.insert(0, ROOT)\n'
    'if HERE not in sys.path:\n'
    '    sys.path.insert(0, HERE)\n'
)


def main():
    files = [f for f in sorted(os.listdir(TESTS)) if f.endswith(".py")]
    changed = 0
    for f in files:
        p = os.path.join(TESTS, f)
        t = io.open(p, encoding="utf-8").read()
        if "ROOT = os.path.dirname(HERE)" in t:
            print("  %-28s 已改过（幂等）" % f)
            continue
        orig = t

        # ① HERE 定义之后插入 ROOT + sys.path
        anchor = "HERE = os.path.dirname(os.path.abspath(__file__))"
        if anchor in t:
            t = t.replace(anchor, anchor + "\n" + SYS_PATH_INS, 1)

        # ② 指向 bl_chain.py 的路径改到 ROOT
        t = t.replace('os.path.join(HERE, "bl_chain.py")',
                      'os.path.join(ROOT, "bl_chain.py")')
        t = t.replace("os.path.join(HERE, 'bl_chain.py')",
                      "os.path.join(ROOT, 'bl_chain.py')")

        # ③ PROBE 改到伞仓内的 probe/
        t = re.sub(r'^PROBE\s*=\s*r"E:\\Document\\_mcp_probe"\s*$',
                   'PROBE = os.path.join(ROOT, "probe")', t, flags=re.M)

        if t != orig:
            io.open(p, "w", encoding="utf-8", newline="\n").write(t)
            print("  %-28s 已改" % f)
            changed += 1
        else:
            print("  %-28s （无需改）" % f)

    print()
    print("改动文件数:", changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
