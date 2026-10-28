#!/usr/bin/env python3
"""Execute shipping leader-slot helpers, complete add/select/check/load functions.

Galaxy declarations become C++ declarations; bodies are extracted by brace depth.
Engine UI/events/messages, floating fixed values, and unrelated option-panel
presentation are explicit doubles. No fake add, load, or uniqueness business is
used. UBSan/bounds execution is not an SC2 compiler/rendering/scheduling test.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from test_egun import ROOT, SCRIPT, function, mask, translate

NAMES = (
    'gf_BHLeaderSlotPool', 'gf_BHLeaderAddBlocked', 'gf_BHListHas',
    'gf_BHSpyMadBlocked', 'gt_OSRoleManipulate_Func', 'gt_OSRoleSelect_Func',
    'gf_OSCheckOptionsB', 'gf_VLoadSaveSlot',
)


def harness(source: str) -> str:
    bodies = [function(source, name) for name in NAMES]
    raw = '\n\n'.join(bodies)
    used = set(re.findall(r'\b(?:gv_|gt_|c_)\w+', mask(raw))) - set(NAMES) - {'c_timeGame'}
    declarations = {}
    for match in re.finditer(r'^(?:const\s+)?(\w+)((?:\[[^\]\n]+\])*)\s+((?:gv_|gt_|c_)\w+)\s*(?:=([^;]*))?;', source, re.M):
        kind, dims, name, initial = match.groups()
        declarations[name] = f'{kind} {name}{dims}' + (f' = {initial}' if name.startswith('c_') and initial else '') + ';'

    assert not used - declarations.keys(), ('missing production globals', used - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(used))
    resets = '\n'.join(f'    clearValue({name});' for name in sorted(used) if not name.startswith('c_'))
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    code = translate(raw)
    # Galaxy implicit-zero locals, null text, and fixed are language adaptation,
    # not business edits. This test never uses random or fixed-weight decisions.
    code = re.sub(r'\bnull\b', 'text{}', code)
    code = re.sub(r'^(\s+(?:int|bool|fixed|text|string|playergroup)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', code, flags=re.M)
    sections = json.loads((ROOT / 'work/roles-list.json').read_text())['sections']
    mappings = []
    for section in sections:
        if 3 in section['variants']:
            mappings.extend((section['category'], entry['role'], i) for i, entry in enumerate(section['entries'], 1))

    menu_rows = ',\n'.join('    {' + ','.join(map(str, row)) + '}' for row in mappings)
    return r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
using std::string;
using text = string;
using fixed = double; // Explicit UI/save boundary double, not Galaxy 19.12 emulation.
using playergroup = unsigned int;
using trigger = int;
constexpr int c_timeGame = 0;
''' + globals_text + r'''
int eventPlayer = 1, eventControl = 0;
int checks = 0, scenarios = 0;
bool enabled[256][16];
int selected[256][16];
std::vector<string> messages;
#define CHECK(x) do { ++checks; if (!(x)) { std::cerr << "FAIL line " << __LINE__ << ": " << #x << '\n'; std::abort(); } } while (0)
template<class T> void clearValue(T& value) { value = T{}; }
template<class T, size_t N> void clearValue(T (&value)[N]) { for (auto& item : value) clearValue(item); }
int EventPlayer() { return eventPlayer; }
int EventDialogControl() { return eventControl; }
playergroup PlayerGroupAll() { return 0xfffe; }
playergroup PlayerGroupSingle(int p) { CHECK(p >= 1 && p <= 15); return 1u << p; }
bool PlayerGroupHasPlayer(playergroup group, int p) { CHECK(p >= 1 && p <= 15); return group & (1u << p); }
int PlayerGroupCount(playergroup group) { return __builtin_popcount(group); }
int PlayerGroupNextPlayer(playergroup group, int previous) {
    for (int p = std::max(1, previous + 1); p <= 15; ++p) if (group & (1u << p)) return p;
    return -1;
}
void DialogControlSetEnabled(int item, playergroup group, bool value) {
    CHECK(item >= 0 && item < 256);
    for (int p = 1; p <= 15; ++p) if (group & (1u << p)) enabled[item][p] = value;
}
void DialogControlSelectItem(int item, playergroup group, int value) {
    CHECK(item >= 0 && item < 256);
    for (int p = 1; p <= 15; ++p) if (group & (1u << p)) selected[item][p] = value;
}
int DialogControlGetSelectedItem(int item, int player) { CHECK(item >= 0 && item < 256 && player >= 1 && player <= 15); return selected[item][player]; }
text StringExternal(const char* key) { return key; }
text StringToText(text value) { return value; }
text IntToText(int value) { return std::to_string(value); }
text FixedToText(fixed value, int) { return std::to_string(value); }
text StringSub(text value, int from, int to) {
    if (from < 1 || to < from || from > int(value.size())) return "";
    return value.substr(from - 1, to - from + 1);
}
fixed MinF(fixed a, fixed b) { return std::min(a, b); }
fixed MaxF(fixed a, fixed b) { return std::max(a, b); }
int Color(double, double, double) { return 0; }
text SoundLink(const char* name, int) { return name; }
void gf_CBSystemMessage(text value, int, int, int, text, int) { messages.push_back(value); }
void TriggerEnable(int, bool) {}
void Wait(double, int) {} // Explicit no scheduler; event callbacks run synchronously.
void DialogControlAddItem(int, playergroup, text) {}
void DialogControlRemoveItem(int, playergroup, int) {}
void DialogControlSetVisible(int, playergroup, bool) {}
void libNtve_gf_SetDialogItemText(int, text, playergroup) {}
void libNtve_gf_SetDialogItemCurrentValue(int, fixed, playergroup) {}
void libNtve_gf_SetDialogItemMaximumValue(int, fixed, playergroup) {}
void gf_BHRoleOptPaint() {} // Unrelated option-checkbox rendering, never add/uniqueness.
void gf_XRSyncChecks() {} // Unrelated global-rule checkbox rendering.
''' + headers + '\n' + code + r'''
struct Slot { int pool, role; };
const std::array<Slot,12> leaders = {{{2,2},{2,17},{2,18},{2,19},{2,22},{4,21},
                                     {5,2},{5,17},{5,18},{5,19},{5,22},{4,22}}};
const int menuRows[][3] = {
''' + menu_rows + r'''
};
int expectedPool(Slot slot) {
    if (slot.pool == 4) return slot.role == 21 ? 2 : slot.role == 22 ? 5 : 0;
    if ((slot.pool == 2 || slot.pool == 5) && (slot.role == 2 || slot.role == 17 || slot.role == 18 || slot.role == 19 || slot.role == 22)) return slot.pool;
    return 0;
}
void put(int seat, Slot slot) { gv_categoriesArray[seat] = slot.pool; gv_rolesArray[seat] = slot.role; }
void choose(Slot slot) { gv_roleCategory = slot.pool; gv_roleSelection = slot.role; }
int menuIndex(Slot slot) {
    for (const auto& row : menuRows) if (row[0] == slot.pool && row[1] == slot.role) return row[2];
    CHECK(false); return 0;
}
void reset() {
''' + resets + r'''
    clearValue(enabled); clearValue(selected); messages.clear();
    eventPlayer = gv_host = 1;
    gv_variantSelection = 3;
    gv_players = gv_currentPlayers = PlayerGroupAll();
    for (int i = 0; i < 10; ++i) gv_rolesMenusItem[i] = 20 + i;
    for (int i = 0; i < 14; ++i) gv_rolePanelItem[i] = 50 + i;
    for (int p = 1; p <= 5; ++p) for (int r = 1; r <= 37; ++r) {
        gv_roleNameArray[p][r] = "role";
        gv_roleDescriptionArray[p][r] = "description";
    }
}
void select(Slot slot) {
    choose(slot);
    eventControl = gv_rolesMenusItem[1];
    selected[eventControl][gv_host] = menuIndex(slot);
    CHECK(gt_OSRoleSelect_Func(true, true));
    CHECK(gv_roleCategory == slot.pool && gv_roleSelection == slot.role);
}
void clickAdd() {
    eventControl = gv_rolesMenusItem[3];
    CHECK(gt_OSRoleManipulate_Func(true, true));
}
void testMap() {
    for (int pool = -2; pool <= 10; ++pool) for (int role = -2; role <= 42; ++role) {
        ++scenarios;
        CHECK(gf_BHLeaderSlotPool(pool, role) == expectedPool({pool,role}));
    }
}
void testPairs() {
    for (auto first : leaders) for (auto second : leaders) for (bool stale : {false,true}) {
        ++scenarios; reset();
        const bool blocked = expectedPool(first) == expectedPool(second);
        gv_rolesAssigned = 1; put(1, first);
        gv_bigRoleAssigned[0] = gv_bigRoleAssigned[5] = stale;
        CHECK(gf_BHLeaderAddBlocked(second.pool, second.role) == blocked);
        select(second);
        CHECK(enabled[gv_rolesMenusItem[3]][gv_host] == !blocked);
        // Invoke callback even when UI says disabled: business must recheck.
        clickAdd();
        CHECK(gv_rolesAssigned == (blocked ? 1 : 2));
        CHECK(gv_categoriesArray[1] == first.pool && gv_rolesArray[1] == first.role);
        if (!blocked) CHECK(gv_categoriesArray[2] == second.pool && gv_rolesArray[2] == second.role);
        CHECK(enabled[gv_rolesMenusItem[3]][gv_host] == false);
    }
}
void testRepeatedClicks() {
    for (auto leader : leaders) {
        ++scenarios; reset();
        select(leader); CHECK(enabled[gv_rolesMenusItem[3]][gv_host]);
        clickAdd(); CHECK(gv_rolesAssigned == 1);
        select(leader); CHECK(!enabled[gv_rolesMenusItem[3]][gv_host]);
        clickAdd(); CHECK(gv_rolesAssigned == 1);
    }
}
void testDeleteAndReadd() {
    for (auto first : leaders) for (auto second : leaders) {
        ++scenarios; reset();
        gv_rolesAssigned = 2; put(1, first); put(2, {1,1});
        gv_bigRoleAssigned[0] = gv_bigRoleAssigned[5] = true;
        choose(second); gv_playerSelection = 1;
        eventControl = gv_rolesMenusItem[4];
        CHECK(gt_OSRoleManipulate_Func(true,true));
        CHECK(gv_rolesAssigned == 1 && gv_categoriesArray[1] == 1);
        CHECK(enabled[gv_rolesMenusItem[3]][gv_host]);
        clickAdd();
        CHECK(gv_rolesAssigned == 2);
        CHECK(gv_categoriesArray[2] == second.pool && gv_rolesArray[2] == second.role);

        // Deleting an unrelated seat cannot unlock an occupied leader slot.
        reset(); gv_rolesAssigned = 2; put(1,first); put(2,{1,1});
        choose(first); gv_playerSelection = 2;
        eventControl = gv_rolesMenusItem[4];
        CHECK(gt_OSRoleManipulate_Func(true,true));
        CHECK(gv_rolesAssigned == 1);
        CHECK(!enabled[gv_rolesMenusItem[3]][gv_host]);
        clickAdd(); CHECK(gv_rolesAssigned == 1);

        if (expectedPool(first) == expectedPool(second)) {
            // A loaded invalid list remains blocked until its final duplicate goes.
            reset(); gv_rolesAssigned = 2; put(1,first); put(2,second);
            choose(second); gv_playerSelection = 1;
            eventControl = gv_rolesMenusItem[4];
            CHECK(gt_OSRoleManipulate_Func(true,true));
            CHECK(gv_rolesAssigned == 1);
            CHECK(!enabled[gv_rolesMenusItem[3]][gv_host]);
            clickAdd(); CHECK(gv_rolesAssigned == 1);
        }
    }
}
void testCheckAndLoad() {
    for (auto first : leaders) for (auto second : leaders) for (bool error : {false,true}) {
        ++scenarios; reset();
        const bool valid = expectedPool(first) != expectedPool(second);
        gv_rolesAssigned = 2; put(1, first); put(2, second);
        // No presence bits: confirm may not depend on stale flag10 caches.
        CHECK(gf_OSCheckOptionsB(error) == valid);
        CHECK(messages.empty() == (valid || !error));
        if (!valid && error) CHECK(messages.front() == (expectedPool(first) == 2 ? "Param/Value/BHLEADERDUP2" : "Param/Value/BHLEADERDUP5"));

        reset();
        gv_bankSaveIntegers[0][1][1] = first.pool; gv_bankSaveIntegers[0][0][1] = first.role;
        gv_bankSaveIntegers[0][1][2] = second.pool; gv_bankSaveIntegers[0][0][2] = second.role;
        gf_VLoadSaveSlot(0,5); // Actual bank loader: do not silently remove roles.
        CHECK(gv_rolesAssigned == 2);
        CHECK(gv_categoriesArray[1] == first.pool && gv_rolesArray[1] == first.role);
        CHECK(gv_categoriesArray[2] == second.pool && gv_rolesArray[2] == second.role);
        CHECK(gf_OSCheckOptionsB(error) == valid);
        select(first);
        CHECK(!enabled[gv_rolesMenusItem[3]][gv_host]);
        clickAdd(); CHECK(gv_rolesAssigned == 2);
    }
}
void testBoundaries() {
    for (auto leader : leaders) {
        ++scenarios; reset();
        gv_rolesAssigned = 15; put(15,leader);
        CHECK(gf_BHLeaderAddBlocked(leader.pool, leader.role));
        gv_rolesAssigned = 14;
        CHECK(!gf_BHLeaderAddBlocked(leader.pool, leader.role));
        gv_rolesAssigned = 0;
        CHECK(!gf_BHLeaderAddBlocked(leader.pool, leader.role));
        for (Slot nonleader : {Slot{1,22},Slot{3,22},Slot{4,1},Slot{4,3},Slot{4,15},Slot{2,1},Slot{5,21}}) {
            CHECK(!gf_BHLeaderAddBlocked(nonleader.pool,nonleader.role));
        }
        // Corrupt over-count is capped before indexing [16].
        gv_rolesAssigned = 100;
        CHECK(gf_BHLeaderAddBlocked(leader.pool,leader.role));
    }
    for (bool stale : {false,true}) {
        ++scenarios; reset(); gv_rolesAssigned = 2;
        put(1,{2,1}); put(2,{2,1});
        gv_bigRoleAssigned[0] = gv_bigRoleAssigned[5] = stale;
        CHECK(gf_OSCheckOptionsB(false)); // Ordinary duplicates still permitted.
        choose({4,3}); clickAdd(); CHECK(gv_rolesAssigned == 3);
    }
    ++scenarios; reset(); choose({4,21});
    eventPlayer = 2; eventControl = gv_rolesMenusItem[3];
    CHECK(!gt_OSRoleManipulate_Func(true,true)); CHECK(gv_rolesAssigned == 0);
    eventPlayer = 1;
    CHECK(gt_OSRoleManipulate_Func(true,false)); CHECK(gv_rolesAssigned == 0);
    for (int variant : {1,4,8,9,10,11,12,14,31,32,33,35,36,37,38,39,40,41}) {
        gv_variantSelection = variant;
        CHECK(!gt_OSRoleManipulate_Func(true,true)); CHECK(gv_rolesAssigned == 0);
    }
}
int main() {
    testMap(); testPairs(); testRepeatedClicks(); testDeleteAndReadd(); testCheckAndLoad(); testBoundaries();
    std::cout << "PASS leader uniqueness: " << scenarios << " scenarios, " << checks
              << " checks; actual helpers + full select/add/delete/CheckOptionsB/bank-load; UI/fixed boundary doubles; UBSan/bounds\n";
}
'''


def run(source: str, directory: Path, label: str) -> subprocess.CompletedProcess[str]:
    cpp, binary = directory / f'{label}.cpp', directory / label
    cpp.write_text(harness(source))
    subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                    '-fno-sanitize-recover=all', str(cpp), '-o', str(binary)], check=True)
    return subprocess.run([str(binary)], capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--mutation-self-test', action='store_true')
    args = parser.parse_args()
    source = args.script.read_text()
    with tempfile.TemporaryDirectory(prefix='bh-leader-unique-') as temporary:
        directory = Path(temporary)
        result = run(source, directory, 'actual')
        print(result.stdout, end='')
        if result.returncode:
            raise SystemExit(result.stderr or result.returncode)

        if args.mutation_self_test:
            variants = {}
            for name, value in [('gf_BHLeaderSlotPool', '0'), ('gf_BHLeaderAddBlocked', 'false')]:
                original = function(source,name)
                replacement = original.split('{',1)[0] + '{ return ' + value + '; }'
                variants[name] = source.replace(original,replacement,1)

            call = 'gf_BHLeaderAddBlocked(gv_roleCategory, gv_roleSelection)'
            for name, count in [('gt_OSRoleManipulate_Func',3), ('gt_OSRoleSelect_Func',1)]:
                owner = function(source,name)
                positions = [m.start() for m in re.finditer(re.escape(call),owner)]
                assert len(positions) == count, ('UI/add integration changed',name,len(positions))
                for index, position in enumerate(positions):
                    broken = owner[:position] + 'false' + owner[position + len(call):]
                    variants[f'{name}_{index}'] = source.replace(owner,broken,1)

            owner = function(source,'gf_OSCheckOptionsB')
            broken = re.sub(r'gf_BHLeaderSlotPool\([^()]*\)', '0', owner)
            assert broken != owner
            variants['confirm'] = source.replace(owner,broken,1)
            for label, mutant in variants.items():
                rejected = run(mutant,directory,label)
                assert rejected.returncode != 0, ('accepted mutation',label)
                assert 'FAIL line' in rejected.stderr, ('not business assertion rejection',label,rejected.stderr)
                print(f'PASS mutation {label}: compiled and rejected by actual-function business assertion')


if __name__ == '__main__':
    main()
