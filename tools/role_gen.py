#!/usr/bin/env python3
"""角色登记表生成器 / 校验器：把「加一个角色要碰的那些封闭位置」收成 spec + 机器校验。

## 它解决什么

「加一个角色要改几十处」里约 70% 是**机械同构登记**（记忆 764 的 11 步流程）。漏一处的
症状各不相同且都很隐蔽：漏上界 ⇒ 角色永远发不到；漏图鉴犯罪 ⇒ 界面显示原始键；
漏审查页偏移 ⇒ 审查员猜出别的角色（用户实测过：选中立·爱人狂 → 播报「审讯」）。
本工具把这些**封闭、位置固定**的位置变成「一份 spec + 一台校验器」，并接进打包门。

**不做**的部分（角色间交互、夜间结算、行动面板、判胜条件）留在手写侧；但 spec 必须
逐条回答记忆 792 的四项硬约束（交换干扰 / 调查 / 限制 / 审查员可猜），校验器会核对
其中的机械部分。

## 四类检查

1. **上界族**：8 处「循环/校验上界」必须 ≥ 脚本里实际存在的最大角色号（shw115/149 事故类型）。
2. **定义块**：名称 / 描述 / 探员线索 / 图鉴犯罪 / 开关四件套（Exists·Important·默认值·文案）
   必须逐行存在且与该池的登记一致。
3. **拼音**：`gv_roleNameInput` 必须存在（审查员 `-role` 与身份选择栏只认拼音）。
4. **审查页**：列表由 `gf_ASGuessRole` 逐下标驱动、空名跳过 ⇒ 对每个项号，
   把下标 1..上界 跑一遍得到的角色序列，必须**正好等于该池有名字的角色**（升序、不漏不重）。
   这条正是 shw205/216/217 那类 bug 的机器版。

用法：
    python3 tools/role_gen.py                # 校验（退出码 1 = 有漂移）
    python3 tools/role_gen.py --bounds       # 只跑上界族
    python3 tools/role_gen.py --inventory    # 打印每个角色登记到哪些位置
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "work" / "blackhand" / "CustomLogic.galaxy"
SPECS = ROOT / "roles"

POOL_CN = {1: "城镇", 2: "黑手D", 3: "中立", 4: "随机", 5: "三合会"}

# 上界族两类判据：
# 上界族：这些「循环 / 校验上界」里的**最大值**必须 ≥ 脚本里实际存在的最大角色号。
# 漏一处 = 该角色的几率/拼音/槽位/帮助面板静默失效（shw115、shw149 的事故类型）。
# 判据取「函数内最大值」而不是逐个比：这些函数里同时有池循环（上界 1..5）与角色循环
# （上界 1..max），逐个比会把池循环误判成漏（首版实测 16 处误报）。
BOUND_EXPLICIT = [
    ("gf_OSGenerateChances", r"auto\w+_ae = (\d+);", "几率清零/计数/归一化（取最大上界）"),
    ("gf_VLoadSaveSlot", r"\(lv_x\[lv_a\]\[0\] > (\d+)\)", "预设槽位加载校验"),
    ("gf_MakeHelpMenu", r"lv_role = (\d+);", "帮助面板角色遍历"),
    # 审查员 -role：角色循环里两层都用变量索引（gv_roleNameInput[lv_a][lv_b]）⇒ 取最大上界比
    ("gt_ASSearcherGuess_Func", r"auto\w+_ae = (\d+);", "审查员 -role 拼音匹配（取最大上界）"),
]
# 审查页列表**有意排除**的角色（不是漏登记）
PINYIN_FUNC = "gf_InitializeOther"   # gv_roleNameInput 登记所在函数
REVIEW_EXCLUDE = {
    (1, 30): "史官：原图未完成占位（只有名字/拼音/权重 0、无夜间逻辑），shw216 起从审查页列表移除",
}


# 角色相关的「文案键」变量：登记行 + 角色卡（缺键的症状 = 界面直接显示 Param/Value/KEY；
# 天选者 TXBOX4 就漏过一版）。拼音表不在此列（它是拼音、不是文本键）。
ROLE_STR_VARS = {
    "gv_roleNameArray": "角色名",
    "gv_roleDescriptionArray": "角色描述",
    "gv_roleInvestigatorArray": "探员线索",
    "gv_e78AAFE7BDAAE58FAFE883BD": "图鉴犯罪",
    "gv_roleOptionsText": "开关文案",
    "gv_roleBoxText": "角色卡",
}
GAME_STRINGS = "zhCN.SC2Data/LocalizedData/GameStrings.txt"


def load_gamestrings():
    """打包第 ⑦ 件的同序合并：自加 strings-*.txt 优先，基线 zhCN 兜底。"""
    import glob

    import sc2map

    gs = {}
    base = ROOT / "work" / "boot2-user.SC2Map"
    if base.exists():
        try:
            raw = sc2map.read(base, GAME_STRINGS).decode("utf-8", errors="replace")
            for line in raw.split("\n"):
                if "=" in line and not line.startswith("//"):
                    k, v = line.split("=", 1)
                    gs.setdefault(k.strip(), v.strip())
        except Exception as exc:
            print(f"    ! 基线 zhCN 读取失败（{exc}），只查自加文案")
    for f in sorted(glob.glob(str(ROOT / "work" / "blackhand" / "strings-*.txt"))):
        for line in Path(f).read_text(encoding="utf-8").split("\n"):
            if "=" in line and not line.startswith("//"):
                k, v = line.split("=", 1)
                gs[k.strip()] = v.strip()
    return gs


def func_span(lines, name):
    for i, l in enumerate(lines):
        if re.match(rf"^\w+ {name} \(", l) and l.rstrip().endswith("{"):
            depth = 0
            for j in range(i, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth == 0:
                    return i, j
    return None


class Script:
    def __init__(self, path=SCRIPT):
        self.lines = path.read_text(encoding="utf-8").split("\n")

    def body(self, name):
        s = func_span(self.lines, name)
        if s is None:
            sys.exit(f"✗ 找不到函数 {name}")
        return self.lines[s[0]:s[1] + 1]

    # ---------- 事实抽取 ----------

    def named_roles(self):
        """{(池, 角色)}：在 gf_InitializeVariables 里有显示名的角色。"""
        out = set()
        for l in self.body("gf_InitializeVariables"):
            m = re.match(r"\s*gv_roleNameArray\[(\d+)\]\[(\d+)\] = StringExternal", l)
            if m:
                out.add((int(m.group(1)), int(m.group(2))))
        return out

    def pinyin_map(self):
        out = {}
        for l in self.lines:
            m = re.match(r'\s*gv_roleNameInput\[(\d+)\]\[(\d+)\] = "([a-z0-9_]+)";', l)
            if m:
                out[(int(m.group(1)), int(m.group(2)))] = m.group(3)
        return out

    def def_block(self, pool, role):
        """该角色的定义行（名称/描述/图鉴/开关四件套…）。

        两处坑（都实测踩过）：
        ① **不能子串匹配** `[1][1]` —— 它会命中 `[8][1][1]`（别池同号角色的行），
           首版因此把别角色的探员线索算进来了；必须要求 `]` 后面是 `[` / 空格 / `=`。
        ② **开关默认值不在定义区** —— `gv_roleOptions[…] = true/false` 常常写在
           `gf_DefaultRoleOptions`（6012 起，晚于 gf_InitializeVariables 执行 ⇒ 后写生效），
           只扫定义区会读到错误默认值（市民 [0] 实际 true、首版导出成 false）。
        """
        # 锚在「变量名 + 池作第一个下标」：`\[1\]\[1\]` 这种写法会命中 `[8][1][1]`
        # 的尾部（别池同号角色），首版就是这么把别角色的探员线索算进来的
        # The default saved weight has an additional leading bank-slot index.
        # Match only slot 0 of this exact array; never relax the pool anchoring
        # (e.g. role 1/1 must still not read another pool's [...][1][1]).
        pat = re.compile(
            rf"(?:gv_\w+\[{pool}\]\[{role}\]|"
            rf"gv_bankSaveWeights\[0\]\[{pool}\]\[{role}\])(?=\[|\s|=)"
        )
        out = []
        for fn in ("gf_InitializeVariables", "gf_DefaultRoleOptions"):
            out += [l for l in self.body(fn) if pat.search(l) and l.strip()]
        return "\n".join(out)

    def guess_pool(self):
        """gf_ASGuessPool：项号 → 池号。写法是 `lv_pool = 1;` 打底 + if/else if 覆写。"""
        out, cur, default = {}, None, None
        for l in self.body("gf_ASGuessPool"):
            m = re.match(r"\s*(?:else )?if \(\(lp_picked == (\d+)\)\) \{", l)
            if m:
                cur = int(m.group(1))
                continue
            m = re.match(r"\s*lv_pool = (\d+);", l)
            if m:
                if cur is None:
                    default = int(m.group(1))
                else:
                    out[cur] = int(m.group(1))
        if default is not None:
            out[1] = default          # 项 1 = 打底值（无分支命中时）
        return out

    def guess_role(self):
        """解析 gf_ASGuessRole 成 {项号: [(下限, 上限, 动作)]} + 兜底 + 上限。

        动作 = ('+', K) 表示 lv_role = lp_index + K；('=', C) 表示 lv_role = C。
        用大括号深度区分「项号块」与「块内规则」。
        """
        rules, fallback, pending, cap = {}, [], None, None
        cur = None
        depth = 0
        for l in self.body("gf_ASGuessRole"):
            if depth == 1:
                m = re.match(r"\s*(?:else )?if \(\(lp_picked == (\d+)\)\) \{", l)
                if m:
                    cur = int(m.group(1))
                    rules.setdefault(cur, [])
                    depth += l.count("{") - l.count("}")
                    continue
                m = re.match(r"\s*else if \(\(lp_index >= (\d+)\)\) \{", l)
                if m:
                    cur, pending = None, (int(m.group(1)), 10 ** 9)
                else:
                    m = re.match(r"\s*if \(\(lv_role > (\d+)\)\) \{", l)
                    if m:
                        cap = int(m.group(1))
            elif depth == 2 and cur is not None:
                m = re.match(r"\s*if \(\(\(lp_index >= (\d+)\) && \(lp_index <= (\d+)\)\)\) \{", l)
                if m:
                    pending = (int(m.group(1)), int(m.group(2)))
                else:
                    m = re.match(r"\s*else if \(\(lp_index == (\d+)\)\) \{", l)
                    if m:
                        pending = (int(m.group(1)), int(m.group(1)))
                    else:
                        # 项号块里的第一条规则是裸 if（`if ((lp_index >= 18)) {`），
                        # 之后的才是 else if —— 两者都要认（首版只认 else if ⇒ 中立项的
                        # 「18/19 → 31/32」被漏掉，于是报出根本不存在的漂移）
                        m = re.match(r"\s*(?:else )?if \(\(lp_index >= (\d+)\)\) \{", l)
                        if m:
                            pending = (int(m.group(1)), 10 ** 9)
            elif depth in (2, 3) and pending is not None:
                m = re.match(r"\s*lv_role = \((\w+ \+ (\d+))\);", l)
                act = None
                if m:
                    act = ("+", int(m.group(2)))
                else:
                    m = re.match(r"\s*lv_role = (\d+);", l)
                    if m:
                        act = ("=", int(m.group(1)))
                if act:
                    (rules[cur] if cur is not None else fallback).append(pending + (act,))
                    pending = None
            depth += l.count("{") - l.count("}")
        return rules, fallback, cap

    def review_bounds(self):
        """审查页列表构建：{下拉项号: 遍历上界}。"""
        body = self.body("gf_ASE5AEA1E69FA5E98089E9A1B92")
        decl = {}
        for l in body:
            m = re.match(r"\s*const int (auto\w+_ae) = (\d+);", l)
            if m:
                decl[m.group(1)] = int(m.group(2))
        out, cur = {}, None
        for l in body:
            m = re.match(r"\s*if \(\(lp_picked == (\d+)\)\) \{", l)
            if m:
                cur = int(m.group(1))
                continue
            m = re.search(r"lv_ii <= (auto\w+_ae)", l)
            if m and cur:
                out[cur] = decl.get(m.group(1))
        return out


def dump_spec(sc, pool, role, pinyins):
    """从脚本反向导出 spec 骨架：所有机械字段自动填，交互矩阵留空等人回答。"""
    block = sc.def_block(pool, role)
    spec = {"pool": pool, "role": role, "pinyin": pinyins.get((pool, role), ""), "cn": "",
            "name_key": "", "desc_key": "", "investigator": [], "crime_key": None,
            "options": [], "flag10": False,
            "guessable": None, "help_preview": None,
            "interactions": {"swap": {"text": ""}, "investigate": {"text": ""},
                             "restrict": {"text": ""}, "guessage": {"text": "", "in_guess_list": None}},
            "note": "机械字段由 tools/role_gen.py --dump 导出；四项交互必须人工逐条回答（记忆 792）"}
    for l in block.split("\n"):
        if (m := re.search(r'gv_roleNameArray\[\d+\]\[\d+\] = StringExternal\("Param/Value/(\w+)"\)', l)):
            spec["name_key"] = m.group(1)
        elif (m := re.search(r'gv_roleDescriptionArray\[\d+\]\[\d+\] = StringExternal\("Param/Value/(\w+)"\)', l)):
            spec["desc_key"] = m.group(1)
        elif (m := re.search(r'gv_roleInvestigatorArray\[\d+\]\[\d+\]\[\d+\] = gv_investigator(\w+)', l)):
            spec["investigator"].append(m.group(1))
        elif (m := re.search(r'gv_e78AAFE7BDAAE58FAFE883BD\[\d+\]\[\d+\] = StringExternal\("Param/Value/(\w+)"\)', l)):
            spec["crime_key"] = m.group(1)
        elif (m := re.search(r'gv_roleOptions\[\d+\]\[\d+\]\[(\d+)\] = true;', l)) and m.group(1) == "10":
            spec["flag10"] = True
    # 开关：原图每个开关未必四行齐全（有的没有 Exists、有的无 Important）⇒
    # 字段「有就记、没有就 null」，校验器只对非 null 的字段要求对应行存在（首版一律
    # 默认 important=2 / default=false，导出后自己报出一堆并不存在的缺项）
    opts = {}
    for l in block.split("\n"):
        m = re.search(r'gv_roleOptions(?:Important|Exists|Text)?\[\d+\]\[\d+\]\[(\d+)\]', l)
        if m and m.group(1) != "10":
            opts.setdefault(int(m.group(1)),
                            {"i": int(m.group(1)), "exists": None, "important": None,
                             "default": None, "key": None})
    for l in block.split("\n"):
        if (m := re.search(r'gv_roleOptionExists\[\d+\]\[\d+\]\[(\d+)\] = (true|false);', l)):
            opts[int(m.group(1))]["exists"] = m.group(2) == "true"
        elif (m := re.search(r'gv_roleOptionsImportant\[\d+\]\[\d+\]\[(\d+)\] = (\d+);', l)):
            opts[int(m.group(1))]["important"] = int(m.group(2))
        elif (m := re.search(r'gv_roleOptions\[\d+\]\[\d+\]\[(\d+)\] = (true|false);', l)) and m.group(1) != "10":
            opts[int(m.group(1))]["default"] = m.group(2) == "true"
        elif (m := re.search(r'gv_roleOptionsText\[\d+\]\[\d+\]\[(\d+)\] = StringExternal\("Param/Value/(\w+)"\)', l)):
            opts[int(m.group(1))]["key"] = m.group(2)
    spec["options"] = [opts[k] for k in sorted(opts)]
    return spec


def _load_specs():
    return sorted((json.loads(p.read_text(encoding="utf-8")) for p in SPECS.glob("*.json")),
                  key=lambda s: (s["pool"], s["role"]))


def required_lines(spec, pinyins):
    """spec 要求该角色在定义区里必须出现的行（顺序即脚本惯例顺序）。"""
    pool, role = spec["pool"], spec["role"]
    out = [
        f'gv_roleNameArray[{pool}][{role}] = StringExternal("Param/Value/{spec["name_key"]}");',
        f'gv_roleDescriptionArray[{pool}][{role}] = StringExternal("Param/Value/{spec["desc_key"]}");',
    ]
    for i, k in enumerate(spec.get("investigator", [])):
        out.append(f"gv_roleInvestigatorArray[{pool}][{role}][{i}] = gv_investigator{k};")
    for opt in spec.get("options", []):
        i = opt["i"]
        if opt.get("exists"):
            out.append(f"gv_roleOptionExists[{pool}][{role}][{i}] = true;")
        if opt.get("important") is not None:
            out.append(f"gv_roleOptionsImportant[{pool}][{role}][{i}] = {opt['important']};")
        if opt.get("default") is not None:
            out.append(f"gv_roleOptions[{pool}][{role}][{i}] = {'true' if opt['default'] else 'false'};")
        if opt.get("key"):
            out.append(f'gv_roleOptionsText[{pool}][{role}][{i}] = StringExternal("Param/Value/{opt["key"]}");')
    if spec.get("flag10"):
        out.append(f"gv_roleOptions[{pool}][{role}][10] = true;")
    if spec.get("crime_key"):
        out.append(f'gv_e78AAFE7BDAAE58FAFE883BD[{pool}][{role}] = StringExternal("Param/Value/{spec["crime_key"]}");')
    out += [x for x in spec.get("extra_def_lines", []) if x.strip()]
    return out


def apply_specs(sc, specs):
    """把每个 spec 缺的登记行**追加在该池最后一条之后**（顺序无关、幂等）。

    安全性：插入点用「该池最后一条定义行的下一个行首」+ 缩进沿用该池既有缩进；
    落盘后自检 ①新增行数 == 缺行数 ②每条新行逐字节等于要求 ③该角色定义块完整性由
    调用方随后的 --check 复核（apply 不跳过检查，退出码即最终状态）。
    """
    lines, total_added, touched = sc.lines[:], 0, 0
    for spec in specs:
        pool, role = spec["pool"], spec["role"]
        pat = re.compile(rf"^\s*gv_\w+\[{pool}\]\[{role}\]")
        present = {l.strip() for l in lines if pat.match(l)}
        missing = [x for x in required_lines(spec, {}) if x not in present]
        if not missing:
            continue
        # 锚点必须限制在定义函数体内 —— 首版在全文件搜「池 3 的任意角色行」，
        # 结果插到了 20230 行的另一个函数里（校验器立刻报「未在定义区登记显示名」）
        fs, fe = func_span(lines, "gf_InitializeVariables")
        idx = [i for i in range(fs, fe + 1)
               if re.match(rf"^\s*gv_\w+\[{pool}\]\[\d+\]", lines[i])]
        if not idx:
            sys.exit(f"✗ 池 {pool} 在 gf_InitializeVariables 里没有任何定义行，拒绝插入")
        anchor = idx[-1]
        indent = re.match(r"^(\s*)", lines[anchor]).group(1)
        block = [indent + x for x in missing]
        lines[anchor + 1:anchor + 1] = block
        added = len(block)
        # 拼音单独插（它在同函数的另一段，且审查员 -role / 身份选择栏只认拼音）
        if f'gv_roleNameInput[{pool}][{role}]' not in "\n".join(lines):
            ps, pe = func_span(lines, PINYIN_FUNC)
            pidx = [i for i in range(ps, pe + 1)
                    if re.match(rf"^\s*gv_roleNameInput\[{pool}\]\[\d+\]", lines[i])]
            if pidx:
                pind = re.match(r"^(\s*)", lines[pidx[-1]]).group(1)
                lines[pidx[-1] + 1:pidx[-1] + 1] = [f'{pind}gv_roleNameInput[{pool}][{role}] = "{spec["pinyin"]}";']
                added += 1
        total_added += added
        touched += 1
        print(f"· {spec['cn']}({pool}/{role})：池 {pool} 末条定义（行 {anchor + 1}）后追加 {added} 行")
    if not total_added:
        print("✓ 没有需要补的登记行（全部已存在）")
        return 0
    SCRIPT.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ 共追加 {total_added} 行（涉及 {touched} 个角色）→ {SCRIPT.relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bounds", action="store_true")
    ap.add_argument("--inventory", action="store_true")
    ap.add_argument("--dump", metavar="池/角色")
    ap.add_argument("--apply", action="store_true", help="把 spec 缺的登记行补进 gf_InitializeVariables")
    args = ap.parse_args()

    sc = Script()
    if args.dump:
        pool, role = (int(x) for x in args.dump.split("/"))
        print(json.dumps(dump_spec(sc, pool, role, sc.pinyin_map()), ensure_ascii=False, indent=1))
        return 0
    named = sc.named_roles()
    pinyins = sc.pinyin_map()
    if args.apply:
        return apply_specs(sc, specs=_load_specs())
    specs = _load_specs()
    problems, warnings, pending = [], [], []

    print(f"脚本 {len(sc.lines)} 行；有名字的角色 {len(named)} 个；拼音 {len(pinyins)} 条；"
          f"spec {len(specs)} 份\n")

    # ---------- 1) 上界族 ----------
    maxrole = {}
    for p_, r_ in named:
        maxrole[p_] = max(maxrole.get(p_, 0), r_)
    gmax_script = max(maxrole.values())
    spec_roles = {(sp["pool"], sp["role"]) for sp in specs}
    gmax = max([gmax_script] + [r for (_, r) in spec_roles])
    extra = (f"；spec 声明到 {gmax}（脚本里最高 {gmax_script}）—— 先放宽下列上界再 --apply"
             if gmax > gmax_script else "")
    print(f"[1] 上界族（各池最大角色号 {dict(sorted(maxrole.items()))} ⇒ 全局 {gmax}）{extra}")
    for fn, pat, why in BOUND_EXPLICIT:
        hits = [int(m.group(1)) for l in sc.body(fn) for m in [re.search(pat, l)] if m]
        if not hits:
            problems.append(f"{fn}: 找不到上界（模式 {pat}）")
            continue
        if len(set(hits)) > 1:
            bad = [] if max(hits) >= gmax else sorted({h for h in hits if h < gmax})
        else:
            bad = sorted({h for h in hits if h < gmax})
        print(f"    {'✗' if bad else '✓'} {fn:26s} {len(hits)} 处 = {sorted(set(hits))} —— {why}")
        if bad:
            problems.append(f"{fn} 有 {len(bad)} 处上界 < {gmax}（{bad}）")

    # ---------- 1b) 文案键存在性（不需要 spec，覆盖全部角色）----------
    print("\n[1b] 文案键存在性（登记行 + 角色卡引用的 Param/Value/键 必须真的存在）")
    gs = load_gamestrings()
    sites, checked = {}, 0
    for i, l in enumerate(sc.lines, 1):
        vm = re.match(r"\s*(gv_\w+)\s*\[", l)
        if not vm or vm.group(1) not in ROLE_STR_VARS:
            continue
        km = re.search(r'StringExternal\("Param/Value/(\w+)"\)', l)
        if not km:
            continue
        checked += 1
        sites.setdefault(km.group(1), []).append((vm.group(1), i, l))

    def role_of(line, var):
        """字面下标的登记行 → (池, 角色)；角色卡是 lv_a ⇒ 靠上方最近的角色条件定位。"""
        idx = re.match(rf"\s*{var}\[(\d+)\]\[(\d+)\]", line)
        if idx:
            return (int(idx.group(1)), int(idx.group(2)))
        return None

    fatal, stale = [], []
    for key, where in sorted(sites.items()):
        if f"Param/Value/{key}" in gs or key in gs:
            continue
        living = any(r in named for r in (role_of(l, v) for v, _, l in where) if r)
        tag = f"{ROLE_STR_VARS[where[0][0]]}键 {key} 缺文案（{len(where)} 处，首见行 {where[0][1]}）"
        (fatal if living else stale).append(tag)
    print(f"    检查 {checked} 处引用 / {len(sites)} 个不同键 ⇒ "
          f"缺文案 {len(fatal) + len(stale)} 个（活角色 {len(fatal)} / 遗留 {len(stale)}）")
    for x in fatal:
        print(f"    ✗ {x}")
    for x in stale[:6]:
        print(f"    · {x}")
    if len(stale) > 6:
        print(f"    · …另有 {len(stale) - 6} 个遗留角色键缺文案（原图未启用角色，不拦打包）")
    problems += fatal

    # ---------- 1c) 夜间镜头组覆盖（不需要 spec）----------
    print("\n[1c] 夜间镜头组覆盖（gt_NPNightCamera_Func 的分发块）")
    cam_fn = None
    for l in sc.lines:
        if re.match(r"^\w+ gt_NPNightCamera_Func \(", l):
            cam_fn = "gt_NPNightCamera_Func"
    if not cam_fn:
        print("    · 找不到 gt_NPNightCamera_Func（机制改名了？）")
    else:
        cs, ce = func_span(sc.lines, cam_fn)
        body = "\n".join(sc.lines[cs:ce + 1])
        covered = {int(x) for x in re.findall(r"gv_roles\[lv_a\]\[0\] == (\d+)", body)}
        groups = sorted(set(re.findall(r"(gf_NP\w+Camera)\(", body)))
        missing = sorted(r for (p_, r) in named if p_ == 1 and r not in covered) + \
                  sorted(r for (p_, r) in named if p_ == 3 and r not in covered)
        spec_roles = {(sp["pool"], sp["role"]) for sp in specs}
        fatal_missing = [f"{p_}/{r}" for (p_, r) in sorted(spec_roles) if r not in covered]
        print(f"    分发块 行 {cs + 1}-{ce + 1}：覆盖 {len(covered)} 个角色号、{len(groups)} 个机位")
        print(f"    有显示名但没镜头的角色（池1/池3）：{len(missing)} 个 {missing}")
        if fatal_missing:
            print(f"    ✗ spec 里登记的角色却没镜头组：{fatal_missing}"
                  f"（不在表中 = 该角色夜间没有专属循环镜头，且不会报错）")
            problems += [f"{x} 缺夜间镜头组（记忆 765）" for x in fatal_missing]

    # ---------- 1d) 死因字母码（不需要 spec）----------
    print("\n[1d] 死因字母码（赋值点 vs 验尸官扫描分支）")
    # 原图自用的「类别码」：这些码表示一整类死法，验尸官故意不为它们写分支
    CODE_WHITELIST = {"h": "黑手D/三合会一类通用夜间死法（7 处击杀路径共用），验尸官无分支属原图设计"}
    assigned = {m.group(1) for l in sc.lines
                for m in [re.search(r'gv_deathMethod\[\w+\] = \(gv_deathMethod\[\w+\] \+ "([^"]+)"\)', l)] if m}
    scanned = {m.group(1) for l in sc.lines
               for m in [re.search(r'StringSub\(gv_deathMethod\[.+?\], lv_b, lv_b\) == "([^"]+)"', l)] if m}
    occupied = sorted(assigned | scanned)
    print(f"    已占用（赋值 ∪ 扫描）{len(occupied)} 个：{occupied}")
    print(f"    ⚠ 新角色选码必须避开上面这组（记忆 771 的占用表由此机器维护）")
    orphan = sorted(assigned - scanned - set(CODE_WHITELIST))
    unused = sorted(scanned - assigned)
    for k, why in sorted(CODE_WHITELIST.items()):
        if k in assigned - scanned:
            print(f"    · 白名单码 {k}：{why}")
    if unused:
        print(f"    · 有扫描分支但当前无人赋值（原图遗留）：{unused}")
    if orphan:
        print(f"    ✗ 赋值了但验尸官没有分支（该死因验尸官查不出）：{orphan}")
        problems += [f"死因码 {x} 无验尸官分支" for x in orphan]

    # ---------- 1e) 成就索引一致性（不需要 spec）----------
    # shw151 的教训：成就名有两处独立的名称链，漏一处就是「列表空白 / -achieve 播报 null」。
    #   列表链 = gt_Stats_Func（玩家查看成就列表）
    #   命令链 = gt_Achieve_Func（管理员 -achieve <玩家> <索引>）
    #   第三处 = 解锁写入点 gv_bankOtherAchievements[玩家][索引] = 1/2/3
    print("\n[1e] 成就索引一致性（列表链 / 命令链 / 解锁写入）")
    ACH_TOTAL = 81          # gv_bankOtherAchievements[16][81]（0..80）

    def chain_indices(fn_name):
        """名称链所在的自动变量 = 该函数里出现次数最多的 `X == 数字`，再取它的索引集合。"""
        try:
            s_, e_ = func_span(sc.lines, fn_name)
        except Exception:
            return None, set()
        seg = "\n".join(sc.lines[s_:e_ + 1])
        cnt = {}
        for name, _ in re.findall(r"(auto\w+|lv_\w+)\s*==\s*(\d+)", seg):
            cnt[name] = cnt.get(name, 0) + 1
        if not cnt:
            return None, set()
        var = max(cnt, key=lambda k: cnt[k])
        return var, {int(x) for x in re.findall(rf"{var}\s*==\s*(\d+)", seg)}

    list_var, list_idx = chain_indices("gt_Stats_Func")
    cmd_var, cmd_idx = chain_indices("gt_Achieve_Func")
    unlock = {int(m.group(1)) for m in re.finditer(
        r"gv_bankOtherAchievements\[\w+\]\[(\d+)\]\s*(?:=\s*[123]|\+=\s*1)", "\n".join(sc.lines))}

    # 已知差异（附原因，出现新的差异才会报警）
    ACH_WHITELIST = {
        "cmd_missing": {57, 58, 59, 60, 61, 62, 63, 64, 65},
        "no_name": set(),       # 24 百万之一已接入两条名称链；42 仍被过滤，但当前没有解锁写入
    }

    print(f"    列表链 gt_Stats_Func（{list_var}）：{len(list_idx)} 个索引")
    print(f"    命令链 gt_Achieve_Func（{cmd_var}）：{len(cmd_idx)} 个索引")
    print(f"    解锁写入点：{len(unlock)} 个索引")

    over = sorted(i for i in unlock if i >= ACH_TOTAL)
    if over:
        print(f"    ✗ 解锁写入的索引越界（数组只有 {ACH_TOTAL} 位）：{over}")
        problems += [f"成就索引 {i} 越界（≥{ACH_TOTAL}）" for i in over]

    extra_cmd = sorted(cmd_idx - list_idx)
    if extra_cmd:
        print(f"    ✗ 命令链有、列表链没有（列表里会空白）：{extra_cmd}")
        problems += [f"成就索引 {i} 命令链有名称、列表链没有" for i in extra_cmd]

    miss_cmd = sorted(set(list_idx) - set(cmd_idx) - ACH_WHITELIST["cmd_missing"])
    if miss_cmd:
        print(f"    ✗ 列表链有、命令链没有（-achieve 播报会是 null）：{miss_cmd}")
        problems += [f"成就索引 {i} 缺 -achieve 名称链条目" for i in miss_cmd]

    noname = sorted(unlock - list_idx - cmd_idx - ACH_WHITELIST["no_name"])
    if noname:
        print(f"    ✗ 能被解锁、但两条链里都没有名字的索引：{noname}")
        problems += [f"成就索引 {i} 可解锁却无名称（列表空白 / 命令 null）" for i in noname]

    if not (over or extra_cmd or miss_cmd or noname):
        print(f"    ✓ 三处一致（白名单：命令链不支持 {sorted(ACH_WHITELIST['cmd_missing'])}、"
              f"设计上不显示的 {sorted(ACH_WHITELIST['no_name'])}）")
        print(f"    · 名称键本体由打包回读 MUST_HAVE_KEYS 兜底；索引上限 {ACH_TOTAL}")

    # ---------- 2) 审查页：列表必须 == 该池有名字的角色 ----------
    print("\n[2] 审查页（gf_ASGuessRole 与列表构建的一致性）")
    pool_item, rules, fb, cap = sc.guess_pool(), *sc.guess_role()
    bounds = sc.review_bounds()

    def guess(item, idx):
        # 兜底规则与项号块是同一条 if/else-if 链：只有**没有专属块**的项（黑手D/三合会）
        # 才会走到兜底（首版无条件拼接 ⇒ 城镇/中立被多套了一次 +2/+13，报出假的漂移）
        for lo, hi, act in (rules.get(item) or fb):
            if lo <= idx <= hi:
                return idx + act[1] if act[0] == "+" else act[1]
        return idx

    if cap is None:
        problems.append("gf_ASGuessRole: 找不到 lv_role 上限钳制")
    listed = {}          # 项号 → 该项列表里的角色号集合（供 spec 反向核对）
    for item in sorted(bounds):
        pool = pool_item.get(item)
        if pool is None:
            problems.append(f"审查页项号 {item} 在 gf_ASGuessPool 里没有映射")
            continue
        got = [guess(item, i) for i in range(1, (bounds[item] or 0) + 1)]
        got = [r for r in got if r and (pool, r) in named]
        expect = sorted(r for (p, r) in named if p == pool and (p, r) not in REVIEW_EXCLUDE)
        listed[item] = set(got)
        flag = "✓" if got == expect else "✗"
        print(f"    {flag} 项{item}→{POOL_CN.get(pool, pool)}池 上界 {bounds[item]}：得到 {len(got)} 个角色"
              f"{'' if got == expect else f'，应为 {len(expect)} 个'}")
        if got != expect:
            miss = [r for r in expect if r not in got]
            extra = [r for r in got if r not in expect]
            problems.append(f"审查页项{item}（{POOL_CN.get(pool)}）角色序列不符：缺 {miss} / 多 {extra}"
                            f"；实际 {got}")

    # spec 里声明「可被猜出」的角色，必须真的出现在审查页列表里（否则审查员永远猜不到）
    for sp in specs:
        if not sp.get("guessable"):
            continue
        key = (sp["pool"], sp["role"])
        item = next((it for it, pl in sorted(pool_item.items()) if pl == key[0]), None)
        if item is None or key[1] not in listed.get(item, set()):
            problems.append(f"spec 声明 {key[0]}/{key[1]} 可被审查员猜出，"
                            f"但它不在审查页项{item}的列表里（gf_ASGuessRole 映射/上界没改）")

    # ---------- 3) spec：定义块 / 拼音 / 交互矩阵 ----------
    print(f"\n[3] spec 登记（{len(specs)} 份）")
    for spec in specs:
        pool, role, tag = spec["pool"], spec["role"], f"{spec['cn']}({spec['pool']}/{spec['role']})"
        block = sc.def_block(pool, role)
        miss = []
        if (pool, role) not in named:
            miss.append("未在定义区登记显示名")
        for key, want_line in [
            ("角色名", f'gv_roleNameArray[{pool}][{role}] = StringExternal("Param/Value/{spec["name_key"]}")'),
            ("角色描述", f'gv_roleDescriptionArray[{pool}][{role}] = StringExternal("Param/Value/{spec["desc_key"]}")'),
        ]:
            if want_line not in block:
                miss.append(key)
        for i, k in enumerate(spec.get("investigator", [])):
            if f"gv_roleInvestigatorArray[{pool}][{role}][{i}] = gv_investigator{k}" not in block:
                miss.append(f"探员线索[{i}]")
        if spec.get("crime_key") and \
                f'gv_e78AAFE7BDAAE58FAFE883BD[{pool}][{role}] = StringExternal("Param/Value/{spec["crime_key"]}")' not in block:
            miss.append("图鉴犯罪可能")
        for opt in spec.get("options", []):
            i = opt["i"]
            checks = []
            if opt.get("exists"):
                checks.append((f"开关[{i}].Exists", f"gv_roleOptionExists[{pool}][{role}][{i}] = true;"))
            if opt.get("important") is not None:
                checks.append((f"开关[{i}].Important",
                               f"gv_roleOptionsImportant[{pool}][{role}][{i}] = {opt['important']};"))
            if opt.get("default") is not None:
                d = "true" if opt["default"] else "false"
                checks.append((f"开关[{i}].默认值", f"gv_roleOptions[{pool}][{role}][{i}] = {d};"))
            if opt.get("key"):
                checks.append((f"开关[{i}].文案",
                               f'gv_roleOptionsText[{pool}][{role}][{i}] = StringExternal("Param/Value/{opt["key"]}")'))
            for what, line in checks:
                if line not in block:
                    miss.append(what)
        if spec.get("flag10") and f"gv_roleOptions[{pool}][{role}][10] = true;" not in block:
            miss.append("开关[10]（夜间无敌标志）")
        for extra in spec.get("extra_def_lines", []):
            if extra.strip() not in block:
                miss.append(f"额外定义行 {extra.strip()[:40]}")
        if pinyins.get((pool, role)) != spec["pinyin"]:
            miss.append(f'拼音（应为 gv_roleNameInput[{pool}][{role}] = "{spec["pinyin"]}"）')

        # 交互**不进 spec**（2026-09-13 用户定稿）：角色间交互是开放集合，新角色会带来
        # 新机制，写进声明只会过期 —— 交互一律以代码实现为准（清单见记忆 792）。
        # spec 只声明「封闭登记位置」，这里的 interactions 仅作设计笔记、不参与判定。
        # 仅剩一条「笔记与结构字段别自相矛盾」的检查（笔记说能猜、结构字段填不能猜）
        inter = spec.get("interactions", {})
        if inter.get("guessage", {}).get("in_guess_list") and not spec.get("guessable"):
            miss.append('写了对审查页可猜但没设 "guessable": true')

        note = []
        if spec.get("interactions"):
            note.append("含交互笔记（不参与判定）")
        print(f"    {'✓' if not miss else '✗'} {tag:16s} {'已登记' if not miss else '缺 ' + str(miss)}"
              f"{'　' + '，'.join(note) if note else ''}")
        if miss:
            problems.append(f"{tag} 登记不全：{miss}")

    # ---------- 4) inventory ----------
    if args.inventory:
        print("\n[4] 清点：每个角色登记到哪些位置")
        for spec in specs:
            pool, role = spec["pool"], spec["role"]
            print(f"    {spec['cn']}({pool}/{role}) 定义块 {len(sc.def_block(pool, role).splitlines())} 行"
                  f"；拼音 {pinyins.get((pool, role), '—')}；审查页 "
                  f"{'在' if (pool, role) in named else '不在'}")

    print(f"\n· 上两项（上界族 / 审查页自洽）**不需要 spec**，覆盖脚本里全部角色；"
          f"下面这 {len(specs)} 份 spec 只声明「封闭登记位置」，按需维护（加/改角色时写一份）")
    print()
    if problems:
        print(f"✗ 共 {len(problems)} 处问题：")
        for x in problems:
            print("    " + x)
        return 1
    print(f"✓ 全部检查通过（上界族+审查页自洽；spec {len(specs)} 份）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
