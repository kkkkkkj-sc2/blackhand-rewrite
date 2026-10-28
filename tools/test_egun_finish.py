#!/usr/bin/env python3
"""Sanitized actual-body 恶棍 death/win tests and complete CheckEnd baseline audit.

Reads current source only. Compiles the complete gf_EGWoundDeath, gf_EGWon,
gf_CheckEnd and baseline gf_CheckEnd (git e9e1c36 by default), not rewritten
versions. Only Galaxy array syntax and Galaxy's implicit local zero initialization
are translated. SC2 presentation calls are instrumented engine doubles. Award
qualification executes all 25 current expressions and pinned pre-CJ 03e6eef
expressions, preserving GK proxy guards and identity-independent CJ shared wins.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from test_egun import ROOT, SCRIPT, function, mask, translate
from test_faction_conversion import with_guoke_dependencies

# Immutable pre-CJ shipping award expressions, already containing GK guards.
AWARD_BASELINE = '03e6eef'


def end_block(source: str, start: int) -> int:
    live = mask(source)
    assert live[start] == '{'
    depth, end = 1, start + 1
    while depth:
        depth += (live[end] == '{') - (live[end] == '}')
        end += 1

    return end


def integration(source: str) -> list[str]:
    wrappers = []
    names = re.findall(r'^void (gf_ET\w+)\s*\([^;\n]*\)\s*\{', source, re.M)
    for name in names:
        body = function(source, name)
        if not re.search(r'\bgv_won\[lv_a\]\s*=\s*true;', mask(body)):
            continue

        matches = list(re.finditer(r'\bif\s*(\([^\n{]+gf_EGWon\([^\n{]+)\s*\{', body))
        assert len(matches) == 1, (name, 'missing/duplicate EG winner branch')
        match = matches[0]
        brace = body.index('{', match.start())
        close = end_block(body, brace)
        winning = body[brace:close]
        assert 'gv_won[lv_a] = true;' in winning, (name, 'EG branch does not award win')
        assert not re.search(r'gv_bankGeneralIntegers\[lv_a\]\[7\]\s*\+=', winning), (name, 'EG included in loss branch')
        # GK qualification already wrapped EG before CJ was added. Positional
        # "starts with EG ||" is obsolete, not a production regression. Below,
        # testAwardQualification executes every actual expression against the
        # pinned pre-CJ expression AND explicit independent GK/CJ/EG fixtures.
        assert len(re.findall(r'\bgf_EGWon\(lv_a\)\s*==\s*true', match[1])) == 1, \
            (name, 'missing/duplicate actual EG qualification; execution checks follow')
        tail = body[close:]
        assert re.match(r'\s*else\s*\{', tail), (name, 'winner must have its original else')
        else_start = close + tail.index('{')
        losing = body[else_start:end_block(body, else_start)]
        assert 'gf_EGWon' not in losing and not re.search(r'gv_won\[lv_a\]\s*=\s*true;', losing)
        assert 'gv_bankGeneralIntegers[lv_a][7] += 1;' in losing, (name, 'loss accounting must remain outside EG win')
        wrappers.append(f'bool award_{name}(int lv_a) {{ int lv_ci=0; int lv_shw=0; int lv_tx=0; return {match[1]}; }}')

    assert len(wrappers) == 25, ('ET winner coverage changed', len(wrappers))
    kills = function(source, 'gf_SequenceKills')
    assert kills.count('gf_EGPrepareNight();') == kills.count('gf_EGResolveNight();') == 1
    assert kills.index('gf_TTApplyProtect();') < kills.index('gf_EGPrepareNight();') < kills.index('gf_ESCultSinisterSmite(')
    assert kills.index('gf_EGResolveNight();') < kills.index('gv_bondedwith[lv_a]')
    assert kills.index('gf_ESLightning(') < kills.index('gf_EGResolveNight();')
    end = function(source, 'auto_gf_EndGame_TriggerFunc')
    assert re.search(r'if\s*\(\(lp_end == 28\)\)\s*\{\s*gf_ETEgunWin\(\);\s*\}', end)
    coroner = function(source, 'gf_SKF_1_fayi')
    assert re.search(r'if\s*\(\(StringSub\([^\n]+== "g"\)\)\s*\{\s*gf_CBSystemMessage\(StringExternal\("Param/Value/EGCORONER"\)', coroner)
    assert 'WinEgun.dds' in function(source, 'gf_ETEgunWin')
    dq = function(source, 'gf_DQShareWin')
    dq_ifs = list(re.finditer(r'\bif\s*(\([^\n{]+)\s*\{', dq))
    outer, gate = dq_ifs[:2]
    assert 'gv_dqRevealed' in outer[1] and '(lp_end == 28)' in gate[1]
    gate_brace = dq.index('{', gate.start())
    assert 'gv_won[lv_a] = true;' in dq[gate_brace:end_block(dq, gate_brace)]
    wrappers.append(f'bool dqShareGate(int lv_a, int lp_end) {{ return ({outer[1]} && {gate[1]}); }}')
    assert 'gf_DQShareWin(lp_end);' in end
    print('PASS: all 25 actual ET qualification branches, true/else accounting, EndGame28, DQ neutral share28, coroner g, Prepare/Resolve ordering', flush=True)
    return wrappers


def harness(source: str, baseline: str, award_baseline: str) -> str:
    wrappers = integration(source)
    award_names = re.findall(r'^bool award_(\w+)', '\n'.join(wrappers), re.M)
    old_wrappers, winner_codes = [], []
    for name in award_names:
        old_body = function(award_baseline, name)
        matches = list(re.finditer(r'\bif\s*(\([^\n{]+gf_EGWon\([^\n{]+)\s*\{', old_body))
        assert len(matches) == 1, (name, 'missing/ambiguous pinned pre-CJ qualification')
        expression = matches[0][1]
        old_wrappers.append(f'bool prior_award_{name}(int lv_a) {{ int lv_ci=0; int lv_shw=0; int lv_tx=0; return {expression}; }}')
        codes = re.findall(r'\bgf_GKWon\(lv_a,\s*(\d+)\)', expression)
        assert len(codes) == 1 and int(codes[0]) in (0, 1, 2, 5), (name, 'pinned GK winner mapping', codes)
        winner_codes.append(codes[0])

    names = ('gf_BHConverted', 'gf_BHFaction',
             'gf_LMCat', 'gf_LMRole', 'gf_JSIs', 'gf_JSWon', 'gf_EGWon',
             'gf_EGWoundDeath', 'gf_CheckEnd')
    award_calls = set(re.findall(r'\b(gf_GK\w+|gf_CJ\w+|gf_BHNoVoteOrCount|gf_BHVisit\w*)\s*\(',
                                mask('\n'.join(wrappers + old_wrappers))))
    names = with_guoke_dependencies(source, (*names, *sorted(award_calls)))
    bodies = [function(source, name) for name in names]
    old = function(baseline, 'gf_CheckEnd')
    bodies.append(old.replace('gf_CheckEnd', 'baseline_CheckEnd'))
    code = '\n\n'.join(bodies + wrappers + old_wrappers)
    death = mask(function(source, 'gf_EGWoundDeath'))
    for forbidden in ('gv_healing', 'gv_immune', 'gv_immuneChance', 'gv_guarded',
                      'gf_BHCrime', 'gf_BHCrimeMurder', 'gf_BHRecordNightKiller',
                      'gf_ESBodyguardKill'):
        assert not re.search(r'\b' + forbidden + r'\b', death), ('death helper must not access', forbidden)

    used = set(re.findall(r'\bgv_\w+', mask(code))) | {
        'gv_healing', 'gv_immune', 'gv_immuneChance', 'gv_guarded',
        'gv_e78AAFE7BDAAE4BA8BE5AE9E',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not used - declarations.keys(), ('missing globals', used - declarations.keys())
    globals_text = '\n'.join(declarations[n] for n in sorted(used))
    resets = '\n'.join(f'    clearValue({n});' for n in sorted(used))
    headers = '\n'.join(b.split('{', 1)[0].strip() + ';' for b in bodies)
    code = translate(code)
    # Galaxy scalar and array locals start at zero; C++ otherwise leaves these
    # uninitialized. No executable Galaxy statements are changed.
    code = re.sub(r'^(\s+(?:int|bool)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', code, flags=re.M)
    calls = set(re.findall(r'\b(\w+)\s*\(', mask(code)))
    defined = set(re.findall(r'^(?:void|int|bool)\s+(\w+)\s*\(', code, re.M))
    known = {'if','for','while','return','PlayerGroupHasPlayer','PlayerGroupCount',
             'PlayerGroupSingle','PlayerGroupAll','SoundLink','Color','StringExternal',
             'gf_KillPlayer','gf_FlashScreen','gf_BHNotify','gf_CBSystemMessage',
             'SoundPlay','Wait','gf_XRGangShare'}
    assert not calls-defined-known, ('unknown calls', calls-defined-known)
    predicate_names = re.findall(r'^bool (award_\w+)', '\n'.join(wrappers), re.M)
    predicate_array = ','.join(predicate_names)
    prior_predicate_array = ','.join('prior_' + name for name in predicate_names)
    winner_code_array = ','.join(winner_codes)
    return r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <climits>
#include <iostream>
#include <random>
#include <string>
#include <vector>
using std::string;
using text=string;
using soundlink=string;
using playergroup=unsigned int;
constexpr int c_timeGame=0;
''' + globals_text + r'''
std::vector<string> events;
std::vector<double> waits;
std::vector<int> broadcasts;
std::vector<string> sounds;
int kills,notifies,flashes,checks;
double clockTime;
template<class T> void clearValue(T& x) { x=T{}; }
template<class T,size_t N> void clearValue(T (&x)[N]) { for(auto& i:x) clearValue(i); }
void checkAt(bool value,int line,const char* expression) {
    ++checks;
    if(!value) std::cerr<<"FAIL generated line "<<line<<": "<<expression<<std::endl;
    assert(value);
}
#define check(value) checkAt((value),__LINE__,#value)
bool PlayerGroupHasPlayer(playergroup group,int p) {
    assert(p>=1 && p<=15); return (group & (1u<<p))!=0;
}
int PlayerGroupCount(playergroup group) { return __builtin_popcount(group); }
playergroup PlayerGroupAll() { return 0xfffe; }
playergroup PlayerGroupSingle(int p) { assert(p>=1 && p<=15); return 1u<<p; }
int Color(double,double,double) { return 0; }
soundlink SoundLink(string name,int index) { assert(index==-1); return name; }
text StringExternal(string key) { return "{"+key+"}"; }
void gf_KillPlayer(int p,bool dissolve) {
    assert(p>=1 && p<=15 && !dissolve);
    assert(gv_diedAtNight[p]); ++kills;
    gv_alivePlayers &= ~(1u<<p); events.push_back("kill");
}
void gf_FlashScreen(int,int p,double length,double period) {
    assert(p>=1 && p<=15 && length==5.0 && period==0.0);
    ++flashes; events.push_back("flash");
}
void gf_BHNotify(text message,int p,soundlink sound) {
    assert(p>=1 && p<=15 && message=="{Param/Value/EGDIED}" && sound=="UI_TipSelect");
    ++notifies; events.push_back("notify");
}
void gf_CBSystemMessage(text message,int target,int sender,int whisper,soundlink sound,int) {
    assert(message=="{Param/Value/EGNIGHT}" && target>=1 && target<=15);
    assert(sender==16 && whisper==0 && sound=="Silent" && clockTime==0.0);
    broadcasts.push_back(target); events.push_back("broadcast");
}
void Wait(double duration,int type) {
    assert(type==c_timeGame); clockTime+=duration; waits.push_back(duration);
    events.push_back(duration==1.0?"wait1":"wait0.5");
}
void SoundPlay(soundlink sound,playergroup group,double volume,double offset) {
    assert(group==PlayerGroupAll() && volume==100.0 && offset==0.0);
    assert(clockTime==1.0 && broadcasts.size()==15 && waits==std::vector<double>{1.0});
    sounds.push_back(sound); events.push_back("sound");
}
bool gf_XRGangShare(int,int) { return false; } // unrelated ET shared-win predicate
''' + headers + '\n' + code + r'''
void reset() {
''' + resets + r'''
    kills=notifies=flashes=0; clockTime=0.0;
    events.clear(); sounds.clear(); waits.clear(); broadcasts.clear();
}
void add(int p,int pool,int id) { gv_roles[p][1]=pool; gv_roles[p][0]=id; gv_alivePlayers|=1u<<p; }
void testDeath() {
    for(int p:{1,8,15}) for(bool male:{false,true}) for(bool night:{false,true}) for(bool desc:{false,true}) {
        reset(); add(p,1,1); gv_isAMan[p]=male;
        gv_nightSequence=night; gv_deathDescriptions=desc;
        gv_healing[p]=3; gv_immuneChance[p]=2; gv_immune[p][0]=true; gv_guarded[p]=p==1?15:1;
        gv_deathMethod[p]="old"; gv_deathText[p]="prior";
        gf_EGWoundDeath(p);
        check(kills==1 && notifies==1 && flashes==1 && gv_damage[p]==1);
        check(gv_diedAtNight[p] && !(gv_alivePlayers&(1u<<p)) && gv_seqKillsZ[1]);
        check(gv_deathMethod[p]=="oldg");
        check(gv_deathText[p]==(night||desc?"prior{Param/Value/EGDEATH}":"prior"));
        check(gv_deathDesc[p]==(night||desc));
        check(gv_healing[p]==3 && gv_immuneChance[p]==2 && gv_immune[p][0] && gv_guarded[p]==(p==1?15:1));
        check(std::all_of(&gv_e78AAFE7BDAAE4BA8BE5AE9E[p][0],&gv_e78AAFE7BDAAE4BA8BE5AE9E[p][0]+11,[](bool v){return !v;}));
        if(night) {
            check(broadcasts.size()==15 && sounds==std::vector<string>{male?"CivilianDeath":"CivilianFemaleDeath"});
            for(int i=0;i<15;++i) check(broadcasts[i]==i+1);
            check(waits==std::vector<double>({1.0,0.5}) && clockTime==1.5);
            check(events[3]=="broadcast" && events[17]=="broadcast" && events[18]=="wait1" && events[19]=="sound" && events[20]=="wait0.5");
        } else check(broadcasts.empty() && sounds.empty() && waits.empty());
        auto before=events; gf_EGWoundDeath(p);
        check(events==before && gv_damage[p]==1 && gv_deathMethod[p]=="oldg");
    }
    for(int invalid:{INT_MIN,-1,0,16,INT_MAX}) {
        reset(); gf_EGWoundDeath(invalid); check(events.empty());
    }
    for(int p:{1,8,15}) for(int deadMode:{0,1,2}) {
        reset(); add(p,1,1);
        if(deadMode!=0) gv_alivePlayers=0;
        if(deadMode!=1) gv_diedAtNight[p]=true;
        gv_deathMethod[p]="ordinary"; gv_deathText[p]="ordinary text";
        gf_EGWoundDeath(p);
        check(events.empty() && !gv_damage[p] && gv_deathMethod[p]=="ordinary" && gv_deathText[p]=="ordinary text");
    }
}
void testWonAndEnd() {
    bool (*predicates[])(int)={''' + predicate_array + r'''};
    for(int p:{1,8,15}) {
        reset(); add(p,3,28); check(gf_EGWon(p)); check(gf_CheckEnd()==28);
        for(auto predicate:predicates) check(predicate(p));
        add(p==1?15:1,1,3); check(!gf_EGWon(p)); check(gf_CheckEnd()==1);
        for(auto predicate:predicates) check(!predicate(p));
        gv_alivePlayers&=~(1u<<p); check(!gf_EGWon(p));
        for(auto predicate:predicates) check(!predicate(p));
    }
    for(int invalid:{INT_MIN,-1,0,16,INT_MAX}) check(!gf_EGWon(invalid));
    reset(); add(1,3,28); add(8,3,28); add(15,3,2);
    check(gf_CheckEnd()==28 && gf_EGWon(1) && gf_EGWon(8) && !gf_EGWon(15));
    gv_alivePlayers&=~(1u<<8); check(!gf_EGWon(8) && gf_EGWon(1));
    // Harmless neutral companions do not erase the strict Town0 victory.
    for(int harmless:{2,3,6,7,16,17,23,24,25}) {
        reset(); add(1,3,28); add(15,3,harmless); check(gf_CheckEnd()==28);
    }
    for(auto faction: {std::pair<int,int>{2,1},{5,1},{3,1},{3,5},{3,9},{3,14},{3,20},{3,22},{3,26},{3,27},{3,13},{3,31},{3,32}}) {
        reset(); add(1,faction.first,faction.second);
        int winner=gf_CheckEnd(); check(winner!=28);
        add(8,3,28); check(gf_CheckEnd()==winner && gf_EGWon(8));
    }
    for(int towns=2;towns<=7;++towns) {
        reset(); add(15,3,28);
        for(int p=1;p<=towns;++p) add(p,1,3);
        check(gf_CheckEnd()==0 && !gf_EGWon(15));
        gv_tieTicker=7; // ordinary majority chain may resolve later, not prematurely
        check(gf_CheckEnd()==1 && !gf_EGWon(15));
    }
    // Per-user one-town/only-egun anti-deadlock exception is Town victory.
    for(int count=1;count<=6;++count) {
        reset(); add(15,1,3); for(int p=1;p<=count;++p) add(p,3,28);
        check(gf_CheckEnd()==1); for(int p=1;p<=count;++p) check(!gf_EGWon(p));
    }
    // Execute the actual Tangjihede outer guard + full faction-share gate.
    for(int p:{1,8,15}) for(bool reveal:{false,true}) for(int alignment=0;alignment<=3;++alignment) {
        reset(); add(p,3,21); gv_dqRevealed[p]=reveal; gv_dqAlign[p]=alignment;
        check(dqShareGate(p,28)==(reveal && alignment==3));
        check(dqShareGate(p,1)==(reveal && alignment==1));
        check(dqShareGate(p,2)==(reveal && alignment==2));
        check(dqShareGate(p,13)==(reveal && alignment==2));
        gv_roles[p][0]=28; check(!dqShareGate(p,28));
    }
    // Real LM getters are included, not constant role stubs.
    reset(); add(1,1,1); gv_lmWin[1][1]=3; gv_lmWin[1][0]=28;
    check(gf_EGWon(1));
}
void testAwardQualification() {
    bool (*current[])(int)={''' + predicate_array + r'''};
    bool (*prior[])(int)={''' + prior_predicate_array + r'''};
    const int winnerCodes[]={''' + winner_code_array + r'''};
    static_assert(sizeof(current)==sizeof(prior));
    static_assert(sizeof(current)/sizeof(current[0])==25);
    for(int p:{1,8,15}) {
        // Actual EG alone is sufficient only after its real Town0 objective.
        reset(); add(p,3,28); check(gf_EGWon(p) && !gf_GKIs(p));
        for(auto predicate:current) check(predicate(p));
        add(p==1?15:1,1,1); check(!gf_EGWon(p));
        for(auto predicate:current) check(!predicate(p));

        for(int faction:{0,1,2,3,5}) for(bool alive:{false,true}) {
            reset(); add(p,3,28); gv_gkRole[p]=33; gv_gkFaction[p]=faction;
            gv_lmWin[p][1]=3; gv_lmWin[p][0]=28; // retain stale EG snapshot
            if(!alive) gv_alivePlayers&=~(1u<<p);
            check(gf_GKIs(p));
            // Actual LMRole already suppresses a GK's stale EG profession.
            check(!gf_EGWon(p));
            for(int i=0;i<25;++i) {
                const bool factionBound=faction==1 || faction==2 || faction==5;
                const bool expected=factionBound?faction==winnerCodes[i]:alive;
                check(current[i](p)==expected);
                check(current[i](p)==prior[i](p));
            }
            // CJ's irrevocable personal win remains independent of identity,
            // alive status and the GK proxy's winning/losing faction.
            gv_cjWon[p]=true;
            for(auto predicate:current) check(predicate(p));
        }
    }

    // Preserve EVERY old qualification term against 25 independently pinned
    // actual shipping expressions, not just selected EG success fixtures.
    std::mt19937 rng(0xC0A628F1);
    const std::pair<int,int> roles[]={{1,1},{2,1},{5,1},{3,1},{3,2},{3,3},{3,4},{3,5},{3,6},{3,7},{3,8},{3,9},{3,10},{3,11},{3,12},{3,13},{3,14},{3,15},{3,16},{3,17},{3,19},{3,20},{3,21},{3,22},{3,23},{3,24},{3,25},{3,26},{3,27},{3,28},{3,30},{3,31},{3,32},{3,33},{3,34},{3,35},{3,36},{3,37},{3,38}};
    const int factions[]={0,1,2,3,5};
    for(int fixture=0;fixture<2000;++fixture) {
        reset();
        for(int p=1;p<=15;++p) {
            auto r=roles[rng()%(sizeof(roles)/sizeof(roles[0]))];
            gv_roles[p][1]=r.first; gv_roles[p][0]=r.second;
            if(rng()%2) gv_alivePlayers|=1u<<p;
            if(rng()%6==0) gv_gkRole[p]=33+rng()%5;
            gv_gkFaction[p]=factions[rng()%5];
            if(rng()%5==0) { r=roles[rng()%(sizeof(roles)/sizeof(roles[0]))]; gv_lmWin[p][1]=r.first; gv_lmWin[p][0]=r.second; }
            gv_executed[p]=rng()%2; gv_executionWin[p]=rng()%2;
            gv_e8B58CE9ACBCE782B9E695B0[p]=rng()%5; gv_jsKills[p]=rng()%4;
            gv_ttWon[p]=rng()%2; gv_grChild[p]=rng()%16;
        }
        gv_roleOptions[3][6][2]=rng()%2;
        for(int p=1;p<=15;++p) {
            for(int i=0;i<25;++i) check(current[i](p)==prior[i](p));
            gv_cjWon[p]=true;
            for(auto predicate:current) check(predicate(p));
            gv_cjWon[p]=false;
        }
    }
}
void baselineComparison() {
    std::mt19937 rng(0xE628F1);
    const std::pair<int,int> roles[]={{1,1},{1,3},{1,12},{2,1},{2,2},{5,1},{5,2},{3,1},{3,2},{3,3},{3,4},{3,5},{3,6},{3,7},{3,8},{3,9},{3,10},{3,11},{3,12},{3,13},{3,14},{3,15},{3,16},{3,17},{3,19},{3,20},{3,22},{3,23},{3,24},{3,25},{3,26},{3,27},{3,31},{3,32}};
    for(int fixture=0;fixture<5000;++fixture) {
        reset();
        for(int p=1;p<=15;++p) {
            auto role=roles[rng()%(sizeof(roles)/sizeof(roles[0]))];
            gv_roles[p][1]=role.first; gv_roles[p][0]=role.second;
            if(rng()%3) gv_alivePlayers|=1u<<p;
            if(rng()%8==0) { auto r=roles[rng()%(sizeof(roles)/sizeof(roles[0]))]; gv_lmWin[p][1]=r.first; gv_lmWin[p][0]=r.second; }
            gv_executed[p]=rng()%7==0; gv_executionWin[p]=rng()%5==0;
            gv_e8B58CE9ACBCE782B9E695B0[p]=rng()%5; gv_jsKills[p]=rng()%4;
        }
        gv_tieTicker=rng()%10; gv_dayOver=rng()%2;
        gv_roleOptions[1][1][1]=rng()%2; gv_roleOptions[3][1][2]=rng()%2; gv_roleOptions[3][6][2]=rng()%2;
        auto original=std::array<int,5>{}; for(int i=0;i<5;++i) gv_specialCaseFlag[i]=original[i]=rng()%3;
        int old=baseline_CheckEnd(); auto oldFlags=std::array<int,5>{};
        for(int i=0;i<5;++i) { oldFlags[i]=gv_specialCaseFlag[i]; gv_specialCaseFlag[i]=original[i]; }
        int current=gf_CheckEnd(); check(current==old);
        for(int i=0;i<5;++i) check(gv_specialCaseFlag[i]==oldFlags[i]);
    }
}
int main() {
    testDeath(); testWonAndEnd(); testAwardQualification(); baselineComparison();
    std::cout<<"PASS: full actual death/Won/CheckEnd; sex-specific sound ordering; bounds/idempotence; strictTown0; 25 ET winner predicates; original faction priority"<<std::endl;
    std::cout<<"PASS: 25 actual award expressions vs pinned pre-CJ 03e6eef over 2000 seeded populations; explicit incomplete EG/GK proxy/CJ identity-independent wins"<<std::endl;
    std::cout<<"PASS: 5000 no-egun baseline comparisons (return + side effects); "<<checks<<" assertions; UBSan/bounds"<<std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--baseline', default='e9e1c36')
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    source = args.script.read_text()
    baseline = subprocess.run(['git', 'show', f'{args.baseline}:work/blackhand/CustomLogic.galaxy'], cwd=ROOT,
                              text=True, capture_output=True, check=True).stdout
    award_baseline = subprocess.run(['git', 'show', f'{AWARD_BASELINE}:work/blackhand/CustomLogic.galaxy'], cwd=ROOT,
                                    text=True, capture_output=True, check=True).stdout
    code = harness(source, baseline, award_baseline)
    with tempfile.TemporaryDirectory(prefix='bh-egun-finish-') as tmp:
        cpp, exe = Path(tmp)/'finish.cpp', Path(tmp)/'finish'
        cpp.write_text(code)
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', *warnings, '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
