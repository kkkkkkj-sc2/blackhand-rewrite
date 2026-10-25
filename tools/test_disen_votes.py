#!/usr/bin/env python3
"""Execute actual disen/withdraw/re-enable/vote callbacks with stateful UI stubs.

The native trigger boundary runs withdrawal immediately and queues button recovery
with captured parameters until flush(). Both inherited and absent event-player
contexts are exercised. This is not SC2 scheduling or an engine/UI smoke test.
The night reset is an exact extracted loop, not the full cinematic/night phase.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from test_bishop_votes import SCRIPT, balanced_end, build_harness, function


EXTRA_CPP = r'''
struct Recovery { int player; fixed delay; };
std::vector<Recovery> pending;
std::map<std::pair<int, int>, bool> enabled;
std::map<int, string> triggerNames;
string command;

string EventChatMessage(bool) { return command; }
string StringCase(string s, bool upper) {
    for (char &ch: s) {
        if (upper && ch >= 'a' && ch <= 'z') ch -= 'a' - 'A';
        if (!upper && ch >= 'A' && ch <= 'Z') ch += 'a' - 'A';
    }
    return s;
}
string StringSub(string s, int first, int last) {
    if (first < 1 || last < first || first > int(s.size())) return "";
    return s.substr(first - 1, last - first + 1);
}
void DialogControlSetEnabled(int id, int group, bool value) {
    for (int p = 0; p <= 15; ++p) {
        if (group & (1 << p)) enabled[{id, p}] = value;
    }
}
bool isEnabled(int target, int slot, int viewer) {
    auto it = enabled.find({gv_actionDialogItem[target][slot], viewer});
    return it == enabled.end() || it->second;
}
int TriggerCreate(string name) {
    int id = int(triggerNames.size()) + 1;
    triggerNames[id] = name;
    return id;
}
void TriggerExecute(int id, bool conditions, bool wait) {
    assert(!conditions && !wait);
    const auto &name = triggerNames.at(id);
    if (name == "auto_gf_ASE692A4E7A5A8EFBC81_TriggerFunc") {
        auto_gf_ASE692A4E7A5A8EFBC81_TriggerFunc(false, true);
    }
    else {
        assert(name == "auto_gf_ASReEnableButtons_TriggerFunc");
        pending.push_back({auto_gf_ASReEnableButtons_lp_player,
                           auto_gf_ASReEnableButtons_lp_delay});
    }
}
void flush(int context) {
    auto jobs = pending;
    pending.clear();
    eventPlayer = context;
    for (const auto &job: jobs) {
        auto_gf_ASReEnableButtons_lp_player = job.player;
        auto_gf_ASReEnableButtons_lp_delay = job.delay;
        assert(auto_gf_ASReEnableButtons_TriggerFunc(false, true));
    }
}
'''

TESTS = r'''
int fixtures = 0;
void setup() {
    reset(); pending.clear(); enabled.clear(); triggerNames.clear(); command.clear();
    for (int p = 1; p <= 15; ++p) {
        gv_alivePlayers |= 1 << p;
        gv_number[p] = std::to_string(p);
        gv_colorName[p] = "COLOR" + std::to_string(p);
        gv_name[p] = "PLAYER" + std::to_string(p);
    }
    gv_currentPlayers = gv_players = gv_alivePlayers;
    gv_roles[2][1] = 3; gv_roles[2][0] = 11;
    gv_e5AEA1E8AEA1E68A80E883BDEFBC9F[2] = 2;
    gv_lynchType = 2;
}
void cast(int player, int target) {
    assert(isEnabled(target, 2, player));
    eventPlayer = player; eventControl = gv_actionDialogItem[target][2];
    gv_transientMessages[player] = 0;
    assert(gt_ASVote_Func(true, true));
}
void castSkip(int player) {
    eventPlayer = player; gv_transientMessages[player] = 0;
    assert(gt_ASSkip_Func(true, true));
}
void disen(int target) {
    eventPlayer = 2; command = "-disen " + std::to_string(target);
    assert(gt_removevotes3_Func(true, true));
}
void nextDay() {
    gf_ASEndActions();
    disenNightReset();
    gv_dayNumber++; gv_isNight = false; gv_trialOn = false;
    gf_ASStartVote();
}
int main() {
    // Direct recovery contract: independently poison all three slots, not just [2].
    for (int target = 1; target <= 15; ++target) for (int context: {0, 2}) {
        setup();
        int other = target == 1 ? 3 : 1;
        for (int row = 1; row <= 15; ++row) for (int slot = 2; slot <= 4; ++slot) {
            DialogControlSetEnabled(gv_actionDialogItem[row][slot], PlayerGroupSingle(target), false);
            DialogControlSetEnabled(gv_actionDialogItem[row][slot], PlayerGroupSingle(other), false);
        }
        gf_ASReEnableButtons(target, 1.0);
        flush(context);
        for (int row = 1; row <= 15; ++row) for (int slot = 2; slot <= 4; ++slot) {
            assert(isEnabled(row, slot, target));
            assert(!isEnabled(row, slot, other));
        }
        ++fixtures;
    }
    // Include every target slot, both event contexts and all existing-ballot kinds.
    for (int target = 1; target <= 15; ++target) {
        if (target == 2) continue;
        int votee = target == 3 ? 4 : 3;
        for (int context: {0, 2}) for (int ballot = 0; ballot < 5; ++ballot) {
            setup();
            gv_votes[target] = target % 4 + 1;
            int weight = gv_votes[target];
            if (ballot == 1 || ballot == 3) { cast(target, votee); flush(target); }
            if (ballot == 2 || ballot == 3) castSkip(target);
            if (ballot == 4) {
                gv_onTrial = votee; gv_trialOn = true;
                eventPlayer = target; eventControl = gv_actionDialogItem[votee][3];
                assert(gt_ASTrialVote_Func(true, true));
                assert(gv_trialVotes[0] == weight);
            }
            disen(target);
            assert(gv_novote[target]);
            assert(gv_e5AEA1E8AEA1E68A80E883BDEFBC9F[2] == 0);
            assert(gv_votes[target] == weight);
            assert(gv_playerVote[target] == 0 && !gv_skipVote[target]);
            assert(gv_voteCount[votee] == 0 && gv_skipVotes == 0 && gv_trialVotes[0] == 0);
            assert(pending.size() == (ballot == 0 ? 0u : 1u));
            // Poison caller UI: a target's delayed restore must not alter the caller.
            DialogControlSetEnabled(gv_actionDialogItem[votee][2], PlayerGroupSingle(2), false);
            flush(context);
            for (int row = 1; row <= 15; ++row) {
                for (int slot = 2; slot <= 4; ++slot) {
                    assert(isEnabled(row, slot, target));
                }
            }
            assert(!isEnabled(votee, 2, 2));
            // Enabled buttons must NOT bypass the current-day disen flag.
            eventPlayer = target; eventControl = gv_actionDialogItem[votee][2];
            gv_trialOn = false;
            assert(gt_ASVote_Func(true, true));
            assert(gv_playerVote[target] == 0 && gv_voteCount[votee] == 0);
            assert(gt_ASSkip_Func(true, true));
            assert(!gv_skipVote[target]);
            gv_trialOn = true; eventControl = gv_actionDialogItem[votee][3];
            assert(gt_ASTrialVote_Func(true, true));
            assert(gv_playerVote[target] == 0 && gv_trialVotes[0] == 0);
            // Normal night clears eligibility; StartVote alone does not unlock UI.
            nextDay();
            assert(!gv_novote[target]);
            cast(target, votee);
            assert(gv_playerVote[target] == votee && gv_voteCount[votee] == weight);
            flush(target);
            cast(target, votee); flush(target);
            assert(gv_voteCount[votee] == 0);
            ++fixtures;
        }
    }
    // Consecutive recoveries must retain their own targets, not the latest caller.
    setup();
    castSkip(1); castSkip(3);
    disen(1);
    gv_e5AEA1E8AEA1E68A80E883BDEFBC9F[2] = 2;
    disen(3);
    assert(pending.size() == 2);
    flush(0); nextDay();
    cast(1, 4); cast(3, 4);
    assert(gv_voteCount[4] == 2);
    ++fixtures;
    std::cout << "PASS disen voting/UI lifecycle: " << fixtures
              << " fixtures; real callbacks, explicit target, current-day ban, night reset, next-day cast\n";
}
'''


def harness(source: str) -> str:
    night = function(source, 'auto_gf_NightTransition_TriggerFunc')
    marker = '        gv_novote[lv_a] = false;'
    assert night.count(marker) == 1
    start = night.rfind('    lv_a = 1;', 0, night.index(marker))
    opening = night.index('{', start)
    block = night[start:balanced_end(night, opening)]
    names = set(re.findall(r'\bauto\w+_(?:ae|ai)\b', block))
    declarations = '\n'.join(line for line in night.splitlines()
                             if re.match(r'    const int (\w+) = ', line)
                             and re.match(r'    const int (\w+) = ', line)[1] in names)
    assert len(declarations.splitlines()) == len(names) == 2
    reset_fn = '\nvoid disenNightReset () {\n    int lv_a;\n' + declarations + '\n' + block + '\n}\n'
    extra = ('gt_removevotes3_Func', 'gf_ASE692A4E7A5A8EFBC81',
             'gf_ASReEnableButtons', 'auto_gf_ASReEnableButtons_TriggerFunc',
             'disenNightReset')
    cpp = build_harness(source + reset_fn, extra_functions=extra,
                        extra_native=('EventChatMessage', 'StringCase', 'StringSub',
                                      'DialogControlSetEnabled', 'TriggerCreate', 'TriggerExecute'),
                        extra_cpp=EXTRA_CPP)
    assert cpp.count('int main() {') == 1
    return cpp[:cpp.index('int main() {')] + TESTS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    source = args.script.read_text()
    with tempfile.TemporaryDirectory(prefix='bh-disen-votes-') as temp:
        cpp, executable = Path(temp) / 'test.cpp', Path(temp) / 'test'
        cpp.write_text(harness(source))
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    main()
