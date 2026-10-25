#!/usr/bin/env python3
"""Execute actual Galaxy trap bodies in a C++ engine-stub harness.

Not an SC2 compiler/rendering test. Optional --baseline compares town traps to
an unchanged script (randomized fixtures, including protection and visitation2).
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
    depth = 1
    for end in range(start + 1, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return end + 1

    raise AssertionError('unbalanced block')


def function(source: str, name: str) -> str:
    match = re.search(r'^(?:void|bool|int) ' + re.escape(name) + r'\s*\([^;\n]*\)\s*\{', source, re.M)
    assert match, name
    start = source.index('{', match.start())
    return source[match.start():balanced_end(source, start)]


def harness(source: str, baseline: str | None) -> str:
    names = [
        'gf_BHConverted', 'gf_BHFaction',
        'gf_HLGang', 'gf_HLCanPlace', 'gf_HLGangSetup', 'gf_HLGangPick',
        'gf_RANoActions', 'gf_RAForesterActions', 'gf_SKA2_1_hulinren',
        'gf_SKP_1_hulinren_0', 'gf_BHVisit', 'gf_BHVisitAction', 'gf_BHWentTo',
        'gf_HLTier', 'gf_HLImmune', 'gf_HLIsVictim', 'gf_HLSnap',
        'gf_ESForesterKill', 'gf_HLResolveOne', 'gf_HLForesterNight',
    ]
    bodies = [function(source, name) for name in names]
    if baseline:
        old_names = ['gf_HLTier', 'gf_HLImmune', 'gf_HLIsVictim', 'gf_HLSnap',
                     'gf_HLResolveOne', 'gf_HLForesterNight']
        bodies += [re.sub(r'\bgf_HL', 'base_gf_HL', function(baseline, n)) for n in old_names]

    # Execute the actual new random-fit conditions, not a reimplementation.
    fit = function(source, 'gf_BHRoleFitsKind')
    clauses = []
    for pool in (2, 5):
        match = re.search(rf'    if \(\(lp_pool == {pool}\) && \(lp_role == 20\)\) \{{\n.*?\n    }}', fit, re.S)
        assert match, pool
        clauses.append(match.group())

    bodies += ['bool trapFits (int lp_kind, int lp_pool, int lp_role) {\n' + '\n'.join(clauses) + '\nreturn false;\n}']
    bodies += ['bool gf_BHRoleFitsKind (int lp_kind, int lp_pool, int lp_role) { return trapFits(lp_kind, lp_pool, lp_role); }']
    weighting = function(source, 'gf_OSRandomize')
    parts = []
    for pool in (2, 5):
        start = weighting.index(f'            if ((lv_a == {pool}) && (lv_b >= 1) && (lv_b <= gv_mafiaTriadMax))')
        parts.append(weighting[start:balanced_end(weighting, weighting.index('{', start))])

    bodies += ['void cumulative () { int lv_a; int lv_b; for(lv_a=2; lv_a<=5; lv_a+=3) { for(lv_b=1; lv_b<=22; lv_b+=1) {\n' + '\n'.join(parts) + '\n}}}']
    matrix = function(source, 'gf_OSRandomizeMatrix')
    parts = []
    for pool in (2, 5):
        start = matrix.index(f'    if ((lv_y >= gv_finalWeights[{pool}][19])')
        parts.append(matrix[start:balanced_end(matrix, matrix.index('{', start))])

    bodies += ['void pickTrap (int lv_a, int lv_x, fixed lv_y) {\n' + '\n'.join(parts) + '\n}']
    code = '\n\n'.join(bodies)
    code = re.sub(r'\b(int|bool|text|string)((?:\[\d+\])+)( +)(\w+)', r'\1\3\4\2', code)
    used = set(re.findall(r'\bgv_\w+', code))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not used - declarations.keys(), used - declarations.keys()
    globals_text = '\n'.join(declarations[n] for n in sorted(used))
    resets = '\n'.join(f'    clearValue({n});' for n in sorted(used))
    headers = '\n'.join(re.match(r'.*?\{', b, re.S).group(0)[:-1] + ';' for b in bodies)
    calls = set(re.findall(r'\b(\w+)\s*\(', re.sub(r'//[^\n]*|"(?:\\.|[^"\\])*"', '', code)))
    known = set(re.findall(r'^(?:void|bool|int) (\w+)\s*\(', code, re.M)) | {
        'if', 'else', 'for', 'while', 'return', 'StringExternal', 'StringToText',
        'IntToText', 'TextWithColor', 'PlayerGroupSingle', 'PlayerGroupAll',
        'PlayerGroupHasPlayer', 'PlayerGroupNextPlayer', 'RandomInt', 'RandomFixed',
        'DialogControlSetVisible', 'gf_CBSystemMessage', 'gf_KillPlayer',
        'gf_BHRecordNightKiller', 'gf_BHCrimeMurder',
    }
    stubs = '\n'.join(f'template<class... A> int {n}(A...) {{ ++calls["{n}"]; return 0; }}' for n in sorted(calls - known))
    constants = '\n'.join(f'constexpr int {n} = {i};' for i, n in enumerate(sorted(set(re.findall(r'\bc_\w+', code))), 1))
    return r'''
#include <algorithm>
#include <cassert>
#include <iostream>
#include <map>
#include <random>
#include <string>
#include <tuple>
#include <vector>
using std::string;
using text = string;
using playergroup = int;
using fixed = double;
using soundlink = int;
using color = int;
std::map<string,int> calls;
std::map<int,bool> visible;
std::vector<int> killed, murderers;
std::vector<std::pair<int,int>> killers;
std::vector<std::pair<string,int>> messages;
int chosen = 1;
string StringExternal(string s) { return s; }
string StringToText(string s) { return s; }
string IntToText(int i) { return std::to_string(i); }
string TextWithColor(string s, int) { return s; }
int PlayerGroupSingle(int p) { return 1 << p; }
int PlayerGroupAll() { return 65534; }
bool PlayerGroupHasPlayer(int g, int p) { assert(p >= 1 && p <= 15); return (g & (1 << p)) != 0; }
int PlayerGroupNextPlayer(int g, int p) {
    for (++p; p <= 15; ++p) if (PlayerGroupHasPlayer(g,p)) return p;
    return -1;
}
int RandomInt(int lo, int hi) { assert(lo <= hi); return std::clamp(chosen,lo,hi); }
double RandomFixed(double lo, double) { return lo; }
void DialogControlSetVisible(int control, int, bool v) { visible[control] = v; }
template<class... A> void gf_CBSystemMessage(string s, int p, A...) { messages.emplace_back(s,p); }
void gf_KillPlayer(int p, bool) { killed.push_back(p); }
void gf_BHRecordNightKiller(int p, int killer) { killers.emplace_back(p,killer); }
void gf_BHCrimeMurder(int p) { murderers.push_back(p); }
template<class T> void clearValue(T &v) { v = T{}; }
template<class T, size_t N> void clearValue(T (&v)[N]) { for (auto &x: v) clearValue(x); }
''' + globals_text + '\n' + constants + '\n' + stubs + '\n' + headers + '\n' + code + r'''
void reset(int pool = 2) {
''' + resets + r'''
    calls.clear(); visible.clear(); killed.clear(); killers.clear(); murderers.clear(); messages.clear(); chosen = 1;
    gv_alivePlayers = 65534;
    gv_isNight = true;
    gv_dayNumber = 2;
    for (int p=1; p<=15; ++p) {
        gv_roles[p][1] = 1;
        gv_roles[p][0] = 1;
        for (int i=0; i<7; ++i) gv_actionDialogItem[p][i] = p*10+i;
    }
    gv_roles[1][1] = pool;
    gv_roles[1][0] = pool == 1 ? 22 : 20;
    gv_shots[1] = 2;
    gv_hlGangInitialized[1] = true;
}
void arm(int pool = 2, int left = 2) {
    reset(pool);
    gv_hlHouse[1][0] = 15;
    gv_hlLeft[1][0] = left;
    gv_hlFaction[1][0] = pool;
}
void visit(int p, int pool, bool second = false) {
    gv_roles[p][1] = pool;
    if (second) gv_visitation2[p] = 15;
    else gv_visitation[p] = 15;
}
void settle() { gf_HLResolveOne(1,0); }
void expectKill(int p) {
    assert(killed == std::vector<int>{p});
    assert(killers == (std::vector<std::pair<int,int>>{{p,1}}));
    assert(murderers == std::vector<int>{1});
    assert(gv_deathMethod[p] == "T" && gv_damage[p] == 1 && gv_diedAtNight[p]);
}
int main() {
    for (int pool: {2,5}) {
        int enemy = pool == 2 ? 5 : 2;
        // Initialization, first night, and idempotent UI (no free refills).
        reset(pool); gv_dayNumber=1; gv_hlGangInitialized[1]=false; gv_shots[1]=-1;
        gf_HLGangSetup(1);
        assert(gv_shots[1]==2 && !visible[25] && !gf_HLCanPlace(1));
        gf_HLGangPick(1,15); assert(gv_action[1][0]==0);
        gv_dayNumber=2; gf_HLGangSetup(1); assert(visible[25] && visible[15]);
        gf_HLGangPick(1,15); assert(gv_action[1][0]==15);
        // Bus immunity and actual-visit landing (witch can still change visit).
        gv_busEligible[1]=true; gf_SKP_1_hulinren_0(1); assert(!gv_busEligible[1]);
        gf_BHVisitAction(1); assert(gv_visitation[1]==15);
        gv_visitation[1]=14; gf_HLForesterNight();
        assert(gv_hlHouse[1][0]==14 && gv_hlLeft[1][0]==1 && gv_shots[1]==1 && gv_hlNextNight[1]==4);
        gv_dayNumber=3; gf_HLGangSetup(1); assert(!visible[25] && gv_shots[1]==1);
        gv_action[1][0]=0; gf_HLGangPick(1,15); assert(gv_action[1][0]==0);
        // Forced stale visit during cooldown cannot spend a charge, but old trap expires.
        gf_HLForesterNight(); assert(gv_shots[1]==1 && gv_hlLeft[1][0]==0);
        gv_dayNumber=4; gf_HLGangSetup(1); assert(visible[25]);
        gf_HLGangPick(1,15); gf_BHVisitAction(1); gf_HLForesterNight();
        assert(gv_shots[1]==0 && gv_hlLeft[1][0]==1 && gv_hlNextNight[1]==6);
        gv_dayNumber=6; gf_HLGangSetup(1); assert(!visible[25] && gv_shots[1]==0);
        // Jail/block/death/zero shots: no new trap or cooldown consumed.
        for(int blocked=0; blocked<6; ++blocked) {
            reset(pool); gv_visitation[1]=15;
            if(blocked==0) gv_jailed[1]=2;
            if(blocked==1) gv_roleblocked[1]=2;
            if(blocked==2) gv_diedAtNight[1]=true;
            if(blocked==3) gv_veteraned[1]=true;
            if(blocked==4) gv_alivePlayers &= ~(1<<1);
            if(blocked==5) gv_shots[1]=0;
            int shots=gv_shots[1]; gf_HLForesterNight();
            assert(gv_shots[1]==shots && gv_hlNextNight[1]==0 && gv_hlLeft[1][0]==0);
        }
        for(int state=0; state<3; ++state) {
            reset(pool);
            if(state==0) gv_isNight=false;
            if(state==1) gv_gameOver=true;
            if(state==2) gv_nightProcessingPhase=true;
            gf_HLGangPick(1,15); assert(gv_action[1][0]==0);
        }
        reset(pool); gf_HLGangPick(1,0); gf_HLGangPick(1,16); assert(!gv_action[1][0]);
        // Friendly-only visitors never trigger a trap; no-visitor traps last exactly two nights.
        arm(pool); visit(2,pool); settle(); assert(killed.empty() && gv_hlLeft[1][0]==1);
        settle(); assert(killed.empty() && gv_hlLeft[1][0]==0);
        // Priority is town, opposite gang, then neutral. vis2 counts as visiting.
        arm(pool); visit(2,3); visit(3,enemy); visit(4,1,true); visit(5,pool); settle(); expectKill(4);
        arm(pool); visit(2,3); visit(3,enemy); visit(5,pool); settle(); expectKill(3);
        arm(pool); visit(2,3,true); visit(5,pool); settle(); expectKill(2);
        // Ties are randomized within the highest priority class, never across classes.
        for(int pick: {1,2}) {
            arm(pool); visit(2,1); visit(3,1); visit(4,enemy); chosen=pick;
            settle(); expectKill(pick+1);
        }
        // Existing traps still work while the owner is blocked, jailed, dead, or cooling down.
        for(int status=0; status<4; ++status) {
            arm(pool); visit(2,1);
            if(status==0) gv_roleblocked[1]=2;
            if(status==1) gv_jailed[1]=2;
            if(status==2) { gv_alivePlayers &= ~(1<<1); gv_diedAtNight[1]=true; }
            if(status==3) gv_hlNextNight[1]=4;
            settle(); expectKill(2);
        }
        // Trap allegiance is captured when placed, not changed by later conversion.
        arm(pool); visit(2,pool); visit(3,enemy); gv_roles[1][1]=3; settle(); expectKill(3);
        // Invalid, already dead, householder, and setter are not eligible visitors.
        arm(pool); visit(2,1); gv_diedAtNight[2]=true; gv_visitation[15]=15; gv_visitation[1]=15;
        settle(); assert(killed.empty() && gv_hlLeft[1][0]==1);
        arm(pool); visit(2,1); gv_alivePlayers &= ~(1<<2); settle(); assert(killed.empty());
        // Healing consumes the trigger; invincible visitors are skipped, as in town traps.
        arm(pool); visit(2,1); gv_healing[2]=1; settle(); assert(killed.empty() && gv_hlLeft[1][0]==0);
        arm(pool); visit(2,1); gv_immune[2][0]=true; settle(); assert(killed.empty() && gv_hlLeft[1][0]==1);
        arm(pool); visit(2,1); gv_immune[2][0]=true; visit(3,enemy); settle(); expectKill(3);
        // Bodyguard interception: guard is attacked, visitor lives. Healing protects guard too.
        arm(pool); visit(2,1); gv_guarded[2]=3; settle(); expectKill(3); assert(!gv_diedAtNight[2]);
        arm(pool); visit(2,1); gv_guarded[2]=3; gv_healing[3]=1; settle(); assert(killed.empty());
        arm(pool); visit(2,1); gv_guarded[2]=3; gv_roles[3][1]=pool; settle(); assert(killed.empty());
        // Cooldown night: old trap fires, second use remains available only on night4.
        arm(pool,1); visit(2,1); gv_dayNumber=3; gv_hlNextNight[1]=4; gv_shots[1]=1;
        gv_visitation[1]=15; gf_HLForesterNight(); expectKill(2); assert(gv_shots[1]==1);
        // Random seat fit: faction support/killing/general, but never leader or wrong faction.
        reset(pool);
        for(int kind=1; kind<=22; ++kind) {
            bool allowed = kind==1 || (pool==2 ? (kind==3||kind==9||kind==11) : (kind==15||kind==16||kind==18));
            assert(trapFits(kind,pool,20)==allowed);
        }
        gv_roleOptions[4][1][0]=true; assert(!trapFits(1,pool,20));
        int general=pool==2?3:15; gv_roleOptions[4][general][0]=true;
        assert(!trapFits(general,pool,20));
    }
    // Actual cumulative/mapping blocks: role20 has a nonempty interval only when weighted;
    // Leaders17–19/22 stay excluded; ordinary lawyer21 remains weighted.
    reset(); gv_townMax=34; gv_mafiaTriadMax=22; gv_finalWeights[1][34]=10.0;
    for(int pool: {2,5}) {
        for(int r=1; r<=22; ++r) gv_roleWeights[pool][r]=1.0;
        gv_roleWeights[pool][20]=0.0;
    }
    cumulative();
    assert(gv_finalWeights[2][20]==26.0 && gv_finalWeights[5][20]==43.0);
    for(int pool: {2,5}) {
        assert(gv_finalWeights[pool][19]==gv_finalWeights[pool][16]);
        assert(gv_finalWeights[pool][21]==gv_finalWeights[pool][20]+1.0);
        assert(gv_finalWeights[pool][22]==gv_finalWeights[pool][21]);
        gv_roles[1][1]=0; gv_roles[1][0]=0; gv_rolesArray[1]=pool==2?3:15;
        pickTrap(1,1,gv_finalWeights[pool][20]); assert(!gv_roles[1][1]);
    }
    gv_roleWeights[2][20]=0.5; gv_roleWeights[5][20]=0.5; cumulative();
    for(int pool: {2,5}) {
        gv_roles[1][1]=0; gv_rolesArray[1]=pool==2?3:15;
        // Not a unique role: explicitly setting [10] must not prevent another random copy.
        gv_roleOptions[pool][20][10]=true;
        pickTrap(1,1,(gv_finalWeights[pool][19]+gv_finalWeights[pool][20])/2.0);
        assert(gv_roles[1][1]==pool && gv_roles[1][0]==20);
    }
    // Original town forester still plants on consecutive nights without gang cooldown.
    reset(1); gv_visitation[1]=15; gf_HLForesterNight();
    gv_dayNumber=3; gv_visitation[1]=14; gf_HLForesterNight();
    assert(gv_shots[1]==0 && gv_hlNextNight[1]==0 && gv_hlHouse[1][1]==14);
''' + town_comparison(bool(baseline)) + r'''
    std::cout << "PASS: actual trap bodies, both factions, cooldown/lifetime, clicks, visitation, protection, random fit" << std::endl;
}
'''


def town_comparison(enabled: bool) -> str:
    if not enabled:
        return ''

    return r'''
    // Seeded differential comparison against actual pre-change town trap functions.
    std::mt19937 rng(0x54524150);
    for(int iteration=0; iteration<3000; ++iteration) {
        int seed=rng();
        auto fixture = [seed]() {
            std::mt19937 r(seed);
            arm(1);
            for(int p=2; p<=14; ++p) {
                const int pools[]={1,2,5,3};
                gv_roles[p][1]=pools[r()%4];
                gv_visitation[p]=(r()%2)?15:0;
                gv_visitation2[p]=(r()%3)?0:15;
                gv_diedAtNight[p]=r()%6==0;
                gv_immune[p][0]=r()%5==0;
                gv_healing[p]=r()%5==0;
                gv_jailed[p]=r()%8==0;
                gv_roleblocked[p]=r()%8==0;
            }
            gv_guarded[2]=(r()%3)?0:3;
        };
        auto result = []() {
            string state;
            for(int p=1; p<=15; ++p) state += gv_deathMethod[p]+":"+std::to_string(gv_damage[p])+":"+std::to_string(gv_diedAtNight[p])+":"+std::to_string(gv_guarded[p])+":"+std::to_string(gv_veteraned[p])+";";
            return std::make_tuple(killed,killers,murderers,messages,state,gv_hlLeft[1][0]);
        };
        fixture(); base_gf_HLResolveOne(1,0); auto old=result();
        fixture(); gf_HLResolveOne(1,0); assert(old==result());
    }
    std::cout << "PASS: 3000 differential fixtures preserve original town trap behavior" << std::endl;
'''


def static_wiring(source: str) -> None:
    for name in ['gf_RSMafiaSetup2', 'gf_RSTriadSetup']:
        assert function(source, name).count('gf_HLGangSetup(lv_a);') == 1, name

    for name in ['gt_ASActionButtonAMafia_Func', 'gt_ASActionButtonATriad_Func']:
        assert function(source, name).count('gf_HLGangPick(lv_source, lv_target);') == 1, name

    prep = function(source, 'gf_SequencePrep')
    assert 'gf_HLGang(lv_a)' in prep and 'gf_HLCanPlace(lv_a)' in prep
    for pool in (2, 5):
        matrix = function(source, 'gf_OSRandomizeMatrix')
        assert f'gf_BHRoleFitsKind(gv_rolesArray[lv_x], {pool}, 20)' in matrix
        assert f'gv_finalWeights[{pool}][20]' in matrix

    for name in ['gf_OSGenerateChances', 'gf_OSRandomize']:
        body = function(source, name)
        assert body.count('if ((((lv_b >= 17) && (lv_b <= 19)) || (lv_b == 22)))') == 2

    print('PASS: setup/click/prep/random wiring, old leader separation')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    source = SCRIPT.read_text()
    static_wiring(source)
    baseline = args.baseline.read_text() if args.baseline else None
    code = harness(source, baseline)
    with tempfile.TemporaryDirectory(prefix='bh-trap-tests-') as tmp:
        cpp, exe = Path(tmp) / 'traps.cpp', Path(tmp) / 'traps'
        cpp.write_text(code)
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
