#!/usr/bin/env python3
"""Actual first-day Baron/Taido panel + complete ability event, UBSan/bounds.

Extends the real-helper/conversion harness in memory. Panel Build/Refresh/Open,
DayButtons, both real panel event phases, actual Init and the COMPLETE shared
ability-button handler execute. Unrelated profession ability leaves fail fast;
UI objects, event delivery, rendering and channel transport are recording engine
doubles, not a reimplementation of panel selection or recruitment policy.

Fixtures enter at the first-day/next-night boundary; actual owning functions are
checked for callback/lifecycle order, but full SC2 scheduling is not executed.
No SC2 compiler, rendering, multiplayer, GUI timing or bank claim is made.
--negative-tests mutates Galaxy IN MEMORY and rejects wrong windows/commits,
previous-night vetoes, lost Triad authority, early commits and privacy leaks by
actual business assertions. No production file is changed.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import test_baron_leaders as baron
from test_egun import SCRIPT, function, mask, translate

ABILITY_BOUNDARIES = {
    'gf_ZCOpenPicker', 'gf_SKY_1_yujing', 'gf_SKY_1_shizhang', 'gf_SQReveal',
    'gf_SKY_1_gonggaoyuan', 'gf_SKY_1_zhengmuguan', 'gf_SKY_1_zhifazhang',
    'gf_FZLooksLike', 'gf_SKY_3_shenjiguan', 'gf_SKY_3_cuanweizhe',
    'gf_SKY_3_faguan', 'gf_SKY_3_shenjiguan_2', 'gf_TTAdjourn', 'gf_JSArm',
}


def harness(source: str) -> str:
    base = baron.harness(source)
    base = base.replace(function(base, 'main'), '')
    names = baron.core.with_guoke_dependencies(source, ('gt_ASAbilityButton_Func',))
    existing = set(re.findall(r'^(?:void|bool|int|text)\s+(\w+)\s*\([^;{}]*\)\s*\{', base, re.M))
    bodies = [function(source, name) for name in names if name not in existing]
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    ability = '\n\n'.join(bodies)
    used = set(re.findall(r'\bgv_\w+', mask(ability))) - set(re.findall(r'\bgv_\w+', base))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not used - declarations.keys(), ('missing actual ability-event globals', used - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(used))
    resets = '\n'.join(f'    clearValue({name});' for name in sorted(used))
    calls = baron.core.calls(ability)
    unknown = calls - baron.core.calls(base) - ABILITY_BOUNDARIES - set(names) - {
        'TriggerIsEnabled', 'DialogControlIsVisible', 'DialogControlCreate',
    }
    assert not unknown, ('new shared ability boundary must be reviewed', unknown)
    stubs = []
    for name in sorted(calls & ABILITY_BOUNDARIES):
        header = function(source, name).split('{', 1)[0].strip()
        result = '' if header.startswith('void ') else ' return false;'
        stubs.append(header + ' { CHECK(false && "unrelated daytime ability boundary");' + result + ' }')

    constants = sorted(set(re.findall(r'\b(?:c_|ge_)\w+', mask(ability))) - set(re.findall(r'\b(?:c_|ge_)\w+', base)))
    constants_text = '\n'.join(f'constexpr int {name}={index};' for index, name in enumerate(constants, 100))
    ability = translate(ability)
    ability = re.sub(r'\bnull\b', '0', ability)
    ability = re.sub(r'^(\s+(?:int|bool|playergroup)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', ability, flags=re.M)
    assert 'gf_BRPanelOpen(EventPlayer());' in ability
    assert 'gf_BRDayButtons();' in mask(function(source, 'gf_ASStartVote'))
    assert 'gf_ASStartVote();' in mask(function(source, 'gf_TXResumeDay'))
    assert 'gf_BRPanelCloseAll();' in mask(function(source, 'gf_ASStopVote'))
    assert 'gt_BRPanel_Init();' in mask(function(source, 'gt_BRRecruit_Init')), 'real registered recruit init must also register the panel event'
    print('PASS actual day-panel/ability bodies, registration and resume/close wiring; unrelated profession branches are explicit fail-fast boundaries', flush=True)
    return base + '\n' + globals_text + '\n' + constants_text + r'''
trigger gt_Type=0;
void DialogControlCreate(int dialog,int type) {
    CHECK(type==c_triggerControlTypeButton);
    createControl(dialog,0,0,0,0,0,"button");
}
bool TriggerIsEnabled(trigger) { return true; }
bool DialogControlIsVisible(int item,int player) {
    CHECK(player>=1 && player<=15);
    return uiVisible[{player,item}];
}
''' + '\n'.join(stubs) + '\n' + headers + '\n' + ability + r'''
void panelReset(const string& label,int pool=2,bool start=true) {
    brReset(label,pool,start);
''' + resets + r'''
}
bool panelEvent(int player,int control,bool run=true) {
    eventPlayer=player; eventControl=control;
    return gt_BRPanel_Func(true,run);
}
bool abilityEvent(int player,int control,bool run=true) {
    eventPlayer=player; eventControl=control;
    return gt_ASAbilityButton_Func(true,run);
}
template<class A,class B> void appendValue(string& out,const std::pair<A,B>& value) {
    appendValue(out,value.first); appendValue(out,value.second);
}
template<class T,size_t N> void appendValue(string& out,const std::array<T,N>& value) {
    for(const auto& item:value) appendValue(out,item);
}
string privateUI(int player) {
    string result;
    auto append=[&](const auto& map) {
        for(const auto& entry:map) if(entry.first.first==player) {
            appendValue(result,entry.first.second); appendValue(result,entry.second);
        }
    };
    append(uiText); append(uiTooltip); append(uiColor); append(uiVisible);
    append(uiEnabled); append(uiDialogVisible); append(uiSize); append(uiPosition);
    return result;
}
void privateWrites(int player) {
    for(const auto& write:uiWrites) CHECK(write.group==(1u<<player));
    for(const auto& message:messages) CHECK(message.target==player);
}
void openBySkill(int player) {
    CHECK(abilityEvent(player,gv_abilityButtonItem));
    CHECK(DialogIsVisible(gv_brPanel,player));
}
void setupAndRegistration() {
    panelReset("actual panel Init registers real callback and generic dialog event");
    gt_BRRecruit_Init();
    CHECK(gt_BRPanel!=gt_BRRecruit);
    CHECK(triggerNames[gt_BRPanel]=="gt_BRPanel_Func");
    CHECK(registeredCommands==std::vector<string>({"-recruit","-pair","-puppet"}));
    CHECK(registeredDialogEvents.size()==2);
    CHECK(registeredDialogEvents[0]==std::array<int,4>{gt_BRPanel,c_playerAny,c_invalidDialogControlId,c_triggerControlEventTypeClick});
    CHECK(registeredDialogEvents[1]==std::array<int,4>{gt_GKPanel,c_playerAny,c_invalidDialogControlId,c_triggerControlEventTypeClick});
    gf_BRPanelBuild(); CHECK(dialogs.size()==1);
    CHECK(dialogs[gv_brPanel].width==900 && dialogs[gv_brPanel].height==470);
    CHECK(!dialogs[gv_brPanel].modal && !dialogs[gv_brPanel].image);
    CHECK(dialogs[gv_brPanel].priority==800);
    const auto count=controls.size(); const int panel=gv_brPanel;
    gf_BRPanelBuild(); CHECK(controls.size()==count && gv_brPanel==panel);
    for(int p=1;p<=15;++p) {
        CHECK(!DialogIsVisible(panel,p));
        CHECK(controls[gv_brPanelButton[p]].parent==panel);
        CHECK(controls[gv_brPanelButton[p]].width==278 && controls[gv_brPanelButton[p]].height==44);
        CHECK(!uiVisible[{1,gv_brPanelButton[p]}]);
        for(int q=p+1;q<=15;++q) CHECK(gv_brPanelButton[p]!=gv_brPanelButton[q]);
    }
    CHECK(!abilityEvent(1,123456));
    CHECK(abilityEvent(1,gv_abilityButtonItem,false));
    CHECK(!DialogIsVisible(panel,1));
    openBySkill(1); CHECK(hasMessage(1,"BRFIRST"));
}
void matrixDayPanel() {
    for(bool start:{false,true}) for(int pool:{2,5}) for(int cap:{2,3,4}) for(int actor:{1,8,15}) {
        panelReset("both start modes/pools/caps/edge seats: skill -> actual picker -> entry commit",pool,start);
        role(1,1,1); role(actor,pool,22); setRecruitCap(pool,cap);
        CHECK(gf_BRFirstDay()==(start?1:2));
        gf_BRDayButtons(); CHECK(uiEnabled[{actor,gv_abilityButtonItem}]);
        gf_BRPanelBuild();
        string other[16]; for(int p=1;p<=15;++p) if(p!=actor) other[p]=privateUI(p);
        uiWrites.clear(); clearEffects();
        openBySkill(actor); privateWrites(actor);
        CHECK(hasMessage(actor,pool==2?"BRFIRST":"BRFIRST5"));
        for(int p=1;p<=15;++p) if(p!=actor) CHECK(privateUI(p)==other[p]);
        CHECK(!uiVisible[{actor,gv_brPanelButton[actor]}]);
        std::vector<int> targets;
        for(int target=1;target<=15 && int(targets.size())<cap;++target) if(target!=actor) targets.push_back(target);
        const string profession=professionState();
        for(int target:targets) {
            CHECK(uiVisible[{actor,gv_brPanelButton[target]}]);
            const int spot=gv_playerSpot[target], row=(spot-1)/3, col=(spot-1)%3;
            CHECK(uiPosition[{actor,gv_brPanelButton[target]}]==std::array<int,3>{c_anchorTopLeft,24+286*col,144+48*row});
            CHECK(uiText[{actor,gv_brPanelButton[target]}].find(std::to_string(spot)+". ")!=string::npos);
            CHECK(uiText[{actor,gv_brPanelButton[target]}].find(gv_name[target])!=string::npos);
            CHECK(panelEvent(actor,gv_brPanelButton[target]));
            CHECK(gf_BHFaction(target)==1 && professionState()==profession);
            CHECK(uiColor[{actor,gv_brPanelButton[target]}]==Color(0.0,45.0,0.0));
            CHECK(uiText[{actor,gv_brPanelButton[target]}].find("● ")==0);
        }
        CHECK(recruits(actor)==targets && gf_BRCount(actor)==cap);
        CHECK(uiText[{actor,gv_brPanelCount}]==StringExternal("Param/Value/BRPANELCOUNT")+std::to_string(cap)+"/"+std::to_string(cap));
        int extra=15; while(extra==actor || std::find(targets.begin(),targets.end(),extra)!=targets.end()) --extra;
        CHECK(panelEvent(actor,gv_brPanelButton[extra])); CHECK(recruits(actor)==targets);
        CHECK(panelEvent(actor,gv_brPanelButton[targets.back()])); CHECK(gf_BRCount(actor)==cap-1);
        CHECK(panelEvent(actor,gv_brPanelButton[targets.back()])); CHECK(recruits(actor)==targets);
        CHECK(panelEvent(actor,gv_brPanelClose)); CHECK(!DialogIsVisible(gv_brPanel,actor));
        CHECK(recruits(actor)==targets);
        CHECK(!panelEvent(actor,gv_brPanelButton[extra])); CHECK(recruits(actor)==targets);
        openBySkill(actor); CHECK(recruits(actor)==targets);
        for(int p=1;p<=15;++p) if(p!=actor) CHECK(privateUI(p)==other[p]);
        CHECK(professionState()==profession && !gv_brFrozen && !gv_brDone);
        gf_BRPanelCloseAll(); CHECK(recruits(actor)==targets);
        commitAtNightEntry();
        for(int target:targets) CHECK(gf_BHFaction(target)==pool && gv_roles[target][1]==1);
        CHECK(gv_brDone && recruits(actor).empty() && professionState()==profession);
        nightActions(); gf_BHRefreshFactionChat();
        for(int target:targets) CHECK(channels[target]==(pool==2?1:4));
        const string committed=baronState(); clearEffects(); gf_BRResolveRecruit();
        CHECK(baronState()==committed && events.empty());
    }
}
void privateTwoLeadersAndHiddenFactions() {
    panelReset("two simultaneous private dialogs carry disjoint selections/styles");
    role(15,5,22); setRecruitCap(2,2); setRecruitCap(5,4);
    gf_BRPanelBuild(); openBySkill(1); CHECK(panelEvent(1,gv_brPanelButton[8]));
    const string first=privateUI(1); const auto firstPending=recruits(1);
    uiWrites.clear(); clearEffects(); openBySkill(15); privateWrites(15);
    CHECK(panelEvent(15,gv_brPanelButton[4]));
    CHECK(privateUI(1)==first && recruits(1)==firstPending);
    CHECK(recruits(15)==std::vector<int>{4});
    CHECK(uiColor[{1,gv_brPanelButton[8]}]==Color(0,45,0));
    CHECK(uiColor[{15,gv_brPanelButton[8]}]==Color(63.53,57.25,80.00));
    CHECK(panelEvent(15,gv_brPanelClear)); CHECK(recruits(15).empty() && recruits(1)==firstPending);
    CHECK(!uiEnabled[{15,gv_brPanelClear}]);
    for(int i=0;i<4;++i) gv_brRecruit[15][i]=i+2;
    CHECK(panelEvent(15,gv_brPanelClear)); for(int i=0;i<4;++i) CHECK(gv_brRecruit[15][i]==0);

    string reference;
    for(int pool:{1,2,3,5}) for(int id:{1,4,17,22,28,29,33,35}) {
        panelReset("picker must not reveal hidden profession/faction before commit");
        role(8,pool,id); gf_BRPanelBuild(); openBySkill(1); clearEffects();
        const string initial=privateUI(1);
        CHECK(panelEvent(1,gv_brPanelButton[8])); CHECK(recruits()==std::vector<int>{8});
        string response=initial+privateUI(1);
        for(const auto& message:messages) { CHECK(message.target==1); appendValue(response,message.value); }
        if(reference.empty()) reference=response; else CHECK(response==reference);
        CHECK(gf_BHFaction(8)==pool && !gv_brDone);
    }
}
void callbackGuardsAndResume() {
    for(int guard=0;guard<17;++guard) {
        panelReset("visible stale panel event must recheck authority");
        gf_BRPanelBuild(); openBySkill(1); CHECK(panelEvent(1,gv_brPanelButton[8]));
        const auto pending=recruits();
        if(guard==0) gv_isNight=true;
        if(guard==1) ++gv_dayNumber;
        if(guard==2) gv_dayOver=true;
        if(guard==3) gv_dayActions=false;
        if(guard==4) gv_trialOn=true;
        if(guard==5) gv_onTrial=8;
        if(guard==6) gv_gameOver=true;
        if(guard==7) gv_gameStarted=false;
        if(guard==8) gv_brFrozen=true;
        if(guard==9) gv_brDone=true;
        if(guard==10) gv_jailed[1]=8;
        if(guard==11) gv_bhFeignRole[1]=22;
        if(guard==12) gv_alivePlayers&=~(1u<<1);
        if(guard==13) gv_currentPlayers&=~(1u<<1);
        if(guard==14) role(1,1,1);
        if(guard==15) gv_nightProcessingPhase=true;
        if(guard==16) role(1,2,21);
        CHECK(!panelEvent(1,gv_brPanelClear,false));
        CHECK(recruits()==pending && DialogIsVisible(gv_brPanel,1));
        CHECK(!panelEvent(1,gv_brPanelClear));
        CHECK(recruits()==pending && !DialogIsVisible(gv_brPanel,1));
    }
    panelReset("close remains legal when authority expires; query phase does not close");
    openBySkill(1); commandTargets({8}); gv_alivePlayers&=~(1u<<1);
    CHECK(panelEvent(1,gv_brPanelClose,false)); CHECK(DialogIsVisible(gv_brPanel,1));
    CHECK(panelEvent(1,gv_brPanelClose)); CHECK(!DialogIsVisible(gv_brPanel,1) && recruits()==std::vector<int>{8});

    panelReset("real callback rejects unknown controls, other players and invalid ids");
    openBySkill(1); const string before=baronState();
    for(int player:{0,-1,16}) CHECK(!panelEvent(player,gv_brPanelClear));
    CHECK(!panelEvent(1,123456)); CHECK(!panelEvent(8,gv_brPanelButton[4]));
    CHECK(baronState()==before);
    CHECK(panelEvent(1,gv_brPanelButton[8],false)); CHECK(recruits().empty());
    CHECK(panelEvent(1,gv_brPanelButton[8])); CHECK(recruits()==std::vector<int>{8});
    CHECK(!panelEvent(1,gv_brPanelButton[1])); // Self cannot be a recruit.
    gv_alivePlayers&=~(1u<<8); CHECK(!panelEvent(1,gv_brPanelButton[8]));
    CHECK(!uiVisible[{1,gv_brPanelButton[8]}]); CHECK(recruits()==std::vector<int>{8});

    panelReset("trial hides panel and disables button; normal/TX vote resume restores only skill");
    openBySkill(1); commandTargets({8});
    gv_trialOn=true; gf_BRDayButtons();
    CHECK(!uiEnabled[{1,gv_abilityButtonItem}] && !DialogIsVisible(gv_brPanel,1));
    CHECK(recruits()==std::vector<int>{8});
    gv_trialOn=false; gv_onTrial=0; gf_BRDayButtons();
    CHECK(uiEnabled[{1,gv_abilityButtonItem}] && !DialogIsVisible(gv_brPanel,1));
    openBySkill(1); CHECK(recruits()==std::vector<int>{8});
    gv_dayOver=true; gf_BRPanelCloseAll(); CHECK(recruits()==std::vector<int>{8});
}
void compatibilityCommandRefresh() {
    panelReset("compatibility chat edits the same private pending list without opening/converting");
    openBySkill(1); commandTargets({8,4});
    CHECK(recruits()==std::vector<int>({8,4}));
    CHECK(uiText[{1,gv_brPanelCount}]==StringExternal("Param/Value/BRPANELCOUNT")+"2/3");
    for(int p:{8,4}) {
        CHECK(uiColor[{1,gv_brPanelButton[p]}]==Color(0,45,0));
        CHECK(gf_BHFaction(p)==1);
    }
    commandTargets({}); CHECK(recruits().empty());
    CHECK(uiText[{1,gv_brPanelCount}]==StringExternal("Param/Value/BRPANELCOUNT")+"0/3");
    CHECK(!uiEnabled[{1,gv_brPanelClear}]);
    CHECK(panelEvent(1,gv_brPanelClose));
    commandTargets({15}); CHECK(recruits()==std::vector<int>{15});
    CHECK(!DialogIsVisible(gv_brPanel,1) && !gv_brDone);
    openBySkill(1); CHECK(recruits()==std::vector<int>{15});
    CHECK(panelEvent(1,gv_brPanelClear,false)); CHECK(recruits()==std::vector<int>{15});
    CHECK(panelEvent(1,gv_brPanelClear)); CHECK(recruits().empty());
}
void fakePanelAndInvalidSpots() {
    for(int pool:{2,5}) for(bool start:{false,true}) {
        panelReset("FZ fake first-day panel never obtains real recruitment authority",pool,start);
        role(1,1,33); gv_fzPool[1]=pool; gv_fzRole[1]=22;
        CHECK(gf_BRFake(1) && !gf_BRIs(1)); openBySkill(1);
        CHECK(panelEvent(1,gv_brPanelButton[8])); CHECK(recruits()==std::vector<int>{8});
        CHECK(gv_roles[1][1]==1 && gv_roles[1][0]==33 && !gv_immune[1][0]);
        commitAtNightEntry(); CHECK(gf_BHFaction(8)==1 && recruits().empty());
    }
    for(int spot:{-1,0,16,999}) {
        panelReset("malformed seat falls back to target id; no panel indexing by seat");
        gv_playerSpot[8]=spot; openBySkill(1);
        CHECK(uiPosition[{1,gv_brPanelButton[8]}]==std::array<int,3>{c_anchorTopLeft,24+286,144+48*2});
        CHECK(uiText[{1,gv_brPanelButton[8]}].find("8. ")!=string::npos);
    }
    panelReset("night-first N1 cannot open/select/freeze/resolve before first daytime",2,false);
    gv_dayNumber=1; nightActions(); gf_BRDayButtons();
    CHECK(!uiEnabled[{1,gv_abilityButtonItem}]);
    gf_BRPanelOpen(1); CHECK(gv_brPanel==0);
    commandTargets({8}); gf_BRFreezeRecruit(); gf_BRResolveRecruit();
    CHECK(!gv_brDone && !gv_brFrozen && recruits().empty());
}
int main() {
    setupAndRegistration(); matrixDayPanel(); privateTwoLeadersAndHiddenFactions();
    callbackGuardsAndResume(); compatibilityCommandRefresh(); fakePanelAndInvalidSpots();
    // Keep the entire pre-existing runtime suite alive in the same executable.
    testSlotReplacement(); testLeaderRandomMasks(); testRandomTown(); testSelectionAndCommand();
    testRecruitCaps(); testLeaderIdentity(); testClosedWindows(); testClaim();
    testFreezeAndResolve(); testUIAndReset();
    std::cout << "PASS first-day panel + whole ability event: " << fixtures << " fixtures, " << checks
              << " assertions; actual helpers/conversion; UBSan/bounds; recording UI/engine boundaries\n";
}
'''


def replace_body(source: str, name: str, old: str, new: str) -> str:
    body = function(source, name)
    assert body.count(old) == 1, ('mutation adapter changed', name, old)
    changed = body.replace(old, new)
    assert source.count(body) == 1
    return source.replace(body, changed)


def mutants(source: str) -> dict[str, str]:
    result = {
        'first-day-always-one': replace_body(source, 'gf_BRFirstDay', 'return 2;', 'return 1;'),
        'reopen-second-day': replace_body(source, 'gf_BRCanSelect', '(gv_dayNumber == gf_BRFirstDay())', 'true'),
        'night-only-selection': replace_body(source, 'gf_BRCanSelect', '(gv_isNight == false)', '(gv_isNight == true)'),
        'wait-for-later-night': replace_body(source, 'gf_BRResolveRecruit', '(gv_isNight == true)', '(gv_isNight == false)'),
        'previous-night-block-veto': replace_body(source, 'gf_BRFreezeRecruit', '(gv_jailed[lv_a] == 0)', '(gv_jailed[lv_a] == 0) && (gv_roleblocked[lv_a] == 0)'),
        'previous-night-death-veto': replace_body(source, 'gf_BRFreezeRecruit', '(gv_jailed[lv_a] == 0)', '(gv_jailed[lv_a] == 0) && (gv_diedAtNight[lv_a] == false)'),
        'mafia-only-commit': replace_body(source, 'gf_BRResolveRecruit', '(gf_BRIs(lv_a) == true)', '(gf_BRIs(lv_a) == true) && (gv_roles[lv_a][1] == 2)'),
        'open-commits-early': replace_body(source, 'gf_BRPanelOpen', '    gf_BRPanelBuild();', '    gf_BRFreezeRecruit();\n    gf_BRResolveRecruit();\n    gf_BRPanelBuild();'),
    }
    body = function(source, 'gf_BRPanelRefresh')
    assert 'PlayerGroupSingle(lp_player)' in body
    result['public-panel-refresh'] = source.replace(body, body.replace('PlayerGroupSingle(lp_player)', 'PlayerGroupAll()'))
    return result


def run(source: str, directory: Path, label: str, cxx: str) -> subprocess.CompletedProcess[str]:
    code = harness(source)
    cpp, binary = directory / f'{label}.cpp', directory / label
    cpp.write_text(code)
    warnings = ['-Wno-parentheses-equality'] if 'clang' in cxx else []
    subprocess.run([cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                    '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                    str(cpp), '-o', str(binary)], check=True)
    return subprocess.run([str(binary)], capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--negative-tests', action='store_true')
    args = parser.parse_args()
    source = args.script.read_text()
    with tempfile.TemporaryDirectory(prefix='bh-baron-day-panel-') as directory:
        result = run(source, Path(directory), 'actual', args.cxx)
        print(result.stdout, end='')
        if result.returncode:
            raise SystemExit(result.stderr or result.returncode)

        if args.negative_tests:
            for label, changed in mutants(source).items():
                result = run(changed, Path(directory), label, args.cxx)
                assert result.returncode != 0 and 'FAIL [' in result.stderr, (
                    'mutant not rejected by a business assertion', label,
                    result.returncode, result.stdout, result.stderr)
                print(f'PASS negative {label}: {result.stderr.strip()}')

    print('Boundary: real local bodies/events + owning-source ordering; no full SC2 scheduler/render/runtime claim.')


if __name__ == '__main__':
    main()
