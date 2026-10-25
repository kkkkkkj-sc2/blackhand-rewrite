#!/usr/bin/env python3
"""shw317: execute actual allied-native apprenticeship and next-night dispatch.

Run with --script PATH; never edits Galaxy. Includes test_apprentice_faction's
entire Town Cartesian regression, 2 new helpers, all six native SKO initializers,
complete Mafia/Triad night setup dispatchers and every called SKM/SKT block.

Native boundaries are EXPLICIT: RA* action-panel leaves, leader-mask UI, BRDraw,
YSDraw, channel APIs and engine rendering are recording presentation doubles.
Real setup control flow, variableOptions, shots, cooldown, identity, option
selection, lawyer/trap initialization, BR first-night gate and YS night gate run.
The old hostile-learning attack is a recording call boundary, NOT a simulated
SC2 combat/defense resolver. No native attack, engine compilation, full timing,
rendering, multiplayer, global succession, bank or first-win payout claim.
First-win identity is tested by retaining gv_originalRole. No native profession
is excluded: pools 2/5, roles 1..22, including disabled legacy 12/13 (whose native
night setup intentionally offers RANoActions), all five leaders and new 20/21/22.
Neutral pool 3 is not a faction override supported by BHConverted; it is NOT
made learnable by equating all independent neutral professions to allies.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

import test_apprentice_faction as town
from test_egun import SCRIPT, function, mask

LEGACY_SHA256 = '05be17591c361f07c9c1758e5b0498751dcde60fccd90eb702954a7fa36faea5'
EXTRA = ('gf_RSMafiaSetup2', 'gf_RSTriadSetup', 'gf_HLGangSetup',
         'gf_RALawyerActions', 'gf_LSIs', 'gf_BRCanSelect', 'gf_BRIs',
         'gf_BRFake', 'gf_BRSetup', 'gf_YSButtons')
LEAVES = (
    'gf_BHLeaderSetup', 'gf_BRDraw', 'gf_YSDraw',
    'gf_RAAdministratorActions', 'gf_RAAgentActions', 'gf_RABeguilerActions',
    'gf_RABlackmailerActions', 'gf_RAConsigliereActions', 'gf_RAConsortActions',
    'gf_RADeceiverActions', 'gf_RADisguiserActions', 'gf_RADragonHeadActions',
    'gf_RAE997A8E5BE92action', 'gf_RAEnforcerActions', 'gf_RAForesterActions',
    'gf_RAForgerActions', 'gf_RAFramerActions', 'gf_RAGodfatherActions',
    'gf_RAIncenseMasterActions', 'gf_RAInformantActions', 'gf_RAJanitorActions',
    'gf_RALiaisonActions', 'gf_RAMafiosoActions', 'gf_RANoActions',
    'gf_RAPretenderActions', 'gf_RAPretenderActions2', 'gf_RAQiziActions',
    'gf_RASilencerActions', 'gf_RAVanguardActions',
)


def harness(source: str) -> str:
    legacy = function(source, 'gf_SKG_1_xuetu')
    start = legacy.index('    // Implementation\n') + len('    // Implementation\n')
    stop = legacy.index('if ((gv_roles[gv_visitation[lv_a]][1] == 1)) {')
    prefix = legacy[start:stop]
    assert 'gf_BHApprenticeAllyLearn(lv_a, gv_visitation[lv_a])' in prefix
    assert hashlib.sha256((legacy[:start] + legacy[stop:]).encode()).hexdigest() == LEGACY_SHA256, (
        'legacy learning body changed: default Town/hostile paths must be byte-identical')
    assert 'gv_originalRole' not in mask(function(source, 'gf_BHApprenticeNativeInit'))
    assert 'gv_originalRole' not in mask(function(source, 'gf_BHApprenticeAllyLearn'))

    extra = list(EXTRA)
    for name in extra:
        for callee in re.findall(r'\b(gf_(?:SKM|SKT)_\w+)\(', mask(function(source, name))):
            if callee not in extra:
                extra.append(callee)

    # Restore module state even if the test is imported/re-run by a mutation test.
    original_names, original_boundaries = town.NAMES, town.BOUNDARIES.copy()
    town.NAMES += tuple(extra)
    town.BOUNDARIES.update(LEAVES)
    town.BOUNDARIES.update({
        'gf_BHCrime', 'gf_CBAllowDisallowChatting', 'gf_CBAssignUnassignChatChannel',
        'gf_CBHighlightText', 'gf_FlashScreen', 'DialogControlSetEnabled',
        'libNtve_gf_SetDialogItemText',
    })
    try:
        code = town.harness(source)
    finally:
        town.NAMES, town.BOUNDARIES = original_names, original_boundaries

    declarations = r'''
std::vector<std::pair<string,int>> panelCalls;
std::vector<std::pair<int,int>> lethalCalls;
int waits=0, deathSounds=0;
constexpr int ge_Clear_DoNotClear=0, ge_Allow_Allow=0, ge_Highlight_Highlighted=0;
void gf_BHCrime(int,int) { CHECK(false && "jail crime path out of scope"); }
void gf_CBAllowDisallowChatting(int,int) {}
void gf_CBAssignUnassignChatChannel(int,int,int) {}
void gf_CBHighlightText(int,int) {}
void gf_FlashScreen(int,int,double,double) {}
template<class... T> void DialogControlSetEnabled(T...) {}
template<class... T> void libNtve_gf_SetDialogItemText(T...) {}
'''
    declarations += '\n'.join(
        f'void {name}(int p) {{ panelCalls.emplace_back("{name}",p); }}'
        for name in LEAVES)
    fixture_globals = ('gv_hlHouse', 'gv_hlLeft', 'gv_hlFaction', 'gv_brFrozen')
    extra_globals = []
    for name in fixture_globals:
        match = re.search(r'^(\w+)((?:\[\d+\])*)\s+' + re.escape(name)
                          + r'\s*(?:=[^;]*)?;', source, re.M)
        assert match, ('missing real fixture declaration', name)
        kind, dims = match.groups()
        extra_globals.append(f'{kind} {name}{dims};')

    anchor = 'struct Message {'
    assert code.count(anchor) == 1
    code = code.replace(anchor, '\n'.join(extra_globals) + declarations + '\n' + anchor)
    reset_anchor = '    context=label+'
    assert code.count(reset_anchor) == 1
    code = code.replace(reset_anchor,
                        '\n'.join(f'    clearValue({name});' for name in fixture_globals)
                        + '\n' + reset_anchor)
    code = code.replace(
        'void gf_ESSerialKillerKill(int,int) { CHECK(false && "external lethal learning branch not simulated"); }',
        'void gf_ESSerialKillerKill(int a,int t) { lethalCalls.emplace_back(a,t); }')
    code = code.replace(
        'void Wait(double,int) { CHECK(false && "external lethal learning branch not simulated"); }',
        'void Wait(double duration,int clock) { CHECK(duration==0.1 && clock==c_timeGame); ++waits; }')
    code = code.replace(
        'template<class... T> void SoundPlayForPlayer(T...) { CHECK(false); }',
        'template<class... T> void SoundPlayForPlayer(T...) { ++deathSounds; }')
    code = code.replace('int main() {', TESTS + '\nint main() {\n    testAlliedNative(); testEligibility(); testSelfAndGuards();')
    return code


TESTS = r'''
bool panel(string name,int p) {
    return std::find(panelCalls.begin(),panelCalls.end(),std::make_pair(name,p))!=panelCalls.end();
}
void nativeReset(int a,int t,int faction,int pool,int role,int options) {
    reset("allied native matrix",a,t,faction,0,role);
    panelCalls.clear(); lethalCalls.clear(); waits=0; deathSounds=0;
    gv_roles[t][1]=pool;
    gv_gameStarted=true; gv_gameOver=false; gv_isNight=true;
    gv_bhFactionChatOpen=true; gv_currentPlayers=PlayerGroupAll();
    gv_dayNumber=3; gv_ysNights=3;
    // The other twelve players are not native setup candidates.
    gv_roles[2][1]=pool; gv_roles[2][0]=1;
    gv_roles[3][1]=pool; gv_roles[3][0]=2;
    gv_votes[a]=4; gv_activated[a]=true; gv_dayAction[a]=true;
    gv_disguised[a]=4; gv_pretended[a]=true; gv_jailing[a]=4;
    gv_lsUsed[a]=true; gv_lsTarget[a]=7; gv_lsDay[a]=2;
    gv_hlGangInitialized[a]=false; gv_hlNextNight[a]=30;
    gv_hlHouse[a][0]=7; gv_hlLeft[a][0]=1; gv_hlFaction[a][0]=5;
    gv_ysPierce[a]=true; gv_brReady[a]=true;
    gv_brFrozen=true; gv_brDone=true;
    for(int i=0;i<4;++i) gv_brRecruit[a][i]=7+i;
    gv_roleOptions[1][24][0]=options&1;
    gv_roleOptions[1][24][1]=options&2;
    gv_roleOptions[1][24][2]=options&4;
    for(int id:{6,11}) for(int i=1;i<=3;++i) gv_roleOptions[pool][id][i]=options&(1<<(i-1));
}
int expectedShots(int role,int options) {
    if(role==6) return (options&4)?3:(options&2)?2:(options&1)?1:-1;
    if(role==9 || role==15) return 1;
    if(role==11) return (options&2)?4:(options&1)?3:2;
    if(role==20) return 2;
    return -1;
}
void verifyFreshNative(int a,int t,int pool,int role,int options) {
    CHECK(gv_roles[a][1]==pool && gv_roles[a][0]==role);
    CHECK(gv_roles[t][1]==pool && gv_roles[t][0]==role);
    CHECK(gv_bhFaction[a]==0 && gf_BHFaction(a)==pool && !gf_BHConverted(a));
    CHECK(gv_originalRole[a][1]==1 && gv_originalRole[a][0]==24);
    CHECK(gv_originalRole[t][1]==1 && gv_originalRole[t][0]==1);
    CHECK(gf_BHRoleName(a)==gv_roleNameArray[pool][role]);
    CHECK(!gf_BHSpyActive(a) && gf_BHSeenFaction(a)==pool);
    CHECK(gv_shots[a]==expectedShots(role,options));
    CHECK(gv_shots[t]==17+t && gv_cooldown[t]==3);
    CHECK(gv_votes[a]==1 && gv_immuneChance[a]==0 && gv_cooldown[a]==0);
    CHECK(!gv_activated[a] && !gv_dayAction[a]);
    CHECK(gv_action[a][0]==0 && gv_action[a][1]==0);
    CHECK(gv_visitation[a]==t && gv_visitation2[a]==0);
    CHECK(gv_immune[a][0] && gv_immune[t][0] && gv_immuneChance[t]==4);
    for(int i=0;i<4;++i) CHECK(gv_variableOptions[a][i]==0);
    CHECK(gv_e4BB8AE6999AE58F98E8BAAB[a]==!(options&2));
    CHECK(!gv_janitized[a] && !gv_zuosi[a] && lethalCalls.empty() && waits==0);
    CHECK(refreshes==1 && panelCalls.empty()); // learning never invokes global/native night setup
    CHECK(renders==std::vector<std::tuple<int,int,int>>{{a,pool,role}});
    for(size_t row=0;row<std::size(gv_roleBoxText[a]);++row) CHECK(gv_roleBoxText[a][row]==rowText(pool,role,int(row)));
    CHECK(int(messages.size())==((options&1)?15:0));
    if(options&1) {
        CHECK(hasMessage(a,(options&2)?"B11B45D7":"A3C3B804"));
        CHECK(messages[0].value.find("PROF:"+std::to_string(pool)+":"+std::to_string(role))!=string::npos);
    }
    if(role==8) CHECK(gv_disguised[a]==0);
    if(role==9) CHECK(gv_jailing[a]==0);
    if(role==15) CHECK(!gv_pretended[a]);
    if(role==19) CHECK(!gv_ysPierce[a]);
    if(role==20) CHECK(gv_hlGangInitialized[a] && gv_hlNextNight[a]==0);
    if(role==21) CHECK(!gv_lsUsed[a] && gv_lsTarget[a]==0 && gv_lsDay[a]==0);
    if(role==22) {
        CHECK(!gv_brReady[a]);
        for(int i=0;i<4;++i) CHECK(gv_brRecruit[a][i]==0);
        CHECK(gv_brFrozen && gv_brDone && !gf_BRCanSelect(a));
    }
    // Learning must not erase traps already acting in the world or mentor state.
    CHECK(gv_hlHouse[a][0]==7 && gv_hlLeft[a][0]==1 && gv_hlFaction[a][0]==5);
    for(int p=1;p<=15;++p) if(p!=a) {
        CHECK(gv_shots[p]==17+p && gv_cooldown[p]==3 && gv_immuneChance[p]==4);
    }
}
void nextNativeSetup(int a,int pool,int role,int options) {
    panelCalls.clear(); visible.clear();
    gv_dayNumber=4;
    // Actual full night setup; NOT called by the apprenticeship helper itself.
    if(pool==2) gf_RSMafiaSetup2(); else gf_RSTriadSetup();
    CHECK(gv_roles[a][1]==pool && gv_roles[a][0]==role);
    CHECK(gv_shots[a]==expectedShots(role,options));
    CHECK(gv_originalRole[a][1]==1 && gv_originalRole[a][0]==24);
    CHECK(gv_immune[a][3]);
    if(role==6 || role==11) CHECK(gv_variableOptions[a][3]==1);
    if(role==10) CHECK(gv_variableOptions[a][3]==1 && gv_cooldown[a]==0);
    if(role==8 || role==15 || role==16 || role==20 || role==21 || role==22) CHECK(gv_variableOptions[a][0]==1);
    if(role==8) CHECK(panel(pool==2?"gf_RADisguiserActions":"gf_RAInformantActions",a));
    if(role==9) CHECK(gv_jailing[a]==0); // first kidnapping waits for real day selection
    if(role==12 || role==13) CHECK(panel("gf_RANoActions",a)); // native legacy no-op
    if(role==15) CHECK(panel(pool==2?"gf_RAPretenderActions":"gf_RAPretenderActions2",a));
    if(role==17) CHECK(panel("gf_BHLeaderSetup",a));
    if(role==19) CHECK(panel("gf_YSDraw",a));
    if(role==20) CHECK(panel("gf_RAForesterActions",a));
    if(role==21) CHECK(visible[{a,gv_actionDialogItem[15][5]}]);
    if(role==22) CHECK(panel("gf_BRDraw",a) && !gf_BRCanSelect(a));
}
void testAlliedNative() {
    for(int a:{1,8,15}) {
        int t=a==15?1:15;
        for(int pool:{2,5}) for(int role=1;role<=22;++role) for(int options=0;options<8;++options) {
            nativeReset(a,t,pool,pool,role,options);
            dispatchClick(a,t); dispatchPrep(a); messages.clear();
            dispatchLearning(a);
            verifyFreshNative(a,t,pool,role,options);
            nextNativeSetup(a,pool,role,options);
        }
    }
}
void testEligibility() {
    for(int f:{0,2,5}) for(int pool:{2,5}) for(int role=1;role<=22;++role) {
        nativeReset(8,15,f,pool,role,0);
        // Native mentors may carry a stale override, but it is not real membership.
        gv_bhFaction[15]=pool==2?5:2;
        dispatchClick(8,15); dispatchPrep(8); messages.clear(); dispatchLearning(8);
        if(f==pool) {
            CHECK(gv_roles[8][1]==pool && gv_roles[8][0]==role && lethalCalls.empty());
        }
        else {
            CHECK(gv_roles[8][1]==1 && gv_roles[8][0]==24 && gv_bhFaction[8]==f);
            CHECK(lethalCalls==std::vector<std::pair<int,int>>{{8,15}} && waits==1 && deathSounds==15);
            CHECK(gv_janitized[8]==1 && gv_zuosi[8]);
            CHECK(hasMessage(8,"77FE2FE0") && hasMessage(15,"8232D2F5"));
        }
    }
    for(int f:{2,5}) for(int role:{0,23,35}) {
        nativeReset(8,15,f,f,role,0);
        CHECK(!gf_BHApprenticeAllyLearn(8,15));
        CHECK(gv_roles[8][1]==1 && gv_roles[8][0]==24 && gv_bhFaction[8]==f);
    }
    // Pool 3 groups independent neutrals, not a supported convertible faction.
    for(int f:{0,2,3,5}) for(int role:{2,3,6,7,17}) {
        nativeReset(8,15,f,3,role,0);
        dispatchClick(8,15); dispatchPrep(8); messages.clear(); dispatchLearning(8);
        CHECK(gv_roles[8][1]==1 && gv_roles[8][0]==24 && gv_bhFaction[8]==f);
        CHECK(lethalCalls.empty() && hasMessage(8,"23328F9D"));
    }
    for(int f:{0,2,5}) {
        nativeReset(8,15,f,3,1,0);
        dispatchClick(8,15); dispatchPrep(8); messages.clear(); dispatchLearning(8);
        CHECK(gv_roles[8][1]==1 && gv_roles[8][0]==24);
        CHECK(lethalCalls==std::vector<std::pair<int,int>>{{8,15}} && waits==1 && deathSounds==15);
    }
}
void testSelfAndGuards() {
    for(int f:{0,2,5}) {
        nativeReset(8,15,f,2,22,0);
        CHECK(!gf_BHApprenticeAllyLearn(8,8));
        CHECK(!gf_BHApprenticeAllyLearn(0,15) && !gf_BHApprenticeAllyLearn(16,15));
        CHECK(!gf_BHApprenticeAllyLearn(8,0) && !gf_BHApprenticeAllyLearn(8,16));
        gv_visitation[8]=8; dispatchLearning(8);
        CHECK(gv_roles[8][0]==24 && gv_shots[8]==25 && renders.empty());
        gv_visitation[8]=15; gv_diedAtNight[8]=true; dispatchLearning(8);
        CHECK(gv_roles[8][0]==24 && gv_roles[8][1]==1 && renders.empty());
        gv_diedAtNight[8]=false; gv_roles[8][1]=2;
        CHECK(!gf_BHApprenticeAllyLearn(8,15));
        dispatchLearning(8); CHECK(gv_roles[8][0]==24 && renders.empty());
    }
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    source = args.script.read_text(encoding='utf-8')
    print(f'Actual source: {args.script}', flush=True)
    code = harness(source)
    with tempfile.TemporaryDirectory(prefix='bh-apprentice-allies-') as tmp:
        cpp, exe = Path(tmp) / 'allies.cpp', Path(tmp) / 'allies'
        cpp.write_text(code, encoding='utf-8')
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)

    print('PASS: additional allied native 2/5 x roles 1..22 x eight options; actual next-night native dispatch; originalRole retained; legacy-body SHA256 unchanged', flush=True)
    print('BOUNDARY: panel/engine/channel doubles and hostile-attack call recording; native attacks, global succession, SC2 compiler/rendering not simulated', flush=True)


if __name__ == '__main__':
    main()
