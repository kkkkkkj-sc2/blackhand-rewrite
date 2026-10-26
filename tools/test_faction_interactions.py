#!/usr/bin/env python3
"""Execute actual faction/legacy-role interactions with UBSan and bounds checks.

Extends test_faction_conversion's generated C++ harness IN MEMORY; neither that
suite nor Galaxy source is edited. Auditing, recruitment, traps, classifications,
revival, leader resolve/feign/kill, bombing, amnesiac inheritance and their helpers
are extracted as complete real function bodies. Death dispatch, game objects,
UI/audio/chat transport and killer-history storage are explicit boundaries.
Complex cult/infection dispatchers additionally get concrete write-site checks:
every non-Town pool write must immediately clear that player's faction override.
No SC2 compiler, multiplayer, rendering, timing or bank-persistence claim is made.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import test_faction_conversion as core
from test_egun import SCRIPT, function, mask, translate

EXTRA = (
    'gf_SKG_3_shenjiguan', 'gf_SKG_1_gongjihuizhanglao',
    'gf_SKG_1_zhengmuguan', 'gf_SKG_3_shiyizhe',
    'gf_HLGang', 'gf_HLCanPlace', 'gf_HLTier', 'gf_HLImmune',
    'gf_HLIsVictim', 'gf_HLSnap', 'gf_ESForesterKill',
    'gf_HLResolveOne', 'gf_HLForesterNight',
    'gf_DQClassify', 'gf_YLTellFaction',
    'gf_JJFactionAllowed', 'gf_RAJijiuActions', 'gf_SKA_1_jijiuzhuanjia',
    'gf_JJRefreshAbilities', 'gf_JJRevive', 'gf_BHApprenticeNativeInit',
    'gf_SKO_2_qinglizhe', 'gf_SKO_5_xiangzhu',
    'gf_SKO_2_bangjiazhe', 'gf_SKO_5_shenxun',
    'gf_SKO_2_qipianzhe', 'gf_SKO_5_mihuo',
    'gf_SKO_1_shimin', 'gf_SKO_1_yijing', 'gf_SKO_1_yujing',
    'gf_SKO_1_gongjihuizhanglao', 'gf_SKO_1_tuiwujunren', 'gf_SKO_1_shiguan',
    'gf_BHLeaderResolve', 'gf_BHFeign', 'gf_BHLeaderKill',
    'gf_ESQiziBomb', 'gf_QiziAtHouse', 'gf_BHWentTo',
    'gf_BHCrime', 'gf_BHCrimeMurder', 'gf_SKC_3_chuxingzhe',
)


def cleanup_sites(source: str) -> None:
    total = 0
    expected = {'gf_SequenceAfter2': 2, 'gf_SKG_3_wuyi': 1,
                'gf_SKC_3_chuxingzhe': 1, 'gf_ESGanranzheKill': 1}
    for name, count in expected.items():
        body = mask(function(source, name))
        writes = list(re.finditer(r'(?:gv_roles\[([^;\n]+)\]\[1\]\s*=\s*[235]|gf_GKSetRoleField\(([^;\n]+),\s*1,\s*[235]\));', body))
        assert len(writes) == count, ('non-Town write sites changed; inspect each path', name, len(writes))
        for write in writes:
            target = '[' + (write[1] or write[2]) + ']'
            assert re.search(r'gv_bhFaction' + re.escape(target) + r'\s*=\s*0;\s*$', body[:write.start()]), ('override must be cleared immediately before this exact pool write', name, write[0])
            total += 1

    print(f'PASS: {total} exact non-Town role-pool write sites clear the same player override first (cult dispatcher/witch doctor/executioner/infection)', flush=True)


def harness(source: str) -> str:
    cleanup_sites(source)
    base = core.harness(source)
    names = tuple(name for name in core.with_guoke_dependencies(source, EXTRA)
                  if not re.search(r'^\w+ ' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', base, re.M))
    bodies = [function(source, name) for name in names]
    raw = '\n\n'.join(bodies)
    used = set(re.findall(r'\bgv_\w+', mask(raw))) | {'gv_location', 'gv_number'}
    existing = set(re.findall(r'\bgv_\w+\b', base))
    needed = sorted(used - existing)
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not set(needed) - declarations.keys(), ('missing actual extra global declaration', set(needed) - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in needed)
    resets = '\n'.join(f'    clearValue({name});' for name in needed)
    snapshots = '\n'.join(f'    appendValue(result, {name});' for name in needed)
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    code = translate(raw)
    # Galaxy null text compares as empty text; game-object handles are integer
    # doubles. Keep this type translation separate from executable game logic.
    code = re.sub(r'(gv_roleNameArray\[[^\n;]+\]\s*==\s*)null\b', r'\1text{}', code)
    code = re.sub(r'\bnull\b', '0', code)
    code = re.sub(r'^(\s+(?:int|bool|text|string|playergroup)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', code, flags=re.M)

    # SKA_jijiuzhuanjia uses the existing private-target hint slot, not always 0;
    # fake death legitimately disables rather than enables chatting.
    old = 'CHECK(target>=1 && target<=15 && mode==0); messages.push_back'
    assert base.count(old) == 1
    base = base.replace(old, '(void)mode; CHECK(target>=1 && target<=15); messages.push_back')
    old = 'CHECK(p>=1 && p<=15 && allow==ge_Allow_Allow); allows.push_back'
    assert base.count(old) == 1
    base = base.replace(old, 'CHECK(p>=1 && p<=15 && (allow==0 || allow==ge_Allow_Allow)); allows.push_back')
    base = base.replace(function(base, 'main'), '')

    constants = sorted(set(re.findall(r'\b(?:c_|ge_)\w+', mask(raw))) - set(re.findall(r'\b(?:c_|ge_)\w+', base)))
    constants_text = '\n'.join(f'constexpr int {name}={index};' for index, name in enumerate(constants, 10))
    # ge_Allow_Disallow is a semantic enum, not an arbitrary catalog placeholder.
    constants_text = re.sub(r'constexpr int ge_Allow_Disallow=\d+;', 'constexpr int ge_Allow_Disallow=0;', constants_text)

    extension = r'''
using point = int;
''' + globals_text + '\n' + constants_text + r'''
std::vector<int> killed;
std::vector<std::pair<int,int>> history;
std::map<int,bool> visible;
int lastCreatedUnit=0;
string createdModel;
string interactionState() {
    string result=state();
''' + snapshots + r'''
    return result;
}
void PlayerGroupRemove(playergroup& group,int p) { CHECK(p>=1 && p<=15); group&=~(1u<<p); }
void PlayerGroupAdd(playergroup& group,int p) { CHECK(p>=1 && p<=15); group|=1u<<p; }
playergroup PlayerGroupCopy(playergroup group) { return group; }
int PlayerGroupPlayer(playergroup group,int index) {
    for(int p=1;p<=15;++p) if(group&(1u<<p)) { if(--index==0) return p; }
    CHECK(false); return 0;
}
int RandomInt(int lo,int hi) { CHECK(lo<=hi); return lo; }
double RandomFixed(double lo,double hi) { CHECK(lo<=hi); return lo; }
void gf_BHNotify(text value,int target,soundlink) { gf_CBSystemMessage(value,target,target,0,"notify",0); }
void gf_BHRecordNightKiller(int victim,int killer) { history.emplace_back(victim,killer); }
void gf_KillPlayer(int p,bool dissolve) {
    CHECK(p>=1 && p<=15 && !dissolve);
    killed.push_back(p); PlayerGroupRemove(gv_alivePlayers,p); events.push_back("death:"+std::to_string(p));
}
void gf_BHMafiaShow(int p,bool landed,bool triad) { events.push_back("show:"+std::to_string(p)+":"+std::to_string(landed)+":"+std::to_string(triad)); }
void gf_BHGunDeathText(int p,bool) { events.push_back("death-text:"+std::to_string(p)); }
void gf_ESBodyguardKill(int killer,int guard) { history.emplace_back(guard,killer); events.push_back("bodyguard"); }
void DialogControlSetVisible(int handle,playergroup,bool show) { visible[handle]=show; }
template<class... T> void DialogControlSetSize(T...) {}
template<class... T> void libNtve_gf_SetDialogItemColor(T...) {}
double ColorGetComponent(int,int) { return 0; }
void UnitRemove(unit p) { events.push_back("unit-remove:"+std::to_string(p)); }
void TextTagDestroy(int) { events.push_back("tag-destroy"); }
bool UnitIsValid(unit p) { return p!=0; }
void libNtve_gf_UnitCreateFacingPoint(int count,string model,int,int,point,point) {
    CHECK(count==1); createdModel=model; lastCreatedUnit=501;
}
unit UnitLastCreated() { return lastCreatedUnit; }
point PointFromId(int n) { return n; }
point UnitGetPosition(unit p) { return p; }
template<class... T> void UnitWeaponRemove(T...) {}
template<class... T> void UnitForceStatusBar(T...) {}
template<class... T> void UnitSetState(T...) {}
template<class... T> void libNtve_gf_PauseUnit(T...) {}
template<class... T> void TextTagCreate(T...) {}
template<class... T> void TextTagAttachToUnit(T...) {}
int TextTagLastCreated() { return 91; }
template<class... T> void DialogSetVisible(T...) {}
''' + headers + '\n' + code + r'''
void interactionReset(string label) {
''' + resets + r'''
    reset(label); killed.clear(); history.clear(); visible.clear(); createdModel=""; lastCreatedUnit=0;
    clearValue(gv_visitation); clearValue(gv_visitation2); clearValue(gv_action);
    gv_dayNumber=2;
    for(int p=1;p<=15;++p) {
        gv_number[p]=std::to_string(p);
        for(int i=0;i<7;++i) gv_actionDialogItem[p][i]=p*10+i;
    }
}
void converted(int p,int team,int id=4) { role(p,1,id); gv_bhFaction[p]=team; }
void testAuditorInteractions() {
    for(int team:{2,5}) for(int id:{1,4,8,14,31,34,35}) for(bool enabled:{false,true}) {
        interactionReset("auditor honors converted target options and lowers actual profession");
        role(1,3,11); gv_visitation[1]=8; converted(8,team,id);
        gv_roleOptions[3][11][team==2?0:1]=enabled; gv_shots[1]=3;
        gf_SKG_3_shenjiguan(1);
        if(!enabled) {
            CHECK(gv_roles[8][1]==1 && gv_roles[8][0]==id && gv_bhFaction[8]==team);
            CHECK(gv_shots[1]==3 && !gv_audited[8]);
        } else {
            CHECK(gv_roles[8][1]==team && gv_roles[8][0]==1 && gv_bhFaction[8]==0);
            CHECK(gf_BHFaction(8)==team && !gf_BHConverted(8));
            CHECK(gv_shots[1]==2 && gv_audited[8] && gv_e78AAFE7BDAAE4BA8BE5AE9E[1][7]);
        }
    }
    for(int id:{1,4,14,31,34,35}) {
        interactionReset("auditor ordinary Town remains Town, no phantom triad write");
        role(1,3,11); role(8,1,id); gv_visitation[1]=8; gv_shots[1]=3;
        gf_SKG_3_shenjiguan(1); CHECK(gv_roles[8][1]==1 && gv_roles[8][0]==1 && gv_bhFaction[8]==0);
        CHECK(gv_audited[8] && gv_shots[1]==2);
    }
    for(int id:{8,10}) {
        interactionReset("auditor existing cult exclusion"); role(1,3,11); role(8,3,id); gv_visitation[1]=8;
        int shots=gv_shots[1]; gf_SKG_3_shenjiguan(1);
        CHECK(gv_roles[8][1]==3 && gv_roles[8][0]==id && !gv_audited[8] && gv_shots[1]==shots);
    }
    interactionReset("auditor existing noncult neutral downgrade retained"); role(1,3,11); role(8,3,4); gv_visitation[1]=8;
    gf_SKG_3_shenjiguan(1); CHECK(gv_roles[8][1]==3 && gv_roles[8][0]==2 && gv_bhFaction[8]==0);
    CHECK(!gf_BHConvertFaction(8,2)); CHECK(!gf_BHConvertFaction(8,5));
}
void testRecruitmentInteractions() {
    for(int recruiter:{14,23}) for(int team:{0,2,5}) {
        interactionReset("Mason elder and recruiter cannot collect converted citizen");
        role(1,1,recruiter); role(8,1,1); gv_bhFaction[8]=team; gv_visitation[1]=8;
        gv_shots[1]=3; gv_roleOptions[1][6][1]=true;
        if(recruiter==14) gf_SKG_1_gongjihuizhanglao(1); else gf_SKG_1_zhengmuguan(1);
        CHECK(gv_roles[8][1]==1 && gv_bhFaction[8]==team);
        if(team!=0) { CHECK(gv_roles[8][0]==1); CHECK(eventCount("role-card")==0); }
        else { CHECK(gv_roles[8][0]==(recruiter==14?7:6)); CHECK(eventCount("role-card")==1); }
    }
}
void testClassificationInteractions() {
    for(int pool:{1,2,3,5}) for(int team:{0,2,5}) {
        interactionReset("DQ and Yanluo see actual alignment without rewriting profession");
        role(8,pool,4); gv_bhFaction[8]=team; int actual=pool==1 && team!=0?team:pool;
        CHECK(gf_DQClassify(8)==(actual==1?1:actual==3?3:2));
        string before=professionState(); gf_YLTellFaction(1,8); CHECK(professionState()==before);
        CHECK(messages.size()==1 && messages[0].target==1);
        CHECK(hasMessage(1,actual==1?"YLFACT1":actual==2?"YLFACT2":actual==5?"YLFACT5":"YLFACTN"));
        if(actual==3) CHECK(messages[0].value.find("PROF:3:4")!=string::npos);
    }
}
void testMedicInteractions() {
    for(int pool:{1,2,3,5}) for(int team:{0,2,5}) {
        interactionReset("medic UI/picker/revive consistently exclude converted corpses");
        role(1,1,34); role(8,pool,4); gv_bhFaction[8]=team; gv_alivePlayers&=~(1u<<8); gv_jjLeft[1]=1;
        bool eligible=pool==1 && team==0;
        gf_RAJijiuActions(1); CHECK(visible[gv_actionDialogItem[8][5]]==eligible);
        clearEffects(); gf_SKA_1_jijiuzhuanjia(1,8);
        CHECK(gv_action[1][0]==(eligible?8:0)); CHECK(gv_jjLeft[1]==1);
        if(!eligible) CHECK(messages.empty());
        clearEffects(); string before=interactionState(); gf_JJRevive(1,8);
        if(!eligible) {
            CHECK(interactionState()==before && events.empty() && killed.empty());
            CHECK(gv_jjLeft[1]==1 && !(gv_alivePlayers&(1u<<8)));
        } else {
            CHECK(gv_jjLeft[1]==0 && (gv_alivePlayers&(1u<<8)));
            CHECK(gv_shots[8]==-1 && gv_cooldown[8]==0); CHECK(hasMessage(8,"JJREVIVED"));
        }
    }
}
void testTrapInteractions() {
    const int teams[]={1,2,3,5};
    const int tiers[3][4]={{0,1,3,2},{1,0,3,2},{1,2,3,0}};
    for(int owner=0;owner<3;++owner) for(int target=0;target<4;++target) for(bool overlay:{false,true}) {
        interactionReset("trap tier real faction matrix");
        if(overlay && (teams[target]==2 || teams[target]==5)) converted(8,teams[target]); else role(8,teams[target],4);
        CHECK(gf_HLTier(8,owner==0?1:owner==1?2:5)==tiers[owner][target]);
    }
    for(int team:{2,5}) for(bool second:{false,true}) {
        interactionReset("converted forester snapshots actual faction and does not spring on ally");
        converted(1,team,22); converted(8,team); gv_shots[1]=2; gv_visitation[1]=15;
        if(second) gv_visitation2[8]=15; else gv_visitation[8]=15;
        gf_HLForesterNight(); CHECK(gv_shots[1]==1 && gv_hlFaction[1][0]==team);
        CHECK(gv_hlLeft[1][0]==1 && gv_hlHouse[1][0]==15 && killed.empty());
        // shw317: an existing converted Forester trap follows the new true team.
        gv_bhFaction[1]=team==2?5:2; gv_visitation[1]=0;
        converted(9,team==2?5:2); gv_visitation[9]=15;
        gf_HLResolveOne(1,0); CHECK(killed==std::vector<int>{8});
        CHECK(gv_alivePlayers&(1u<<9)); CHECK(gv_hlLeft[1][0]==0);
        CHECK(gv_hlFaction[1][0]==(team==2?5:2));
    }
    for(int team:{2,5}) for(bool alliedGuard:{false,true}) {
        interactionReset("party trap must spare converted allied bodyguard interceptor");
        role(1,team,20); converted(8,alliedGuard?team:(team==2?5:2)); converted(9,team==2?5:2);
        gv_hlHouse[1][0]=15; gv_hlFaction[1][0]=team; gv_hlLeft[1][0]=2;
        gv_visitation[9]=15; gv_guarded[9]=8; gf_HLResolveOne(1,0);
        CHECK(killed==(alliedGuard?std::vector<int>{}:std::vector<int>{8})); CHECK(gv_alivePlayers&(1u<<9));
    }
}
void testLeaderAndLimaoInteractions() {
    for(int team:{2,5}) for(int targetTeam:{0,2,5}) for(int profession:{4,8,34}) {
        interactionReset("leader chooses fake death by actual faction, not profession id alias");
        role(1,team,17); role(8,1,profession); gv_bhFaction[8]=targetTeam; gv_bhMask[1]=4;
        gf_BHLeaderResolve(1,8);
        if(targetTeam==team) {
            CHECK(killed.empty() && gv_bhFeignRole[8]==4 && !(gv_alivePlayers&(1u<<8)));
            CHECK(gv_roles[8][1]==1 && gv_roles[8][0]==profession && gv_bhFaction[8]==team);
            // Converted fake-dead profession cannot be stolen out of the leader's roster.
            role(2,3,24); clearEffects(); string before=interactionState(); gf_LMSwap(2,8);
            CHECK(interactionState()==before && events.empty());
        } else {
            CHECK(killed==std::vector<int>{8} && gv_bhFeignRole[8]==0);
        }
    }
    for(int team:{2,5}) {
        interactionReset("real party disguiser still protected from allied leader"); role(1,team,17); role(8,team,8);
        gf_BHLeaderResolve(1,8); CHECK(killed.empty() && !gv_bhFeignRole[8] && hasMessage(1,"BZNO8"));
        for(int defense=0;defense<3;++defense) {
            interactionReset("leader converted target retains shield/doctor/bodyguard priority"); role(1,team,17); converted(8,team);
            if(defense==0) gv_immuneChance[8]=1;
            if(defense==1) gv_healing[8]=1;
            if(defense==2) gv_guarded[8]=9;
            gf_BHLeaderResolve(1,8); CHECK(killed.empty() && !gv_bhFeignRole[8]);
            if(defense==0) CHECK(gv_immuneChance[8]==0);
            if(defense==1) CHECK(gv_healing[8]==0);
            if(defense==2) CHECK(eventCount("bodyguard")==1);
        }
    }
}
void testBombInteractions() {
    for(int team:{2,5}) for(bool second:{false,true}) for(bool enemy:{false,true}) {
        interactionReset("suicide bomber excludes converted allies and hits converted enemies");
        role(1,team,16); role(15,team,1); converted(8,team); converted(9,team==2?5:2);
        gv_visitation[8]=15;
        if(enemy) { if(second) gv_visitation2[9]=15; else gv_visitation[9]=15; }
        gf_ESQiziBomb(1,15);
        CHECK(gv_alivePlayers&(1u<<8)); CHECK(gv_damage[8]==0 && !gv_diedAtNight[8]);
        CHECK(killed==(enemy?std::vector<int>{1,9}:std::vector<int>{}));
        CHECK(gv_qzKills[1]==(enemy?1:0));
        CHECK(gv_e78AAFE7BDAAE4BA8BE5AE9E[1][1]==enemy);
        if(!enemy) CHECK(hasMessage(1,"QZFAIL") && gv_damage[1]==0);
    }
}
void testAmnesiacInteractions() {
    for(int team:{0,2,5}) for(int profession:{4,7,14,31,34,35}) for(int shots:{0,3}) {
        interactionReset("amnesiac inherits corpse profession plus independent actual alignment");
        role(1,3,7); gv_originalRole[1][1]=3; gv_originalRole[1][0]=7; gv_bhFaction[1]=5;
        role(8,1,profession); gv_bhFaction[8]=team; gv_alivePlayers&=~(1u<<8); gv_shots[8]=shots;
        role(2,team==0?2:team,1); converted(3,team==0?2:team); role(4,1,7);
        gf_SKG_3_shiyizhe(1,8);
        CHECK(gv_roles[1][1]==1 && gv_roles[1][0]==profession && gv_bhFaction[1]==team);
        CHECK(gv_remembered[1][1]==1 && gv_remembered[1][0]==profession);
        CHECK(gv_originalRole[1][1]==3 && gv_originalRole[1][0]==7);
        CHECK(gv_shots[1]==(shots==0?1:shots));
        if(team!=0) {
            CHECK(hasMessage(2,team==2?"B6985398":"B47B1919"));
            CHECK(hasMessage(3,team==2?"B6985398":"B47B1919"));
            CHECK(!hasMessage(4,"3E7D9AA5"));
            CHECK(gf_LMCat(1)==team && gf_LMRole(1)==0);
        } else CHECK(gf_LMCat(1)==1 && gf_LMRole(1)==profession);
    }
    for(int team:{2,5}) {
        interactionReset("executioner fallback actively clears stale alignment override");
        converted(8,team,4); gv_currentPlayers=gv_alivePlayers=1u<<8;
        gf_SKC_3_chuxingzhe(8); CHECK(gv_roles[8][1]==3 && gv_roles[8][0]==3 && gv_bhFaction[8]==0);
    }
}
int main() {
    testAuditorInteractions(); testRecruitmentInteractions(); testClassificationInteractions();
    testMedicInteractions(); testTrapInteractions(); testLeaderAndLimaoInteractions();
    testBombInteractions(); testAmnesiacInteractions(); testClosedNightWindow();
    std::cout << "PASS: actual auditor/recruitment/classification/medic UI+pick+revive/trap tier+snapshot+interceptor/leader fake+real death/bomber/amnesiac/limao fake-death interactions" << '\n';
    std::cout << "PASS: " << fixtures << " interaction fixtures, " << checks << " assertions; UBSan/bounds; five exact override-cleanup write sites" << std::endl;
}
'''
    definitions = set(re.findall(r'\b(?:void|bool|int|text|string|soundlink|trigger|playergroup|double|unit|point)\s+(\w+)\s*\(', base + extension))
    unknown = core.calls(raw) - definitions
    assert not unknown, ('new actual dependency requires body or documented boundary', unknown)
    print(f'Extracted {len(EXTRA)} additional complete actual functions, {len(needed)} additional actual globals; base logic reused in memory', flush=True)
    return base + extension


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    code = harness(args.script.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='bh-faction-interactions-') as tmp:
        cpp, exe = Path(tmp) / 'interactions.cpp', Path(tmp) / 'interactions'
        cpp.write_text(code, encoding='utf-8')
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
