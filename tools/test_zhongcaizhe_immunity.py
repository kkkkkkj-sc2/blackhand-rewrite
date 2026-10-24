#!/usr/bin/env python3
"""Run actual 仲裁者 setup/pruning and ordinary-defense attack source with UBSan.

Requires g++ or clang++; --script selects integrated Galaxy source. Only array
syntax/type aliases are translated. UI, player groups and final death cleanup
are explicit engine doubles. Night reset/dispatch are checked statically, not
executed; jailed setup calls below isolate the passive from jail's own protection.
This is not an SC2 compiler, rendering, packaging or live-game test.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
NAMES = ('gf_ZCPrune', 'gf_SKN_3_zhongcaizhe', 'gf_GSAttack', 'gf_ESZhongcaiKill')


def mask(source: str) -> str:
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), source)


def block(source: str, opening: int) -> tuple[str, int]:
    live = mask(source)
    assert live[opening] == '{'
    depth, end = 1, opening + 1
    while depth:
        assert end < len(live), 'unbalanced source block'
        depth += (live[end] == '{') - (live[end] == '}')
        end += 1

    return source[opening:end], end


def function(source: str, name: str) -> str:
    match = re.search(r'^(?:void|bool|int|text)\s+' + re.escape(name)
                      + r'\s*\([^;{}]*\)\s*\{', mask(source), re.M)
    assert match, f'missing function {name}'
    _, end = block(source, match.end() - 1)
    return source[match.start():end]


def guarded(source: str, condition: str) -> tuple[str, int]:
    matches = list(re.finditer(r'if\s*\(\(' + re.escape(condition) + r'\)\)\s*\{', mask(source)))
    assert len(matches) == 1, f'expected one guard: {condition}'
    return block(source, matches[0].end() - 1)


def check_wiring(source: str) -> None:
    setup = mask(function(source, NAMES[1]))
    passive, _ = guarded(setup, 'gv_roleOptions[3][27][0] == true')
    assert 'gv_immune[lv_a][0] = true;' in passive, 'missing option-controlled immunity'
    no_picks, _ = guarded(setup, 'gv_zcN[lv_a] == 0')
    assert 'return;' in no_picks, 'expected no-picks early return'
    assert setup.index(passive) < setup.index('gf_ZCPrune(lv_a);') < setup.index(no_picks), \
        'passive must precede pruning and the no-picks return'
    assert len(re.findall(r'gv_immune\[[^;]+?\]\s*=(?!=)', setup)) == 1, \
        'setup must only add its own immunity, not clear other protection'

    neutral = mask(function(source, 'gf_RSNeutralSetup'))
    alive, _ = guarded(neutral, 'PlayerGroupHasPlayer(gv_alivePlayers, lv_a) == true')
    pool, _ = guarded(alive, 'gv_roles[lv_a][1] == 3')
    jailed, end = guarded(pool, 'gv_jailed[lv_a] != 0')
    otherwise = re.match(r'\s*else\s*\{', pool[end:])
    assert otherwise, 'missing nonjailed neutral branch'
    free, _ = block(pool, end + otherwise.end() - 1)
    for branch in (jailed, free):
        role, _ = guarded(branch, 'gv_roles[lv_a][0] == 27')
        assert role.count('gf_SKN_3_zhongcaizhe(lv_a);') == 1, 'lost role-27 dispatch'

    assert neutral.count('gf_SKN_3_zhongcaizhe(lv_a);') == 2
    wrapper = function(source, 'gf_NightTransition')
    assert 'TriggerCreate("auto_gf_NightTransition_TriggerFunc")' in wrapper
    assert 'TriggerExecute(auto_gf_NightTransition_Trigger, false, false);' in wrapper
    night = mask(function(source, 'auto_gf_NightTransition_TriggerFunc'))
    reset, call = 'gv_immune[lv_a][0] = false;', 'gf_RSNeutralSetup();'
    assert night.count(reset) == night.count(call) == 1
    assert night.index(reset) < night.index(call), 'nightly reset must precede neutral setup'
    assert 'autoDEE7CD8E_ae = 15;' in night and 'autoDEE7CD8E_ai = 1;' in night
    loop = re.search(r'lv_a = 1;\s*for\s*\([^\{]*autoDEE7CD8E_ae[^\{]*\{', night)
    assert loop, 'missing all-player reset loop'
    reset_body, _ = block(night, loop.end() - 1)
    assert reset in reset_body, 'immunity reset must be inside the all-player loop'

    for name in (*NAMES, 'gf_RSNeutralSetup', 'auto_gf_NightTransition_TriggerFunc'):
        body = function(source, name)
        first = source.count('\n', 0, source.index(body)) + 1
        print(f'{name}: lines {first}..{first + body.count(chr(10))}', flush=True)

    print('PASS source wiring: jailed/free dispatch, nightly reset, passive before early return', flush=True)


PREFIX = r'''
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
using string = std::string;
using text = std::string;
using playergroup = unsigned int;
'''

STUBS = r'''
int ensureCalls, deathCalls, murders, killer;
bool visible[16][3];
const int c_playerStatusActive = 1;

template<class T> void clear(T& value) { value = T{}; }
template<class T, size_t N> void clear(T (&values)[N]) {
    for (auto& value : values) clear(value);
}
bool PlayerGroupHasPlayer(playergroup group, int p) {
    assert(p >= 1 && p <= 15);
    return (group & (1u << p)) != 0;
}
int PlayerGroupCount(playergroup group) {
    int count = 0;
    for (int p = 1; p <= 15; ++p) count += PlayerGroupHasPlayer(group, p);
    return count;
}
int PlayerGroupSingle(int p) { assert(p >= 1 && p <= 15); return p; }
int PlayerStatus(int p) { assert(p >= 1 && p <= 15); return c_playerStatusActive; }
void gf_ZCEnsureUi() { ++ensureCalls; gv_zcUiReady = true; }
void DialogSetVisible(int dialog, int p, bool show) {
    assert(dialog >= 1 && dialog <= 2 && p >= 1 && p <= 15);
    visible[p][dialog] = show;
}
text StringExternal(string s) { return s; }
text StringToText(string s) { return s; }
text TextWithColor(text s, int) { return s; }
int libNtve_gf_ConvertPlayerColorToColor(int c) { return c; }
int Color(double, double, double) { return 0; }
int SoundLink(string, int) { return 0; }
void gf_CBSystemMessage(text, int p, int, int, int, int) { assert(p >= 1 && p <= 15); }
void gf_BHNotify(text, int p, int) { assert(p >= 1 && p <= 15); }
void gf_GSNightNotice(text) {}
void gf_ESBodyguardKill(int, int) { assert(false && "bodyguard branch outside focused test"); }
void gf_BHCrimeMurder(int p) { assert(p >= 1 && p <= 15); ++murders; }
void gf_BHRecordNightKiller(int target, int actor) { if (target != actor) killer = actor; }
void gf_FlashScreen(int, int, double, double) {}
bool gf_GSKillPlayerDirect(int p, bool, bool) {
    assert(PlayerGroupHasPlayer(gv_alivePlayers, p));
    gv_alivePlayers &= ~(1u << p);
    ++deathCalls;
    return true;
}
void gf_KillPlayer(int p, bool disguised) { gf_GSKillPlayerDirect(p, disguised, false); }
'''

TESTS = r'''
void fixture(int who, bool option, int picks) {
    clearGlobals();
    clear(visible);
    ensureCalls = deathCalls = murders = killer = 0;
    gv_alivePlayers = gv_currentPlayers = gv_players = 0xfffeu;
    gv_zcPickBox = 1;
    gv_zcFateBox = 2;
    gv_zcUiReady = true;
    gv_roleOptions[3][27][0] = option;
    gv_roleOptions[3][27][1] = true;  // unrelated option must survive
    gv_roles[who][0] = 27;
    gv_roles[who][1] = 3;
    gv_zcN[who] = picks;
    for (int p = 0; p <= 15; ++p) {
        gv_immune[p][0] = p != who && (p % 2 == 0);
        for (int bit = 1; bit < 4; ++bit) gv_immune[p][bit] = (p + bit) % 2;
        gv_immuneChance[p] = 2;
        gv_cooldown[p] = 3;
        gv_shots[p] = 4;
        gv_zcChoice[p] = 2;
        gv_busEligible[p] = gv_witchEligible[p] = gv_veteranEligible[p] = true;
        gv_number[p] = std::to_string(p);
        gv_name[p] = "player";
    }
    for (int i = 0; i < picks; ++i) {
        int target = (who + i) % 15 + 1;
        gv_zcPick[who][i] = target;
        gv_zcOwner[target] = who;
    }
}
void checkedSetup(int who, bool expected) {
    decltype(gv_immune) before;
    decltype(gv_roleOptions) options;
    decltype(gv_immuneChance) charges;
    decltype(gv_zcLock) locks;
    decltype(gv_cooldown) cooldowns;
    decltype(gv_shots) shots;
    std::memcpy(before, gv_immune, sizeof before);
    std::memcpy(options, gv_roleOptions, sizeof options);
    std::memcpy(charges, gv_immuneChance, sizeof charges);
    std::memcpy(locks, gv_zcLock, sizeof locks);
    std::memcpy(cooldowns, gv_cooldown, sizeof cooldowns);
    std::memcpy(shots, gv_shots, sizeof shots);
    gf_SKN_3_zhongcaizhe(who);
    before[who][0] = expected;
    assert(std::memcmp(before, gv_immune, sizeof before) == 0);
    assert(std::memcmp(options, gv_roleOptions, sizeof options) == 0);
    assert(std::memcmp(charges, gv_immuneChance, sizeof charges) == 0);
    assert(std::memcmp(locks, gv_zcLock, sizeof locks) == 0);
    assert(std::memcmp(cooldowns, gv_cooldown, sizeof cooldowns) == 0);
    assert(std::memcmp(shots, gv_shots, sizeof shots) == 0);
}
void knife(int who, bool protectedNow) {
    // Remove chance charges from this combat fixture to isolate ordinary immune[0].
    gv_immuneChance[who] = 0;
    int actor = who % 15 + 1;
    gf_GSAttack(actor, who);
    assert(PlayerGroupHasPlayer(gv_alivePlayers, who) == protectedNow);
    assert(gv_diedAtNight[who] == !protectedNow);
    assert(deathCalls == !protectedNow && murders == !protectedNow);
    assert(killer == (protectedNow ? 0 : actor));
}
int main() {
    int cases = 0;
    // Cross product: every player slot, option, list size, cooldown, restriction, jail.
    for (int who = 1; who <= 15; ++who) for (bool option : {false, true})
    for (int picks : {0, 1, 3}) for (int lock : {0, 2})
    for (int blocked : {0, 6}) for (int jailed : {0, 7}) {
        fixture(who, option, picks);
        gv_zcLock[who] = lock;
        gv_roleblocked[who] = blocked;
        gv_jailed[who] = jailed;
        checkedSetup(who, option);
        assert(gv_zcN[who] == picks && ensureCalls == (picks > 0));
        assert(gv_busEligible[who] == (picks == 0));
        assert(gv_witchEligible[who] == (picks == 0));
        assert(gv_veteranEligible[who] == (picks == 0));
        for (int i = 0; i < picks; ++i) {
            int target = (who + i) % 15 + 1;
            assert(gv_zcPick[who][i] == target && gv_zcOwner[target] == who);
            assert(gv_zcChoice[target] == 0 && visible[target][gv_zcFateBox]);
        }
        knife(who, option);
        ++cases;
    }

    // Stale ownership is not stolen; dead/night-dead targets are really pruned.
    for (bool option : {false, true}) for (bool ui : {false, true})
    for (int mode = 0; mode < 4; ++mode) {
        fixture(1, option, 3);
        gv_zcUiReady = ui;
        visible[2][2] = true;
        if (mode == 0) gv_alivePlayers &= ~(1u << 2);
        if (mode == 1) gv_diedAtNight[2] = true;
        if (mode == 2) gv_zcOwner[2] = 8;
        if (mode == 3) {
            gv_alivePlayers &= ~(1u << 2);
            gv_diedAtNight[3] = true;
            gv_zcOwner[4] = 8;
        }

        checkedSetup(1, option);
        assert(gv_zcN[1] == (mode == 3 ? 0 : 2));
        assert(ensureCalls == (mode != 3));
        if (mode == 2) {
            assert(gv_zcOwner[2] == 8 && gv_zcChoice[2] == 2 && visible[2][2]);
        } else {
            assert(gv_zcOwner[2] == 0 && gv_zcChoice[2] == 0);
            assert(visible[2][2] == !ui);
        }

        if (mode == 3) {
            assert(gv_zcPick[1][0] == 0 && gv_zcPick[1][1] == 0 && gv_zcPick[1][2] == 0);
            assert(gv_zcOwner[3] == 0 && gv_zcOwner[4] == 8);
        } else {
            assert(gv_zcPick[1][0] == 3 && gv_zcPick[1][1] == 4 && gv_zcPick[1][2] == 0);
        }

        knife(1, option);
        ++cases;
    }

    // Option off preserves externally supplied immunity (jail/doctor, not role passive).
    for (int picks : {0, 1, 3}) {
        fixture(1, false, picks);
        gv_immune[1][0] = true;
        checkedSetup(1, true);
        knife(1, true);
        ++cases;
    }

    // Several nights with no charge replenishment, including toggles and empty lists.
    fixture(15, true, 0);
    gv_immuneChance[15] = 0;
    for (bool option : {true, true, true, false, true, false}) {
        gv_immune[15][0] = false;  // nightly reset is checked in production wiring
        gv_alivePlayers |= 1u << 15;
        gv_diedAtNight[15] = false;
        gv_damage[15] = 0;
        deathCalls = murders = killer = 0;
        gv_roleOptions[3][27][0] = option;
        checkedSetup(15, option);
        assert(gv_immuneChance[15] == 0 && ensureCalls == 0);
        knife(15, option);
        if (option) knife(15, true);  // passive survives repeated ordinary attacks
        ++cases;
    }

    // The arbiter's own verdict deliberately bypasses passive immunity and defenses.
    fixture(1, true, 0);
    checkedSetup(1, true);
    gv_healing[1] = 5;
    assert(gf_ESZhongcaiKill(1, 1, "verdict"));
    assert(!PlayerGroupHasPlayer(gv_alivePlayers, 1) && gv_diedAtNight[1]);
    assert(gv_immune[1][0] && gv_immuneChance[1] == 2 && gv_healing[1] == 5);
    assert(gv_deathMethod[1] == "Z" && deathCalls == 1 && murders == 1 && killer == 0);
    assert(!gf_ESZhongcaiKill(1, 1, "verdict") && deathCalls == 1);
    ++cases;
    std::cout << "PASS " << cases << " extracted-source setup/prune/attack/verdict scenarios\n";
}
'''


def run_harness(source: str) -> None:
    bodies = [function(source, name) for name in NAMES]
    definitions = '\n\n'.join(bodies)
    required = set(re.findall(r'\bgv_\w+', mask(definitions))) | {
        'gv_roles', 'gv_jailed', 'gv_roleblocked', 'gv_zcLock', 'gv_cooldown', 'gv_shots',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not required - declarations.keys(), ('missing globals', required - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(required))
    reset = 'void clearGlobals() {\n' + ''.join(f'    clear({name});\n' for name in sorted(required)) + '}\n'
    # The only source conversion: Galaxy int[3] name -> C++ int name[3].
    definitions = re.sub(r'\b(int|bool|text|string)((?:\[\d+\])+)\s+(\w+)', r'\1 \3\2', definitions)
    program = PREFIX + globals_text + STUBS + reset + definitions + TESTS
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'C++17 compiler required'
    with tempfile.TemporaryDirectory(prefix='zc-immunity-test-') as directory:
        cpp, binary = Path(directory) / 'test.cpp', Path(directory) / 'test'
        cpp.write_text(program)
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    source = args.script.read_text()
    check_wiring(source)
    run_harness(source)


if __name__ == '__main__':
    main()
