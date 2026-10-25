#!/usr/bin/env python3
"""Execute the integrated faction-conversion Galaxy, not a Python reimplementation.

Uses test_egun.function/translate; compiles actual conversion, UI/chat helpers,
solo command,狸猫 exchange, sheriff, CheckEnd, and all three faction ET bodies.
Every ET winner expression is also extracted from its actual award branch.
Only engine/presentation boundaries are doubles. CheckEnd's first population
loop is instrumented AFTER it completes to expose its actual local counters;
4,000 seeded populations are checked against an independent classification oracle
and an effective-identity materialization metamorphic test. Galaxy implicit local
zero initialization and null text are translated explicitly. Not an SC2 engine,
Galaxy compiler, multiplayer, rendering, or bank persistence integration test.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

from test_egun import SCRIPT, function, mask, translate

NAMES = (
    'gf_BHConverted', 'gf_BHFaction', 'gf_BHRoleName', 'gf_BHDeathName',
    'gf_BHFactionCard', 'gf_BHRefreshFactionChat', 'gf_BHConvertFaction',
    'gt_BHFaction_Func', 'gt_BHFaction_Init', 'gf_LMCat', 'gf_LMRole',
    'gf_LMJoin', 'gf_LMFinder', 'gf_LMSwap', 'gf_LMResolve',
    'gf_GSChatReady', 'gf_JSIs', 'gf_JSWon', 'gf_EGWon', 'gf_XRGangShare',
    'gf_CheckEnd', 'gf_SKF_1_jingzhang',
    'gf_ETTownWin', 'gf_ETMafiaWin', 'gf_ETTriadWin', 'gf_BHFactionReset',
)
# Pre-conversion profession investigation body, fixed at the implementation start.
INVESTIGATOR_SHA256 = '8e2a4c5c121b49b6757fdafe4e045c7afbe862b8ee473ab719d893b0937b0ee2'


def block_end(source: str, brace: int) -> int:
    live = mask(source)
    assert live[brace] == '{'
    depth, end = 1, brace + 1
    while depth:
        assert end < len(live), 'unbalanced source block'
        depth += (live[end] == '{') - (live[end] == '}')
        end += 1

    return end


def calls(source: str) -> set[str]:
    return set(re.findall(r'\b(\w+)\s*\(', mask(source))) - {
        'if', 'for', 'while', 'return', 'else',
    }


def integration(source: str) -> list[tuple[str, str]]:
    live = mask(source)
    for name in ('gv_bhFaction', 'gv_lmFaction'):
        declaration = re.search(r'^int\[16\]\s+' + name + r'\s*;', live, re.M)
        assert declaration, ('missing actual int[16] declaration', name)
        assert declaration.start() + declaration[0].index(name) == live.index(name), ('global used before declaration', name)

    assert re.search(r'^trigger\s+gt_BHFaction\s*;', live, re.M)
    assert re.search(r'^const bool c_bhSoloBuild\s*=\s*false\s*;', live, re.M), 'source must remain non-solo'
    for name in NAMES[:9]:
        signature = function(source, name).split('{', 1)[0].strip()
        assert signature + ';' in source, ('missing forward declaration', name)

    init = function(source, 'gt_BHFaction_Init')
    assert 'TriggerCreate("gt_BHFaction_Func")' in init
    assert re.search(r'TriggerAddEventChatMessage\(gt_BHFaction,\s*c_playerAny,\s*"-faction",\s*false\)', init)
    assert re.search(r'^\s+gt_BHFaction_Init\(\);', live, re.M), 'event never initialized'

    conversion = mask(function(source, 'gf_BHConvertFaction'))
    permitted = {
        'gf_BHFaction', 'PlayerGroupHasPlayer', 'gf_BHFactionCard',
        'gf_RefreshRoleBox', 'gf_BHRefreshFactionChat', 'gf_GSRefreshChat',
        'gf_RTRoleCard',  # FZ needs its true profession rendered, never role setup.
        'gf_CBSystemMessage', 'StringExternal', 'SoundLink', 'Color',
    }
    conversion_calls = calls(conversion[conversion.index('{') + 1:])
    assert not conversion_calls - permitted, ('conversion calls role setup or unknown side effect', conversion_calls - permitted)
    for name in ('gv_roles', 'gv_originalRole', 'gv_shots', 'gv_cooldown',
                 'gv_action', 'gv_visitation', 'gv_visitation2'):
        assert not re.search(r'\b' + name + r'(?:\[[^\]\n]+\])+\s*(?:[+*/-]?=(?!=)|\+\+|--)', conversion), ('profession-state write', name)

    flag = re.search(r'^bool\s+gv_bhFactionChatOpen\s*=\s*false\s*;', live, re.M)
    assert flag and flag.start() + flag[0].index('gv_bhFactionChatOpen') == live.index('gv_bhFactionChatOpen'), 'chat-window flag must be declared before first use and default closed'
    night = mask(function(source, 'auto_gf_NightTransition_TriggerFunc'))
    opening, closing = night.index('gv_bhFactionChatOpen = true;'), night.index('gv_bhFactionChatOpen = false;')
    clear = night.index('auto1D25B969_g = gv_currentPlayers;')
    wait = re.search(r'Wait\(2\.0,\s*c_timeGame\)', night[clear:])
    assert opening < night.index('gf_FZRefreshActions();') < night.index('gf_BHRefreshFactionChat();') < closing < clear, 'actual night chat open/close must bracket FZ/faction refresh and precede channel clear'
    assert wait, 'night close timing changed; inspect actual Wait(2.0) gap'
    assert 'gv_bhFactionChatOpen = false;' in mask(function(source, 'gf_BHFactionReset'))
    assert re.search(r'if \(\(gv_roles\[lp_player\]\[0\] == 33\)\) \{\s*gf_RTRoleCard\(lp_player\);\s*}\s*else \{\s*gf_BHFactionCard\(lp_player\);\s*}', conversion), 'only FZ must re-render its true profession card instead of applying the limited overlay'
    assert len(re.findall(r'\bgf_RTRoleCard\(', conversion)) == 1
    print('PASS: actual chat-window declaration/reset, opening before FZ refresh, closing before channel clear/Wait(2.0), and FZ-only render dispatch', flush=True)

    card = mask(function(source, 'gf_BHFactionCard'))
    rows = re.findall(r'gv_roleBoxText\[lp_player\]\[(\d+)\]\s*=(?!=)', card)
    assert set(rows) == {'0', '3', '6'}, ('card may only write alignment/goal/win rows', rows)
    investigator = function(source, 'gf_SKF_1_tanyuan')
    assert hashlib.sha256(investigator.encode()).hexdigest() == INVESTIGATOR_SHA256, 'profession investigation must remain byte-identical'
    sheriff = mask(function(source, 'gf_SKF_1_jingzhang'))
    assert 'gf_BHFaction(gv_visitation[lv_a])' in sheriff, 'sheriff must query target alignment'
    assert not re.search(r'gv_roles\[gv_visitation\[lv_a\]\]\[1\]\s*==\s*[25]\b', sheriff)

    predicates = []
    for name in re.findall(r'^void (gf_ET\w+)\s*\([^;{}]*\)\s*\{', live, re.M):
        body = function(source, name)
        if not re.search(r'gv_won\[lv_a\]\s*=\s*true;', mask(body)):
            continue

        branches = list(re.finditer(r'\bif\s*(\([^\n{]+gf_EGWon\([^\n{]+)\s*\{', body))
        assert len(branches) == 1, ('missing/ambiguous actual winner branch', name)
        branch = branches[0]
        brace = body.index('{', branch.start())
        end = block_end(body, brace)
        assert re.search(r'gv_won\[lv_a\]\s*=\s*true;', body[brace:end]), name
        assert re.match(r'\s*else\s*\{', body[end:]), ('winner lacks original losing branch', name)
        predicates.append((name, f'bool award_{name}(int lv_a) {{ int lv_ci=0, lv_shw=0, lv_tx=0; return {branch[1]}; }}'))

    assert len(predicates) == 25, ('ET qualification coverage changed; review new entries', len(predicates))
    print('PASS: declarations/forward references, solo event registration, conversion side-effect allowlist, card rows 0/3/6, unchanged investigator, sheriff target faction, 25 actual ET award expressions', flush=True)
    return predicates


def harness(source: str) -> str:
    predicates = integration(source)
    bodies = [function(source, name) for name in NAMES]
    end_index = NAMES.index('gf_CheckEnd')
    end_body = bodies[end_index]
    # Observe actual counters after the first player loop, never alter a guard,
    # counter update, winning expression, or executable Galaxy statement.
    population_loop = end_body.rfind('for ', 0, end_body.index('lv_x[10] += 1;'))
    assert population_loop >= 0
    brace = end_body.index('{', population_loop)
    end = block_end(end_body, brace)
    bodies[end_index] = end_body[:end] + '\n    captureCounts(lv_x, lv_eg);\n' + end_body[end:]

    code = '\n\n'.join(bodies + [body for _, body in predicates])
    used = set(re.findall(r'\bgv_\w+', mask(code))) | {
        'gv_roles', 'gv_originalRole', 'gv_shots', 'gv_cooldown', 'gv_action',
        'gv_visitation', 'gv_visitation2', 'gv_bhFaction', 'gv_lmFaction',
        'gv_lmWin', 'gv_currentPlayers', 'gv_alivePlayers', 'gv_players',
        'gv_playerSpot', 'gv_gsHost',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not used - declarations.keys(), ('missing actual global declarations', used - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(used))
    resets = '\n'.join(f'    clearValue({name});' for name in sorted(used))
    snapshots = '\n'.join(f'    appendValue(result, {name});' for name in sorted(used))
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    code = translate(code)
    code = re.sub(r'\bnull\b', 'text{}', code)
    code = re.sub(r'^(\s+(?:int|bool|text|string|playergroup)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', code, flags=re.M)
    supported = {
        'captureCounts', 'PlayerGroupHasPlayer', 'PlayerGroupCount',
        'PlayerGroupAll', 'PlayerGroupSingle', 'PlayerGroupNextPlayer',
        'StringExternal', 'StringToText', 'IntToString', 'IntToText', 'StringToInt',
        'StringWord', 'EventChatMessage', 'EventPlayer', 'TextWithColor',
        'libNtve_gf_ConvertPlayerColorToColor', 'Color', 'SoundLink',
        'TriggerCreate', 'TriggerAddEventChatMessage', 'gf_CBSystemMessage',
        'gf_CBAssignUnassignChatChannel', 'gf_CBAllowDisallowChatting',
        'gf_RefreshRoleBox', 'gf_GSRefreshChat', 'gf_RTRoleCard',
        'gf_RTMakeWinList', 'gf_DQSeenName', 'gf_GSIs', 'gf_GSShareWin',
        'SoundPlay', 'Wait', 'gf_DEBUG', 'gf_FlashScreen', 'gf_GiveBonus',
        'gf_WinScreen', 'PlayerName', 'libNtve_gf_ShowHideUnit', 'ActorSend',
        'TextTagShow', 'libNtve_gf_SetDialogItemText',
        'libNtve_gf_SetDialogItemImage2', 'libNtve_gf_SetDialogItemImage',
    }
    defined = set(NAMES) | {'award_' + name for name, _ in predicates}
    unknown_calls = calls(code) - defined - supported - {'text'}
    assert not unknown_calls, ('unstubbed actual call', unknown_calls)
    predicate_array = ',\n'.join('{"' + name + '", award_' + name + '}' for name, _ in predicates)
    print(f'Extracted {len(bodies)} complete actual functions, {len(predicates)} actual ET expressions, {len(used)} actual globals; no conversion/population/winner stubs', flush=True)

    return r'''
#include <algorithm>
#include <array>
#include <climits>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
using std::string;
using text = string;
using playergroup = unsigned int;
using soundlink = string;
using unit = int;
using actor = int;
using trigger = int;
using fixed = double;
constexpr int c_playerAny=-1, ge_Clear_DoNotClear=0, ge_Allow_Allow=1, c_timeGame=0;
// Mutable engine double for the build-time constant: exercise both packaged modes.
bool c_bhSoloBuild=false;
trigger gt_BHFaction=0;
int checks=0, fixtures=0;
string context;
#define CHECK(...) do { ++checks; if(!(__VA_ARGS__)) { std::cerr << "FAIL [" << context << "] line " << __LINE__ << ": " << #__VA_ARGS__ << '\n'; std::abort(); } } while(0)
''' + globals_text + r'''
struct Message { string value; int target, sender; };
std::vector<Message> messages;
std::vector<string> events;
std::vector<std::pair<int,int>> assignments;
std::map<int,int> channels;
std::vector<int> allows;
int observedCounts[31]{}, observedEgun=0, eventPlayer=1;
string eventMessage;

void captureCounts(const int (&values)[31], int egun) {
    std::copy(std::begin(values),std::end(values),observedCounts); observedEgun=egun;
}
template<class T> void clearValue(T& value) { value=T{}; }
template<class T, size_t N> void clearValue(T (&values)[N]) { for(auto& value:values) clearValue(value); }
void appendValue(string& out,const string& value) { out+=std::to_string(value.size())+":"+value+";"; }
template<class T> void appendValue(string& out,const T& value) { out+=std::to_string(value)+";"; }
template<class T,size_t N> void appendValue(string& out,const T (&values)[N]) { for(const auto& value:values) appendValue(out,value); }
string state() {
    string result;
''' + snapshots + r'''
    return result;
}
string professionState() {
    string result;
    appendValue(result,gv_roles); appendValue(result,gv_originalRole);
    appendValue(result,gv_shots); appendValue(result,gv_cooldown);
    appendValue(result,gv_action); appendValue(result,gv_visitation); appendValue(result,gv_visitation2);
    return result;
}
bool PlayerGroupHasPlayer(playergroup group,int p) { CHECK(p>=1 && p<=15); return (group&(1u<<p))!=0; }
int PlayerGroupCount(playergroup group) { return __builtin_popcount(group); }
playergroup PlayerGroupAll() { return 65534; }
playergroup PlayerGroupSingle(int p) { CHECK(p>=1 && p<=15); return 1u<<p; }
int PlayerGroupNextPlayer(playergroup group,int p) {
    for(int n=std::max(1,p+1);n<=15;++n) if(group&(1u<<n)) return n;
    return -1;
}
text StringExternal(string key) { return "{"+key+"}"; }
text StringToText(string value) { return value; }
string IntToString(int value) { return std::to_string(value); }
text IntToText(int value) { return std::to_string(value); }
int StringToInt(string value) { try { return std::stoi(value); } catch(...) { return 0; } }
string StringWord(string value,int index) {
    CHECK(index>=1); std::istringstream stream(value); string word;
    for(int i=1;i<=index;++i) if(!(stream>>word)) return "";
    return word;
}
string EventChatMessage(bool value) { CHECK(!value); return eventMessage; }
int EventPlayer() { return eventPlayer; }
int Color(double r,double g,double b) { return int(std::lround(r))*1000000+int(std::lround(g))*1000+int(std::lround(b)); }
text TextWithColor(text value,int color) { return "<c="+std::to_string(color)+">"+value+"</c>"; }
int libNtve_gf_ConvertPlayerColorToColor(int color) { return color; }
soundlink SoundLink(string name,int index) { CHECK(index==-1); return name; }
text PlayerName(int p) { return "P"+std::to_string(p); }
void gf_CBSystemMessage(text value,int target,int sender,int,int,int) = delete;
void gf_CBSystemMessage(text value,int target,int sender,int mode,soundlink,int) {
    CHECK(target>=1 && target<=15 && mode==0); messages.push_back({value,target,sender}); events.push_back("message");
}
void gf_CBAssignUnassignChatChannel(int p,int channel,int clear) {
    CHECK(p>=1 && p<=15 && clear==ge_Clear_DoNotClear);
    assignments.emplace_back(p,channel); channels[p]=channel; events.push_back("channel");
}
void gf_CBAllowDisallowChatting(int p,int allow) { CHECK(p>=1 && p<=15 && allow==ge_Allow_Allow); allows.push_back(p); events.push_back("allow"); }
void gf_RefreshRoleBox() { events.push_back("refresh"); }
void gf_GSRefreshChat() { events.push_back("gs-refresh"); }
void gf_RTRoleCard(int p) { CHECK(p>=1 && p<=15); events.push_back("role-card"); }
text gf_RTMakeWinList(int pool,int role) { return "WIN:"+std::to_string(pool)+":"+std::to_string(role); }
text gf_DQSeenName(int p) { CHECK(p>=1 && p<=15); events.push_back("dq-name"); return "DQ:"+std::to_string(p); }
bool gf_GSIs(int) { return false; } // isolate faction ET, symbiote sharing has its own actual-body suite
void gf_GSShareWin(string image) { events.push_back("gs-win:"+image); }
trigger TriggerCreate(string name) { events.push_back("trigger:"+name); return 701; }
void TriggerAddEventChatMessage(trigger handle,int player,string command,bool exact) {
    CHECK(handle==701 && player==c_playerAny && command=="-faction" && !exact); events.push_back("chat-event");
}
template<class... T> void SoundPlay(T...) {}
template<class... T> void Wait(T...) {}
template<class... T> void gf_DEBUG(T...) {}
template<class... T> void gf_FlashScreen(T...) {}
void gf_GiveBonus(int p,int points) { events.push_back("bonus:"+std::to_string(p)+":"+std::to_string(points)); }
void gf_WinScreen(string image,int p) { events.push_back("win:"+image+":"+std::to_string(p)); }
template<class... T> void libNtve_gf_ShowHideUnit(T...) {}
template<class... T> void ActorSend(T...) {}
template<class... T> void TextTagShow(T...) {}
template<class... T> void libNtve_gf_SetDialogItemText(T...) {}
template<class... T> void libNtve_gf_SetDialogItemImage2(T...) {}
template<class... T> void libNtve_gf_SetDialogItemImage(T...) {}
''' + headers + '\n' + code + r'''
void clearEffects() { messages.clear(); events.clear(); assignments.clear(); allows.clear(); }
void role(int p,int pool,int number) { gv_roles[p][1]=pool; gv_roles[p][0]=number; }
void reset(string label,int players=15) {
''' + resets + r'''
    context=label; ++fixtures; clearEffects(); channels.clear(); c_bhSoloBuild=false;
    gt_BHFaction=0; eventPlayer=1; eventMessage="";
    gv_gameStarted=true;
    for(int p=1;p<=15;++p) {
        role(p,1,1); gv_originalRole[p][1]=1; gv_originalRole[p][0]=1;
        gv_playerSpot[p]=16-p; gv_name[p]="P"+std::to_string(p); gv_playerColor[p]=p;
        gv_shots[p]=p+3; gv_cooldown[p]=p%3;
        gv_action[p][0]=16-p; gv_action[p][1]=p;
        gv_visitation[p]=16-p; gv_visitation2[p]=p;
        if(p<=players) { gv_alivePlayers|=1u<<p; gv_currentPlayers|=1u<<p; gv_players|=1u<<p; }
        for(int row=0;row<11;++row) gv_roleBoxText[p][row]="ROW:"+std::to_string(p)+":"+std::to_string(row);
    }
    for(int pool=0;pool<9;++pool) for(int id=0;id<41;++id)
        gv_roleNameArray[pool][id]="PROF:"+std::to_string(pool)+":"+std::to_string(id);
}
int eventCount(string value) { return std::count(events.begin(),events.end(),value); }
bool hasMessage(int p,string key) {
    return std::any_of(messages.begin(),messages.end(),[&](const Message& m) { return m.target==p && m.value.find("{Param/Value/"+key+"}")!=string::npos; });
}
void testQueries() {
    reset("faction helper Cartesian cases");
    for(int p:{1,8,15}) for(int pool=0;pool<=8;++pool) for(int id=0;id<=40;++id) for(int faction:{-1,0,1,2,3,5,9}) {
        role(p,pool,id); gv_bhFaction[p]=faction;
        bool converted=pool==1 && (faction==2 || faction==5);
        CHECK(gf_BHConverted(p)==converted); CHECK(gf_BHFaction(p)==(converted?faction:pool));
        CHECK(gf_LMCat(p)==(converted?faction:pool)); CHECK(gf_LMRole(p)==(converted?0:id));
        string expected=converted?TextWithColor(StringExternal("Param/Value/BHFROLE"+std::to_string(id)),Color(faction==2?100:20,faction==2?0:40,faction==2?0:100)):gv_roleNameArray[pool][id];
        CHECK(gf_BHRoleName(p)==expected);
    }
    for(int invalid:{INT_MIN,-1,0,16,INT_MAX}) {
        CHECK(!gf_BHConverted(invalid)); CHECK(gf_BHFaction(invalid)==0); CHECK(gf_BHRoleName(invalid).empty());
    }
    reset("death name preserves disguise unless converted");
    role(1,1,34); CHECK(gf_BHDeathName(1)=="DQ:1"); CHECK(eventCount("dq-name")==1);
    gv_bhFaction[1]=2; clearEffects(); CHECK(gf_BHDeathName(1)==gf_BHRoleName(1)); CHECK(events.empty());
    role(1,3,21); clearEffects(); CHECK(gf_BHDeathName(1)=="DQ:1");
}
void reject(int p,int team) {
    string before=state(); clearEffects(); CHECK(!gf_BHConvertFaction(p,team)); CHECK(state()==before); CHECK(events.empty() && messages.empty());
}
void testConversionGuardsAndState() {
    for(int p:{1,8,15}) for(int team:{2,5}) for(int id=1;id<=35;++id) {
        reset("all town professions and side-effect preservation"); role(p,1,id);
        if(id==28 || id==29) { reject(p,team); continue; }
        string before=professionState(); CHECK(gf_BHConvertFaction(p,team));
        CHECK(professionState()==before && gf_BHFaction(p)==team && gf_LMRole(p)==0);
        CHECK(eventCount("refresh")==1 && eventCount("gs-refresh")==1 && eventCount("role-card")==int(id==33));
        CHECK(messages.size()==1 && hasMessage(p,team==2?"BHFJOIN2":"BHFJOIN5")); CHECK(messages[0].sender==p);
        CHECK(assignments.empty());
        for(int other=1;other<=15;++other) for(int row=0;row<11;++row) {
            if(other==p && (row==0 || row==3 || row==6)) continue;
            CHECK(gv_roleBoxText[other][row]=="ROW:"+std::to_string(other)+":"+std::to_string(row));
        }
        // Full FZ rendering is an explicit presentation double here; its actual
        // renderer/true-profession card is exercised by the identity UI suite.
        if(id!=33) {
            CHECK(gv_roleBoxText[p][3]==StringExternal(team==2?"Param/Value/BHFGOAL2":"Param/Value/BHFGOAL5"));
            CHECK(gv_roleBoxText[p][6]=="WIN:"+std::to_string(team)+":0");
        }
        reject(p,team); reject(p,team==2?5:2);
    }
    for(int invalid:{INT_MIN,-1,0,16,INT_MAX}) { reset("invalid player"); reject(invalid,2); }
    for(int team:{INT_MIN,-1,0,1,3,4,6,INT_MAX}) { reset("invalid faction"); reject(1,team); }
    for(int pool:{0,2,3,4,5,6,7,8}) for(int id=1;id<=40;++id) { reset("non-town cannot convert"); role(1,pool,id); reject(1,2); reject(1,5); }
    for(int id:{INT_MIN,-1,0,28,29,36,40,INT_MAX}) { reset("unsupported profession"); role(1,1,id); reject(1,2); }
    for(int guard=0;guard<6;++guard) {
        reset("lifecycle/current/alive/feign guards");
        if(guard==0) gv_gameStarted=false;
        if(guard==1) gv_gameOver=true;
        if(guard==2) gv_nightProcessingPhase=true;
        if(guard==3) gv_currentPlayers&=~(1u<<1);
        if(guard==4) gv_alivePlayers&=~(1u<<1);
        if(guard==5) gv_bhFeignRole[1]=12;
        reject(1,2); reject(1,5);
    }
}
void testChat() {
    for(int team:{2,5}) for(int guard=0;guard<10;++guard) {
        reset("night chat eligibility, stale channel removal"); role(8,1,14); gv_bhFaction[8]=team; gv_isNight=true; gv_bhFactionChatOpen=true;
        channels[8]=2; channels[7]=3;
        if(guard==1) gv_jailed[8]=1;
        if(guard==2) gv_jailing[8]=1;
        if(guard==3) gv_privateChannel[8]=7;
        if(guard==4) gv_silenced[8][0]=true;
        if(guard==5) gv_alivePlayers&=~(1u<<8);
        if(guard==6) gv_currentPlayers&=~(1u<<8);
        if(guard==7) gv_bhFeignRole[8]=12;
        if(guard==8) gv_nightProcessingPhase=true;
        if(guard==9) gv_gameOver=true;
        gf_BHRefreshFactionChat(); CHECK(channels[7]==3);
        if(guard>=8) { CHECK(assignments.empty() && allows.empty() && channels[8]==2); continue; }
        CHECK(!assignments.empty() && assignments[0]==std::make_pair(8,0));
        if(guard==0) { CHECK(channels[8]==(team==2?1:4)); CHECK(allows==std::vector<int>{8}); }
        else { CHECK(channels[8]==0 && allows.empty()); }
    }
    reset("daytime chat untouched"); gv_bhFaction[8]=2; gf_BHRefreshFactionChat(); CHECK(events.empty());
    reset("successful night conversion updates faction chat"); gv_isNight=true; gv_bhFactionChatOpen=true; role(8,1,7);
    CHECK(gf_BHConvertFaction(8,5)); CHECK(channels[8]==4 && allows==std::vector<int>{8});
}
void testClosedNightWindow() {
    for(int team:{2,5}) for(bool phase:{false,true}) {
        reset("night channels already cleared, including before phase flag flips");
        gv_isNight=true; gv_bhFactionChatOpen=false; gv_nightProcessingPhase=phase;
        role(8,1,14); gv_bhFaction[8]=team; channels[8]=0;
        string before=state(); gf_BHRefreshFactionChat();
        CHECK(state()==before && assignments.empty() && allows.empty() && events.empty());
        CHECK(channels[8]==0);
        reject(9,team); CHECK(channels[8]==0);
    }
    reset("faction reset closes chat and clears both inherited identities");
    gv_bhFactionChatOpen=true;
    for(int p=1;p<=15;++p) { gv_bhFaction[p]=2; gv_lmFaction[p]=5; }
    gf_BHFactionReset(); CHECK(!gv_bhFactionChatOpen);
    for(int p=1;p<=15;++p) CHECK(gv_bhFaction[p]==0 && gv_lmFaction[p]==0);
}
void testCommand() {
    reset("event registration"); gt_BHFaction_Init(); CHECK(gt_BHFaction==701);
    CHECK(events==std::vector<string>({"trigger:gt_BHFaction_Func","chat-event"}));
    for(string command:{"-faction mafia","-faction triad","-faction 15 mafia","-faction 15 triad"}) {
        reset("non-solo command must be entirely silent"); eventMessage=command; string before=state();
        CHECK(!gt_BHFaction_Func(true,true)); CHECK(!gt_BHFaction_Func(false,true));
        CHECK(state()==before && events.empty());
    }
    for(int team:{2,5}) for(bool bySeat:{false,true}) {
        reset("solo command and displayed-seat resolution"); c_bhSoloBuild=true; eventPlayer=8;
        int target=bySeat?3:8; eventMessage="-faction "+string(bySeat?"13 ":"")+(team==2?"mafia":"triad");
        string before=state(); CHECK(gt_BHFaction_Func(true,false)); CHECK(state()==before && events.empty());
        CHECK(gt_BHFaction_Func(false,true)); CHECK(gv_bhFaction[target]==team); CHECK(gv_bhFaction[bySeat?13:3]==0);
        CHECK(hasMessage(target,team==2?"BHFJOIN2":"BHFJOIN5")); CHECK(hasMessage(8,"BHFDONE"));
    }
    for(string command:{"-faction","-faction town","-faction 0 mafia","-faction 16 triad","-faction 01 mafia","-faction garbage mafia","-faction mafia extra","-faction 15 mafia extra"}) {
        reset("solo malformed command cannot convert"); c_bhSoloBuild=true; eventMessage=command; string before=professionState();
        CHECK(!gt_BHFaction_Func(false,true)); CHECK(professionState()==before);
        for(int p=1;p<=15;++p) CHECK(gv_bhFaction[p]==0);
    }
    for(int guard=0;guard<3;++guard) {
        reset("solo command lifecycle guard"); c_bhSoloBuild=true; eventMessage="-faction mafia";
        if(guard==0) gv_gameStarted=false;
        if(guard==1) gv_gameOver=true;
        if(guard==2) gv_nightProcessingPhase=true;
        string before=state(); CHECK(!gt_BHFaction_Func(false,true)); CHECK(state()==before);
    }
}
void testLimao() {
    for(int team:{2,5}) for(int id:{1,4,14,31,34,35}) {
        reset("limao profession and alignment snapshot inheritance");
        role(1,3,24); role(8,1,id); gv_bhFaction[8]=team;
        gv_lmMark[1]=8; gv_alivePlayers&=~(1u<<8);
        int shots=gv_shots[8],cooldown=gv_cooldown[8];
        gv_originalRole[1][1]=3; gv_originalRole[1][0]=24;
        gv_lmFaction[1]=5; // stale victory snapshot must be cleared on acquiring identity
        gf_LMResolve();
        CHECK(gv_roles[1][1]==1 && gv_roles[1][0]==id && gv_bhFaction[1]==team);
        CHECK(gf_BHFaction(1)==team && gf_LMCat(1)==team && gf_LMRole(1)==0);
        CHECK(gv_shots[1]==shots && gv_cooldown[1]==cooldown);
        CHECK(gv_lmWin[8][1]==1 && gv_lmWin[8][0]==id && gv_lmFaction[8]==team);
        CHECK(gv_roles[8][1]==3 && gv_roles[8][0]==24 && gv_bhFaction[8]==0);
        CHECK(gf_LMCat(8)==team && gf_LMRole(8)==0);
        CHECK(gv_lmWin[1][1]==0 && gv_lmFaction[1]==0);
        CHECK(gv_originalRole[1][1]==3 && gv_originalRole[1][0]==24);
        CHECK(gv_originalRole[8][1]==1 && gv_originalRole[8][0]==1);
        CHECK(gv_lmMark[1]==0);
    }
    reset("ordinary town snapshot retains profession"); role(1,3,24); role(8,1,34); gv_lmMark[1]=8; gv_alivePlayers&=~(1u<<8);
    gf_LMResolve(); CHECK(gv_lmWin[8][1]==1 && gv_lmWin[8][0]==34 && gv_lmFaction[8]==0);
    CHECK(gf_LMCat(8)==1 && gf_LMRole(8)==34 && gf_BHFaction(1)==1);
    reset("stale lmFaction without lmWin must not affect victory identity"); gv_lmFaction[1]=5; role(1,1,34);
    CHECK(gf_LMCat(1)==1 && gf_LMRole(1)==34);
}
void testSheriff() {
    for(int team:{2,5}) for(bool immune:{false,true}) for(bool enabled:{false,true}) {
        reset("sheriff real alignment without profession rewrite"); role(1,1,2); role(8,1,34); gv_bhFaction[8]=team;
        gv_visitation[1]=8; gv_immune[8][2]=immune; gv_roleOptions[1][2][0]=enabled;
        string before=professionState(); gf_SKF_1_jingzhang(1); CHECK(professionState()==before);
        CHECK(hasMessage(1,team==2?"BD797B72":"361742C1")==(!immune && enabled));
        CHECK(!hasMessage(1,team==2?"361742C1":"BD797B72"));
    }
}
struct Predicate { const char* name; bool (*fn)(int); };
Predicate predicates[]={
''' + predicate_array + r'''
};
void runET(int team) { if(team==1) gf_ETTownWin(); else if(team==2) gf_ETMafiaWin(); else gf_ETTriadWin(); }
void testET() {
    std::mt19937 random(306019);
    for(int trial=0;trial<300;++trial) for(int winner:{1,2,5}) {
        reset("actual faction ET randomized accounting");
        int expected[16]{};
        for(int p=1;p<=15;++p) {
            int teams[]={1,2,5}; expected[p]=teams[random()%3];
            role(p,expected[p],1+random()%20);
            if(expected[p]!=1 && random()%2) { role(p,1,1+random()%35); gv_bhFaction[p]=expected[p]; }
            if(random()%2) gv_alivePlayers&=~(1u<<p);
            if(random()%4==0) gv_currentPlayers&=~(1u<<p);
            if(random()%5==0 && !(gv_alivePlayers&(1u<<p))) {
                gv_lmWin[p][1]=1; gv_lmWin[p][0]=4;
                if(expected[p]!=1) gv_lmFaction[p]=expected[p];
                role(p,3,24); gv_bhFaction[p]=0;
            }
            for(const auto& predicate:predicates) {
                bool primary=string(predicate.name)=="gf_ETTownWin"?expected[p]==1:string(predicate.name)=="gf_ETMafiaWin"?expected[p]==2:string(predicate.name)=="gf_ETTriadWin"?expected[p]==5:false;
                CHECK(predicate.fn(p)==primary);
            }
        }
        runET(winner);
        for(int p=1;p<=15;++p) {
            bool won=expected[p]==winner,current=(gv_currentPlayers&(1u<<p))!=0;
            CHECK(gv_won[p]==won); CHECK(gv_bankGeneralIntegers[p][6]==int(won && current));
            CHECK(gv_bankGeneralIntegers[p][7]==int(!won && current));
        }
    }
    // High-number town professions must never index a gang profession table or
    // accidentally get Town-only role achievements after their faction wins.
    for(int winner:{2,5}) {
        reset("converted Town loses Town game and wins its new faction"); role(1,1,34); gv_bhFaction[1]=winner;
        gf_ETTownWin(); CHECK(!gv_won[1] && gv_bankGeneralIntegers[1][7]==1);
        reset("converted team achievements"); role(1,1,34); gv_bhFaction[1]=winner;
        gv_specialCaseFlag[2]=1; gv_specialCaseFlag[4]=1; runET(winner);
        CHECK(gv_won[1] && gv_bankOtherAchievements[1][13]==1 && gv_bankOtherAchievements[1][15]==1);
        CHECK(gv_bankOtherAchievements[1][10]==0 && gv_bankOtherAchievements[1][11]==0);
    }
}
void addOracle(int* counts,int& egun,int pool,int id,bool alive,bool executed,bool executionWin,int points,bool executionNeedsAlive) {
    if(alive) {
        ++counts[10];
        if(pool==1) { ++counts[0]; if(id==1) ++counts[11]; }
        if(pool==2) ++counts[1];
        if(pool==5) ++counts[15];
        if(pool==3) {
            const std::map<int,int> index={{1,2},{2,3},{3,4},{4,5},{5,6},{6,8},{7,12},{8,13},{10,13},{9,14},{11,16},{12,17},{13,18},{14,19},{15,20},{16,21},{17,22},{19,26},{20,27},{22,28},{26,29},{27,30},{31,24},{32,25}};
            auto found=index.find(id); if(found!=index.end()) ++counts[found->second];
            if(id==28) ++egun;
        }
    }
    if(pool==3 && id==3 && executed) ++counts[7];
    if(pool==3 && id==6 && executionWin && (!executionNeedsAlive || alive)) ++counts[9];
    if(pool==3 && id==17 && points>=3) ++counts[23];
}
void testCheckEnd() {
    for(int team:{2,5}) {
        reset("single converted player belongs only to gang",1); role(1,1,1); gv_bhFaction[1]=team;
        CHECK(gf_CheckEnd()==(team==2?2:13)); CHECK(observedCounts[0]==0 && observedCounts[11]==0);
        CHECK(observedCounts[team==2?1:15]==1);
        reset("converted versus serial killer uses actual two-player priority",2); gv_bhFaction[1]=team; role(2,3,1);
        CHECK(gf_CheckEnd()==3);
    }
    std::mt19937 random(306042);
    for(int trial=0;trial<4000;++trial) {
        reset("CheckEnd independent populations and effective-identity equivalence");
        int expected[31]{},egun=0,pools[16]{},ids[16]{};
        gv_alivePlayers=gv_currentPlayers=0;
        gv_dayOver=random()%2; gv_tieTicker=random()%9; gv_roleOptions[1][1][1]=random()%2;
        gv_roleOptions[3][1][2]=random()%2; gv_roleOptions[3][6][2]=random()%2;
        const int neutrals[]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,19,20,22,24,26,27,28,29,31,32};
        for(int p=1;p<=15;++p) {
            const int teams[]={1,2,3,5}; int pool=teams[random()%4],id=pool==3?neutrals[random()%27]:1+random()%35;
            bool alive=random()%4!=0; if(alive) gv_alivePlayers|=1u<<p;
            gv_currentPlayers|=1u<<p; role(p,pool,id);
            pools[p]=pool; ids[p]=id;
            if(pool==1 && random()%2) { int team=random()%2?2:5; gv_bhFaction[p]=team; pools[p]=team; ids[p]=0; }
            if(!alive && random()%3==0) {
                gv_lmWin[p][1]=pool; gv_lmWin[p][0]=id; role(p,3,24);
                if(pool==1 && gv_bhFaction[p]!=0) { gv_lmFaction[p]=gv_bhFaction[p]; ids[p]=0; }
                gv_bhFaction[p]=0;
            }
            gv_executed[p]=random()%2; gv_executionWin[p]=random()%2; gv_e8B58CE9ACBCE782B9E695B0[p]=random()%5;
            addOracle(expected,egun,pools[p],ids[p],alive,gv_executed[p],gv_executionWin[p],gv_e8B58CE9ACBCE782B9E695B0[p],gv_roleOptions[3][6][2]);
        }
        int result=gf_CheckEnd();
        for(int i=0;i<31;++i) CHECK(observedCounts[i]==expected[i]);
        CHECK(observedEgun==egun);
        std::array<int,7> flags{}; std::copy(std::begin(gv_specialCaseFlag),std::end(gv_specialCaseFlag),flags.begin());
        clearValue(gv_specialCaseFlag); clearValue(gv_bhFaction); clearValue(gv_lmFaction); clearValue(gv_lmWin);
        for(int p=1;p<=15;++p) role(p,pools[p],ids[p]);
        CHECK(gf_CheckEnd()==result);
        CHECK(std::equal(flags.begin(),flags.end(),std::begin(gv_specialCaseFlag)));
    }
}
int main() {
    testQueries(); testConversionGuardsAndState(); testChat(); testClosedNightWindow(); testCommand();
    testLimao(); testSheriff(); testET(); testCheckEnd();
    std::cout << "PASS: actual faction API/guards/no-side-effects/profession state; role/death names; card rows; night chat; solo commands; limaо snapshots; sheriff; 25 ET expressions; three complete faction ET bodies; CheckEnd" << '\n';
    std::cout << "PASS: 4000 seeded independent counter populations + effective-identity metamorphism; 900 randomized full ET fixtures; " << fixtures << " fixtures, " << checks << " assertions; UBSan/bounds" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    source = args.script.read_text(encoding='utf-8')
    print(f'Actual source: {args.script}; engine/rendering/banks require separate verification', flush=True)
    code = harness(source)
    with tempfile.TemporaryDirectory(prefix='bh-faction-tests-') as tmp:
        cpp, exe = Path(tmp) / 'faction.cpp', Path(tmp) / 'faction'
        cpp.write_text(code, encoding='utf-8')
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
