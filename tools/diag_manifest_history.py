# -*- coding: utf-8 -*-
r"""逐版本检查 `module/mcp/manifest.json` 的乱码（PUA）数量。

目的：**找有没有一个干净的历史版本可以还原** ——
若有，就 `git checkout <rev> -- 该文件`（比重新写一份描述靠谱得多）；
若无，才考虑重写。

★ 踩过的坑（写进注释）：
  用 `subprocess.run(..., text=True)` 读 git 输出时，Python 会按 **locale 编码
  （中文 Windows = GBK）** 解码 —— 而 git 输出里有 UTF-8 字节 ⇒ 抛
  `UnicodeDecodeError: 'gbk' codec can't decode`。
  ⇒ 正解：**capture_output=True 拿 bytes，自己 decode('utf-8', errors='replace')**，
    并给 git 设 `-c core.quotepath=false` 与 `i18n.logOutputEncoding=UTF-8`。
"""
import io
import json
import os
import subprocess
import sys

REPO = r"C:\Users\LCGX\CodeBuddy\20260923171333\BlBridge"
REL = "module/mcp/manifest.json"


def git_bytes(*args):
    r = subprocess.run(
        ["git", "-C", REPO, "-c", "core.quotepath=false",
         "-c", "i18n.logOutputEncoding=UTF-8"] + list(args),
        capture_output=True)
    return r.stdout


def pua_of(text):
    return sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)


def main():
    raw = git_bytes("log", "--format=%h|%ad|%s", "--date=short", "--", REL)
    lines = [l for l in raw.decode("utf-8", "replace").strip().split("\n") if l.strip()]
    print("  该文件的版本数: %d" % len(lines))
    print()
    print("  %-10s %-12s %-6s %-10s %s" % ("rev", "date", "PUA", "可解析", "说明"))
    print("  " + "-" * 72)

    best = None
    for l in lines[:20]:
        parts = l.split("|", 2)
        if len(parts) < 3:
            continue
        rev, date, subj = parts
        b = git_bytes("show", "%s:%s" % (rev, REL))
        t = b.decode("utf-8", "replace")
        p = pua_of(t)
        try:
            json.loads(t)
            ok = "✅"
            if best is None:
                best = rev
        except Exception:  # noqa: BLE001
            ok = "✗"
        print("  %-10s %-12s %-6d %-10s %s" % (rev, date, p, ok, subj[:40]))

    print()
    if best:
        print("  ★ 找到一个**可解析**的版本: %s" % best)
        print("    可用 `git checkout %s -- %s` 还原（但要先确认它的内容是否过时）" % (best, REL))
    else:
        print("  ✗ 近 20 个版本**全部**乱码且不可解析 ⇒ 没有可还原的干净版本")
        print("    ⇒ 只能重写这些描述字段（或从别处重新生成）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
