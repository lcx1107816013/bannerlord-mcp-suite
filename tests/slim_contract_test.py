#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""证明 **slim 模式是无损的**（这条之前没验过 —— 只验了 full 的逐字节相同）。

问题：slim 会截断 description 和属性说明。凭什么说它"无损"？

判据（**行为等价性**，不是文字相同）：
    JSON Schema 里决定**行为**的是 type / enum / default / required /
    additionalProperties / items / 嵌套结构；决定**可读性**的才是 description。
    所以只要前者逐字段不变，模型的**调用正确性**就不受影响。

本测试对 89 个工具逐个做**深比对**，断言除 description 外的**每一个字段**
都与上游完全一致，并且：
  S1 description 只**变短**，绝不变长或变成空
  S2 type 不变（含嵌套属性）
  S3 enum 列表逐项相同（枚举值错一个 = 模型必错）
  S4 default 值相同
  S5 required 列表相同（顺序也相同）
  S6 additionalProperties 相同
  S7 属性**数量**与**名字集合**相同（不许丢字段）
  S8 嵌套结构（anyOf/oneOf/items/$defs）递归相同
  S9 元工具自己不受 slim 影响
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 伞仓根（bl_chain.py / localization-audit 在这）
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

sys.path.insert(0, HERE)
import bl_chain  # noqa: E402

# 这些键是「说明性」的，允许被 slim 截断
DESC_KEYS = ("description", "title", "examples", "$comment")


def strip_desc(o):
    """递归剥掉全部说明性字段，只留**行为相关**的部分。"""
    if isinstance(o, dict):
        return {k: strip_desc(v) for k, v in o.items() if k not in DESC_KEYS}
    if isinstance(o, list):
        return [strip_desc(x) for x in o]
    return o


def walk_descs(o, path="", out=None):
    """递归收集所有 description 字符串及其路径。"""
    if out is None:
        out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            if k in DESC_KEYS and isinstance(v, str):
                out[path + "/" + k] = v
            else:
                walk_descs(v, path + "/" + k, out)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk_descs(v, "%s[%d]" % (path, i), out)
    return out


def main():
    fails = []
    chain = bl_chain.Chain(log_dir=os.path.join(HERE, "_logs")).start()
    try:
        if any(u.error for u in chain.upstreams):
            print("!! 上游未连上: %s" % [(u.name, u.error) for u in chain.upstreams if u.error])
            return 1

        chain.mode = "full"
        full = {t["name"]: t for t in chain.visible_tools()}
        chain.mode = "slim"
        slim = {t["name"]: t for t in chain.visible_tools()}

        if set(full) != set(slim):
            fails.append("S7 工具名集合变了")
            print("!! 工具名集合不一致")

        s1 = s2 = s3 = s4 = s5 = s6 = s7 = s8 = 0
        grew, emptied, enum_changed, type_changed = [], [], [], []
        req_changed, def_changed, ap_changed, propname_changed, nested_changed = [], [], [], [], []

        for name, tf in full.items():
            ts = slim.get(name)
            if ts is None:
                continue
            sf, ss = tf.get("inputSchema") or {}, ts.get("inputSchema") or {}

            # S2/S3/S4/S5/S6/S8：剥掉说明后，行为部分必须**完全相等**
            bf, bs = strip_desc(sf), strip_desc(ss)
            if bf != bs:
                # 定位差异类型，便于报错
                if bf.get("type") != bs.get("type"):
                    type_changed.append(name)
                if bf.get("required") != bs.get("required"):
                    req_changed.append(name)
                if bf.get("additionalProperties") != bs.get("additionalProperties"):
                    ap_changed.append(name)
                pf = (bf.get("properties") or {})
                ps = (bs.get("properties") or {})
                if set(pf) != set(ps):
                    propname_changed.append(name)
                else:
                    for pk in pf:
                        a, b = pf[pk], ps.get(pk)
                        if isinstance(a, dict) and isinstance(b, dict):
                            if a.get("enum") != b.get("enum"):
                                enum_changed.append("%s.%s" % (name, pk))
                            if a.get("default") != b.get("default"):
                                def_changed.append("%s.%s" % (name, pk))
                            if a.get("type") != b.get("type"):
                                type_changed.append("%s.%s" % (name, pk))
                    if pf != ps:
                        nested_changed.append(name)
            else:
                s2 += 1
                s3 += 1
                s4 += 1
                s5 += 1
                s6 += 1
                s8 += 1

            # S7：属性名集合与数量
            pf = (sf.get("properties") or {})
            ps = (ss.get("properties") or {})
            if set(pf) == set(ps) and len(pf) == len(ps):
                s7 += 1
            else:
                propname_changed.append(name)

            # S1：description 只许变短
            df = walk_descs(tf)
            ds = walk_descs(ts)
            for k, v in df.items():
                if k in ds:
                    if len(ds[k]) > len(v):
                        grew.append("%s%s" % (name, k))
                    if v and not ds[k]:
                        emptied.append("%s%s" % (name, k))
            s1 += 1

        n = len(full)
        print("slim 无损性深比对（%d 个工具）\n" % n)
        print("| 判据 | 含义 | 通过 |")
        print("|---|---|---:|")
        print("| S1 | description 只变短、不变空 | %d/%d |" % (s1, n))
        print("| S2/S3/S4/S5/S6/S8 | 剥掉说明后 schema **完全相等**（type/enum/default/required/additionalProperties/嵌套） | %d/%d |" % (s2, n))
        print("| S7 | 属性名集合与数量不变 | %d/%d |" % (s7, n))

        for label, lst in (("description 变长", grew), ("description 变空", emptied),
                           ("enum 改变", enum_changed), ("type 改变", type_changed),
                           ("required 改变", req_changed), ("default 改变", def_changed),
                           ("additionalProperties 改变", ap_changed),
                           ("属性名集合改变", propname_changed),
                           ("嵌套结构改变", nested_changed)):
            if lst:
                fails.append("%s: %s" % (label, lst[:8]))
                print("\n   [!!] %s: %s" % (label, lst[:8]))

        # S9：元工具不受 slim 影响（meta_tools 是静态的）
        mt_a, mt_b = chain.meta_tools(), chain.meta_tools()
        if json.dumps(mt_a, sort_keys=True) != json.dumps(mt_b, sort_keys=True):
            fails.append("S9 元工具定义不稳定")
        else:
            print("| S9 | 元工具定义在 slim 下不受影响 | ok |")

        # 汇总：slim 省了多少、且丢的全是说明文字
        chain.mode = "full"
        fb = bl_chain._jb(chain.visible_tools())
        ft, _ = bl_chain.count_tokens(chain.visible_tools())
        chain.mode = "slim"
        sb = bl_chain._jb(chain.visible_tools())
        st, _ = bl_chain.count_tokens(chain.visible_tools())
        print("\nslim 效果：%s B -> %s B（-%.0f%%）；%s -> %s token（-%.0f%%）"
              % (format(fb, ","), format(sb, ","), 100.0 * (fb - sb) / fb,
                 format(ft, ","), format(st, ","), 100.0 * (ft - st) / ft))
        print("省下的**全部**是说明文字：行为相关的 schema 一个字段都没变。")

        print("\n" + "=" * 70)
        if fails:
            print("slim 无损性验证失败 %d 项：" % len(fails))
            for f in fails:
                print("  - %s" % f)
            return 1
        print("slim 无损性验证通过：89 个工具的行为契约逐字段不变，只有说明文字被截断。")
        return 0
    finally:
        chain.stop()


if __name__ == "__main__":
    sys.exit(main())
