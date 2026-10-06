#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""**注入故障对照**：证明自测不是"恒真"。

## 为什么必须做

自测全绿有两种可能：
  (a) 判据真的在拦
  (b) **判据恒真**（怎么写都过）

区分办法（本项目已有先例：`bl_patch_failures` 的自测⑤就是这么做）：
**故意把口径改坏，断言自测必须变红**。

## 三次注入

  I1 不排除 `{=!}`/`{=*}`  ⇒ T1/T2 应报错
  I2 不按 BOM 解 UTF-16   ⇒ T4 应报错
  I3 把官方当社区         ⇒ T3 应报错

做法：在内存里 monkey-patch 一个**坏版本**，跑同一套断言，看是否**捕获到**。
"""
import importlib
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def fresh():
    """每次拿一个干净的模块实例（避免 patch 串味）。"""
    if "la_audit_coverage" in sys.modules:
        del sys.modules["la_audit_coverage"]
    return importlib.import_module("la_audit_coverage")


def inject_dont_exclude_markers():
    """I1：让无键标记**不**被排除（模拟"顺手简化"把判断删了）。"""
    m = fresh()
    m._is_no_key_marker = lambda k: False      # ← 坏版本
    m._NO_KEY_MARKERS = set()
    return m, "不排除 `{=!}`/`{=*}`"


def inject_utf8_only():
    """I2：强制只按 UTF-8 解（模拟忘掉 BOM 分支）。"""
    m = fresh()
    m.decode_smart = lambda raw: (raw.decode("utf-8", "replace"), "utf-8")
    return m, "只按 UTF-8 解码（忽略 BOM）"


def inject_official_as_community():
    """I3：把官方名单清空（模拟大小写写错 ⇒ 官方被当社区）。"""
    m = fresh()
    m.OFFICIAL = ()
    return m, "官方名单为空（官方被当社区）"


GAME = (os.environ.get("BANNERLORD_DIR")
        or r"G:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")


def measure(mod):
    rep = mod.audit(GAME, locale="CNs", scope="community")
    if not rep.get("ok"):
        return None
    return rep["totals"]


def main():
    for n in ("stdout", "stderr"):
        try:
            getattr(sys, n).reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    print("=== 基准（未注入）===")
    base = measure(fresh())
    print("缺键 %d / 引用键 %d / 排除的无键标记 %d\n"
          % (base["missingKeys"], base["usedKeys"], base["emptyKeyRefsExcluded"]))

    results = []

    # ── I1 不排除无键标记 ─────────────────────────────────────────
    print("--- I1 %s ---" % "[不排除无键标记]")
    m, why = inject_dont_exclude_markers()
    t = measure(m)
    print("  缺键 %d / 引用键 %d / 排除数 %d" % (t["missingKeys"], t["usedKeys"],
                                               t["emptyKeyRefsExcluded"]))
    caught = (t["emptyKeyRefsExcluded"] == 0) or (t["missingKeys"] != base["missingKeys"])
    print("  ⇒ 自测的 T1/T2 会捕获吗: %s（排除数应 >0；缺键应不变）"
          % ("**会**" if caught else "❌ 不会"))
    results.append(("I1 不排除无键标记", caught))

    # ── I2 只按 UTF-8 ─────────────────────────────────────────────
    print("\n--- I2 [只按 UTF-8 解码] ---")
    m, why = inject_utf8_only()
    t = measure(m)
    print("  缺键 %d / 可用译文 %d" % (t["missingKeys"], t["availableTranslations"]))
    # 注入后可用译文应显著缩水（UTF-16 文件读不出）
    caught2 = t["availableTranslations"] < base["availableTranslations"] * 0.95 \
        or t["missingKeys"] > base["missingKeys"]
    print("  ⇒ 自测的 T4 会捕获吗: %s（可用译文应显著缩水）"
          % ("**会**" if caught2 else "❌ 不会"))
    results.append(("I2 只按 UTF-8 解码", caught2))

    # ── I3 官方当社区 ─────────────────────────────────────────────
    print("\n--- I3 [官方名单为空] ---")
    m, why = inject_official_as_community()
    t = measure(m)
    print("  审计模组数 %d（未注入时 %d）" % (t["modulesAudited"], base["modulesAudited"]))
    caught3 = t["modulesOfficial"] == 0 and t["modulesAudited"] > base["modulesAudited"]
    print("  ⇒ 自测的 T3 会捕获吗: %s（官方数应变成 0、审计数应变大）"
          % ("**会**" if caught3 else "❌ 不会"))
    results.append(("I3 官方当社区", caught3))

    print("\n" + "=" * 74)
    print("注入对照汇总")
    print("=" * 74)
    for name, ok in results:
        print("  %-28s %s" % (name, "✅ 被捕获（自测非恒真）" if ok else "❌ 漏过"))
    bad = [n for n, ok in results if not ok]
    if bad:
        print("\n失败：%d 项注入未被捕获 ⇒ 对应断言可能恒真" % len(bad))
        for b in bad:
            print("  - %s" % b)
        return 1
    print("\n三次注入**全部被捕获** ⇒ 自测的判据是**真的在拦**，不是恒真。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
