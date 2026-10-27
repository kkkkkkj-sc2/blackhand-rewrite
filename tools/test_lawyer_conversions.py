#!/usr/bin/env python3
"""Execute actual lawyer/gang conversion Galaxy bodies under C++17 UBSan/bounds.

Compiles the complete gf_RSConversions dispatcher, every gf_SKV_* it calls,
plus gf_LSConvert/gf_LSIs. Only engine/UI boundaries are stubbed; missing or new
logic dependencies fail closed. This is not an SC2 compiler/rendering test.
Historical unrelated conversion bugs (e.g. triad wuxian's pool indices) are not
rewritten or treated as this change's regression fixtures.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from test_trap_roles import function

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
BOUNDARIES = {
    'StringExternal', 'SoundLink', 'Color', 'PlayerGroupHasPlayer',
    'PlayerGroupCount', 'gf_CBSystemMessage', 'gf_RTRoleCard', 'gf_RefreshRoleBox',
}


def calls_in(code: str) -> set[str]:
    stripped = re.sub(r'//[^\n]*|"(?:\\.|[^"\\])*"', '', code)
    return set(re.findall(r'\b(\w+)\s*\(', stripped)) - {
        'if', 'else', 'for', 'while', 'return',
    }


def harness(source: str) -> str:
    names = ['gf_RSConversions', 'gf_LSConvert', 'gf_LSIs',
             'gf_BHConvertedSuccession', 'gf_BHConverted', 'gf_BHFaction',
             'gf_GKIs', 'gf_GKSetRoleField']
    bodies = []
    for name in names:
        body = function(source, name)
        bodies.append(body)
        for dependency in sorted(calls_in(body)):
            if dependency.startswith('gf_SKV_') and dependency not in names:
                names.append(dependency)

    # Full dispatch/count/convert implementations, never generated count stubs.
    code = '\n\n'.join(bodies)
    unknown = calls_in(code) - set(names) - BOUNDARIES
    assert not unknown, ('new dependency needs actual body or explicit boundary', unknown)
    dispatcher = bodies[0]
    hooks = list(re.finditer(r'\bgf_LSConvert\(lv_a\);', dispatcher))
    assert len(hooks) == 2, ('expected one hook in each gang pool', len(hooks))
    for fallback in ('gf_SKV_2_qizi(', 'gf_SKV_5_sishi('):
        assert all(hook.start() < dispatcher.index(fallback) for hook in hooks), fallback

    code = re.sub(r'\b(int|bool|text|string)((?:\[\d+\])+)( +)(\w+)', r'\1\3\4\2', code)
    used = set(re.findall(r'\bgv_\w+', code)) | {
        'gv_roles', 'gv_alivePlayers', 'gv_players', 'gv_rsConvX', 'gv_roleOptions',
        'gv_roleNameArray', 'gv_specialCasePlayer', 'gv_visitation', 'gv_visitation2',
        'gv_lsUsed', 'gv_lsTarget', 'gv_lsDay',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not used - declarations.keys(), ('missing actual globals', used - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(used))
    resets = '\n'.join(f'    clearValue({name});' for name in sorted(used))
    headers = '\n'.join(body.split('{', 1)[0] + ';' for body in bodies)
    skv_count = sum(name.startswith('gf_SKV_') for name in names)
    print(f'Extracted full dispatcher, LSConvert/LSIs, faction succession/identity and GK guards, {skv_count} actual SKV functions, '
          f'{len(used)} actual global declarations; no conversion/count stubs', flush=True)

    return r'''
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <iterator>
#include <map>
#include <string>
#include <tuple>
#include <vector>
using std::string;
using text = string;
using playergroup = int;
using fixed = double;
string caseName;
int fixtures=0;
#define CHECK(...) do { if(!(__VA_ARGS__)) { std::cerr << "FAIL [" << caseName << "] line " << __LINE__ << ": " << #__VA_ARGS__ << std::endl; std::abort(); } } while(0)
std::map<string,int> calls;
std::vector<int> cards;
std::vector<std::pair<string,int>> messages;
std::vector<int> visitsBefore, visits2Before, targetsBefore, daysBefore;
std::vector<bool> usedBefore;
string StringExternal(string value) { return value; }
int SoundLink(string, int) { return 0; }
int Color(double, double, double) { return 0; }
bool PlayerGroupHasPlayer(int group, int p) {
    CHECK(p>=1 && p<=15);
    return (group & (1<<p))!=0;
}
int PlayerGroupCount(int group) {
    int count=0;
    for(int p=1;p<=15;++p) count+=PlayerGroupHasPlayer(group,p);
    return count;
}
template<class T> void clearValue(T &value) { value=T{}; }
template<class T, size_t N> void clearValue(T (&value)[N]) {
    for(auto &element:value) clearValue(element);
}
''' + globals_text + r'''
void gf_RTRoleCard(int p) {
    CHECK(p>=1 && p<=15);
    CHECK(gv_roleOptions[gv_roles[p][1]][gv_roles[p][0]][10]);
    ++calls["card"]; cards.push_back(p);
}
void gf_RefreshRoleBox() { ++calls["refresh"]; }
void gf_CBSystemMessage(string value, int to, int from, int mode, int, int) {
    CHECK(to>=1 && to<=15 && from==to && mode==0);
    messages.emplace_back(value,to);
}
''' + headers + '\n' + code + r'''
int offset(int pool) { return pool==2?0:10; }
int other(int pool) { return pool==2?5:2; }
void role(int p, int pool, int number) { gv_roles[p][1]=pool; gv_roles[p][0]=number; }
void reset(string label) {
''' + resets + r'''
    caseName=label; ++fixtures;
    calls.clear(); cards.clear(); messages.clear();
    gv_alivePlayers=65534; gv_players=65534;
    for(int p=1;p<=15;++p) {
        role(p,1,1);
        gv_visitation[p]=16-p; gv_visitation2[p]=p;
        gv_lsUsed[p]=(p%2==1); gv_lsTarget[p]=16-p; gv_lsDay[p]=p+1;
        gv_specialCasePlayer[p][17]=100+p;
    }
    for(int pool: {2,5}) {
        gv_roleNameArray[pool][1]="KILLER_POOL_"+std::to_string(pool);
        gv_roleNameArray[pool][2]="LEADER_POOL_"+std::to_string(pool);
    }
    visitsBefore.assign(std::begin(gv_visitation),std::end(gv_visitation));
    visits2Before.assign(std::begin(gv_visitation2),std::end(gv_visitation2));
    usedBefore.assign(std::begin(gv_lsUsed),std::end(gv_lsUsed));
    targetsBefore.assign(std::begin(gv_lsTarget),std::end(gv_lsTarget));
    daysBefore.assign(std::begin(gv_lsDay),std::end(gv_lsDay));
}
void invariants() {
    // Converting must not rewrite either visit slot or refill spent LS charges.
    for(int p=1;p<=15;++p) {
        CHECK(gv_visitation[p]==visitsBefore[p] && gv_visitation2[p]==visits2Before[p]);
        CHECK(gv_lsUsed[p]==usedBefore[p]);
        CHECK(gv_lsTarget[p]==targetsBefore[p] && gv_lsDay[p]==daysBefore[p]);
    }
}
void run() { gf_RSConversions(); invariants(); }
void unchangedLawyer(int p, int pool) {
    CHECK(gv_roles[p][0]==21 && gv_roles[p][1]==pool);
    CHECK(gv_specialCasePlayer[p][17]==100+p);
    CHECK(std::count(cards.begin(),cards.end(),p)==0);
}
void noChanges() {
    CHECK(cards.empty() && messages.empty() && calls["refresh"]==0);
    for(int p=1;p<=15;++p) CHECK(gv_specialCasePlayer[p][17]==100+p);
}
void converted(int p, int pool, bool alone) {
    CHECK(gv_roles[p][0]==1 && gv_roles[p][1]==pool);
    CHECK(gv_specialCasePlayer[p][17]==101+p);
    CHECK(std::count(cards.begin(),cards.end(),p)==1);
    string value="Param/Value/"+string(alone?"2E52C7C4":"1DAED953")+
        gv_roleNameArray[pool][1]+"Param/Value/"+(alone?"38F4D320":"6B729A4E");
    CHECK(std::count(messages.begin(),messages.end(),std::make_pair(value,p))==1);
}
int killers(int pool) {
    int result=0;
    for(int p=1;p<=15;++p) {
        if(PlayerGroupHasPlayer(gv_alivePlayers,p) && gv_roles[p][1]==pool &&
           (gv_roles[p][0]==1 || (gv_roles[p][0]>=17 && gv_roles[p][0]<=19) ||
            (gv_roles[p][0]==2 && gv_roleOptions[pool][2][3]))) ++result;
    }
    return result;
}
int main() {
    for(int pool: {2,5}) {
        const int base=offset(pool), enemy=other(pool);
        for(int seat: {1,8,15}) for(bool original: {false,true}) {
            reset("solo / flag restore / seat "+std::to_string(seat)+" pool "+std::to_string(pool));
            role(seat,pool,21); gv_roleOptions[pool][1][10]=original;
            gv_roleOptions[enemy][1][10]=!original;
            // Poison previous invocation's state: dispatcher must recount from zero.
            std::fill(std::begin(gv_rsConvX),std::end(gv_rsConvX),77);
            run(); converted(seat,pool,true);
            CHECK(gv_roleOptions[pool][1][10]==original);
            CHECK(gv_roleOptions[enemy][1][10]==!original);
            CHECK(gv_rsConvX[base]==1 && gv_rsConvX[base+2]==1 && gv_rsConvX[base+3]==1);
            CHECK(gv_rsConvX[offset(enemy)]==0 && gv_rsConvX[offset(enemy)+3]==0);
            CHECK(cards.size()==1 && messages.size()==1 && calls["refresh"]==1);
            calls.clear(); cards.clear(); messages.clear();
            run();
            CHECK(cards.empty() && messages.empty() && calls["refresh"]==0);
            CHECK(gv_specialCasePlayer[seat][17]==101+seat && gv_rsConvX[base+3]==0);
        }
    }
    std::cout << "PASS: solo conversion, seats 1/8/15, both original flag10 values, pool identity, cards/messages/stats/refresh" << std::endl;

    for(int pool: {2,5}) {
        const int base=offset(pool);
        reset("dead lawyer pool "+std::to_string(pool));
        role(1,pool,21); gv_alivePlayers &= ~(1<<1);
        run(); unchangedLawyer(1,pool); noChanges();
        CHECK(gv_rsConvX[base]==0 && gv_rsConvX[base+2]==0);

        for(int killer: {1,17,18,19}) for(int seat: {1,15}) {
            reset("existing killer "+std::to_string(killer)+" pool "+std::to_string(pool));
            role(seat,pool,21); role(16-seat,pool,killer);
            run(); unchangedLawyer(seat,pool); noChanges();
            CHECK(gv_rsConvX[base]==1 && gv_rsConvX[base+2]==2 && killers(pool)==1);
        }
        for(int killer: {1,17,18,19}) {
            reset("dead killer does not reserve knife pool "+std::to_string(pool));
            role(1,pool,21); role(15,pool,killer); gv_alivePlayers &= ~(1<<15);
            run(); converted(1,pool,true);
            CHECK(gv_rsConvX[base]==1 && gv_rsConvX[base+2]==1 && calls["refresh"]==1);
        }
        for(bool canKill: {false,true}) for(bool convertLeader: {false,true}) for(int seat: {1,15}) {
            reset("leader canKill="+std::to_string(canKill)+" convert="+std::to_string(convertLeader)+" pool "+std::to_string(pool));
            role(seat,pool,21); role(16-seat,pool,2);
            gv_roleOptions[pool][2][3]=canKill;
            gv_roleOptions[pool][2][4]=convertLeader;
            run();
            if(canKill || (convertLeader && seat==15)) unchangedLawyer(seat,pool);
            else converted(seat,pool,false);
            CHECK(killers(pool)==1);
            CHECK(gv_rsConvX[base+2]==2);
            CHECK(calls["refresh"]==int(!canKill || convertLeader));
        }
        // Promotion reservation is set before the player-ordered conversion pass.
        for(bool canKill: {false,true}) for(int seat: {1,15}) {
            reset("advisor leader priority pool "+std::to_string(pool));
            role(seat,pool,21); role(16-seat,pool,4);
            gv_roleOptions[pool][4][0]=true; gv_roleOptions[pool][2][10]=true;
            gv_roleOptions[pool][2][3]=canKill;
            run();
            CHECK(gv_roles[16-seat][0]==2 && gv_roles[16-seat][1]==pool);
            CHECK(gv_rsConvX[base+6]==1 && gv_rsConvX[base+1]==16-seat);
            if(canKill) unchangedLawyer(seat,pool);
            else converted(seat,pool,false);
            CHECK(killers(pool)==1 && calls["refresh"]==1);
        }
        for(int seat: {1,15}) for(bool fallback: {false,true}) {
            reset("advisor ordinary conversion competition pool "+std::to_string(pool));
            role(seat,pool,21); role(16-seat,pool,4);
            gv_roleOptions[pool][4][2]=fallback;
            run();
            CHECK(killers(pool)==1 && gv_rsConvX[base]==1);
            CHECK(cards.size()==1 && calls["refresh"]==1);
            if(fallback && seat==15) unchangedLawyer(seat,pool);
            else converted(seat,pool,false);
        }
    }
    std::cout << "PASS: death, existing/dead killers 1/17/18/19, leader attack/conversion, advisor/butler priority and knife fallback" << std::endl;

    for(int pool: {2,5}) {
        const int base=offset(pool);
        reset("multiple lawyers pool "+std::to_string(pool));
        for(int p: {1,8,15}) role(p,pool,21);
        run(); converted(1,pool,false); unchangedLawyer(8,pool); unchangedLawyer(15,pool);
        CHECK(killers(pool)==1 && cards.size()==1 && messages.size()==1 && calls["refresh"]==1);
        CHECK(gv_rsConvX[base]==1 && gv_rsConvX[base+2]==3);
        auto stats=gv_specialCasePlayer[1][17];
        cards.clear(); messages.clear(); calls.clear();
        for(int repeat=0;repeat<4;++repeat) {
            run(); unchangedLawyer(8,pool); unchangedLawyer(15,pool);
            CHECK(gv_specialCasePlayer[1][17]==stats);
            CHECK(cards.empty() && messages.empty() && calls["refresh"]==0 && killers(pool)==1);
            CHECK(gv_rsConvX[base]==1 && gv_rsConvX[base+3]==0);
        }
        // Use role3, not historical triad role15/wuxian's unrelated pool-index bug.
        for(int seat: {1,15}) {
            reset("ordinary convertible competes pool "+std::to_string(pool));
            role(seat,pool,21); role(16-seat,pool,3); gv_roleOptions[pool][3][0]=true;
            run(); CHECK(killers(pool)==1 && gv_rsConvX[base]==1);
            CHECK(cards.size()==1 && messages.size()==1 && calls["refresh"]==1);
            if(seat==1) converted(seat,pool,false);
            else unchangedLawyer(seat,pool);
        }
        for(int seat: {1,15}) {
            reset("lawyer before fallback16 pool "+std::to_string(pool));
            role(seat,pool,21); role(16-seat,pool,16); gv_roleOptions[pool][16][0]=true;
            run(); converted(seat,pool,false);
            CHECK(gv_roles[16-seat][0]==16 && gv_specialCasePlayer[16-seat][17]==116-seat);
            CHECK(killers(pool)==1 && cards.size()==1 && calls["refresh"]==1);
        }
        reset("fallback16 without lawyer remains functional pool "+std::to_string(pool));
        role(1,pool,16); gv_roleOptions[pool][16][0]=true;
        run(); CHECK(gv_roles[1][0]==1 && killers(pool)==1 && calls["refresh"]==1);
    }
    std::cout << "PASS: multi-lawyer single knife, repeated dispatcher idempotence, ordinary-role competition, lawyer before fallback16" << std::endl;

    for(int state=0;state<4;++state) {
        reset("independent gangs state "+std::to_string(state));
        role(1,2,21); role(15,5,21);
        if(state&1) role(2,2,17);
        if(state&2) role(14,5,19);
        run();
        if(state&1) unchangedLawyer(1,2); else converted(1,2,true);
        if(state&2) unchangedLawyer(15,5); else converted(15,5,true);
        CHECK(gv_rsConvX[0]==1 && gv_rsConvX[10]==1);
        CHECK(gv_rsConvX[2]==1+int(bool(state&1)) && gv_rsConvX[12]==1+int(bool(state&2)));
        CHECK(gv_rsConvX[3]==int(!(state&1)) && gv_rsConvX[13]==int(!(state&2)));
        CHECK(calls["refresh"]==int(state!=3));
        CHECK(cards.size()==size_t(2-int(bool(state&1))-int(bool(state&2))));
    }
    // Exercise helper guards directly, independently of dispatcher's alive guard.
    for(int pool: {2,5}) {
        const int base=offset(pool);
        for(int bad: {-1,0,16,99}) {
            reset("helper invalid player"); role(1,pool,21);
            gf_LSConvert(bad); invariants(); noChanges(); unchangedLawyer(1,pool);
        }
        for(int wrong: {1,3,4}) {
            reset("helper wrong pool"); role(1,wrong,21);
            gf_LSConvert(1); invariants(); noChanges(); CHECK(gv_roles[1][0]==21);
        }
        reset("helper wrong role"); role(1,pool,3);
        gf_LSConvert(1); invariants(); noChanges(); CHECK(gv_roles[1][0]==3);
        reset("helper dead lawyer"); role(1,pool,21); gv_alivePlayers &= ~(1<<1);
        gf_LSConvert(1); invariants(); noChanges(); unchangedLawyer(1,pool);
        for(bool reserved: {false,true}) for(bool canKill: {false,true}) {
            reset("helper reserved leader guard pool "+std::to_string(pool));
            role(1,pool,21); gv_rsConvX[base+2]=1;
            gv_rsConvX[base+6]=reserved;
            gv_roleOptions[pool][2][3]=canKill;
            gv_roleOptions[other(pool)][2][3]=!canKill;
            gf_LSConvert(1); invariants();
            if(reserved && canKill) { unchangedLawyer(1,pool); noChanges(); }
            else {
                converted(1,pool,true);
                CHECK(gv_rsConvX[base]==1 && gv_rsConvX[base+3]==1);
                CHECK(calls["refresh"]==0); // Dispatcher owns the single final refresh.
            }
        }
        reset("helper existing count"); role(1,pool,21); gv_rsConvX[base]=1;
        gf_LSConvert(1); invariants(); unchangedLawyer(1,pool); noChanges();
    }
    std::cout << "PASS: independent gang counts/flags, helper guards/reservation, unchanged visits/LS lifetime state; " << fixtures << " fixtures" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    code = harness(args.script.read_text())
    with tempfile.TemporaryDirectory(prefix='bh-lawyer-conversions-') as tmp:
        cpp, exe = Path(tmp) / 'conversions.cpp', Path(tmp) / 'conversions'
        cpp.write_text(code)
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
