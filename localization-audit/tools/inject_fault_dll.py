#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""**注入故障对照**：证明 `la_dll_strings` 的自测不是"恒真"。

## 为什么必须做

自测全绿有两种可能：(a) 判据真在拦 (b) **判据恒真**。
区分办法：**故意把解析改坏，断言自测必须变红**。

## 三次注入（都对应一个**真实踩过的坑**）

  I1 **`#Blob` 要求"整项可解"** —— 这正是第一版的 bug（得 0 条），
     复现它，断言 `#Blob` 会掉到 0。
  I2 **不剥 `#US` 的终止字节** —— ECMA-335 说末字节是标志，不剥会串进乱码。
  I3 **`#US` 只解 ASCII**（而非 UTF-16LE）—— 模拟"没意识到是 UTF-16"，
     断言 `#US` 无键文本会暴增（因为把 UTF-16 字节当 ASCII 解出噪声）。
"""
import importlib
import io
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
GAME = (os.environ.get("BANNERLORD_DIR")
        or r"G:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")
PROBE = "GovernorsGonnaGovern"


def fresh():
    if "la_dll_strings" in sys.modules:
        del sys.modules["la_dll_strings"]
    return importlib.import_module("la_dll_strings")


def base_measure(m):
    dll = m.find_dll(GAME, PROBE)
    return m.analyze(dll)


def inject_blob_whole_item():
    """I1：要求 blob **整项**按 UTF-8 解得出（第一版的 bug）。"""
    m = fresh()
    orig = m.extract_blob_strings

    def broken(data, streams):
        out = []
        if "#Blob" not in streams:
            return out
        off, size = streams["#Blob"]
        end, p = off + size, off
        while p < end:
            try:
                length, n = m.read_compressed_uint(data, p)
            except IndexError:
                break
            if length == 0:
                p += n
                continue
            p += n
            chunk = data[p:p + length]
            if len(chunk) < length:
                break
            p += length
            try:
                s = chunk.decode("utf-8")     # ← 整项必须可解（坏）
            except UnicodeDecodeError:
                continue
            if m.is_printable_text(s):
                out.append(s)
        return out

    m.extract_blob_strings = broken
    return m, "I1 blob 要求整项可解（第一版 bug）"


def inject_no_strip_terminator():
    """I2：不剥 `#US` 每项的终止字节。"""
    m = fresh()

    def broken(data, streams):
        out = []
        if "#US" not in streams:
            return out
        off, size = streams["#US"]
        end, p = off + size, off + 1
        while p < end:
            try:
                length, n = m.read_compressed_uint(data, p)
            except IndexError:
                break
            if length == 0:
                p += n
                continue
            p += n
            blob = data[p:p + length]
            if len(blob) < length:
                break
            p += length
            # ← 不剥末字节（坏）：文本里会混进终止标志
            try:
                out.append(blob.decode("utf-16-le", "replace"))
            except Exception:  # noqa: BLE001
                continue
        return out

    m.extract_us_heap = broken
    return m, "I2 不剥 #US 终止字节"


def inject_us_ascii():
    """I3：把 `#US` 当 ASCII 解（而非 UTF-16LE）。"""
    m = fresh()

    def broken(data, streams):
        out = []
        if "#US" not in streams:
            return out
        off, size = streams["#US"]
        raw = data[off:off + size]
        for mm in m._PRINTABLE_RUN.finditer(raw):
            try:
                out.append(mm.group(0).decode("ascii"))
            except UnicodeDecodeError:
                continue
        return out

    m.extract_us_heap = broken
    return m, "I3 #US 当 ASCII 解（非 UTF-16LE）"


def main():
    for n in ("stdout", "stderr"):
        try:
            getattr(sys, n).reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    b = base_measure(fresh())
    print("=== 基准 ===")
    print("  `#Blob` 无键 %d / `#US` 无键 %d / 合计 %d\n"
          % (b["blob"]["bare"], b["us"]["bare"], b["hardcodedTotal"]))

    results = []

    m, why = inject_blob_whole_item()
    r = base_measure(m)
    print("--- %s ---" % why)
    print("  `#Blob` 无键 %d（基准 %d）" % (r["blob"]["bare"], b["blob"]["bare"]))
    ok1 = r["blob"]["bare"] == 0 or r["blob"]["bare"] < b["blob"]["bare"] * 0.2
    print("  ⇒ 自测 S1 会捕获吗: %s" % ("**会**（blob 掉到 0 或极少）" if ok1 else "❌ 不会"))
    results.append(("I1 blob 要求整项可解", ok1))

    m, why = inject_no_strip_terminator()
    r = base_measure(m)
    print("\n--- %s ---" % why)
    print("  `#US` 无键 %d（基准 %d）" % (r["us"]["bare"], b["us"]["bare"]))
    # ⚠️ 第一次我只断言"**数量**变化" ⇒ **漏过了 I2**（数量都是 66）。
    #    实测原因：不剥终止字节时，70 条**内容全都不同**（尾部混进替换字符 U+FFFD），
    #    但"无键文本"的**条数不变**。
    #    ⇒ 判据必须看**内容**，不能只看数量。这正是"注入对照"的价值：
    #      它暴露了断言太弱，而不只是证明断言非恒真。
    sample_a = set(x for x in b["us"]["bareSample"])
    sample_b = set(x for x in r["us"]["bareSample"])
    changed = sample_a != sample_b
    # 更直接的判据：内容里出现替换字符（U+FFFD）或控制字符 = 没剥干净
    dirty = [s for s in r["us"]["bareSample"]
             if "\ufffd" in s or any(ord(c) < 32 for c in s)]
    ok2 = changed or bool(dirty)
    print("    样例内容变化: %s；含替换/控制字符的样例: %d 条"
          % ("是" if changed else "否", len(dirty)))
    print("  ⇒ 自测会捕获吗: %s" % ("**会**（内容变化 / 出现替换字符）" if ok2
                                    else "❌ 不会"))
    results.append(("I2 不剥 #US 终止字节", ok2))

    m, why = inject_us_ascii()
    r = base_measure(m)
    print("\n--- %s ---" % why)
    print("  `#US` 无键 %d（基准 %d）" % (r["us"]["bare"], b["us"]["bare"]))
    ok3 = r["us"]["bare"] != b["us"]["bare"]
    print("  ⇒ 自测会捕获吗: %s" % ("**会**（数量变化）" if ok3 else "❌ 不会"))
    results.append(("I3 #US 当 ASCII 解", ok3))

    print("\n" + "=" * 74)
    for name, ok in results:
        print("  %-34s %s" % (name, "✅ 被捕获（非恒真）" if ok else "❌ 漏过"))
    bad = [n for n, ok in results if not ok]
    if bad:
        print("\n失败：%d 项注入未被捕获 ⇒ 对应断言可能恒真" % len(bad))
        return 1
    print("\n三次注入**全部被捕获** ⇒ 自测判据确实在拦。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
