#!/usr/bin/env python3
"""shw317: execute actual medic/amnesiac Galaxy with UBSan/bounds.

Reuses the old interaction suite's extraction/explicit engine doubles IN MEMORY;
never edits it or executes its old medic expectations. Added complete production
functions and exact immediate caller blocks execute unchanged. Game objects,
chat/UI transport, cards, waits and deaths remain explicit boundary doubles.
This is not SC2 compilation, rendering, timing, multiplayer or bank validation.
Native 2/5 refresh executes the shared actual initializer and all six SKO bodies;
revival preserves votes, existing shields, external defenses and world traps.

Run: python3 tools/test_revival_memory_faction.py --script PATH
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import test_faction_interactions as legacy
from test_egun import SCRIPT, function

ADDITIONAL = (
    'gf_SKR_1_jijiuzhuanjia', 'gf_SKP_1_jijiuzhuanjia',
    'gf_SKP_1_jijiuzhuanjia_2', 'gf_JJResolve', 'gf_RANoActions',
    'gf_RAAmnesiacActions', 'gf_SKA_3_shiyizhe', 'gf_SKP_3_shiyizhe',
    'gf_SKN_3_shiyizhe', 'gf_SKG_3_shiyizhe_2',
    'gf_BHVisit', 'gf_BHVisitAction', 'gf_BHConvertedSuccession',
    'gf_BHApprenticeNativeInit',
    'gf_SKO_2_qinglizhe', 'gf_SKO_5_xiangzhu',
    'gf_SKO_2_bangjiazhe', 'gf_SKO_5_shenxun',
    'gf_SKO_2_qipianzhe', 'gf_SKO_5_mihuo',
)


def caller(source: str, owner: str, callee: str, wrapper: str, args: str) -> str:
    body = function(source, owner)
    matches = list(re.finditer(r'(?m)^\s*if ([^\n]+) \{\s*'
                              + re.escape(callee) + r'\([^;]+;\s*}', body))
    assert len(matches) == 1, (owner, callee)
    block = matches[0][0].strip()
    assert 'gf_BHFaction(' not in block, ('dispatch must retain profession', owner)
    return f'void {wrapper}({args}) {{\n{block}\n}}'


def harness(source: str) -> str:
    guards = [
        caller(source, 'gf_RSTownSetup', 'gf_SKR_1_jijiuzhuanjia', 'medicSetup', 'int lv_a'),
        caller(source, 'gf_SequencePrep', 'gf_SKP_1_jijiuzhuanjia', 'medicPrep', 'int lv_a'),
        caller(source, 'gf_SequencePrep', 'gf_SKP_1_jijiuzhuanjia_2', 'medicVisit', 'int lv_a'),
        caller(source, 'gt_ASActionButtonATown_Func', 'gf_SKA_1_jijiuzhuanjia', 'medicClick', 'int lv_source, int lv_target'),
        caller(source, 'gt_ASActionButtonANeutral_Func', 'gf_SKA_3_shiyizhe', 'memoryClick', 'int lv_source, int lv_target'),
        caller(source, 'gf_SequenceAfter2', 'gf_SKG_3_shiyizhe', 'memoryResolve', 'int lv_a, int lv_h'),
    ]
    dawn = function(source, 'auto_gf_DayTransition_TriggerFunc')
    frozen = re.search(r'if \(\(gv_roles\[lv_a\]\[1\] == 1\) && \(gv_roles\[lv_a\]\[0\] == 34\)\) \{', dawn)
    assert frozen
    end = legacy.core.block_end(dawn, dawn.index('{', frozen.start()))
    block = dawn[frozen.start():end]
    assert 'gv_jjPick[lv_a] = gv_action[lv_a][0];' in block
    guards.append('void medicFreeze(int lv_a) {\n' + block + '\n}')
    assert dawn.index('gf_JJResolve();') > dawn.index('gv_jjPick[lv_a] = gv_action[lv_a][0];')

    # Keep all legacy gameplay bodies/dimensions; only add one presentation double.
    original_extra, original_base = legacy.EXTRA, legacy.core.harness
    names = ADDITIONAL + tuple(re.findall(r'^void (\w+)\(', '\n'.join(guards), re.M))
    if re.search(r'^bool gf_JJFactionAllowed\s*\([^;]+\) \{', source, re.M):
        names += ('gf_JJFactionAllowed',)

    def base_with_tooltip(text: str) -> str:
        return original_base(text) + '\ntemplate<class... T> void libNtve_gf_SetDialogItemTooltip(T...) {}\n'

    try:
        legacy.EXTRA = tuple(dict.fromkeys(original_extra + names))
        legacy.core.harness = base_with_tooltip
        code = legacy.harness(source + '\n' + '\n\n'.join(guards))
    finally:
        legacy.EXTRA, legacy.core.harness = original_extra, original_base

    code = code.replace(function(code, 'main'), '')
    for name in ('gv_janitized', 'gv_variant', 'gv_brFrozen', 'gv_brDone'):
        if not re.search(r'\b' + name + r'\b', code):
            declaration = re.search(r'^(\w+)((?:\[\d+\])*)\s+' + name + r'\s*(?:=[^;]*)?;', source, re.M)
            assert declaration, ('missing actual metadata declaration', name)
            kind, dims = declaration.groups()
            code += f'\n{kind} {name}{dims};\n'

    for name in ('gf_RAJijiuActions', 'gf_SKA_1_jijiuzhuanjia', 'gf_JJRevive',
                 'gf_JJResolve', 'gf_SKG_3_shiyizhe', *ADDITIONAL):
        body = function(source, name)
        start = source.index(body)
        print(f'  {name}: {source.count(chr(10), 0, start)+1}..'
              f'{source.count(chr(10), 0, start+len(body))+1}', flush=True)

    print('Added complete medic/memory/visit/succession bodies and 7 exact caller blocks; '
          'outer scheduling and presentation remain boundaries', flush=True)
    return code + TESTS


TESTS = r'''
void fresh(string label,int faction=0) {
    interactionReset(label); role(1,1,34); gv_bhFaction[1]=faction;
    clearValue(gv_janitized); gv_variant="";
    gv_action[1][0]=0; gv_jjLeft[1]=1; gv_jjArmed[1]=true;
    gv_originalRole[1][1]=1; gv_originalRole[1][0]=34;
}
void corpse(int p,int pool,int id,int faction=0) {
    role(p,pool,id); gv_bhFaction[p]=faction; PlayerGroupRemove(gv_alivePlayers,p);
}
void testMedicFactionMatrix() {
    for(int medic:{0,2,5}) for(int pool:{1,2,3,5})
    for(int faction:{0,2,5}) for(int id:{4,8,34}) {
        fresh("medic UI/click/freeze/resolve faction Cartesian matrix",medic);
        corpse(8,pool,id,faction);
        int actual=pool==1 && faction!=0?faction:pool;
        bool allowed=actual==1 || (medic!=0 && actual==medic);
        int oldShots=gv_shots[8], oldCooldown=gv_cooldown[8];
        gv_activated[8]=true; gv_dayAction[8]=true; gv_skillCount[8]=3;
        gv_originalRole[8][1]=3; gv_originalRole[8][0]=7;
        medicSetup(1); CHECK(visible[gv_actionDialogItem[8][5]]==allowed);
        medicClick(1,8); CHECK(gv_action[1][0]==(allowed?8:0)); CHECK(gv_jjLeft[1]==1);
        medicPrep(1); medicVisit(1);
        CHECK(!gv_busEligible[1] && !gv_witchEligible[1] && !gv_veteranEligible[1]);
        CHECK(gv_visitation[1]==(allowed?8:0));
        medicFreeze(1); CHECK(gv_jjPick[1]==(allowed?8:0));
        gf_JJResolve(); CHECK(gv_jjPick[1]==0);
        CHECK(PlayerGroupHasPlayer(gv_alivePlayers,8)==allowed);
        CHECK(gv_jjLeft[1]==(allowed?0:1));
        CHECK(gv_roles[8][1]==pool && gv_roles[8][0]==id && gv_bhFaction[8]==faction);
        CHECK(gv_originalRole[8][1]==3 && gv_originalRole[8][0]==7);
        CHECK(gv_originalRole[1][1]==1 && gv_originalRole[1][0]==34);
        if(allowed && pool==1) {
            CHECK(gv_shots[8]==-1 && gv_cooldown[8]==0);
            CHECK(!gv_activated[8] && !gv_dayAction[8] && gv_skillCount[8]==0);
            if(id==34) CHECK(gv_jjLeft[8]==1 && gv_jjArmed[8]);
        } else if(allowed && (pool==2 || pool==5)) {
            CHECK(gv_shots[8]==-1 && gv_cooldown[8]==0);
            CHECK(!gv_activated[8] && !gv_dayAction[8] && gv_skillCount[8]==0);
        } else {
            CHECK(gv_shots[8]==oldShots && gv_cooldown[8]==oldCooldown);
            CHECK(gv_activated[8] && gv_dayAction[8] && gv_skillCount[8]==3);
        }
        if(allowed) CHECK(hasMessage(8,"JJREVIVED"));
        if(pool==1 && id==8 && faction!=0) CHECK(gf_BHSeenFaction(8)==1 && actual!=1);
        clearEffects(); medicSetup(1);
        if(allowed) CHECK(!visible[gv_actionDialogItem[8][5]]);
    }
}
void testMedicBoundaries() {
    for(int failure=0;failure<8;++failure) {
        fresh("medic freeze and commit failure consumes no charge",2); corpse(8,2,4);
        medicClick(1,8);
        if(failure==0) gv_roleblocked[1]=9;
        if(failure==1) gv_jailed[1]=9;
        if(failure==2) gv_jjLeft[1]=0;
        if(failure==3) PlayerGroupRemove(gv_alivePlayers,1);
        medicFreeze(1);
        if(failure<4) CHECK(gv_jjPick[1]==0);
        if(failure==4) PlayerGroupRemove(gv_currentPlayers,8);
        if(failure==5) PlayerGroupAdd(gv_alivePlayers,8);
        if(failure==6) gv_bhFaction[1]=5;
        if(failure==7) { role(8,1,8); gv_bhFaction[8]=5; }
        int left=gv_jjLeft[1]; gf_JJResolve(); CHECK(gv_jjLeft[1]==left);
        CHECK(PlayerGroupHasPlayer(gv_alivePlayers,8)==(failure==5));
    }
    fresh("medic change/cancel and spent charges",2); corpse(8,2,4); corpse(9,1,4);
    medicClick(1,8); medicClick(1,9); CHECK(gv_action[1][0]==9);
    medicClick(1,1); CHECK(gv_action[1][0]==0);
    gv_jjLeft[1]=0; medicClick(1,8); CHECK(gv_action[1][0]==0);
    medicSetup(1); CHECK(!visible[gv_actionDialogItem[8][5]]);

    fresh("two medics cannot double-revive one corpse",2); role(2,1,34); gv_bhFaction[2]=2;
    gv_jjLeft[2]=1; corpse(8,2,4); gv_jjPick[1]=8; gv_jjPick[2]=8;
    gf_JJResolve(); CHECK(gv_jjLeft[1]==0 && gv_jjLeft[2]==1);
    CHECK(PlayerGroupHasPlayer(gv_alivePlayers,8)); CHECK(hasMessage(2,"JJLIVE"));

    // Both cleaned and ordinary corpses retain the existing medic eligibility:
    // neither production medic nor amnesiac UI currently filters gv_janitized.
    for(int cleaned:{0,9}) for(string variant:{"", "clue"}) {
        fresh("existing corpse visibility metadata is not rewritten",2); corpse(8,1,4);
        gv_janitized[8]=cleaned; gv_variant=variant;
        medicClick(1,8); medicFreeze(1); gf_JJResolve();
        CHECK(gv_jjLeft[1]==0 && PlayerGroupHasPlayer(gv_alivePlayers,8));
        CHECK(gv_janitized[8]==cleaned && gv_variant==variant);
    }
}
void memoryFresh(int pool,int id,int faction,int shots=0) {
    fresh("amnesiac remembers true faction without originalRole rewrite");
    role(1,3,7); gv_originalRole[1][1]=3; gv_originalRole[1][0]=7;
    gv_bhFaction[1]=5; corpse(8,pool,id,faction); gv_shots[8]=shots;
    gv_e5A4B1E5BF86E8ADA6E5918A[1]=0;
}
void testMemoryInheritance() {
    const std::vector<std::pair<int,int>> targets={
        {1,1},{1,4},{1,7},{1,8},{1,18},{1,23},{1,24},{1,31},{1,32},{1,33},{1,34},{1,35},
        {2,1},{2,4},{2,8},{2,17},{2,20},{2,22},
        {5,1},{5,4},{5,8},{5,17},{5,20},{5,22},
        {3,1},{3,2},{3,3},{3,4},{3,5},{3,6},{3,7},{3,8},{3,9},{3,11},
        {3,14},{3,15},{3,16},{3,17},{3,19},{3,20},{3,21},{3,22},{3,24},
        {3,25},{3,26},{3,27},{3,28},{3,29},{3,31},{3,32}
    };
    for(auto target:targets) for(int faction:{0,2,5}) for(int shots:{-1,0,3}) {
        int pool=target.first, id=target.second;
        memoryFresh(pool,id,faction,shots);
        int actual=pool==1 && faction!=0?faction:pool;
        // Full function coverage beyond slots that the legacy UI can select.
        gf_SKG_3_shiyizhe(1,8);
        CHECK(gv_roles[1][1]==pool && gv_roles[1][0]==id && gf_BHFaction(1)==actual);
        CHECK(gv_bhFaction[1]==(pool==1?faction:0));
        CHECK(gv_originalRole[1][1]==3 && gv_originalRole[1][0]==7);
        CHECK(gv_remembered[1][1]==pool && gv_remembered[1][0]==id);
        CHECK(gv_shots[1]==(shots==0?1:shots));
        CHECK(gf_LMCat(1)==actual);
        CHECK(gf_LMRole(1)==(pool==1 && faction!=0?0:id));
    }
    for(int pool:{1,2,3,5}) for(int faction:{0,2,5}) for(int opts=0;opts<8;++opts) {
        memoryFresh(pool,4,faction);
        for(int bit=0;bit<3;++bit) gv_roleOptions[3][7][bit+1]=(opts&(1<<bit))!=0;
        bool blocked=(pool==1 && (opts&1)) || ((pool==2 || pool==5) && (opts&2));
        gf_SKN_3_shiyizhe(1); CHECK(visible[gv_actionDialogItem[8][5]]==!blocked);
        // Invoke click even when UI-hidden: actual settlement options still guard it.
        memoryClick(1,8); memoryResolve(1,8);
        CHECK(gv_roles[1][1]==(blocked?3:pool) && gv_roles[1][0]==(blocked?7:4));
        if(!blocked) CHECK(gf_BHFaction(1)==(pool==1 && faction!=0?faction:pool));
    }
    for(int team:{2,5}) {
        memoryFresh(1,8,team); gf_SKN_3_shiyizhe(1); CHECK(visible[gv_actionDialogItem[8][5]]);
        memoryClick(1,8); memoryClick(1,1); CHECK(gv_action[1][0]==0);
        memoryResolve(1,8); CHECK(gv_roles[1][1]==3 && gv_roles[1][0]==7);
        memoryClick(1,8); memoryResolve(1,8);
        CHECK(gf_BHFaction(1)==team && gf_BHSeenFaction(1)==1 && !gf_BHSpyActive(1));
    }
    for(auto target:std::vector<std::pair<int,int>>{{1,12},{1,14},{1,19},{1,20},{2,2},{5,2},{3,10},{3,12}}) {
        memoryFresh(target.first,target.second,0);
        gf_SKN_3_shiyizhe(1); CHECK(!visible[gv_actionDialogItem[8][5]]);
        memoryClick(1,8); memoryResolve(1,8);
        CHECK(gv_roles[1][1]==3 && gv_roles[1][0]==7);
    }
    for(int cleaned:{0,9}) for(string variant:{"", "clue"}) {
        memoryFresh(1,4,2); gv_janitized[8]=cleaned; gv_variant=variant;
        gf_SKN_3_shiyizhe(1); CHECK(visible[gv_actionDialogItem[8][5]]);
        memoryClick(1,8); memoryResolve(1,8);
        CHECK(gf_BHFaction(1)==2 && gv_janitized[8]==cleaned && gv_variant==variant);
    }
}
void testSuccessionAndRefresh() {
    for(int team:{2,5}) for(bool missing:{false,true}) {
        memoryFresh(1,34,team); memoryClick(1,8); memoryResolve(1,8);
        int offset=team==2?0:10; gv_rsConvX[offset]=missing?0:1;
        gf_BHConvertedSuccession(1);
        CHECK(gf_BHFaction(1)==team);
        CHECK(gv_roles[1][1]==(missing?team:1) && gv_roles[1][0]==(missing?1:34));
        CHECK(gv_bhFaction[1]==(missing?0:team));
        CHECK(gv_originalRole[1][1]==3 && gv_originalRole[1][0]==7);
        if(missing) CHECK(gv_action[1][0]==0 && gv_action[1][1]==0);
        else { medicSetup(1); CHECK(gv_jjLeft[1]==1 && gv_jjArmed[1]); }
    }
    for(int id:{1,6,13,14,17,19,22,23,30,34}) for(int opts=0;opts<8;++opts) {
        fresh("Town revival retains existing option-dependent charge/cooldown reset"); corpse(8,1,id);
        gv_roleOptions[1][id][0]=(opts&1)!=0;
        gv_roleOptions[1][id][1]=(opts&2)!=0;
        gv_roleOptions[1][id][2]=(opts&4)!=0;
        gv_cooldown[8]=5; gv_activated[8]=true;
        gf_JJRevive(1,8);
        CHECK(gv_jjLeft[1]==0 && gv_cooldown[8]==0 && !gv_activated[8]);
        if(id==22) CHECK(gv_shots[8]==2);
        if(id==23) CHECK(gv_shots[8]==3);
        if(id==34) CHECK(gv_jjLeft[8]==1 && gv_jjArmed[8]);
    }
}
int nativeShots(int id,int options) {
    if(id==6) return options&4?3:options&2?2:options&1?1:-1;
    if(id==9 || id==15) return 1;
    if(id==11) return options&2?4:options&1?3:2;
    if(id==20) return 2;
    return -1;
}
string nativeResources(int p) {
    string result;
    appendValue(result,gv_roles[p]); appendValue(result,gv_originalRole[p]);
    appendValue(result,gv_bhFaction[p]); appendValue(result,gv_shots[p]);
    appendValue(result,gv_cooldown[p]); appendValue(result,gv_activated[p]);
    appendValue(result,gv_dayAction[p]); appendValue(result,gv_skillCount[p]);
    appendValue(result,gv_votes[p]); appendValue(result,gv_immuneChance[p]);
    appendValue(result,gv_immune[p]); appendValue(result,gv_healing[p]); appendValue(result,gv_guarded[p]);
    appendValue(result,gv_disguised[p]); appendValue(result,gv_jailing[p]); appendValue(result,gv_pretended[p]);
    appendValue(result,gv_ysPierce[p]); appendValue(result,gv_variableOptions[p]);
    appendValue(result,gv_hlGangInitialized[p]); appendValue(result,gv_hlNextNight[p]);
    appendValue(result,gv_hlHouse[p]); appendValue(result,gv_hlLeft[p]); appendValue(result,gv_hlFaction[p]);
    appendValue(result,gv_lsUsed[p]); appendValue(result,gv_lsTarget[p]); appendValue(result,gv_lsDay[p]);
    appendValue(result,gv_brReady[p]); appendValue(result,gv_brRecruit[p]);
    return result;
}
void testNativeRevivalRefresh() {
    for(int pool:{2,5}) for(int id=1;id<=22;++id) for(int options=0;options<8;++options)
    for(int target:{8,15}) {
        fresh("native 2/5 revival refreshes only revived player's complete ability state",pool);
        corpse(target,pool,id);
        gv_brDone=(options&1)!=0; gv_brFrozen=(options&2)!=0;
        bool done=gv_brDone, frozen=gv_brFrozen;
        gv_dayNumber=3;
        for(int p=1;p<=15;++p) {
            gv_shots[p]=0; gv_cooldown[p]=7; gv_activated[p]=true;
            gv_dayAction[p]=true; gv_skillCount[p]=4;
            gv_votes[p]=4; gv_immuneChance[p]=3;
            for(auto& shield:gv_immune[p]) shield=true;
            gv_healing[p]=6; gv_guarded[p]=7;
            gv_disguised[p]=5; gv_jailing[p]=5; gv_pretended[p]=true;
            gv_ysPierce[p]=true;
            for(int i=0;i<4;++i) { gv_variableOptions[p][i]=2; gv_brRecruit[p][i]=3+i; }
            gv_hlGangInitialized[p]=false; gv_hlNextNight[p]=20;
            for(int i=0;i<2;++i) {
                gv_hlHouse[p][i]=3+i; gv_hlLeft[p][i]=2; gv_hlFaction[p][i]=pool;
            }
            gv_lsUsed[p]=true; gv_lsTarget[p]=6; gv_lsDay[p]=2; gv_brReady[p]=true;
        }
        for(int option=1;option<=3;++option) gv_roleOptions[pool][6][option]=(options&(1<<(option-1)))!=0;
        for(int option=1;option<=2;++option) gv_roleOptions[pool][11][option]=(options&(1<<(option-1)))!=0;
        gv_originalRole[target][1]=3; gv_originalRole[target][0]=7;
        // Stale coverage has no effect on a native profession and must not be rewritten.
        gv_bhFaction[target]=pool==2?5:2;
        string others[16];
        for(int p=2;p<=15;++p) if(p!=target) others[p]=nativeResources(p);
        medicClick(1,target); medicFreeze(1); gf_JJResolve();
        CHECK(PlayerGroupHasPlayer(gv_alivePlayers,target) && gv_jjLeft[1]==0);
        CHECK(gv_roles[target][1]==pool && gv_roles[target][0]==id && gf_BHFaction(target)==pool);
        CHECK(gv_bhFaction[target]==(pool==2?5:2));
        CHECK(gv_originalRole[target][1]==3 && gv_originalRole[target][0]==7);
        CHECK(gv_shots[target]==nativeShots(id,options) && gv_cooldown[target]==0);
        CHECK(!gv_activated[target] && !gv_dayAction[target] && gv_skillCount[target]==0);
        CHECK(gv_votes[target]==4 && gv_immuneChance[target]==3);
        for(auto shield:gv_immune[target]) CHECK(shield);
        CHECK(gv_healing[target]==6 && gv_guarded[target]==7);
        CHECK(gv_action[target][0]==0 && gv_action[target][1]==0);
        for(auto value:gv_variableOptions[target]) CHECK(value==0);
        CHECK(gv_disguised[target]==(id==8?0:5));
        CHECK(gv_jailing[target]==(id==9?0:5));
        CHECK(gv_pretended[target]==(id!=15));
        CHECK(gv_ysPierce[target]==(id!=19));
        CHECK(gv_hlGangInitialized[target]==(id==20));
        CHECK(gv_hlNextNight[target]==(id==20?0:20));
        for(int i=0;i<2;++i) {
            CHECK(gv_hlHouse[target][i]==3+i && gv_hlLeft[target][i]==2 && gv_hlFaction[target][i]==pool);
        }
        CHECK(gv_lsUsed[target]==(id!=21));
        CHECK(gv_lsTarget[target]==(id==21?0:6) && gv_lsDay[target]==(id==21?0:2));
        CHECK(gv_brReady[target]==(id!=22));
        for(int i=0;i<4;++i) CHECK(gv_brRecruit[target][i]==(id==22?0:3+i));
        CHECK(gv_brDone==done && gv_brFrozen==frozen);
        for(int p=2;p<=15;++p) if(p!=target) CHECK(nativeResources(p)==others[p]);
        CHECK(killed.empty());
    }
}
int main() {
    testMedicFactionMatrix(); testMedicBoundaries(); testMemoryInheritance(); testSuccessionAndRefresh();
    testNativeRevivalRefresh();
    std::cout << "PASS: " << fixtures << " medic/memory fixtures, " << checks
              << " actual-body assertions; UBSan/bounds; no SC2 engine claim" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    code = harness(args.script.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='bh-revival-memory-') as tmp:
        cpp, exe = Path(tmp) / 'revival.cpp', Path(tmp) / 'revival'
        cpp.write_text(code, encoding='utf-8')
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
