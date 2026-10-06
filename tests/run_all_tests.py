#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""一键跑完**全部**验证 —— 任何一项失败就以非零码退出。

为什么需要：本项目的结论全是"实测"，那就必须能**一条命令复现全部实测**，
否则"实测"会随代码漂移而变成"曾经实测"。这个脚本是那些结论的**守门人**。

跑法：
    python run_all_tests.py            # 全部
    python run_all_tests.py --fast     # 跳过耗时的（只跑纯静态/快速项）
"""
import argparse
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 伞仓根（bl_chain.py / localization-audit 在这）
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

PROBE = os.path.join(ROOT, "probe")
PY = r"D:\Program Files\Python312\python.exe"
NODE = r"C:\Program Files\nodejs\node.exe"


def run(label, cmd, cwd, timeout=900):
    t0 = time.time()
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                           timeout=timeout)
        out = (p.stdout or b"").decode("utf-8", "replace")
        err = (p.stderr or b"").decode("utf-8", "replace")
        ok = p.returncode == 0
        dt = time.time() - t0
        print("%s %-42s (%5.1fs)" % ("[PASS]" if ok else "[FAIL]", label, dt))
        if not ok:
            tail = (out + "\n" + err).strip().splitlines()[-25:]
            for line in tail:
                print("        | %s" % line)
        return ok
    except subprocess.TimeoutExpired:
        print("[FAIL] %-42s 超时（%ss）" % (label, timeout))
        return False
    except Exception as exc:  # noqa: BLE001
        print("[FAIL] %-42s 启动失败: %r" % (label, exc))
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="只跑快速项")
    a = ap.parse_args()

    results = []

    print("=" * 74)
    print("A. 三个上游的工具面实测（口径：compact JSON + 真实 tokenizer）")
    print("=" * 74)
    results.append(("上游工具面实测", run(
        "measure_any.py（三个服务器）", [PY, "measure_any.py"], PROBE)))

    print()
    print("=" * 74)
    print("B. 决定性实验：隐藏的工具还能不能调")
    print("=" * 74)
    results.append(("隐藏工具可调用性", run(
        "test_hidden_call.py", [PY, "test_hidden_call.py"], PROBE)))

    print()
    print("=" * 74)
    print("C. 分层桥：无损 / 完整 / 分层 / 检索 / 分组")
    print("=" * 74)
    results.append(("桥自测（8 段）", run(
        "bl_chain.py --selftest", [PY, os.path.join(ROOT, "bl_chain.py"), "--selftest"], HERE)))
    results.append(("slim 行为契约深比对", run(
        "slim_contract_test.py", [PY, "slim_contract_test.py"], HERE)))
    results.append(("上游适配性 T1-T6", run(
        "adapt_test.py", [PY, "adapt_test.py"], HERE)))
    results.append(("端到端 MCP 协议", run(
        "e2e_test.py", [PY, "e2e_test.py"], HERE)))
    results.append(("交叉校验（桥 vs 探针）", run(
        "crosscheck_test.py", [PY, "crosscheck_test.py"], HERE)))

    print()
    print("=" * 74)
    print("D. 官方 MCP SDK schema 合规（抓线 -> zod 校验）")
    print("=" * 74)
    if os.path.isfile(NODE):
        results.append(("协议线抓取", run(
            "capture_wire.py", [PY, "capture_wire.py"], HERE)))
        results.append(("官方 SDK schema 校验", run(
            "verify_schema.mjs", [NODE, "verify_schema.mjs"], HERE)))
    else:
        print("[SKIP] node 不在 %s" % NODE)

    if not a.fast:
        print()
        print("=" * 74)
        print("E. 真实 token 数（Spark2.5 tokenizer）")
        print("=" * 74)
        results.append(("真实 token 测量", run(
            "real_tokens.py", [PY, "real_tokens.py"], HERE)))

        print()
        print("=" * 74)
        print("F. 原生调用链（bl_crash 补丁）")
        print("=" * 74)
        # ★ 可配置：bl_crash.py 住在**另一个仓库**（BlBridge，第三个 MCP 的宿主）。
        #   原来写死本机路径 ⇒ 换台机器就 SKIP。改成环境变量优先。
        blcrash = os.environ.get("DSH_CHAIN_BLCRASH") or os.path.join(
            os.environ.get("DSH_CHAIN_BLBRIDGE",
                           r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge"),
            "tools", "bl_crash.py")
        if os.path.isfile(blcrash):
            results.append(("bl_crash 原生栈自测", run(
                "selftest_native_stack.py --default",
                [PY, "selftest_native_stack.py", "--default"], HERE)))
        else:
            print("[SKIP] 找不到 %s（设 DSH_CHAIN_BLCRASH 或 DSH_CHAIN_BLBRIDGE 可指定）" % blcrash)

        print()
        print("=" * 74)
        print("G. 汉化真缺键审计（口径自测 + 注入对照）")
        print("=" * 74)
        # ★ 自测住在**第 4 个 MCP 自己的目录**里（localization-audit/tools/），
        #   不在 tests/ ⇒ 必须显式指过去，否则一律 ModuleNotFoundError。
        AUDIT = os.path.join(ROOT, "localization-audit", "tools")
        results.append(("审计口径自测 T1-T6", run(
            "selftest_audit.py", [PY, "selftest_audit.py"], AUDIT)))
        results.append(("审计注入对照（证明非恒真）", run(
            "inject_fault_audit.py", [PY, "inject_fault_audit.py"], AUDIT)))

        print()
        print("=" * 74)
        print("G2. DLL 硬编码抽取（第 1 类，两个堆）")
        print("=" * 74)
        results.append(("DLL 双堆抽取自测 S1-S7", run(
            "selftest_dll_strings.py", [PY, "selftest_dll_strings.py"], AUDIT)))
        results.append(("DLL 抽取注入对照", run(
            "inject_fault_dll.py", [PY, "inject_fault_dll.py"], AUDIT)))

        print()
        print("=" * 74)
        print("H. 产物重新生成（保持与实测一致）")
        print("=" * 74)
        results.append(("工具清单生成", run(
            "gen_inventory.py", [PY, "gen_inventory.py"], HERE)))
        results.append(("分层度量", run(
            "bl_chain.py --measure", [PY, os.path.join(ROOT, "bl_chain.py"), "--measure"], HERE)))
        results.append(("分层模拟（独立第二意见）", run(
            "layering_sim.py", [PY, "layering_sim.py"], PROBE)))

    print()
    print("=" * 74)
    failed = [n for n, ok in results if not ok]
    print("汇总：%d 项，通过 %d，失败 %d"
          % (len(results), len(results) - len(failed), len(failed)))
    for n in failed:
        print("  - 失败: %s" % n)
    if failed:
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
