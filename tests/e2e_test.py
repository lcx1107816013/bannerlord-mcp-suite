#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""端到端：把 bl_chain.py **当成一个 MCP 服务器**，用与 DSH 完全一样的协议跟它说话。

这验证的是 DSH 真正会做的事：
    initialize -> notifications/initialized -> tools/list -> tools/call
（而不是只在 Python 里直接调函数 —— 那样测不出协议面是否正确。）

对每个模式各跑一遍，断言：
  1. initialize 返回合法 capabilities
  2. tools/list 的工具数与预期一致
  3. tools/call 能经元工具打通一个真上游
  4. 隐藏的工具**照样**调得到（无损的实证）
"""
import glob
import io
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

CHAIN = os.path.join(ROOT, "bl_chain.py")
PY = r"D:\Program Files\Python312\python.exe"
PROBE = os.path.join(ROOT, "probe")
def _expected_total():
    """全量工具数 = **独立量出来的**各上游之和（不硬编码）。

    ★ 为什么改成这样（2026-10-06 踩到两次）：
    原来这里写死 `89`，于是每加一个工具就要手工改测试 ——
    而"忘了改"的症状是**测试红了但功能是好的**，读者会去查桥，
    浪费时间。更糟的是**麻木**：见惯"这个红是正常的"之后，
    真的坏了也不会有人看。
    ⇒ 改成从 `_mcp_probe/measured_<server>_raw.json`（**独立探针**产出）
      现场求和。加工具时探针会重新量，期望值**自己跟上**。
    ⇒ 这仍是有意义的判据：若桥**少转发/多转发**了工具，两边就对不上。
    """
    import glob as _g
    total = 0
    for p in sorted(_g.glob(os.path.join(PROBE, "measured_*_raw.json"))):
        with io.open(p, encoding="utf-8") as fh:
            total += len(json.load(fh))
    return total


def _expected_group(group):
    """某组的工具数 —— 取自 bl_chain 的 TOOL_GROUPS。

    ⚠️ 这一项是**自指**的（从被测对象读分组表），所以它只证明
    「分组筛选逻辑生效」，**不**证明"分组内容对不对"。
    分组内容的独立校验在 `crosscheck_test.py` 的 X3 段（比对上游 TOOL_GROUPS）。
    ⇒ 分工写清楚，避免把自指判据当成独立判据。
    """
    sys.path.insert(0, HERE)
    import bl_chain as c
    return len((c.TOOL_GROUPS.get(group) or {}).get("names") or [])


MODES = [
    ("full", None, None),          # None ⇒ 用 _expected_total()
    ("slim", None, None),
    ("meta", None, 5),
    ("full", "ro", None),          # None ⇒ 用 _expected_group("ro")
    ("meta", "battle", 5),
]


class Client:
    def __init__(self, mode, groups):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["DSH_CHAIN_MODE"] = mode
        if groups:
            env["DSH_CHAIN_GROUPS"] = groups
        else:
            env.pop("DSH_CHAIN_GROUPS", None)
        self.proc = subprocess.Popen([PY, CHAIN], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     env=env, cwd=HERE, bufsize=0)
        self._id = 0

    def send(self, obj):
        self.proc.stdin.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def recv(self):
        raw = self.proc.stdout.readline()
        if not raw:
            return None
        return json.loads(raw.decode("utf-8", "replace"))

    def request(self, method, params=None):
        self._id += 1
        self.send({"jsonrpc": "2.0", "id": self._id, "method": method,
                   "params": params or {}})
        return self.recv()

    def init(self):
        r = self.request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "e2e", "version": "1"}})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return r

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def text_of(resp):
    out = []
    for c in (resp.get("result") or {}).get("content") or []:
        if c.get("type") == "text":
            out.append(c.get("text") or "")
    return "\n".join(out)


def main():
    fails = []
    for mode, groups, expect in MODES:
        # 期望值：显式给的用显式，否则现场从**独立探针**/分组表算
        if expect is None:
            expect = _expected_group(groups) if groups else _expected_total()
        label = mode + ("/" + groups if groups else "")
        c = Client(mode, groups)
        try:
            init = c.init()
            caps = (init.get("result") or {}).get("capabilities")
            tl = c.request("tools/list")
            tools = (tl.get("result") or {}).get("tools") or []
            names = [t["name"] for t in tools]

            ok_count = len(tools) == expect
            print("[%s] initialize caps=%s" % (label, json.dumps(caps, ensure_ascii=False)))
            print("      tools/list -> %d 个（期望 %d）%s"
                  % (len(tools), expect, "OK" if ok_count else "**不符**"))
            if not ok_count:
                fails.append("%s 工具数 %d != %d" % (label, len(tools), expect))
            if not caps or "tools" not in caps:
                fails.append("%s capabilities 异常" % label)

            # meta 模式：用检索 -> details -> call 走完整三步
            if mode in ("meta", "slim+meta"):
                meta_names = set(names)
                for need in ("chain_search_tools", "chain_get_tool_details",
                             "chain_call_tool", "chain_status", "chain_refresh"):
                    if need not in meta_names:
                        fails.append("%s 缺元工具 %s" % (label, need))
                # 三步：检索
                r1 = c.request("tools/call", {"name": "chain_search_tools",
                                              "arguments": {"query": "汉化", "limit": 4}})
                t1 = text_of(r1)
                # 参数：取 details
                r2 = c.request("tools/call", {"name": "chain_get_tool_details",
                                              "arguments": {"name": "bh_list_languages"}})
                t2 = text_of(r2)
                # 调用：一个安全的只读上游工具
                r3 = c.request("tools/call", {"name": "chain_call_tool",
                                              "arguments": {"name": "bh_list_languages",
                                                            "args": {}}})
                t3 = text_of(r3)
                three_ok = ('bh_' in t1 and 'inputSchema' in t2 and t3
                            and "未知工具" not in t3)
                print("      三步链路 search/details/call -> %s"
                      % ("OK" if three_ok else "**失败**"))
                if not three_ok:
                    fails.append("%s 三步链路失败: %s | %s | %s"
                                 % (label, t1[:120], t2[:120], t3[:120]))
                # ★ 无损实证：一个**不在** tools/list 里的工具，仍能经 call_tool 调到
                if "bl_mcm_settings" not in meta_names:
                    r4 = c.request("tools/call", {
                        "name": "chain_call_tool",
                        "arguments": {"name": "bl_config", "args": {}}})
                    t4 = text_of(r4)
                    hidden_ok = bool(t4) and "未知工具" not in t4
                    print("      隐藏工具 bl_config 仍可调 -> %s" % ("OK" if hidden_ok else "**失败**"))
                    if not hidden_ok:
                        fails.append("%s 隐藏工具调用失败: %s" % (label, t4[:150]))
            else:
                # 非 meta：工具原样可见，直接调一个只读的
                r = c.request("tools/call", {"name": "bh_list_languages", "arguments": {}})
                t = text_of(r)
                ok = bool(t) and "未知工具" not in t
                print("      直呼 bh_list_languages -> %s" % ("OK" if ok else "**失败**"))
                if not ok:
                    fails.append("%s 直呼失败: %s" % (label, t[:150]))
            print()
        finally:
            c.close()

    print("=" * 70)
    if fails:
        print("端到端失败 %d 项：" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    print("端到端全部通过：bl_chain 是一个可用的 MCP 服务器（%d 种模式配置）。" % len(MODES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
