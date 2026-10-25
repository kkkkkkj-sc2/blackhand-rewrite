#!/usr/bin/env python3
"""Execute actual Baron/Taidou option defaults, helpers and whole click handler.

Only Galaxy declaration syntax is translated to C++; engine event/checkbox APIs
are explicit doubles. Also verify final setup ordering, four-part registration,
role specs and shipping label keys. This is not an SC2 compiler/rendering test.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import tempfile
from pathlib import Path

from test_egun import ROOT, SCRIPT, function, mask, translate

NAMES = (
    'gf_DefaultRoleOptions', 'gf_BRNormalizeOptions', 'gf_BROptionClick',
    'gf_ZJNormalizeOptions', 'gf_ZJOptionClick', 'gt_OSCheckboxes_Func',
)


def integration(source: str) -> str:
    init = function(source, 'gf_InitializeVariables')
    defaults = function(source, 'gf_DefaultRoleOptions')
    setup = function(source, 'auto_gf_OSComputeOptions_TriggerFunc')
    click = function(source, 'gt_OSCheckboxes_Func')
    assert setup.count('gf_BRNormalizeOptions();') == 1
    assert setup.index('gf_DefaultRoleOptions();') < setup.index('gf_BRNormalizeOptions();') < setup.index('gf_OSGenerateChances();') < setup.index('gf_BRReplaceSlots();')
    assert click.index('gv_roleOptions[gv_roleCategory][gv_roleSelection][lv_bit] = false;') < click.index('gf_BROptionClick();')
    for name in NAMES[1:3]:
        header = function(source, name).split('{', 1)[0].strip()
        assert header + ';' in source, ('missing forward declaration', name)

    labels = dict(line.split('=', 1) for line in (ROOT / 'work/blackhand/strings-baron.txt').read_text().splitlines() if line.startswith('Param/Value/'))
    build = ast.parse((ROOT / 'tools/boot2_build.py').read_text())
    must_have = next(ast.literal_eval(node.value) for node in build.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'MUST_HAVE_KEYS' for target in node.targets))
    assert labels['Param/Value/BRBOXMAX'] == '<n/>- 本局首夜招募人数上限：'
    assert 'Param/Value/BRBOXMAX' in must_have
    assert labels['Param/Value/BRLIMIT'] == '招募人数上限：'
    assert '至多3' not in labels['Param/Value/BRUSAGE']
    for name, key in (('gf_RTMafiaRoleText', 'NJBOX2'), ('gf_RTTriadRoleText', 'TDBOX2')):
        card = function(source, name)
        assert f'gv_roleBoxText[lv_a][2] = (StringExternal("Param/Value/{key}") + StringExternal("Param/Value/BRBOXMAX") + IntToText(gf_BRRecruitLimit(lv_a)));' in card
        assert '至多三个人' not in labels[f'Param/Value/{key}']

    registration = []
    for pool, spec_name in ((2, 'nanjue'), (5, 'taidou')):
        spec = json.loads((ROOT / f'roles/{spec_name}.json').read_text())
        expected = []
        for slot, count, cn in ((0, 2, '二'), (1, 3, '三'), (2, 4, '四')):
            key = f'BRMAX{count}'
            expected.append(dict(i=slot, exists=True, important=2, default=slot == 1, key=key))
            statements = (
                f'gv_roleOptionExists[{pool}][22][{slot}] = true;',
                f'gv_roleOptionsImportant[{pool}][22][{slot}] = 2;',
                f'gv_roleOptionsText[{pool}][22][{slot}] = StringExternal("Param/Value/{key}");',
            )
            for statement in statements:
                assert init.count(statement) == 1, statement
                registration.append(statement)

            assert f'gv_roleOptionAllowed[{pool}][22][{slot}] = true;' in defaults
            assert f'gv_roleOptions[{pool}][22][{slot}] = {str(slot == 1).lower()};' in defaults
            assert labels[f'Param/Value/{key}'] == f'可以招募{cn}人'
            assert f'Param/Value/{key}' in must_have

        assert spec['options'] == expected, spec_name

    print('PASS integration: both option registrations/specs/labels; forward declarations; final setup and actual click dispatch ordering', flush=True)
    return '\n'.join(registration)


def harness(source: str) -> str:
    registration = integration(source)
    bodies = [function(source, name) for name in NAMES]
    raw = '\n\n'.join(bodies)
    used = set(re.findall(r'\bgv_\w+', mask(raw + registration)))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not used - declarations.keys(), ('missing globals', used - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(used))
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    return r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <iostream>
#include <string>
using fixed = double;
using text = std::string;
using playergroup = unsigned int;
''' + globals_text + r'''
int eventPlayer = 1;
int eventControl = 0;
bool ui[16][256];
int writes[16][256];
int checks = 0;
#define CHECK(x) do { ++checks; if (!(x)) { std::cerr << "FAIL line " << __LINE__ << ": " << #x << '\n'; std::abort(); } } while (0)
int EventPlayer() { return eventPlayer; }
int EventDialogControl() { return eventControl; }
playergroup PlayerGroupAll() { return 0xfffe; }
playergroup PlayerGroupSingle(int p) { return 1u << p; }
bool PlayerGroupHasPlayer(playergroup g, int p) { return g & (1u << p); }
bool libNtve_gf_DialogItemIsChecked(int item, int p) { return ui[p][item]; }
void libNtve_gf_SetDialogItemChecked(int item, bool checked, playergroup group) {
    CHECK(item >= 0 && item < 256);
    for (int p = 1; p <= 15; ++p) if (PlayerGroupHasPlayer(group, p)) {
        ui[p][item] = checked;
        ++writes[p][item];
    }
}
void DialogControlSetVisible(int, playergroup, bool) {}
text StringExternal(const char* key) { return key; }
''' + headers + '\n' + translate(raw) + r'''
void registration() {
''' + registration + r'''
}
void setMask(int pool, int bits) {
    for (int bit = 0; bit < 3; ++bit) gv_roleOptions[pool][22][bit] = bits & (1 << bit);
}
int getMask(int pool) {
    int bits = 0;
    for (int bit = 0; bit < 3; ++bit) if (gv_roleOptions[pool][22][bit]) bits |= 1 << bit;
    return bits;
}
int expected(int bits) { return bits & 4 ? 4 : bits & 1 ? 1 : 2; }
void reset() {
    gf_DefaultRoleOptions();
    registration();
    eventPlayer = gv_host = 1;
    gv_variantSelection = 3;
    gv_roleCategory = 2;
    gv_roleSelection = 22;
    gv_currentPlayers = PlayerGroupAll();
    for (int row = 0; row < 5; ++row) {
        gv_roleOptBox[row] = 100 + row;
        gv_roleOptShown[row] = -1;
    }
    for (int item = 0; item < 32; ++item) gv_optionsPanelItem[item] = 150 + item;
    for (int p = 0; p < 16; ++p) for (int item = 0; item < 256; ++item) {
        ui[p][item] = false;
        writes[p][item] = 0;
    }
}
int main() {
    reset();
    for (int pool : {2, 5}) {
        CHECK(getMask(pool) == 2);
        for (int bit = 0; bit < 3; ++bit) {
            CHECK(gv_defaultRoleOptions[pool][22][bit] == (bit == 1));
            CHECK(gv_roleOptionAllowed[pool][22][bit]);
            CHECK(gv_roleOptionExists[pool][22][bit]);
            CHECK(gv_roleOptionsImportant[pool][22][bit] == 2);
        }
    }
    for (int a = 0; a < 8; ++a) for (int b = 0; b < 8; ++b) {
        setMask(2, a);
        setMask(5, b);
        gv_roleOptions[2][21][0] = true;
        gv_roleOptions[2][22][10] = true;
        gf_BRNormalizeOptions();
        CHECK(getMask(2) == expected(a));
        CHECK(getMask(5) == expected(b));
        CHECK(gv_roleOptions[2][21][0] && gv_roleOptions[2][22][10]);
        gf_BRNormalizeOptions();
        CHECK(getMask(2) == expected(a) && getMask(5) == expected(b));
    }

    // All 24 visible row permutations: slot != row, including an empty row.
    std::array<int, 4> layout = {-1, 0, 1, 2};
    do {
        for (int pool : {2, 5}) for (int selected = 0; selected < 3; ++selected)
        for (int row = 0; row < 4; ++row) for (bool checked : {false, true}) {
            reset();
            gv_roleCategory = pool;
            setMask(pool, 1 << selected);
            for (int i = 0; i < 4; ++i) gv_roleOptShown[i] = layout[i];
            eventControl = gv_roleOptBox[row];
            ui[gv_host][eventControl] = checked;
            CHECK(gt_OSCheckboxes_Func(true, true));
            const int bit = layout[row];
            const int result = bit < 0 ? (1 << selected) : checked ? (1 << bit) : expected((1 << selected) & ~(1 << bit));
            CHECK(getMask(pool) == result);
            CHECK(getMask(pool == 2 ? 5 : 2) == 2);
            if (bit >= 0) for (int i = 0; i < 4; ++i) if (layout[i] >= 0) {
                for (int p = 1; p <= 15; ++p) {
                    CHECK(writes[p][gv_roleOptBox[i]] > 0);
                    CHECK(ui[p][gv_roleOptBox[i]] == bool(result & (1 << layout[i])));
                }
            }
        }
    } while (std::next_permutation(layout.begin(), layout.end()));

    // Generic handler guards must still guard the new mutually exclusive helper.
    for (int variant : {1, 8, 9, 10}) {
        reset();
        gv_variantSelection = variant;
        gv_roleOptShown[3] = 2;
        eventControl = gv_roleOptBox[3];
        ui[1][eventControl] = true;
        gt_OSCheckboxes_Func(true, true);
        CHECK(getMask(2) == 2);
    }
    reset();
    gv_roleOptShown[0] = 2;
    eventControl = gv_roleOptBox[0];
    ui[1][eventControl] = true;
    gv_roleOptionAllowed[2][22][2] = false;
    gt_OSCheckboxes_Func(true, true);
    CHECK(getMask(2) == 2);
    gv_roleOptionAllowed[2][22][2] = true;
    eventPlayer = 2;
    CHECK(!gt_OSCheckboxes_Func(true, true));
    CHECK(getMask(2) == 2);
    eventPlayer = 1;
    CHECK(gt_OSCheckboxes_Func(true, false));
    CHECK(getMask(2) == 2);
    for (int pool : {1, 3, 4}) {
        gv_roleCategory = pool;
        gf_BROptionClick();
        CHECK(getMask(2) == 2 && getMask(5) == 2);
    }
    gv_roleCategory = 2;
    gv_roleSelection = 21;
    gf_BROptionClick();
    CHECK(getMask(2) == 2 && getMask(5) == 2);
    std::cout << "PASS actual defaults/normalization/whole click handler: " << checks << " assertions (UBSan + bounds)\n";
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    code = harness(args.script.read_text())
    with tempfile.TemporaryDirectory(prefix='baron-options-') as temp:
        cpp, binary = Path(temp) / 'options.cpp', Path(temp) / 'options'
        cpp.write_text(code)
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
