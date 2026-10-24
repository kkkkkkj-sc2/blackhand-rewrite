#!/usr/bin/env python3
"""Execute actual extracted GS source, plus balanced-scoped production wiring checks.

Default: test the maintained integrated CustomLogic.galaxy directly.
--script PATH selects another integrated source. No staging fragments or patcher
are required. Engine/death-presentation helpers are explicit doubles; no SC2
compiler/rendering claim is made. Requires a C++ compiler.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from test_egun import function as extracted, mask

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
NAMES = ('gf_GSIs', 'gf_GSActive', 'gf_GSReset', 'gf_GSStageDeath',
         'gf_GSFlushDeaths', 'gf_GSNightNotice', 'gf_GSHostDied',
         'gf_GSFirstDawn', 'gf_GSPrepareNight', 'gf_GSApplyShield',
         'gf_GSAttack', 'gf_GSResolveKills')


def report(source: str) -> None:
    for name in ('gf_GSKillPlayerDirect', 'auto_gf_KillPlayer_TriggerFunc',
                 'gf_SequencePrep', 'gf_SequenceKills', 'gt_NightSequence_Func',
                 'gf_ESBodyguardKill', 'gf_SKF_1_fayi'):
        body = extracted(source, name)
        start = source.index(body)
        first = source.count('\n', 0, start) + 1
        last = first + body.count('\n')
        print(f'{name}: lines {first}..{last}')


def check_wiring(source: str) -> None:
    prep = extracted(source, 'gf_SequencePrep')
    kills = extracted(source, 'gf_SequenceKills')
    night = extracted(source, 'gt_NightSequence_Func')
    direct = extracted(source, 'gf_GSKillPlayerDirect')
    wrapper = extracted(source, 'auto_gf_KillPlayer_TriggerFunc')
    guard = extracted(source, 'gf_ESBodyguardKill')
    coroner = extracted(source, 'gf_SKF_1_fayi')
    assert prep.count('gf_GSPrepareNight();') == 1
    assert kills.index('gf_GSApplyShield();') < kills.index('gf_SKK_1_bashisiji(lv_a);')
    assert kills.index('gf_GSResolveKills();') < kills.index('gf_SKK_3_zonghuozhe(lv_a);')
    assert night.index('gf_SequencePrep();') < night.index('gf_SequenceBullshit();') < night.index('gf_SequenceKills();')
    assert night.index('gf_SequenceAfter2();') < night.index('gf_GSFirstDawn();') < night.index('gv_dayNumber += 1;')
    removal = direct.index('PlayerGroupRemove(gv_alivePlayers, lp_player);')
    assert direct.index('gf_GSHostDied(lp_player);') > removal
    assert 'gf_KillPlayer(' not in direct
    assert 'auto_gf_KillPlayer_lp_' not in direct
    assert 'lp_gsStaged == true' in direct
    assert 'return gf_GSKillPlayerDirect(lp_player, lp_disguised, false);' in wrapper
    # Original full cleanup must remain, never a lightweight corpse-only replacement.
    for token in ('gv_bankGeneralIntegers[lp_player][18] -= 1;', 'gf_CAssembleMainBank(lp_player);',
                  'TextTagDestroy(gv_nameTag[lp_player]);', 'UnitRemove(gv_unit[lp_player]);',
                  'gv_corpse[lp_player] =', 'gf_XRLifeNote(lp_player, (lp_disguised == false));'):
        assert token in direct, token

    assert guard.count('if (!((gf_GSIs(lp_killer) == true) && (gv_gsSacrificed[lp_killer] == true) && (PlayerGroupHasPlayer(gv_alivePlayers, lp_killer) == false))) {') == 2
    for code in 'qrst':
        assert f'lv_b, lv_b) == "{code}"' in coroner
        assert f'GSCORONER{code.upper()}' in coroner

    report(source)
    print('PASS source wiring, full cleanup retention, all four coroner branches')


HARNESS_PREFIX = r'''
#include <cassert>
#include <iostream>
#include <string>
using text = std::string;
using string = std::string;
using soundlink = int;
int gv_gsHost[16], gv_gsStrike[16], gv_gsResult[16], gv_bhFeignRole[16];
bool gv_gsUsed[16], gv_gsShield[16], gv_gsSacrificed[16], gv_gsDeathPending[16];
int gv_roles[16][2], gv_action[16][2], gv_visitation[16], gv_jailed[16], gv_roleblocked[16];
int gv_damage[16], gv_guarded[16], gv_healing[16], gv_immuneChance[16], gv_specialCasePlayer[16][20];
bool gv_immune[16][4], gv_diedAtNight[16], gv_veteraned[16], gv_zuosi[16];
bool gv_witchEligible[16], gv_busEligible[16];
string gv_deathMethod[16], gv_deathText[16], gv_placedNote[16], gv_deathNote[16];
bool gv_deathDesc[16], alive[16], players[16];
bool gv_isNight = true, gv_nightEvents = false;
int phaseNotices = 0;
int gv_dayNumber = 1, gv_alivePlayers = 1, gv_players = 2;
int murders[16], trespass[16], killer[16], cleanup[16], bodyguardCalls;
int auditHost = 0, expectedDeadMask = 0;
void gf_GSHostDied(int);
void gf_GSFlushDeaths();

bool PlayerGroupHasPlayer(int group, int p) { assert(p >= 1 && p <= 15); return group == 1 ? alive[p] : players[p]; }
int PlayerGroupCount(int group) { int n = 0; for (int p=1;p<=15;p++) n += PlayerGroupHasPlayer(group,p); return n; }
void PlayerGroupRemove(int group, int p) { assert(group == 1 && p>=1 && p<=15); alive[p] = false; }
soundlink SoundLink(string, int) { return 0; }
text StringExternal(string key) { return key; }
void gf_BHNotify(text msg, int p, soundlink) { assert(p >= 1 && p <= 15); if(msg=="phase") phaseNotices++; }
void gf_BHVisitSelf(int p) { gv_visitation[p]=p; }
void gf_BHVisitAction(int p) { gv_visitation[p]=gv_action[p][0]; }
void gf_BHCrimeTrespass(int p) { trespass[p]++; }
void gf_BHCrimeMurder(int p) { murders[p]++; }
void gf_BHRecordNightKiller(int target,int actor) { if(target!=actor && !killer[target]) killer[target]=actor; }
bool gf_GSKillPlayerDirect(int p, bool, bool staged) {
    assert(p >= 1 && p <= 15);
    if(!alive[p] && !staged) return true;
    alive[p] = false;
    gf_GSHostDied(p);
    // Audit a simulated yielding cleanup: ALL of the host's dependents already disappeared.
    if(auditHost) for(int s=1;s<=15;s++) if(expectedDeadMask & (1<<s)) assert(!alive[s]);
    cleanup[p]++;
    return true;
}
void gf_ESBodyguardKill(int actor, int guard) {
    bodyguardCalls++;
    // Guard-side normal baseline immunity, heal, death. Real production skip guard checked separately.
    if(gv_immuneChance[guard]>0 || gv_immune[guard][0]) {
        if(gv_immuneChance[guard]>0) gv_immuneChance[guard]--;
    } else if(gv_healing[guard]>0) {
        gv_healing[guard]--;
    } else {
        gf_BHRecordNightKiller(guard,actor);
        gv_diedAtNight[guard]=true;
        gf_GSKillPlayerDirect(guard,false,false);
    }
    // Patched bodyguard never adds a second attacker death when sacrifice already removed actor.
    if(alive[actor]) { gv_diedAtNight[actor]=true; gf_GSKillPlayerDirect(actor,false,false); }
}
'''

HARNESS_TESTS = r'''
void setup(int hostPool=3) {
    auditHost=expectedDeadMask=0;
    bodyguardCalls=0;
    gv_dayNumber=1;
    gv_isNight=true;
    gv_nightEvents=false;
    phaseNotices=0;
    gf_GSReset();
    for(int p=0;p<=15;p++) {
        alive[p]=players[p]=p>0;
        gv_roles[p][0]=1; gv_roles[p][1]=1; gv_bhFeignRole[p]=0;
        gv_action[p][0]=gv_action[p][1]=gv_visitation[p]=0;
        gv_jailed[p]=gv_roleblocked[p]=gv_damage[p]=gv_guarded[p]=gv_healing[p]=gv_immuneChance[p]=0;
        gv_diedAtNight[p]=gv_veteraned[p]=gv_zuosi[p]=false;
        gv_deathMethod[p]=gv_deathText[p]=gv_placedNote[p]=gv_deathNote[p]="";
        gv_deathDesc[p]=false;
        murders[p]=trespass[p]=killer[p]=cleanup[p]=0;
        for(int j=0;j<4;j++) gv_immune[p][j]=false;
        for(int j=0;j<20;j++) gv_specialCasePlayer[p][j]=0;
    }
    gv_roles[1][0]=29; gv_roles[1][1]=3;
    gv_roles[2][1]=hostPool;
    gv_gsHost[1]=2;
}
void order() { gv_gsStrike[1]=3; gf_GSPrepareNight(); }
int main() {
    int cases=0;
    setup(); assert(gf_GSIs(1) && !gf_GSIs(2) && !gf_GSIs(0) && !gf_GSIs(16)); cases++;
    setup(); assert(gf_GSActive(1)); alive[2]=false; assert(!gf_GSActive(1)); cases++;
    setup(); alive[1]=false; assert(!gf_GSActive(1)); cases++;
    for(bool selecting : {true,false}) for(bool resolving : {true,false}) {
        setup(); gv_isNight=selecting; gv_nightEvents=resolving;
        gf_GSNightNotice("phase");
        assert(phaseNotices == ((selecting || resolving) ? 15 : 0)); cases++;
    }
    setup(); gv_gsUsed[1]=true; gv_gsResult[1]=2; gf_GSReset();
    assert(!gv_gsUsed[1] && gv_gsResult[1]==0 && gv_gsHost[1]==0); cases++;

    for(int pool : {1,2,5}) {
        setup(pool); gv_gsShield[1]=true; gf_GSPrepareNight(); gf_GSApplyShield();
        assert(gv_gsUsed[1] && gv_immune[2][0] && alive[1] && !gv_diedAtNight[1]);
        assert(gv_visitation[1]==1 && !gv_witchEligible[1] && !gv_busEligible[1]);
        // A later night never restores this single lifetime opportunity.
        gv_immune[2][0]=false; gv_dayNumber++;
        gv_gsShield[1]=true; gf_GSApplyShield(); assert(!gv_immune[2][0]); cases++;
    }
    for(int block : {1,2,3}) {
        setup(1); gv_gsShield[1]=true;
        if(block==1) gv_roleblocked[1]=4;
        if(block==2) gv_jailed[1]=4;
        if(block==3) gv_jailed[2]=4;
        gf_GSApplyShield(); assert(!gv_gsUsed[1] && !gv_immune[2][0] && alive[1]); cases++;
    }
    setup(); gv_gsShield[1]=true; gf_GSApplyShield(); assert(!gv_gsUsed[1]); cases++;
    setup(); gv_action[2][0]=7; order();
    assert(gv_action[1][0]==3 && gv_visitation[1]==3 && gv_action[2][0]==7);
    assert(gv_witchEligible[1] && gv_busEligible[1]); cases++;

    for(int block : {1,2,3,4,5,6,7}) {
        setup(); order();
        if(block==1) { gv_roleblocked[1]=4; gv_visitation[1]=0; }
        if(block==2) gv_jailed[1]=4;
        if(block==3) gv_jailed[2]=4;
        if(block==4) { alive[2]=false; gv_diedAtNight[2]=true; }
        if(block==5) { alive[3]=false; gv_diedAtNight[3]=true; }
        if(block==6) gv_veteraned[1]=true;
        if(block==7) gv_visitation[1]=0;
        gf_GSResolveKills(); assert(!gv_gsUsed[1] && !gv_gsSacrificed[1] && alive[1]); cases++;
    }
    setup(); order(); gv_action[2][0]=8; gf_GSResolveKills();
    assert(!alive[1] && !alive[3] && alive[2]);
    assert(gv_gsUsed[1] && gv_gsSacrificed[1] && gv_action[2][0]==8);
    assert(killer[3]==1 && murders[1]==1 && trespass[1]==1);
    assert(gv_damage[1]==1 && gv_damage[3]==1 && cleanup[1]==1 && cleanup[3]==1);
    assert(gv_deathMethod[1]=="t" && gv_deathMethod[3]=="q"); cases++;

    setup(); order(); gv_visitation[1]=4; gf_GSResolveKills();
    assert(alive[3] && !alive[4] && killer[4]==1); cases++;
    setup(); order(); gv_visitation[1]=1; gf_GSResolveKills();
    assert(!alive[1] && gv_damage[1]==1 && cleanup[1]==1 && gv_deathMethod[1]=="t"); cases++;
    setup(); order(); gv_visitation[1]=2; gf_GSResolveKills();
    assert(!alive[1] && !alive[2] && gv_deathMethod[1]=="t" && gv_damage[1]==1); cases++;

    for(int defense : {1,2,3}) {
        setup(); order();
        if(defense==1) gv_healing[3]=1;
        if(defense==2) gv_immune[3][0]=true;
        if(defense==3) gv_immuneChance[3]=1;
        gf_GSResolveKills();
        assert(!alive[1] && alive[3] && gv_gsUsed[1] && gv_gsSacrificed[1]);
        assert(gv_healing[3]==0 && gv_immuneChance[3]==0 && murders[1]==0 && cleanup[1]==1);
        cases++;
    }
    setup(); order(); gv_guarded[3]=4; gf_GSResolveKills();
    assert(bodyguardCalls==1 && alive[3] && !alive[4] && !alive[1]);
    assert(killer[4]==1 && murders[1]==1 && gv_guarded[3]==0 && gv_damage[1]==1); cases++;
    setup(); order(); gv_guarded[3]=4; gv_healing[4]=1; gf_GSResolveKills();
    assert(bodyguardCalls==1 && alive[3] && alive[4] && !alive[1] && gv_healing[4]==0); cases++;

    // Deterministic bond deaths ignore invulnerability/healing; all linked sym stage before cleanup yields.
    for(bool night : {true,false}) {
        setup(); gv_isNight=night;
        gv_roles[5][0]=29; gv_roles[5][1]=3; gv_gsHost[5]=2;
        gv_healing[1]=9; gv_immune[1][0]=true; gv_immuneChance[1]=9;
        auditHost=2; expectedDeadMask=(1<<1)|(1<<5);
        gf_GSKillPlayerDirect(2,false,false);
        assert(!alive[1] && !alive[5] && gv_damage[1]==1 && gv_damage[5]==1);
        assert(cleanup[1]==1 && cleanup[5]==1 && gv_deathMethod[1]=="s");
        gf_GSHostDied(2); assert(gv_damage[1]==1 && cleanup[1]==1); cases++;
    }
    setup(); gv_diedAtNight[1]=true; gv_damage[1]=1; alive[2]=false; gf_GSHostDied(2);
    assert(gv_damage[1]==1 && cleanup[1]==0); cases++;
    setup(); gv_gsHost[1]=0; gv_immune[1][0]=true; gv_healing[1]=9;
    gf_GSFirstDawn(); assert(!alive[1] && gv_deathMethod[1]=="r" && cleanup[1]==1); cases++;
    setup(); gv_gsHost[1]=0; gv_dayNumber=2; gf_GSFirstDawn(); assert(alive[1]); cases++;
    setup(); gf_GSFirstDawn(); assert(alive[1]); cases++;
    std::cout << "PASS " << cases << " extracted-source combat/lifecycle scenarios\n";
}
'''


def run_harness(core: str) -> None:
    bodies = [extracted(core, name) for name in NAMES]
    definitions = '\n\n'.join(bodies)
    # Actual Galaxy definitions, only language aliases differ; no business-logic rewrite.
    prototypes = '\n'.join(chunk[:chunk.index('{')].strip() + ';' for chunk in bodies)
    assert mask(definitions).count('{') == mask(definitions).count('}')
    program = HARNESS_PREFIX + prototypes + '\n' + definitions + '\n' + HARNESS_TESTS
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'C++ compiler required'
    with tempfile.TemporaryDirectory(prefix='gs-core-test-') as directory:
        cpp, binary = Path(directory) / 'core.cpp', Path(directory) / 'core'
        cpp.write_text(program)
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    source = args.script.read_text()
    check_wiring(source)
    stage = extracted(source, 'gf_GSStageDeath')
    assert 'Wait(' not in stage and 'gf_KillPlayer(' not in stage
    assert 'gv_gsUsed[lv_p] = true' not in extracted(source, 'gf_GSPrepareNight')
    run_harness(source)


if __name__ == '__main__':
    main()
