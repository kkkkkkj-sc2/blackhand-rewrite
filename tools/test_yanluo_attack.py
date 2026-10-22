#!/usr/bin/env python3
"""Execute actual Yanluo Galaxy attack/sequence bodies in C++17 engine stubs.

Requires g++; enables UBSan/bounds. Covers unblockable delayed attacks and their
presentation, not the SC2 compiler, engine death pipeline, or actual rendering.
Use --script PATH with a temporary `git show HEAD:work/blackhand/CustomLogic.galaxy`
copy to demonstrate that the former protection/bodyguard implementation fails.
Only syntax/default-initialization conversion is applied to extracted bodies.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
FUNCTIONS = (
    'gf_ESYanluoKill', 'gf_SKK_3_yanluo', 'gf_YLTellFaction',
    'gf_BHVisit', 'gf_BHVisitSelf', 'gf_BHCrime', 'gf_BHCrimeMurder',
    'gf_BHRecordNightKiller',
)


def function(source: str, name: str) -> str:
    """Extract one whole definition by balancing braces outside comments/strings."""
    match = re.search(r'^void ' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', source, re.M)
    assert match, f'missing definition: {name}'
    tokens = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[{}]', re.S)
    depth = 0
    for token in tokens.finditer(source, match.end() - 1):
        if token.group() == '{':
            depth += 1
        elif token.group() == '}':
            depth -= 1
            if depth == 0:
                first, last = (source.count('\n', 0, match.start()) + 1,
                               source.count('\n', 0, token.end()) + 1)
                print(f'Actual {name}: lines {first}-{last}', flush=True)
                return source[match.start():token.end()]

    raise AssertionError(f'unbalanced definition: {name}')


def harness(source: str) -> str:
    bodies = [function(source, name) for name in FUNCTIONS]
    # Wrap only helper entry points to count calls; helper bodies still run, and
    # the two subject functions remain unchanged apart from C++ syntax conversion.
    for index, name in enumerate(FUNCTIONS):
        if name in ('gf_BHCrimeMurder', 'gf_BHRecordNightKiller'):
            bodies[index] = re.sub(r'^void ' + name + r'\b', 'void actual_' + name, bodies[index])

    code = '\n\n'.join(bodies)
    code = re.sub(r'\b(int|bool|text|string)((?:\[\d+\])+)( +)(\w+);', r'\1\3\4\2{};', code)
    code = re.sub(r'^(\s+)(int|bool|text|string) (\w+);', r'\1\2 \3{};', code, flags=re.M)
    used = set(re.findall(r'\bgv_\w+', code)) | {
        'gv_immune', 'gv_immuneChance', 'gv_healing', 'gv_guarded', 'gv_zuosi',
        'gv_action', 'gv_seqKillsZ', 'gv_visitation', 'gv_damage', 'gv_deathMethod',
        'gv_deathText', 'gv_ylMark', 'gv_bhNightKiller', 'gv_roles',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims}{{}};'

    assert not used - declarations.keys(), ('missing globals', used - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(used))
    resets = '\n'.join(f'    clearValue({name});' for name in sorted(used))
    headers = '\n'.join(body.split('{', 1)[0] + ';' for body in bodies)
    return r'''
#include <algorithm>
#include <cassert>
#include <iostream>
#include <map>
#include <string>
#include <tuple>
#include <utility>
#include <vector>
using std::string;
using text = string;
using playergroup = unsigned int;
constexpr int c_timeGame = 1;
std::map<string,int> calls;
std::vector<std::pair<string,int>> notices, broadcasts;
std::vector<double> waits;
std::vector<string> events;
int randomChoice = 1, scenarios = 0, failures = 0, checks = 0;
int expectedVictim = 15, expectedKiller = 1;
bool delayed = false;
string context;

void require(bool condition, const string &reason) {
    ++checks;
    if (!condition) {
        // Keep a broken pre-fix script's combinatorial run readable.
        if (failures < 24) std::cerr << "FAIL: " << context << ": " << reason << '\n';
        ++failures;
    }
}
template<class T> void clearValue(T &value) { value = T{}; }
template<class T, size_t N> void clearValue(T (&value)[N]) {
    for (auto &element : value) clearValue(element);
}
playergroup PlayerGroupAll() { return 65534U; }
bool PlayerGroupHasPlayer(playergroup group, int player) {
    return player >= 1 && player <= 15 && (group & (1U << player));
}
string StringExternal(string key) { return key; }
string StringToText(string value) { return value; }
string TextWithColor(string value, int) { return value; }
int libNtve_gf_ConvertPlayerColorToColor(int color) { return color; }
int SoundLink(string, int) { return 0; }
int Color(double, double, double) { return 0; }
void gf_BHNotify(string value, int player, int) { notices.emplace_back(value, player); }
void gf_CBSystemMessage(string value, int player, int, int, int, int) {
    broadcasts.emplace_back(value, player);
}
void gf_FlashScreen(int, int player, double duration, double intensity) {
    ++calls["flash"];
    require(player == expectedVictim && duration == 1.5 && intensity == 15.0,
            "wrong victim flash (or bodyguard/attacker flash)");
}
void SoundPlay(int, playergroup group, double volume, double offset) {
    ++calls["sound"];
    require(group == PlayerGroupAll() && volume == 80.0 && offset == 0.0, "wrong attack sound");
}
void Wait(double duration, int clock) {
    waits.push_back(duration);
    require(clock == c_timeGame && (duration == 0.6 || duration == 1.0), "unexpected wait");
}
int RandomInt(int first, int last) {
    ++calls["random"];
    require(first == 1 && last == 2, "wrong death-text random range");
    return randomChoice;
}
void gf_ESBodyguardKill(int, int) { ++calls["bodyguard"]; }
''' + globals_text + '\n' + headers + r'''
void gf_BHCrimeMurder(int player) {
    ++calls["crime"];
    events.push_back("crime");
    require(player == expectedKiller, "wrong murder suspect");
    actual_gf_BHCrimeMurder(player);
}
void gf_BHRecordNightKiller(int victim, int killer) {
    ++calls["record"];
    events.push_back("record");
    require(victim == expectedVictim && killer == expectedKiller, "wrong killer registration");
    require(PlayerGroupHasPlayer(gv_alivePlayers, victim), "killer registered after removal");
    actual_gf_BHRecordNightKiller(victim, killer);
}
// Deliberately isolate the engine's trigger-based death pipeline. The subject
// must call it once with the right victim; this stub models alive-group removal.
void gf_KillPlayer(int player, bool disguised) {
    ++calls["kill"];
    events.push_back("kill");
    require(player == expectedVictim && !disguised, "wrong kill arguments");
    if (delayed) {
        require(gv_ylMark[expectedKiller] == expectedVictim, "old mark replaced before attack");
        require(notices.empty(), "new faction reported before old-mark attack");
    }
    gv_alivePlayers &= ~(1U << player);
}
''' + code + r'''
void reset(int killer=1, int victim=15) {
''' + resets + r'''
    calls.clear(); notices.clear(); broadcasts.clear(); waits.clear(); events.clear();
    expectedKiller = killer; expectedVictim = victim; delayed = false;
    gv_alivePlayers = PlayerGroupAll();
    gv_currentPlayers = (1U << 1) | (1U << 5) | (1U << 15);
    for (int player=1; player<=15; ++player) {
        gv_roles[player][0]=1; gv_roles[player][1]=1;
        gv_name[player]="player" + std::to_string(player);
        gv_number[player]=std::to_string(player);
        gv_damage[player]=7;
        gv_deathMethod[player]="prior:";
        gv_deathText[player]="prior text:";
    }
    gv_roles[killer][0]=26; gv_roles[killer][1]=3;
    gv_action[killer][0]=14;
}
void checkKill() {
    require(calls["kill"]==1 && calls["crime"]==1 && calls["record"]==1,
            "kill/murder/registration must each occur once");
    require(events==std::vector<string>{"crime","record","kill"}, "wrong death side-effect order");
    require(!PlayerGroupHasPlayer(gv_alivePlayers,expectedVictim) && gv_diedAtNight[expectedVictim],
            "target did not die");
    require(gv_deathMethod[expectedVictim]=="prior:Y", "death method must append only Y");
    require(gv_bhNightKiller[expectedVictim]==expectedKiller, "missing killer registration");
    require(!calls["bodyguard"], "Yanluo must never call gf_ESBodyguardKill");
    for (int player=1; player<=15; ++player) {
        require(gv_damage[player]==7+(player==expectedVictim), "damage must increment only target once");
        if (player!=expectedVictim) {
            require(PlayerGroupHasPlayer(gv_alivePlayers,player) && !gv_diedAtNight[player], "collateral death");
            require(gv_deathMethod[player]=="prior:", "collateral death method");
        }
        for (int crime=0; crime<=10; ++crime) {
            require(gv_e78AAFE7BDAAE4BA8BE5AE9E[player][crime]==(player==expectedKiller && crime==1),
                    "wrong murder crime/extra crime");
        }
    }
}
void checkFaction(int target, int pool) {
    string expected="Param/Value/YLSEE1"+gv_number[target]+"."+gv_name[target];
    expected += "Param/Value/YLFACT" + (pool==3 ? string("N") : std::to_string(pool));
    if (pool==3) expected += "neutral role。";
    require(notices==std::vector<std::pair<string,int>>{{expected,expectedKiller}},
            "wrong faction report/recipient or unexpected protection notification");
    require(gv_visitation[expectedKiller]==expectedKiller, "must visit self, never either target");
}
void checkInert() {
    require(calls["kill"]==0 && calls["crime"]==0 && calls["record"]==0 && !calls["bodyguard"],
            "inert action produced death side effects");
    require(notices.empty() && broadcasts.empty() && waits.empty() && !calls["random"] && !calls["flash"] && !calls["sound"],
            "inert action produced report/presentation");
    for (int player=1; player<=15; ++player) {
        require(gv_damage[player]==7 && gv_deathMethod[player]=="prior:", "inert action changed damage/method");
        require(gv_deathText[player]=="prior text:" && !gv_bhNightKiller[player], "inert action changed text/killer");
        for (int crime=0; crime<=10; ++crime) require(!gv_e78AAFE7BDAAE4BA8BE5AE9E[player][crime], "inert crime");
    }
}
int main() {
    // Full protection cross-product, both player-array ends and both random texts.
    for (int killer: {1,15}) for (bool immune: {false,true})
    for (int shield: {0,1,3}) for (int heal: {0,1,3}) for (int guard: {0,3,14})
    for (bool zuosi: {false,true}) for (bool sequence: {false,true})
    for (bool descriptions: {false,true}) for (int roll: {1,2}) {
        const int victim=killer==1?15:1;
        reset(killer,victim); ++scenarios;
        context="direct killer="+std::to_string(killer)+" immune="+std::to_string(immune)
                +" shield="+std::to_string(shield)+" heal="+std::to_string(heal)
                +" guard="+std::to_string(guard)+" sequence="+std::to_string(sequence)
                +" descriptions="+std::to_string(descriptions)+" roll="+std::to_string(roll);
        gv_immune[victim][0]=immune; gv_immune[victim][1]=true;
        gv_immuneChance[victim]=shield; gv_healing[victim]=heal; gv_guarded[victim]=guard;
        gv_zuosi[victim]=zuosi; gv_nightSequence=sequence; gv_deathDescriptions=descriptions;
        randomChoice=roll;
        gf_ESYanluoKill(victim,killer);
        checkKill();
        require(gv_immuneChance[victim]==shield && gv_healing[victim]==heal, "consumed shield/healing");
        require(gv_immune[victim][0]==immune && gv_immune[victim][1], "changed immunity flags");
        require(gv_guarded[victim]==guard, "bodyguard must remain available for other attacks");
        require(calls["random"]==int(sequence||descriptions), "death-text switch ignored");
        const string text="prior text:" + (sequence||descriptions ? string("Param/Value/YLDEATH")+std::to_string(roll-1) : string());
        require(gv_deathText[victim]==text, "wrong random death text or lost prior text");
        require(calls["flash"]==int(sequence) && calls["sound"]==int(sequence), "night presentation switch ignored");
        require(waits==(sequence ? std::vector<double>{0.6} : std::vector<double>{}), "wrong presentation waits");
        require(broadcasts==(sequence ? std::vector<std::pair<string,int>>{
            {"Param/Value/YLNIGHT",1},{"Param/Value/YLNIGHT",5},{"Param/Value/YLNIGHT",15}}
            : std::vector<std::pair<string,int>>{}), "wrong night broadcast recipients");
        require(notices.empty(), "unexpected immune/healed/guarded private notice");
        // Re-entry after successful attack must neither kill nor register twice.
        const auto before=std::make_tuple(calls,notices,broadcasts,waits,events);
        gf_ESYanluoKill(victim,killer);
        require(before==std::make_tuple(calls,notices,broadcasts,waits,events), "duplicate attack side effects");
        checkKill();
    }
    for (int reason=0; reason<3; ++reason) {
        reset(); ++scenarios; context="direct inert "+std::to_string(reason);
        if (reason==0) gv_alivePlayers &= ~(1U<<15);
        if (reason==1) gv_diedAtNight[15]=true; // Still in alive group until engine cleanup.
        gv_nightSequence=gv_deathDescriptions=true;
        gf_ESYanluoKill(reason==2?1:15,1);
        checkInert();
    }
    // No choice, repeated choice, self, invalid/dead choice, blocked/jailed/dead
    // owner: preserve the old mark and do not report, attack, or change visitation.
    for (int reason=0; reason<11; ++reason) {
        reset(); ++scenarios; context="sequence inert "+std::to_string(reason);
        gv_ylMark[1]=15; gv_visitation[1]=9; gv_seqKillsZ[1]=true;
        if (reason==0) gv_action[1][0]=0;
        if (reason==1) gv_action[1][0]=15;
        if (reason==2) gv_action[1][0]=1;
        if (reason==3) gv_action[1][0]=-1;
        if (reason==4) gv_action[1][0]=16;
        if (reason==5) gv_alivePlayers &= ~(1U<<14);
        if (reason==6) gv_roleblocked[1]=2;
        if (reason==7) gv_jailed[1]=2;
        if (reason==8) gv_alivePlayers &= ~(1U<<1);
        if (reason==9) gv_diedAtNight[1]=true;
        if (reason==10) { gv_action[1][0]=0; gv_ylMark[1]=0; }
        const int previous=gv_ylMark[1];
        gf_SKK_3_yanluo(1);
        checkInert();
        require(gv_ylMark[1]==previous && gv_visitation[1]==9 && gv_seqKillsZ[1], "inert sequence changed mark/visit/sequence");
    }
    // First cast only marks; an already-dead previous mark is skipped. In each
    // case the new live choice still gets its actual faction report/self visit.
    for (int old: {0,15}) for (bool nightDead: {false,true}) for (int pool: {1,2,3,5}) {
        reset(); ++scenarios; context="mark only old="+std::to_string(old)+" pool="+std::to_string(pool);
        gv_ylMark[1]=old;
        if (old && nightDead) gv_diedAtNight[old]=true;
        if (old && !nightDead) gv_alivePlayers &= ~(1U<<old);
        gv_roles[14][1]=pool; gv_roleNameArray[3][1]="neutral role";
        gf_SKK_3_yanluo(1);
        require(gv_ylMark[1]==14 && !gv_seqKillsZ[1], "first/dead-old mark timing changed");
        checkFaction(14,pool);
        // Report/visit are expected here, death/presentation is not.
        notices.clear(); checkInert();
    }
    // Real delayed kill: old mark, not the newly clicked target. Repeating the
    // same new choice must remain inert rather than kill it immediately.
    for (bool priorSequence: {false,true}) for (int pool: {1,2,3,5}) {
        reset(); ++scenarios; context="delayed pool="+std::to_string(pool);
        gv_ylMark[1]=15; gv_action[1][0]=14; gv_seqKillsZ[1]=priorSequence;
        gv_roles[14][1]=pool; gv_roleNameArray[3][1]="neutral role";
        gv_immune[15][0]=true; gv_immuneChance[15]=3; gv_healing[15]=3; gv_guarded[15]=3;
        delayed=true;
        gf_SKK_3_yanluo(1);
        checkKill(); checkFaction(14,pool);
        require(gv_ylMark[1]==14 && gv_seqKillsZ[1], "delayed attack did not advance mark/sequence");
        require(waits==(priorSequence?std::vector<double>{1.0}:std::vector<double>{}), "inter-kill wait changed");
        require(gv_immuneChance[15]==3 && gv_healing[15]==3 && gv_guarded[15]==3, "delayed attack consumed protections");
        const auto before=std::make_tuple(calls,notices,broadcasts,waits,events);
        gf_SKK_3_yanluo(1);
        require(before==std::make_tuple(calls,notices,broadcasts,waits,events), "same new mark attacked again");
        require(PlayerGroupHasPlayer(gv_alivePlayers,14) && !gv_diedAtNight[14], "new mark killed too soon");
    }
    std::cout << (failures?"FAIL: ":"PASS: ") << scenarios << " scenarios, " << checks
              << " checks, " << failures << " failures; actual Yanluo bodies; UBSan/bounds; NOT SC2 runtime" << std::endl;
    return failures?1:0;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT, help='Galaxy script (including temporary HEAD copy)')
    args = parser.parse_args()
    code = harness(args.script.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='bh-yanluo-tests-') as tmp:
        cpp, exe = Path(tmp) / 'yanluo.cpp', Path(tmp) / 'yanluo'
        cpp.write_text(code, encoding='utf-8')
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
