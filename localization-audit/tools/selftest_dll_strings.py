#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""自测：`la_dll_strings.py` 的**两个堆都真的读到了**。

## 为什么按"位置"断言

本工具最大的坑不是"跑不起来"，而是**静默漏掉一半**：

    第一版 `#Blob` 解析要求「**整项**按 UTF-8 解得出且像文本」
    ⇒ 而 blob 项常是**多值打包**的（`[string][int][string]`）
    ⇒ 整项解码几乎必然失败 ⇒ **得 0 条**，但脚本**照常跑完、输出正常**。

知识库把这件事的后果写得很重：

> **漏扫一半会得出"已全覆盖"的错误结论**，与第 2 条"有键却不生效"的表象难以区分。

⇒ 所以必须**逐位置断言**，且**两个位置都必须非零**。

## 断言

  S1 `#Blob`（UTF-8）**非零** ← 直击上面那个坑
  S2 `#US`（UTF-16LE）**非零**
  S3 **两处都非零** ⇒ "只扫一种会漏"的前提在本机成立
  S4 `#US` 堆被**完整遍历**（不提前 break）
  S5 用知识库的 **GGG blob 270** 校准（±15%）
  S6 抽取结果**不含替换字符 / 控制字符**（★ 见下）
  S7 护栏：任何一份 DLL 都不许出现"两个堆都 0"

## ★ S6 是怎么来的（注入对照暴露的）

`inject_fault_dll.py` 的 I2 注入（**不剥 `#US` 每项的终止字节**）第一次**漏过了** ——
因为原判据只比"**条数**"，而那个 bug **条数不变**（都是 66），
只是**每条内容尾部多一个替换字符**（实测 70 条**全部**不同）。

⇒ 于是加 S6：**检查内容干净**（无 U+FFFD、无控制字符）。
这条判据才是真正能拦住"解码没剥干净"的那一条。
"""
import importlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
GAME = (os.environ.get("BANNERLORD_DIR")
        or r"G:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")

# 覆盖不同类型的模组：有 MCM 的 / 纯 ldstr 的 / 小的
CASES = ["GovernorsGonnaGovern", "WanderersInParties", "HarvestAndProduction",
         "RTSCamera", "BetterBanditsPlus", "BellumCivile"]


def main():
    for n in ("stdout", "stderr"):
        try:
            getattr(sys, n).reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    if "la_dll_strings" in sys.modules:
        del sys.modules["la_dll_strings"]
    m = importlib.import_module("la_dll_strings")

    fails = []
    print("| 模组 | #Blob 无键 | #US 无键 | 合计 | blob 键 | us 键 | 并集 |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    rows = []
    for mod in CASES:
        dll = m.find_dll(GAME, mod)
        if not dll:
            print("| `%s` | **找不到 DLL** | | | | | |" % mod)
            fails.append("%s 找不到 DLL" % mod)
            continue
        r = m.analyze(dll)
        if not r.get("ok"):
            print("| `%s` | **解析失败** | | | | | |" % mod)
            fails.append("%s 解析失败: %s" % (mod, r.get("error")))
            continue
        rows.append((mod, dll, r))
        k = r["keys"]
        print("| `%s` | **%d** | **%d** | %d | %d | %d | %d |"
              % (mod, r["blob"]["bare"], r["us"]["bare"], r["hardcodedTotal"],
                 k["blobOnly"], k["usOnly"], k["union"]))
    print()

    # ── S1/S2/S3 两个位置都非零 ───────────────────────────────────
    print("S1/S2/S3 两个位置都必须读到东西")
    blob_zero = [m_ for m_, _d, r in rows if r["blob"]["bare"] == 0]
    us_zero = [m_ for m_, _d, r in rows if r["us"]["bare"] == 0]
    both_zero = [m_ for m_, _d, r in rows
                 if r["blob"]["bare"] == 0 and r["us"]["bare"] == 0]

    if blob_zero:
        # `#Blob` 为空**可能**是该 DLL 真没有特性参数 ⇒ 只提示，不判失败；
        # 但**全部**都空就一定是解析坏了
        if len(blob_zero) == len(rows):
            fails.append("S1 **所有** DLL 的 `#Blob` 都是 0 —— 解析很可能坏了（多值打包坑）")
            print("   [!!] 所有 #Blob 均为 0 ⇒ 多值打包判据失效")
        else:
            print("   [ok] `#Blob` 非零的有 %d/%d（%s 本就无特性参数 ⇒ 允许为 0）"
                  % (len(rows) - len(blob_zero), len(rows), ", ".join(blob_zero)))
    else:
        print("   [ok] `#Blob` 全部非零（%d 份）" % len(rows))

    if us_zero:
        fails.append("S2 这些 DLL 的 `#US` 为 0：%s" % us_zero)
        print("   [!!] `#US` 为 0：%s" % ", ".join(us_zero))
    else:
        print("   [ok] `#US` 全部非零（%d 份）" % len(rows))

    if both_zero:
        fails.append("S3 两个堆都 0：%s" % both_zero)
        print("   [!!] 两个堆都 0：%s" % ", ".join(both_zero))
    else:
        print("   [ok] 没有「两个堆都 0」的 DLL")

    has_both = [m_ for m_, _d, r in rows
                if r["blob"]["bare"] > 0 and r["us"]["bare"] > 0]
    if has_both:
        print("   [ok] **两处都有内容**的模组 %d 个 ⇒ 「只扫一种会漏」在本机成立"
              % len(has_both))
    else:
        print("   ⚠ 没有同时两处都有内容的模组（无法在本机演示'会漏'）")

    # ── S4 #US 完整遍历 ──────────────────────────────────────────
    print("\nS4 `#US` 堆是否被完整遍历（不提前 break）")
    bad_walk = []
    for mod, dll, r in rows:
        got, data, err = m.read_cli_streams(dll)
        if err:
            continue
        streams, _ = got
        off, size = streams["#US"]
        end = off + size
        p = off + 1
        while p < end:
            try:
                length, n = m.read_compressed_uint(data, p)
            except IndexError:
                break
            if length == 0:
                p += n
                continue
            p += n + length
        if p < end - 4:
            bad_walk.append((mod, size, p - off))
    if bad_walk:
        fails.append("S4 这些 DLL 的 `#US` 未走到堆尾：%s" % bad_walk)
        for mod, size, walked in bad_walk:
            print("   [!!] %s: 堆 %d 字节，只走到 %d" % (mod, size, walked))
    else:
        print("   [ok] 全部 %d 份都走到了堆尾" % len(rows))

    # ── S5 用知识库的 GGG 270 校准 ────────────────────────────────
    print("\nS5 用知识库基准校准（GGG blob = 270，`concepts/bannerlord-display-layer-rules.md:41`）")
    ggg = [r for m_, _d, r in rows if m_ == "GovernorsGonnaGovern"]
    if ggg:
        n_blob = ggg[0]["blob"]["bare"]
        dev = abs(n_blob - 270) / 270 * 100
        if dev <= 15:
            print("   [ok] 实测 %d vs 知识库 270（偏差 %.0f%%）⇒ 口径吻合"
                  % (n_blob, dev))
        else:
            fails.append("S5 GGG blob 实测 %d 与知识库 270 偏差 %.0f%%（>15%%）"
                         % (n_blob, dev))
            print("   [!!] 实测 %d vs 270（偏差 %.0f%%）" % (n_blob, dev))
    else:
        print("   ⚠ GGG 不在样本里，跳过")

    # ── S6 内容干净（无替换字符；控制字符只允许 \n \r \t）──────────
    print("\nS6 **上报的**无键文本是否干净（无 U+FFFD；控制字符只允许 \\n \\r \\t）")
    # 为什么需要这条：I2 注入（不剥 `#US` 终止字节）**条数不变**（66→66），
    # 只比数量**拦不住**；而内容里会出现 U+FFFD（`'Player'` → `'Player\ufffd'`）。
    #
    # ⚠️ 判据的**检查对象**也踩过两次，都值得记：
    #   ① 第一版把"任何控制字符"当脏 ⇒ 真实数据报 165 条，
    #      但看原文是 `'\n'` / `',\n'` / `'...item.\nReserved...'` —— **正常多行文本**。
    #      ⇒ 只把 `\n \r \t` **之外**的控制字符当脏。
    #   ② 第二版改成只放行这三种后仍报 1 条：`BellumCivile` 的 `'\x1f'`。
    #      查证：它**没有字母** ⇒ `is_printable_text()` 本来就不收它
    #      ⇒ 它**不出现在上报结果里**，是"原始堆"里的东西。
    #      ⇒ 判据应该检查**上报的输出**（= `bare`），而不是原始堆。
    #        这样既拦得住 I2（`\ufffd` 串有字母、会进 bare），
    #        又不会被 `'\x1f'` 这类非文本噪声误伤。
    ALLOWED_CTRL = {"\n", "\r", "\t"}

    def is_dirty(s):
        if "\ufffd" in s:
            return True
        return any(ord(c) < 32 and c not in ALLOWED_CTRL for c in s)

    dirty_total = 0
    dirty_samples = []
    for mod, dll, r in rows:
        got, data, err = m.read_cli_streams(dll)
        if err:
            continue
        streams, _ = got
        # 只查**会上报的**那一类：无键文本（`classify` 之后）
        for heap, kind in ((m.extract_us_heap(data, streams), "us"),
                           (m.extract_blob_strings(data, streams), "blob")):
            _keyed, bare = m.classify(heap, kind)
            for s in bare:
                if is_dirty(s):
                    dirty_total += 1
                    if len(dirty_samples) < 5:
                        dirty_samples.append((mod, s[:60]))
    if dirty_total:
        fails.append("S6 上报的无键文本里有 %d 条含替换字符 —— 解码可能没剥干净"
                     % dirty_total)
        print("   [!!] 脏文本 %d 条" % dirty_total)
        for mod, s in dirty_samples:
            print("        %s: %r" % (mod, s))
    else:
        print("   [ok] 上报的无键文本全部干净（U+FFFD 0 条）"
              " —— 这条能拦住「不剥 #US 终止字节」那类 bug")
        print("        （`BellumCivile` 的 `'\\x1f'` 因**无字母**本就不上报，故不算脏）")

    # ── S7 数量级护栏 ─────────────────────────────────────────────
    print("\nS7 数量级护栏")
    tot = sum(r["hardcodedTotal"] for _m, _d, r in rows)
    if tot == 0:
        fails.append("S7 全部 DLL 合计 0 —— 解析肯定坏了")
        print("   [!!] 合计 0")
    else:
        print("   [ok] %d 份 DLL 合计无键文本 %d（>0）" % (len(rows), tot))

    print("\n" + "=" * 74)
    if fails:
        print("自测失败 %d 项：" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    print("自测全部通过：`#Blob`(UTF-8) 与 `#US`(UTF-16LE) **两个位置都读到了**，")
    print("且 `#US` 堆完整遍历、GGG 口径与知识库吻合。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
