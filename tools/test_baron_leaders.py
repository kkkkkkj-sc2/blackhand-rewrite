#!/usr/bin/env python3
"""Execute actual Baron/Taido Galaxy helpers with UBSan and bounds checking.

Extends test_faction_conversion's harness in memory, never edits that suite or
production Galaxy. Recruitment, command parsing, slot replacement, knife claim,
and the existing conversion API are extracted whole, not reimplemented. Engine
randomness and UI are explicit doubles. Lifecycle call ordering is checked in
actual owning functions; the enormous DayTransition/SC2 revive presentation is
not simulated. A late revival fixture changes engine membership between actual
Freeze and Resolve calls. This is not an SC2 compiler/rendering/timing test.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import test_faction_conversion as core
from test_egun import SCRIPT, function, mask, translate

REQUIRED = {
    'gf_BRIs', 'gf_BRRandomTown', 'gf_BRReplaceSlots', 'gf_BRReset',
    'gf_BRCanSelect', 'gf_BRSelectable', 'gf_BRCount', 'gf_BRList',
    'gf_BRDraw', 'gf_BRSetup', 'gf_BRClick', 'gf_BRClaim',
    'gf_BRFreezeRecruit', 'gf_BRResolveRecruit',
}
VISITS = ('gf_BHVisit', 'gf_BHVisit2', 'gf_BHVisitNone', 'gf_BHVisitSelf')


def integration(source: str) -> tuple[str, ...]:
    live = mask(source)
    names = set(re.findall(r'^(?:void|bool|int|text)\s+(gf_BR\w+)\s*\([^;{}]*\)\s*\{', live, re.M))
    assert REQUIRED <= names, ('missing Baron helper definitions', REQUIRED - names)
    for name in ('gv_brRecruit', 'gv_brReady', 'gv_brFrozen', 'gv_brDone'):
        declaration = re.search(r'^\w+(?:\[\d+\])*\s+' + name + r'\s*(?:=[^;]*)?;', live, re.M)
        assert declaration, ('missing actual declaration', name)
        assert declaration.start() + declaration[0].index(name) == live.index(name), ('global used before declaration', name)

    assert re.search(r'^int\[16\]\[3\]\s+gv_brRecruit\s*;', live, re.M)
    assert re.search(r'^bool\[16\]\s+gv_brReady\s*;', live, re.M)
    assert re.search(r'^trigger\s+gt_BRRecruit\s*;', live, re.M)
    for name in names | {'gt_BRRecruit_Func', 'gt_BRRecruit_Init'}:
        header = function(source, name).split('{', 1)[0].strip()
        assert header + ';' in source, ('missing forward declaration', name)

    setup = mask(function(source, 'auto_gf_OSComputeOptions_TriggerFunc'))
    assert setup.index('gf_OSRandomize();') < setup.index('gf_BRReplaceSlots();') < setup.index('lv_bhPreferSlot[lv_a] = 0;'), 'replace final slots before preference binding and profession setup'
    assert 'gf_BRReset();' in mask(function(source, 'gf_InitializeVariables')), 'new-game reset not wired'
    prep = mask(function(source, 'gf_SequencePrep'))
    for pool in (2, 5):
        assert re.search(r'gf_YSClaim\(' + str(pool) + r'\);\s*gf_BRClaim\(' + str(pool) + r'\);', prep), ('knife claim must follow legacy faction claim', pool)

    day = mask(function(source, 'auto_gf_DayTransition_TriggerFunc'))
    clear = day.index('gf_CBClearChat(autoE5ABDFBB_var);')
    freeze, jail = day.index('gf_BRFreezeRecruit();'), day.index('gv_jailed[lv_a] = 0;')
    revive, resolve, end = day.index('gf_JJResolve();'), day.index('gf_BRResolveRecruit();'), day.index('gf_CheckEnd()')
    assert day.index('gv_nightProcessingPhase = false;') < clear < freeze < jail < revive < resolve < end, 'freeze before jail reset, resolve AFTER late revival, before first dawn CheckEnd'
    assert len(re.findall(r'\bgf_BRFreezeRecruit\(', day)) == 1
    assert len(re.findall(r'\bgf_BRResolveRecruit\(', day)) == 1

    init = function(source, 'gt_BRRecruit_Init')
    assert 'TriggerCreate("gt_BRRecruit_Func")' in init
    assert re.search(r'TriggerAddEventChatMessage\(gt_BRRecruit,\s*c_playerAny,\s*"-recruit",\s*false\)', init)
    assert re.search(r'^\s+gt_BRRecruit_Init\(\);', live, re.M), 'new chat event not initialized'
    command = mask(function(source, 'gt_BRRecruit_Func'))
    assert 'c_bhSoloBuild' not in command, 'real role command must work in non-solo packages'
    assert 'gf_BHConvertFaction' not in command, 'command may only change pending selection'
    resolve_body = mask(function(source, 'gf_BRResolveRecruit'))
    assert 'gf_BHConvertFaction' in resolve_body, 'resolve must use guarded public conversion API'
    for name in names - {'gf_BRClaim', 'gf_BRResolveRecruit'}:
        body = mask(function(source, name))
        assert not re.search(r'\b(?:gf_BHConvertFaction|gf_ESMafiaKill|gf_ESTriadKill|gf_BHLeaderNight)\s*\(', body), ('unexpected immediate conversion or duplicate kill', name)
    selectable = mask(function(source, 'gf_BRSelectable'))
    assert not re.search(r'\b(?:gf_BHFaction|gv_bhFaction|gv_roles|gv_fzPool)\b', selectable), 'click eligibility must not reveal hidden faction/profession'
    assert not re.search(r'\bgv_(?:visitation2?|location)\b', resolve_body), 'non-visiting recruitment must not depend on attack visitation'
    print('PASS wiring: slot replacement before binding; reset; both knife claims; freeze before jail reset; JJ revival before resolve before CheckEnd; registered production command', flush=True)
    return tuple(sorted(names)) + ('gt_BRRecruit_Func', 'gt_BRRecruit_Init', 'gf_BHPickLeader') + VISITS


def harness(source: str) -> str:
    names = integration(source)
    base = core.harness(source)
    base = base.replace(function(base, 'main'), '')
    bodies = [function(source, name) for name in names]
    raw = '\n\n'.join(bodies)
    used = set(re.findall(r'\bgv_\w+', mask(raw))) | {
        'gv_semifinalRole', 'gv_roleWeights', 'gv_roleNameArray', 'gv_townMax',
        'gv_immune', 'gv_variableOptions', 'gv_actionDialogItem', 'gv_dayNumber',
        'gv_mafiaHitman', 'gv_mafiaTarget', 'gv_triadHitman', 'gv_triadTarget',
        'gv_fzPool', 'gv_fzRole', 'gv_diedAtNight', 'gv_bhPickPool', 'gv_bhPickRole',
    }
    needed = sorted(used - set(re.findall(r'\bgv_\w+', base)))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not set(needed) - declarations.keys(), ('missing globals', set(needed) - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in needed)
    resets = '\n'.join(f'    clearValue({name});' for name in needed)
    snapshots = '\n'.join(f'    appendValue(result, {name});' for name in needed)
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    code = translate(raw)
    code = re.sub(r'\bnull\b', 'text{}', code)
    code = re.sub(r'^(\s+(?:int|bool|fixed|text|string|playergroup)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', code, flags=re.M)

    # Replace only presentation doubles in the generated core; never production.
    replacements = {
        'libNtve_gf_SetDialogItemText': 'void libNtve_gf_SetDialogItemText(int item,text value,playergroup group) { for(int p=1;p<=15;++p) if(group&(1u<<p)) uiText[{p,item}]=value; }',
        'TriggerAddEventChatMessage': 'void TriggerAddEventChatMessage(trigger handle,int player,string command,bool exact) { CHECK(handle==701 && player==c_playerAny && !exact); registeredCommands.push_back(command); }',
    }
    for name, replacement in replacements.items():
        if name.startswith('libNtve_'):
            old = 'template<class... T> void ' + name + '(T...) {}'
        else:
            old = function(base, name)

        assert base.count(old) == 1, ('presentation replacement anchor', name)
        base = base.replace(old, replacement)

    constants = sorted(set(re.findall(r'\b(?:c_|ge_)\w+', mask(raw))) - set(re.findall(r'\b(?:c_|ge_)\w+', base)))
    constants_text = '\n'.join(f'constexpr int {name}={index};' for index, name in enumerate(constants, 10))
    boundary = r'''
std::map<std::pair<int,int>,text> uiText;
std::map<std::pair<int,int>,int> uiColor;
std::map<std::pair<int,int>,bool> uiVisible;
std::map<std::pair<int,int>,std::pair<int,int>> uiSize;
std::vector<string> registeredCommands;
std::mt19937 brRng(13682);
int randomCalls=0;
'''
    base = base.replace('struct Message {', boundary + '\nstruct Message {', 1)
    extension = r'''
''' + globals_text + '\n' + constants_text + r'''
using color = int;
trigger gt_BRRecruit=0;
fixed forcedRandomFraction=-1;
int RandomInt(int lo,int hi) { CHECK(lo<=hi); ++randomCalls; return std::uniform_int_distribution<int>(lo,hi)(brRng); }
fixed RandomFixed(fixed lo,fixed hi) {
    CHECK(lo<=hi); ++randomCalls;
    if(forcedRandomFraction>=0) return lo+(hi-lo)*forcedRandomFraction;
    return lo==hi?lo:std::uniform_real_distribution<fixed>(lo,hi)(brRng);
}
int StringLength(string value) { return int(value.size()); }
string StringCase(string value,bool upper) { for(char& c:value) c=upper?std::toupper((unsigned char)c):std::tolower((unsigned char)c); return value; }
string StringSub(string value,int start,int end) { CHECK(start>=1); if(end<start || start>int(value.size())) return ""; return value.substr(start-1,end-start+1); }
void DialogControlSetVisible(int item,playergroup group,bool show) { for(int p=1;p<=15;++p) if(group&(1u<<p)) uiVisible[{p,item}]=show; }
void DialogControlSetSize(int item,playergroup group,int width,int height) { for(int p=1;p<=15;++p) if(group&(1u<<p)) uiSize[{p,item}]={width,height}; }
void libNtve_gf_SetDialogItemColor(int item,int color,playergroup group) { for(int p=1;p<=15;++p) if(group&(1u<<p)) uiColor[{p,item}]=color; }
template<class... T> void DialogControlSetPosition(T...) {}
template<class... T> void libNtve_gf_SetDialogItemTooltip(T...) {}
template<class... T> void gf_CBHighlightText(T...) {}
void gf_RANoActions(int p) { for(int t=1;t<=15;++t) for(int slot:{5,6}) uiVisible[{p,gv_actionDialogItem[t][slot]}]=false; }
''' + headers + '\n' + code + r'''
string baronState() {
    string result=state();
''' + snapshots + r'''
    return result;
}
void brReset(string label,int pool=2) {
    reset(label);
''' + resets + r'''
    uiText.clear(); uiColor.clear(); uiVisible.clear(); uiSize.clear(); registeredCommands.clear();
    gf_BRReset();
    gv_dayNumber=1; gv_isNight=true; gv_bhFactionChatOpen=true;
    gv_townMax=35;
    clearValue(gv_action); clearValue(gv_visitation); clearValue(gv_visitation2);
    clearValue(gv_jailed); clearValue(gv_roleblocked);
    for(int p=1;p<=15;++p) {
        gv_playerSpot[p]=16-p;
        for(int slot=0;slot<7;++slot) gv_actionDialogItem[p][slot]=p*100+slot;
    }
    role(1,pool,22); gv_originalRole[1][1]=pool; gv_originalRole[1][0]=22;
    eventPlayer=1;
}
std::vector<int> recruits(int p=1) {
    std::vector<int> result;
    for(int slot=0;slot<3;++slot) if(gv_brRecruit[p][slot]!=0) result.push_back(gv_brRecruit[p][slot]);
    return result;
}
void command(string message,int p=1) {
    eventPlayer=p; eventMessage=message; gt_BRRecruit_Func(true,true);
}
void commandTargets(std::vector<int> targets,int p=1) {
    string message="-recruit";
    for(int target:targets) message+=" "+std::to_string(gv_playerSpot[target]);
    command(message,p);
}
void freeze() {
    gv_dayNumber=2; gv_isNight=false; gv_bhFactionChatOpen=false; gv_nightProcessingPhase=false;
    gf_BRFreezeRecruit();
}
void testSlotReplacement() {
    for(int pool:{2,5}) {
        brReset("same-pool slots become true Town, enemy untouched",pool);
        clearValue(gv_roleNameArray); clearValue(gv_roleWeights);
        gv_roleNameArray[1][4]="investigator"; gv_roleWeights[1][4]=1;
        gv_semifinalRole[1][1]=pool; gv_semifinalRole[1][0]=22;
        for(int slot=2;slot<=15;++slot) { gv_semifinalRole[slot][1]=(slot%2?pool:(pool==2?5:2)); gv_semifinalRole[slot][0]=slot; }
        gv_semifinalRole[15][1]=1; gv_semifinalRole[15][0]=35;
        const string before=professionState();
        gf_BRReplaceSlots();
        CHECK(gv_semifinalRole[1][1]==pool && gv_semifinalRole[1][0]==22);
        for(int slot=2;slot<=14;++slot) {
            CHECK(gv_semifinalRole[slot][1]==(slot%2?1:(pool==2?5:2)));
            CHECK(gv_semifinalRole[slot][0]==(slot%2?4:slot));
        }
        CHECK(gv_semifinalRole[15][1]==1 && gv_semifinalRole[15][0]==35);
        CHECK(professionState()==before);
    }
    brReset("both leaders preserve themselves and replace both own teams");
    clearValue(gv_roleNameArray); clearValue(gv_roleWeights); gv_roleNameArray[1][3]="doctor"; gv_roleWeights[1][3]=1;
    for(int slot=1;slot<=15;++slot) { gv_semifinalRole[slot][1]=(slot<=7?2:5); gv_semifinalRole[slot][0]=(slot==1 || slot==15?22:slot); }
    gf_BRReplaceSlots();
    CHECK(gv_semifinalRole[1][1]==2 && gv_semifinalRole[15][1]==5);
    for(int slot=2;slot<15;++slot) CHECK(gv_semifinalRole[slot][1]==1 && gv_semifinalRole[slot][0]==3);
    brReset("no leader leaves all slots unchanged");
    for(int slot=1;slot<=15;++slot) { gv_semifinalRole[slot][1]=slot%2?2:5; gv_semifinalRole[slot][0]=slot; }
    int before[16][2]{};
    for(int slot=0;slot<16;++slot) for(int column=0;column<2;++column) before[slot][column]=gv_semifinalRole[slot][column];
    gf_BRReplaceSlots();
    for(int slot=0;slot<16;++slot) for(int column=0;column<2;++column) CHECK(gv_semifinalRole[slot][column]==before[slot][column]);
}
void testLeaderRandomMasks() {
    const int leaders[5]={2,17,18,19,22};
    for(int pool:{2,5}) for(int occupied=0;occupied<32;++occupied) {
        brReset("five-leader actual random picker: all 32 occupancy masks, both inclusive endpoints",pool);
        std::vector<int> available;
        for(int index=0;index<5;++index) {
            gv_roleOptions[pool][leaders[index]][10]=(occupied&(1<<index))!=0;
            if(!gv_roleOptions[pool][leaders[index]][10]) available.push_back(leaders[index]);
            gv_roleOptions[pool==2?5:2][leaders[index]][10]=!gv_roleOptions[pool][leaders[index]][10];
        }
        // Ordinary crime weights are NOT the random-leader distribution.
        gv_roleWeights[pool][2]=100000; gv_roleWeights[pool][22]=0;
        for(fixed endpoint:{0.0,1.0}) {
            forcedRandomFraction=endpoint;
            gf_BHPickLeader(pool==2?21:22);
            CHECK(gv_bhPickPool==(available.empty()?0:pool));
            CHECK(gv_bhPickRole==(available.empty()?0:endpoint==0?available.front():available.back()));
        }
        for(size_t index=0;index<available.size();++index) {
            forcedRandomFraction=(index+0.5)/available.size();
            gf_BHPickLeader(pool==2?21:22);
            CHECK(gv_bhPickPool==pool && gv_bhPickRole==available[index]);
        }
        forcedRandomFraction=-1;
    }
}
void testRandomTown() {
    brReset("weighted named Town and fallback");
    clearValue(gv_roleNameArray); clearValue(gv_roleWeights);
    CHECK(gf_BRRandomTown()==1);
    gv_roleNameArray[1][4]="investigator"; gv_roleWeights[1][4]=1;
    gv_roleWeights[1][30]=100000; // Unnamed slot must NEVER be picked.
    for(int excluded:{28,29}) { gv_roleNameArray[1][excluded]="forbidden"; gv_roleWeights[1][excluded]=100000; }
    gv_roleNameArray[2][2]="godfather"; gv_roleWeights[2][2]=100000;
    for(int i=0;i<100;++i) CHECK(gf_BRRandomTown()==4);
    gv_roleNameArray[1][35]="bishop"; gv_roleWeights[1][35]=3;
    int first=0,second=0;
    for(int i=0;i<4000;++i) { int role=gf_BRRandomTown(); CHECK(role==4 || role==35); first+=role==4; second+=role==35; }
    CHECK(first>700 && first<1300 && second>2700 && second<3300);
}
void testSelectionAndCommand() {
    for(int pool:{2,5}) {
        brReset("production command, seat mapping, independent knife selection",pool);
        gf_BRSetup(1); CHECK(gv_immune[1][0]);
        CHECK(gf_BRIs(1) && gf_BRCanSelect(1));
        gv_action[1][0]=8; gv_visitation[1]=8; gv_visitation2[1]=13;
        const string before=professionState();
        commandTargets({2,8,15});
        CHECK(recruits()==std::vector<int>({2,8,15}) && gf_BRCount(1)==3);
        CHECK(professionState()==before);
        const auto pending=recruits();
        for(string invalid:{"-recruit 0", "-recruit 16", "-recruit -1", "-recruit 01", "-recruit x", "-recruit 15", "-recruit 14 14", "-recruit 14 13 12 11", "-recruit 14 junk", "-recruitx 1"}) {
            command(invalid); CHECK(recruits()==pending && professionState()==before);
        }
        command("-recruit"); CHECK(recruits().empty() && gf_BRCount(1)==0);
        for(int target:{2,3,4}) gf_BRClick(1,target,true);
        CHECK(recruits()==std::vector<int>({2,3,4}));
        gf_BRClick(1,5,true); CHECK(recruits()==std::vector<int>({2,3,4}));
        gf_BRClick(1,3,true); CHECK(recruits()==std::vector<int>({2,4}));
        gf_BRClick(1,15,true); CHECK(gf_BRCount(1)==3);
        gf_BRClick(1,9,false); CHECK(gv_action[1][0]==9 && gf_BRCount(1)==3);
        for(int p=1;p<=15;++p) CHECK(gv_bhFaction[p]==0);
    }
    brReset("hidden factions do not alter selection eligibility or immediate feedback");
    std::vector<string> reference;
    for(int pool:{1,2,3,5}) for(int id:{1,2,17,22,28,29,33,35}) {
        role(8,pool,id); gv_bhFaction[8]=0;
        CHECK(gf_BRSelectable(1,8));
        command("-recruit"); clearEffects();
        commandTargets({8}); CHECK(recruits()==std::vector<int>{8} && gf_BHFaction(8)==pool);
        std::vector<string> actual; for(const auto& m:messages) actual.push_back(m.value);
        if(reference.empty()) reference=actual; else CHECK(actual==reference);
    }
    brReset("invalid selection bounds and membership");
    for(int target:{INT_MIN,-1,0,1,16,INT_MAX}) CHECK(!gf_BRSelectable(1,target));
    gv_alivePlayers&=~(1u<<8); CHECK(!gf_BRSelectable(1,8));
    gv_alivePlayers|=1u<<8; gv_currentPlayers&=~(1u<<8); CHECK(!gf_BRSelectable(1,8));
}
void testLeaderIdentity() {
    brReset("true role identity, never effective-faction or FZ presentation identity");
    for(int invalid:{INT_MIN,-1,0,16,INT_MAX}) CHECK(!gf_BRIs(invalid));
    for(int pool=0;pool<=8;++pool) for(int id=0;id<=40;++id) for(int overridePool:{0,2,5}) {
        role(1,pool,id); gv_bhFaction[1]=overridePool;
        CHECK(gf_BRIs(1)==((pool==2 || pool==5) && id==22));
    }
}
void testClosedWindows() {
    for(int guard=0;guard<11;++guard) {
        brReset("closed selection windows"); commandTargets({2,3});
        if(guard==0) gv_dayNumber=2;
        if(guard==1) gv_isNight=false;
        if(guard==2) gv_bhFactionChatOpen=false;
        if(guard==3) gv_nightProcessingPhase=true;
        if(guard==4) gv_gameOver=true;
        if(guard==5) gv_alivePlayers&=~(1u<<1);
        if(guard==6) gv_currentPlayers&=~(1u<<1);
        if(guard==7) gv_jailed[1]=7;
        if(guard==8) role(1,1,22);
        if(guard==9) { role(1,1,33); gv_fzPool[1]=2; gv_fzRole[1]=19; }
        if(guard==10) gv_gameStarted=false;
        CHECK(!gf_BRCanSelect(1));
        const auto before=recruits(); const string profession=professionState();
        commandTargets({4,5}); gf_BRClick(1,4,true);
        CHECK(recruits()==before && professionState()==profession);
        if(guard!=0) {
            // Later nights close recruitment, not the role's nightly knife.
            gf_BRClick(1,4,false); CHECK(professionState()==profession);
        }
    }
}
void testClaim() {
    for(int pool:{2,5}) for(int mode=0;mode<6;++mode) {
        brReset("one standard faction knife, leader personally claims",pool);
        gv_action[1][0]=8; gv_action[1][1]=13;
        gv_mafiaHitman=gv_triadHitman=4; gv_mafiaTarget=gv_triadTarget=12;
        gv_visitation[4]=12; gv_visitation2[4]=14;
        if(mode==1) gv_action[1][0]=0;
        if(mode==2) gv_jailed[1]=3;
        if(mode==3) gv_alivePlayers&=~(1u<<1);
        if(mode==4) gv_currentPlayers&=~(1u<<1);
        if(mode==5) gv_bhFeignRole[1]=22;
        gf_BRClaim(pool);
        CHECK((pool==2?gv_triadHitman:gv_mafiaHitman)==4);
        CHECK((pool==2?gv_triadTarget:gv_mafiaTarget)==12);
        if(mode==0) {
            CHECK((pool==2?gv_mafiaHitman:gv_triadHitman)==1);
            CHECK((pool==2?gv_mafiaTarget:gv_triadTarget)==8 && gv_visitation[1]==8);
            CHECK(gv_visitation[4]==0 && gv_visitation2[4]==0 && gv_visitation2[1]==0);
            CHECK(gv_action[1][1]==13);
        }
        if(mode==1 || mode==2) CHECK((pool==2?gv_mafiaHitman:gv_triadHitman)==0 && (pool==2?gv_mafiaTarget:gv_triadTarget)==0);
        if(mode>=3) CHECK((pool==2?gv_mafiaHitman:gv_triadHitman)==4 && gv_visitation[1]==0);
    }
    brReset("invalid faction selector cannot claim either faction knife");
    gv_action[1][0]=8; const string before=baronState();
    for(int invalid:{INT_MIN,-1,0,1,3,4,6,INT_MAX}) { gf_BRClaim(invalid); CHECK(baronState()==before); }
    brReset("converted Town22 is not a new criminal leader");
    role(1,1,22); gv_bhFaction[1]=2; gv_action[1][0]=8;
    CHECK(!gf_BRIs(1)); gf_BRClaim(2); CHECK(gv_mafiaHitman==0 && gv_visitation[1]==0);
}
void testFreezeAndResolve() {
    for(int pool:{2,5}) {
        brReset("dawn conversion retains original profession state",pool);
        for(int p:{2,8,15}) { role(p,1,p==2?4:p==8?33:35); gv_originalRole[p][1]=1; gv_originalRole[p][0]=gv_roles[p][0]; }
        commandTargets({2,8,15}); const string before=professionState();
        gf_BRResolveRecruit(); CHECK(gf_BHFaction(2)==1 && professionState()==before);
        freeze(); CHECK(gv_brFrozen && gv_brReady[1]);
        gf_BRResolveRecruit();
        CHECK(gv_brDone && professionState()==before);
        CHECK(std::any_of(messages.begin(),messages.end(),[](const Message& m) { return m.target==1 && m.value==StringExternal("Param/Value/BRRESULT")+"3"; }));
        for(int p:{2,8,15}) {
            CHECK(gf_BHFaction(p)==pool && gv_roles[p][1]==1);
            CHECK(hasMessage(p,pool==2?"BHFJOIN2":"BHFJOIN5"));
            CHECK(gv_roleBoxText[p][3]==StringExternal(pool==2?"Param/Value/BHFGOAL2":"Param/Value/BHFGOAL5") || p==8);
        }
        CHECK(gf_BHRoleName(2).find(pool==2?"<c=85063056>":"<c=20040100>")==0);
        const string state=baronState(); clearEffects(); gf_BRResolveRecruit();
        CHECK(baronState()==state && events.empty());
    }
    for(int guard=0;guard<5;++guard) {
        brReset("leader action eligibility frozen before jail/roleblock reset"); commandTargets({8});
        if(guard==0) gv_roleblocked[1]=3;
        if(guard==1) gv_jailed[1]=3;
        if(guard==2) gv_alivePlayers&=~(1u<<1);
        if(guard==3) gv_currentPlayers&=~(1u<<1);
        if(guard==4) role(1,1,33);
        freeze(); CHECK(!gv_brReady[1]);
        gv_roleblocked[1]=0; gv_jailed[1]=0; gv_alivePlayers|=1u<<1; gv_currentPlayers|=1u<<1;
        role(1,2,22); gf_BRFreezeRecruit(); CHECK(!gv_brReady[1]);
        gf_BRResolveRecruit(); CHECK(gf_BHFaction(8)==1);
    }
    for(int guard=0;guard<3;++guard) {
        brReset("leader must still be a current living real leader at final commit"); commandTargets({8}); freeze();
        if(guard==0) gv_currentPlayers&=~(1u<<1);
        if(guard==1) gv_alivePlayers&=~(1u<<1);
        if(guard==2) role(1,1,33);
        gf_BRResolveRecruit(); CHECK(gf_BHFaction(8)==1);
    }
    for(int guard=0;guard<11;++guard) {
        brReset("final target eligibility, cannot steal an enemy or convert dead/left targets"); commandTargets({8}); freeze();
        if(guard==0) gv_alivePlayers&=~(1u<<8);
        if(guard==1) gv_currentPlayers&=~(1u<<8);
        if(guard==2) role(8,2,4);
        if(guard==3) role(8,5,4);
        if(guard==4) role(8,3,4);
        if(guard==5) gv_bhFaction[8]=5;
        if(guard==6) role(8,1,28);
        if(guard==7) role(8,1,29);
        if(guard==8) gv_bhFeignRole[8]=4;
        if(guard==9) role(8,1,0);
        if(guard==10) role(8,1,36);
        const int faction=gf_BHFaction(8); gf_BRResolveRecruit(); CHECK(gf_BHFaction(8)==faction);
        CHECK(std::any_of(messages.begin(),messages.end(),[](const Message& m) { return m.target==1 && m.value==StringExternal("Param/Value/BRRESULT")+"0"; }));
    }
    brReset("late JJ revival: target dead at freeze, alive at final commit");
    commandTargets({8}); gv_alivePlayers&=~(1u<<8); gv_diedAtNight[8]=true;
    freeze(); CHECK(gv_brReady[1]);
    // Engine-membership boundary corresponding to JJResolve/JJRevive, whose
    // actual production call order is separately asserted above.
    gv_alivePlayers|=1u<<8; gv_diedAtNight[8]=false;
    gf_BRResolveRecruit(); CHECK(gf_BHFaction(8)==2);
    brReset("simultaneous opposite leaders cannot steal a committed recruit");
    role(15,5,22); commandTargets({8},1); commandTargets({8},15); freeze();
    gf_BRResolveRecruit(); CHECK(gf_BHFaction(8)==2 || gf_BHFaction(8)==5);
    const int winner=gf_BHFaction(8); gf_BRResolveRecruit(); CHECK(gf_BHFaction(8)==winner);
    for(int pool:{2,5}) {
        brReset("FZ22 can privately plan, but never obtains real conversion authority");
        role(1,1,33); gv_fzPool[1]=pool; gv_fzRole[1]=22;
        CHECK(!gf_BRIs(1) && gf_BRCanSelect(1));
        commandTargets({2,8}); CHECK(recruits()==std::vector<int>({2,8}));
        gf_BRClick(1,2,true); CHECK(recruits()==std::vector<int>{8});
        freeze(); CHECK(!gv_brReady[1]); gf_BRResolveRecruit();
        CHECK(gf_BHFaction(2)==1 && gf_BHFaction(8)==1);
    }
}
void testUIAndReset() {
    brReset("two buttons coexist and recruitment is private"); gf_BRSetup(1);
    for(int target=2;target<=15;++target) {
        CHECK(uiVisible[{1,gv_actionDialogItem[target][5]}]);
        CHECK(uiVisible[{1,gv_actionDialogItem[target][6]}]);
        CHECK(uiSize[{1,gv_actionDialogItem[target][5]}].first==60);
        CHECK(uiSize[{1,gv_actionDialogItem[target][6]}].first==60);
    }
    CHECK(!uiVisible[{1,gv_actionDialogItem[1][6]}]);
    const string before=professionState(); gf_BRDraw(1); gf_BRList(1); CHECK(professionState()==before);
    for(const auto& m:messages) CHECK(m.target==1);
    commandTargets({8}); freeze(); gf_BRResolveRecruit();
    gf_BRReset(); CHECK(!gv_brFrozen && !gv_brDone);
    for(int p=0;p<16;++p) { CHECK(!gv_brReady[p]); CHECK(recruits(p).empty()); }
    gt_BRRecruit_Init(); CHECK(registeredCommands==std::vector<string>{"-recruit"});
}
int main(int argc,char** argv) {
    const string selected=argc>1?argv[1]:"all";
    if(selected=="all" || selected=="slots") testSlotReplacement();
    if(selected=="all" || selected=="leaders") testLeaderRandomMasks();
    if(selected=="all" || selected=="town") testRandomTown();
    if(selected=="all" || selected=="select") testSelectionAndCommand();
    if(selected=="all" || selected=="identity") testLeaderIdentity();
    if(selected=="all" || selected=="windows") testClosedWindows();
    if(selected=="all" || selected=="claim") testClaim();
    if(selected=="all" || selected=="dawn") testFreezeAndResolve();
    if(selected=="all" || selected=="ui") testUIAndReset();
    std::cout << "PASS actual Baron/Taido helpers [" << selected << "]: " << fixtures << " fixtures, " << checks << " checks; UBSan/bounds; real conversion API, no membership/selection/knife algorithm doubles" << std::endl;
}
'''
    return base + '\n' + extension


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--case', choices=('all', 'slots', 'leaders', 'town', 'select', 'identity', 'windows', 'claim', 'dawn', 'ui'), default='all', help='Run one group for diagnosis, or the full suite (default)')
    args = parser.parse_args()
    source = args.script.read_text(encoding='utf-8')
    code = harness(source)
    with tempfile.TemporaryDirectory(prefix='bh-baron-tests-') as directory:
        cpp, executable = Path(directory) / 'baron.cpp', Path(directory) / 'baron'
        cpp.write_text(code, encoding='utf-8')
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable), args.case], check=True)


if __name__ == '__main__':
    main()
