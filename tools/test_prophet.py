#!/usr/bin/env python3
"""Execute complete production Prophet Galaxy functions with C++ UBSan/bounds.

Reuses test_egun's brace-aware extraction/array translation. Original passive SKN
functions come from pinned 22d12a5, never mutable HEAD. Gameplay dependencies are
extracted recursively; only named engine/message/panel boundaries are doubles.
Static hook checks are not execution of the night/day trigger or an SC2 test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
from test_egun import SCRIPT, function, mask, translate
from test_faction_conversion import block_end, calls, missing_actual_globals

ROOT = Path(__file__).resolve().parent.parent
BASELINE = '22d12a5ee7a8813c20f9a9d0b6bc85efe605983e'
STRINGS = ROOT / 'work/blackhand/strings-xz.txt'
CORE = ('gf_XZIsCult', 'gf_XZCanConvertIntrinsic', 'gf_XZPlayerLabel',
        'gf_XZSendCult', 'gf_XZProphecy', 'gf_SKN_3_xianzhi',
        'gf_XZFirstNight', 'gf_XZFirstDawn', 'gf_XZFlushDawn')
# Independent audited source map; execute these full old setups for the oracle.
PASSIVES = {
    1: 'lianhuanshashou', 5: 'zonghuozhe', 6: 'chuxingzhe', 9: 'sharenkuang',
    13: 'duoluoshenpanzhe', 14: 'wenyisanbuzhe', 15: 'yuanhun_2',
    20: 'kaitangshou', 22: 'ganranzhe', 26: 'yanluo', 27: 'zhongcaizhe',
    31: 'yingwuzhe', 32: 'tianxuanzhe',
}
TEXT_KEYS = {'XZNAME', 'XZDESC', 'XZHEAD', 'XZBOX1', 'XZBOX2', 'XZBOX4',
             'XZCARD', 'XZINFOPREFIX', 'XZINFOFULL', 'XZINFOSHORT',
             'XZINFONOFAKE', 'XZINFOEMPTY', 'XZBECOME', 'XZSEP'}
BOUNDARIES = {
    'PlayerGroupHasPlayer', 'PlayerGroupSingle', 'PlayerGroupAll',
    'PlayerStatus', 'RandomInt', 'StringExternal', 'StringToText', 'IntToText',
    'TextWithColor', 'libNtve_gf_ConvertPlayerColorToColor', 'Color', 'SoundLink',
    'gf_CBSystemMessage', 'gf_BHNotify', 'gf_RTRoleCard',
    'gf_CBAllowDisallowChatting', 'gf_CBHighlightText', 'gf_ZCEnsureUi',
    'DialogControlSetEnabled', 'DialogControlSetVisible', 'DialogSetVisible',
    'gf_ASE5AEA1E69FA5E98089E9A1B9',
}
PROTECTED = ('gv_visitation', 'gv_visitation2', 'gv_action', 'gv_cooldown',
             'gv_shots', 'gv_skillCount', 'gv_e78AAFE7BDAAE4BA8BE5AE9E',
             'gv_cultConversionsLeft', 'gv_cultCooldown', 'gv_cultSmiteCount',
             'gv_bhFaction', 'gv_jailed', 'gv_roleblocked', 'gv_immune',
             'gv_immuneChance', 'gv_originalRole', 'gv_preCultRole',
             'gv_specialCasePlayer', 'gv_roles')


def panel_boundary(name: str) -> bool:
    return name in BOUNDARIES or bool(re.fullmatch(r'gf_RA\w+', name))


def extract_closure(source: str, names: list[str]) -> tuple[list[str], set[str]]:
    """Unknown gameplay calls must have real bodies; never synthesize a guard."""
    bodies, boundary = [], set()
    pending = list(dict.fromkeys(names))
    cursor = 0
    while cursor < len(pending):
        body = function(source, pending[cursor])
        bodies.append(body)
        for name in sorted(calls(body) - {pending[cursor]}):
            if panel_boundary(name):
                boundary.add(name)
            elif name not in pending:
                assert name.startswith(('gf_', 'auto_gf_')), ('unknown engine boundary', name)
                pending.append(name)

        cursor += 1

    return bodies, boundary


def load_strings() -> dict[str, str]:
    table = {}
    for line in STRINGS.read_text(encoding='utf-8').splitlines():
        if not line.startswith('Param/Value/'):
            continue

        key, value = line.split('=', 1)
        assert key not in table, ('duplicate text key', key)
        table[key] = value

    assert set(table) == {'Param/Value/' + key for key in TEXT_KEYS}, 'all 14 real text keys required'
    assert table['Param/Value/XZBECOME'] == '你受到了神的感召，你成为了一名邪教徒。'
    return table


def static_integration(source: str, baseline: str) -> None:
    """Extensible integration entry: checks actual hook ordering, not execution."""
    night = mask(function(source, 'auto_gf_NightTransition_TriggerFunc'))
    hook = night.index('gf_XZFirstNight();')
    for name in ('gf_RSTownSetup', 'gf_RSMafiaSetup2', 'gf_RSTriadSetup',
                 'gf_RSNeutralSetup', 'gf_GSRefreshChat', 'gf_GKMailAnnounce'):
        assert night.index(name + '(') < hook, ('opening hook too early', name)

    assert night.count('gf_XZFirstNight();') == 1
    sequence = mask(function(source, 'gt_NightSequence_Func'))
    assert sequence.count('gf_XZFirstDawn();') == 1
    assert sequence.index('gf_GSFirstDawn();') < sequence.index('gf_XZFirstDawn();') < sequence.index('gv_dayNumber += 1;')
    day = mask(function(source, 'auto_gf_DayTransition_TriggerFunc'))
    clear = day.index('gf_CBClearChat(')
    enclosing = [i for i, char in enumerate(day[:clear]) if char == '{' and block_end(day, i) > clear]
    assert enclosing
    loop_end = min(block_end(day, start) for start in enclosing)
    assert loop_end < day.index('gf_XZFlushDawn();'), 'dawn notice must survive morning clear loop'
    for name in CORE:
        signature = function(source, name).split('{', 1)[0].strip()
        assert signature + ';' in source, ('missing forward declaration', name)

    for name in ('gv_xzAnnounced', 'gv_xzDawnNotice'):
        declaration = re.search(r'^bool\[16\]\s+' + name + r'\s*;', source, re.M)
        assert declaration and declaration.start() <= source.index(name), ('bad player flag declaration', name)

    for name in ('gt_ASCultSmite_Func', 'gt_ASCultSmiteveto_Func'):
        current_guard = function(source, name).split('// Actions', 1)[0]
        original_guard = function(baseline, name).split('// Actions', 1)[0]
        compact = lambda value: re.sub(r'\s+', '', mask(value))
        assert compact(current_guard) == compact(original_guard), ('active Cult permission changed', name)

    assert calls(function(source, 'gf_SKN_3_xianzhi')) == {
        'gf_SKN_3_xianzhi', 'gf_CBAssignUnassignChatChannel',
        'gf_CBAllowDisallowChatting', 'gf_RANoActions',
    }, 'Prophet setup must not borrow a Cult active panel'
    print('PASS static hooks: after setup/routing; after final night deaths before day++; after morning clear; unchanged original active-smite guards')


def cult_award_expression(source: str) -> str:
    """Actual ET winner expression only; not a replacement victory algorithm."""
    body = function(source, 'gf_ETCultWin')
    matches = list(re.finditer(r'\bif\s*(\([^\n{]+gf_EGWon\([^\n{]+)\s*\{', body))
    assert len(matches) == 1, 'missing/ambiguous actual Cult award condition'
    match = matches[0]
    end = block_end(body, body.index('{', match.start()))
    assert 'gv_won[lv_a] = true;' in body[match.start():end]
    return 'bool actualCultAward(int lv_a) { return ' + match[1] + '; }'


def static_membership(source: str) -> None:
    """Opt-in final-member wiring audit, callable after integration is complete."""
    for name in ('gf_CheckEnd', 'gf_ETCultWin', 'gf_RSNeutralSetup', 'gf_SequenceAfter2'):
        body = mask(function(source, name))
        has_new_member = ('gf_XZIsCult(' in body or bool(re.search(r'gv_roles\[[^\n]+\]\[0\] == 30', body))
                          or 'gf_LMRole(lv_a) == 30' in body)
        assert has_new_member, ('Cult member role30 not integrated', name)

    assert 'gf_LMRole(lv_a) == 30' in cult_award_expression(source), 'dead Prophet missing Cult award'
    for variable in ('gv_roleWeights[3][30]', 'gv_bankSaveWeights[0][3][30]'):
        assignments = re.findall(re.escape(variable) + r'\s*=\s*([^;]+);', source)
        assert assignments and all(value.strip() in {'0.0', '0'} for value in assignments), ('Prophet must not appear randomly', variable)

    win_list = mask(function(source, 'gf_RTMakeWinList'))
    cult_presence = ('(gv_roleChance[3][8] > 0.0) || '
                     '(gv_roleChance[3][10] > 0.0)')
    assert win_list.count(cult_presence) == 11
    assert win_list.count(cult_presence + ' || (gv_roleChance[3][30] > 0.0)') == 11, 'Prophet-only Cult missing from victory display'

    print('PASS static membership: population/setup/passive charge/Cult award, 11 Cult-presence displays and zero random weights')


def harness(source: str, baseline: str, strings: dict[str, str], membership: bool = False) -> str:
    names = list(CORE) + ['gf_GKIs', 'gf_GKSetRoleField', 'gf_GSEffectiveChannel']
    award = cult_award_expression(source) if membership else ''
    if award:
        names += sorted(name for name in calls(award) if name.startswith('gf_'))

    actual, boundaries = extract_closure(source, names)
    if award:
        actual.append(award)
    old_names = ['gf_SKN_3_' + value for value in PASSIVES.values()]
    old_names += ['gf_SKR_1_mushi', 'gf_SKR_1_zhujiao', 'gf_SKN_3_tangjihede']
    old, old_boundaries = extract_closure(baseline, old_names)
    boundaries |= old_boundaries
    # Keep all old function bodies intact; namespace only identifiers to coexist.
    old_defined = {re.search(r'\b(\w+)\s*\(', mask(body))[1] for body in old}
    for index, body in enumerate(old):
        old[index] = re.sub(r'\b(' + '|'.join(map(re.escape, sorted(old_defined))) + r')\b',
                            lambda match: 'baseline_' + match[0], body)

    bodies = actual + old
    code = '\n\n'.join(bodies)
    # Fail closed if a core introduces another untested Prophet gameplay helper.
    defined_xz = set(re.findall(r'^(?:void|bool|int|text)\s+(gf_XZ\w+|gf_SKN_3_xianzhi)\s*\([^;{}]*\)\s*\{', mask(source), re.M))
    assert defined_xz == set(CORE), ('uncovered Prophet function', defined_xz ^ set(CORE))
    constants = []
    for name in sorted(set(re.findall(r'\b(?:ge_\w+|gv_gkMailChannel)\b', mask(code)))):
        match = re.search(r'^const int ' + name + r'\s*=\s*[^;]+;', source, re.M)
        assert match, ('missing actual constant', name)
        constants.append(match[0])

    declarations = missing_actual_globals(source, bodies + [' '.join(PROTECTED)], '\n'.join(constants))
    globals_used = re.findall(r'\bgv_\w+(?=\[|;)', declarations)
    reset_globals = '\n'.join(f'    clearValue({name});' for name in globals_used)
    mutable = {'gv_roles', 'gv_preCultRole', 'gv_bhFaction', 'gv_xzAnnounced', 'gv_xzDawnNotice'}
    snapshots = '\n'.join(f'    appendValue(out, {name});' for name in globals_used if name not in mutable)
    prototypes = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    # Presentation doubles retain the actual production signature, notably Notify.
    custom = {'gf_CBSystemMessage', 'gf_BHNotify', 'gf_RTRoleCard', 'gf_CBAllowDisallowChatting'}
    panel_stubs = []
    for name in sorted(boundaries):
        if name.startswith('gf_') and name not in custom:
            owner = source if re.search(r'^void\s+' + name + r'\s*\([^;{}]*\)\s*\{', source, re.M) else baseline
            signature = function(owner, name).split('{', 1)[0].strip()
            assert signature.startswith('void '), ('non-void business/panel boundary', name)
            panel_stubs.append(signature + ' { ++panelCalls; }')

    notify = function(source, 'gf_BHNotify').split('{', 1)[0].strip()
    assert re.fullmatch(r'void gf_BHNotify\s*\(text lp_msg, int lp_target, soundlink lp_sound\)', notify), ('Notify signature changed', notify)
    table = ',\n'.join('{' + json.dumps(key, ensure_ascii=False) + ',' + json.dumps(value, ensure_ascii=False) + '}' for key, value in sorted(strings.items()))
    dispatch = '\n'.join(f'case {role}: baseline_gf_SKN_3_{name}(p' + (', false' if role == 5 else '') + '); break;' for role, name in PASSIVES.items())
    translated = translate(code)
    translated = re.sub(r'^(\s+(?:int|bool|text|string|playergroup)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', translated, flags=re.M)
    print(f'Extracted {len(actual) - bool(award)} complete production functions + {len(old)} pinned baseline functions'
          f' + {bool(award):d} actual Cult award expression; {len(globals_used)} production globals')
    print('Presentation boundaries:', ', '.join(sorted(boundaries)))
    return r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <map>
#include <random>
#include <regex>
#include <set>
#include <sstream>
#include <string>
#include <vector>
using std::string;
using text=string;
using playergroup=unsigned;
using soundlink=string;
struct color { double r,g,b; };
const int c_playerStatusActive=1;
''' + '\n'.join(constants) + '\n' + declarations + r'''
long checks=0;
int panelCalls=0, randomCalls=0;
std::mt19937 rng;
void checked(bool ok,int line,const char* expression) {
    ++checks;
    if(!ok) { std::cerr<<"check failed #"<<checks<<" at generated C++ line "<<line<<": "<<expression<<"\n"; std::exit(1); }
}
#define check(expression) checked((expression),__LINE__,#expression)
template<class T> void clearValue(T& x) { x=T{}; }
template<class T,size_t N> void clearValue(T (&x)[N]) { for(auto& y:x) clearValue(y); }
template<class T> void appendValue(std::ostringstream& out,const T& x) { out<<x<<'|'; }
template<class T,size_t N> void appendValue(std::ostringstream& out,const T (&x)[N]) { for(const auto& y:x) appendValue(out,y); }
struct Message { text value; int to,from; };
std::vector<Message> messages;
std::vector<int> cards;
std::map<string,string> strings={
''' + table + r'''
};
text StringExternal(string key) { auto it=strings.find(key); return it==strings.end()?"{"+key+"}":it->second; }
text StringToText(string s) { return s; }
text IntToText(int p) { return std::to_string(p); }
color Color(double r,double g,double b) { return {r,g,b}; }
color libNtve_gf_ConvertPlayerColorToColor(int p) { return {double(p),0,0}; }
text TextWithColor(text s,color c) { return "<pc"+std::to_string(int(c.r))+">"+s+"</pc>"; }
soundlink SoundLink(string s,int variant) { check(variant==-1); return s; }
playergroup PlayerGroupSingle(int p) { check(p>=1&&p<=15); return 1u<<p; }
playergroup PlayerGroupAll() { return 0xfffe; }
bool PlayerGroupHasPlayer(playergroup g,int p) { check(p>=1&&p<=15); return g&(1u<<p); }
int PlayerStatus(int) { return c_playerStatusActive; }
int RandomInt(int a,int b) { check(a<=b&&a>=0&&b<15); ++randomCalls; return std::uniform_int_distribution<int>(a,b)(rng); }
void gf_CBSystemMessage(text value,int to,int from,int option,soundlink,color) {
    check(to>=1&&to<=15&&from>=0&&from<=15&&option==0); messages.push_back({value,to,from});
}
void gf_BHNotify(text value,int to,soundlink) { check(to>=1&&to<=15); messages.push_back({value,to,to}); }
void gf_RTRoleCard(int p) { check(p>=1&&p<=15); cards.push_back(p); }
void gf_CBAllowDisallowChatting(int p,int allow) { check(p>=1&&p<=15); ++panelCalls; }
void DialogControlSetEnabled(int,playergroup,bool) { ++panelCalls; }
void DialogControlSetVisible(int,playergroup,bool) { ++panelCalls; }
void DialogSetVisible(int,playergroup,bool) { ++panelCalls; }
''' + '\n'.join(panel_stubs) + '\n' + prototypes + '\n' + translated + r'''
void reset(int n=15) {
''' + reset_globals + r'''
    messages.clear(); cards.clear(); panelCalls=randomCalls=0; rng.seed(17);
    gv_gameStarted=true; gv_dayNumber=1; gv_isNight=true;
    for(int p=1;p<=15;++p) {
        if(p<=n) gv_alivePlayers|=(1u<<p);
        gv_name[p]="P"+std::to_string(p)+"!"; gv_playerColor[p]=p;
        gv_playerSpot[p]=16-p; gv_roles[p][1]=1; gv_roles[p][0]=2;
    }
    gv_currentPlayers=gv_alivePlayers;
}
void role(int p,int pool,int r) { gv_roles[p][1]=pool; gv_roles[p][0]=r; }
string protectedState() {
    std::ostringstream out;
''' + snapshots + r'''
    return out.str();
}
string stableState(bool flags=false) {
    std::ostringstream out;
    out<<protectedState();
    appendValue(out,gv_roles); appendValue(out,gv_preCultRole); appendValue(out,gv_bhFaction);
    if(flags) { appendValue(out,gv_xzAnnounced); appendValue(out,gv_xzDawnNotice); }
    return out.str();
}
void oldSetup(int p,int role) {
    switch(role) {
''' + dispatch + r'''
    default: break;
    }
}
void qualifications() {
    for(int cultOption=0;cultOption<2;++cultOption) for(int option=0;option<12;++option)
    for(int on=0;on<2;++on) for(int roleId=1;roleId<=32;++roleId) {
        reset(); role(8,3,roleId); gv_roleOptions[3][roleId][option]=on;
        gv_roleOptions[3][8][1]=cultOption;
        oldSetup(8,roleId);
        bool expected=roleId!=8&&roleId!=10&&roleId!=30 && (!gv_immune[8][0]||!cultOption);
        auto before=stableState(true);
        check(gf_XZCanConvertIntrinsic(8)==expected);
        check(stableState(true)==before);
        // All temporary runtime defenses must be ignored by intrinsic query.
        gv_jailed[8]=3; gv_roleblocked[8]=4; gv_immune[8][0]=gv_immune[8][3]=true;
        gv_immuneChance[8]=99; gv_bhFaction[8]=2;
        check(gf_XZCanConvertIntrinsic(8)==expected);
    }
    for(int cultOption=0;cultOption<2;++cultOption) for(int pool:{1,2,5})
    for(int r=1;r<=35;++r) {
        reset();role(8,pool,r);gv_roleOptions[3][8][1]=cultOption;
        check(gf_XZCanConvertIntrinsic(8)==(pool==1&&r!=7&&r!=14));
        if(pool==1) {
            gv_bhFaction[8]=5;
            check(gf_XZCanConvertIntrinsic(8)==(r!=7&&r!=14));
        }
    }
    for(int pool:{1,3}) for(int r=1;r<=37;++r) {
        reset();role(8,pool,r);
        if(pool==3&&r>=33) check(!gf_XZCanConvertIntrinsic(8));
        gv_gkRole[8]=33;check(!gf_XZCanConvertIntrinsic(8));
    }
    reset(); gv_alivePlayers=0;check(!gf_XZCanConvertIntrinsic(8));
    for(int p:{-1,0,16,100}) { check(!gf_XZCanConvertIntrinsic(p));check(!gf_XZIsCult(p)); }
    for(int p=1;p<=15;++p) for(int pool:{1,2,3,5}) for(int r:{8,10,30,31}) {
        reset();role(p,pool,r);check(gf_XZIsCult(p)==(pool==3&&(r==8||r==10||r==30)));
    }
    // Town clerics have no hidden permanent cult protection in old real setups.
    reset();role(8,1,25);baseline_gf_SKR_1_mushi(8);check(!gv_immune[8][0]&&!gv_immune[8][3]);
    reset();role(8,1,35);baseline_gf_SKR_1_zhujiao(8);check(!gv_immune[8][0]&&!gv_immune[8][3]);
    reset();role(8,3,21);baseline_gf_SKN_3_tangjihede(8);check(!gv_immune[8][0]);
    // Actual ordinary setter refuses to mutate a constructed immutable passer.
    reset();role(8,3,33);gv_gkRole[8]=33;
    gf_GKSetRoleField(8,0,8);check(gv_roles[8][0]==33);
}
std::vector<int> selected(const string& message) {
    std::vector<int> out;
    const std::regex name("P([0-9]+)!");
    for(auto it=std::sregex_iterator(message.begin(),message.end(),name);it!=std::sregex_iterator();++it)
        out.push_back(std::stoi((*it)[1]));
    return out;
}
void candidates() {
    bool fakePositions[3]={};
    for(int n=0;n<=15;++n) for(int trues=0;trues<=n;++trues)
    for(int seed=0;seed<32;++seed) {
        reset(n);rng.seed(seed);
        if(n>0) role(1,3,30);
        for(int p=2;p<=n;++p) if(p>trues+1) role(p,2,1);
        int trueN=std::min(trues,std::max(n-1,0));
        int falseN=std::max(n-1-trueN,0);
        auto before=stableState();
        gf_XZFirstNight();
        check(stableState()==before);
        for(int p=1;p<=15;++p) {
            check(gv_xzAnnounced[p]==(n>0&&p==1));
            check(!gv_xzDawnNotice[p]);
        }
        if(n==0) { check(messages.empty()&&randomCalls==0); continue; }
        check(messages.size()==1&&messages[0].to==1&&messages[0].from==1);
        auto picks=selected(messages[0].value);
        check(int(picks.size())==std::min(2,trueN)+(falseN>0));
        int yes=0,no=0;
        for(size_t i=0;i<picks.size();++i) {
            int p=picks[i];check(p>=2&&p<=n);
            check(std::count(picks.begin(),picks.end(),p)==1);
            check(messages[0].value.find(std::to_string(16-p)+".<pc"+std::to_string(p)+">P"+std::to_string(p)+"!</pc>")!=string::npos);
            if(p<=trueN+1) ++yes;
            else { ++no; if(picks.size()==3) fakePositions[i]=true; }
        }
        check(yes==std::min(2,trueN)&&no==(falseN>0));
        if(picks.empty()) check(messages[0].value==strings.at("Param/Value/XZINFOEMPTY"));
        else if(picks.size()==3) check(messages[0].value.find(strings.at("Param/Value/XZINFOFULL"))!=string::npos);
        else check(messages[0].value.find(strings.at(falseN?"Param/Value/XZINFOSHORT":"Param/Value/XZINFONOFAKE"))!=string::npos);
        auto count=messages.size();int randomBefore=randomCalls;
        gf_XZFirstNight();check(messages.size()==count&&randomCalls==randomBefore);
    }
    check(fakePositions[0]&&fakePositions[1]&&fakePositions[2]);
    std::set<std::vector<int>> sets,orders;
    for(int seed=0;seed<1024;++seed) {
        reset(6);rng.seed(seed);role(1,3,30);role(5,2,1);role(6,5,1);
        gf_XZFirstNight();auto picks=selected(messages[0].value);
        check(picks.size()==3);
        int truthCount=0;for(int p:picks) { check(p>=2&&p<=6);truthCount+=(p<=4); }
        check(truthCount==2);orders.insert(picks);
        std::sort(picks.begin(),picks.end());sets.insert(picks);
    }
    check(sets.size()==6&&orders.size()==36); // every legal pair/fake and all output permutations
    // Passers are real ineligible targets, not fake cult teammates.
    reset(4);role(1,3,30);role(4,3,33);gf_XZFirstNight();
    check(selected(messages[0].value).size()==3);
    for(int p:{1,8,15}) for(int bad:{-1,0,16,99}) {
        reset();gv_playerSpot[p]=bad;
        check(gf_XZPlayerLabel(p).find(std::to_string(p)+".<pc")==0);
    }
}
void routingAndMultiple() {
    reset();role(1,3,30);role(2,3,30);role(3,3,8);role(4,3,10);
    for(int p:{1,2,3,4,6}) gv_channel[p]=3; // 6 models a channel-3 symbiote listener
    gv_alivePlayers&=~(1u<<6); // dead spectators must not receive
    gv_channel[7]=4;gv_channel[8]=20;
    gf_XZFirstNight();check(messages.size()==8);
    for(const auto& m:messages) {
        check(m.to>=1&&m.to<=4&&(m.from==1||m.from==2));
        for(int p:selected(m.value)) check(p>4);
    }
    auto count=messages.size();gf_XZFirstNight();check(messages.size()==count);
    reset();role(1,3,30);gv_channel[5]=3;gv_currentPlayers&=~(1u<<5);
    gf_XZSendCult(1,"channel probe");check(messages.size()==1&&messages[0].to==1);
    // Real inherited-channel query: GSRefreshChat never writes raw gv_channel.
    reset();role(1,3,30);role(3,3,8);role(6,3,29);
    gv_channel[1]=gv_channel[3]=3;gv_gsHost[6]=3;
    check(gv_channel[6]==0&&gf_GSEffectiveChannel(6)==3);
    gf_XZSendCult(1,"symbiote probe");
    check(messages.size()==3);
    check(messages[0].to==1&&messages[1].to==3&&messages[2].to==6);
}
void stateAndDawn() {
    for(int p=1;p<=15;++p) for(int blocked=0;blocked<4;++blocked) {
        reset();role(p,3,30);gv_bhFaction[p]=5;
        gv_roleblocked[p]=(blocked&1)?7:0;gv_jailed[p]=(blocked&2)?6:0;
        gv_visitation[p]=4;gv_visitation2[p]=5;gv_action[p][0]=9;
        gv_shots[p]=17;gv_cooldown[p]=3;gv_cultConversionsLeft=8;
        gv_xzAnnounced[p]=(blocked&1);
        auto before=protectedState();gf_XZFirstDawn();
        check(protectedState()==before);
        check(gv_roles[p][1]==3&&gv_roles[p][0]==8&&gv_bhFaction[p]==0);
        check(gv_preCultRole[p][1]==3&&gv_preCultRole[p][0]==30);
        check(gv_xzDawnNotice[p]&&cards.size()==1&&cards[0]==p&&messages.empty());
        check(gv_xzAnnounced[p]==bool(blocked&1));
        for(int q=1;q<=15;++q) if(q!=p) check(gv_roles[q][1]==1&&gv_roles[q][0]==2&&!gv_xzDawnNotice[q]);
        gf_XZFirstDawn();check(cards.size()==1);
        gf_XZFlushDawn();check(messages.size()==1&&messages[0].to==p&&messages[0].from==p);
        check(messages[0].value=="你受到了神的感召，你成为了一名邪教徒。");
        check(!gv_xzDawnNotice[p]);gf_XZFlushDawn();check(messages.size()==1);
    }
    for(int reason=0;reason<6;++reason) {
        reset();role(8,3,30);
        if(reason==0) gv_alivePlayers&=~(1u<<8);
        if(reason==1) gv_diedAtNight[8]=true;
        if(reason==2) gv_dayNumber=2;
        if(reason==3) gv_dayNumber=0;
        if(reason==4) role(8,1,2);
        if(reason==5) role(8,3,4);
        int pool=gv_roles[8][1],r=gv_roles[8][0];
        gf_XZFirstDawn();gf_XZFlushDawn();
        check(gv_roles[8][1]==pool&&gv_roles[8][0]==r&&cards.empty()&&messages.empty());
        if(reason<2) check(gf_XZIsCult(8)); // dead first-night prophet remains a cult member
    }
    for(int reason=0;reason<5;++reason) {
        reset();role(8,3,30);
        if(reason==0) gv_dayNumber=2;
        if(reason==1) gv_dayNumber=0;
        if(reason==2) gv_isNight=false;
        if(reason==3) gv_gameOver=true;
        if(reason==4) gv_alivePlayers&=~(1u<<8);
        gf_XZFirstNight();check(messages.empty()&&!gv_xzAnnounced[8]);
    }
    reset();role(8,3,30);gf_SKN_3_xianzhi(8);
    check(gv_channel[8]==3&&panelCalls>=1);
}
''' + (r'''
void actualAwards() {
    for(int p=1;p<=15;++p) for(bool alive:{false,true}) for(int roleId:{8,10,30}) {
        reset();role(p,3,roleId);
        if(!alive) gv_alivePlayers&=~(1u<<p);
        check(actualCultAward(p));
        if(roleId==30&&!alive) {
            gf_XZFirstDawn();check(gv_roles[p][0]==30&&actualCultAward(p));
        }
    }
    // The true LM snapshot must retain a dead prophet's shared victory.
    reset();role(8,3,24);gv_alivePlayers&=~(1u<<8);
    gv_lmWin[8][1]=3;gv_lmWin[8][0]=30;check(actualCultAward(8));
    reset();role(8,1,2);check(!actualCultAward(8));
}
''' if membership else 'void actualAwards() {}\n') + r'''
int main() {
    qualifications();candidates();routingAndMultiple();stateAndDawn();actualAwards();
    std::cout<<"PASS Prophet: "<<checks<<" assertions; complete actual functions + pinned old SKN oracle; UBSan/bounds (NOT SC2)\n";
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--skip-integration', action='store_true', help='core execution only; explicitly skip static hook checks')
    parser.add_argument('--check-membership', action='store_true', help='also execute the real Cult award expression and audit final member wiring')
    args = parser.parse_args()
    assert shutil.which(args.cxx), 'C++17 compiler required'
    source = args.script.read_text(encoding='utf-8')
    baseline = subprocess.run(['git', 'show', BASELINE + ':work/blackhand/CustomLogic.galaxy'],
                              cwd=ROOT, capture_output=True, text=True, check=True).stdout
    strings = load_strings()
    generated = harness(source, baseline, strings, args.check_membership)
    with tempfile.TemporaryDirectory(prefix='bh-prophet-') as directory:
        cpp, executable = Path(directory) / 'prophet.cpp', Path(directory) / 'prophet'
        cpp.write_text(generated, encoding='utf-8')
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra',
                        '-Wno-unused-parameter', '-Wno-unused-variable',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)

    if args.skip_integration:
        print('SKIP static integration hooks (explicit --skip-integration)')
    else:
        static_integration(source, baseline)

    if args.check_membership:
        static_membership(source)
    else:
        print('SKIP final membership/award-expression checks (enable --check-membership)')

    print('Source SHA256:', hashlib.sha256(source.encode()).hexdigest())
    print('Pinned original SKN baseline:', BASELINE)


if __name__ == '__main__':
    main()
