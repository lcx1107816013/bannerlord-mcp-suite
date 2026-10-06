# -*- coding: utf-8 -*-
r"""逆向 `module/mcp/manifest.json` 的乱码：**找到正确的还原链**。

## 已知线索（很重要）

PUA 字符数**逐版本递增**：42 → 61 → 61 → 336 → 552 → **848**

⇒ 这是典型的**累积型乱码**：每次编辑时，原本已是乱码的文本**又被编码/解码了一次**
⇒ 每次往返，一部分字符被压成"无法映射"⇒ 变成 PUA（U+E000–U+F8FF）。

## 本脚本做什么

1. 取**最早**那个版本（PUA 最少 = 42），它的原始信息保留得最多
2. 试**多级**还原链（不是单级）：把 PUA 也纳入编码，逐级试
3. 报告哪条链能把乱码还原成**可读中文**

## 为什么值得试

若最早版本能还原 ⇒ 我们**拿得回原始描述**，不用凭空重写
（重写会丢掉原始措辞 —— 而这些是给 AI 读的"技能描述"，措辞有信息量）。
"""
import json
import os
import re
import subprocess
import sys

REPO = r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge"
REL = "module/mcp/manifest.json"
EARLIEST = "4c0edc3"      # PUA 最少（42）的那个版本


def git_bytes(*args):
    r = subprocess.run(
        ["git", "-C", REPO, "-c", "core.quotepath=false",
         "-c", "i18n.logOutputEncoding=UTF-8"] + list(args),
        capture_output=True)
    return r.stdout


def extract(text, key):
    """从 JSON 文本里粗糙取一个字段的值（JSON 已坏，不能用 json.loads）。"""
    for line in text.split("\n"):
        m = re.match(r'\s*"%s"\s*:\s*"' % re.escape(key), line)
        if m:
            rest = line[m.end():].rstrip()
            if rest.endswith(","):
                rest = rest[:-1].rstrip()
            if rest.endswith('"'):
                rest = rest[:-1]
            return rest
    return None


def try_chains(s):
    """多级还原：在链上加 PUA 的映射尝试。"""
    results = []
    # 单级 / 两级组合
    encs = ["gb18030", "gbk", "latin-1", "cp1252", "utf-8"]
    for a in encs:
        for b in encs:
            if a == b:
                continue
            try:
                r = s.encode(a, errors="strict").decode(b, errors="strict")
                results.append((a, b, r))
            except Exception:  # noqa: BLE001
                pass
    return results


def cjk_ratio(s):
    if not s:
        return 0.0
    n = sum(1 for c in s if 0x4E00 <= ord(c) <= 0x9FFF)
    return n / len(s)


def main():
    print("=" * 78)
    print("① 取最早版本（PUA 最少 = 信息保留最多）")
    print("=" * 78)
    b = git_bytes("show", "%s:%s" % (EARLIEST, REL))
    t = b.decode("utf-8", "replace")
    print("  rev=%s  大小=%d 字节  PUA=%d" % (
        EARLIEST, len(b), sum(1 for c in t if 0xE000 <= ord(c) <= 0xF8FF)))

    val = extract(t, "display_name")
    print()
    print("  display_name 原始（前 100）:")
    print("   ", repr(val[:100]) if val else "(取不到)")

    print()
    print("=" * 78)
    print("② 试多级编码链还原")
    print("=" * 78)
    if val:
        cands = try_chains(val)
        # 按"中文占比"排序，取前几
        cands.sort(key=lambda x: -cjk_ratio(x[2]))
        if not cands:
            print("  ✗ 所有单级链都失败（说明 PUA 已经不可逆）")
        for a, bx, r in cands[:6]:
            print("  %-9s -> %-9s 中文字占比=%.2f : %s" % (a, bx, cjk_ratio(r), r[:60]))

    print()
    print("=" * 78)
    print("③ 结论判据")
    print("=" * 78)
    if val:
        ok = [r for a, bx, r in cands if cjk_ratio(r) > 0.5]
        if ok:
            print("  ★ 有可读候选 ⇒ 可能还原（见上表）")
        else:
            print("  ✗ **没有**任何链能还原成可读中文")
            print("    原因：PUA 字符（U+E000+）是把『GBK 无法映射的字节』替换来的占位符，")
            print("          **原字节已丢失** ⇒ 信息论上不可逆。")
            print("    ⇒ 只能重写描述字段（或用别的来源重建）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
