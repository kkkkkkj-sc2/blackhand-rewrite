#!/usr/bin/env python3
"""Execute real Baron refusal/selection/conversion/GK guards, UBSan + bounds.

Only engine/presentation calls are recording doubles inherited from the Baron
suite. Actual localized refusal keys are loaded from strings-baron.txt. This is
not an SC2 compiler, rendering, multiplayer or scheduling test.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import test_baron_leaders as baron
from test_egun import SCRIPT, function

ROOT = Path(__file__).resolve().parent.parent
NEW_KEYS = ('BRFAIL1', 'BRFAIL2', 'BRFAIL3', 'BRREFUSE2', 'BRREFUSE5')


def harness(source: str) -> str:
    entries = {}
    for line in (ROOT / 'work/blackhand/strings-baron.txt').read_text().splitlines():
        if line.startswith('Param/Value/'):
            key, value = line.split('=', 1)
            assert key not in entries, ('duplicate key', key)
            entries[key] = value

    expected = dict(zip(NEW_KEYS, (
        '你尝试招募', '失败了，他是个「', '」。',
        '有一位领袖尝试邀请你加入黑手党，你无情地拒绝了他。',
        '有一位领袖尝试邀请你加入三合会，你无情地拒绝了他。',
    )))
    for key, value in expected.items():
        assert entries['Param/Value/' + key] == value, ('localized refusal text', key)

    for key in ('NJBOX2', 'TDBOX2', 'NJDESC', 'TDDESC'):
        assert '若你招募了无法招募的角色，你会得知他们的身份。' in entries['Param/Value/' + key]

    for name in ('nanjue', 'taidou'):
        spec = json.loads((ROOT / 'roles' / (name + '.json')).read_text())
        assert [option['i'] for option in spec['options']] == [0, 1, 2]
        assert '死亡、离局、假死及无效目标不泄漏' in spec['note']

    code = baron.harness(source)
    code = code.replace(function(code, 'main'), '')
    # Real GK guard/dependencies are inherited, not a permissive bool stub.
    assert 'gv_gkRole[lp_player] >= 33' in function(code, 'gf_GKIs')
    assert 'gf_GKIs(lp_player)' in function(code, 'gf_BHFaction')
    assert 'TriggerCreate("gt_GKPanel_Func")' in function(code, 'gt_GKAbilities_Init')
    lookup = '\n'.join(
        '    if(key==' + json.dumps('Param/Value/' + key) + ') return '
        + json.dumps(value, ensure_ascii=False) + ';'
        for key, value in expected.items()
    )
    code = code.replace(function(code, 'StringExternal'),
                        'text StringExternal(string key) {\n' + lookup
                        + '\n    return "{"+key+"}";\n}')
    return code + r'''
int countExact(int player,const string& value) {
    return std::count_if(messages.begin(),messages.end(),[&](const Message& m) {
        return m.target==player && m.value==value;
    });
}
string refusal(int pool) {
    return pool==2?"有一位领袖尝试邀请你加入黑手党，你无情地拒绝了他。":
                   "有一位领袖尝试邀请你加入三合会，你无情地拒绝了他。";
}
string failure(int target) {
    return "你尝试招募"+std::to_string(gv_playerSpot[target])+". "+
        TextWithColor(gv_name[target],gv_playerColor[target])+"失败了，他是个「"+
        gf_BHRoleName(target)+"」。";
}
void namedTarget(int p,int pool,int id) {
    role(p,pool,id);
    gv_name[p]="目标"+std::to_string(p);
    gv_playerColor[p]=p*137;
    gv_roleNameArray[pool][id]="真实职业"+std::to_string(pool)+"/"+std::to_string(id);
}
void checkNoRefusal() {
    for(const auto& m:messages) {
        CHECK(m.value.find("你尝试招募")==string::npos);
        CHECK(m.value!=refusal(2) && m.value!=refusal(5));
    }
}
void testNamedFailures() {
    for(int pool:{2,5}) for(bool start:{false,true}) {
        const int roles[][2]={{2,4},{5,4},{3,1},{3,21},{3,32},{3,33},{3,37},{1,28},{1,29}};
        for(const auto& entry:roles) {
            brReset("every living valid unrecruitable profession: private true identity",pool,start);
            namedTarget(8,entry[0],entry[1]);
            if(entry[0]==3 && entry[1]>=33) {
                gv_gkRole[8]=entry[1]; gv_gkFaction[8]=1;
                CHECK(gf_GKIs(8) && gf_BHFaction(8)==1);
            }
            commandTargets({8});
            CHECK(!hasMessage(1,"BRFAIL1"));
            checkNoRefusal();
            const string before=professionState();
            clearEffects(); commitAtNightEntry();
            CHECK(professionState()==before && gv_bhFaction[8]==0);
            CHECK(countExact(1,failure(8))==1 && countExact(8,refusal(pool))==1);
            CHECK(messages.size()==3);
            CHECK(countExact(1,StringExternal("Param/Value/BRRESULT")+"0")==1);
            for(const auto& m:messages) {
                CHECK(m.sender==m.target);
                CHECK(m.target==1 || m.target==8);
                CHECK(m.value.find("DQ:")==string::npos);
            }
            CHECK(gv_brDone && recruits().empty());
            clearEffects(); gf_BRResolveRecruit(); CHECK(messages.empty());
        }
    }
}
void testMixedCounts() {
    for(int pool:{2,5}) for(bool start:{false,true}) for(int cap:{2,3,4}) {
        brReset("mixed success and per-target failure do not change cap/timing/profession",pool,start);
        setRecruitCap(pool,cap);
        std::vector<int> targets;
        namedTarget(2,1,4);
        for(int p=3;p<cap+2;++p) namedTarget(p,3,p==3?21:p==4?33:32);
        for(int p=2;p<cap+2;++p) {
            targets.push_back(p);
            gv_shots[p]=p+7; gv_cooldown[p]=p+11;
            gv_action[p][0]=14; gv_visitation[p]=14; gv_visitation2[p]=13;
        }
        commandTargets(targets); checkNoRefusal();
        CHECK(gf_BHFaction(2)==1 && gf_BRCount(1)==cap);
        const string before=professionState();
        clearEffects(); commitAtNightEntry();
        CHECK(professionState()==before && gf_BHFaction(2)==pool);
        CHECK(countExact(1,StringExternal("Param/Value/BRRESULT")+"1")==1);
        CHECK(hasMessage(2,pool==2?"BHFJOIN2":"BHFJOIN5"));
        CHECK(countExact(2,refusal(pool))==0);
        for(int p=3;p<cap+2;++p) {
            CHECK(countExact(1,failure(p))==1 && countExact(p,refusal(pool))==1);
            CHECK(gv_bhFaction[p]==0);
        }
        CHECK(messages.size()==size_t(2+2*(cap-1)));
        CHECK(recruits().empty() && gv_brDone);
    }
}
void testInvalidTargetPrivacy() {
    for(int pool:{2,5}) for(int invalid=0;invalid<16;++invalid) {
        brReset("dead/left/feigned/invalid target must not leak identity",pool);
        namedTarget(8,3,21); commandTargets({8}); freezeAtNightEntry();
        if(invalid==0) gv_alivePlayers&=~(1u<<8);
        if(invalid==1) gv_currentPlayers&=~(1u<<8);
        if(invalid==2) gv_bhFeignRole[8]=21;
        if(invalid==3) gv_brRecruit[1][0]=0;
        if(invalid==4) gv_brRecruit[1][0]=-1;
        if(invalid==5) gv_brRecruit[1][0]=16;
        if(invalid==6) gv_brRecruit[1][0]=INT_MAX;
        if(invalid==7) gv_brRecruit[1][0]=INT_MIN;
        if(invalid==8) gv_roles[8][1]=-1;
        if(invalid==9) gv_roles[8][1]=9;
        if(invalid==10) gv_roles[8][0]=-1;
        if(invalid==11) gv_roles[8][0]=41;
        if(invalid==12) gv_roles[8][0]=0;
        if(invalid==13) gv_roleNameArray[3][21]="";
        if(invalid==14) { role(8,4,1); gv_roleNameArray[4][1]="random slot, not profession"; }
        if(invalid==15) gv_brRecruit[1][0]=1;
        clearEffects(); gf_BRResolveRecruit(); checkNoRefusal();
        CHECK(messages.size()==1 && messages[0].target==1);
        CHECK(countExact(1,StringExternal("Param/Value/BRRESULT")+"0")==1);
        CHECK(gv_bhFaction[8]==0);
    }
}
void testLeaderPrivacy() {
    for(int pool:{2,5}) for(int invalid=0;invalid<5;++invalid) {
        brReset("ineligible leader must not gain refusal information",pool);
        namedTarget(8,3,21); commandTargets({8}); freezeAtNightEntry();
        if(invalid==0) gv_alivePlayers&=~(1u<<1);
        if(invalid==1) gv_currentPlayers&=~(1u<<1);
        if(invalid==2) gv_bhFeignRole[1]=22;
        if(invalid==3) gv_jailed[1]=8;
        if(invalid==4) role(1,1,33);
        clearEffects(); gf_BRResolveRecruit(); CHECK(messages.empty());
    }
}
void testBothLeaders() {
    brReset("both leaders independently reject same target with own faction copy");
    role(15,5,22); namedTarget(8,3,21);
    commandTargets({8},1); commandTargets({8},15);
    clearEffects(); commitAtNightEntry();
    CHECK(countExact(1,failure(8))==1 && countExact(15,failure(8))==1);
    CHECK(countExact(8,refusal(2))==1 && countExact(8,refusal(5))==1);
    CHECK(countExact(1,StringExternal("Param/Value/BRRESULT")+"0")==1);
    CHECK(countExact(15,StringExternal("Param/Value/BRRESULT")+"0")==1);
    CHECK(messages.size()==6 && gv_bhFaction[8]==0);

    brReset("first committed leader wins contested Town; loser sees real converted profession");
    role(15,5,22); namedTarget(8,1,8);
    commandTargets({8},1); commandTargets({8},15);
    clearEffects(); commitAtNightEntry();
    CHECK(gf_BHFaction(8)==2 && gv_roles[8][1]==1 && gv_roles[8][0]==8);
    CHECK(hasMessage(8,"BHFJOIN2"));
    CHECK(countExact(15,failure(8))==1 && countExact(8,refusal(5))==1);
    CHECK(countExact(1,failure(8))==0 && countExact(8,refusal(2))==0);
    CHECK(countExact(1,StringExternal("Param/Value/BRRESULT")+"1")==1);
    CHECK(countExact(15,StringExternal("Param/Value/BRRESULT")+"0")==1);
    CHECK(messages.size()==5);
}
int main() {
    testNamedFailures(); testMixedCounts(); testInvalidTargetPrivacy();
    testLeaderPrivacy(); testBothLeaders();
    std::cout << "PASS localized Baron/Taido refusals: " << fixtures << " fixtures, " << checks
              << " checks; real recruitment/conversion/GK functions, UBSan/bounds" << std::endl;
}
'''


def main() -> None:
    code = harness(SCRIPT.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='bh-baron-refusal-') as directory:
        cpp, executable = Path(directory) / 'refusal.cpp', Path(directory) / 'refusal'
        cpp.write_text(code, encoding='utf-8')
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    main()
