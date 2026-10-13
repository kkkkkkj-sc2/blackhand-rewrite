#!/usr/bin/env python3
"""预设生成器：从 JSON 规格生成黑手：升温 随机系列锁定预设（gf_V*Options）所需数据。

用法:
  python3 tools/preset_gen.py work/presets/dashenpan.json               # 校验 + 生成函数体到 <spec>.galaxy.txt + 打印接线清单
  python3 tools/preset_gen.py work/presets/dashenpan.json --selfcheck   # 与源码中同名函数回归比对阵容串/使能串

数据来源（每次运行时从 work/blackhand/CustomLogic.galaxy + 基线地图 GameStrings 重新抽取）:
  - 角色名表 gv_roleNameArray[池][号]（含随机槽名）
  - 随机槽选项 gv_roleOptionExists[4][槽][位] + gv_roleOptionsText[4][槽][位]

座席排序规则（用户约定，生成器内建）:
  阵营序 = 城镇 → 黑手党 → 三合会 → 中立致命 → 中立邪恶 → 中立温和
  城镇内 = 固定位 → 城镇随机 → 城镇保护 → 城镇调查 → 城镇政府（最后）
  黑手/三合会内 = 固定位 → 随机 → 致命/支援/欺诈等其他随机槽
  中立内 = 致命固定位 → 中立随机槽 → 中立邪恶槽 → 温和固定位 → 中立温和槽
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_MAP = ROOT / 'work' / 'boot2-user.SC2Map'
SRC_GALAXY = ROOT / 'work' / 'blackhand' / 'CustomLogic.galaxy'

sys.path.insert(0, str(ROOT / 'tools'))
import sc2map  # noqa: E402

# 非十六进制名称键的角色（StringExternal 键非 Param/Value/HEX），手工映射
ALIAS = {
    '影武者': (3, 31),
    '观察者': (1, 31),
    '???': (8, 1),
    '天选者': (3, 32),
    '煽动家': (3, 19),
    '篡位者': (3, 19),
    '党徒': (2, 1),
    'D徒': (2, 1),
    '造假者': (5, 5),
    '造假': (5, 5),
    '审计官': (3, 11),
    '审ji官': (3, 11),
    '征募官': (1, 23),
    '开膛手': (3, 20),
    '连环杀手': (3, 1),
    '连环爱手': (3, 1),
    '弃子': (2, 16),
    '死士': (5, 16),
    '杀人狂': (3, 9),
    '爱人狂': (3, 9),
    '感染者': (3, 22),
    '中立混乱': (4, 20),
    '阎罗': (3, 26),
    '仲裁者': (3, 27),
}

# 池3 固定角色 → 中立子层（致命=默认；其余两集合来自随机槽 4/13、4/14 的选项清单）
NEUTRAL_EVIL_ROLES = {(3, 8), (3, 12), (3, 4), (3, 11), (3, 19)}     # 协教徒、法官、女巫、审ji官、煽动家
NEUTRAL_MILD_ROLES = {(3, 2), (3, 3), (3, 6), (3, 7), (3, 17)}  # 生存者、小丑、处刑者、失忆者、赌鬼

# 随机槽的规格友好名 → 源码槽名（源码名见 roleNameArray[4][N] 去空格）
SLOT_ALIAS = {
    '城镇政府': '城镇zf',
    '政府': '城镇zf',
    '保护': '城镇保护',
    '黑手随机': '黑手D随机',
    '黑手党随机': '黑手D随机',
    '中立邪恶': '中立协恶',
    '中立致命': '中立致命',
}

# 随机槽(池4) → (层序, 层内序)。层: 1城镇 2黑手 3三合会 4中立致命 5中立邪恶 6中立温和
SLOT_TIER = {
    1: (7, 1),
    2: (1, 1), 6: (1, 2), 5: (1, 3), 4: (1, 4), 7: (1, 5), 8: (1, 6),
    3: (2, 1), 9: (2, 2), 10: (2, 3), 11: (2, 4),
    15: (3, 1), 16: (3, 2), 17: (3, 3), 18: (3, 4),
    12: (4, 1), 19: (4, 2), 20: (4, 3),
    13: (5, 1),
    14: (6, 1),
}
POOL_TIER = {1: 1, 2: 2, 5: 3}
# 黑手/三合会层内顺序：固定在随机槽之前由 pool tier 前缀保证（fixed 序 0，槽序 1..）
PLAYER_COUNTS = [15, 14, 13, 12]
OPTION_LIMIT = 6


def load_strings():
    gs = sc2map.read(SRC_MAP, 'zhCN.SC2Data\\LocalizedData\\GameStrings.txt').decode('utf-8', 'replace')
    d = {}
    for line in gs.splitlines():
        line = line.replace('\r', '')
        if '=' in line:
            k, _, v = line.partition('=')
            d[k.strip()] = v

    # 自加文案（work/blackhand/strings-*.txt，格式同 GameStrings：每行 键=值，// 为注释）
    # 需要在基线 zhCN 之上叠加，否则新选项/新角色的文案（尚未打进基线地图）解析不出来
    for f in sorted(SRC_GALAXY.parent.glob('strings-*.txt')):
        for line in f.read_text(encoding='utf-8').splitlines():
            line = line.replace('\r', '').strip()
            if not line or line.startswith('//') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            d[k.strip()] = v
    return d


def strip_tags(s):
    return re.sub(r'<[^>]*>', '', s)


def load_roles():
    src = SRC_GALAXY.read_text(encoding='utf-8')
    strings = load_strings()
    roles = {}
    for m in re.finditer(r'gv_roleNameArray\[(\d)\]\[(\d+)\] = StringExternal\("Param/Value/([0-9A-Fa-f]+)"\)', src):
        cat, role, key = int(m.group(1)), int(m.group(2)), m.group(3)
        v = strings.get('Param/Value/' + key)
        if v is None:
            raise SystemExit(f'GameStrings 缺键 Param/Value/{key} (角色 {cat}/{role})')
        roles[(cat, role)] = strip_tags(v)
    for name, coord in ALIAS.items():
        roles[coord] = name
    return roles


def name_index(roles):
    idx = {}
    for (cat, role), name in roles.items():
        if cat not in (1, 2, 3, 4, 5):
            continue
        key = name.replace(' ', '')
        if key in idx and idx[key] != (cat, role):
            raise SystemExit(f'角色名重名: {key} = {idx[key]} 与 {(cat, role)}')
        idx[key] = (cat, role)
    for friendly, canonical in SLOT_ALIAS.items():
        if canonical in idx and friendly not in idx:
            idx[friendly] = idx[canonical]
    for name, coord in ALIAS.items():
        key = name.replace(' ', '')
        if key in idx and idx[key] != coord:
            raise SystemExit(f'ALIAS 重名: {key} = {idx[key]} 与 {coord}')
        idx[key] = coord
    return idx


def load_random_slots():
    """{槽号: {'name': 去空格槽名, 'options': {位: 标签}}}"""
    src = SRC_GALAXY.read_text(encoding='utf-8')
    strings = load_strings()
    roles = load_roles()
    slots = {}
    for slot in range(1, 20):
        name = roles.get((4, slot))
        if name is None:
            continue
        opts = {}
        for b in range(OPTION_LIMIT):
            if re.search(r'gv_roleOptionExists\[4\]\[%d\]\[%d\] = true' % (slot, b), src):
                m = re.search(r'gv_roleOptionsText\[4\]\[%d\]\[%d\] = StringExternal\("Param/Value/([0-9A-Za-z_]+)"\)' % (slot, b), src)
                opts[b] = strip_tags(strings.get('Param/Value/' + m.group(1), '(无文案)')) if m else '(无文案)'
        slots[slot] = {'name': name.replace(' ', ''), 'options': opts}
    return slots


def seat_sort_key(seat):
    """(层, 层内序)。同层同序的座位由 sort_seats 先按名字字数、再按输入序稳定排序。"""
    cat, role = seat
    if cat == 4:
        tier, order = SLOT_TIER[role]
        return (tier, 1 + order / 100.0)
    if cat == 1:
        return (1, 0)
    if cat == 2:
        return (2, 0)
    if cat == 5:
        return (3, 0)
    if cat == 3:
        if seat in NEUTRAL_EVIL_ROLES:
            return (5, 0)
        if seat in NEUTRAL_MILD_ROLES:
            return (6, 0)
        return (4, 0)
    raise SystemExit(f'未知座席池: {seat}')


def sort_seats(seats, name_len=None):
    """层序排列；同层内先按名字字数（少的在前），再按「该座席首次出现」的次序。

    用户口径（shw177）：同一层里重复的角色必须相邻——如两个瘟疫散布者放一起、
    系命人排在瘟疫下面（而不是被另一张瘟疫散布者从中间隔开）。
    用户口径（2026-09-13）：同是固定角色时，名字字数少的排在上面
    （如 侦探 排在 观察者 前面）；字数相同的保持用户列出顺序（`first` = 首次出现下标）。
    name_len 传 seat → 名字字数的函数；不传则只按层序 + 首次出现序。
    """
    first = {}
    for i, s in enumerate(seats):
        first.setdefault(s, i)

    def key(s):
        tier, order = seat_sort_key(s)
        return (tier, order, name_len(s) if name_len else 0, first[s])

    return sorted(seats, key=key)


def encode_enable(info, enable_labels, slot):
    opts = info['options']
    unknown = [x for x in enable_labels if x not in opts.values()]
    if unknown:
        raise SystemExit(f'随机槽 4/{slot}({info["name"]}) 无选项 {unknown}；可用: {list(opts.values())}')
    bits = ''.join('1' if opts[b] in enable_labels else '0' for b in sorted(opts))
    bits = bits.rstrip('0')
    return bits if bits else '0'


def sub_enable_string(slots, sub, spec):
    overrides = spec.get('enable_overrides', {}).get(sub, {})
    parts = []
    for slot in range(1, 20):
        info = slots.get(slot)
        if info is None:
            parts.append('0')
            continue
        labels = overrides.get(info['name'], [])
        for friendly, canonical in SLOT_ALIAS.items():
            if canonical == info['name'] and friendly in overrides:
                labels = overrides[friendly]
        parts.append(encode_enable(info, labels, slot))
    return ' '.join(parts)


def resolve_seat(name_idx, label):
    if label not in name_idx:
        raise SystemExit(f'未知角色别名: {label}；可在 preset_gen.ALIAS 增加，或确认源码有该角色名')
    return name_idx[label]


def build_lineup(sub_data, name_idx, spec, n):
    seats = []
    for label, count in sub_data['randoms']:
        seats.extend([resolve_seat(name_idx, label)] * count)
    for label in sub_data['fixed']:
        seats.append(resolve_seat(name_idx, label))
    dec = resolve_seat(name_idx, spec['decrement'])
    fallback = spec.get('decrement_fallback')
    while len(seats) > n:
        if dec in seats:
            seats.reverse()
            seats.remove(dec)
            seats.reverse()
            continue
        if fallback:
            dec2 = resolve_seat(name_idx, fallback)
            if dec2 in seats:
                seats.reverse()
                seats.remove(dec2)
                seats.reverse()
                continue
        raise SystemExit(f'人数 {len(seats)}→{n}: 可递减角色 "{spec["decrement"]}" 已耗尽')
    if len(seats) != n:
        raise SystemExit(f'该子变体无法配到 {n} 人（当前 {len(seats)}）')

    label_of = {seat: label for label, seat in name_idx.items()}
    return sort_seats(seats, lambda s: len(label_of.get(s, '')))


def emit_lines(seats):
    cat = ' '.join(str(c) for c, _ in seats)
    role = ' '.join(str(r) for _, r in seats)
    assert len(cat.split()) == len(role.split())
    return cat, role


def gen_function(spec, slots, name_idx):
    fn = spec['function']
    nsubs = len(spec['subs'])
    out = []
    out.append(f'void {fn} () {{')
    out.append('    int init_i;')
    out.append('')
    out.append('    // Variable Declarations')
    out.append('    int lv_a;')
    out.append('    int lv_c;')
    out.append('    string[10] lv_str;')
    out.append('    string lv_category;')
    out.append('    string lv_role;')
    out.append('')

    # 自动变量声明块：从 gf_VBFCZOptions 原样克隆（shw139 事故：漏了它 → 循环变量未声明 → 整脚本编译失败）
    _src = SRC_GALAXY.read_text(encoding='utf-8')
    _ref = _src.find('void gf_VBFCZOptions () {')
    _as = _src.find('    // Automatic Variable Declarations\n', _ref)
    _ae = _src.find('    // Variable Initialization\n', _as)
    assert _as > 0 and _ae > _as, '找不到参考函数的自动变量声明块'
    out.extend(_src[_as:_ae].rstrip('\n').split('\n'))
    out.append('')

    out.append('    // Variable Initialization')
    out.append('    for (init_i = 0; init_i <= 9; init_i += 1) {')
    out.append('        lv_str[init_i] = "";')
    out.append('    }')
    out.append('')
    out.append('    lv_category = "";')
    out.append('    lv_role = "";')
    out.append('')
    out.append('    // Implementation')
    out.append(f'    libNtve_gf_SetDialogItemText(gv_confirmationButtonItem[1], StringExternal("Param/Value/{spec.get("btn_key", "GCZJBTN")}"), PlayerGroupAll());')
    for k in ['C264FEA4', 'C1E1492C', 'FF2C2A34', 'FBD78287', '36EB4524']:
        out.append(f'    DialogControlAddItem(gv_rolesMenusItem[0], PlayerGroupAll(), StringExternal("Param/Value/{k}"));')
    for grp, keys in [(3, ['B4F7A9F6', 'F429FE99', 'E4DDE61D']),
                      (6, ['3EBC62A6', '6A680082', 'A2853A16', 'CD5FE7E9']),
                      (21, ['452C0568', 'A1C287A2', '40640D5E'])]:
        for k in keys:
            out.append(f'    DialogControlAddItem(gv_optionsPanelItem[{grp}], PlayerGroupAll(), StringExternal("Param/Value/{k}"));')
    out.append('    gv_rolesAssigned = 0;')
    out.append('    lv_str[0] = gv_timelength;')
    out.append('    lv_str[1] = gv_townOptions;')
    out.append('    lv_str[2] = gv_mafiaOptions;')
    out.append('    lv_str[3] = gv_neutralOptions;')
    out.append(f'    lv_c = RandomInt(1, {nsubs});')
    out.append('    lv_str[5] = gv_triadOptions;')
    out.append('    lv_str[6] = gv_townWeights;')
    out.append('    lv_str[7] = gv_mafiaWeights;')
    out.append('    lv_str[8] = gv_neutralWeights;')
    out.append('    lv_str[9] = gv_triadWeights;')
    for i, (sub, data) in enumerate(spec['subs'].items()):
        kw = 'if' if i == 0 else 'else if'
        out.append(f'    {kw} ((lv_c == {i + 1})) {{')
        out.append(f'        lv_str[4] = "{sub_enable_string(slots, sub, spec)}";')
        out.append(f'        gv_setupInfo[1] = StringExternal("Param/Value/{spec["sub_key_prefix"]}{sub}");')
        for n in PLAYER_COUNTS:
            cat, role = emit_lines(build_lineup(data, name_idx, spec, n))
            out.append(f'        if ((PlayerGroupCount(gv_currentPlayers) == {n})) {{')
            out.append(f'            lv_category = "{cat}";')
            out.append(f'            lv_role = "{role}";')
            out.append('        }')
            out.append('')
        out.append('    }')
    src = SRC_GALAXY.read_text(encoding='utf-8')
    i0 = src.find('void gf_VBFCZOptions () {')
    tail_src = src[i0:]
    fill_start = tail_src.find('    gv_bankSaveStrings[0][0][0] = StringWord(lv_str[1], 1);')
    fill_end = tail_src.find('\n}\n', fill_start)
    out.append(tail_src[fill_start:fill_end + 3].rstrip())

    body = '\n'.join(out) + '\n'
    cut = body.find('// Implementation')
    used = set(re.findall(r'\b(auto[0-9A-F]{8}_[a-z]+)\b', body))
    declared = set(re.findall(r'\b(auto[0-9A-F]{8}_[a-z]+)\b', body[:cut]))
    miss = sorted(used - declared)
    assert not miss, f'生成的函数缺少自动变量声明: {miss}'

    return body


def parse_data_rows(text):
    """顺序扫描，返回 [(category, role, enable)] 每个人数档一条。"""
    rows = []
    cur_cat = cur_role = cur_en = None
    for line in text.splitlines():
        s = line.strip()
        if 'lv_category = "' in s:
            cur_cat = s.split('"')[1]
        elif 'lv_role = "' in s:
            cur_role = s.split('"')[1]
            if cur_cat and cur_en:
                rows.append((cur_cat, cur_role, cur_en))
                cur_cat = cur_role = cur_en = None
        elif 'lv_str[4] = "' in s:
            cur_en = s.split('"')[1]
    return rows


def extract_live_data(fn):
    src = SRC_GALAXY.read_text(encoding='utf-8')
    i0 = src.find(f'void {fn} () {{')
    assert i0 > 0, f'源码中找不到 {fn}'
    endm = src.find('\n}\n', i0)
    return parse_data_rows(src[i0:endm])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    spec_path = Path(sys.argv[1])
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    name_idx = name_index(load_roles())
    slots = load_random_slots()
    body = gen_function(spec, slots, name_idx)

    if '--selfcheck' in sys.argv:
        gen_rows = parse_data_rows(body)
        live_rows = extract_live_data(spec['function'])
        if len(gen_rows) != len(live_rows):
            print(f'selfcheck 行数不一致: 生成 {len(gen_rows)} vs 源码 {len(live_rows)}')
            return 2
        diffs = []
        for g, v in zip(gen_rows, live_rows):
            if (g[0], g[1]) != (v[0], v[1]):
                diffs.append(f'  阵容: 生成={g[0]}/{g[1]} 源码={v[0]}/{v[1]}')
                continue
            gw = g[2].split()
            vw = v[2].split()
            used = {int(r) for c, r in zip(g[0].split(), g[1].split()) if c == '4'}
            for slot in sorted(used):
                gn = (gw[slot - 1] if slot - 1 < len(gw) else '0').rstrip('0') or '0'
                vn = (vw[slot - 1] if slot - 1 < len(vw) else '0').rstrip('0') or '0'
                if gn != vn:
                    diffs.append(f'  槽4/{slot} 使能: 生成={gn} 源码={vn}')
        if not diffs:
            print(f'selfcheck OK: {spec["function"]} 阵容与使能串（用到的槽）与源码一致（{len(gen_rows)} 档）')
            return 0
        print('selfcheck 差异:')
        for d in diffs:
            print(d)
        return 2

    out_path = spec_path.with_suffix('.galaxy.txt')
    out_path.write_text(body, encoding='utf-8')
    tag = spec.get('variant_tag', spec['id'].lower())
    print(f'函数体已生成: {out_path}')
    print('接线清单:')
    print(f'  1. 原型区: void {spec["function"]} ();')
    print(f'  2. 变体菜单追加第 {spec["menu_item"]} 项（GameStrings 键 {spec.get("menu_name_key", "GCZJNAME")}）')
    print(f'  3. gt_OSVariantsMenuChange_Func: item=={spec["menu_item"]} 分支（NAME/DESC 键）')
    print(f'  4. gt_OSVariantsMenuConfirm_Func: item=={spec["menu_item"]} → variantSelection={spec["variant"]}')
    print(f'  5. Confirm 分发: variantSelection=={spec["variant"]} → {spec["function"]}()')
    print(f'  6. gv_variant 映射: variantSelection=={spec["variant"]} → "{tag}"')
    print(f'  7. 开局白字广播条件追加 "{tag}"')
    print(f'  8. 锁定三件套加 variant {spec["variant"]}: RoleManipulate `!= 31` 守卫 / 预览选中白名单 / 移除按钮条件')
    print(f'  9. GameStrings: {spec.get("menu_name_key", "GCZJNAME")}/GCZJDESC/'
          f'{spec["sub_key_prefix"]}{"/".join(spec["subs"].keys())}/GCZJBTN')
    return 0


if __name__ == '__main__':
    sys.exit(main())
