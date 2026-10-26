#!/usr/bin/env python3
"""Run actual recruitment + complete gang succession Galaxy under UBSan/bounds.

Extends test_baron_leaders' actual-body harness only in memory. The full
RSConversions dispatcher, all SKV dependencies, LSConvert and converted-member
succession are extracted intact. Engine/UI calls remain explicit doubles.
Native-lawyer materialization supplies a metamorphic priority/count oracle;
it does not replace production dispatch or counting. Not an SC2 compiler,
rendering, multiplayer, or timing test.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import test_baron_leaders as baron
import test_faction_conversion as core
from test_egun import SCRIPT, function, mask, translate


def harness(source: str) -> str:
    base = baron.harness(source)
    base = base.replace(function(base, 'main'), '')
    names = ['gf_RSConversions', 'gf_LSConvert', 'gf_LSIs', 'gf_BHConvertedSuccession']
    bodies = []
    for name in names:
        body = function(source, name)
        bodies.append(body)
        for dependency in sorted(core.calls(body)):
            if dependency.startswith('gf_SKV_') and dependency not in names:
                names.append(dependency)

    dispatcher = mask(bodies[0])
    hook = dispatcher.index('gf_BHConvertedSuccession(lv_a);')
    assert dispatcher.count('gf_BHConvertedSuccession(lv_a);') == 1
    assert dispatcher.index('gf_LSConvert(lv_a);') < hook < dispatcher.index('gf_SKV_2_qizi(')
    assert hook < dispatcher.index('gf_SKV_5_sishi(')
    for count, pool in ((2, 2), (12, 5)):
        assert re.search(r'if \(\(gf_BHFaction\(lv_a\) == ' + str(pool) + r'\) && \(gf_GKIs\(lv_a\) == false\)\) \{\s*gv_rsConvX\[' + str(count) + r'\] \+= 1;', dispatcher)

    night = mask(function(source, 'auto_gf_NightTransition_TriggerFunc'))
    assert night.index('gf_BRResolveRecruit();') < night.index('gv_isNight = true;') < night.index('gf_RSConversions();') < night.index('gf_RAActionsBase(lv_a);') < night.index('gf_RSTownSetup();')
    assert 'gf_BHConvertedSuccession' not in mask(function(source, 'gf_BRResolveRecruit'))
    feign = mask(function(source, 'gf_BHFeign'))
    assert 'PlayerGroupRemove(gv_alivePlayers, lp_victim);' in feign
    helper = mask(function(source, 'gf_BHConvertedSuccession'))
    assert helper.index('gv_bhFaction[lp_player] = 0;') < helper.index('gf_RTRoleCard(lp_player);')
    assert not re.search(r'\bgv_(?:bhFeignRole|roleblocked|jailed)\b', helper)
    assert not re.search(r'\bgv_(?:bhFeignRole|roleblocked|jailed)\b', dispatcher)
    for key, faction, target in (('NJBOX2', '黑手党', '党徒'), ('TDBOX2', '三合会', '暴徒')):
        strings = (SCRIPT.parent / 'strings-baron.txt').read_text()
        value = next(line.split('=', 1)[1] for line in strings.splitlines() if line.startswith('Param/Value/' + key + '='))
        assert value.endswith(f'<n/>- 若当前没有可以杀人的{faction}角色，被你招募的人会成为{target}。')

    raw = '\n\n'.join(bodies)
    used = set(re.findall(r'\bgv_\w+', mask(raw)))
    needed = sorted(used - set(re.findall(r'\bgv_\w+', base)))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not set(needed) - declarations.keys(), ('missing actual globals', set(needed) - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in needed)
    resets = '\n'.join(f'    clearValue({name});' for name in needed)
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    unknown = core.calls(raw) - set(names) - core.calls(base)
    assert not unknown, ('unstubbed dependency', unknown)
    code = translate(raw)
    code = re.sub(r'^(\s+(?:int|bool|fixed|text|string|playergroup)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', code, flags=re.M)
    old_card = function(base, 'gf_RTRoleCard')
    base = base.replace(old_card, '''std::vector<std::array<int,5>> successionCards;
void gf_RTRoleCard(int p) {
    CHECK(p>=1 && p<=15);
    successionCards.push_back({p,gv_roles[p][1],gv_roles[p][0],gv_bhFaction[p],int(gv_roleOptions[gv_roles[p][1]][gv_roles[p][0]][10])});
    events.push_back("role-card");
}''')
    print(f'Extracted complete dispatcher + {len(names)-1} actual conversion helpers; real recruitment and conversion API; verified night timing, alive-only eligibility, clear-before-card, and card features', flush=True)
    return base + '\n' + globals_text + '\n' + headers + '\n' + code + r'''
int successionOffset(int pool) { return pool==2?0:10; }
void succReset(string label,int pool=2) {
    brReset(label,pool);
''' + resets + r'''
    role(1,1,1);
    for(int p=1;p<=15;++p) {
        gv_originalRole[p][1]=1; gv_originalRole[p][0]=6;
        gv_specialCasePlayer[p][17]=100+p;
        gv_votes[p]=1;
    }
    successionCards.clear(); clearEffects();
}
void recruit(int p,int pool,int profession=6) { role(p,1,profession); gv_bhFaction[p]=pool; }
string lifetime(bool includeAction=true) {
    string result;
    appendValue(result,gv_originalRole); appendValue(result,gv_shots); appendValue(result,gv_cooldown);
    if(includeAction) appendValue(result,gv_action);
    appendValue(result,gv_visitation); appendValue(result,gv_visitation2);
    return result;
}
void succRun() {
    const string before=lifetime(false);
    int actions[16][2]{};
    bool wasConverted[16]{};
    for(int p=1;p<=15;++p) {
        wasConverted[p]=gf_BHConverted(p);
        actions[p][0]=gv_action[p][0]; actions[p][1]=gv_action[p][1];
    }
    gf_RSConversions(); CHECK(lifetime(false)==before);
    for(int p=1;p<=15;++p) {
        bool promoted=wasConverted[p] && !gf_BHConverted(p) && gv_roles[p][0]==1;
        CHECK(gv_action[p][0]==(promoted?0:actions[p][0]));
        CHECK(gv_action[p][1]==(promoted?0:actions[p][1]));
    }
}
void stillRecruited(int p,int pool,int profession=6) {
    CHECK(gv_roles[p][1]==1 && gv_roles[p][0]==profession && gv_bhFaction[p]==pool);
    CHECK(gf_BHConverted(p) && gf_BHFaction(p)==pool);
    CHECK(gv_specialCasePlayer[p][17]==100+p);
}
void successor(int p,int pool) {
    CHECK(gv_roles[p][1]==pool && gv_roles[p][0]==1 && gv_bhFaction[p]==0);
    CHECK(!gf_BHConverted(p) && gf_BHFaction(p)==pool);
    CHECK(gv_specialCasePlayer[p][17]==101+p);
    CHECK(gv_votes[p]==1 && gv_immuneChance[p]==0);
    CHECK(gv_action[p][0]==0 && gv_action[p][1]==0);
    CHECK(std::count(successionCards.begin(),successionCards.end(),std::array<int,5>{p,pool,1,0,1})==1);
}
void testRecruitThenSucceed() {
    for(int pool:{2,5}) for(bool leaderDies:{false,true}) {
        succReset("actual first-day night-entry recruitment pool="+std::to_string(pool)+" leaderDies="+std::to_string(leaderDies),pool);
        role(1,pool,22); role(4,1,6); role(8,1,4); role(15,1,35);
        commandTargets({4,8,15});
        const string before=lifetime();
        commitAtNightEntry();
        CHECK(lifetime()==before);
        stillRecruited(4,pool); stillRecruited(8,pool,4); stillRecruited(15,pool,35);
        CHECK(successionCards.empty());
        if(leaderDies) gv_alivePlayers &= ~(1u<<1); // death after successful night-entry recruitment
        succRun();
        if(!leaderDies) {
            CHECK(gv_roles[1][0]==22); stillRecruited(4,pool);
            CHECK(successionCards.empty());
            gv_alivePlayers &= ~(1u<<1);
            succRun();
        }
        successor(4,pool); stillRecruited(8,pool,4); stillRecruited(15,pool,35);
        CHECK(gv_rsConvX[successionOffset(pool)]==1 && gv_rsConvX[successionOffset(pool)+2]==3);
        CHECK(hasMessage(4,"1DAED953"));
        successionCards.clear(); clearEffects(); succRun();
        CHECK(successionCards.empty() && eventCount("refresh")==0);
        gv_alivePlayers &= ~(1u<<4);
        succRun(); successor(8,pool); stillRecruited(15,pool,35);
        successionCards.clear(); clearEffects(); gv_alivePlayers &= ~(1u<<8);
        succRun(); successor(15,pool); CHECK(hasMessage(15,"2E52C7C4"));
        CHECK(eventCount("refresh")==1);
    }
}
void testCountsAndPriority() {
    for(int pool:{2,5}) {
        const int base=successionOffset(pool);
        for(int killer:{1,2,17,18,19,22}) for(int seat:{1,15}) for(bool alive:{false,true}) {
            succReset("existing killers only block while alive",pool);
            recruit(seat,pool); role(16-seat,pool,killer);
            gv_roleOptions[pool][2][3]=true;
            if(!alive) gv_alivePlayers &= ~(1u<<(16-seat));
            succRun();
            if(alive) { stillRecruited(seat,pool); CHECK(successionCards.empty()); }
            else { successor(seat,pool); CHECK(hasMessage(seat,"2E52C7C4")); }
            CHECK(gv_rsConvX[base+2]==(alive?2:1));
        }
        for(bool canKill:{false,true}) for(int seat:{1,15}) {
            succReset("advisor promotion priority before recruited candidate",pool);
            recruit(seat,pool); role(16-seat,pool,4);
            gv_roleOptions[pool][4][0]=true; gv_roleOptions[pool][2][10]=true;
            gv_roleOptions[pool][2][3]=canKill;
            succRun(); CHECK(gv_roles[16-seat][0]==2);
            if(canKill) stillRecruited(seat,pool); else successor(seat,pool);
            CHECK(gv_rsConvX[base+6]==1 && gv_rsConvX[base+2]==2);
        }
        for(int native:{3,21}) for(int seat:{1,15}) {
            succReset("same ordinary player order, not new global priority",pool);
            recruit(seat,pool); role(16-seat,pool,native); gv_roleOptions[pool][3][0]=true;
            succRun();
            if(seat==1) { successor(seat,pool); CHECK(gv_roles[15][0]==native); }
            else { stillRecruited(seat,pool); CHECK(gv_roles[1][0]==1); }
            CHECK(gv_rsConvX[base]==1 && successionCards.size()==1);
        }
        for(int seat:{1,15}) {
            succReset("recruited candidate before fallback16 regardless of player id",pool);
            recruit(seat,pool); role(16-seat,pool,16); gv_roleOptions[pool][16][0]=true;
            succRun(); successor(seat,pool); CHECK(gv_roles[16-seat][0]==16);
        }
        succReset("converted faction counts prevent native lone-disguiser shortcut",pool);
        recruit(1,pool); role(15,pool,8);
        succRun(); successor(1,pool); CHECK(gv_rsConvX[base+2]==2);
        CHECK(gv_roles[15][0]==8);
        for(bool flag:{false,true}) {
            succReset("temporary flag10 restored and independent from enemy",pool);
            recruit(15,pool); gv_roleOptions[pool][1][10]=flag;
            gv_roleOptions[pool==2?5:2][1][10]=!flag;
            succRun(); successor(15,pool);
            CHECK(gv_roleOptions[pool][1][10]==flag && gv_roleOptions[pool==2?5:2][1][10]==!flag);
        }
    }
    for(int mask=0;mask<4;++mask) {
        succReset("both gangs independent actual counts"); recruit(1,2); recruit(15,5);
        if(mask&1) role(4,2,22);
        if(mask&2) role(8,5,22);
        succRun();
        if(mask&1) stillRecruited(1,2); else successor(1,2);
        if(mask&2) stillRecruited(15,5); else successor(15,5);
        CHECK(gv_rsConvX[0]==1 && gv_rsConvX[10]==1);
    }
}
void testTownStateAndGuild() {
    for(int pool:{2,5}) {
        for(int profession:{7,12,13,14,17,33,35}) {
            succReset("recruit keeps Town capabilities; real succession drops permanent Town powers",pool);
            role(1,pool,22); role(8,1,profession);
            gv_votes[8]=3; gv_immuneChance[8]=2;
            gv_action[8][0]=4; gv_action[8][1]=15;
            commandTargets({8});
            const string before=lifetime();
            commitAtNightEntry();
            CHECK(lifetime()==before && gv_votes[8]==3 && gv_immuneChance[8]==2);
            CHECK(gv_action[8][0]==4 && gv_action[8][1]==15);
            stillRecruited(8,pool,profession);
            successionCards.clear(); clearEffects(); // converted FZ legitimately re-renders its profession at recruitment
            succRun(); stillRecruited(8,pool,profession);
            CHECK(gv_votes[8]==3 && gv_immuneChance[8]==2);
            gv_alivePlayers &= ~(1u<<1);
            succRun(); successor(8,pool);
            CHECK(gv_rsConvX[successionOffset(pool)]==1);
            role(8,1,6); // future real Town profession cannot revive a stale faction overlay
            CHECK(!gf_BHConverted(8) && gf_BHFaction(8)==1 && gv_bhFaction[8]==0);
        }
        succReset("converted Mason first inherits killer, not Town elder",pool);
        recruit(8,pool,7); gv_roleOptions[1][7][0]=true; gv_previousShots=3;
        succRun(); successor(8,pool); CHECK(gv_rsConvX[4]==0);

        succReset("converted elder first pass only records membership; succession clears override",pool);
        recruit(8,pool,14);
        succRun(); successor(8,pool); CHECK(gv_rsConvX[4]==8);

        succReset("retained Mason can first become Town elder while leader lives, then inherit killer",pool);
        role(1,pool,22); recruit(8,pool,7);
        gv_roleOptions[1][7][0]=true; gv_previousShots=3;
        gf_RSConversions();
        CHECK(gv_roles[8][1]==1 && gv_roles[8][0]==14 && gv_bhFaction[8]==pool);
        CHECK(gf_BHConverted(8) && gv_shots[8]==3 && gv_rsConvX[4]==8);
        CHECK(gv_specialCasePlayer[8][17]==109);
        successionCards.clear(); clearEffects(); gv_alivePlayers &= ~(1u<<1);
        succRun();
        CHECK(gv_roles[8][1]==pool && gv_roles[8][0]==1 && gv_bhFaction[8]==0);
        CHECK(!gf_BHConverted(8) && gv_specialCasePlayer[8][17]==110);
        CHECK(successionCards==std::vector<std::array<int,5>>{{8,pool,1,0,1}});
    }
}
void testEligibility() {
    for(int pool:{2,5}) {
        for(int guard=0;guard<5;++guard) {
            succReset("alive-only succession exactly like native rules",pool);
            recruit(1,pool); recruit(8,pool);
            if(guard==0) gv_alivePlayers &= ~(1u<<1);
            if(guard==1) { gv_bhFeignRole[1]=6; gv_alivePlayers &= ~(1u<<1); }
            if(guard==2) gv_roleblocked[1]=8;
            if(guard==3) gv_jailed[1]=8;
            if(guard==4) gv_bhFeignRole[1]=6; // poison field without removal: alive stays authoritative
            succRun();
            if(guard<2) { stillRecruited(1,pool); successor(8,pool); }
            else { successor(1,pool); stillRecruited(8,pool); }
        }
        for(int bad:{INT_MIN,-1,0,16,INT_MAX}) {
            succReset("helper invalid id before array access",pool); recruit(8,pool);
            const string before=baronState(); gf_BHConvertedSuccession(bad); CHECK(baronState()==before);
        }
        for(int wrongPool:{0,2,3,4,5}) {
            succReset("stale overrides on non-Town roles cannot inherit",pool);
            role(8,wrongPool,6); gv_bhFaction[8]=pool;
            const string before=baronState(); gf_BHConvertedSuccession(8); CHECK(baronState()==before);
        }
        succReset("helper dead candidate",pool); recruit(8,pool); gv_alivePlayers &= ~(1u<<8);
        const string before=baronState(); gf_BHConvertedSuccession(8); CHECK(baronState()==before);
    }
}
struct Fixture {
    int pool[16]{}, id[16]{}, faction[16]{};
    bool alive[16]{};
    bool options[9][41][11]{};
};
void testNativeMaterialization() {
    std::mt19937 rng(20261025);
    for(int round=0;round<1024;++round) {
        Fixture fixture;
        const int nativeIds[]={1,2,3,4,8,16,17,18,19,21,22};
        for(int p=1;p<=15;++p) {
            fixture.alive[p]=(rng()%4)!=0;
            if(p%3==0) { fixture.pool[p]=1; fixture.id[p]=6; fixture.faction[p]=(rng()%2?2:5); }
            else { fixture.pool[p]=(rng()%2?2:5); fixture.id[p]=nativeIds[rng()%11]; }
        }
        for(int pool:{2,5}) for(int id:{1,2,3,4,16}) for(int option:{0,2,3,4,10}) fixture.options[pool][id][option]=rng()%2;
        std::vector<int> expectedRole,expectedStats,expectedCounters;
        std::vector<std::pair<string,int>> expectedMessages;
        for(bool materialize:{true,false}) {
            succReset("native-lawyer materialization round "+std::to_string(round));
            for(int p=1;p<=15;++p) {
                role(p,fixture.pool[p],fixture.id[p]); gv_bhFaction[p]=fixture.faction[p];
                if(materialize && fixture.faction[p]) { role(p,fixture.faction[p],21); gv_bhFaction[p]=0; }
                if(!fixture.alive[p]) gv_alivePlayers &= ~(1u<<p);
            }
            for(int pool:{2,5}) for(int id:{1,2,3,4,16}) for(int option:{0,2,3,4,10}) gv_roleOptions[pool][id][option]=fixture.options[pool][id][option];
            succRun();
            std::vector<int> actualRole,actualStats,actualCounters;
            std::vector<std::pair<string,int>> actualMessages;
            for(int p=1;p<=15;++p) {
                bool promoted=fixture.faction[p] && gv_roles[p][1]==fixture.faction[p] && gv_roles[p][0]==1;
                if(fixture.faction[p]) {
                    actualRole.push_back(promoted);
                    CHECK(gv_bhFaction[p]==((materialize || promoted)?0:fixture.faction[p]));
                }
                else { actualRole.push_back(gv_roles[p][1]*100+gv_roles[p][0]); }
                actualStats.push_back(gv_specialCasePlayer[p][17]);
            }
            for(int x:gv_rsConvX) actualCounters.push_back(x);
            for(const auto& m:messages) actualMessages.emplace_back(m.value,m.target);
            if(materialize) { expectedRole=actualRole; expectedStats=actualStats; expectedCounters=actualCounters; expectedMessages=actualMessages; }
            else { CHECK(actualRole==expectedRole); CHECK(actualStats==expectedStats); CHECK(actualCounters==expectedCounters); CHECK(actualMessages==expectedMessages); }
        }
    }
}
int main() {
    testRecruitThenSucceed(); testCountsAndPriority(); testTownStateAndGuild(); testEligibility(); testNativeMaterialization();
    std::cout << "PASS actual recruitment + complete succession: " << fixtures << " fixtures, " << checks << " checks; UBSan/bounds; native-materialization oracle, no faction/count/priority algorithm stubs" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    code = harness(args.script.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='bh-baron-succession-') as directory:
        cpp, executable = Path(directory) / 'succession.cpp', Path(directory) / 'succession'
        cpp.write_text(code, encoding='utf-8')
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    main()
