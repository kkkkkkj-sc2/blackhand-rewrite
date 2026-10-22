#!/usr/bin/env python3
"""Execute actual recruiter Galaxy bodies in a small C++ engine-stub harness.

This tests logic, not the SC2 compiler or rendering. Requires g++ and no Python
packages. Optionally compare modern settlement against a pre-change script:
    python3 tools/test_recruiter_modes.py --baseline /tmp/CustomLogic.galaxy
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'


def function(source: str, name: str) -> str:
    match = re.search(r'^(?:void|bool|int) ' + re.escape(name) + r'\s*\([^;\n]*\)\s*\{', source, re.M)
    assert match, name
    start = source.index('{', match.start())
    end = balanced_end(source, start)
    return source[match.start():end]


def balanced_end(source: str, start: int) -> int:
    depth = 1
    for end in range(start + 1, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return end + 1

    raise AssertionError('unbalanced block')


def role_block(source: str, role: int) -> str:
    body = function(source, 'gf_RTTownRoleText')
    start = body.index(f'    if ((gv_roles[lv_a][0] == {role})) {{')
    return body[start:balanced_end(body, body.index('{', start))]


def build_harness(source: str, baseline: str | None) -> str:
    names = [
        'gf_ZMEnsureUi', 'gf_ZMSelect', 'gf_ZMOnNight', 'gf_ZMCloseChoices',
        'gt_ZMChoice_Func', 'gf_ZMLegacyRecruit', 'gf_SKG_1_zhengmuguan',
        'gf_SKO_1_yijing', 'gf_SKK_1_yijing', 'gf_JJRefreshAbilities', 'gf_SKY_1_zhengmuguan',
        'gt_ASCryerAction_Func', 'gf_SKA2_1_zhengmuguan', 'gf_SKP_1_zhengmuguan',
    ]
    functions = [function(source, name) for name in names]
    functions.append('void gf_RTRoleCard (int lv_a) {\n' + role_block(source, 6) + '\n' + role_block(source, 23) + '\n}')
    day = function(source, 'gt_DaySequence_Func')
    line = next(line for line in day.splitlines() if 'gv_abilityButtonItem' not in line and 'gv_roles[lv_a][0] == 23' in line)
    condition = re.fullmatch(r'\s*if \((.*)\) \{', line).group(1)
    functions.append('bool dayButton (int lv_a) { return ' + condition + '; }')
    shot_line = next(line for line in source.splitlines() if 'if ((gv_visitation[lv_a] != 0)' in line and '(gv_roles[lv_a][0] == 6)' in line and '(gv_veteraned[lv_a] == false)' in line)
    shot_condition = re.fullmatch(r'\s*if \((.*)\) \{', shot_line).group(1)
    functions.append('bool canShoot (int lv_a) { return ' + shot_condition + '; }')
    if baseline:
        functions.append(function(baseline, 'gf_SKG_1_zhengmuguan').replace('gf_SKG_1_zhengmuguan', 'modernBaseline'))

    code = '\n\n'.join(functions)
    # Galaxy puts array dimensions on types rather than variables.
    code = re.sub(r'\b(int|bool|text|string)((?:\[\d+\])+)( +)(\w+)', r'\1\3\4\2', code)
    globals_used = set(re.findall(r'\bgv_\w+', code))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not globals_used - declarations.keys(), globals_used - declarations.keys()
    globals_text = '\n'.join(declarations[name] for name in sorted(globals_used))
    reset_text = '\n'.join(f'    clearValue({name});' for name in sorted(globals_used))
    defined = set(re.findall(r'^(?:void|bool|int) (\w+)\s*\(', code, re.M))
    headers = '\n'.join(re.match(r'.*?\{', body, re.S).group(0)[:-1] + ';' for body in functions)
    calls = set(re.findall(r'\b(\w+)\s*\(', re.sub(r'//[^\n]*|"(?:\\.|[^"\\])*"', '', code)))
    special = {'if', 'while', 'for', 'return'}
    native = {
        'StringExternal', 'StringToText', 'IntToText', 'TextWithColor', 'PlayerGroupSingle', 'PlayerGroupAll',
        'PlayerGroupHasPlayer', 'PlayerGroupNextPlayer', 'EventPlayer', 'EventDialogControl',
        'DialogCreate', 'DialogControlCreate', 'DialogLastCreated', 'DialogControlLastCreated',
        'DialogSetVisible', 'gf_CBSystemMessage', 'gf_BHVisitAction',
        'libNtve_gf_CreateDialogItemButton',
    }
    stubs = '\n'.join(f'template<class... A> int {name}(A... args) {{ ++calls["{name}"]; return 0; }}' for name in sorted(calls - defined - special - native))
    constants = '\n'.join(f'constexpr int {name} = {i};' for i, name in enumerate(sorted(set(re.findall(r'\bc_\w+', code))), 1))
    return r'''
#include <cassert>
#include <iostream>
#include <map>
#include <string>
#include <tuple>
#include <vector>
using std::string;
using text = string;
using playergroup = int;
using trigger = int;
using soundlink = int;
using color = int;
using fixed = double;
using unit = int;
struct Message { string value; int recipient; };
std::vector<Message> messages;
std::map<string,int> calls;
std::map<std::pair<int,int>,bool> visible;
int eventPlayer = 1, eventControl = 0, lastId = 100;
string StringExternal(string s) { return s; }
string StringToText(string s) { return s; }
string IntToText(int n) { return std::to_string(n); }
string TextWithColor(string s, int) { return s; }
int PlayerGroupSingle(int p) { return 1 << p; }
int PlayerGroupAll() { return 65534; }
bool PlayerGroupHasPlayer(int g, int p) { return (g & (1 << p)) != 0; }
int PlayerGroupNextPlayer(int g, int p) {
    for (++p; p < 16; ++p) if (PlayerGroupHasPlayer(g, p)) return p;
    return -1;
}
int EventPlayer() { return eventPlayer; }
int EventDialogControl() { return eventControl; }
template<class... A> void DialogCreate(A...) { ++lastId; }
template<class... A> void DialogControlCreate(A...) { ++lastId; }
template<class... A> void libNtve_gf_CreateDialogItemButton(A...) { ++lastId; }
int DialogLastCreated() { return lastId; }
int DialogControlLastCreated() { return lastId; }
void DialogSetVisible(int dialog, int group, bool v) {
    for (int p = 1; p <= 15; ++p) if (PlayerGroupHasPlayer(group, p)) visible[{dialog,p}] = v;
}
template<class... A> void gf_CBSystemMessage(string message, int recipient, A...) {
    messages.push_back({message,recipient});
}
template<class T> void clearValue(T &v) { v = T{}; }
template<class T, size_t N> void clearValue(T (&v)[N]) { for (auto &item: v) clearValue(item); }
''' + constants + '\n' + globals_text + r'''
void gf_BHVisitAction(int p) { gv_visitation[p] = gv_action[p][0]; }
''' + stubs + '\n' + headers + '\n' + code + '\n' + r'''
void reset() {
''' + reset_text + r'''
    messages.clear(); calls.clear(); visible.clear();
    eventPlayer = 1; eventControl = 0; lastId = 100;
    gv_alivePlayers = PlayerGroupAll(); gv_currentPlayers = PlayerGroupAll();
    gv_dayNumber = 2; gv_isNight = true; gv_dayActions = true;
    gv_chatPrivilege[1] = true;
    gv_roles[1][0] = 23; gv_roles[1][1] = 1; gv_zmMode[1] = 2; gv_shots[1] = 2;
    gv_roles[2][0] = 2; gv_roles[2][1] = 1; gv_shots[2] = 7;
    gv_name[1] = "recruiter"; gv_number[1] = "1";
    gv_name[2] = "target"; gv_number[2] = "2";
    gv_visitation[1] = 2; gv_action[1][0] = 2;
    gv_roleOptions[1][6][2] = true; gv_roleOptions[1][23][3] = true;
}
bool hasMessage(string key, int p) {
    for (auto &m: messages) if (m.recipient == p && m.value.find(key) != string::npos) return true;
    return false;
}
int main() {
    int cases = 0;
    // Every pool/role and failure condition, with all permissive global recruiter options enabled.
    for (int pool = 0; pool < 9; ++pool) for (int role = 1; role <= 40; ++role)
    for (int flags = 0; flags < 64; ++flags) {
        reset();
        bool immune = flags & 1, blocked = flags & 2, jailed = flags & 4;
        bool dead = flags & 8, died = flags & 16, noVisit = flags & 32;
        gv_roles[2][1] = pool; gv_roles[2][0] = role; gv_immune[2][0] = immune;
        gv_roleblocked[1] = blocked ? 3 : 0; gv_jailed[1] = jailed ? 4 : 0;
        gv_diedAtNight[2] = died;
        if (dead) gv_alivePlayers &= ~PlayerGroupSingle(2);
        if (noVisit) gv_visitation[1] = 0;
        gv_roleOptions[1][23][0] = true; gv_roleOptions[1][23][1] = true;
        gv_roleOptions[1][23][3] = false;
        bool ok = pool == 1 && role != 7 && role != 12 && role != 14 && role != 19 && flags == 0;
        gf_ZMLegacyRecruit(1);
        assert(gv_shots[1] == 1);
        assert(gv_roles[2][0] == (ok ? 6 : role));
        assert(gv_roles[2][1] == pool);
        assert(gv_shots[2] == (ok ? 1 : 7));
        assert(gv_zmOneShot[2] == ok);
        assert(hasMessage(ok ? "ZMOK" : "ZMFAIL", 1));
        assert(hasMessage("2.target", 1) == ok);
        assert(hasMessage("ZMOKEND", 1) == ok);
        bool reached = !blocked && !jailed && !dead && !died && !noVisit;
        assert(hasMessage("recruiter", 2) == reached);
        for (auto &m: messages) assert(m.recipient == 1 || m.recipient == 2);
        ++cases;
    }
    // No selection is not an attempt; exhausted ability cannot spend negative or generate more feedback.
    reset(); gv_visitation[1] = 0; gv_action[1][0] = 0;
    gf_ZMLegacyRecruit(1); assert(gv_shots[1] == 2 && messages.empty());
    reset(); gv_shots[1] = 1; gf_ZMLegacyRecruit(1);
    assert(gv_shots[1] == 0); auto n = messages.size(); gf_ZMLegacyRecruit(1);
    assert(gv_shots[1] == 0 && messages.size() == n);
    // A legacy recruit reaches the real shot handler once, spends its only shot, then fails the dispatch guard.
    reset(); gf_ZMLegacyRecruit(1); gv_visitation[2] = 3;
    assert(canShoot(2)); gf_SKK_1_yijing(2);
    assert(gv_shots[2] == 0 && gv_damage[3] == 1 && !canShoot(2));
    assert(gv_zmOneShot[2]); ++cases;
    // All global vigilante shot options leave a legacy recruit at one on initialization/revival.
    for (int opts = 0; opts < 16; ++opts) {
        reset();
        for (int j = 0; j < 4; ++j) gv_roleOptions[1][6][j] = (opts & (1 << j)) != 0;
        gv_zmOneShot[2] = true; gv_roles[2][0] = 6;
        gf_SKO_1_yijing(2); assert(gv_shots[2] == 1);
        gf_JJRefreshAbilities(2); assert(gv_shots[2] == 1);
        gf_RTRoleCard(2); assert(gv_roleBoxText[2][2].find("ZMVIGBOX") != string::npos);
        ++cases;
    }
    for (int mode = 1; mode <= 2; ++mode) {
        reset(); gv_zmMode[1] = mode;
        gf_JJRefreshAbilities(1); assert(gv_shots[1] == (mode == 1 ? 3 : 2));
        assert(gv_zmMode[1] == mode);
    }
    // Choice is per player, first-night only, one-shot, and unavailable during settlement/death/game-over.
    for (int mode = 1; mode <= 2; ++mode) for (int flag = 0; flag < 9; ++flag) {
        reset(); gv_dayNumber = 1; gv_zmMode[1] = 0; gv_shots[1] = 3;
        gf_ZMEnsureUi(); eventControl = mode == 1 ? gv_zmNewButton : gv_zmOldButton;
        if (flag == 1) gv_dayNumber = 2;
        if (flag == 2) gv_isNight = false;
        if (flag == 3) gv_nightProcessingPhase = true;
        if (flag == 4) gv_alivePlayers &= ~PlayerGroupSingle(1);
        if (flag == 5) gv_roles[1][1] = 3;
        if (flag == 6) gv_roles[1][0] = 2;
        if (flag == 7) gv_gameOver = true;
        if (flag == 8) eventControl = 9999;
        bool accepted = flag == 0;
        assert(gt_ZMChoice_Func(true, false) == accepted);
        assert(gv_zmMode[1] == 0); // Condition-only evaluation never commits.
        assert(gt_ZMChoice_Func(true, true) == accepted);
        assert(gv_zmMode[1] == (accepted ? mode : 0));
        if (accepted) {
            assert(gv_shots[1] == (mode == 1 ? 3 : 2));
            assert(!gt_ZMChoice_Func(true, true));
            gf_ZMSelect(1, mode == 1 ? 2 : 1); assert(gv_zmMode[1] == mode);
        }
        ++cases;
    }
    reset(); gv_dayNumber = 1; gv_zmMode[1] = 0;
    gv_roles[3][0] = 23; gv_roles[3][1] = 1;
    gv_jailed[1] = 4; // Jailed recruiters still get to select their rules.
    gf_ZMOnNight(); assert(visible[std::make_pair(gv_zmChoiceBox,1)] && visible[std::make_pair(gv_zmChoiceBox,3)]);
    gf_ZMSelect(1,2); assert(!visible[std::make_pair(gv_zmChoiceBox,1)] && visible[std::make_pair(gv_zmChoiceBox,3)]);
    gf_ZMCloseChoices(); assert(gv_zmMode[1] == 2 && gv_shots[1] == 2);
    assert(gv_zmMode[3] == 1 && gv_shots[3] == 3 && hasMessage("ZMDEFAULT",3));
    assert(!visible[std::make_pair(gv_zmChoiceBox,3)]);
    // Late inherited role defaults to modern and gets its action panel on that same night.
    reset(); gv_zmMode[1] = 0; gf_ZMOnNight(); assert(gv_zmMode[1] == 1 && calls["gf_RAREcAction"] == 1);
    // Both reveal entry points and the day-button enabling condition enforce mode == modern.
    for (int mode = 0; mode <= 2; ++mode) {
        reset(); gv_zmMode[1] = mode; gv_isNight = false;
        assert(dayButton(1) == (mode == 1));
        gf_SKY_1_zhengmuguan(); assert(gv_activated[1] == (mode == 1));
        assert(messages.size() == (mode == 1 ? 15 : 1));
        reset(); gv_zmMode[1] = mode; gv_isNight = false;
        assert(gt_ASCryerAction_Func(true,true)); assert(gv_activated[1] == (mode == 1));
        assert(messages.size() == (mode == 1 ? 15 : 1));
        ++cases;
    }
    reset(); gv_roles[1][0] = 20; gv_zmMode[1] = 0; gv_isNight = false;
    assert(gt_ASCryerAction_Func(true,true) && gv_activated[1]); // Town crier unaffected.
    // Role card shows both indented modes, the current selection, and one-shot recruit text.
    for (int mode = 0; mode <= 2; ++mode) {
        reset(); gv_zmMode[1] = mode; gf_RTRoleCard(1);
        assert(gv_roleBoxText[1][2].find("ZMBOXNEW") != string::npos);
        assert(gv_roleBoxText[1][2].find("ZMBOXOLD") != string::npos);
        assert(gv_roleBoxText[1][2].find("ZMSTATE" + std::to_string(mode)) != string::npos);
    }
    // First-night target clicks and visits cannot turn into actual recruitment.
    reset(); gv_dayNumber = 1; gv_action[1][0] = 0; gv_visitation[1] = 0;
    gf_SKA2_1_zhengmuguan(1,2); gf_SKP_1_zhengmuguan(1);
    assert(gv_action[1][0] == 0 && gv_visitation[1] == 0);
    reset(); gv_visitation[1] = 0; gf_SKP_1_zhengmuguan(1); assert(gv_visitation[1] == 2);
''' + (r'''
    // Same actual modern settlement body, same state transitions as the pre-change version.
    for (int pool: {1,2,3,5}) for (int role: {2,3,6,7,12,14,19,23})
    for (int opts = 0; opts < 16; ++opts) for (int ammo = 0; ammo < 4; ++ammo) {
        auto prepare = [&] {
            reset(); gv_zmMode[1] = 1; gv_shots[1] = 3;
            gv_roles[2][0] = role; gv_roles[2][1] = pool;
            for (int j = 0; j < 4; ++j) {
                gv_roleOptions[1][23][j] = (opts & (1 << j)) != 0;
                gv_roleOptions[1][6][j] = j == ammo;
            }
        };
        prepare(); modernBaseline(1);
        auto expected = std::make_tuple(gv_roles[2][0],gv_roles[2][1],gv_shots[1],gv_shots[2],gv_immune[2][0],gv_immuneChance[2],gv_specialCasePlayer[1][58],calls["gf_BHCrime"]);
        prepare(); gf_SKG_1_zhengmuguan(1);
        assert(expected == std::make_tuple(gv_roles[2][0],gv_roles[2][1],gv_shots[1],gv_shots[2],gv_immune[2][0],gv_immuneChance[2],gv_specialCasePlayer[1][58],calls["gf_BHCrime"]));
        assert(!hasMessage("ZMOK",1) && !hasMessage("ZMFAIL",1));
        ++cases;
    }
''' if baseline else '') + r'''
    std::cout << "PASS: " << cases << " recruiter state/interaction cases (engine-stub logic tests, not SC2 runtime)\n";
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    source = SCRIPT.read_text()
    baseline = args.baseline.read_text() if args.baseline else None

    assert 'gf_ZMOnNight();' in function(source, 'auto_gf_NightTransition_TriggerFunc')
    assert 'gf_ZMCloseChoices();' in function(source, 'gt_NightSequence_Func')
    assert 'gt_ZMChoice_Init();' in function(source, 'SH_InitTriggers')
    dispatch = function(source, 'gf_SequenceAfter2')
    assert '(gv_zmMode[lv_a] == 2)' in dispatch and 'gf_ZMLegacyRecruit(lv_a);' in dispatch
    assert '(gv_zmMode[lv_a] == 1)' in dispatch and 'gf_SKG_1_zhengmuguan(lv_a);' in dispatch
    strings = (ROOT / 'work/blackhand/strings-zm.txt').read_text()
    keys = re.findall(r'^([^=\n]+)=', strings, re.M)
    assert len(keys) == len(set(keys))
    plain = {key: re.sub(r'<[^>]+>', '', value) for key, value in (line.split('=', 1) for line in strings.splitlines())}
    assert plain['Param/Value/ZMOK'] + '2.目标' + plain['Param/Value/ZMOKEND'] == '你成功征募了2.目标为一名义警。'
    assert plain['Param/Value/ZMFAIL'] == '你的征募失败了。'
    assert plain['Param/Value/ZMBY'] + '1.征募官名字' + plain['Param/Value/ZMTOFAIL'] == '征募官1.征募官名字尝试将你征募为义警，他暴露了。'
    assert 'ZMCOMMON' not in strings and 'ZMCOMMON' not in role_block(source, 23)
    build = (ROOT / 'tools/boot2_build.py').read_text()
    assert all(repr(key) in build for key in keys)
    assert all('　　-' in line for line in strings.splitlines() if line.startswith(('Param/Value/ZMBOXNEW=', 'Param/Value/ZMBOXOLD=')))

    with tempfile.TemporaryDirectory(prefix='bh-zm-tests-') as temp:
        cpp = Path(temp) / 'recruiter.cpp'
        binary = Path(temp) / 'recruiter'
        cpp.write_text(build_harness(source, baseline))
        subprocess.run(['g++', '-std=c++17', '-O0', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
