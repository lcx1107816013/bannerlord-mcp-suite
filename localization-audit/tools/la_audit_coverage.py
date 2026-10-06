#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""`la_audit_coverage` —— 汉化**真缺键审计**（知识库"覆盖审计配方"的工具化）。

## 它回答什么

知识库 `concepts/bannerlord-localization-audit.md:14` 的原话：

> 当玩家问"这个 mod 的菜单能不能汉化"时，答案不是感觉，而是**机械判定**

已装的 10 个汉化工具全是**施工**（插键 / 生成模板 / 翻译），**没有"判定"**。
本工具补的就是这一环：**算出差集，告诉你还有没有活可干**。

## 配方（工具化的就是它，逐条对应知识库）

    ① 页面所需键 = 模组 ModuleData 里的 `{=KEY}` 引用集合
    ② 可用译文   = **所有已装模组** `ModuleData/Languages/CNs/*.xml` 的 `<string id>` 并集
    ③ 真缺键     = ① − ②
    ④ 按游戏版本挑程序集 —— 本工具只做 XML 侧，DLL 侧见下

## ★ 四处口径修正（每一处都会让结论错一个数量级，全部实测）

这几条是**调试本工具时逐个撞出来的**，不写下来下一个人会重踩：

| # | 坑 | 错的后果 | 实测 |
|---|---|---|---|
| ① | **`{=*}` 空键标记**必须排除 | 误报（把它算成缺键） | 实测出现 **184 次**；正则 `[A-Za-z0-9+/]*` **匹配不到** `*` |
| ② | **`{=!}` 也是无键标记**必须排除 | 虚报缺键 | 实测 **1686 次**；三条证据定案：后跟开发者标识符 / 全库无 `<string id="!">` / **官方自己用 940 次** |
| ③ | **官方 / 社区必须分开算** | 把"游戏本体没装官方中文"算成"你的 mod 缺一万条翻译" | 混算 **2487** vs 分开 官方 193 / 社区 117 |
| ④ | **编码必须按 BOM 解** | 官方 CNs 全是 **UTF-16**，只按 UTF-8 扫 ⇒ 得出"官方译文 **0**" | 正确解码后官方译文是 **23776**（不是 0） |

④ 与本项目已有的教训**同源**（知识库：`.NET 程序集里 C# 字符串在 #US 堆，编码是 UTF-16LE，
只按 ASCII 正则扫会漏掉绝大部分`）—— **同一个坑在 XML 侧也存在**，而且有**三种**编码：

    实测 4027 个语言文件：utf-8 2444 / utf-8-bom 1358 / utf-16-be 192 / utf-16-le 33

## 已知边界（如实）

- **只做 XML 侧**，**不含 DLL 硬编码（第 1 类）**。第 1 类要靠 Cecil / `Bannerlord.LocalizationParser`。
  所以本工具的意思是："XML 侧还有没有活"，而不是"全部还有没有活"。
- **不解析 `{=KEY}` 之外的本地化通道**（如 `str_*` 引用、`@` 前缀）。
- **不做"有键有译文却不生效"（第 2 类）的判定** —— 知识库说那类机制**未坐实**，不能机械判定。
- 键的**可用性以"全局并集"为准**（语言文件是全局加载的）——
  这正是知识库强调的"逐 mod 找自己的包会得出错误结论"。

## 用法

    python la_audit_coverage.py                        # 全量审计（社区口径）
    python la_audit_coverage.py --module RBM           # 单模组
    python la_audit_coverage.py --scope all            # 含官方
    python la_audit_coverage.py --json                 # 机器可读
    python la_audit_coverage.py --locale CNt           # 换语言
"""
import argparse
import ast
import collections
import io
import json
import os
import re
import sys

DEFAULT_GAME = (r"G:\Program Files (x86)\Steam\steamapps\common"
                r"\Mount & Blade II Bannerlord")

# 官方模块（**大小写以磁盘为准** —— 本机是 `SandBox` 不是 `Sandbox`；
# 写错大小写会把官方误判成社区，实测污染了整份排名）
OFFICIAL = ("Native", "SandBoxCore", "SandBox", "CustomBattle", "StoryMode",
            "BirthAndDeath", "FastMode", "NavalDLC", "Multiplayer",
            "MultiplayerCoop")   # 最后一个为将来预留，不存在也无害

# `{=KEY}` / `{=*}` / `{=!}`。★ 用 `[^}]*` 而非 `[A-Za-z0-9+/]*`：
#   后者**匹配不到** `{=*}`（实测 184 次），会把空键标记当成"缺键"。
BRACE_RE = re.compile(r"\{=([^}]*)\}")
# `<string id="KEY" ...>`（在**解码后的文本**上匹配，故跨编码一致）
STRING_RE = re.compile(r'<string\s+id="([^"]+)"')

# ★ ②' 「无键标记」白名单 —— 它们**不是待翻译的键**
#
# 这是调试本工具时用**三条独立证据**定案的（`_diag/audit_bang_marker.py`）：
#
#   C1 `{=!}` 后跟的是**开发者标识符**（`MP` / `wanderer_equipment` / `Aserai`
#      / `{FIRSTNAME}` …），而不是人话 ⇒ 语义是"**原样用字面量，不做本地化**"。
#   C2 全库**没有一个** `<string id="!">` 的译文 ⇒ `!` **从来不是一个键**。
#   C3 **官方模块自己就大量使用**（Native 940 次、SandBox 248、SandBoxCore 246…）
#      ⇒ 它是**引擎约定**，不是任何 mod 的缺陷。
#
# 实测出现次数：`{=!}` **1686** 次、`{=*}` **184** 次。
# 若不排除，会**虚报缺键** —— 而本工具的全部价值就是这个数字可不可信。
_NO_KEY_MARKERS = {"*", "!"}


def _is_no_key_marker(k):
    """键位置是否为「无键标记」（不是待翻译的键）。"""
    return (not k) or (k in _NO_KEY_MARKERS)


# ══════════════════════════════════════════════════════════════════
# 编码：本审计最容易翻车的一步
# ══════════════════════════════════════════════════════════════════

def decode_smart(raw):
    """按 BOM 选编码解码，返回 (text, encoding_name)。

    ⚠️ **必须先剥 BOM 再解码**，且 UTF-16 要按 BOM 分 LE/BE。
       猜错字节序会得到乱码，而正则会**静默不命中** —— 这是最难发现的一类错。
       实测本机 4027 个语言文件里 **225 个是 UTF-16**（官方 CNs 尤其多）。
    """
    if raw.startswith(b"\xff\xfe\x00\x00"):
        return raw[4:].decode("utf-32-le", "replace"), "utf-32-le"
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", "replace"), "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", "replace"), "utf-16-be"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", "replace"), "utf-8-bom"
    return raw.decode("utf-8", "replace"), "utf-8"


def read_text(path):
    """读文件并按 BOM 解码。失败返回 (None, err)。"""
    try:
        with io.open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return None, None, "读取失败: %r" % (exc,)
    text, enc = decode_smart(raw)
    return text, enc, None


def walk_xml(root):
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith(".xml"):
                yield os.path.join(dirpath, fn)


# ══════════════════════════════════════════════════════════════════
# 两个集合
# ══════════════════════════════════════════════════════════════════

def collect_used_keys(module_dir):
    """模组 ModuleData 里 `{=KEY}` 引用的键（**排除** `{=*}` 空键标记）。

    返回 (keys:set, stats:dict)
    """
    keys = set()
    stats = {"files": 0, "braceRefs": 0, "emptyKeyRefs": 0,
             "encodings": collections.Counter(), "readErrors": 0}
    mdata = os.path.join(module_dir, "ModuleData")
    if not os.path.isdir(mdata):
        return keys, stats
    for f in walk_xml(mdata):
        # 语言文件自身不是"使用方"
        if os.sep + "Languages" + os.sep in f:
            continue
        text, enc, err = read_text(f)
        if err:
            stats["readErrors"] += 1
            continue
        stats["files"] += 1
        stats["encodings"][enc] += 1
        for m in BRACE_RE.finditer(text):
            stats["braceRefs"] += 1
            k = m.group(1)
            if _is_no_key_marker(k):
                # ★ ①② 「无键标记」不是缺键：
                #   `{=*}`（空）与 `{=!}`（后跟开发者标识符）都是"不做本地化"的约定，
                #   本机实测分别为 184 / 1686 次。误算会虚报缺键。
                stats["emptyKeyRefs"] += 1
                continue
            keys.add(k)
    return keys, stats


def collect_provided_keys(module_dir, locale="CNs"):
    """模组自带的该语言译文键集合。"""
    keys = set()
    stats = {"files": 0, "encodings": collections.Counter(), "readErrors": 0}
    ldir = os.path.join(module_dir, "ModuleData", "Languages", locale)
    if not os.path.isdir(ldir):
        return keys, stats
    for f in walk_xml(ldir):
        text, enc, err = read_text(f)
        if err:
            stats["readErrors"] += 1
            continue
        stats["files"] += 1
        stats["encodings"][enc] += 1
        for m in STRING_RE.finditer(text):
            keys.add(m.group(1))
    return keys, stats


# ══════════════════════════════════════════════════════════════════
# 审计
# ══════════════════════════════════════════════════════════════════

def list_modules(game_dir):
    modules_dir = os.path.join(game_dir, "Modules")
    if not os.path.isdir(modules_dir):
        return []
    out = []
    for name in sorted(os.listdir(modules_dir)):
        d = os.path.join(modules_dir, name)
        if os.path.isfile(os.path.join(d, "SubModule.xml")):
            out.append(name)
    return out


def audit(game_dir, locale="CNs", scope="community", only_module=None,
          sample=12):
    mods = list_modules(game_dir)
    if not mods:
        return {"ok": False, "error": "找不到任何模组（game_dir=%s）" % game_dir}

    # ★ ② 官方 / 社区分开：官方键缺中文是"游戏本体没装官方中文"，
    #    算进 mod 的账会得出"你的 mod 缺一万条"这种荒谬结论。
    official = [m for m in mods if m in OFFICIAL]
    community = [m for m in mods if m not in OFFICIAL]
    if only_module:
        targets = [m for m in mods if m == only_module]
        if not targets:
            return {"ok": False, "error": "找不到模组 %r" % only_module}
    elif scope == "official":
        targets = official
    elif scope == "all":
        targets = mods
    else:
        targets = community

    modules_dir = os.path.join(game_dir, "Modules")

    # 全局可用译文 = **所有已装模组**的并集（语言文件是全局加载的）
    provided_all = set()
    provided_by_mod = {}
    prov_enc = collections.Counter()
    for m in mods:
        p, st = collect_provided_keys(os.path.join(modules_dir, m), locale)
        provided_by_mod[m] = len(p)
        provided_all |= p
        prov_enc.update(st["encodings"])

    per_module = []
    used_all = set()
    empty_total = 0
    for m in targets:
        used, st = collect_used_keys(os.path.join(modules_dir, m))
        used_all |= used
        empty_total += st["emptyKeyRefs"]
        missing = used - provided_all
        per_module.append({
            "module": m,
            "used": len(used),
            "missing": len(missing),
            "missingSample": sorted(missing)[:sample],
            "ownTranslations": provided_by_mod.get(m, 0),
            "filesScanned": st["files"],
            "readErrors": st["readErrors"],
        })

    per_module.sort(key=lambda r: -r["missing"])
    missing_all = used_all - provided_all

    return {
        "ok": True,
        "gameDir": game_dir,
        "locale": locale,
        "scope": scope,
        "totals": {
            "modulesTotal": len(mods),
            "modulesOfficial": len(official),
            "modulesCommunity": len(community),
            "modulesAudited": len(targets),
            "usedKeys": len(used_all),
            "availableTranslations": len(provided_all),
            "missingKeys": len(missing_all),
            "emptyKeyRefsExcluded": empty_total,
        },
        "providedEncodings": dict(prov_enc),
        "missingSample": sorted(missing_all)[:sample],
        "perModule": per_module,
        "notes": [
            "只含 XML 侧（`{=KEY}`）；**不含 DLL 硬编码（第 1 类）**。",
            "可用译文取**全局并集** —— 语言文件是全局加载的，逐 mod 找自己的包会得出错误结论。",
            "无键标记已排除：`{=*}`（空）与 `{=!}`（后跟开发者标识符）共 %d 次 —— 它们不是待翻译的键。"
            % empty_total,
            "官方/社区已分开：官方键缺中文属'游戏本体'，不计入社区待办。",
        ],
    }


def fmt(report):
    if not report.get("ok"):
        return "审计失败: %s" % report.get("error")
    t = report["totals"]
    L = []
    L.append("=" * 74)
    L.append("汉化真缺键审计 · locale=%s scope=%s" % (report["locale"], report["scope"]))
    L.append("=" * 74)
    L.append("模组 %d 个（官方 %d / 社区 %d）；本次审计 %d 个"
             % (t["modulesTotal"], t["modulesOfficial"], t["modulesCommunity"],
                t["modulesAudited"]))
    L.append("")
    L.append("被引用键     : %d" % t["usedKeys"])
    L.append("可用译文(全局): %d" % t["availableTranslations"])
    L.append("★ 真缺键     : %d" % t["missingKeys"])
    L.append("（已排除 `{=*}` 空键标记 %d 次 —— 它不是缺键）" % t["emptyKeyRefsExcluded"])
    L.append("")
    if t["missingKeys"] == 0:
        L.append("⇒ **没有真缺键** ⇒ 补词条收益为 0（知识库的判据：这一类的活不用干）")
    else:
        L.append("⇒ 这 %d 条才值得动笔。" % t["missingKeys"])
    L.append("")
    L.append("── 逐模组（按缺键降序）──")
    L.append("%-38s %8s %8s %10s" % ("模组", "引用键", "缺键", "自带译文"))
    for r in report["perModule"][:20]:
        if r["used"] == 0:
            continue
        L.append("%-38s %8d %8d %10d"
                 % (r["module"], r["used"], r["missing"], r["ownTranslations"]))
    L.append("")
    L.append("缺键样例: %s" % ", ".join(report["missingSample"][:10]))
    L.append("")
    L.append("── 边界（如实）──")
    for n in report["notes"]:
        L.append("  · %s" % n)
    return "\n".join(L)


def main(argv=None):
    for _n in ("stdin", "stdout", "stderr"):
        try:
            getattr(sys, _n).reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    ap = argparse.ArgumentParser(description="汉化真缺键审计")
    ap.add_argument("--game-dir", default=os.environ.get("BANNERLORD_DIR") or DEFAULT_GAME)
    ap.add_argument("--locale", default="CNs")
    ap.add_argument("--scope", default="community",
                    choices=["community", "official", "all"])
    ap.add_argument("--module", default=None, help="只审计这一个模组")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    rep = audit(a.game_dir, locale=a.locale, scope=a.scope, only_module=a.module)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print(fmt(rep))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
