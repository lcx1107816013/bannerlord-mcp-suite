# -*- coding: utf-8 -*-
r"""核对我在 Helper 的 AGENTS.md 里写的断言（工具名 / 语言数 / 钩子）。

★ 为什么单独做：写文档时我列了"10 个工具"与"13 种语言" ——
   这些**必须实测核对**，不能凭印象（本项目纪律：只写已核实的）。
"""
import io
import json
import os
import re

H = r"F:\Program Files\Bannerlord.Helper"

print("=" * 70)
print("① mcp/server.ts 的工具名")
print("=" * 70)
t = io.open(os.path.join(H, "mcp", "server.ts"), encoding="utf-8").read()
names = re.findall(r"name:\s*'(bh_[a-z_]+)'", t)
print("  实测 %d 个：" % len(names))
for n in names:
    print("    ", n)

print()
print("=" * 70)
print("② 语言数")
print("=" * 70)
p = os.path.join(H, "src", "shared", "language-dictionary.ts")
if os.path.isfile(p):
    t2 = io.open(p, encoding="utf-8", errors="replace").read()
    codes = re.findall(r"code:\s*'([A-Za-z0-9\-]+)'", t2)
    print("  文件: src/shared/language-dictionary.ts")
    print("  去重 code 数: %d" % len(set(codes)))
    print("  ", sorted(set(codes)))
    LANG_N = len(set(codes))
else:
    print("  ✗ 找不到 language-dictionary.ts")
    LANG_N = None

print()
print("=" * 70)
print("③ husky / lint-staged 钩子（我写了会跑 lint）")
print("=" * 70)
pkg = json.loads(io.open(os.path.join(H, "package.json"), encoding="utf-8").read())
print("  scripts.prepare  =", pkg.get("scripts", {}).get("prepare"))
print("  scripts.lint     =", pkg.get("scripts", {}).get("lint"))
print("  scripts.lint-staged =", pkg.get("scripts", {}).get("lint-staged"))
ls = os.path.join(H, ".lintstagedrc.yml")
if os.path.isfile(ls):
    print("  .lintstagedrc.yml:")
    for line in io.open(ls, encoding="utf-8").read().split("\n"):
        if line.strip():
            print("     ", line)
print("  .husky/pre-commit 存在:", os.path.isfile(os.path.join(H, ".husky", "pre-commit")))

print()
print("=" * 70)
print("④ 我的断言核对")
print("=" * 70)
print("  我写「10 个工具」        -> 实测 %d 个  %s" % (len(names), "✅" if len(names) == 10 else "★ 不符"))
