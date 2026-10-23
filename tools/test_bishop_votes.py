#!/usr/bin/env python3
"""Execute real Galaxy vote handlers/snapshots in a C++17 engine-stub harness.

Includes every nomination mode, both skip paths, real trial/fake-death choices,
full disconnect/AFK callbacks, forced withdrawal, and reset functions. SC2 UI,
engine scheduling, compilation, and bishop night settlement are not simulated.
Support globals and all tested handlers are required to exist in the source.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'


def balanced_end(source: str, start: int) -> int:
    depth = 0
    tokens = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[{}]', re.S)
    for match in tokens.finditer(source, start):
        if match.group() == '{':
            depth += 1
        elif match.group() == '}':
            depth -= 1
            if depth == 0:
                return match.end()

    raise AssertionError('unbalanced Galaxy block')


def function(source: str, name: str) -> str:
    match = re.search(r'^(?:void|bool|int) ' + re.escape(name) + r'\s*\([^;\n]*\)\s*\{', source, re.M)
    assert match, name
    return source[match.start():balanced_end(source, source.index('{', match.start()))]


def audit(source: str) -> None:
    owners = []
    for match in re.finditer(r'^(?:void|bool|int) (\w+)\s*\([^;\n]*\)\s*\{', source, re.M):
        body = source[match.start():balanced_end(source, source.index('{', match.start()))]
        for line in body.splitlines():
            if 'gv_votes[' in line and not re.search(r'gv_votes\[.*?\]\s*=(?!=)', line):
                owners.append(match.group(1))

    assert sorted(owners) == ['gf_BHVoteWeight', 'gf_JSHeroDay', 'gf_JSHeroRestore'], owners
    for name in ['gt_DetectLeave_Func', 'gt_ADAntiAFKPeriod_Func']:
        body = function(source, name)
        assert body.count('gf_BHWithdrawVotes(lv_a);') == (2 if name == 'gt_DetectLeave_Func' else 1), name
        assert 'gv_skipVotes -= 1' not in body and 'gv_voteCount[' not in body, name
    assert 'gv_bhTrialWeight' not in function(source, 'gf_ASStopVote'), 'StopVote must preserve deferred secret votes'
    tally = function(source, 'auto_gf_TrialVoteResults_TriggerFunc')
    assert 'lv_sg += gv_bhTrialWeight[lv_a];' in tally
    assert 'lv_si += gv_bhTrialWeight[lv_a];' in tally
    assert function(source, 'gt_ASVote_Func').count('= gf_BHVoteWeight(EventPlayer());') == 6
    assert function(source, 'gt_ASTrialVote_Func').count('= gf_BHVoteWeight(EventPlayer());') == 4
    for name in ['gf_ASTrialVote', 'gf_ASStartVote', 'gf_ASTieVote', 'gf_ASEndActions']:
        body = function(source, name)
        for kind in ['Nomination', 'Trial', 'Skip']:
            assert f'gv_bh{kind}Weight[lv_a] = 0;' in body, (name, kind)
        assert 'gv_zjSupport' not in body, name


def build_harness(source: str) -> str:
    names = [
        'gf_BHVoteWeight', 'gf_BHWithdrawVotes', 'gt_ASVote_Func',
        'gt_ASTrialVote_Func', 'gt_ASSkipButton_Func', 'gt_ASSkip_Func',
        'gf_ASTrialVote', 'gf_ASStartVote', 'gf_ASTieVote', 'gf_ASEndActions',
        'gf_ASStopVote', 'gt_DetectLeave_Func', 'gt_ADAntiAFKPeriod_Func',
        'auto_gf_ASE692A4E7A5A8EFBC81_TriggerFunc',
    ]
    bodies = [function(source, name) for name in names]
    tally = function(source, 'auto_gf_TrialVoteResults_TriggerFunc')
    a = tally.index('    lv_sg = 0;')
    b = tally.index('    if ((lv_si > 0))', a)
    # Compile the exact deferred tally block, not a Python model of it.
    bodies.append('void secretTally () {\n    int lv_sg;\n    int lv_si;\n    int lv_a;\n'
                  + '\n'.join(line for line in tally.splitlines() if re.match(r'    const int autoBZSEC_(?:ae|ai) = ', line))
                  + '\n' + tally[a:b] + '\n}')
    code = '\n\n'.join(bodies)
    code = re.sub(r'\b(int|bool|text|string|fixed)((?:\[\d+\])+)( +)(\w+)', r'\1\3\4\2', code)
    code = re.sub(r'(?m)^(\s*)(int|bool|text|string|fixed|playergroup|unit|trigger) (\w+(?:\[\d+\])*)\s*;', r'\1\2 \3 = {};', code)
    used = set(re.findall(r'\b(?:gv_|gt_|auto_gf_)\w+', code))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +((?:gv_|gt_|auto_gf_)\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = (kind, dims)
    defined = set(re.findall(r'^(?:void|bool|int) (\w+)\s*\(', code, re.M))
    used -= defined
    assert not used - declarations.keys(), used - declarations.keys()
    globals_text = '\n'.join(f'{declarations[name][0]} {name}{declarations[name][1]};' for name in sorted(used))
    reset = '\n'.join(f'    clearValue({name});' for name in sorted(used))
    types = {kind for kind, _ in declarations.values()} - {'void', 'bool', 'int', 'string', 'text', 'fixed'}
    aliases = '\n'.join(f'using {kind} = int;' for kind in sorted(types))
    headers = '\n'.join(body[:body.index('{')] + ';' for body in bodies)
    calls = set(re.findall(r'\b(\w+)\s*\(', re.sub(r'//[^\n]*|"(?:\\.|[^"\\])*"', '', code)))
    native = {
        'EventPlayer', 'EventDialogControl', 'PlayerGroupAll', 'PlayerGroupSingle',
        'PlayerGroupHasPlayer', 'PlayerGroupNextPlayer', 'PlayerGroupRemove', 'PlayerGroupCount',
        'PlayerStatus', 'PlayerName', 'StringExternal', 'StringToText', 'IntToText',
        'TextWithColor', 'StringLength', 'IntToFixed', 'FixedToInt', 'CeilingI', 'ModI',
        'MaxF', 'RandomInt', 'TriggerIsEnabled', 'DialogControlIsVisible',
        'libNtve_gf_SetDialogItemImage', 'libNtve_gf_SetDialogItemImage2',
    }
    stubs = '\n'.join(f'template<class... A> int {name}(A... args) {{ ++calls["{name}"]; return 0; }}'
                      for name in sorted(calls - defined - native - {'if', 'else', 'for', 'while', 'return'}))
    constants = '\n'.join(f'constexpr int {name} = {i};' for i, name in enumerate(sorted(set(re.findall(r'\b(?:c_|ge_)\w+', code)) - {'c_bhSoloBuild'}), 1))
    return r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <map>
#include <string>
#include <vector>
using std::string;
using text = string;
using fixed = double;
constexpr int null = 0;
constexpr bool c_bhSoloBuild = false;
''' + aliases + '\n' + constants + '\n' + globals_text + r'''
std::map<string, int> calls;
int eventPlayer = 1, eventControl = 0;
int statuses[16];
std::vector<int> changedImageIds;
template<class T> void clearValue(T &x) { x = {}; }
template<class T, size_t N> void clearValue(T (&x)[N]) { for (auto &v: x) clearValue(v); }
int EventPlayer() { return eventPlayer; }
int EventDialogControl() { return eventControl; }
int PlayerGroupAll() { return 65534; }
int PlayerGroupSingle(int p) { return 1 << p; }
bool PlayerGroupHasPlayer(int g, int p) { assert(p >= 0 && p <= 15); return (g & (1 << p)) != 0; }
int PlayerGroupNextPlayer(int g, int p) { for (++p; p < 16; ++p) if (PlayerGroupHasPlayer(g, p)) return p; return -1; }
void PlayerGroupRemove(int &g, int p) { g &= ~(1 << p); }
int PlayerGroupCount(int g) { return __builtin_popcount(unsigned(g)); }
int PlayerStatus(int p) { return statuses[p]; }
string PlayerName(int p) { return std::to_string(p); }
string StringExternal(string x) { return x; }
string StringToText(string x) { return x; }
string IntToText(int x) { return std::to_string(x); }
string TextWithColor(string x, int) { return x; }
int StringLength(string x) { return int(x.size()); }
fixed IntToFixed(int x) { return x; }
int FixedToInt(fixed x) { return int(x); }
int CeilingI(fixed x) { return int(std::ceil(x)); }
int ModI(int x, int y) { return x % y; }
fixed MaxF(fixed x, fixed y) { return std::max(x, y); }
int RandomInt(int a, int) { return a; }
bool TriggerIsEnabled(int) { return false; }
bool DialogControlIsVisible(int, int) { return true; }
void libNtve_gf_SetDialogItemImage(int id, string, int) { changedImageIds.push_back(id); }
void libNtve_gf_SetDialogItemImage2(int id, string, int) { changedImageIds.push_back(id); }
''' + stubs + '\n' + headers + '\n' + code + '\nvoid reset() {\n' + reset + r'''
    calls.clear(); changedImageIds.clear(); eventPlayer = 1;
    gv_alivePlayers = gv_currentPlayers = gv_players = 0;
    for (int p = 1; p <= 15; ++p) {
        gv_votes[p] = 1; gv_roles[p][1] = 1; gv_roles[p][0] = 4;
        gv_name[p] = std::to_string(p);
        statuses[p] = c_playerStatusActive;
        if (p <= 6) gv_alivePlayers |= 1 << p;
        for (int j = 0; j < 7; ++j) gv_actionDialogItem[p][j] = 100*p+j;
    }
    gv_players = gv_currentPlayers = gv_alivePlayers;
    gv_voteOn = true; gv_dayNumber = 3; gv_onTrial = 6;
    gv_gameStarted = true;
    auto_gf_ASE692A4E7A5A8EFBC81_lp_e58F97E5AEB3E88085 = 1;
}
void support(int p = 1, int weight = 3) { gv_zjSupportDay[p] = gv_dayNumber; gv_zjSupportVotes[p] = weight; }
void nominate(int target) {
    gv_transientMessages[1] = 0; eventControl = gv_actionDialogItem[target][2];
    assert(gt_ASVote_Func(true, true));
}
void judge(int choice) {
    gv_transientMessages[1] = 0; eventControl = gv_actionDialogItem[6][choice == 1 ? 3 : 4];
    assert(gt_ASTrialVote_Func(true, true));
}
void skip(bool button = false) {
    gv_transientMessages[1] = 0; eventControl = gv_skipButtonItem;
    if (button) assert(gt_ASSkipButton_Func(true, true)); else assert(gt_ASSkip_Func(true, true));
}
int main() {
    reset(); support(); assert(gf_BHVoteWeight(1) == 3);
    gv_votes[1] = 4; assert(gf_BHVoteWeight(1) == 4);
    gv_votes[1] = 2; support(1, 2); assert(gf_BHVoteWeight(1) == 2);
    gv_votes[1] = 0; assert(gf_BHVoteWeight(1) == 0);
    gv_votes[1] = -1; assert(gf_BHVoteWeight(1) == -1);
    gv_votes[1] = 1; gv_dayNumber++; assert(gf_BHVoteWeight(1) == 1);
    support(); gv_isNight = true; assert(gf_BHVoteWeight(1) == 1);
    assert(gf_BHVoteWeight(0) == 0 && gf_BHVoteWeight(16) == 0 && gf_BHVoteWeight(-1) == 0);
    gf_BHWithdrawVotes(0); gf_BHWithdrawVotes(16); gf_BHWithdrawVotes(-1);

    // All five lynch types, plus court and marshal precedence.
    for (int mode = 0; mode < 7; ++mode) {
        reset(); support(); gv_lynchType = mode % 5;
        gv_court = mode == 5; gv_marshalled = mode == 6;
        nominate(2); assert(gv_voteCount[2] == 3 && gv_bhNominationWeight[1] == 3);
        gv_votes[1] = 4;
        nominate(3); assert(gv_voteCount[2] == 0 && gv_voteCount[3] == 4);
        gv_votes[1] = 1; gv_zjSupportVotes[1] = 2;
        nominate(3); assert(gv_voteCount[3] == 0 && gv_playerVote[1] == 0 && gv_bhNominationWeight[1] == 0);
        nominate(2); assert(gv_voteCount[2] == 2);
        gv_currentPlayers &= ~(1 << 1); gv_novote[1] = true; gv_votes[1] = 9;
        gf_BHWithdrawVotes(1); assert(gv_voteCount[2] == 0 && gv_bhNominationWeight[1] == 0);
    }
    for (bool button: {false, true}) {
        reset(); support(); skip(button); assert(gv_skipVotes == 3 && gv_bhSkipWeight[1] == 3);
        gv_votes[1] = 8; skip(button); assert(gv_skipVotes == 0 && !gv_skipVote[1]);
        skip(button); assert(gv_skipVotes == 8); gv_votes[1] = 1;
        gf_BHWithdrawVotes(1); assert(gv_skipVotes == 0 && gv_bhSkipWeight[1] == 0);
    }
    reset(); support(); gv_trialOn = true; judge(1); assert(gv_trialVotes[0] == 3);
    gv_votes[1] = 4; judge(2); assert(gv_trialVotes[0] == 0 && gv_trialVotes[1] == 4);
    gv_votes[1] = 9; judge(2); assert(gv_trialVotes[1] == 0 && gv_bhTrialWeight[1] == 0);
    judge(2); gv_votes[1] = 1; judge(1); assert(gv_trialVotes[1] == 0 && gv_trialVotes[0] == 3);
    gv_votes[1] = 8; judge(1); assert(gv_trialVotes[0] == 0);
    judge(2); gv_voteCount[1] = 77; gv_voteCount[2] = 88;
    gf_BHWithdrawVotes(1); assert(gv_trialVotes[1] == 0 && gv_voteCount[1] == 77 && gv_voteCount[2] == 88);

    // Deferred fake-death ballots keep choice-time weights, and StopVote cannot erase them.
    for (int choice: {1, 2}) {
        reset(); support(); gv_trialOn = true; gv_bhFeignRole[1] = 4; gv_alivePlayers &= ~(1 << 1);
        judge(choice); assert(gv_trialVotes[0] == 0 && gv_trialVotes[1] == 0 && gv_bhTrialWeight[1] == 3);
        gv_votes[1] = 4; judge(choice); assert(gv_bhTrialWeight[1] == 0);
        judge(choice); gv_votes[1] = 7; gf_ASStopVote(); secretTally();
        assert(gv_trialVotes[choice-1] == 4 && gv_trialVotes[2-choice] == 0);
        reset(); support(); gv_trialOn = true; gv_bhFeignRole[1] = 4;
        judge(choice); judge(3-choice); assert(gv_playerVote[1] == 3-choice);
        gf_BHWithdrawVotes(1); secretTally(); assert(gv_trialVotes[0] == 0 && gv_trialVotes[1] == 0);
    }

    // Execute full real leave/AFK callbacks, including skip-only and trial phases.
    for (bool afk: {false, true}) for (int mode = 0; mode < 5; ++mode) {
        for (int ballot = 0; ballot < 4; ++ballot) {
            reset(); support(); gv_lynchType = mode;
            if (ballot == 0 || ballot == 2) nominate(2);
            if (ballot == 1 || ballot == 2) skip();
            if (ballot == 3) { gv_trialOn = true; judge(1); }
            gv_votes[1] = 11; gv_voteCount[4] = 42;
            if (afk) { gv_aFK[1] = 719; assert(gt_ADAntiAFKPeriod_Func(true, true)); }
            else { statuses[1] = c_playerStatusLeft; assert(gt_DetectLeave_Func(true, true)); }
            assert(gv_voteCount[2] == 0 && gv_skipVotes == 0 && gv_trialVotes[0] == 0);
            assert(gv_voteCount[4] == 42 && gv_playerVote[1] == 0 && !gv_skipVote[1]);
        }
    }
    reset(); support(); gv_trialOn = true; gv_bhFeignRole[1] = 4; gv_alivePlayers &= ~(1 << 1);
    judge(1); statuses[1] = c_playerStatusLeft; assert(gt_DetectLeave_Func(true, true));
    secretTally(); assert(gv_playerVote[1] == 0 && gv_bhTrialWeight[1] == 0 && gv_trialVotes[0] == 0);
    // Force-revoke uses actual target UI line even when its received count exceeds 15.
    reset(); support(); nominate(2); gv_voteCount[1] = 99; changedImageIds.clear();
    auto_gf_ASE692A4E7A5A8EFBC81_TriggerFunc(false, true);
    assert(gv_voteCount[2] == 0 && changedImageIds.front() == gv_actionDialogItem[2][2]);
    reset(); support(); skip(); auto_gf_ASE692A4E7A5A8EFBC81_TriggerFunc(false, true); assert(gv_skipVotes == 0);
    reset(); support(); gv_trialOn = true; judge(2);
    auto_gf_ASE692A4E7A5A8EFBC81_TriggerFunc(false, true); assert(gv_trialVotes[1] == 0);

    // A whole ballot restart clears snapshots but retains the day's support floor.
    for (int how = 0; how < 4; ++how) {
        reset(); support(); nominate(2); skip(); gv_bhTrialWeight[1] = 9;
        if (how == 0) gf_ASTrialVote(6);
        if (how == 1) gf_ASStartVote();
        if (how == 2) gf_ASTieVote();
        if (how == 3) gf_ASEndActions();
        assert(gv_bhNominationWeight[1] == 0 && gv_bhTrialWeight[1] == 0 && gv_bhSkipWeight[1] == 0);
        assert(!gv_skipVote[1] && gv_skipVotes == 0 && gf_BHVoteWeight(1) == 3);
    }
    reset(); support(); gv_novote[1] = true; nominate(2); skip(); assert(gv_voteCount[2] == 0 && gv_skipVotes == 0);
    gv_trialOn = true; judge(1); assert(gv_trialVotes[0] == 0);
    reset(); support(); gv_roles[1][0] = 18;
    eventControl = gv_actionDialogItem[2][2]; assert(!gt_ASVote_Func(true, true));
    gv_trialOn = true; eventControl = gv_actionDialogItem[6][3]; assert(!gt_ASTrialVote_Func(true, true));
    std::cout << "bishop vote handlers: PASS (all modes, cast/change/cancel, snapshots, skip, trial/secret, leave/AFK, forced revoke, resets)\n";
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    source = args.script.read_text()
    audit(source)
    with tempfile.TemporaryDirectory(prefix='bh-bishop-votes-') as temp:
        cpp, executable = Path(temp) / 'test.cpp', Path(temp) / 'test'
        cpp.write_text(build_harness(source))
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
    print('bishop vote call-site audit: PASS')


if __name__ == '__main__':
    main()
