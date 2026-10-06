# -*- coding: utf-8 -*-
r"""把 `bl_chain.py` 里写死的本机绝对路径改成 **环境变量 + 兜底默认**。

## 为什么必须做（不是洁癖）

伞仓要能被别人（或另一台机器）clone 后直接跑。而现在的 `bl_chain.py` 写死了：

    PY312        = r"D:\Program Files\Python312\python.exe"
    BUN          = r"C:\Users\LCGX\AppData\Local\Microsoft\WinGet\...\bun.exe"
    GAME_DIR     = r"G:\Program Files (x86)\Steam\...\Mount & Blade II Bannerlord"
    BLBRIDGE_DIR = r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge"
    TOKENIZER_PATH = r"E:\Document\spark-heretic\model\tokenizer.json"

⇒ 别人 clone 后**一个上游都起不来**，而这跟"我们代码对不对"无关 —— 是**可配置性**问题。

## 改法（每条都是「环境变量优先，本机默认兜底」）

| 常量 | 环境变量 | 兜底 |
|---|---|---|
| `PY312` | `DSH_CHAIN_PYTHON` | `sys.executable`（跑本脚本的解释器） |
| `BUN` | `DSH_CHAIN_BUN` | 本机 WinGet 路径（找不到就报错，不静默） |
| `GAME_DIR` | `BANNERLORD_DIR` | 本机 Steam 路径 |
| `BLBRIDGE_DIR` | `DSH_CHAIN_BLBRIDGE` | 本机 CodeBuddy 路径 |
| `BANNERLORDSAGE_DIR` | `DSH_CHAIN_SAGE` | 本机 `F:\Program Files\BannerlordSage` |
| `BANNERLORDHELPER_DIR` | `DSH_CHAIN_HELPER` | 本机 `F:\Program Files\Bannerlord.Helper` |
| `TOKENIZER_PATH` | `DSH_CHAIN_TOKENIZER` | 空（没有就用字节/3.80 估算，**不报错**） |

★ 关键设计：**`sys.executable` 作 python 兜底** —— 这最自然：
用哪个解释器跑 `bl_chain.py`，就用它去起子进程。

⚠️ 幂等：重复跑不会重复改（检测标记注释）。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 伞仓根
TARGET = os.path.join(ROOT, "bl_chain.py")

MARK = "# ── 路径可配置化（伞仓）"

NEW_BLOCK = '''# ── 路径可配置化（伞仓）────────────────────────────────────────────────────
#
# ★ 为什么有这个块：本文件原来写死了本机绝对路径，别人 clone 后**一个上游都起不来**。
#   这不是"代码对不对"的问题，是**可配置性**问题 ⇒ 全部改成
#   「**环境变量优先，本机默认兜底**」。
#
# 设计取舍：`PY312` 的兜底用 `sys.executable`（跑本脚本的那个解释器）——
# 这最自然：谁跑本桥就用谁去起子进程，不假设 Python 装在哪。
#
# 设不了的环境变量**不静默**：`BUN` 找不到时会由上游启动失败如实报出
# （本桥的 `chain_status` 会点名是哪个上游 `connected: false`）。
_ENV = os.environ.get

PY312 = _ENV("DSH_CHAIN_PYTHON") or sys.executable

BUN = _ENV("DSH_CHAIN_BUN") or (
    r"C:\\Users\\LCGX\\AppData\\Local\\Microsoft\\WinGet\\Packages"
    r"\\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\\bun-windows-x64\\bun.exe")

GAME_DIR = _ENV("BANNERLORD_DIR") or (
    r"G:\\Program Files (x86)\\Steam\\steamapps\\common\\Mount & Blade II Bannerlord")

BLBRIDGE_DIR = _ENV("DSH_CHAIN_BLBRIDGE") or (
    r"C:\\Users\\LCGX\\CodeBuddy\\20260923171333\\BlBridge")

BANNERLORDSAGE_DIR = _ENV("DSH_CHAIN_SAGE") or r"F:\\Program Files\\BannerlordSage"

BANNERLORDHELPER_DIR = _ENV("DSH_CHAIN_HELPER") or r"F:\\Program Files\\Bannerlord.Helper"

# 真实 tokenizer（可选）：设了就用它精确计数；没设就退到 bytes/3.80 估算。
# ⚠️ 这是**度量**用的，不是功能依赖 ⇒ 缺了**绝不能报错**。
TOKENIZER_PATH = _ENV("DSH_CHAIN_TOKENIZER") or ""
# ──────────────────────────────────────────────────────────────────────────
'''


def main():
    t = io.open(TARGET, encoding="utf-8").read()
    if MARK in t:
        print("  已改过（幂等跳过）")
        return 0

    # 1) 删掉旧的 5 个常量定义行
    olds = [
        r'^PY312\s*=.*$',
        r'^BUN\s*=.*(?:\n\s+r?["\'].*)*$',
        r'^GAME_DIR\s*=.*$',
        r'^BLBRIDGE_DIR\s*=.*$',
        r'^TOKENIZER_PATH\s*=.*$',
    ]
    removed = 0
    for pat in olds:
        new_t, n = re.subn(pat, "", t, count=1, flags=re.M)
        if n:
            removed += 1
            t = new_t
    print("  删除旧常量定义: %d/5" % removed)

    # 2) 在 CHAIN_DIR 之前插入新块
    anchor = "CHAIN_DIR = os.path.dirname(os.path.abspath(__file__))"
    if anchor not in t:
        print("  ✗ 找不到 CHAIN_DIR 锚点，中止")
        return 1
    t = t.replace(anchor, NEW_BLOCK + "\n" + anchor, 1)

    # 3) SERVERS 里两处硬编码目录 → 新常量
    #    ⚠️ 顺序很重要：**先换长的、具体的**，再换短的泛化串。
    #    否则 `r"F:\Program Files\BannerlordSage"` 会先把
    #    `...\BannerlordSage\src\entrypoints\...` 的前缀吃掉 ——
    #    本脚本第一版就栽在这：它把**刚插进 NEW_BLOCK 的默认值**
    #    也替换成了自己，得到 `X = _ENV(...) or X`（NameError）。
    t = t.replace(
        r'"F:\Program Files\BannerlordSage\src\entrypoints\bannerlord-full-stdio.ts"',
        'os.path.join(BANNERLORDSAGE_DIR, "src", "entrypoints", "bannerlord-full-stdio.ts")')
    t = t.replace(r'r"F:\Program Files\Bannerlord.Helper\mcp\server.ts"',
                  'os.path.join(BANNERLORDHELPER_DIR, "mcp", "server.ts")')
    # ★ 只替换 **SERVERS 段**里的裸目录字面量；NEW_BLOCK 里的默认值必须原样保留
    t = t.replace(r'        "cwd": r"F:\Program Files\BannerlordSage",',
                  '        "cwd": BANNERLORDSAGE_DIR,')
    t = t.replace(r'        "cwd": r"F:\Program Files\Bannerlord.Helper",',
                  '        "cwd": BANNERLORDHELPER_DIR,')

    # 4) 清理删行留下的连续空行
    t = re.sub(r"\n{3,}", "\n\n", t)

    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(t)
    print("  已写入")

    # 校验
    t2 = io.open(TARGET, encoding="utf-8").read()
    print()
    print("=== 校验 ===")
    for probe, want in (("DSH_CHAIN_PYTHON", True), ("sys.executable", True),
                        ("BANNERLORDSAGE_DIR", True), ("BANNERLORDHELPER_DIR", True),
                        (r"F:\Program Files", False)):
        present = probe in t2
        ok = (present == want)
        print("  %-22s 出现=%-6s 期望=%-6s %s" % (probe, present, want, "OK" if ok else "★ 不符"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
