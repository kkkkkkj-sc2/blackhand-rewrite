#!/usr/bin/env python3
"""Translate and execute the actual integrated 恶棍 Galaxy core with UBSan/bounds.

Default is --core work/blackhand/CustomLogic.galaxy.
Only Galaxy array declaration syntax is translated; every core function body is
compiled verbatim. Engine declarations, BHCrime and BHWentTo come from --script.
The external death presentation and ordinary attack are explicit engine doubles.
Randomized expectations are computed independently in C++, not a second copy of
Prepare/Resolve. No SC2 compiler/rendering claim is made.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
CORE = SCRIPT
NAMES = ('gf_EGIs', 'gf_EGCanAct', 'gf_EGName', 'gf_EGReset',
         'gf_EGInjure', 'gf_EGPrepareNight', 'gf_EGResolveNight')


def mask(source: str) -> str:
    """Keep offsets/newlines while hiding strings/comments for structural scans."""
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), source)


def function(source: str, name: str) -> str:
    live = mask(source)
    match = re.search(r'^(?:void|bool|int|text)\s+' + re.escape(name)
                      + r'\s*\([^;{}]*\)\s*\{', live, re.M)
    assert match, f'missing function {name}'
    depth = 1
    start = match.end()
    while depth:
        assert start < len(live), f'unbalanced function {name}'
        depth += (live[start] == '{') - (live[start] == '}')
        start += 1

    return source[match.start():start]


def translate(source: str) -> str:
    return re.sub(r'\b(int|bool|text|string)((?:\[\d+\])+)\s+(\w+)',
                  r'\1 \3\2', source)


def harness(source: str, core: str) -> str:
    bodies = [function(core, name) for name in NAMES]
    bodies += [function(source, name) for name in ('gf_BHCrime', 'gf_BHWentTo')]
    code = '\n\n'.join(bodies)
    live = mask(code)
    assert not re.search(r'\b(?:gf_BHCrimeMurder|gf_BHRecordNightKiller|gf_ESBodyguardKill|Wait|TriggerExecute)\s*\(', live)
    assert not re.search(r'\bgv_(?:healing|immuneChance|immune)\s*\[[^;\n]*\]\s*(?:[+\-*/]?=(?!=)|\+\+|--)', live), 'core must not consume defenses'
    crimes = re.findall(r'\bgf_BHCrime\(([^,]+),\s*(\d+)\)', live)
    assert crimes == [('lp_actor', '4')], ('successful injury only: crime4, never 1/7', crimes)
    resolve = mask(function(core, 'gf_EGResolveNight'))
    for name in ('gv_healing', 'gv_immuneChance', 'gv_visitation', 'gv_visitation2'):
        assert not re.search(r'\b' + name + r'\b', resolve), ('post-attack recheck', name)

    required = set(re.findall(r'\bgv_\w+', live)) | {
        'gv_action', 'gv_damage', 'gv_healing', 'gv_guarded',
        'gv_deathMethod', 'gv_deathText', 'gv_e78AAFE7BDAAE4BA8BE5AE9E',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source + '\n' + core, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not required - declarations.keys(), ('missing declarations', required - declarations.keys())
    for name in required:
        if name.startswith('gv_eg') and name not in ('gv_egPreparedNight', 'gv_egResolvedNight'):
            assert '[16]' in declarations[name], ('player bounds', name)

    globals_text = '\n'.join(declarations[n] for n in sorted(required))
    resets = '\n'.join(f'    clearValue({n});' for n in sorted(required))
    prototypes = '\n'.join(b.split('{', 1)[0].strip() + ';' for b in bodies)
    declared_core = set(re.findall(r'^(?:void|bool|int|text)\s+(gf_EG\w+)\s*\([^;{}]*\)\s*\{', mask(core), re.M))
    # --core may also point at the integrated script. Win/presentation helpers
    # are owned by the main thread and deliberately outside this logic harness.
    declared_core -= {'gf_EGWoundDeath', 'gf_EGWon'}
    assert declared_core == set(NAMES), ('untested new core function', declared_core ^ set(NAMES))
    calls = set(re.findall(r'\b(\w+)\s*\(', live))
    supported = set(NAMES) | {
        'gf_BHCrime', 'gf_BHWentTo', 'if', 'while', 'return',
        'PlayerGroupHasPlayer', 'StringToText', 'IntToText', 'TextWithColor',
        'libNtve_gf_ConvertPlayerColorToColor', 'gf_BHNotify', 'SoundLink',
        'StringExternal', 'gf_EGWoundDeath',
    }
    assert not calls - supported, ('unstubbed actual call', calls - supported)

    return r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <climits>
#include <iostream>
#include <random>
#include <string>
#include <tuple>
#include <vector>
using std::string;
using text = string;
using playergroup = unsigned int;
using soundlink = string;
''' + globals_text + r'''
struct Message { text value; int target; soundlink sound; };
std::vector<Message> messages;
std::vector<int> deaths;
int killerCredit[16];
int guardRetaliations;
int attackRescues;
int checks;

template<class T> void clearValue(T& x) { x = T{}; }
template<class T, size_t N> void clearValue(T (&x)[N]) {
    for (auto& item: x) clearValue(item);
}
bool PlayerGroupHasPlayer(playergroup group, int p) {
    assert(p >= 1 && p <= 15);
    return (group & (1u << p)) != 0;
}
text StringExternal(const char* key) { return string("{") + key + "}"; }
text StringToText(const string& value) { return value; }
text IntToText(int value) { return std::to_string(value); }
text TextWithColor(const text& value, int color) {
    return "<color" + std::to_string(color) + ">" + value + "</color>";
}
int libNtve_gf_ConvertPlayerColorToColor(int color) { return color; }
soundlink SoundLink(const char* sound, int index) {
    assert(index == -1);
    return sound;
}
void gf_BHNotify(text message, int target, soundlink sound) {
    assert(target >= 1 && target <= 15);
    messages.push_back({message, target, sound});
}
// This is the documented external-helper contract, not a fake implementation of
// any core logic. In particular it deliberately DOES NOT inspect live defenses.
void gf_EGWoundDeath(int target) {
    assert(target >= 1 && target <= 15);
    assert(PlayerGroupHasPlayer(gv_alivePlayers, target));
    assert(!gv_diedAtNight[target]);
    ++gv_damage[target];
    gv_deathMethod[target] += "[wound]";
    gv_deathText[target] += "[pain]";
    gv_diedAtNight[target] = true;
    gv_alivePlayers &= ~(1u << target);
    deaths.push_back(target);
    gf_BHNotify(StringExternal("Param/Value/EGWOUNDDEATH"), target, "CivilianDeath");
}
''' + prototypes + '\n' + translate(code) + r'''
void reset(int players=15) {
''' + resets + r'''
    clearValue(killerCredit);
    messages.clear(); deaths.clear(); guardRetaliations=attackRescues=0;
    gv_dayNumber=1;
    for(int p=1; p<=15; ++p) {
        gv_roles[p][0]=1; gv_roles[p][1]=1;
        gv_name[p]="P" + std::to_string(p); gv_playerColor[p]=p;
        gv_number[p]=std::to_string(p);
        if(p<=players) gv_alivePlayers |= 1u << p;
    }
    gf_EGReset();
}
void role(int p, int pool, int id) { gv_roles[p][1]=pool; gv_roles[p][0]=id; }
void egun(int p, int target) { role(p,3,28); gv_visitation[p]=target; }
void nextNight() {
    ++gv_dayNumber;
    clearValue(gv_visitation); clearValue(gv_visitation2);
    clearValue(gv_healing); clearValue(gv_guarded); clearValue(gv_immune);
    clearValue(gv_roleblocked); clearValue(gv_jailed); clearValue(gv_veteraned);
    clearValue(gv_diedAtNight); clearValue(gv_damage);
    messages.clear(); deaths.clear();
}
int countMessage(int p, const string& key) {
    return std::count_if(messages.begin(),messages.end(),[&](const Message& m) {
        return m.target==p && m.value.find("Param/Value/" + key + "}")!=string::npos;
    });
}
bool alive(int p) { return PlayerGroupHasPlayer(gv_alivePlayers,p); }
void check(bool condition) { ++checks; assert(condition); }
void checkNoCredit() {
    for(int p=1;p<=15;++p) {
        check(killerCredit[p]==0);
        for(int c=0;c<=10;++c) {
            if(c!=4) check(!gv_e78AAFE7BDAAE4BA8BE5AE9E[p][c]);
        }
    }
    check(guardRetaliations==0);
}
void normalKill(int p) {
    ++gv_damage[p]; gv_diedAtNight[p]=true;
    gv_alivePlayers &= ~(1u<<p);
    gv_deathMethod[p]="ordinary"; gv_deathText[p]="ordinary text";
}
// Explicit consuming attack double: checks core leaves the counters available
// for the existing kill phase. It does not purport to test an SC2 ES* function.
void normalAttack(int p) {
    if(gv_immuneChance[p]>0) { --gv_immuneChance[p]; return; }
    if(gv_immune[p][0]) return;
    if(gv_healing[p]>0) { --gv_healing[p]; ++attackRescues; return; }
    normalKill(p);
}
void firstAndNextNight() {
    for(int a: {1,8,15}) for(int t: {1,8,15}) if(a!=t) {
        int v=24-a-t;
        reset(); egun(a,t); gv_visitation[v]=t;
        gf_EGPrepareNight(); check(gv_egWoundNight[t]==1);
        check(gv_e78AAFE7BDAAE4BA8BE5AE9E[a][4]);
        check(countMessage(t,"EGWOUND")==1 && countMessage(a,"EGATTACK1")==1);
        gf_EGResolveNight(); check(alive(t) && deaths.empty());
        nextNight(); gv_alivePlayers &= ~(1u<<a); // original egun dead
        gv_visitation2[v]=t; gf_EGPrepareNight();
        normalKill(v); // visitor no longer alive at resolution
        gv_visitation2[v]=0; // resolved visit cannot be lost
        gf_EGResolveNight(); check(!alive(t) && deaths==std::vector<int>{t});
        check(gv_egWoundNight[t]==0 && gv_damage[t]==1);
        check(countMessage(t,"EGWOUNDDEATH")==1);
        checkNoCredit();
    }
    // Identical grace applies to later new injuries, not merely calendar N1.
    reset(); gv_dayNumber=7; egun(1,8); gv_visitation[15]=8;
    gf_EGPrepareNight(); gf_EGResolveNight(); check(alive(8) && gv_egWoundNight[8]==7);
    nextNight(); gv_visitation[15]=8; gf_EGPrepareNight(); gf_EGResolveNight();
    check(!alive(8));
}
void boundariesAndGuards() {
    reset(); gv_number[1]="15";
    check(gf_EGName(1).find("15.P1")!=string::npos);
    check(gf_EGName(1).find("1.P1")==string::npos);
    for(int n: {1,8,15}) {
        reset(n); gf_EGPrepareNight(); gf_EGResolveNight(); check(deaths.empty());
        for(int p: {-100,0,16,INT_MAX}) {
            check(!gf_EGIs(p) && !gf_EGCanAct(p) && gf_EGName(p).empty());
            gf_EGInjure(p);
        }
        for(int target: {-1,0,16,INT_MAX}) {
            reset(n); egun(1,target); gv_visitation2[1]=target;
            gf_EGPrepareNight(); gf_EGResolveNight(); check(messages.empty());
        }
    }
    for(int a: {1,8,15}) for(int guard=0;guard<8;++guard) {
        reset(); int t=a==8?15:8; egun(a,t);
        if(guard==0) gv_roleblocked[a]=8;
        if(guard==1) gv_jailed[a]=8;
        if(guard==2) gv_alivePlayers &= ~(1u<<a);
        if(guard==3) gv_diedAtNight[a]=true;
        if(guard==4) gv_veteraned[a]=true;
        if(guard==5) gv_visitation[a]=a; // redirected self, not chosen target
        if(guard==6) gv_alivePlayers &= ~(1u<<t);
        if(guard==7) gv_diedAtNight[t]=true;
        gf_EGPrepareNight(); gf_EGResolveNight();
        check(!gv_egWoundNight[t] && !gv_e78AAFE7BDAAE4BA8BE5AE9E[a][4]);
        check(messages.empty());
    }
    reset(); egun(1,15); gv_action[1][0]=8;
    gf_EGPrepareNight(); check(gv_egWoundNight[15] && !gv_egWoundNight[8]);
    // No primary target means secondary visitaion is not an extra wound cast.
    reset(); egun(1,0); gv_visitation2[1]=8;
    gf_EGPrepareNight(); check(!gv_egWoundNight[8]);
}
void visitRulesAndBodyguard() {
    for(int slot: {0,1}) for(int visitorType=0;visitorType<6;++visitorType) {
        reset(); gv_dayNumber=2; gv_egWoundNight[8]=1;
        int v=visitorType==0?8:15;
        if(visitorType==1) role(v,3,28); // every egun exempt
        if(visitorType==2) role(v,1,28); // same role id, different pool not exempt
        if(visitorType==3) { role(v,1,11); gv_guarded[8]=v; }
        if(visitorType==4) gv_alivePlayers &= ~(1u<<v);
        if(visitorType==5) gv_diedAtNight[v]=true;
        (slot?gv_visitation2[v]:gv_visitation[v])=8;
        gf_EGPrepareNight(); gf_EGResolveNight();
        bool dies=visitorType==2 || visitorType==3;
        check(alive(8)!=dies && deaths.size()==size_t(dies));
        check(alive(15)==(visitorType!=4));
        check(gv_guarded[8]==(visitorType==3?15:0));
        checkNoCredit();
    }
    // Simultaneous duplicate slots/visitors cause exactly one injury death.
    reset(); gv_dayNumber=2; gv_egWoundNight[8]=1;
    gv_visitation[1]=gv_visitation2[1]=gv_visitation[15]=gv_visitation2[15]=8;
    gf_EGPrepareNight(); gf_EGResolveNight(); gf_EGResolveNight();
    check(deaths==std::vector<int>{8} && gv_damage[8]==1);
    // Actor immune-to-restriction residual blocker does not erase a real visit.
    reset(); gv_dayNumber=2; gv_egWoundNight[8]=1;
    gv_visitation2[15]=8; gv_roleblocked[15]=1;
    gf_EGPrepareNight(); gf_EGResolveNight(); check(!alive(8));
}
void immunitySnapshots() {
    for(int kind=0;kind<4;++kind) for(bool old: {false,true}) {
        reset(); gv_dayNumber=2; egun(15,8); gv_visitation[1]=8;
        if(old) gv_egWoundNight[8]=1;
        gv_immune[8][0]=kind!=0;
        gv_immuneChance[8]=kind==0 || kind==2?1:kind==3?3:0;
        int before=gv_immuneChance[8];
        gf_EGPrepareNight();
        check(!gv_egWoundNight[8] && gv_immuneChance[8]==before);
        check(countMessage(8,"EGIMMUNET1")==1 && countMessage(15,"EGIMMUNEA1")==1);
        check(countMessage(8,"EGCLEANSE")==int(old));
        check(!gv_e78AAFE7BDAAE4BA8BE5AE9E[15][4]);
        check(messages[0].value.find("<color15>15.P15</color>")!=string::npos);
        check(messages[1].value.find("<color8>8.P8</color>")!=string::npos);
        // Consume or remove BOTH defenses in the ordinary-attack phase.
        gv_immuneChance[8]=0; gv_immune[8][0]=false;
        gf_EGPrepareNight(); // must not recapture/spawn a wound or duplicate reveal
        gf_EGResolveNight(); check(alive(8) && deaths.empty());
        check(countMessage(15,"EGIMMUNEA1")==1);
        checkNoCredit();
    }
    // Protection gained on a later night clears old wounds, no egun present.
    reset(); gv_dayNumber=4; gv_egWoundNight[8]=1; gv_immuneChance[8]=2;
    gf_EGPrepareNight(); normalAttack(8); gf_EGResolveNight();
    check(alive(8) && gv_immuneChance[8]==1 && !gv_egWoundNight[8]);
    // Other immunity bits are NOT injury immunity.
    reset(); egun(1,8); gv_immune[8][1]=gv_immune[8][3]=true;
    gf_EGPrepareNight(); check(gv_egWoundNight[8]==1);
}
void healerPriorityAndNormalDamage() {
    for(int a: {1,8,15}) for(int h: {1,8,15}) if(a!=h) {
        int t=24-a-h;
        for(int pool: {1,3}) for(int slot: {0,1}) for(bool old: {false,true}) {
            reset(); gv_dayNumber=3; egun(a,t); role(h,pool,pool==1?3:10);
            if(old) gv_egWoundNight[t]=1;
            (slot?gv_visitation2[h]:gv_visitation[h])=t;
            gv_healing[t]=1;
            gf_EGPrepareNight();
            check(!gv_egWoundNight[t] && gv_healing[t]==1);
            check(countMessage(h,"EGHEALER")==1 && countMessage(t,"EGPATIENT")==1);
            check(countMessage(a,old?"EGALREADY":"EGHEALBLOCK1")==1);
            check(!countMessage(a,"EGATTACK1") && !countMessage(t,"EGWOUND"));
            check(!gv_e78AAFE7BDAAE4BA8BE5AE9E[a][4]);
            normalAttack(t); // ordinary damage still receives the doctor's heal
            check(attackRescues==1 && gv_healing[t]==0 && alive(t));
            normalKill(h); // same-night doctor death cannot undo their cure
            gf_EGResolveNight(); check(alive(t) && deaths.empty());
            checkNoCredit();
        }
    }
    for(int guard=0;guard<5;++guard) {
        reset(); gv_dayNumber=2; gv_egWoundNight[8]=1; role(15,1,3); gv_visitation[15]=8;
        if(guard==0) gv_roleblocked[15]=1;
        if(guard==1) gv_jailed[15]=1;
        if(guard==2) gv_alivePlayers &= ~(1u<<15);
        if(guard==3) gv_diedAtNight[15]=true;
        if(guard==4) gv_veteraned[15]=true;
        gf_EGPrepareNight(); check(gv_egWoundNight[8]==1 && !countMessage(15,"EGHEALER"));
    }
    // Healing resources alone (non-doctor) are not a wound cure.
    reset(); gv_dayNumber=2; gv_egWoundNight[8]=1; gv_visitation[1]=8; gv_healing[8]=3;
    gf_EGPrepareNight(); gf_EGResolveNight(); check(!alive(8) && gv_healing[8]==3);
    // Two real healers both learn of one cure; patient hears once.
    reset(); gv_dayNumber=2; gv_egWoundNight[8]=1;
    role(1,1,3); role(15,3,10); gv_visitation[1]=gv_visitation2[15]=8;
    gf_EGPrepareNight(); gf_EGResolveNight();
    check(countMessage(1,"EGHEALER")==1 && countMessage(15,"EGHEALER")==1);
    check(countMessage(8,"EGPATIENT")==1 && alive(8));
    // Doctor self-care is still a cure although self-visits are not triggers.
    reset(); gv_dayNumber=2; gv_egWoundNight[8]=1; role(8,1,3); gv_visitation[8]=8;
    gf_EGPrepareNight(); gf_EGResolveNight(); check(!gv_egWoundNight[8] && alive(8));
}
void multiActorsAndDeathPriority() {
    reset(); egun(1,8); egun(15,8);
    gf_EGPrepareNight(); check(gv_egWoundNight[8]==1);
    check(countMessage(1,"EGATTACK1")==1 && countMessage(15,"EGALREADY")==1);
    check(gv_e78AAFE7BDAAE4BA8BE5AE9E[1][4] && !gv_e78AAFE7BDAAE4BA8BE5AE9E[15][4]);
    nextNight(); egun(1,15); egun(8,1); // several players remain wounded at once
    gf_EGPrepareNight(); check(gv_egWoundNight[8]==1 && gv_egWoundNight[15]==2 && gv_egWoundNight[1]==2);
    gf_EGResolveNight(); check(deaths.empty());
    nextNight(); gv_visitation[7]=1; gv_visitation2[7]=8; gv_visitation[9]=15;
    gf_EGPrepareNight(); gf_EGResolveNight(); check(deaths==std::vector<int>({1,8,15}));
    checkNoCredit();
    for(int mode=0;mode<3;++mode) {
        reset(); gv_dayNumber=2; gv_egWoundNight[8]=1; gv_visitation[15]=8;
        gf_EGPrepareNight();
        if(mode==0) normalKill(8);
        if(mode==1) { gv_diedAtNight[8]=true; gv_deathMethod[8]="ordinary"; gv_deathText[8]="ordinary text"; }
        if(mode==2) { gv_alivePlayers &= ~(1u<<8); gv_deathMethod[8]="ordinary"; gv_deathText[8]="ordinary text"; }
        gf_EGResolveNight(); check(deaths.empty() && !gv_egWoundNight[8]);
        check(gv_deathMethod[8]=="ordinary" && gv_deathText[8]=="ordinary text");
    }
    reset(); gv_dayNumber=0; egun(1,8); gf_EGPrepareNight(); gf_EGResolveNight();
    check(!gv_egWoundNight[8] && messages.empty());
    reset(); gv_dayNumber=2; gv_egWoundNight[8]=1; gv_visitation[15]=8;
    gf_EGResolveNight(); check(alive(8)); // missing prepare must not use stale state
    gf_EGPrepareNight(); auto messageCount=messages.size(); gf_EGPrepareNight();
    check(messages.size()==messageCount); gf_EGResolveNight(); gf_EGResolveNight();
    check(deaths==std::vector<int>{8});
    gf_EGReset(); check(!gv_egWoundNight[8] && !gv_egPreparedNight && !gv_egResolvedNight);
}
void randomizedOracle() {
    std::mt19937 rng(0xE628C47A);
    for(int fixture=0;fixture<4000;++fixture) {
        reset(); gv_dayNumber=2 + rng()%12;
        std::array<bool,16> live{}, protectedNow{}, healer{}, visited{}, healed{};
        std::array<int,16> wounds{}, expected{}, castResult{}, oldShield{}, oldHeal{};
        for(int p=1;p<=15;++p) {
            int kind=rng()%7;
            if(kind==0) role(p,3,28);
            if(kind==1) role(p,1,3);
            if(kind==2) role(p,3,10);
            if(kind==3) role(p,1,11);
            if(kind==4) role(p,1,28); // must not be mistaken for egun
            if(rng()%12==0) gv_alivePlayers &= ~(1u<<p);
            gv_diedAtNight[p]=rng()%17==0;
            gv_roleblocked[p]=rng()%8==0?1:0;
            gv_jailed[p]=rng()%11==0?1:0;
            gv_veteraned[p]=rng()%19==0;
            gv_immune[p][0]=rng()%9==0;
            gv_immuneChance[p]=rng()%8==0?1+rng()%3:0;
            gv_healing[p]=rng()%4;
            gv_visitation[p]=int(rng()%18)-1;
            gv_visitation2[p]=int(rng()%18)-1;
            gv_egWoundNight[p]=rng()%3==0?int(1+rng()%(gv_dayNumber-1)):0;
            live[p]=alive(p) && !gv_diedAtNight[p];
            protectedNow[p]=gv_immune[p][0] || gv_immuneChance[p]>0;
            healer[p]=live[p] && !gv_roleblocked[p] && !gv_jailed[p] && !gv_veteraned[p]
                && ((gv_roles[p][1]==1 && gv_roles[p][0]==3) || (gv_roles[p][1]==3 && gv_roles[p][0]==10));
            wounds[p]=live[p]?gv_egWoundNight[p]:0;
            oldShield[p]=gv_immuneChance[p]; oldHeal[p]=gv_healing[p];
        }
        // Independent per-target set comprehension: compute incoming visitors
        // and healers before applying the seat-ordered accepted wound claims.
        for(int t=1;t<=15;++t) if(live[t]) {
            for(int v=1;v<=15;++v) if(live[v] && (gv_visitation[v]==t || gv_visitation2[v]==t)) {
                if(v!=t && !(gv_roles[v][1]==3 && gv_roles[v][0]==28)) visited[t]=true;
                if(healer[v]) healed[t]=true;
            }
        }
        expected=wounds;
        for(int a=1;a<=15;++a) {
            int t=gv_visitation[a];
            if(!(gv_roles[a][1]==3 && gv_roles[a][0]==28) || !live[a] || gv_roleblocked[a] || gv_jailed[a] || gv_veteraned[a]) continue;
            if(t<1 || t>15 || t==a || !live[t]) continue;
            if(protectedNow[t]) castResult[a]=1;
            else if(expected[t]) castResult[a]=2;
            else if(healed[t]) castResult[a]=3;
            else { castResult[a]=4; expected[t]=gv_dayNumber; }
        }
        for(int t=1;t<=15;++t) if(protectedNow[t] || healed[t]) expected[t]=0;
        gf_EGPrepareNight();
        for(int p=1;p<=15;++p) {
            check(gv_egWoundNight[p]==expected[p]);
            check(gv_immuneChance[p]==oldShield[p] && gv_healing[p]==oldHeal[p]);
            check(gv_e78AAFE7BDAAE4BA8BE5AE9E[p][4]==(castResult[p]==4));
            if(castResult[p]==1) check(countMessage(p,"EGIMMUNEA1")==1);
            if(castResult[p]==2) check(countMessage(p,"EGALREADY")==1);
            if(castResult[p]==3) check(countMessage(p,"EGHEALBLOCK1")==1);
            if(castResult[p]==4) check(countMessage(p,"EGATTACK1")==1);
        }
        // Arbitrary ordinary kills and consumption happen AFTER the snapshot.
        std::vector<int> expectedDeaths;
        for(int p=1;p<=15;++p) {
            gv_immuneChance[p]=0; gv_immune[p][0]=false; gv_healing[p]=0;
            if(live[p] && rng()%5==0) normalKill(p);
            if(alive(p) && !gv_diedAtNight[p] && expected[p]>0 && expected[p]<gv_dayNumber && visited[p]) expectedDeaths.push_back(p);
            gv_visitation[p]=gv_visitation2[p]=0;
        }
        gf_EGResolveNight(); check(deaths==expectedDeaths);
        gf_EGResolveNight(); check(deaths==expectedDeaths);
        checkNoCredit();
    }
}
int main() {
    firstAndNextNight(); boundariesAndGuards(); visitRulesAndBodyguard();
    immunitySnapshots(); healerPriorityAndNormalDamage();
    multiActorsAndDeathPriority(); randomizedOracle();
    std::cout << "PASS: actual Galaxy core; UBSan/bounds; 1/8/15 seats; both visits; multi-egun; N1/N2; redirects; doctors/witch doctors; healing/shield preservation; ordinary death priority; no murder/killer/guard credit" << std::endl;
    std::cout << "PASS: 4000 seeded independent-oracle fixtures; " << checks << " assertions" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--core', type=Path, default=CORE)
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    source, core = args.script.read_text(), args.core.read_text()
    print(f'Actual core: {args.core}; engine/rendering and presentation require separate verification', flush=True)
    code = harness(source, core)
    with tempfile.TemporaryDirectory(prefix='bh-egun-tests-') as tmp:
        cpp, exe = Path(tmp) / 'egun.cpp', Path(tmp) / 'egun'
        cpp.write_text(code)
        # Galaxy's generated ((comparison)) spelling is intentional; Clang's
        # stylistic warning is not a logic defect and must not rewrite the body.
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra',
                        '-Werror', *warnings, '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
