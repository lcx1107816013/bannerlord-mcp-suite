# -*- coding: utf-8 -*-
r"""诊断 `module/mcp/manifest.json` 的乱码：能否还原？根因是什么？

## 已知事实

- 该文件**已入库**（`git ls-files` 命中），且是 **AI 读的第一个文件**
  （`module/mcp/` 是给 AI 的"MCP 包"）
- 6 个**描述字段**含 **848 个私用区字符（U+E000–U+F8FF）**：
  `display_name` / `description` / `long_description` / `title` / `note`
- **不是本次引入**：`HEAD~1` 也是同样 848 个
- 后果：`json.loads()` **直接失败**（"Invalid control character"）
  ⇒ AI 拿到的是一个**读不动的 manifest**

## 本脚本要回答

1. 这些 PUA 字符能不能解回正常中文？（试多种编码链）
2. 根因是哪一种 mojibake？（UTF-8→GBK / latin-1 往返 / 其它）
3. 有没有"源"可以重新生成（而不是硬修这个文件）？
"""
import io
import json
import os
import re
import subprocess
import sys

REPO = r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge"
P = os.path.join(REPO, "module", "mcp", "manifest.json")

t = io.open(P, encoding="utf-8", errors="replace").read()
lines = t.split("\n")

print("=" * 78)
print("① 逐字段：PUA 字符数")
print("=" * 78)
fields = {}
for i, l in enumerate(lines):
    # ⚠️ 不能用 `re.match(r'...$')`：行里含**控制字符**（\x1f 等）会让 `.` 匹配失败。
    #    改成"取第一个引号对做键、其余做值"的手工切分。
    mm = re.match(r'\s*"([^"]+)"\s*:\s*"', l)
    if not mm:
        continue
    k = mm.group(1)
    rest = l[mm.end():]
    # 值的结尾：最后一个 `",` 或 `"` （行尾）
    end = rest.rstrip()
    if end.endswith(","):
        end = end[:-1].rstrip()
    if end.endswith('"'):
        end = end[:-1]
    v = end
    pua = sum(1 for c in v if 0xE000 <= ord(c) <= 0xF8FF)
    if pua:
        fields[k] = v
        print("  L%-3d %-18s PUA=%-4d 长度=%-5d" % (i + 1, k, pua, len(v)))

print()
print("=" * 78)
print("② 能否还原？（对一个样本试编码链）")
print("=" * 78)
sample = fields.get("display_name") or next(iter(fields.values()))
print("  样本（前 90 字符）:")
print("   ", sample[:90])
print()

# 把 PUA 先替换掉再看——PUA 是"无法映射的字节"的替身，通常已不可逆
pua_count = sum(1 for c in sample if 0xE000 <= ord(c) <= 0xF8FF)
print("  该样本含 PUA %d 个 ⇒ 这些字节在解码时**已丢失原值**" % pua_count)
print()

chains = [
    ("gb18030", "utf-8"), ("gbk", "utf-8"),
    ("latin-1", "gb18030"), ("latin-1", "utf-8"),
    ("cp1252", "utf-8"), ("utf-8", "gb18030"),
]
for a, b in chains:
    try:
        r = sample.encode(a, errors="strict").decode(b, errors="strict")
        ok = all(0x4E00 <= ord(c) <= 0x9FFF or ord(c) < 0x3000 for c in r)
        print("  %-10s -> %-9s : %s   %s" % (a, b, r[:52], "看起来像正常中文" if ok else ""))
    except Exception as e:  # noqa: BLE001
        print("  %-10s -> %-9s : 失败 %s" % (a, b, str(e)[:46]))

print()
print("=" * 78)
print("③ 有没有『源』可以重新生成（比硬修更好）")
print("=" * 78)
# 找生成器：搜哪个脚本会写 module/mcp/manifest.json
hits = []
for root, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "out", "dist")]
    for f in files:
        if not f.endswith((".py", ".ps1", ".cs", ".md", ".json")):
            continue
        p = os.path.join(root, f)
        try:
            c = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "manifest.json" in c and "module" in c:
            hits.append(os.path.relpath(p, REPO))
for h in sorted(set(hits))[:12]:
    print("  ", h)

print()
print("=" * 78)
print("④ 该文件能否被 json.loads 解析（AI 的实际处境）")
print("=" * 78)
try:
    json.loads(t)
    print("  ✅ 可解析")
except Exception as e:  # noqa: BLE001
    print("  ✗ 解析失败: %s" % e)
    print("    ⇒ AI 拿到的是一个**读不动的 manifest**")
