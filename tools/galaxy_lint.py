#!/usr/bin/env python3
"""CustomLogic.galaxy 静态体检（shw139 事故后加入）。

目前检查六类「编译期才会炸」的问题：

1. **变量未声明**（auto* / lv_* 两类：自动变量与局部变量）：SC2 生成代码里的 `for ( ; ( (autoXXXX_ai >= 0 && lv_a <= autoXXXX_ae) ...)`
   依赖函数声明区的 `const int autoXXXX_ae/_ai;`。preset_gen 生成的函数曾漏掉这一段声明块
   → 整个脚本读取失败（游戏内报「解析for时出错，可能缺少分号」）。
2. **大括号配平**：全文 `{`/`}` 必须相等。
3. **text/string 转换误用**；3b. **string 左值 ← 文本表达式**（两者都是实测会编译失败的类型错误，
   后者见 shw254b 事故：`string 变量 = StringExternal(...) + IntToString(...)`）；
4. **函数外裸语句**；5. **未声明标识符**。
5. **未声明标识符（与名字族无关的硬校验）**：函数体里出现在**变量位置**的标识符
   （后面不接 `(` 的，即非函数调用）减去「本函数声明 + 参数 + 文件作用域名字 +
   关键字/类型 + `c_*`/`libNtve_*` 库常量」，剩下的就是编译器会拒收的名字。
   前四项都建立在名字族正则上，而正则一旦写窄就与代码同源同错（shw239/240 连续
   两次漏掉 auto 声明），故加这一项做兜底：它对未知名字族天然免疫。

用法：
    python3 tools/galaxy_lint.py [galaxy路径]         # 默认 work/blackhand/CustomLogic.galaxy
退出码：0 = 通过，1 = 发现问题。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HEAD = re.compile(
    r"^(void|bool|int|string|text|fixed|unit|point|playergroup|bank|trigger|unitgroup|"
    r"region|soundlink|color|timer|order)\s+\w+\s*\("
)
# 中段不一定是十六进制（autoCHRON30B_ae 等 178 种语义化中段）；排除 auto_gf_*/auto_gt_* 包装函数
AUTO = re.compile(r"\b(auto(?!_g[ft]_)\w+_\w+)\b")
LOCAL = re.compile(r"(?<![A-Za-z0-9_])(lv_[A-Za-z0-9_]+)")
# 声明行（用于确定声明区边界，与 role_block_extract.DECL_RE 同口径）
DECL_ANY = re.compile(r"(?:const\s+)?[A-Za-z][\w\[\]]*\s+\w+\s*(?:=|;)")

# ── 第 5 项（未声明标识符）用到的判据 ─────────────────────────────────────
STR_LIT = re.compile(r'"(?:\\.|[^"\\])*"')
IDENT = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_]\w*)")
FUNC_DEF = re.compile(r"^\s*(?:const\s+)?[A-Za-z][\w\[\]]*\s+(\w+)\s*\(")
GLOBAL_NAME = re.compile(r"\s(\w+)\s*(?:\[[^\]]*\])*\s*(?:=|;)")
# 一行声明里的名字：`<类型>[维度] <名字>[维度] [= 初值];`（Galaxy 一行只声明一个）
DECL_NAME = re.compile(r"^\s*(?:const\s+)?[A-Za-z][\w\[\]]*\s+(\w+)\s*(?:\[[^\]]*\])*\s*(?:=|;)")
# 库提供的常量/枚举（不在本文件声明）：c_* 引擎常量、libNtve_* 库枚举
LIB_PREFIXES = ("c_", "libNtve_")
# 关键字与类型 —— 出现在变量位置的它们不是「标识符」
KEYWORDS = set("""if else for while do return break continue true false null const static native
include struct enum void bool int string text fixed byte short unit point region playergroup unitgroup
bank trigger timer order soundlink color doodad actor""".split())
# 半截语句：语句以一个「标识符[索引]」开头、后面紧跟逗号 —— 合法语句里它只会作为实参出现，
# 出现在行首就说明这一行的前半截被切掉了（shw231 事故：脚本化删除删多了，留下
# `riantDescriptionItem[1], PlayerGroupAll(), 500, 50);`，全文大括号仍配平、函数外裸语句检查也过，
# 但游戏读脚本时报「解析函数行出错」⇒ 整个脚本读取失败）。
TRUNCATED = re.compile(r"^\s*[A-Za-z_]\w*(?:\[[^\]]*\])+\s*,")
# 行内 () 不配平：只有在「行尾也不是续行」时才算断行（长条件/长调用会跨行，行尾留 && || , + 等）
CONTINUATION = re.compile(r"(&&|\|\||,|\+|\-|\*|/|\(|\{|=|:|\?)\s*(//.*)?$")
# 全局 text/string 声明（用于检查转换函数误用）
DECL = re.compile(r"^(text|string)((?:\[[^\]]*\])*)\s+(\w+)\s*;", re.M)
# 转换函数：第一个参数期望的类型
CONV = {"StringToText": "string", "TextToString": "text"}
CONV_CALL = re.compile(r"\b(StringToText|TextToString)\s*\(\s*(\w+)")
# 第 3b 项（string 左值 ← 文本表达式）用到的判据。返回 text 的引擎/库函数：
# StringExternal/IntToText/FixedToText/TextWithColor/PlayerName 是原生，StringToText 是 string→text 的转换。
# PlayerHandle 返回的是 string（不在表里）。
TEXT_FUNCS = ("StringExternal", "StringToText", "IntToText", "FixedToText", "TextWithColor", "PlayerName")
TEXT_CALL = re.compile(r"\b(" + "|".join(TEXT_FUNCS) + r")\s*\(")
DECL_STR = re.compile(r"^\s*(?:const\s+)?(string|text)(?:\[[^\]]*\])*\s+(\w+)\s*(?:\[[^\]]*\])*\s*(?:=|;)")
ASSIGN_ONE = re.compile(r"^\s*([A-Za-z_]\w*)(?:\[[^\]]*\])*\s*=\s*(.+?);\s*$")

TYPES = (r"void|bool|int|string|text|fixed|unit|point|region|playergroup|unitgroup|"
         r"bank|trigger|timer|order|soundlink|color|doodad|actor")
# 函数外的合法行：全局变量声明 / 前向声明 / include
# 声明形如 `<类型>[可带维度] <名字>[可带维度] [= 初值];`（调用语句长得不像：标识符后紧跟 `(`）
GLOBAL_DECL = re.compile(
    r"^(?:const\s+)?[A-Za-z_]\w*(?:\[[^\]]*\])*\s+[A-Za-z_]\w*(?:\[[^\]]*\])*\s*(?:=.*)?;\s*$")
FORWARD = re.compile(rf"^(?:{TYPES})\s+\w+\s*\([^;]*\)\s*;\s*$")
INCLUDE = re.compile(r'^\s*include\s+"')


def strip_comment(s: str) -> str:
    """去掉行尾 // 注释（引号内的 `//` 不算注释 —— 脚本里有内联字符串）。"""
    i = s.find("//")
    while i != -1:
        if s[:i].count('"') % 2 == 0:
            return s[:i]
        i = s.find("//", i + 2)
    return s


def func_ranges(lines: list[str]):
    """产出每个函数定义的 (签名行, 闭合大括号行)。

    原型行（以 `;` 结尾、无花括号）必须跳过 —— 否则深度永远不归零，范围会一直
    吞到下一个真函数的结尾：既让该函数漏检，又在错的范围里报假问题（shw239：
    `void gf_SKF_5_shentou (...);` 原型把旁边原型签名里的 lv_source/lv_target
    当成了未声明变量）。
    """
    i = 0
    while i < len(lines):
        line = lines[i]
        code = strip_comment(line).rstrip()
        if not (HEAD.match(line) and not line.startswith(" ")) or code.endswith(";"):
            i += 1
            continue

        j = i
        while j < len(lines) and "{" not in strip_comment(lines[j]):
            j += 1
        if j >= len(lines):
            break

        depth, k = 0, j
        while k < len(lines):
            depth += lines[k].count("{") - lines[k].count("}")
            if depth == 0:
                break
            k += 1

        yield i, k
        i = k + 1


def lint(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    problems = 0

    balance = text.count("{") - text.count("}")
    if balance:
        print(f"✗ 大括号配平 {balance:+d}（应为 0）")
        problems += 1
    else:
        print("✓ 大括号配平 0")

    # text/string 转换误用：text 变量套 StringToText、string 变量套 TextToString
    types = {}
    for m in DECL.finditer(text):
        for _ in range(m.group(2).count("[")):
            pass
        types[m.group(3)] = m.group(1)
    conv_bad = 0
    for m in CONV_CALL.finditer(text):
        fn, ident = m.group(1), m.group(2)
        want = CONV[fn]
        got = types.get(ident)
        if got and got != want:
            ln = text[:m.start()].count("\n") + 1
            print(f"✗ {ln:6} {fn}({ident}...) 参数需 {want}，但 {ident} 声明为 {got}")
            conv_bad += 1
    if conv_bad:
        problems += conv_bad
    else:
        print("✓ text/string 转换无类型误用")

    # string 左值 ← 文本表达式（shw254b 事故，**实测会编译失败**）：
    # `lv_name = StringExternal("Param/Value/KEY") + IntToString(n);` ⇒
    # 「不正确的类型（不允许进行隐式强制转换）」→「脚本读取失败」，整张图界面全废。
    # 原因：Galaxy 只允许 string → text 的**隐式**转换（StringToText 是把它写成显式时的函数），
    # 反方向 **没有任何函数可转**（引擎 2944 个原生/库函数里「ret=string 且收 text 参数」的 = 0 个；
    # 社区常写的 TextToString 在本版本并不存在）⇒ 拼出来的 text 永远进不了 string 变量。
    # 修法只有两条：① 目标变量改用 text ② 别拿文本函数拼（要数字就 IntToString 拼纯 string）。
    ranges = list(func_ranges(lines))
    global_types: dict[str, str] = {}
    for m in DECL_STR.finditer(text):
        ln = text[:m.start()].count("\n")
        if not any(s <= ln <= e for s, e in ranges):
            global_types[m.group(2)] = m.group(1)

    ts_bad = 0
    for start, end in ranges:
        local: dict[str, str] = {}
        for idx in range(start, end + 1):
            m = DECL_STR.match(strip_comment(lines[idx]))
            if m:
                local.setdefault(m.group(2), m.group(1))

        for idx in range(start, end + 1):
            m = ASSIGN_ONE.match(strip_comment(lines[idx]))
            if not m:
                continue

            name, rhs = m.group(1), m.group(2)
            if (local.get(name) or global_types.get(name)) != "string":
                continue

            hit = TEXT_CALL.search(rhs)
            if hit:
                print(f"✗ {idx + 1:6} {name} 声明为 string，右边却是 {hit.group(1)}(…) 的文本表达式"
                      f"（Galaxy 无 text → string 转换）: {rhs[:80]}")
                ts_bad += 1

    if ts_bad:
        problems += ts_bad
    else:
        print("✓ 无「string 变量 ← 文本表达式」的编译错误")

    # 函数外裸语句（语句飘到 `}` 之后 → 游戏内「脚本读取失败: 语法错误」，shw218 事故）
    depth = 0
    stray: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        code = line.split("//")[0].rstrip()
        stripped = code.strip()
        if depth == 0 and stripped and stripped not in ("{", "}") \
                and not HEAD.match(line) and not INCLUDE.match(code) \
                and not GLOBAL_DECL.match(stripped) and not FORWARD.match(stripped):
            stray.append((idx + 1, stripped[:100]))
        depth += code.count("{") - code.count("}")
    if stray:
        for ln, txt in stray[:20]:
            print(f"✗ {ln:6} 函数外的语句: {txt}")
        problems += len(stray)
    else:
        print("✓ 无函数外裸语句")

    # 半截语句（shw231 事故）：语句以「标识符[索引]」开头且紧跟逗号
    truncated: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        code = line.split("//")[0]
        if TRUNCATED.match(code):
            truncated.append((idx + 1, code.strip()[:100]))
    if truncated:
        for ln, txt in truncated[:20]:
            print(f"✗ {ln:6} 半截语句（行首是『名字[索引],』）: {txt}")
        problems += len(truncated)
    else:
        print("✓ 无半截语句")

    # 行内 () 不配平且行尾不是续行（判据同 AGENTS.md 铁律 2b）
    broken: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        code = strip_comment(line).rstrip()
        if not code.strip() or CONTINUATION.search(code):
            continue
        if code.count("(") != code.count(")"):
            broken.append((idx + 1, code.strip()[:100]))
    if broken:
        for ln, txt in broken[:20]:
            print(f"✗ {ln:6} 行内 () 不配平且非续行: {txt}")
        problems += len(broken)
    else:
        print("✓ 行内 () 均配平")

    # 文件作用域的名字表（第 5 项用）：函数名 + 全局变量/常量/触发器声明。
    # 注意必须先剥注释 —— 本工程的全局声明普遍带行尾注释
    # （`int[16] gv_txStrikes; // 天选者(3/32) 剩余雷击次数`），不剥就会漏掉整批。
    known_funcs: set[str] = set()
    known_globals: set[str] = set()
    depth = 0
    for line in lines:
        code = strip_comment(line)
        if depth == 0:
            m = FUNC_DEF.match(code)
            if m:
                known_funcs.add(m.group(1))
            if GLOBAL_DECL.match(code):
                g = GLOBAL_NAME.search(code)
                if g:
                    known_globals.add(g.group(1))
        depth += code.count("{") - code.count("}")

    checked = 0
    missing_glob: list[tuple[int, str, list[str]]] = []
    for start, end in func_ranges(lines):
        body_lines = lines[start:end + 1]
        body = "\n".join(body_lines)

        # 声明区 = 函数体开头连续的「空行/注释/声明」；第一条真语句之前的一切。
        # （旧判据靠 "// Implementation" 标记切分 —— 自加函数没有该标记时会把整个函数体
        #   当成声明区 ⇒ 检查恒过。shw239 事故：抽出的函数用了未声明的 autoXXXX_n 没被拦住。）
        sig = body_lines[0]
        params = set(re.findall(r"\b(\w+)\s*(?=,|\))", sig[sig.find("(") + 1:]))
        decl_lines, k = [], 1
        while k < len(body_lines):
            t = strip_comment(body_lines[k]).strip()
            if not t or t.startswith("//") or DECL_ANY.match(t):
                decl_lines.append(body_lines[k])
                k += 1
                continue
            break
        decl = "\n".join(decl_lines)

        # 声明区里的**所有**声明名（不限 lv_/auto 两个族）——第 5 项要用
        decl_names = {m.group(1) for m in
                      (DECL_NAME.match(STR_LIT.sub('""', strip_comment(x))) for x in decl_lines) if m}

        used = set(AUTO.findall(body)) | set(LOCAL.findall(body))
        declared = set(AUTO.findall(decl)) | set(LOCAL.findall(decl))
        miss = sorted(used - declared - params)

        name = re.search(r"\b(\w+)\s*\(", lines[start]).group(1)
        checked += 1
        if miss:
            print(f"✗ {start + 1:6} {name}: 缺变量声明 {miss}")
            problems += 1

        # ── 第 5 项：未声明标识符（与名字族无关的硬校验）────────────────────
        # 前四项都建立在「名字族正则」上，而正则一旦写窄就与代码同源同错（shw239/240
        # 连续两次漏掉 auto 声明的教训）。这里不依赖任何族：把函数体里**出现在变量位置**
        # 的标识符（后面不接 `(` 的，即不是函数调用）减去「本函数声明 + 参数 + 文件作用域
        # 名字 + 关键字/类型 + 库常量前缀」，剩下的就是编译器会拒收的名字。
        clean_body = [STR_LIT.sub('""', strip_comment(x)) for x in body_lines[k:]]
        unknown = []
        for ln, text in zip(range(start + k + 1, end + 2), clean_body):
            for m in IDENT.finditer(text):
                n = m.group(1)
                if text[m.end():].lstrip()[:1] == "(":
                    continue                                   # 函数调用
                if n in KEYWORDS or n in params or n in declared or n in decl_names:
                    continue
                if n in known_globals or n in known_funcs:
                    continue
                if n.startswith(LIB_PREFIXES):
                    continue                                   # c_* / libNtve_* 库常量枚举
                if n not in unknown:
                    unknown.append(n)
        if unknown:
            missing_glob.append((start + 1, name, unknown))

    if missing_glob:
        for line_no, name, names in missing_glob:
            print(f"✗ {line_no:6} {name}: 未声明标识符 {names[:6]}")
        problems += len(missing_glob)
    else:
        print("✓ 无未声明标识符")

    # ── 第 6 项：重复函数定义（shw243 事故）────────────────────────────────
    # 抽取器按「家族标签 + 池 + 角色」生成函数名，标签撞车就会生成同名不同签名的两个
    # 函数（点击族的 B = gt_ASActionButtonBTown_Func，夜间 Bullshit 族也曾用 B）——
    # 游戏内是「重复定义」编译错误，而前五项全都查不出来（每处单独看都合法）。
    seen_defs: dict[str, list[int]] = {}
    for start, end in func_ranges(lines):
        nm = re.search(r"\b(\w+)\s*\(", lines[start])
        if nm:
            seen_defs.setdefault(nm.group(1), []).append(start + 1)
    dup = {k: v for k, v in seen_defs.items() if len(v) > 1}
    if dup:
        for k, v in sorted(dup.items()):
            print(f"✗ 函数 {k} 被定义了 {len(v)} 次，行 {v}")
        problems += len(dup)
    else:
        print("✓ 无重复函数定义")

    # ── 第 7 项：先调用后定义、且没有前向声明（2026-10-23 事故）──────────────
    # Galaxy 单遍顺序解析：函数必须在**调用点之前**出现过（定义或 `void f ();` 前向声明），
    # 否则引擎报「解析函数行出错，可能有无效的变量名/函数调用，或是函数结尾缺失」并
    # **整个脚本读取失败**（地图进不去）。前六项都查不出这类问题 —— 每处单独看都合法。
    TYPES = (r"(?:void|bool|int|fixed|string|text|unit|point|timer|trigger|region|"
             r"playergroup|actor|soundlink|color|gamelink|wave|unitgroup|doodad|doodadgroup)")
    defs: dict[str, int] = {}
    decls: dict[str, int] = {}
    code_lines: list[str] = []
    for i, line in enumerate(lines):
        code = strip_comment(line)
        code_lines.append(code)
        m = re.match(rf"^{TYPES}\s+(\w+)\s*\(", code)
        if not m:
            continue
        name = m.group(1)
        if code.rstrip().endswith(";"):
            decls.setdefault(name, i + 1)
        else:
            defs.setdefault(name, i + 1)

    CALL_KEYWORDS = {"if", "for", "while", "return", "else", "switch", "do", "break", "continue"}
    early: list[tuple[int, str, int, int | None]] = []
    for i, code in enumerate(code_lines):
        if re.match(rf"^{TYPES}\s+\w+\s*\(", code):
            continue
        for m in re.finditer(r"\b(\w+)\s*\(", code):
            name = m.group(1)
            if name in CALL_KEYWORDS or name not in defs or defs[name] < i + 1:
                continue
            decl = decls.get(name)
            if decl is not None and decl < i + 1:
                continue
            early.append((i + 1, name, defs[name], decl))

    if early:
        for line_no, name, d, decl in early[:10]:
            print(f"✗ 行 {line_no} 调用了后定义的 {name}()（定义在 {d}，前向声明 "
                  f"{'无' if decl is None else decl}）")
        problems += len(early)
    else:
        print("✓ 无「先调用后定义且无前向声明」")

    print(f"{'✓' if not problems else '✗'} 扫描函数 {checked} 个，问题 {problems} 处")
    return 1 if problems else 0


def main() -> int:
    default = Path(__file__).resolve().parent.parent / "work" / "blackhand" / "CustomLogic.galaxy"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not path.exists():
        print(f"找不到 {path}")
        return 1

    print(f"=== {path} ===")
    return lint(path)


if __name__ == "__main__":
    sys.exit(main())
