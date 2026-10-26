#!/usr/bin/env python3
"""Execute actual 白手起家 and its complete loader in a C++17 UBSan harness.

Only Galaxy declarations are translated. Core gf_* calls are recursively extracted,
never automatically stubbed; only the explicit chat/UI boundary is doubled. String
and player-group natives have small declared doubles. This is not an SC2 compiler,
engine StringWord, rendering, or live-play test.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from test_egun import mask

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
SPEC = ROOT / 'work/presets/baishouqijia.json'
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'


def function(source: str, name: str) -> str:
    live = mask(source)
    match = re.search(r'^(?:void|bool|int|text|string|fixed)\s+' + re.escape(name)
                      + r'\s*\([^;{}]*\)\s*\{', live, re.M)
    assert match, f'missing actual function {name}'
    depth, end = 1, match.end()
    while depth:
        assert end < len(live), f'unbalanced actual function {name}'
        depth += (live[end] == '{') - (live[end] == '}')
        end += 1
    return source[match.start():end]


def validate_spec(spec: dict) -> None:
    fields = spec['source_save_code'].split(' ')
    assert len(fields) == 14 and fields[10] == ''
    assert all(c in ALPHABET for word in fields for c in word)
    assert spec['category'] == sum(([ALPHABET.index(c) >> 3, ALPHABET.index(c) & 7]
                                    for c in fields[0]), [])[:15]
    assert spec['role'] == [ALPHABET.index(c) for c in fields[1]]
    assert spec['category'] == [1, 1, 1, 4, 4, 4, 4, 4, 4, 4, 4, 4, 2, 3, 4]
    assert spec['role'] == [2, 2, 13, 4, 2, 2, 2, 2, 5, 5, 7, 6, 22, 1, 13]
    for pool, field in ((1, 2), (2, 3), (3, 4), (4, 5), (5, 6)):
        expected = ''.join(f'{ALPHABET.index(c):06b}' for c in fields[field])
        assert spec['physical_options'][str(pool)] == expected
    for pool, field in ((1, 7), (2, 8), (3, 9), (5, 11)):
        assert spec['weights'][str(pool)] == [ALPHABET.index(c) / 10 for c in fields[field]]
    assert spec['player_counts'] == [15]
    assert spec['trial'] == '1211001111000'
    assert spec['times'] == [1.2, 0.6, 0.3, 0.8]
    assert spec['missing_options'] == 'current_defaults'
    assert spec['special_rules'] == dict(dead=False, gang=False, life=False)


def boolean_terms(expression: str, operator: str) -> list[str]:
    """Split actual top-level boolean terms, not similarly numbered role operands."""
    expression = expression.strip()
    while expression.startswith('('):
        depth, closes_at = 0, -1
        for i, ch in enumerate(expression):
            depth += (ch == '(') - (ch == ')')
            if depth == 0:
                closes_at = i
                break
        if closes_at != len(expression) - 1:
            break
        expression = expression[1:-1].strip()
    parts, depth, start, i = [], 0, 0, 0
    while i < len(expression):
        depth += (expression[i] == '(') - (expression[i] == ')')
        if depth == 0 and expression.startswith(operator, i):
            parts.append(expression[start:i].strip())
            i += len(operator)
            start = i
        else:
            i += 1
    parts.append(expression[start:].strip())
    if len(parts) == 1:
        return [expression]
    return [term for part in parts for term in boolean_terms(part, operator)]


def static_checks(source: str, spec: dict) -> None:
    body = function(source, spec['function'])
    live = mask(body)
    assert 'gf_OSLoadBase64(' not in live and 'gf_BHApplyBoardWeights(' not in live
    assert 'gf_VLoadSaveSlot(0, 10)' in body
    for name, values in (('category', spec['category']), ('roleList', spec['role'])):
        assert f'lv_{name} = "' + ' '.join(map(str, values)) + '";' in body
    for pool, bits in spec['physical_options'].items():
        assert f'lv_bits[{pool}] = "{bits}";' in body
    for pool, weights in spec['weights'].items():
        match = re.search(r'lv_weights\[' + pool + r'\]\s*=\s*"([^"]*)";', body)
        assert match and list(map(float, match[1].split())) == weights
    assert f'"{spec["trial"]}"' in body
    assert re.search(r'PlayerGroupCount\(gv_currentPlayers\)\s*==\s*15', body)
    assert not re.search(r'PlayerGroupCount\(gv_currentPlayers\)\s*==\s*(?:12|13|14)\b', body)
    assert 'c_bhSaveRoleMax' in body and re.search(r'<=\s*11\b', body)
    assert re.search(r'if \(\(gv_variantSelection == 41\)\) \{\s*gv_variant = "bsqj";', source)
    assert '(gv_variant == "bsqj")' in source
    assert len(re.findall(r'if \(\(DialogControlGetSelectedItem\([^\n]+== 41\)\) \{\s*gv_variantSelection = 41;', source)) == 2
    assert re.search(r'if \(\(gv_variantSelection == 41\)\) \{\s*gf_VBSQJOptions\(\);', source)
    assert source.count('StringExternal("Param/Value/BSQJNAME")') >= 2
    for key in ('BSQJNAME', 'BSQJDESC', 'BSQJBTN', 'BSQJSUBA', 'BSQJONLY15'):
        assert f'Param/Value/{key}' in source
    assert function(source, 'gf_InitializeVariables').count('gf_BSQJSnapshotDefaults();') == 1

    manipulate = function(source, 'gt_OSRoleManipulate_Func')
    condition_section = manipulate.split('// Conditions', 1)[1].split('// Actions', 1)[0]
    assert 'if (testConds)' in condition_section
    guard = re.search(r'if \(!\(([^\n]*gv_variantSelection != 41[^\n]*)\)\) \{\s*return false;', condition_section)
    assert guard and 'gv_variantSelection != 41' in boolean_terms(guard[1], '&&')

    select = function(source, 'gt_OSRoleSelect_Func')
    add_guard = re.search(r'if \(([^\n]*gv_variantSelection == 41[^\n]*)\) \{\s*'
                          r'DialogControlSetEnabled\(gv_rolesMenusItem\[3\], PlayerGroupSingle\(gv_host\), false\);', select)
    assert add_guard and 'gv_variantSelection == 41' in boolean_terms(add_guard[1], '||')

    menus = function(source, 'gt_OSMenus_Func')
    delete_guard = re.search(r'if \(([^\n]*EventDialogControl\(\) == gv_rolesMenusItem\[2\][^\n]*gv_variantSelection != 41[^\n]*)\) \{([\s\S]*?)\n    \}', menus)
    assert delete_guard and 'gv_variantSelection != 41' in boolean_terms(delete_guard[1], '&&')
    assert 'DialogControlSetEnabled(gv_rolesMenusItem[4], PlayerGroupSingle(gv_host), true)' in delete_guard[2]

    strings = dict(line.split('=', 1) for line in (ROOT / 'work/blackhand/strings-bsqj.txt').read_text(encoding='utf-8').splitlines() if line.startswith('Param/Value/'))
    build = (ROOT / 'tools/boot2_build.py').read_text(encoding='utf-8')
    for key in ('BSQJNAME', 'BSQJDESC', 'BSQJBTN', 'BSQJSUBA', 'BSQJONLY15'):
        assert 'Param/Value/' + key in strings and repr('Param/Value/' + key) in build
    assert strings['Param/Value/BSQJDESC'] == spec['desc']
    assert re.sub('<[^>]+>', '', strings['Param/Value/BSQJNAME']) == spec['name']
    assert '<s val="ModLeftSize16">' in strings['Param/Value/BSQJONLY15']
    print('PASS codec/spec, menu mappings/dispatch/tag, three exact lock guards and strings/build hooks')


PREFIX = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>
using string = std::string;
using text = std::string;
using fixed = double;
using playergroup = unsigned int;
using soundlink = string;
const string null = "";
std::vector<string> messages;
std::map<int, bool> enabled, checked, visible;
std::map<int, fixed> current;
std::map<int, int> selected;
std::map<int, std::vector<text>> items;
int checks = 0;
void require(bool ok, const string &message) {
    ++checks;
    if (!ok) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}
string StringExternal(string key) { return key; }
string StringWord(string value, int index) {
    require(index >= 1, "StringWord index must be positive");
    std::istringstream stream(value);
    string result;
    for (int i = 1; i <= index; ++i) if (!(stream >> result)) return "";
    return result;
}
string StringSub(string value, int first, int last) {
    require(first >= 1 && last >= first, "StringSub positive inclusive bounds");
    if (size_t(first) > value.size()) return "";
    return value.substr(first - 1, last - first + 1);
}
int StringLength(string value) { return int(value.size()); }
fixed StringToFixed(string value) { return value.empty() ? 0 : std::stod(value); }
int StringToInt(string value) { return value.empty() ? 0 : std::stoi(value); }
string IntToString(int value) { return std::to_string(value); }
text IntToText(int value) { return std::to_string(value); }
text StringToText(string value) { return value; }
text FixedToText(fixed value, int places) {
    std::ostringstream out; out << std::fixed << std::setprecision(places) << value; return out.str();
}
fixed MaxF(fixed a, fixed b) { return std::max(a, b); }
fixed MinF(fixed a, fixed b) { return std::min(a, b); }
playergroup PlayerGroupAll() { return 0xfffe; }
playergroup PlayerGroupSingle(int player) { return 1U << player; }
int PlayerGroupCount(playergroup group) { return __builtin_popcount(group); }
int PlayerGroupNextPlayer(playergroup group, int previous) {
    for (int p = std::max(1, previous + 1); p <= 15; ++p) if (group & (1U << p)) return p;
    return -1;
}
int Color(fixed, fixed, fixed) { return 0; }
soundlink SoundLink(string name, int) { return name; }
// Explicit presentation boundary, not an automatically generated gf_* stub.
void gf_CBSystemMessage(text message, int, int, int, soundlink, int) { messages.push_back(message); }
void DialogControlAddItem(int control, playergroup, text message) { items[control].push_back(message); }
void DialogControlRemoveAllItems(int control, playergroup) { items[control].clear(); }
void DialogControlSetEnabled(int control, playergroup, bool value) { enabled[control] = value; }
void DialogControlSetVisible(int control, playergroup, bool value) { visible[control] = value; }
void DialogControlSelectItem(int control, playergroup, int value) { selected[control] = value; }
void libNtve_gf_SetDialogItemText(int, text, playergroup) {}
void libNtve_gf_SetDialogItemCurrentValue(int control, fixed value, playergroup) { current[control] = value; }
void libNtve_gf_SetDialogItemChecked(int control, bool value, playergroup) { checked[control] = value; }
template<class T> void clearValue(T &value) { value = T{}; }
template<class T, size_t N> void clearValue(T (&value)[N]) { for (auto &x : value) clearValue(x); }
'''


def harness(source: str, spec: dict) -> str:
    # Recursively compile actual helpers. No unknown gf_* call is auto-stubbed.
    bodies = {}
    todo = [spec['function'], 'gf_DefaultRoleOptions', 'gf_VLoadSaveSlot', 'gf_BSQJSnapshotDefaults']
    while todo:
        name = todo.pop()
        if name in bodies or name == 'gf_CBSystemMessage':
            continue
        body = function(source, name)
        bodies[name] = body
        todo.extend(set(re.findall(r'\b(gf_\w+)\s*\(', mask(body))) - bodies.keys())
    code = '\n\n'.join(bodies.values())
    required = set(re.findall(r'\bgv_\w+', mask(code))) | {
        'gv_roleOptionExists', 'gv_roleNameArray', 'gv_bankSaveWeights',
        'gv_defaultRoleOptions', 'gv_currentPlayers', 'gv_categoriesArray',
        'gv_rolesArray', 'gv_rolesAssigned', 'gv_roleOptions', 'gv_roleWeights',
        'gv_bankSaveStrings', 'gv_bankSaveIntegers', 'gv_xrDead', 'gv_xrGang', 'gv_xrLife',
        'gv_townMax', 'gv_mafiaTriadMax', 'gv_neutralMax', 'gv_randomMax',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims}{{}};'
    assert not required - declarations.keys(), ('missing globals', required - declarations.keys())
    global_text = '\n'.join(declarations[name] for name in sorted(required))
    constants = []
    for name in set(re.findall(r'\bc_\w+', mask(code))):
        match = re.search(r'^const (int|fixed|bool) ' + name + r'\s*=\s*([^;]+);', source, re.M)
        assert match, ('unmapped engine constant', name)
        constants.append(match.group())

    init = function(source, 'gf_InitializeVariables')
    # Fixture data comes only from actual literal initializations, not a reimplementation
    # of either the preset or loader. The full DefaultRoleOptions then runs unchanged.
    literals = []
    for match in re.finditer(r'(gv_\w+(?:\[\d+\])*)\s*=\s*'
                             r'(true|false|-?\d+(?:\.\d+)?|"[^"\n]*"|StringExternal\("[^"\n]*"\))\s*;', init):
        if re.match(r'gv_\w+', match[1])[0] in required:
            literals.append(match.group())
    for name in ('gv_townMax', 'gv_mafiaTriadMax', 'gv_neutralMax', 'gv_randomMax'):
        match = re.search(r'\b' + name + r'\s*=\s*\d+;', source)
        assert match
        literals.append(match.group())
    prototype_text = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies.values())
    # Galaxy locals are zero-initialized. Only declaration syntax changes.
    code = re.sub(r'\b(int|bool|fixed|text|string)((?:\[\d+\])+)\s+(\w+);', r'\1 \3\2{};', code)
    code = re.sub(r'(?m)^(\s+)(int|bool|fixed|playergroup) (\w+);', r'\1\2 \3{};', code)
    case_data = 'int expectedPools[15] = {' + ','.join(map(str, spec['category'])) + '};\n'
    case_data += 'int expectedRoles[15] = {' + ','.join(map(str, spec['role'])) + '};\n'
    case_data += 'string exported[6] = {"",' + ','.join(json.dumps(spec['physical_options'][str(p)]) for p in range(1, 6)) + '};\n'
    for p in (1, 2, 3, 5):
        case_data += f'const fixed weights{p}[] = {{' + ','.join(map(str, spec['weights'][str(p)])) + '};\n'
    case_data += 'std::vector<fixed> expectedWeights[6] = {{}, {std::begin(weights1),std::end(weights1)}, {std::begin(weights2),std::end(weights2)}, {std::begin(weights3),std::end(weights3)}, {}, {std::begin(weights5),std::end(weights5)}};\n'
    fixture = '\n'.join(f'    clearValue({name});' for name in sorted(required))
    fixture += '\n' + '\n'.join('    ' + line for line in literals)
    for name, body in bodies.items():
        first = source.count('\n', 0, source.index(body)) + 1
        print(f'Actual {name}: lines {first}..{first + body.count(chr(10))}', flush=True)
    return PREFIX + '\n' + '\n'.join(constants) + '\n' + global_text + '\n' + prototype_text + '\n' + code + '\n' + case_data + r'''
bool baselineOptions[9][41][12];
fixed baselineWeights[9][41];
void fixture() {
''' + fixture + r'''
    gf_DefaultRoleOptions();
    gf_BSQJSnapshotDefaults();
    for (int p = 1; p <= 5; ++p) for (int r = 1; r <= 37; ++r) {
        baselineWeights[p][r] = gv_bankSaveWeights[0][p][r];
        for (int b = 0; b <= 11; ++b) baselineOptions[p][r][b] = gv_defaultRoleOptions[p][r][b];
    }
    for (int i = 0; i < 32; ++i) gv_optionsPanelItem[i] = 1000 + i;
    for (int i = 0; i < 10; ++i) gv_rolesMenusItem[i] = 2000 + i;
    gv_host = 1;
    gv_xrUi = true;
    gv_xrDeadBox = 3001; gv_xrGangBox = 3002; gv_xrLifeBox = 3003;
}
void poison() {
    for (int p = 1; p <= 5; ++p) for (int r = 1; r <= 37; ++r) {
        gv_roleWeights[p][r] = gv_bankSaveWeights[0][p][r] = 4.9;
        gv_bankSaveStrings[0][r][p] = "111111111111";
        for (int b = 0; b <= 11; ++b) {
            gv_roleOptions[p][r][b] = !baselineOptions[p][r][b];
            gv_defaultRoleOptions[p][r][b] = !baselineOptions[p][r][b];
        }
    }
    for (int i = 1; i <= 15; ++i) { gv_rolesArray[i] = 1; gv_categoriesArray[i] = 5; }
    gv_xrDead = gv_xrGang = gv_xrLife = true;
    gv_dayLength = 6; gv_nightLength = 2; gv_discussionLength = 3; gv_trialLength = 2;
    gv_rolesAssigned = 15;
    items.clear(); messages.clear(); enabled.clear(); checked.clear();
}
void checkPreset() {
    require(gv_rolesAssigned == 15, "exactly 15 roles, no accumulation");
    for (int i = 1; i <= 15; ++i) {
        require(gv_categoriesArray[i] == expectedPools[i-1], "category seat " + std::to_string(i));
        require(gv_rolesArray[i] == expectedRoles[i-1], "role seat " + std::to_string(i));
    }
    for (int p = 1; p <= 5; ++p) for (int r = 1; r <= 37; ++r) {
        const bool loadable = (p == 1 && r <= gv_townMax) || ((p == 2 || p == 5) && r <= gv_mafiaTriadMax) || p == 3 || (p == 4 && r <= gv_randomMax);
        if (!loadable) continue;
        for (int b = 0; b <= 11; ++b) if (gv_roleOptionExists[p][r][b]) {
            const int offset = (r-1)*5+b;
            const bool expected = b <= 4 && offset < int(exported[p].size())
                ? exported[p][offset] == '1' : baselineOptions[p][r][b];
            require(gv_roleOptions[p][r][b] == expected,
                    "physical/Exists/default option " + std::to_string(p) + "/" + std::to_string(r) + "/" + std::to_string(b));
        }
        if (p != 4) {
            const fixed expected = r <= int(expectedWeights[p].size()) ? expectedWeights[p][r-1] : baselineWeights[p][r];
            require(std::abs(gv_roleWeights[p][r] - expected) < 1e-8,
                    "preserved/default weight " + std::to_string(p) + "/" + std::to_string(r));
        }
    }
    require(std::abs(gv_dayLength - 1.2) < 1e-8 && std::abs(gv_nightLength - 0.6) < 1e-8 && std::abs(gv_discussionLength - 0.3) < 1e-8 && std::abs(gv_trialLength - 0.8) < 1e-8, "all four durations");
    require(gv_startonDay && !gv_lynchonDay1 && gv_lynchType == 2, "start and lynch mode");
    require(gv_willsEnabled && gv_startDayWithDiscussion && gv_nightSequence && gv_deathDescriptions, "wills/discussion/night presentation");
    require(gv_pMAllowed && gv_trialDefense && gv_trialPausesDay && gv_chooseNames, "PM/defense/pause/names (not broken BASE64 import)");
    require(!gv_xrDead && !gv_xrGang && !gv_xrLife, "three special rules off");
    require(!checked[gv_xrDeadBox] && !checked[gv_xrGangBox] && !checked[gv_xrLifeBox], "special-rule UI synchronized off");
    for (int i : {1, 2, 3, 4, 5, 6, 7, 21, 23, 24, 27, 29, 31})
        require(enabled.count(gv_optionsPanelItem[i]) && !enabled[gv_optionsPanelItem[i]], "13 option controls locked");
    require(checked[gv_optionsPanelItem[4]] && checked[gv_optionsPanelItem[5]], "wills/discussion UI synchronized");
    require(std::abs(current[gv_optionsPanelItem[1]] - 1.2) < 1e-8 && std::abs(current[gv_optionsPanelItem[2]] - 0.6) < 1e-8, "duration UI synchronized");
    require(items[gv_rolesMenusItem[2]].size() == 15, "15 visible list rows, no accumulation");
}
int main() {
    fixture();
    gv_currentPlayers = PlayerGroupAll();
    gf_VBSQJOptions();
    checkPreset();
    for (int iteration = 0; iteration < 3; ++iteration) {
        poison();
        gv_currentPlayers = PlayerGroupAll();
        gf_DefaultRoleOptions(); // Actual confirmation chain, before the preset.
        gf_VBSQJOptions();
        checkPreset();
        for (int count : {0, 1, 4, 11, 12, 13, 14}) {
            gv_currentPlayers = 0;
            for (int i = 1; i <= count; ++i) gv_currentPlayers |= 1U << i;
            gf_VBSQJOptions();
            require(gv_rolesAssigned == 0, "non15 must not silently trim roster");
            for (int i = 1; i <= 15; ++i) require(gv_rolesArray[i] == 0 && gv_categoriesArray[i] == 0, "non15 stale seat cleared");
            require(!messages.empty(), "non15 explicit warning");
        }
    }
    std::cout << "PASS complete actual preset/loader/defaults: 15 seats, every Exists option and all weights, missing defaults, global flags, non15 rejection, repeat-switch poison; " << checks << " checks; UBSan/bounds; not SC2 engine test\n";
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--spec-only', action='store_true')
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    validate_spec(spec)
    print('PASS JSON exact raw export decode, double-space provenance and confirmed defaults policy')
    if args.spec_only:
        return

    source = args.script.read_text(encoding='utf-8')
    static_checks(source, spec)
    code = harness(source, spec)
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'C++17 compiler required'
    with tempfile.TemporaryDirectory(prefix='bh-bsqj-') as tmp:
        cpp, binary = Path(tmp) / 'test.cpp', Path(tmp) / 'test'
        cpp.write_text(code, encoding='utf-8')
        subprocess.run([compiler, '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
