#!/usr/bin/env python3
"""Run actual auditor decision and cemetery expressions against converted roles.

Reuses the actual faction/recruitment harness. Searcher/bodyguard kill effects are
explicit recording boundaries: tests validate attack selection, not SC2 combat.
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
    skill = function(source, 'gf_SKK_1_shenchayuan')
    assert 'gv_roleOptions[1][26][0] = false;' in function(source, 'gf_DefaultRoleOptions')
    assignments = []
    for name in ('auto_gf_DayTransition_TriggerFunc', 'auto_gf_EExecution_TriggerFunc'):
        body = function(source, name)
        expressions = re.findall(r'^\s*(gv_deadBoxText\[[01]\] = [^\n]*gf_BHDeathName\([^\n]*;)', body, re.M)
        assert len(expressions) >= 2, ('known-identity cemetery paths lost faction-aware display', name)
        assignments.extend(expressions)

    assert len(assignments) == 6, 'review every existing public cemetery expression'
    projection_owners = {'gf_SKF_1_jingzhang': 4, 'gf_SKK_1_shenchayuan': 1,
                         'gf_YLTellFaction': 3, 'gf_BHInvestigatedRoleName': 1}
    for name, count in projection_owners.items():
        assert len(re.findall(r'\bgf_BHSeenFaction\s*\(', mask(function(source, name)))) == count, name

    assert len(re.findall(r'\bgf_BHSeenFaction\s*\(', mask(source))) == 11, 'outward projection leaked into true-faction mechanics'
    roster = mask(function(source, 'gf_RefreshRoleBox'))
    assert roster.count('gf_BHPrivateRoleName(') == 9 and 'gf_BHDeathName(' not in roster
    assert 'Param/Value/BHFSPYTRAIT' in function(source, 'gf_RTTownRoleText')
    faction_report = function(source, 'gf_YLTellFaction')
    raw = skill + '\n' + faction_report + '\n' + '\n'.join(assignments)
    used = set(re.findall(r'\bgv_\w+', mask(raw)))
    needed = used - set(re.findall(r'\bgv_\w+', base))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not needed - declarations.keys(), needed - declarations.keys()
    unknown = core.calls(raw) - core.calls(base) - {'gf_SKK_1_shenchayuan', 'gf_ESSearcherKill', 'gf_ESBodyguardKill', 'gf_YLTellFaction', 'gf_BHNotify'}
    assert not unknown, ('new effect boundary must be explicit', unknown)
    wrappers = '\n'.join(f'void grave_{i}(int p) {{ int lv_a={"0" if "gv_executionList[lv_a]" in statement else "p"}; int lp_player=p; {translate(statement)} }}' for i, statement in enumerate(assignments))
    renderers = ','.join(f'grave_{i}' for i in range(len(assignments)))
    print(f'Extracted actual auditor + {len(assignments)} actual night/execution cemetery expressions; default immunity switch remains off', flush=True)
    return base + '\n' + '\n'.join(declarations[name] for name in sorted(needed)) + r'''
std::vector<std::pair<int,int>> searcherHits, guardHits;
void gf_ESSearcherKill(int target,int killer) { searcherHits.push_back({target,killer}); }
void gf_ESBodyguardKill(int target,int guard) { guardHits.push_back({target,guard}); }
void gf_BHNotify(text value,int player,string sound) { gf_CBSystemMessage(value,player,player,0,sound,Color(0,0,0)); }
''' + translate(skill) + '\n' + translate(faction_report) + '\n' + wrappers + r'''
void cornerReset(string label) {
    brReset(label);
''' + '\n'.join(f'    clearValue({name});' for name in sorted(needed)) + r'''
    searcherHits.clear(); guardHits.clear();
}
void testAuditorFaction() {
    for(int pool:{1,2,3,5}) for(int profession:{1,4,8,13,21,26,27,33,35})
    for(int overridePool:{0,2,5}) for(bool immunity:{false,true}) for(int guess=0;guess<3;++guess) for(bool guarded:{false,true}) {
        cornerReset("auditor role/true-faction/option/guess/bodyguard matrix");
        role(1,1,26); role(8,pool,profession); gv_bhFaction[8]=overridePool;
        gv_visitation[1]=8; gv_roleOptions[1][26][0]=immunity;
        gv_e8A880E781B5E78C9CE6B58B[1][0]=guess==1?(profession==1?4:1):profession;
        gv_e8A880E781B5E78C9CE6B58B[1][1]=guess==2?(pool==1?2:1):pool;
        gv_guarded[8]=guarded?15:0; gv_damage[8]=4;
        const string before=professionState();
        const int faction=pool==1 && overridePool!=0?overridePool:pool;
        const bool spared=guess==0 && immunity && pool==1 && (faction==1 || profession==8);
        const bool attacked=guess==0 && !spared;
        gf_SKK_1_shenchayuan(1);
        CHECK(professionState()==before && gv_bhFaction[8]==overridePool);
        CHECK(searcherHits.size()==size_t(attacked && !guarded));
        CHECK(guardHits.size()==size_t(attacked && guarded));
        CHECK(gv_seqKillsZ[1]==(attacked && !guarded));
        if(attacked && !guarded) CHECK(searcherHits[0]==std::make_pair(8,1));
        if(attacked && guarded) {
            CHECK(guardHits[0]==std::make_pair(1,15));
            CHECK(gv_damage[8]==3 && gv_damage[15]==1 && gv_damage[1]==1 && gv_guarded[8]==0);
        }
        else CHECK(gv_damage[8]==4 && gv_damage[15]==0 && gv_damage[1]==0 && gv_guarded[8]==(guarded?15:0));
        CHECK(hasMessage(1,guess!=0?"0CFCAFEA":spared?"0F85F45E":"A4C61FD7"));
    }
}
void testReportedFaction() {
    for(int pool:{1,2,3,5}) for(int profession:{1,4,8,24,27,35}) for(int faction:{0,2,5}) {
        cornerReset("Spy outward town identity versus unchanged true faction");
        role(1,1,2); role(8,pool,profession); gv_bhFaction[8]=faction;
        gv_visitation[1]=8; gv_roleOptions[1][2][0]=true;
        const int actual=pool==1 && faction!=0?faction:pool;
        const int reported=pool==1 && profession==8?1:actual;
        const string before=professionState();
        CHECK(gf_BHFaction(8)==actual && gf_BHSeenFaction(8)==reported);
        gf_SKF_1_jingzhang(1);
        CHECK(hasMessage(1,"BD797B72")==bool(reported==2));
        CHECK(hasMessage(1,"361742C1")==bool(reported==5));
        messages.clear(); gf_YLTellFaction(1,8);
        CHECK(hasMessage(1,reported==1?"YLFACT1":reported==2?"YLFACT2":reported==5?"YLFACT5":"YLFACTN"));
        CHECK(professionState()==before && gv_bhFaction[8]==faction);
    }
}
void testConvertedGraveyard() {
    const std::vector<void(*)(int)> renderers={
''' + renderers + r'''
    };
    for(int faction:{2,5}) for(int profession:{1,4,26,27,33,35}) for(int player:{1,8,15}) {
        cornerReset("converted cemetery body and tooltip retain faction color");
        role(player,1,profession); gv_bhFaction[player]=faction;
        gv_executionList[0]=player;
        gv_name[player]="target"; gv_number[player]="8";
        const auto expected=gf_BHRoleName(player);
        CHECK(expected.find(faction==2?"<c=85063056>":"<c=56075082>")==0);
        CHECK(expected.find("BHFROLE"+std::to_string(profession))!=string::npos);
        const string before=professionState();
        for(auto render:renderers) {
            clearValue(gv_deadBoxText);
            render(player);
            CHECK(gv_deadBoxText[0].find(expected)!=string::npos || gv_deadBoxText[1].find(expected)!=string::npos);
            CHECK(professionState()==before && gv_bhFaction[player]==faction);
        }
    }
}
int main() {
    testAuditorFaction(); testReportedFaction(); testConvertedGraveyard();
    std::cout << "PASS actual auditor + cemetery expressions: " << fixtures << " fixtures, " << checks << " checks; UBSan/bounds; explicit combat/rendering boundaries" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    code = harness(args.script.read_text())
    with tempfile.TemporaryDirectory(prefix='bh-faction-corners-') as directory:
        cpp, executable = Path(directory) / 'corners.cpp', Path(directory) / 'corners'
        cpp.write_text(code)
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    main()
