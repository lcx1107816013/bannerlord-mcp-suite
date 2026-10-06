# -*- coding: utf-8 -*-
r"""精确核验 `module/mcp/manifest.json` 到底坏在哪。

## 为什么要单独查（前后矛盾）

- `json.loads()` 报 `Invalid control character at: line 4 column 251`
- 但我按字节扫 `<0x20`（除 \n \r \t）⇒ **一个都没有**

⇒ 两者不可能同时为真 ⇒ 我的某一次读取引入了偏差。
（嫌疑：我用过 `errors="replace"` 读，而 replace 会把**非法 UTF-8 字节**换成 U+FFFD，
  那是 >0x20 的字符 —— 于是"控制字符"是在**解码那一刻**由别的字节产生的。）

## 本脚本（每步都不加 errors=，让问题自己暴露）

1. 该文件是不是**合法 UTF-8**？（严格解码）
2. 若不合法 ⇒ 非法字节在哪、长什么样
3. 严格解码后 `json.loads` 报的"控制字符"具体是哪个字符、哪个偏移
"""
import io
import json
import os
import sys

P = r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge\module\mcp\manifest.json"

b = io.open(P, "rb").read()
print("文件大小: %d 字节" % len(b))

print()
print("=" * 78)
print("① 严格 UTF-8 解码")
print("=" * 78)
try:
    t = b.decode("utf-8")
    print("  ✅ 是合法 UTF-8（%d 字符）" % len(t))
except UnicodeDecodeError as e:
    print("  ✗ **不是合法 UTF-8**")
    print("    位置: %d  原因: %s" % (e.start, e.reason))
    print("    上下文 bytes:", b[max(0, e.start - 20):e.start + 20])
    print("    ⇒ 这就是根因：文件里混着**非 UTF-8 字节**")
    # 用 replace 读，继续后面的分析
    t = b.decode("utf-8", "replace")

print()
print("=" * 78)
print("② 严格解码的文本里，json.loads 报的『控制字符』是哪个")
print("=" * 78)
try:
    json.loads(t)
    print("  ✅ 现在能解析了")
except json.JSONDecodeError as e:
    print("  ✗ 报错: %s" % e)
    print("    位置 char offset = %d（行 %d 列 %d）" % (e.pos, e.lineno, e.colno))
    lo, hi = max(0, e.pos - 3), min(len(t), e.pos + 3)
    for i in range(lo, hi):
        c = t[i]
        mark = "  ← 这里" if i == e.pos else ""
        print("      [%6d] U+%04X %r%s" % (i, ord(c), c, mark))
    print()
    print("    ⇒ 该字符的 code point = U+%04X" % ord(t[e.pos]))
    print("       若 <0x20 ⇒ 真的是控制字符；否则说明读入时已被替换过。")

print()
print("=" * 78)
print("③ PUA（乱码）统计 —— 用严格解码的文本")
print("=" * 78)
pua = [i for i, c in enumerate(t) if 0xE000 <= ord(c) <= 0xF8FF]
print("  PUA 字符数: %d" % len(pua))
print("  首个 PUA 偏移: %s" % (pua[0] if pua else "无"))
if pua:
    i = pua[0]
    print("    上下文: %r" % t[max(0, i - 30):i + 30])
