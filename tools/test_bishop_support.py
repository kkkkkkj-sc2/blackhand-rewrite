#!/usr/bin/env python3
"""Execute actual bishop Galaxy bodies in a C++17 engine-stub harness.

Requires g++; enables undefined/bounds sanitizers. Tests logic and static wiring,
not the SC2 compiler, rendering, or complete bus/witch engine. Redirection tests
inject the final visitation produced by those existing engine stages.
Default: extract everything from CustomLogic.galaxy. --core PATH explicitly tests
an unintegrated draft, keeping the real vote getter and helper bodies from source.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from preset_gen import load_strings
from test_faction_conversion import with_guoke_dependencies
from test_recruiter_modes import balanced_end, function

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
CORE = (
    'gf_ZJSupportWeight', 'gf_ZJNormalizeOptions', 'gf_ZJOptionClick',
    'gf_RAZhujiaoActions', 'gf_SKR_1_zhujiao', 'gf_SKA_1_zhujiao',
    'gf_SKP_1_zhujiao', 'gf_SKU_1_zhujiao', 'gf_SKK_1_zhujiao', 'gf_ZJMorning',
)
HELPERS = ('gf_BHVoteWeight', 'gf_BHNoVoteOrCount', 'gf_GKIs',
           'gf_RANoActions', 'gf_BHVisit', 'gf_BHVisit2',
           'gf_BHVisitAction', 'gf_BHVisitNone')


def integration(source: str) -> str:
    """Check dispatcher presence/order and execute actual night expiry statements."""
    for name in CORE:
        references = re.findall(r'\b' + name + r'\s*\(', source)
        # A declaration plus a definition alone does not constitute wiring.
        assert len(references) >= 3, (name, 'missing caller or forward declaration')

    day = function(source, 'auto_gf_DayTransition_TriggerFunc')
    assert day.index('gf_JJResolve(') < day.index('gf_BHFeignDayMute(') < day.index('gf_ZJMorningDefer(') < day.index('gf_CheckEnd('), 'schedule announcement after revival/fake-death handling, before victory'
    assert 'TriggerExecute(gt_ZJMorning, false, false);' in function(source, 'gf_ZJMorningDefer')
    delayed = function(source, 'gt_ZJMorning_Func')
    assert delayed.index('Wait(1.5, c_timeGame);') < delayed.index('gf_ZJMorning();')
    defaults = function(source, 'gf_DefaultRoleOptions')
    default_lines = []
    for array, indices, value in (
        ('gv_bankSaveWeights', '[0][1][35]', '0.0'),
        ('gv_roleWeights', '[1][35]', '0.0'),
        ('gv_roleOptions', '[1][35][0]', 'false'),
        ('gv_roleOptions', '[1][35][1]', 'true'),
        ('gv_roleOptionAllowed', '[1][35][0]', 'true'),
        ('gv_roleOptionAllowed', '[1][35][1]', 'true'),
    ):
        line = f'{array}{indices} = {value};'
        assert line in defaults, ('wrong/missing bishop default', line)
        default_lines.append(line)

    assert 'gf_SKP_1_zhujiao(' in function(source, 'gf_SequencePrep')
    redirect = function(source, 'gf_SequenceBullshit')
    assert redirect.index('gf_SKU_1_zhujiao(') < redirect.index('gv_location[lv_a] = gv_visitation[lv_a]'), 'validate final visit before positions are frozen'
    kills = function(source, 'gf_SequenceKills')
    assert kills.index('gf_SKK_1_zhujiao(') < kills.index('gf_HLForesterNight('), 'support must precede subsequent night kills'
    night = function(source, 'auto_gf_NightTransition_TriggerFunc')
    expiry = []
    for name in ('gv_zjSupportDay', 'gv_zjSupportVotes'):
        matches = re.findall(r'^\s*' + name + r'\[lv_a\]\s*=\s*0\s*;', night, re.M)
        assert len(matches) == 1, (name, 'night must clear every player exactly once')
        expiry.append(matches[0].strip())

    getter = function(source, 'gf_BHVoteWeight')
    assert not re.search(r'gv_votes\[[^\]]+\]\s*=(?!=)', getter), 'getter changed base votes'
    print('PASS: dispatcher references, revival-before-announcement, night expiry, immutable base votes', flush=True)
    return ('void expireSupport(int lv_a) {\n' + '\n'.join(expiry) + '\n}\n'
            + 'void bishopDefaults() {\n' + '\n'.join(default_lines) + '\n}')


def random_wiring(source: str) -> list[str]:
    """Run both real town accumulation blocks and the bishop's real draw branch."""
    bodies = []
    for index, name in enumerate(('gf_OSGenerateChances', 'gf_OSRandomize')):
        body = function(source, name)
        marker = 'if ((lv_a == 1) && (lv_b >= 1) && (lv_b <= gv_townMax)) {'
        start = body.index(marker)
        block = body[start:balanced_end(body, body.index('{', start))]
        assert 'if ((lv_b == 34))' in block, 'town bound extension must not open medic random draws'
        bodies.append(f'void townCumulative{index}(int lv_b) {{\nint lv_a = 1;\n' + block + '\n}')

    matrix = function(source, 'gf_OSRandomizeMatrix')
    marker = 'if ((lv_y >= gv_finalWeights[1][34]) && (lv_y < gv_finalWeights[1][35])'
    start = matrix.index(marker)
    block = matrix[start:balanced_end(matrix, matrix.index('{', start))]
    assert 'gf_GKSetRoleField(lv_a, 0, 35);' in block
    bodies.append('void bishopDraw(int lv_x, fixed lv_y) {\nint lv_a = 1;\n' + block + '\n}')
    bodies.extend(function(source, name) for name in (
        'gf_BHRoleFitsKind', 'gf_BHListHas', 'gf_GKSetRoleField',
    ))
    return bodies


def harness(source: str, core: str, integrated: bool) -> str:
    bodies = [function(core, name) for name in CORE]
    bodies += [function(source, name) for name in HELPERS]
    night = function(source, 'auto_gf_NightTransition_TriggerFunc')
    match = re.search(r'if\s*\(\(gv_cooldown\[lv_a\]\s*>\s*0\)\)\s*\{', night)
    assert match, 'missing existing per-night cooldown decrement'
    cooldown = night[match.start():balanced_end(night, night.index('{', match.start()))]
    bodies.append('void advanceCooldown(int lv_a) {\n' + cooldown + '\n}')
    if integrated:
        bodies.append(integration(source))
        bodies.extend(random_wiring(source))

    # The real random draw writes through GKSetRoleField, including CJ role
    # cleanup. Add only absent bodies from its real recursive closure; existing
    # CORE/draft bodies and synthesized random/expiry wrappers stay untouched.
    roots = (*HELPERS, *(('gf_GKSetRoleField',) if integrated else ()))
    present = set(re.findall(r'^(?:void|bool|int|text)\s+(\w+)\s*\(', '\n'.join(bodies), re.M))
    for name in with_guoke_dependencies(source, roots):
        if name not in present:
            bodies.append(function(source, name))
            present.add(name)

    code = '\n\n'.join(bodies)
    assert not re.search(r'gv_votes\[[^\]]+\]\s*(?:[+*/-]?=(?!=)|\+\+|--)', code), 'support wrote base votes'
    code = re.sub(r'\b(int|bool|text|string)((?:\[\d+\])+)( +)(\w+)', r'\1\3\4\2', code)
    used = set(re.findall(r'\bgv_\w+', code)) | {
        'gv_votes', 'gv_roleOptions', 'gv_visitation2', 'gv_playerColor',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    if not integrated:
        for name, dims in (('gv_zjSupportDay', '[16]'), ('gv_zjSupportVotes', '[16]'),
                           ('gv_zjAnnouncedDay', '')):
            declarations.setdefault(name, f'int {name}{dims};')

    assert not used - declarations.keys(), ('missing globals', used - declarations.keys())
    globals_text = '\n'.join(declarations[n] for n in sorted(used))
    resets = '\n'.join(f'    clearValue({n});' for n in sorted(used))
    headers = '\n'.join(body.split('{', 1)[0] + ';' for body in bodies)
    defined = set(re.findall(r'^(?:void|bool|int) (\w+)\s*\(', code, re.M))
    calls = set(re.findall(r'\b(\w+)\s*\(', re.sub(r'//[^\n]*|"(?:\\.|[^"\\])*"', '', code)))
    natives = {
        'if', 'for', 'while', 'return', 'Color', 'SoundLink',
        'StringExternal', 'StringToText', 'IntToText', 'TextWithColor',
        'PlayerGroupSingle', 'PlayerGroupAll', 'PlayerGroupHasPlayer',
        'EventDialogControl', 'gf_CBSystemMessage', 'DialogControlSetVisible',
        'libNtve_gf_SetDialogItemChecked', 'libNtve_gf_SetDialogItemText',
        'libNtve_gf_SetDialogItemTooltip', 'libNtve_gf_SetDialogItemColor',
        'DialogControlSetSize', 'libNtve_gf_SetDialogItemImage',
        'libNtve_gf_SetDialogItemImage2', 'libNtve_gf_ConvertPlayerColorToColor',
    }
    assert not calls - defined - natives, ('new dependency needs deliberate stub', calls - defined - natives)
    strings = {k: v for k, v in load_strings().items() if k.startswith('Param/Value/ZJ')}
    string_rows = ',\n'.join('{' + json.dumps(k) + ',' + json.dumps(v, ensure_ascii=False) + '}'
                             for k, v in sorted(strings.items()))
    expiry_tests = r'''
    reset(); gv_roleOptions[1][35][0]=true; gv_roleOptions[1][35][1]=false;
    gv_bankSaveWeights[0][1][35]=7; gv_roleWeights[1][35]=7;
    bishopDefaults(); assert(!gv_roleOptions[1][35][0] && gv_roleOptions[1][35][1]);
    assert(gv_bankSaveWeights[0][1][35]==0 && gv_roleWeights[1][35]==0);
    assert(gv_roleOptionAllowed[1][35][0] && gv_roleOptionAllowed[1][35][1]); ++cases;
    reset(); support(1,2,3); morning(); assert(gf_BHVoteWeight(2)==3);
    for(int p=1;p<=15;++p) expireSupport(p);
    assert(gv_zjSupportDay[2]==0 && gv_zjSupportVotes[2]==0);
    assert(gf_BHVoteWeight(2)==1 && gv_votes[2]==1);
    ++cases;

    // Both preview and actual cumulative weights; medic stays excluded.
    for(int implementation=0;implementation<2;++implementation) for(fixed weight: {0.0,0.5,3.0}) {
        reset(); gv_townMax=35;
        gv_roleWeights[1][1]=2.0; gv_roleWeights[1][34]=900.0; gv_roleWeights[1][35]=weight;
        for(int role=1;role<=35;++role) {
            if(implementation==0) townCumulative0(role); else townCumulative1(role);
        }
        assert(gv_finalWeights[1][33]==2.0 && gv_finalWeights[1][34]==2.0 && gv_finalWeights[1][35]==2.0+weight);
        ++cases;
        for(int slot=1;slot<=23;++slot) for(int exclusions=0;exclusions<8;++exclusions) {
            gv_rolesArray[1]=slot;
            gv_roleOptions[4][1][2]=(exclusions&1)!=0; // All random: exclude Town.
            gv_roleOptions[4][2][1]=(exclusions&2)!=0; // Town random: exclude Government.
            gv_roleOptions[4][2][4]=(exclusions&4)!=0; // Town random: exclude Power.
            const bool eligible=slot==8 || (slot==1 && !(exclusions&1)) || (slot==2 && !(exclusions&4));
            assert(gf_BHRoleFitsKind(slot,1,35)==eligible);
            const fixed probes[]={2.0,2.0+weight/2,2.0+weight-1.0/4096,2.0+weight,2.0-1.0/4096};
            for(fixed roll:probes) {
                gv_roles[1][0]=0; gv_roles[1][1]=0;
                bishopDraw(1,roll);
                const bool drawn=eligible && roll>=2.0 && roll<2.0+weight;
                assert(gv_roles[1][0]==(drawn?35:0));
                assert(gv_roles[1][1]==(drawn?1:0));
            }
            ++cases;
        }
    }
    // Individual Power exclusions refer to other professions, not the whole pool.
    for(int exclusions=0;exclusions<16;++exclusions) {
        reset();
        for(int option=0;option<4;++option) gv_roleOptions[4][8][option]=(exclusions&(1<<option))!=0;
        gv_rolesArray[1]=8; gv_finalWeights[1][34]=2; gv_finalWeights[1][35]=3;
        assert(gf_BHRoleFitsKind(8,1,35));
        bishopDraw(1,2.5); assert(gv_roles[1][0]==35);
        assert(!gf_BHRoleFitsKind(4,1,17)); // Veteran is not Government either.
        assert(gf_BHRoleFitsKind(8,1,17)==!(exclusions&1));
        ++cases;
    }
''' if integrated else ''
    return r'''
#include <algorithm>
#include <cassert>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>
using std::string;
using text=string;
using playergroup=int;
using color=int;
using soundlink=int;
using fixed=double;
struct Message {string value; int recipient;};
std::vector<Message> messages;
std::map<std::pair<int,int>,bool> visible, checked;
std::map<std::pair<int,int>,string> labels;
std::map<string,string> strings={
''' + string_rows + r'''
};
int eventControl=0;
string StringExternal(string key) {assert(strings.count(key)); return strings.at(key);}
string StringToText(string s) {return s;}
string IntToText(int n) {return std::to_string(n);}
string TextWithColor(string s,int) {return s;}
int Color(double,double,double) {return 0;}
int SoundLink(string,int) {return 0;}
int libNtve_gf_ConvertPlayerColorToColor(int c) {return c;}
int PlayerGroupAll() {return 65534;}
int PlayerGroupSingle(int p) {assert(p>=1 && p<=15); return 1<<p;}
bool PlayerGroupHasPlayer(int g,int p) {assert(p>=1 && p<=15); return (g&(1<<p))!=0;}
int EventDialogControl() {return eventControl;}
void DialogControlSetVisible(int item,int group,bool value) {
    for(int p=1;p<=15;++p) if(PlayerGroupHasPlayer(group,p)) visible[{item,p}]=value;
}
void libNtve_gf_SetDialogItemChecked(int item,bool value,int group) {
    for(int p=1;p<=15;++p) if(PlayerGroupHasPlayer(group,p)) checked[{item,p}]=value;
}
void libNtve_gf_SetDialogItemText(int item,string value,int group) {
    for(int p=1;p<=15;++p) if(PlayerGroupHasPlayer(group,p)) labels[{item,p}]=value;
}
template<class... A> void libNtve_gf_SetDialogItemTooltip(A...) {}
template<class... A> void libNtve_gf_SetDialogItemColor(A...) {}
template<class... A> void DialogControlSetSize(A...) {}
template<class... A> void libNtve_gf_SetDialogItemImage(A...) {}
template<class... A> void libNtve_gf_SetDialogItemImage2(A...) {}
template<class... A> void gf_CBSystemMessage(string msg,int recipient,A...) {
    messages.push_back({msg,recipient});
}
template<class T> void clearValue(T &v) {v=T{};}
template<class T,size_t N> void clearValue(T (&v)[N]) {for(auto &x:v) clearValue(x);}
''' + globals_text + '\n' + headers + '\n' + code + r'''
void reset() {
''' + resets + r'''
    messages.clear(); visible.clear(); checked.clear(); labels.clear(); eventControl=0;
    gv_alivePlayers=PlayerGroupAll(); gv_currentPlayers=PlayerGroupAll();
    gv_dayNumber=4; gv_isNight=true; gv_zjAnnouncedDay=-1;
    gv_roleOptions[1][35][1]=true;
    gv_roleCategory=1; gv_roleSelection=35;
    for(int i=0;i<4;++i) {gv_roleOptShown[i]=i; gv_roleOptBox[i]=100+i;}
    gv_roleOptionAllowed[1][35][0]=true; gv_roleOptionAllowed[1][35][1]=true;
    for(int p=1;p<=15;++p) {
        gv_votes[p]=1; gv_number[p]=std::to_string(p+6); gv_name[p]="镇民"+std::to_string(p);
        gv_actionDialogItem[p][5]=200+p; gv_playerColor[p]=p;
    }
    gv_number[2]="9"; gv_name[2]="受助者";
}
bool isVisible(int target,int viewer=1) {return visible[{gv_actionDialogItem[target][5],viewer}];}
void pick(int p,int target) {gf_SKA_1_zhujiao(p,target); gf_SKP_1_zhujiao(p); gf_SKU_1_zhujiao(p);}
void support(int p,int target,int weight) {
    gv_roleOptions[1][35][0]=(weight==2); gf_ZJNormalizeOptions();
    pick(p,target); gf_SKK_1_zhujiao(p);
}
void morning() {++gv_dayNumber; gv_isNight=false; messages.clear(); gf_ZJMorning();}
string announcement(int p,int weight) {
    return gv_number[p]+"."+gv_name[p]+"获得了教区的支持！他在今天投下的票相当于"+std::to_string(weight)+"人。";
}
void checkNews(int target,int weight) {
    assert(!messages.empty());
    for(auto &m:messages) assert(m.value==announcement(target,weight));
}
int main() {
    int cases=0;
    reset(); assert(gf_ZJSupportWeight()==3);
    for(int bits=0;bits<4;++bits) {
        reset(); gv_roleOptions[1][35][0]=bits&1; gv_roleOptions[1][35][1]=bits&2;
        gf_ZJNormalizeOptions();
        assert(gv_roleOptions[1][35][0]!=gv_roleOptions[1][35][1]);
        assert(gf_ZJSupportWeight()==((bits&1)?2:3)); ++cases;
    }
    // Generic UI toggles the clicked bit first; bishop callback synchronizes its peer.
    for(int initial=0;initial<2;++initial) for(int bit=0;bit<2;++bit) for(int value=0;value<2;++value) {
        reset(); gv_roleOptions[1][35][0]=initial; gf_ZJNormalizeOptions();
        gv_roleOptions[1][35][bit]=value; eventControl=gv_roleOptBox[bit]; gf_ZJOptionClick();
        assert(gv_roleOptions[1][35][bit]==bool(value));
        assert(gv_roleOptions[1][35][1-bit]!=bool(value));
        for(int p=1;p<=15;++p) for(int j=0;j<2;++j)
            assert(checked.at({gv_roleOptBox[j],p})==gv_roleOptions[1][35][j]);
        ++cases;
    }
    for(int bad=0;bad<4;++bad) {
        reset(); eventControl=gv_roleOptBox[0];
        if(bad==0) gv_roleCategory=3;
        if(bad==1) gv_roleSelection=34;
        if(bad==2) eventControl=999;
        if(bad==3) gv_roleOptionAllowed[1][35][0]=false;
        gf_ZJOptionClick(); assert(checked.empty()); ++cases;
    }
    reset(); gv_alivePlayers &= ~PlayerGroupSingle(15); gf_RAZhujiaoActions(1);
    assert(!isVisible(1) && !isVisible(15) && isVisible(2));
    assert(labels.at({gv_actionDialogItem[2][5],1})==StringExternal("Param/Value/ZJSELECT"));
    gf_SKA_1_zhujiao(1,2); assert(gv_action[1][0]==2 && isVisible(1) && !isVisible(2));
    assert(messages.back().value==StringExternal("Param/Value/ZJPICK")+"9.受助者"+StringExternal("Param/Value/ZJPICKEND"));
    gf_SKA_1_zhujiao(1,3); assert(gv_action[1][0]==3 && isVisible(2) && !isVisible(3));
    gf_SKA_1_zhujiao(1,1); assert(gv_action[1][0]==0 && !isVisible(1));
    assert(messages.back().value==StringExternal("Param/Value/ZJOFF"));
    auto count=messages.size(); gf_SKA_1_zhujiao(1,1); assert(messages.size()==count);
    gf_SKA_1_zhujiao(1,15); assert(gv_action[1][0]==0); ++cases;
    // Invalid UI indices do not index player arrays; cooldown/jail/death reject clicks.
    for(int p: {-1,0,16}) {gf_SKA_1_zhujiao(p,2); gf_SKA_1_zhujiao(1,p);}
    for(int flag=0;flag<3;++flag) {
        reset();
        if(flag==0) gv_cooldown[1]=1;
        if(flag==1) gv_jailed[1]=3;
        if(flag==2) gv_alivePlayers &= ~PlayerGroupSingle(1);
        gf_SKA_1_zhujiao(1,2); assert(!gv_action[1][0]); ++cases;
    }
    for(int jailed=0;jailed<2;++jailed) {
        reset(); gf_RAZhujiaoActions(1); gv_cooldown[1]=jailed?0:1; gv_jailed[1]=jailed?3:0;
        gf_SKR_1_zhujiao(1); for(int p=1;p<=15;++p) assert(!isVisible(p));
        if(!jailed) assert(messages.back().value==StringExternal("Param/Value/ZJCOOLDOWN"));
        ++cases;
    }
    for(int target: {-1,0,1,16}) {
        reset(); gv_action[1][0]=target; gv_visitation[1]=8; gv_visitation2[1]=9;
        gf_SKP_1_zhujiao(1); assert(!gv_visitation[1] && !gv_visitation2[1]); ++cases;
    }
    // Inject bus/witch/deceiver final visitation, not a duplicate implementation of their engine.
    for(int redirected: {2,3,15}) {
        reset(); pick(1,2); assert(gv_visitation[1]==2); gv_visitation[1]=redirected;
        gf_SKU_1_zhujiao(1); gf_SKK_1_zhujiao(1);
        assert(gv_zjSupportVotes[redirected]==3 && gv_cooldown[1]==2);
        if(redirected!=2) assert(gv_zjSupportVotes[2]==0); ++cases;
    }
    for(int redirected: {-1,0,1,16}) {
        reset(); pick(1,2); gv_visitation[1]=redirected; gv_visitation2[1]=3;
        gf_SKU_1_zhujiao(1); gf_SKK_1_zhujiao(1);
        assert(!gv_visitation[1] && !gv_visitation2[1] && !gv_cooldown[1]); ++cases;
    }
    // All combinations: failure never spends cooldown; singleton cases identify each guard.
    for(int flags=0;flags<1024;++flags) {
        reset(); pick(1,2);
        if(flags&1) gv_cooldown[1]=1;
        if(flags&2) gv_jailed[1]=3;
        if(flags&4) gv_roleblocked[1]=3;
        if(flags&8) gv_e59CA8E5BC80party=true;
        if(flags&16) gv_diedAtNight[1]=true;
        if(flags&32) gv_veteraned[1]=true;
        if(flags&64) gv_alivePlayers &= ~PlayerGroupSingle(1);
        if(flags&128) gv_alivePlayers &= ~PlayerGroupSingle(2);
        if(flags&256) gv_diedAtNight[2]=true;
        if(flags&512) gv_visitation[1]=0;
        int cooldown=gv_cooldown[1]; gf_SKU_1_zhujiao(1); gf_SKK_1_zhujiao(1);
        assert(gv_cooldown[1]==(flags?cooldown:2));
        assert(gv_zjSupportVotes[2]==(flags?0:3));
        assert(gv_votes[2]==1); ++cases;
    }
    reset(); support(1,2,3); assert(gv_cooldown[1]==2);
    gv_isNight=false; ++gv_dayNumber; assert(gf_BHVoteWeight(2)==3);
    gv_isNight=true; advanceCooldown(1); assert(gv_cooldown[1]==1 && gf_BHVoteWeight(2)==1);
    pick(1,3); gf_SKK_1_zhujiao(1); assert(gv_cooldown[1]==1 && gv_zjSupportVotes[3]==0);
    ++gv_dayNumber; advanceCooldown(1); assert(gv_cooldown[1]==0);
    pick(1,3); gf_SKK_1_zhujiao(1); assert(gv_zjSupportVotes[3]==3 && gv_cooldown[1]==2); ++cases;
    // Multiple providers establish max, not sum; announcements are target-deduplicated.
    for(int first: {2,3}) for(int second: {2,3}) {
        reset(); support(1,2,first); support(15,2,second);
        assert(gv_zjSupportVotes[2]==std::max(first,second));
        assert(gv_cooldown[1]==2 && gv_cooldown[15]==2);
        gv_alivePlayers &= ~PlayerGroupSingle(1); // Provider dies after executing.
        gv_currentPlayers &= ~PlayerGroupSingle(14); // Disconnected viewer excluded, dead viewer included.
        morning(); checkNews(2,std::max(first,second)); assert(messages.size()==14);
        int seen[16]={}; for(auto &m:messages) ++seen[m.recipient];
        assert(seen[1]==1 && seen[14]==0); for(int p=1;p<=15;++p) assert(seen[p]==(p!=14));
        auto n=messages.size(); gf_ZJMorning(); assert(messages.size()==n); ++cases;
    }
    for(int revived=0;revived<2;++revived) {
        reset(); support(1,2,3); gv_diedAtNight[2]=true; gv_alivePlayers &= ~PlayerGroupSingle(2);
        if(revived) gv_alivePlayers |= PlayerGroupSingle(2); // Medic resolves before morning.
        morning();
        if(revived) {checkNews(2,3); assert(gf_BHVoteWeight(2)==3);}
        else {
            assert(messages.empty() && !gv_zjSupportDay[2] && !gv_zjSupportVotes[2]);
            assert(gf_BHVoteWeight(2)==1); // Even fake-death trial cannot retain support.
        }
        ++cases;
    }
    reset(); support(1,2,3); support(15,3,3); morning(); assert(messages.size()==30);
    int targets[4]={};
    for(auto &m:messages) {if(m.value==announcement(2,3)) ++targets[2]; else {assert(m.value==announcement(3,3)); ++targets[3];}}
    assert(targets[2]==15 && targets[3]==15); ++cases;
    // Exhaustively preserve <=0 base votes, mayor/admin weights, night/day mismatch and expiry.
    for(int base=-2;base<=5;++base) for(int bonus: {2,3}) for(int delta=-1;delta<=1;++delta) for(int nightFlag=0;nightFlag<2;++nightFlag) {
        reset(); gv_votes[2]=base; gv_zjSupportDay[2]=gv_dayNumber+delta; gv_zjSupportVotes[2]=bonus;
        gv_isNight=nightFlag;
        int expected=base>0 && !nightFlag && !delta ? std::max(base,bonus):base;
        assert(gf_BHVoteWeight(2)==expected && gv_votes[2]==base);
        assert(gv_zjSupportVotes[2]==bonus); ++cases;
    }
    reset(); for(int p: {-1,0,16}) assert(gf_BHVoteWeight(p)==0);
    for(int base: {1,2,4}) {
        reset(); gv_votes[2]=base; support(1,2,3); morning();
        checkNews(2,std::max(base,3));
        assert(gf_BHVoteWeight(2)==std::max(base,3) && gv_votes[2]==base);
        ++gv_dayNumber; assert(gf_BHVoteWeight(2)==base && gv_votes[2]==base); ++cases;
    }
''' + expiry_tests + r'''
    std::cout << "PASS: " << cases << " bishop cases; actual bodies, options/UI, redirect, blockers, cooldown, max/non-persistence, death/revival, exact morning messages" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--core', type=Path, help='explicit draft core; skips integration checks')
    args = parser.parse_args()
    source = args.script.read_text(encoding='utf-8')
    core = args.core.read_text(encoding='utf-8') if args.core else source
    if args.core:
        print(f'DRAFT CORE ONLY: {args.core}; integration not tested', flush=True)

    cpp_source = harness(source, core, integrated=args.core is None)
    with tempfile.TemporaryDirectory(prefix='bh-bishop-tests-') as tmp:
        cpp, exe = Path(tmp) / 'bishop.cpp', Path(tmp) / 'bishop'
        cpp.write_text(cpp_source, encoding='utf-8')
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
