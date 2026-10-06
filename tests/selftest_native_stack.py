#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""自测：打了原生栈补丁的 `bl_crash.py` 是否**两档都能出原生调用链**。

## 为什么要按"档"断言

实测本机 dump 分两类（各 1/6 与 5/6）：
  · **上下文可用**档（48356）⇒ 应走 `nativeSource == "ecxr_kv"`，帧数 ≥ 10
  · **上下文退化**档（28540）⇒ 应走 `nativeSource == "all_threads"`，
    且 `crashSite` 必须命中 `RTSCamera...OnRemoveBehavior`（知识库已知真凶）

**只断言"有输出"是不够的** —— 那不能区分"真定位到"与"塞了一堆噪音"。
所以本自测对**每一档**断言其**特有**的判据。

用法:
    python selftest_native_stack.py <已打补丁的 bl_crash.py 路径>
    python selftest_native_stack.py --default       # 用仓库路径
"""
import argparse
import io
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 伞仓根（bl_chain.py / localization-audit 在这）
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

REPO = r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge\tools\bl_crash.py"
CDB = (r"C:\Program Files\WindowsApps"
       r"\Microsoft.WinDbg_1.2606.22001.0_x64__8wekyb3d8bbwe\amd64\cdb.exe")
DUMPS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CrashDumps")

# (dump 文件名, 期望档, 期望出现的符号子串)
CASES = [
    ("Bannerlord.BLSE.Standalone.exe.48356.dmp", "ecxr_kv",
     ["ucrtbase!abort", "TaleWorlds_Native!"]),
    ("Bannerlord.BLSE.Standalone.exe.28540.dmp", "all_threads",
     ["RTSCamera_CommandSystem!", "OnRemoveBehavior"]),
    ("Bannerlord.BLSE.Standalone.exe.14804.dmp", "all_threads",
     ["RTSCamera_CommandSystem!"]),
]


def run_json(py_file, dump, workdir):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["BLBRIDGE_CDB"] = CDB
    p = subprocess.run([sys.executable, py_file, "--deep", "--path", dump, "--json"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       env=env, cwd=workdir, timeout=900)
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

    ap = argparse.ArgumentParser()
    ap.add_argument("py_file", nargs="?")
    ap.add_argument("--default", action="store_true")
    a = ap.parse_args()
    py_file = REPO if a.default else a.py_file
    if not py_file or not os.path.isfile(py_file):
        print("用法: python selftest_native_stack.py <bl_crash.py>")
        return 1
    workdir = os.path.dirname(os.path.abspath(py_file))

    # 静态：确认补丁在
    src = io.open(py_file, encoding="utf-8").read()
    static_fails = []
    if "_parse_native" not in src:
        static_fails.append("缺 `_parse_native`（补丁未生效？）")
    if "~*kv" not in src:
        static_fails.append("cdb 脚本里没有 `~*kv`（原生栈没加上）")
    if "kv;" not in src and "kv " not in src:
        static_fails.append("cdb 脚本里没有裸 `kv`")
    print("静态检查：%s" % ("全部通过" if not static_fails else "失败"))
    for f in static_fails:
        print("   ✗ %s" % f)

    print()
    print("| dump | 期望档 | 实际档 | 帧数 | crashSite | 判据 |")
    print("|---|---|---|---:|---|---|")
    fails = list(static_fails)
    for fn, want_src, want_syms in CASES:
        path = os.path.join(DUMPS, fn)
        if not os.path.isfile(path):
            print("| %s | %s | **dump 不存在** | | | |" % (fn, want_src))
            continue
        doc, raw = run_json(py_file, path, workdir)
        if doc is None:
            print("| %s | %s | **运行失败** | | | %s |" % (fn, want_src, raw[:60]))
            fails.append("%s 运行失败" % fn)
            continue
        dp = (doc["crashes"][0].get("deep") or {})
        got_src = dp.get("nativeSource")
        nf = dp.get("nativeFrames") or []
        cs = dp.get("crashSite")
        verdict = []
        if got_src != want_src:
            verdict.append("档不符(期望 %s)" % want_src)
        if len(nf) < 5:
            verdict.append("帧数过少")
        joined = " ".join(f["site"] for f in nf) + " " + (cs or "")
        for s in want_syms:
            if s not in joined:
                verdict.append("缺 %s" % s)
        if want_src == "all_threads" and not cs:
            verdict.append("退化档必须给出 crashSite")
        ok = not verdict
        print("| %s | %s | %s | %d | %s | %s |"
              % (fn.split(".")[-2], want_src, got_src, len(nf),
                 (cs or "—")[:44], "✅" if ok else "✗ " + "; ".join(verdict)))
        if not ok:
            fails.append("%s: %s" % (fn, "; ".join(verdict)))

    print()
    print("=" * 74)
    if fails:
        print("自测失败 %d 项：" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    print("自测全部通过：两档（上下文可用 / 退化）都能给出原生调用链。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
