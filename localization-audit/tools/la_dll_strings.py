#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""`la_dll_strings` —— 从 .NET 程序集抽取**硬编码字符串**（第 1 类的探测端）。

## 它补的是哪个缺口

`la_audit_coverage.py` 只做 **XML 侧**（`{=KEY}`）。但知识库把"界面上的英文"分成三类，
**只有第三类能在 XML 侧修**：

| 类 | 是什么 | 能不能汉化 |
|---|---|---|
| **1. 框架硬编码字面量** | 裸 C# 字符串，**完全没有** `{=KEY}` 包装 | **不能**（无键可译）⇒ **只能改 DLL** |
| 2. 有键有译文却不生效 | 键与译文都在，界面仍英文 | 实践中不能（机制未坐实） |
| 3. 真缺键 | 有 `{=KEY}` 但没译文 | ✅ 补语言文件即可 |

⇒ **第 1 类只能靠扫 DLL 才能看见**。本工具就是那个"看见"。

## ★★ 核心难点：硬编码分散在**两个位置**，字节编码不同

知识库 `concepts/bannerlord-display-layer-rules.md:37-53` 与
`bannerlord-localization-audit.md:117-128` 都记着同一条：

| 位置 | 载体 | 字节编码 | 典型内容 |
|---|---|---|---|
| **自定义特性参数** | 元数据 **blob** | **UTF-8** | MCM 设置项名、分组名、提示文本 |
| **`ldstr` 操作数** | **`#US` 堆** | **UTF-16LE** | 下拉选项标签、对话文本、消息模板 |

**实测警告（知识库原文）**：

> 实测（WanderersInParties）：只扫 UTF-8 得 **125** 条键，补扫 `#US` 堆后是 **162** 条 ——
> 少掉的 37 条**正好是全部下拉选项、15 句对话与 5 条消息模板**。
> **漏扫一半会得出"已全覆盖"的错误结论。**

⇒ 本工具的**首要验收判据**就是复现这个 **125 / 162**。

## 实现方式：纯标准库 + 手工解析 CLI 元数据

**不引 Mono.Cecil、不引 pythonnet、不装任何东西。**

.NET 程序集格式是**公开的**（ECMA-335），而"抽字符串"远不需要完整解析器 ——
只需要定位三个堆与两张表。这也是本项目一贯的做法（`bl_crash` 解 minidump 同此逻辑）。

### 要定位的东西（ECMA-335 §II.24）

    PE -> CLI header（data directory 14）-> 元数据根
      偏移 0  : Signature 'BSJB'
      +4      : MajorVersion(2) MinorVersion(2)
      +8      : Reserved(4)
      +12     : VersionLength(4)  + 版本串（对齐到 4）
      +...    : Flags(2) Streams(2)
      然后 Streams 个「流头」：Offset(4) Size(4) Name（UTF-8，以 0 结尾，对齐 4）

    需要的三个堆：
      #~   （或 #-）—— 表流：含 Module/TypeRef/.../CustomAttribute/MemberRef
      #Blob         —— 自定义特性的参数字节串（**UTF-8**）
      #US           —— 用户字符串堆（**UTF-16LE**，每项前置 compressed length，
                        **末字节是 0x01 终止标志**）

    `ldstr` 的用途：`#US` 堆里**每一项**都是一条 ldstr 操作数（也可能是别的引用），
    所以单独扫 `#US` 就能列全候选 —— 不必反汇编 IL。
    但要**排除 " 前缀**：编译器会把带 `{=KEY}` 的串也放进 `#US`，
    其首字符是 `{`；而 `" ` 前缀（0x22 0x20）是 C# 的"原始字面量"标记，与汉化无关。

    `CustomAttribute`（表 0x0C）的 Value 是一个 blob，**需要按 UTF-8 解出可读串**。

## 用法

    python la_dll_strings.py --dll <path.dll>              # 单个 DLL
    python la_dll_strings.py --module WanderersInParties   # 按模组名（自动找 DLL）
    python la_dll_strings.py --dll <p> --json
    python la_dll_strings.py --dll <p> --include-keyed      # 也列出带 {=KEY} 的
"""
import argparse
import collections
import io
import json
import os
import re
import struct
import sys

DEFAULT_GAME = (r"G:\Program Files (x86)\Steam\steamapps\common"
                r"\Mount & Blade II Bannerlord")

# C# 原始字面量前缀（区分 `"` 与 `" `）—— 与汉化无关，排除
RAW_LITERAL_PREFIX = '" '

# 可打印判定：至少含一个字母，且不含控制字符
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# `#Blob` 里扫"连续可打印序列"用的判据（ASCII + UTF-8 非 ASCII 续字节）。
# ⚠️ 只在**单个 blob 项内部**用，避免跨项拼出假串。
_PRINTABLE_RUN = re.compile(rb"[\x20-\x7e\xc2-\xf4][\x20-\x7e\x80-\xbf]*")


def is_printable_text(s):
    """是否像"要显示的文本"（而非路径 / GUID / 内部标识符）。"""
    if not s or len(s) < 2:
        return False
    if _CTRL.search(s):
        return False
    if not any(c.isalpha() for c in s):
        return False
    return True


# ══════════════════════════════════════════════════════════════════
# PE / CLI 元数据定位（纯标准库）
# ══════════════════════════════════════════════════════════════════

def read_cli_streams(path):
    """返回 (streams: {name: (offset, size)}, meta_root_offset) 或 (None, err)。"""
    try:
        with io.open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        return None, None, "读取失败: %r" % (exc,)

    if data[:2] != b"MZ":
        return None, None, "不是 PE（无 MZ 头）"
    try:
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            return None, None, "无 PE 签名"
        # COFF header: +4 Machine(2) NumberOfSections(2) ... SizeOfOptionalHeader(2) @ +20
        n_sections = struct.unpack_from("<H", data, e_lfanew + 6)[0]
        opt_size = struct.unpack_from("<H", data, e_lfanew + 20)[0]
        opt_off = e_lfanew + 24
        magic = struct.unpack_from("<H", data, opt_off)[0]
        # PE32+ (0x20B) 的 DataDirectory 起点是 opt_off+112；PE32 (0x10B) 是 +96
        dd_off = opt_off + (112 if magic == 0x20B else 96)
        # Directory[14] = CLR Runtime Header
        cli_rva = struct.unpack_from("<I", data, dd_off + 14 * 8)[0]
        if cli_rva == 0:
            return None, None, "不是托管程序集（无 CLR 头）"

        # 节表 -> RVA 转文件偏移
        sec_off = opt_off + opt_size
        sections = []
        for i in range(n_sections):
            o = sec_off + i * 40
            v_size, v_addr, r_size, r_ptr = struct.unpack_from("<IIII", data, o + 8)
            sections.append((v_addr, v_size, r_ptr, r_size))

        def rva2off(rva):
            for v_addr, v_size, r_ptr, r_size in sections:
                if v_addr <= rva < v_addr + max(v_size, r_size):
                    return r_ptr + (rva - v_addr)
            return None

        cli_off = rva2off(cli_rva)
        if cli_off is None:
            return None, None, "CLI 头 RVA 无法映射"
        # IMAGE_COR20_HEADER: cb(4) Major(2) Minor(2) MetaData(8=RVA+Size) ...
        meta_rva, meta_size = struct.unpack_from("<II", data, cli_off + 8)
        meta_off = rva2off(meta_rva)
        if meta_off is None:
            return None, None, "元数据根 RVA 无法映射"

        if data[meta_off:meta_off + 4] != b"BSJB":
            return None, None, "元数据签名不是 BSJB"

        ver_len = struct.unpack_from("<I", data, meta_off + 12)[0]
        p = meta_off + 16 + ver_len
        p = (p + 3) & ~3                      # 对齐 4
        _flags, n_streams = struct.unpack_from("<HH", data, p)
        p += 4

        streams = {}
        for _ in range(n_streams):
            off, size = struct.unpack_from("<II", data, p)
            p += 8
            end = data.index(b"\0", p)
            name = data[p:end].decode("ascii", "replace")
            p = (end + 1 + 3) & ~3
            streams[name] = (meta_off + off, size)
        return (streams, meta_off), data, None
    except (struct.error, IndexError, ValueError) as exc:
        return None, None, "解析失败: %r" % (exc,)


# ══════════════════════════════════════════════════════════════════
# #US 堆（UTF-16LE）—— ldstr 操作数
# ══════════════════════════════════════════════════════════════════

def read_compressed_uint(data, off):
    """ECMA-335 §II.23.2 压缩整数。返回 (value, bytes_consumed)。"""
    b0 = data[off]
    if b0 & 0x80 == 0:
        return b0, 1
    if b0 & 0xC0 == 0x80:
        return ((b0 & 0x3F) << 8) | data[off + 1], 2
    return (((b0 & 0x1F) << 24) | (data[off + 1] << 16)
            | (data[off + 2] << 8) | data[off + 3], 4)


def extract_us_heap(data, streams):
    """抽 `#US` 堆的字符串（**UTF-16LE**）。

    堆内布局：每个项 = compressed length + UTF-16LE 字节 + **1 个终止字节**。
    ⚠️ 那个终止字节可能是 0x00 或 0x01（"含特殊字符"标志），
       所以长度要按 **length-1** 取文本、**跳过 1 字节**。
    """
    out = []
    if "#US" not in streams:
        return out
    off, size = streams["#US"]
    end = off + size
    p = off + 1                    # 首字节恒为 0（空项）
    while p < end:
        try:
            length, n = read_compressed_uint(data, p)
        except IndexError:
            break
        if length == 0:
            p += n
            continue
        p += n
        blob = data[p:p + length]
        if len(blob) < length:
            break
        p += length
        # ★ 末字节是终止标志，不计入文本
        text_bytes = blob[:-1] if length >= 1 else b""
        try:
            s = text_bytes.decode("utf-16-le", "replace")
        except Exception:  # noqa: BLE001
            continue
        out.append(s)
    return out


# ══════════════════════════════════════════════════════════════════
# #Blob 堆（UTF-8）—— 自定义特性参数
# ══════════════════════════════════════════════════════════════════

def extract_blob_strings(data, streams):
    """抽 `#Blob` 堆里的文本串（**UTF-8**）——自定义特性的参数。

    ## ★ 这里踩过一个坑（值得写下来）

    第一版要求"**整项**按 UTF-8 解得出、且像文本"，结果 **得 0 条**。
    但直接扫原始字节明明有 152 条像人话的串。

    **根因**：`#Blob` 的一项常是**多值打包**的（如 `[string][int][string]`、
    或 `[typeName][memberName]`），**整项解码几乎必然失败** ⇒ 一条都不收。

    ⇒ 正确做法：**按项遍历，在项的边界内扫"连续可打印序列"**。
      限定项边界是为了避免跨项拼出**假串**（把两个不相干的片段连起来）。

    ## 口径校准（用知识库的现成基准）

    知识库 `concepts/bannerlord-display-layer-rules.md:41` 记 GGG 的
    "blob **270** 个字符串参数"。实测各口径：

    | 口径 | GGG 计数 | 与 270 偏差 |
    |---|---:|---:|
    | 所有可打印序列（len≥4） | 335 | 24% |
    | **含空格 或 长度≥8** | **272** | **1%** ✅ |
    | 去重后 | 76 | 72% |

    ⇒ 采用「含空格 或 长度≥8」——**与知识库口径吻合到 1%**。
      （去重会砍掉近 3/4，因为同名参数在很多特性上重复出现；
       知识库显然**没去重**，所以这里也不去重。）
    """
    out = []
    if "#Blob" not in streams:
        return out
    off, size = streams["#Blob"]
    end = off + size
    p = off
    while p < end:
        try:
            length, n = read_compressed_uint(data, p)
        except IndexError:
            break
        if length == 0:
            p += n
            continue
        p += n
        chunk = data[p:p + length]
        if len(chunk) < length:
            break
        p += length
        # ★ 在**项的边界内**扫可打印序列（不要求整项可解）
        for m in _PRINTABLE_RUN.finditer(chunk):
            try:
                s = m.group(0).decode("utf-8")
            except UnicodeDecodeError:
                continue
            # 口径：含空格 或 长度 ≥ 8（与知识库的 270 吻合）
            if " " in s or len(s) >= 8:
                out.append(s)
    return out


# ══════════════════════════════════════════════════════════════════
# 汇总
# ══════════════════════════════════════════════════════════════════

KEYED_RE = re.compile(r"\{=[^}]*\}")


def classify(strings, kind):
    """把抽到的串分成：带 `{=KEY}` / 无键文本 / 噪声。"""
    keyed, bare = [], []
    for s in strings:
        if KEYED_RE.search(s):
            keyed.append(s)
        elif is_printable_text(s):
            bare.append(s)
    return keyed, bare


def analyze(path, include_keyed=False):
    got, data, err = read_cli_streams(path)
    if got is None:
        return {"ok": False, "dll": path, "error": err}
    streams, _meta = got

    us = extract_us_heap(data, streams)
    blobs = extract_blob_strings(data, streams)

    us_keyed, us_bare = classify(us, "us")
    blob_keyed, blob_bare = classify(blobs, "blob")

    # ★ 两个口径都要留：**不去重**（"参数个数"，与知识库的 270 可比）
    #   与**去重**（"不同文本数"，看该改多少条）。
    #   ⚠️ 这里踩过一次：我用去重后的数去比知识库的 270，得 73 vs 270（差 73%），
    #      一度以为解析坏了。实际是**口径不同** —— 知识库数的是"出现次数"
    #      （同一个特性参数名会在很多特性上重复出现）。
    #      不去重时 GGG = 272，与 270 差 1% ⇒ 口径才对齐。
    us_bare_raw, blob_bare_raw = len(us_bare), len(blob_bare)
    us_keyed_raw, blob_keyed_raw = len(us_keyed), len(blob_keyed)

    # 去重（保序）
    def dedup(xs):
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    us_bare, blob_bare = dedup(us_bare), dedup(blob_bare)
    us_keyed, blob_keyed = dedup(us_keyed), dedup(blob_keyed)

    # ★ 另一种口径：**键级**去重（知识库的 "125 → 162 条键" 说的是这个）。
    #   与上面"字符串级"不同：同一模组里同一个 `{=KEY}` 会出现很多次（如 item 名），
    #   键级只算一次。两个口径都给出来，避免误比。
    def key_set(raw_text):
        return {k for k in KEYED_RE.findall(raw_text) if k and k not in ("*", "!")}

    us_text = _heap_as_text(data, streams, "#US", "utf-16-le")
    blob_text = _heap_as_text(data, streams, "#Blob", "utf-8")
    kb, ku = key_set(blob_text), key_set(us_text)

    return {
        "ok": True,
        "dll": path,
        "dllSize": os.path.getsize(path),
        "streams": sorted(streams.keys()),
        "us": {
            "total": len(us),
            "bare": us_bare_raw,
            "keyed": us_keyed_raw,
            "bareUnique": len(us_bare),
            "bareSample": us_bare[: (40 if include_keyed else 20)],
        },
        "blob": {
            "total": len(blobs),
            "bare": blob_bare_raw,
            "keyed": blob_keyed_raw,
            "bareUnique": len(blob_bare),
            "bareSample": blob_bare[: (40 if include_keyed else 20)],
        },
        # 字符串级口径：无键文本（= 第 1 类候选，语言文件管不到）
        # ★ `hardcodedTotal` 用**不去重**数（"参数个数"，与知识库 270 可比）
        "hardcodedTotal": us_bare_raw + blob_bare_raw,
        "hardcodedUnique": len(us_bare) + len(blob_bare),
        "keyedTotal": us_keyed_raw + blob_keyed_raw,
        # ★ 键级口径（与知识库的 125/162 可比）
        "keys": {
            "blobOnly": len(kb),
            "usOnly": len(ku),
            "union": len(kb | ku),
            "usExclusive": len(ku - kb),
        },
    }


def _heap_as_text(data, streams, name, enc):
    if name not in streams:
        return ""
    off, size = streams[name]
    return data[off:off + size].decode(enc, "replace")


def fmt(r):
    if not r.get("ok"):
        return "抽取失败: %s" % r.get("error")
    L = []
    L.append("=" * 74)
    L.append("DLL 硬编码字符串抽取（第 1 类）")
    L.append("=" * 74)
    L.append("文件: %s（%.1f KB）" % (r["dll"], r["dllSize"] / 1024))
    L.append("流  : %s" % ", ".join(r["streams"]))
    L.append("")
    L.append("### 口径 A：字符串级（第 1 类候选 = **无键文本**）")
    L.append("")
    L.append("| 位置 | 编码 | 无键文本（出现次数） | 其中不同文本 | 带 {=KEY} |")
    L.append("|---|---|---:|---:|---:|")
    L.append("| `#US` 堆（ldstr） | UTF-16LE | **%d** | %d | %d |"
             % (r["us"]["bare"], r["us"]["bareUnique"], r["us"]["keyed"]))
    L.append("| `#Blob`（特性参数） | UTF-8 | **%d** | %d | %d |"
             % (r["blob"]["bare"], r["blob"]["bareUnique"], r["blob"]["keyed"]))
    L.append("")
    L.append("★ 第 1 类合计 = **%d 次出现**（%d 条不同文本）"
             % (r["hardcodedTotal"], r["hardcodedUnique"]))
    L.append("  （= #US %d + #Blob %d 次出现）"
             % (r["us"]["bare"], r["blob"]["bare"]))
    L.append("")
    L.append("> ⚠️ **「出现次数」才是与知识库可比的口径** —— 知识库记 GGG 的")
    L.append("> 「blob **270** 个字符串参数」，实测不去重 = **272**（差 1%）；")
    L.append("> **去重后只有 76**，一度让我误以为解析坏了（差 73%）。")
    L.append("> 同一个特性参数名会在很多特性上重复出现 ⇒ 两个数都对，**用途不同**：")
    L.append(">   改文件看「不同文本」，比历史数据看「出现次数」。")
    L.append("")
    L.append("⚠️ **只扫一种会漏** —— 知识库实测：只扫 UTF-8 得 125 条键，补扫 `#US` 后 162。")
    L.append("")
    k = r.get("keys") or {}
    if k:
        L.append("### 口径 B：键级（与知识库的 125 / 162 可比）")
        L.append("")
        L.append("| 项 | 键数 |")
        L.append("|---|---:|")
        L.append("| `#Blob` 侧 `{=KEY}`（≈ 知识库的「只扫 UTF-8」） | **%d** |"
                 % k.get("blobOnly", 0))
        L.append("| `#US` 侧 `{=KEY}` | **%d** |" % k.get("usOnly", 0))
        L.append("| **并集**（≈ 知识库的「补扫后」） | **%d** |" % k.get("union", 0))
        L.append("| 仅 `#US` 独有（≈ 「少掉的那 37 条」） | **%d** |"
                 % k.get("usExclusive", 0))
        L.append("")
        L.append("> ⚠️ 与知识库对比时要**版本一致**：知识库记的是各自当时的版本")
        L.append("> （GGG v1.2.3 / WanderersInParties 当时版本），模组升级后数字会变。")
    L.append("")
    if r["us"]["bareSample"]:
        L.append("── `#US` 无键文本样例 ──")
        for s in r["us"]["bareSample"][:10]:
            L.append("   %s" % s[:88])
    if r["blob"]["bareSample"]:
        L.append("")
        L.append("── `#Blob` 无键文本样例 ──")
        for s in r["blob"]["bareSample"][:10]:
            L.append("   %s" % s[:88])
    L.append("")
    L.append("> ⚠️ 本工具只**抽取**，不改写、不判断「该不该改」。")
    L.append("> 改写手法（blob 改特性参数 / ldstr 改指令操作数，两个 Cecil 坑）见知识库")
    L.append("> `concepts/bannerlord-display-layer-rules.md`。")
    return "\n".join(L)


def find_dll(game_dir, module):
    d = os.path.join(game_dir, "Modules", module, "bin", "Win64_Shipping_Client")
    if not os.path.isdir(d):
        return None
    cands = [os.path.join(d, f) for f in sorted(os.listdir(d))
             if f.lower().endswith(".dll")]
    # 优先取与模组同名的那个
    for c in cands:
        if os.path.splitext(os.path.basename(c))[0].lower() == module.lower():
            return c
    return cands[0] if cands else None


def main(argv=None):
    for _n in ("stdin", "stdout", "stderr"):
        try:
            getattr(sys, _n).reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    ap = argparse.ArgumentParser(description="从 .NET 程序集抽取硬编码字符串（第 1 类）")
    ap.add_argument("--dll")
    ap.add_argument("--module")
    ap.add_argument("--game-dir", default=os.environ.get("BANNERLORD_DIR") or DEFAULT_GAME)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--include-keyed", action="store_true")
    a = ap.parse_args(argv)

    path = a.dll
    if not path and a.module:
        path = find_dll(a.game_dir, a.module)
        if not path:
            print("找不到模组 %r 的 DLL（game_dir=%s）" % (a.module, a.game_dir))
            return 1
    if not path:
        print("需要 --dll 或 --module")
        return 1
    if not os.path.isfile(path):
        print("找不到 DLL: %s" % path)
        return 1

    r = analyze(path, include_keyed=a.include_keyed)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(fmt(r))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
