#!/usr/bin/env python3
"""Execute the complete actual gf_OSCheckOptionsA in a C++17 stub harness.

Requires g++; enables undefined/bounds sanitizers. Only engine calls and the
external B/C checks are stubbed (B/C return true to isolate A). A's player count,
role-list count, option marking and opposing-faction logic execute unchanged.
This is not an SC2 compiler/rendering test. Fixed leaders in pools 2/5 already
work; the regression concerns random leader slots (4,21) and (4,22).

Use --script PATH to test another script, including a temporary git HEAD copy.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'


def extract_function(source: str) -> tuple[str, int, int]:
    """Balance braces while ignoring comments and strings; exclude prototypes."""
    tokens = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[{}]', re.S)
    match = re.search(r'^bool gf_OSCheckOptionsA\s*\(bool lp_error\)\s*\{', source, re.M)
    if match is None:
        raise AssertionError('missing gf_OSCheckOptionsA definition')

    depth = 0
    for token in tokens.finditer(source, match.end() - 1):
        if token.group() == '{':
            depth += 1
        elif token.group() == '}':
            depth -= 1
            if depth == 0:
                start, end = match.start(), token.end()
                return (source[start:end], source.count('\n', 0, start) + 1,
                        source.count('\n', 0, end) + 1)

    raise AssertionError('unbalanced gf_OSCheckOptionsA definition')


def harness(source: str) -> str:
    body, first, last = extract_function(source)
    print(f'Actual gf_OSCheckOptionsA: lines {first}-{last} ({last - first + 1} lines)', flush=True)
    # Syntax-only conversion; Galaxy initializes local arrays to zero, C++ does not.
    body = re.sub(r'\b(int|bool)((?:\[\d+\])+)( +)(\w+);', r'\1\3\4\2{};', body)
    used = set(re.findall(r'\bgv_\w+', body))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims}{{}};'

    if used - declarations.keys():
        raise AssertionError(('missing global declarations', used - declarations.keys()))

    globals_text = '\n'.join(declarations[name] for name in sorted(used))
    resets = '\n'.join(f'    clearValue({name});' for name in sorted(used))
    return r'''
#include <algorithm>
#include <cassert>
#include <initializer_list>
#include <iostream>
#include <string>
#include <utility>
#include <vector>
using std::string;
using playergroup = unsigned int;
using Role = std::pair<int, int>; // category, role
struct Message { string key; int player; };
std::vector<Message> messages;
std::vector<string> downstream;
bool expectedError = false;
int failures = 0, scenarios = 0, checks = 0;
string context;

void require(bool condition, const string &reason) {
    ++checks;
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << context << ": " << reason << '\n';
    }
}

template<class T> void clearValue(T &value) { value = T{}; }
template<class T, size_t N> void clearValue(T (&value)[N]) {
    for (auto &element : value) clearValue(element);
}
int PlayerGroupCount(playergroup group) {
    int count = 0;
    for (int player = 1; player <= 15; ++player) count += (group >> player) & 1U;
    return count;
}
int PlayerGroupNextPlayer(playergroup group, int previous) {
    for (int player = std::max(1, previous + 1); player <= 15; ++player) {
        if (group & (1U << player)) return player;
    }
    return -1;
}
string StringExternal(const string &key) { return key; }
int SoundLink(const string &, int) { return 0; }
int Color(double, double, double) { return 0; }
void gf_CBSystemMessage(const string &key, int player, int, int, int, int) {
    messages.push_back({key, player});
}
// Deliberately do NOT execute B/C: this suite measures A, not role-option
// compatibility or random-weight feasibility. Record their order/argument.
bool gf_OSCheckOptionsB(bool error) {
    require(error == expectedError, "B received wrong lp_error");
    downstream.push_back("B");
    return true;
}
bool gf_OSCheckOptionsC(bool error) {
    require(error == expectedError, "C received wrong lp_error");
    downstream.push_back("C");
    return true;
}
void gf_OSGenerateChances() { require(false, "unexpected variant6 generate branch"); }
void gf_OSSaveSlot(int) { require(false, "unexpected variant6 save branch"); }
''' + globals_text + '\n' + body + r'''

void reset() {
''' + resets + r'''
    messages.clear();
    downstream.clear();
    gv_variantSelection = 3; // Ordinary custom setup, never variant6 save mode.
    gv_soloTest = false;
    gv_host = 2;
    gv_players = gv_currentPlayers = (1U << 2) | (1U << 15);
    gv_rolesAssigned = PlayerGroupCount(gv_currentPlayers);
    // Verify the real initial clearing loop runs without touching other options.
    gv_roleOptions[8][20][10] = true;
    gv_roleOptions[8][20][9] = true;
}

void scenario(const string &label, Role first, Role second, bool valid,
              const string &errorKey = "Param/Value/9C14C2DE") {
    // Both ends of the real 1..15 list loop, and both role orders.
    for (bool tail : {false, true}) {
        for (bool error : {false, true}) {
            reset();
            expectedError = error;
            context = label + (tail ? " [slots15,14]" : " [slots1,2]")
                      + (error ? " [lp_error=true]" : " [lp_error=false]");
            ++scenarios;
            const int a = tail ? 15 : 1, b = tail ? 14 : 2;
            gv_categoriesArray[a] = first.first;
            gv_rolesArray[a] = first.second;
            gv_categoriesArray[b] = second.first;
            gv_rolesArray[b] = second.second;
            require(gv_rolesAssigned == 2 && PlayerGroupCount(gv_currentPlayers) == 2,
                    "fixture must assign exactly one role per current player");
            const bool actual = gf_OSCheckOptionsA(error);
            require(actual == valid, valid ? "A should accept opposing factions" : "A should reject setup");
            require(downstream == (valid ? std::vector<string>{"B", "C"} : std::vector<string>{}),
                    "B/C must run exactly once in order, only after valid A");
            require(!gv_roleOptions[8][20][10], "A must clear stale role-presence flag");
            require(gv_roleOptions[8][20][9], "A must preserve unrelated role options");
            for (Role role : {first, second}) {
                require(gv_roleOptions[role.first][role.second][10], "A must mark actual selected role");
            }

            const size_t expectedMessages = !valid && error ? 2 : 0;
            require(messages.size() == expectedMessages, "wrong error-message count");
            for (size_t i = 0; i < messages.size(); ++i) {
                require(messages[i].key == errorKey, "wrong error-message key: " + messages[i].key);
                require(messages[i].player == (i == 0 ? 2 : 15), "wrong error-message recipient");
            }
        }
    }
}

void bothOrders(const string &label, Role first, Role second, bool valid) {
    scenario(label, first, second, valid);
    scenario(label + " reversed", second, first, valid);
}

int main() {
    const Role town{1, 1}, mafiaLeaderRandom{4, 21}, triadLeaderRandom{4, 22};
    bothOrders("town + mafia leader random(4,21)", town, mafiaLeaderRandom, true);
    bothOrders("town + triad leader random(4,22)", town, triadLeaderRandom, true);
    bothOrders("opposing leader random slots", mafiaLeaderRandom, triadLeaderRandom, true);

    scenario("pure town", town, {1, 2}, false);
    scenario("pure fixed mafia", {2, 3}, {2, 17}, false);
    scenario("pure fixed triad", {5, 3}, {5, 17}, false);
    scenario("pure mafia leader random", mafiaLeaderRandom, mafiaLeaderRandom, false);
    scenario("pure triad leader random", triadLeaderRandom, triadLeaderRandom, false);

    // Fixed leaders (2/17/18/19/22) are classified by their actual pool.
    // Role 3 is an ordinary crime role, retained as another control.
    for (int pool : {2, 5}) {
        for (int role : {2, 3, 17, 18, 19, 22}) {
            const string label = (role == 3 ? "fixed crime role(" : "fixed leader(")
                                 + std::to_string(pool) + "," + std::to_string(role) + ")";
            bothOrders("town + " + label, town, {pool, role}, true);
            scenario("pure " + label, {pool, role}, {pool, role}, false);
        }
    }

    // Existing crime random slots must still identify exactly their own faction.
    for (int role : {3, 9, 10, 11}) {
        const Role random{4, role};
        const string label = "old mafia random(4," + std::to_string(role) + ")";
        bothOrders("town + " + label, town, random, true);
        bothOrders("same-faction " + label, mafiaLeaderRandom, random, false);
        bothOrders("opposing " + label, triadLeaderRandom, random, true);
        for (int triadRole : {15, 16, 17, 18}) {
            bothOrders(label + " + old triad random(4," + std::to_string(triadRole) + ")",
                       random, {4, triadRole}, true);
        }
    }

    for (int role : {15, 16, 17, 18}) {
        const Role random{4, role};
        const string label = "old triad random(4," + std::to_string(role) + ")";
        bothOrders("town + " + label, town, random, true);
        bothOrders("same-faction " + label, triadLeaderRandom, random, false);
        bothOrders("opposing " + label, mafiaLeaderRandom, random, true);
    }

    // Keep rolesAssigned == player count even in malformed-list fixtures. This
    // exercises A's real list-count rejection before any faction/B/C validation.
    scenario("missing category in two-player list", town, {0, 3}, false, "Param/Value/A887F1ED");
    std::cout << (failures ? "FAIL: " : "PASS: ") << scenarios << " scenarios, "
              << checks << " checks, " << failures << " failures; complete actual A; "
              << "B/C isolated; lp_error both ways; UBSan/bounds enabled" << std::endl;
    return failures ? 1 : 0;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT, help='Galaxy script to extract A from')
    args = parser.parse_args()
    code = harness(args.script.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='bh-start-factions-') as tmp:
        cpp, exe = Path(tmp) / 'start_factions.cpp', Path(tmp) / 'start_factions'
        cpp.write_text(code, encoding='utf-8')
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
