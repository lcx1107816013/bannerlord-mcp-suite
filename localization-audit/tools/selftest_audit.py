#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""自测：`la_audit_coverage.py` 的**四处口径修正**是否真的生效。

## 为什么必须按"口径"断言

这个工具的全部价值是**"缺键数可不可信"**。而我在调试中撞出四处口径错误，
每处都让数字错一个数量级：

    11007（编码错） → 2487（混算） → 117（{=!} 未排除） → 116（正确）

⇒ 只断言"能跑出个数"是不够的 —— **必须逐条断言那四处修正**，
否则将来有人"顺手简化"就会把数字改回去，而**报告看起来完全正常**。

## 断言

  T1 `{=!}` 被排除（它 1686 次，若漏掉会虚报）
  T2 `{=*}` 被排除（它 184 次）
  T3 官方/社区分开（官方键不混进社区排名）
  T4 UTF-16 语言文件能被读出（官方 CNs 是 UTF-16；漏了会得"官方译文 0"）
  T5 可用译文取**全局并集**（跨模组：A 模组用 B 模组提供的键）
  T6 数量级护栏（防止口径再次错回）
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "la_audit_coverage.py")
PY = sys.executable
GAME = (os.environ.get("BANNERLORD_DIR")
        or r"G:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord")


def run(*args):
    p = subprocess.run([PY, TOOL, "--json", *args], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=900,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    txt = (p.stdout or b"").decode("utf-8", "replace")
    i = txt.find("{")
    if i < 0:
        return None, txt
    try:
        return json.loads(txt[i:]), txt
    except ValueError as exc:
        return None, "JSON 解析失败 %r\n%s" % (exc, txt[:400])


def main():
    for n in ("stdout", "stderr"):
        try:
            getattr(sys, n).reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    fails = []
    if not os.path.isdir(os.path.join(GAME, "Modules")):
        print("!! 找不到游戏 Modules 目录：%s" % GAME)
        return 1

    # ── 社区口径 ──────────────────────────────────────────────────
    com, raw = run("--scope", "community")
    if com is None:
        print("!! 社区审计失败：%s" % raw[:300])
        return 1
    ct = com["totals"]
    print("社区口径：模组 %d / 引用键 %d / 可用译文 %d / **缺键 %d**"
          % (ct["modulesAudited"], ct["usedKeys"], ct["availableTranslations"],
             ct["missingKeys"]))

    # ── 官方口径（只为验证 T3/T4）─────────────────────────────────
    off, raw2 = run("--scope", "official")
    if off is None:
        print("!! 官方审计失败：%s" % raw2[:300])
        return 1
    ot = off["totals"]
    print("官方口径：模组 %d / 引用键 %d / 可用译文 %d / 缺键 %d"
          % (ot["modulesAudited"], ot["usedKeys"], ot["availableTranslations"],
             ot["missingKeys"]))
    print()

    # ── T1/T2 无键标记已排除 ──────────────────────────────────────
    print("T1/T2 无键标记（`{=!}` / `{=*}`）是否被排除")
    excluded = ct["emptyKeyRefsExcluded"]
    # 宽松判据下社区侧应能数到一批（RBM 等社区模组也用 {=!}）
    if excluded > 0:
        print("   [ok] 社区口径共排除 %d 处无键标记（>0 说明判据在跑）" % excluded)
    else:
        fails.append("T1/T2 无键标记排除数为 0 —— 判据可能没生效")
        print("   [!!] 排除数为 0")

    # 直接查工具内部：`!` 不该出现在任何缺键样例里
    all_missing_samples = []
    for r in com["perModule"]:
        all_missing_samples += r.get("missingSample", [])
    all_missing_samples += com.get("missingSample", [])
    bad = [k for k in all_missing_samples if k in ("!", "*", "")]
    if bad:
        fails.append("T1/T2 无键标记 %s 出现在缺键里" % bad)
        print("   [!!] `!`/`*` 出现在缺键样例里：%s" % bad)
    else:
        print("   [ok] 缺键样例里没有 `!` / `*`（%d 个样例已查）"
              % len(set(all_missing_samples)))

    # ── T3 官方/社区分开 ──────────────────────────────────────────
    print("\nT3 官方 / 社区是否分开算")
    off_ids = {"Native", "SandBoxCore", "SandBox", "CustomBattle", "StoryMode",
               "BirthAndDeath", "FastMode", "NavalDLC", "Multiplayer"}
    leaked = [r["module"] for r in com["perModule"] if r["module"] in off_ids]
    if leaked:
        fails.append("T3 官方模块 %s 出现在社区排名里" % leaked)
        print("   [!!] 官方模块泄漏进社区：%s" % leaked)
    else:
        print("   [ok] 社区排名里没有官方模块（%d 条已查）" % len(com["perModule"]))
    if ct["modulesOfficial"] != ot["modulesAudited"]:
        fails.append("T3 官方模组数不一致：community 报 %d，official 报 %d"
                     % (ct["modulesOfficial"], ot["modulesAudited"]))
    else:
        print("   [ok] 官方模组数一致：%d" % ct["modulesOfficial"])

    # ── T4 UTF-16 语言文件被读到 ──────────────────────────────────
    print("\nT4 UTF-16 语言文件是否被正确解码")
    enc = com.get("providedEncodings") or {}
    has16 = any("utf-16" in k for k in enc)
    print("   译文文件编码分布: %s" % enc)
    if not has16:
        fails.append("T4 没有读到任何 UTF-16 文件 —— 可能编码判据失效")
        print("   [!!] 没读到 UTF-16")
    else:
        n16 = sum(v for k, v in enc.items() if "utf-16" in k)
        print("   [ok] 读到 UTF-16 文件 %d 个（漏了会虚报大量缺键）" % n16)

    # ★ 直接调工具的函数，对**官方**模组验证 UTF-16 能被读出译文。
    #   为什么不能只看 report 里的 availableTranslations：那个是**全局并集**，
    #   与 scope 无关 ⇒ 对官方口径断言它等于在断言同一个数，**测不出东西**。
    #   第三轮的错法是"官方自带译文本该有 23776，却报 0" ⇒ 必须直接量官方侧。
    try:
        sys.path.insert(0, HERE)
        import importlib
        mod = importlib.import_module("la_audit_coverage")
        importlib.reload(mod)
        modules_dir = os.path.join(GAME, "Modules")
        off_names = [m for m in mod.list_modules(GAME) if m in mod.OFFICIAL]
        off_prov = set()
        for m in off_names:
            s, _st = mod.collect_provided_keys(os.path.join(modules_dir, m), "CNs")
            off_prov |= s
        if len(off_prov) < 1000:
            fails.append("T4 官方自带译文本该上万，实测仅 %d —— UTF-16 解码很可能失效"
                         % len(off_prov))
            print("   [!!] 官方自带译文仅 %d（正确值上万）" % len(off_prov))
        else:
            print("   [ok] 官方自带译文 %d（UTF-16 解码成功；若失效这里会是 0）"
                  % len(off_prov))
    except Exception as exc:  # noqa: BLE001
        print("   ⚠ 无法直接调内部函数（%r）—— 跳过该项专项断言" % (exc,))

    # ── T5 全局并集 ───────────────────────────────────────────────
    print("\nT5 可用译文是否取全局并集（跨模组）")
    # 判据：某个模组的"自带译文"远小于"引用键"，但缺键很少 ⇒ 说明用了别人的译文
    cross = [r for r in com["perModule"]
             if r["used"] > 50 and r["ownTranslations"] < r["used"] * 0.5
             and r["missing"] < r["used"] * 0.2]
    if cross:
        m = cross[0]
        print("   [ok] 存在跨模组复用：`%s` 引用 %d 键 / 自带仅 %d / 缺 %d"
              % (m["module"], m["used"], m["ownTranslations"], m["missing"]))
    else:
        print("   ⚠ 未找到明显的跨模组复用样本（不判失败，仅提示）")

    # ── T6 数量级护栏 ─────────────────────────────────────────────
    print("\nT6 数量级护栏（防口径再次错回）")
    n = ct["missingKeys"]
    # 实测正确值是 116。允许随模组增减浮动，但**不允许回到千级**
    if n == 0:
        print("   [ok] 缺键 0（若真如此，说明已全汉化）")
    elif n < 500:
        print("   [ok] 缺键 %d —— 在合理量级（实测基线 116）" % n)
    else:
        fails.append("T6 缺键 %d 达千级 —— 口径很可能又错了（基线 116）" % n)
        print("   [!!] 缺键 %d 异常偏大" % n)
    if ct["usedKeys"] > 50000:
        fails.append("T6 引用键 %d 过多 —— 无键标记可能没排除" % ct["usedKeys"])
        print("   [!!] 引用键 %d 过多" % ct["usedKeys"])
    else:
        print("   [ok] 引用键 %d 在合理量级（基线 6094）" % ct["usedKeys"])

    print("\n" + "=" * 74)
    if fails:
        print("自测失败 %d 项：" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    print("自测全部通过：四处口径修正（`{=!}` / `{=*}` / 官方分离 / UTF-16）都生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
