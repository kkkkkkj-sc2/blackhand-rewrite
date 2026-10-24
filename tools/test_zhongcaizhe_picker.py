#!/usr/bin/env python3
"""Execute actual 仲裁者 picker source with C++17 UBSan/bounds and UI doubles.

--script selects integrated Galaxy source. Tests logical coordinates, text and
internal player identity, not SC2 compilation/rendering or live mouse delivery.
Confirm/fate settlement is outside this regression; unrelated helpers are stubs.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / 'work/blackhand/CustomLogic.galaxy'
NAMES = ('gf_ZCRefreshPick', 'gf_ZCToggle', 'gt_ZCClick_Func')


def mask(source: str) -> str:
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), source)


def function(source: str, name: str) -> str:
    live = mask(source)
    match = re.search(r'^(?:void|bool)\s+' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', live, re.M)
    assert match, f'missing function {name}'
    depth, end = 1, match.end()
    while depth:
        assert end < len(live), f'unbalanced function {name}'
        depth += (live[end] == '{') - (live[end] == '}')
        end += 1

    return source[match.start():end]


PREFIX = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <iostream>
#include <numeric>
#include <random>
#include <string>
#include <tuple>
#include <vector>
using string = std::string;
using text = string;
using playergroup = unsigned int;
'''

STUBS = r'''
struct Control {
    bool shown = false;
    int x = -999, y = -999, anchor = -999;
    string label;
    bool operator==(const Control& b) const {
        return std::tie(shown, x, y, anchor, label) == std::tie(b.shown, b.x, b.y, b.anchor, b.label);
    }
};
std::array<std::array<Control, 16>, 16> ui;
int eventPlayer, eventControl, notices;
const int c_anchorTop = 5;

template<class T> void resetValue(T& value) { value = T{}; }
template<class T, size_t N> void resetValue(T (&values)[N]) {
    for (auto& value : values) resetValue(value);
}
int playerId(int handle) {
    for (int p = 1; p <= 15; ++p) if (gv_zcPickBtn[p] == handle) return p;
    assert(false && "unknown control handle");
    return 0;
}
bool PlayerGroupHasPlayer(playergroup group, int p) {
    assert(p >= 1 && p <= 15);
    return (group & (1u << p)) != 0;
}
int PlayerGroupSingle(int p) { assert(p >= 1 && p <= 15); return p; }
int EventPlayer() { return eventPlayer; }
int EventDialogControl() { return eventControl; }
int StringToInt(string value) { try { return std::stoi(value); } catch (...) { return 0; } }
text StringToText(string value) { return value; }
text StringExternal(string value) { return value; }
int SoundLink(string, int) { return 0; }
void gf_BHNotify(text, int, int) { ++notices; }
void DialogControlSetVisible(int handle, int viewer, bool shown) { ui.at(viewer).at(playerId(handle)).shown = shown; }
void DialogControlSetPosition(int handle, int viewer, int anchor, int x, int y) {
    auto& control = ui.at(viewer).at(playerId(handle));
    control.anchor = anchor; control.x = x; control.y = y;
}
void libNtve_gf_SetDialogItemText(int handle, text label, int viewer) { ui.at(viewer).at(playerId(handle)).label = label; }
void gf_ZCApply(int, int, int, int, int) { assert(false && "confirm outside test"); }
void DialogSetVisible(int, int, bool) { assert(false && "confirm outside test"); }
'''

TESTS = r'''
void fixture(const std::array<int, 15>& floors) {
    clearGlobals();
    ui = {};
    notices = 0;
    gv_alivePlayers = 0xfffeu;
    gv_zcUiReady = true;
    gv_zcFateLive = 901; gv_zcFateDie = 902; gv_zcPickOk = 903;
    for (int p = 1; p <= 15; ++p) {
        gv_zcPickBtn[p] = 1000 + 37 * p;  // handles deliberately differ from floors/IDs
        gv_number[p] = std::to_string(floors[p - 1]);
        gv_name[p] = "name" + std::to_string(p);
    }
}
void draft(int viewer, std::vector<int> expected) {
    assert(gv_zcDraftN[viewer] == int(expected.size()));
    for (int i = 0; i < 3; ++i) assert(gv_zcDraft[viewer][i] == (i < int(expected.size()) ? expected[i] : 0));
}
void verify(int viewer) {
    for (int p = 1; p <= 15; ++p) {
        const auto& control = ui[viewer][p];
        assert(control.shown == PlayerGroupHasPlayer(gv_alivePlayers, p));
        if (!control.shown) continue;

        int floor = StringToInt(gv_number[p]);
        if (floor < 1 || floor > 15) floor = p;
        assert(control.anchor == c_anchorTop);
        assert(control.x == (floor % 2 ? -160 : 160));
        assert(control.y == 40 + 28 * ((floor - 1) / 2));
        bool selected = false;
        for (int id : gv_zcDraft[viewer]) selected |= id == p;
        assert(control.label == (selected ? "● " : "") + gv_number[p] + "." + gv_name[p]);
    }
}
void refresh(int viewer) {
    auto before = ui;
    gf_ZCRefreshPick(viewer);
    verify(viewer);
    for (int p = 0; p <= 15; ++p) if (p != viewer) assert(ui[p] == before[p]);
}
int atFloor(int viewer, int floor) {
    int found = 0;
    for (int p = 1; p <= 15; ++p) {
        const auto& c = ui[viewer][p];
        if (c.shown && c.x == (floor % 2 ? -160 : 160) && c.y == 40 + 28 * ((floor - 1) / 2)) {
            assert(found == 0); found = p;
        }
    }
    assert(found != 0);
    return found;
}

void click(int viewer, int target) {
    auto before = ui;
    eventPlayer = viewer;
    eventControl = gv_zcPickBtn[target];
    assert(gt_ZCClick_Func(false, true));
    verify(viewer);
    for (int p = 0; p <= 15; ++p) if (p != viewer) assert(ui[p] == before[p]);
}
int main() {
    std::array<int, 15> floors;
    std::iota(floors.begin(), floors.end(), 1);
    std::mt19937 rng(270315);
    int checks = 0;
    for (int permutation = 0; permutation < 34; ++permutation) {
        if (permutation == 1) std::reverse(floors.begin(), floors.end());
        if (permutation > 1) std::shuffle(floors.begin(), floors.end(), rng);
        fixture(floors);
        for (int viewer = 1; viewer <= 15; ++viewer) {
            refresh(viewer);
            for (int floor = 1; floor <= 15; ++floor) {
                int target = std::find(floors.begin(), floors.end(), floor) - floors.begin() + 1;
                assert(atFloor(viewer, floor) == target);
                click(viewer, atFloor(viewer, floor)); draft(viewer, {target});
                click(viewer, atFloor(viewer, floor)); draft(viewer, {});
                ++checks;
            }

            // Maximum three, removing the middle compacts IDs, then append fourth.
            click(viewer, 2); click(viewer, 5); click(viewer, 12);
            draft(viewer, {2, 5, 12});
            int oldNotices = notices;
            click(viewer, 9); draft(viewer, {2, 5, 12});
            assert(notices == oldNotices + 1);
            click(viewer, 5); draft(viewer, {2, 12});
            click(viewer, 9); draft(viewer, {2, 12, 9});
            click(viewer, 2); click(viewer, 12); click(viewer, 9);

            // Leave a distinct persistent draft while subsequent viewers interact.
            int retained = viewer % 15 + 1;
            click(viewer, retained); draft(viewer, {retained});
            for (int prior = 1; prior <= viewer; ++prior) draft(prior, {prior % 15 + 1});
            ++checks;
        }

        // Sparse alive floors keep holes, not compacted rows; hide existing controls.
        for (int p = 1; p <= 15; ++p) if (floors[p - 1] % 2) gv_alivePlayers &= ~(1u << p);
        refresh(1);
        gv_zcDraftN[1] = 0;
        for (int& id : gv_zcDraft[1]) id = 0;
        refresh(1);
        for (int p = 1; p <= 15; ++p) if (!PlayerGroupHasPlayer(gv_alivePlayers, p)) {
            click(1, p); draft(1, {}); ++checks;
        }

        // Current floor/name swaps move and relabel the existing ID-backed control.
        fixture(floors);
        refresh(1); refresh(2); click(1, 3);
        std::swap(gv_number[3], gv_number[12]);
        std::swap(gv_name[3], gv_name[12]);
        refresh(1); draft(1, {3});
        click(1, 3); draft(1, {});
        click(1, 12); draft(1, {12});
        ++checks;
    }

    // Invalid floors fall back to the internal player's safe 1..15 slot.
    for (int p = 1; p <= 15; ++p) for (string invalid : {"0", "16", "-2", "999", ""}) {
        fixture(floors);
        gv_number[p] = invalid;
        refresh(1); click(1, p); draft(1, {p}); ++checks;
    }

    fixture(floors); refresh(1);
    gv_diedAtNight[8] = true;
    click(1, 8); draft(1, {});
    eventPlayer = 1; eventControl = gv_zcPickBtn[7];
    assert(gt_ZCClick_Func(false, false)); draft(1, {});
    gv_zcUiReady = false;
    assert(gt_ZCClick_Func(false, true)); draft(1, {});
    std::cout << "PASS " << checks << " picker layout/identity scenarios; selection callback guards\n";
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    source = parser.parse_args().script.read_text()
    bodies = [function(source, name) for name in NAMES]
    callback = mask(bodies[2])
    assert re.search(r'if\s*\(\(EventDialogControl\(\) == gv_zcPickBtn\[lv_i\]\)\)\s*\{\s*gf_ZCToggle\(lv_p, lv_i\);', callback), \
        'callback must map the control handle to internal ID, never displayed floor'
    required = set(re.findall(r'\bgv_\w+', mask('\n'.join(bodies))))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not required - declarations.keys(), ('missing globals', required - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(required))
    reset = 'void clearGlobals() {\n' + ''.join(f'    resetValue({name});\n' for name in sorted(required)) + '}\n'
    definitions = re.sub(r'\b(int|bool|text|string)((?:\[\d+\])+)\s+(\w+)', r'\1 \3\2', '\n\n'.join(bodies))
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'C++17 compiler required'
    for name, body in zip(NAMES, bodies):
        first = source.count('\n', 0, source.index(body)) + 1
        print(f'{name}: lines {first}..{first + body.count(chr(10))}', flush=True)

    with tempfile.TemporaryDirectory(prefix='zc-picker-test-') as directory:
        cpp, binary = Path(directory) / 'test.cpp', Path(directory) / 'test'
        cpp.write_text(PREFIX + globals_text + STUBS + reset + definitions + TESTS)
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
