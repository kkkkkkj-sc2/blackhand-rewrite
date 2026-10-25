#!/usr/bin/env python3
"""Execute actual apprenticeship Galaxy with retained faction, UBSan and bounds.

Extracts the COMPLETE learning, Prep, action, action-panel setup, faction queries,
role-name, role-card dispatcher and faction-overlay functions. Exact immediate
caller guards are also executed (not their enormous surrounding night/UI loops).
All global array types/dimensions come from the selected Galaxy source.

Fixtures seed post-conversion identity; conversion itself has its own suite.
Pool-specific card text and win-list formatting are explicit presentation doubles;
real dispatcher/overlay control flow executes. Thus no full card-text, SC2 compiler,
rendering, multiplayer, night scheduling, or engine-timing claim is made. The
non-Town lethal learning branches are compiled but deliberately NOT exercised:
their external serial-killer helper fails fast rather than pretending to resolve
an attack. Original asymmetries (target immunity, Mason leader shortcut, flag,
shots and lawyer-copy differences) are locked down, not silently repaired.

Run: python3 tools/test_apprentice_faction.py [--script PATH] [--cxx g++]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from test_egun import SCRIPT, function, mask, translate

NAMES = (
    'gf_SKG_1_xuetu', 'gf_SKP_1_xuetu', 'gf_SKA2_1_xuetu',
    'gf_SKR_1_xuetu', 'gf_RAE5ADA6E5BE92Actions',
    'gf_BHVisitAction', 'gf_BHVisit', 'gf_BHConverted', 'gf_BHFaction',
    'gf_BHRoleName', 'gf_RTRoleCard', 'gf_BHFactionCard',
    'gf_BHSpyActive', 'gf_BHSeenFaction',
)
BOUNDARIES = {
    'StringExternal', 'IntToString', 'StringToText', 'TextWithColor', 'Color',
    'SoundLink', 'PlayerGroupHasPlayer', 'PlayerGroupAll', 'PlayerGroupSingle',
    'libNtve_gf_ConvertPlayerColorToColor', 'gf_CBSystemMessage',
    'gf_RefreshRoleBox', 'gf_RTTownRoleText', 'gf_RTMafiaRoleText',
    'gf_RTNeutralRoleText', 'gf_RTTriadRoleText', 'gf_RTMakeWinList',
    'DialogControlSetVisible', 'DialogControlSetSize',
    'libNtve_gf_SetDialogItemTooltip', 'libNtve_gf_SetDialogItemColor',
    'libNtve_gf_SetDialogItemImage', 'libNtve_gf_SetDialogItemImage2',
    'RandomFixed', 'Wait', 'SoundPlayForPlayer', 'gf_ESSerialKillerKill',
}


def immediate_guard(source: str, owner: str, callee: str, wrapper: str,
                    arguments: str) -> str:
    """Keep the exact owning if, including its actual call, without night loops."""
    body = function(source, owner)
    match = re.search(r'(?m)^\s*if ([^\n]+) \{\s*' + re.escape(callee)
                      + r'\([^;]+\);\s*}', body)
    assert match, ('missing immediate dispatch guard', owner, callee)
    assert len(re.findall(r'\b' + re.escape(callee) + r'\(', body)) == 1
    guard = match[0].strip()
    assert 'gv_roles[' in guard and 'gf_BHFaction(' not in guard, (
        'apprentice dispatch must test profession, not real faction', owner)
    return f'void {wrapper}({arguments}) {{\n{guard}\n}}'


def harness(source: str) -> str:
    names = NAMES
    if 'bool gf_BHApprenticeAllyLearn (int lp_player, int lp_mentor) {' in source:
        names += ('gf_BHApprenticeAllyLearn', 'gf_BHApprenticeNativeInit',
                  'gf_SKO_2_qinglizhe', 'gf_SKO_5_xiangzhu',
                  'gf_SKO_2_bangjiazhe', 'gf_SKO_5_shenxun',
                  'gf_SKO_2_qipianzhe', 'gf_SKO_5_mihuo')

    bodies = [function(source, name) for name in names]
    guards = [
        immediate_guard(source, 'gf_SequencePrep', 'gf_SKP_1_xuetu',
                        'dispatchPrep', 'int lv_a'),
        immediate_guard(source, 'gf_SequenceAfter2', 'gf_SKG_1_xuetu',
                        'dispatchLearning', 'int lv_a'),
        immediate_guard(source, 'gt_ASActionButtonATown2_Func',
                        'gf_SKA2_1_xuetu', 'dispatchClick',
                        'int lv_source, int lv_target'),
    ]
    raw = '\n\n'.join(bodies + guards)
    live = mask(raw)
    learning = mask(bodies[0])
    assert 'gv_roles[gv_visitation[lv_a]][1] == 1' in learning
    town_start = learning.index('if ((gv_roles[gv_visitation[lv_a]][1] == 1)) {')
    town_open = learning.index('{', town_start)
    town_end, depth = town_open + 1, 1
    while depth:
        depth += (learning[town_end] == '{') - (learning[town_end] == '}')
        town_end += 1

    assert not re.search(r'\bgv_bhFaction\b|\bgf_BHFaction\(',
                         learning[town_start:town_end]), (
        'Town learning must keep its own faction, independent of mentor faction')
    assert set(re.findall(r'gv_roleBoxText\[lp_player\]\[(\d+)\]\s*=',
                          mask(function(source, 'gf_BHFactionCard')))) == {'0', '3', '6'}

    used = set(re.findall(r'\bgv_\w+', live)) | {
        'gv_originalRole', 'gv_cooldown', 'gv_visitation2', 'gv_variableOptions',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;',
                             source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not used - declarations.keys(), ('missing real declarations', used - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(used))
    resets = '\n'.join(f'    clearValue({name});' for name in sorted(used))
    calls = set(re.findall(r'\b(\w+)\s*\(', live)) - {'if', 'for', 'while', 'return'}
    defined = set(names) | {'dispatchPrep', 'dispatchLearning', 'dispatchClick'}
    assert not calls - defined - BOUNDARIES, ('new unreviewed dependency', calls - defined - BOUNDARIES)
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    code = translate(raw)
    code = re.sub(r'\bnull\b', 'text{}', code)
    code = re.sub(r'^(\s+(?:int|bool|text|string)\s+\w+(?:\[\d+\])*)\s*;',
                  r'\1 = {};', code, flags=re.M)
    for name, body in zip(names, bodies):
        start = source.index(body)
        print(f'  {name}: {source.count(chr(10), 0, start) + 1}..'
              f'{source.count(chr(10), 0, start + len(body)) + 1}', flush=True)

    print(f'Extracted {len(bodies)} complete functions, 3 exact immediate guards, '
          f'{len(used)} real global declarations; no learning/faction doubles', flush=True)
    return r'''
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <map>
#include <string>
#include <tuple>
#include <vector>
using std::string;
using text = string;
using soundlink = string;
using playergroup = unsigned int;
constexpr int c_timeGame=0, c_maxPlayers=16;
int checks=0, fixtures=0;
string context;
#define CHECK(...) do { ++checks; if(!(__VA_ARGS__)) { std::cerr << "FAIL [" << context << "] line " << __LINE__ << ": " << #__VA_ARGS__ << '\n'; std::abort(); } } while(0)
''' + globals_text + r'''
struct Message { text value; int player; };
std::vector<Message> messages;
std::vector<std::tuple<int,int,int>> renders;
std::map<std::pair<int,int>,bool> visible;
int refreshes=0;
template<class T> void clearValue(T& value) { value=T{}; }
template<class T,size_t N> void clearValue(T (&values)[N]) { for(auto& value:values) clearValue(value); }
playergroup PlayerGroupSingle(int p) { CHECK(p>=1 && p<=15); return 1u<<p; }
playergroup PlayerGroupAll() { return 65534u; }
bool PlayerGroupHasPlayer(playergroup group,int p) { CHECK(p>=1 && p<=15); return (group&(1u<<p))!=0; }
text StringExternal(string key) { return "{"+key+"}"; }
text StringToText(string value) { return value; }
string IntToString(int value) { return std::to_string(value); }
int Color(double r,double g,double b) { return int(std::lround(r))*1000000+int(std::lround(g))*1000+int(std::lround(b)); }
text TextWithColor(text value,int color) { return "<c="+std::to_string(color)+">"+value+"</c>"; }
int libNtve_gf_ConvertPlayerColorToColor(int value) { return value; }
soundlink SoundLink(string value,int index) { CHECK(index==-1); return value; }
void gf_CBSystemMessage(text value,int p,int,int mode,soundlink,int) { CHECK(p>=1 && p<=15 && mode==0); messages.push_back({value,p}); }
void gf_RefreshRoleBox() { ++refreshes; }
// Presentation-only pool renderers: profession-shaped sentinels, never gameplay.
string rowText(int pool,int role,int row) { return "CARD:"+std::to_string(pool)+":"+std::to_string(role)+":"+std::to_string(row); }
void draw(int p,int pool) {
    CHECK(gv_roles[p][1]==pool); renders.emplace_back(p,pool,gv_roles[p][0]);
    for(size_t row=0;row<std::size(gv_roleBoxText[p]);++row) gv_roleBoxText[p][row]=rowText(pool,gv_roles[p][0],int(row));
}
void gf_RTTownRoleText(int p) { draw(p,1); }
void gf_RTMafiaRoleText(int p) { draw(p,2); }
void gf_RTNeutralRoleText(int p) { draw(p,3); }
void gf_RTTriadRoleText(int p) { draw(p,5); }
text gf_RTMakeWinList(int pool,int role) { return "WIN:"+std::to_string(pool)+":"+std::to_string(role); }
void DialogControlSetVisible(int item,playergroup group,bool show) {
    for(int p=1;p<=15;++p) if(group&(1u<<p)) visible[{p,item}]=show;
}
template<class... T> void DialogControlSetSize(T...) {}
template<class... T> void libNtve_gf_SetDialogItemTooltip(T...) {}
template<class... T> void libNtve_gf_SetDialogItemColor(T...) {}
template<class... T> void libNtve_gf_SetDialogItemImage(T...) {}
template<class... T> void libNtve_gf_SetDialogItemImage2(T...) {}
double RandomFixed(double lo,double hi) { CHECK(lo<=hi); return (lo+hi)/2; }
// Out-of-scope lethal/non-Town branch: never fake attack semantics.
void gf_ESSerialKillerKill(int,int) { CHECK(false && "external lethal learning branch not simulated"); }
void Wait(double,int) { CHECK(false && "external lethal learning branch not simulated"); }
template<class... T> void SoundPlayForPlayer(T...) { CHECK(false); }
''' + headers + '\n' + code + r'''
bool hasMessage(int p,string key) {
    return std::any_of(messages.begin(),messages.end(),[&](const Message& m) { return m.player==p && m.value.find("{Param/Value/"+key+"}")!=string::npos; });
}
void reset(string label,int learner,int mentor,int faction,int mentorFaction,int role) {
''' + resets + r'''
    context=label+" a="+std::to_string(learner)+" t="+std::to_string(mentor)+" f="+std::to_string(faction)+" tf="+std::to_string(mentorFaction)+" r="+std::to_string(role);
    ++fixtures; messages.clear(); renders.clear(); visible.clear(); refreshes=0;
    gv_alivePlayers=PlayerGroupAll(); gv_dayNumber=2;
    for(int p=1;p<=15;++p) {
        gv_roles[p][1]=1; gv_roles[p][0]=1;
        gv_originalRole[p][1]=1; gv_originalRole[p][0]=p==learner?24:1;
        gv_shots[p]=17+p; gv_cooldown[p]=3; gv_immune[p][0]=true; gv_immuneChance[p]=4;
        gv_name[p]="P"+std::to_string(p); gv_playerColor[p]=p;
        gv_rolesArray[p]=4; gv_variableOptions[p][0]=8;
        for(size_t slot=0;slot<std::size(gv_actionDialogItem[p]);++slot) gv_actionDialogItem[p][slot]=p*100+int(slot);
        for(size_t row=0;row<std::size(gv_roleBoxText[p]);++row) gv_roleBoxText[p][row]="OLD:"+std::to_string(p)+":"+std::to_string(row);
    }
    for(size_t pool=0;pool<std::size(gv_roleNameArray);++pool)
        for(size_t id=0;id<std::size(gv_roleNameArray[pool]);++id)
            gv_roleNameArray[pool][id]="PROF:"+std::to_string(pool)+":"+std::to_string(id);
    gv_roles[learner][0]=24; gv_roles[mentor][0]=role;
    gv_bhFaction[learner]=faction; gv_bhFaction[mentor]=mentorFaction;
    // Stale FZ disguise must not masquerade as the learnt role after conversion.
    gv_fzPool[learner]=2; gv_fzRole[learner]=2;
    for(int slot=0;slot<5;++slot) {
        gv_e6B395E5B888E68A80E883BD[learner][slot]=slot%2!=0;
        gv_e6B395E5B888E68A80E883BD[mentor][slot]=slot%2==0;
    }
    gv_e6B395E5B888E58FA0E5B182[learner]=1;
    gv_e6B395E5B888E58FA0E5B182[mentor]=4;
}
void verifyIdentity(int a,int faction,int role) {
    CHECK(gv_roles[a][1]==1 && gv_roles[a][0]==role);
    CHECK(gv_bhFaction[a]==faction);
    CHECK(gf_BHConverted(a)==(faction==2 || faction==5));
    CHECK(gf_BHFaction(a)==(faction==0?1:faction));
    text expected=faction==0?gv_roleNameArray[1][role]:TextWithColor(StringExternal("Param/Value/BHFROLE"+std::to_string(role)),faction==2?Color(85.10,62.75,56.08):Color(56.08,74.90,81.96));
    CHECK(gf_BHRoleName(a)==expected);
}
void verifyOverlay(int a,int faction,int renderedPool,int renderedRole) {
    CHECK(renders==std::vector<std::tuple<int,int,int>>{{a,renderedPool,renderedRole}});
    for(size_t row=0;row<std::size(gv_roleBoxText[a]);++row) {
        text expected=rowText(renderedPool,renderedRole,int(row));
        if(faction!=0) {
            if(row==0) expected=StringExternal(faction==2?"Param/Value/1447EB27":"Param/Value/C49DA5F4")+StringExternal("Param/Value/BHFKEEP");
            if(row==3) expected=StringExternal(faction==2?"Param/Value/BHFGOAL2":"Param/Value/BHFGOAL5");
            if(row==6) expected="WIN:"+std::to_string(faction)+":0";
        }
        CHECK(gv_roleBoxText[a][row]==expected);
    }
}
void testTownMatrix() {
    // Every supported conversion profession 1..35 except reserved 28/29/30.
    // Includes Spy 8, leader 14->7, apprentice 24, FZ 33, and new 31..35.
    for(int a:{1,8,15}) {
        int t=a==15?1:15;
        for(int f:{0,2,5}) for(int tf:{0,2,5}) for(int role=1;role<=35;++role) {
            if(role==28 || role==29 || role==30) continue;
            for(bool gov:{false,true}) for(bool reveal:{false,true}) for(bool announce:{false,true}) {
                reset("Town Cartesian learning",a,t,f,tf,role);
                gv_roleOptions[1][24][0]=reveal;
                gv_roleOptions[1][24][1]=gov;
                gv_roleOptions[1][24][2]=announce;
                // Actual button -> Prep -> exact learning caller guard -> complete body.
                dispatchClick(a,t); CHECK(gv_action[a][0]==t);
                dispatchPrep(a); CHECK(gv_visitation[a]==t);
                messages.clear(); dispatchLearning(a);
                bool rejected=!gov && (role==12 || role==19 || role==20 || role==23);
                int learnt=rejected?24:role==14?7:role;
                verifyIdentity(a,f,learnt); verifyIdentity(t,tf,role);
                CHECK(gf_BHSpyActive(a)==(learnt==8 && f==0));
                CHECK(gf_BHSeenFaction(a)==(learnt==8?1:(f==0?1:f)));
                CHECK(gv_originalRole[a][1]==1 && gv_originalRole[a][0]==24);
                CHECK(gv_originalRole[t][1]==1 && gv_originalRole[t][0]==1);
                CHECK(gv_cooldown[a]==3 && gv_cooldown[t]==3);
                CHECK(gv_shots[t]==17+t);
                CHECK(gv_action[a][0]==t && gv_visitation[a]==t && gv_visitation2[a]==0);
                CHECK(gv_variableOptions[a][0]==8);
                CHECK(gv_immune[a][0] && gv_immuneChance[a]==4); // target, NOT learner!
                CHECK(gv_immune[t][0]==!(!rejected && !gov && role!=14));
                CHECK(gv_immuneChance[t]==(!rejected && !gov && role!=14?0:4));
                CHECK(gv_e4BB8AE6999AE58F98E8BAAB[a]==(!gov && !rejected));
                CHECK(gv_specialCasePlayer[a][56]==int(!rejected && role==24));
                CHECK(gv_specialCasePlayer[a][64]==int(role==21 && !gov));
                CHECK(!gv_janitized[a] && !gv_zuosi[a]);
                if(rejected) {
                    CHECK(gv_shots[a]==17+a && refreshes==0 && renders.empty());
                    CHECK(messages.size()==1 && hasMessage(a,"001D07B7"));
                }
                else if(role==14) {
                    // Legacy shortcut does NOT call RTRoleCard or reset learner shots.
                    CHECK(gv_shots[a]==17+a && refreshes==1 && renders.empty());
                    CHECK(gv_roleBoxText[a][0]=="OLD:"+std::to_string(a)+":0");
                    int count=(gov?reveal:announce)?15:0;
                    CHECK(int(messages.size())==count);
                    if(count) {
                        CHECK(hasMessage(a,gov?"164A4891":reveal?"47D65902":"6B1F733B"));
                        if(gov || reveal) CHECK(messages[0].value.find("PROF:1:4")!=string::npos); // gv_rolesArray legacy lookup
                    }
                }
                else {
                    CHECK(gv_shots[a]==(role==12 || role==19?1:2) && refreshes==1);
                    int pool=role==33 && f==0?2:1, rendered=role==33 && f==0?2:role;
                    verifyOverlay(a,f,pool,rendered);
                    CHECK(int(messages.size())==(reveal?15:0)+int(role==21 && !gov));
                    if(reveal) CHECK(hasMessage(a,gov?"B11B45D7":"A3C3B804"));
                }
                for(int slot=0;slot<5;++slot) CHECK(gv_e6B395E5B888E68A80E883BD[a][slot]==(role==21 && !gov && slot<4?slot%2==0:slot%2!=0));
                CHECK(gv_e6B395E5B888E58FA0E5B182[a]==(role==21 && !gov?4:1));
                for(int p=1;p<=15;++p) if(p!=a) {
                    CHECK(gv_roles[p][1]==1 && gv_roles[p][0]==(p==t?role:1));
                    CHECK(gv_shots[p]==17+p && gv_cooldown[p]==3);
                    for(size_t row=0;row<std::size(gv_roleBoxText[p]);++row) CHECK(gv_roleBoxText[p][row]=="OLD:"+std::to_string(p)+":"+std::to_string(row));
                }
            }
        }
    }
}
void testActionsAndCallerGuards() {
    for(int f:{0,2,5}) for(int tf:{0,2,5}) {
        reset("real action setup and retarget/cancel",8,15,f,tf,8);
        gv_dayNumber=1; gf_SKR_1_xuetu(8);
        CHECK(hasMessage(8,"8168A928") && visible.empty());
        gv_dayNumber=2; gv_alivePlayers&=~(1u<<7); gf_SKR_1_xuetu(8);
        for(int p=1;p<=15;++p) CHECK(visible[{8,gv_actionDialogItem[p][5]}]==(p!=8 && p!=7));
        CHECK(visible[{8,gv_actionDialogItem[15][5]}]); // even converted mentor
        dispatchClick(8,15); CHECK(gv_action[8][0]==15);
        dispatchClick(8,1); CHECK(gv_action[8][0]==1 && visible[{8,gv_actionDialogItem[15][5]}]);
        dispatchClick(8,8); CHECK(gv_action[8][0]==0 && !visible[{8,gv_actionDialogItem[8][5]}]);
        dispatchPrep(8); CHECK(gv_visitation[8]==0);
        renders.clear(); dispatchLearning(8); CHECK(renders.empty() && gv_roles[8][0]==24);
        dispatchClick(8,15); dispatchPrep(8); gv_diedAtNight[8]=true;
        dispatchLearning(8); CHECK(renders.empty() && gv_roles[8][0]==24);
        gv_diedAtNight[8]=false;
        // True gang profession with a stale faction flag is not a Town apprentice.
        gv_roles[8][1]=2; gv_visitation[8]=0;
        dispatchPrep(8); CHECK(gv_visitation[8]==0);
        gv_visitation[8]=15; dispatchLearning(8); CHECK(gv_roles[8][0]==24 && renders.empty());
        gv_action[8][0]=0; dispatchClick(8,15); CHECK(gv_action[8][0]==0);
        gv_roles[8][1]=1; gv_roles[8][0]=4; dispatchLearning(8);
        CHECK(gv_roles[8][0]==4 && renders.empty());
    }
}
void testMasonExistingOverlay() {
    for(int f:{0,2,5}) for(int tf:{0,2,5}) for(bool gov:{false,true}) {
        reset("leader shortcut preserves preexisting converted overlay",8,15,f,tf,14);
        gv_roleOptions[1][24][1]=gov;
        gf_RTRoleCard(8);
        std::vector<text> before(std::begin(gv_roleBoxText[8]),std::end(gv_roleBoxText[8]));
        renders.clear(); refreshes=0;
        dispatchClick(8,15); dispatchPrep(8); dispatchLearning(8);
        verifyIdentity(8,f,7);
        CHECK(renders.empty() && refreshes==1 && gv_shots[8]==25);
        CHECK(std::equal(before.begin(),before.end(),std::begin(gv_roleBoxText[8])));
        // Old 24 profession text survives this historical no-rerender shortcut,
        // but the actual faction/name queries immediately see the new role 7.
        CHECK(gv_roleBoxText[8][1]==rowText(1,24,1));
        if(f!=0) CHECK(gv_roleBoxText[8][6]=="WIN:"+std::to_string(f)+":0");
    }
}
void testNeutralRefusalAndRepeatedLearning() {
    for(int f:{0,2,5}) for(int role:{2,3,6,7,17}) {
        reset("native nonlethal neutral refusal",1,15,f,0,role);
        gv_roles[15][1]=3;
        dispatchClick(1,15); dispatchPrep(1); dispatchLearning(1);
        verifyIdentity(1,f,24);
        CHECK(gv_shots[1]==18 && renders.empty() && refreshes==0);
        CHECK(hasMessage(1,"23328F9D") && hasMessage(15,"8170EF20"));
        CHECK(!gv_janitized[1] && !gv_zuosi[1]);
    }
    for(int f:{0,2,5}) {
        reset("apprentice into apprentice then next mentor",1,15,f,5,24);
        dispatchClick(1,15); dispatchPrep(1); dispatchLearning(1);
        CHECK(gv_specialCasePlayer[1][56]==1 && gv_shots[1]==2);
        gv_roles[15][0]=35; renders.clear();
        dispatchLearning(1); verifyIdentity(1,f,35);
        CHECK(gv_specialCasePlayer[1][56]==1 && gv_shots[1]==2);
        CHECK(gv_originalRole[1][0]==24 && gv_bhFaction[1]==f);
        verifyOverlay(1,f,1,35);
    }
}
int main() {
    testTownMatrix(); testActionsAndCallerGuards(); testMasonExistingOverlay(); testNeutralRefusalAndRepeatedLearning();
    std::cout << "PASS: original Town/mafia/triad learners x mentors; 32 supported Town professions; all 8 option combinations; government refusals; Spy/Mason/apprentice/FZ/31..35; actual action/Prep/caller guards; retained faction/name/card overlay; native asymmetries" << '\n';
    std::cout << "PASS: " << fixtures << " fixtures, " << checks << " assertions; UBSan/bounds; no Galaxy edits; presentation/SC2 engine boundaries documented" << std::endl;
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
    with tempfile.TemporaryDirectory(prefix='bh-apprentice-tests-') as tmp:
        cpp, exe = Path(tmp) / 'apprentice.cpp', Path(tmp) / 'apprentice'
        cpp.write_text(code, encoding='utf-8')
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
