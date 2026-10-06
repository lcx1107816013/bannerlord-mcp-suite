#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""用**真实 tokenizer** 测工具面 token 数 —— 取代 bytes/3.44 的估算。

为什么能做：`E:\Document\spark-heretic\model\tokenizer.json` 是 **Spark2.5** 的
tokenizer，而用户跑的 4B 模型（`spark4b` / Spark-X2.5-4B-heretic-NVFP4）正是这一族
（config.json: `architectures: Spark2_5ForCausalLM`, `vocab_size: 131072`）。
所以这份 tokenizer 对该模型**是权威的**，不是近似。

先验证 vocab 与 GGUF 一致，再测：
  - 三个上游各自的工具面 token
  - full / slim / meta 三模式常驻 token
  - **真实 bytes/token 比**（用来替换全项目的 3.44 估算系数）
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

TOK_PATH = r"E:\Document\spark-heretic\model\tokenizer.json"
GGUF = r"E:\Document\spark-gguf\Spark-X2.5-4B-heretic-NVFP4.gguf"

sys.path.insert(0, HERE)
import bl_chain  # noqa: E402


def gguf_vocab(path):
    """从 GGUF 头部读 vocab_size（只读元数据，不加载张量）。"""
    try:
        with io.open(path, "rb") as fh:
            magic = fh.read(4)
            if magic != b"GGUF":
                return None, "不是 GGUF"
            ver = int.from_bytes(fh.read(4), "little")
            n_tensors = int.from_bytes(fh.read(8), "little")
            n_kv = int.from_bytes(fh.read(8), "little")

            def rd_str():
                n = int.from_bytes(fh.read(8), "little")
                return fh.read(n).decode("utf-8", "replace")

            def rd_val(t):
                if t == 0: return fh.read(1)[0]
                if t == 1: return int.from_bytes(fh.read(1), "little", signed=True)
                if t == 2: return int.from_bytes(fh.read(2), "little")
                if t == 3: return int.from_bytes(fh.read(2), "little", signed=True)
                if t == 4: return int.from_bytes(fh.read(4), "little")
                if t == 5: return int.from_bytes(fh.read(4), "little", signed=True)
                if t == 6: return int.from_bytes(fh.read(4), "little")
                if t == 7: return fh.read(1)[0] != 0
                if t == 8: return rd_str()
                if t == 9:
                    et = int.from_bytes(fh.read(4), "little")
                    n = int.from_bytes(fh.read(8), "little")
                    return [rd_val(et) for _ in range(n)]
                if t == 10: return int.from_bytes(fh.read(8), "little")
                if t == 11: return int.from_bytes(fh.read(8), "little", signed=True)
                if t == 12: return int.from_bytes(fh.read(8), "little")
                raise ValueError("未知 GGUF 类型 %d" % t)

            for _ in range(n_kv):
                key = rd_str()
                vt = int.from_bytes(fh.read(4), "little")
                val = rd_val(vt)
                if key.endswith("vocab_size"):
                    return val, "GGUF 元数据"
            return None, "未找到 vocab_size（kv=%d, tensors=%d, ver=%d）" % (n_kv, n_tensors, ver)
    except Exception as exc:  # noqa: BLE001
        return None, "读 GGUF 失败: %r" % (exc,)


def main():
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(TOK_PATH)
    tok_vocab = tok.get_vocab_size()
    print("tokenizer: %s" % TOK_PATH)
    print("  vocab_size = %d" % tok_vocab)

    gv, src = gguf_vocab(GGUF)
    print("GGUF:      %s" % os.path.basename(GGUF))
    print("  vocab_size = %s（%s）" % (gv, src))
    match = (gv == tok_vocab)
    print("  => vocab 一致: %s" % ("是 ✅（tokenizer 对该模型权威）" if match else "否 ⚠️"))
    if not match:
        print("  ⚠️ vocab 不一致，下面的 token 数仅供参考，不能声称是精确值。")

    def ntok(s):
        return len(tok.encode(s, add_special_tokens=False).ids)

    chain = bl_chain.Chain(log_dir=os.path.join(HERE, "_logs")).start()
    try:
        if any(u.error for u in chain.upstreams):
            print("!! 上游未连上: %s" % [(u.name, u.error) for u in chain.upstreams if u.error])
            return 1

        print("\n## 1. 三个上游的工具面（真实 token）\n")
        print("| 上游 | 工具数 | 字节 | **真实 token** | bytes/token |")
        print("|---|---:|---:|---:|---:|")
        grand_b = grand_t = grand_n = 0
        for u in chain.upstreams:
            payload = json.dumps(u.tools, ensure_ascii=False, separators=(",", ":"))
            b = len(payload.encode("utf-8"))
            t = ntok(payload)
            grand_b += b
            grand_t += t
            grand_n += len(u.tools)
            print("| `%s` | %d | %s | **%s** | %.2f |"
                  % (u.name, len(u.tools), format(b, ","), format(t, ","), b / t))
        print("| **合计** | **%d** | **%s** | **%s** | %.2f |"
              % (grand_n, format(grand_b, ","), format(grand_t, ","), grand_b / grand_t))

        print("\n## 2. 各模式常驻面（真实 token）\n")
        print("| 模式 | 可见工具 | 字节 | **真实 token** | 占 full |")
        print("|---|---:|---:|---:|---:|")
        save_mode, save_groups = chain.mode, chain.groups
        base_t = None
        rows = []
        for m in ("full", "slim", "meta"):
            chain.mode, chain.groups = m, []
            payload = json.dumps(chain.visible_tools(), ensure_ascii=False,
                                 separators=(",", ":"))
            b = len(payload.encode("utf-8"))
            t = ntok(payload)
            vis = len(chain.visible_tools())
            if m == "full":
                base_t = t
            rows.append((m, vis, b, t))
        for m, vis, b, t in rows:
            print("| `%s` | %d | %s | **%s** | %.1f%% |"
                  % (m, vis, format(b, ","), format(t, ","), 100.0 * t / base_t))
        chain.mode, chain.groups = save_mode, save_groups

        print("\n## 3. 估算系数校准\n")
        full_t = rows[0][3]
        full_b = rows[0][2]
        est = full_b / 3.44
        print("- 实测 bytes/token = **%.2f**（本项目原用 3.44 估算）" % (full_b / full_t))
        if full_t < est:
            print("  ⇒ 3.44 估算**高估**了工具面 token **%.1f%%**"
                  % (100.0 * (est - full_t) / full_t))
            print("    真实 %s token，而 bytes/3.44 报 %s token（多报 %s）。"
                  % (format(full_t, ","), format(round(est), ","),
                     format(round(est - full_t), ",")))
        else:
            print("  ⇒ 3.44 估算**低估**了工具面 token **%.1f%%**"
                  % (100.0 * (full_t - est) / est))
            print("    真实 %s token，而 bytes/3.44 只报 %s token。"
                  % (format(full_t, ","), format(round(est), ",")))
        print("  ⇒ 结论：真实 token 比 3.44 估算**低**，所以分层的紧迫性不变、"
              "但收益的绝对数应按真实值报。")

        print("\n## 4. 各上下文窗口下工具面占比（真实 token）\n")
        print("| 窗口 | full | slim | meta |")
        print("|---|---:|---:|---:|")
        for ctx in (32768, 131072, 262144):
            cells = []
            for _, _, _, t in rows:
                cells.append("%.1f%%" % (100.0 * t / ctx))
            print("| %s | %s |" % (format(ctx, ","), " | ".join(cells)))

        out = {"tokenizer": TOK_PATH, "tokenizerVocab": tok_vocab,
               "ggufVocab": gv, "vocabMatch": match,
               "convention": "compact JSON (separators=(',',':')), no trailing newline",
               "upstreams": [{"name": u.name, "tools": len(u.tools),
                              "bytes": len(json.dumps(u.tools, ensure_ascii=False,
                                                      separators=(",", ":")).encode()),
                              "tokens": ntok(json.dumps(u.tools, ensure_ascii=False,
                                                        separators=(",", ":")))}
                             for u in chain.upstreams],
               "modes": [{"mode": m, "visible": v, "bytes": b, "tokens": t}
                         for m, v, b, t in rows],
               "bytesPerToken": round(full_b / full_t, 3)}
        dest = os.path.join(HERE, "real_tokens.json")
        with io.open(dest, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print("\n-> %s" % dest)
        return 0
    finally:
        chain.stop()


if __name__ == "__main__":
    sys.exit(main())
