#!/usr/bin/env python3
"""Focused mayor reveal regression: actual Galaxy bodies, observable engine doubles.

Extracts the complete faction helper, chat trigger, button role handler, real
BHFaction dependencies and crime writer. The full button dispatcher (including
its caller guards) is checked verbatim against a pinned pre-change commit, not
reimplemented or stubbed. Only the actual mayor card branch is executed, alongside
its baseline branch. C++/UBSan doubles are NOT an SC2 engine/runtime test.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
from test_egun import SCRIPT, function, mask, translate
from test_faction_conversion import block_end, missing_actual_globals

ROOT = Path(__file__).resolve().parent.parent
BASELINE = '6409cf7505d5351e343bad16573f7e7823b4d6e3'
STRINGS = ROOT / 'work/blackhand/strings-faction.txt'
HELPER = 'gf_BHMayorRevealFaction'
CHAT = 'gt_ASMayorAction_Func'
BUTTON = 'gf_SKY_1_shizhang'
CARD = 'gf_RTTownRoleText'
NAMES = (HELPER, CHAT, BUTTON, 'gf_BHFaction', 'gf_BHConverted', 'gf_GKIs', 'gf_BHCrime')
TRAIT = '若你的阵营发生了转变，在你揭示自己的身份时，其他人会知道你是什么阵营。'


def mayor_card(source: str) -> str:
    body = function(source, CARD)
    anchor = 'if ((gv_roles[lv_a][0] == 12)) {'
    assert body.count(anchor) == 1, 'ambiguous mayor card branch'
    start = body.index(anchor)
    end = block_end(body, body.index('{', start))
    return body[start:end]


def normalized(source: str) -> str:
    # Preserve literal values: masking strings would miss changed reveal keys.
    return re.sub(r'"(?:\\.|[^"\\])*"|\s+',
                  lambda match: match[0] if match[0].startswith('"') else '', source)


def integration(source: str, baseline: str, strings: dict[str, str]) -> None:
    for name in (CHAT, BUTTON):
        body, old = function(source, name), function(baseline, name)
        call = r'^\s*' + HELPER + r'\(EventPlayer\(\)\);[^\S\n]*\n'
        assert len(re.findall(r'\b' + HELPER + r'\s*\(', mask(body))) == 1, (name, 'exactly one hook')
        restored, count = re.subn(call, '\n', body, flags=re.M)
        assert count == 1 and normalized(restored) == normalized(old), (name, 'old reveal behavior changed')
        hook = body.index(HELPER + '(EventPlayer());')
        loop = body.index('while (true)')
        loop_end = block_end(body, body.index('{', loop))
        assert loop_end < hook < body.index('gv_votes[EventPlayer()] = 2;'), (name, 'hook placement')
        assert not mask(body[loop_end:hook]).strip(), (name, 'hook must stand alone immediately after reveal loop')

    assert function(source, 'gt_ASMayorAction_Init') == function(baseline, 'gt_ASMayorAction_Init'), 'original -vote registration changed'

    # Full dispatcher equality proves ALL caller conditions, including one-use,
    # chat privilege/day/night/life and raw profession guards, remain unchanged.
    dispatcher = function(source, 'gt_ASAbilityButton_Func')
    assert dispatcher == function(baseline, 'gt_ASAbilityButton_Func'), 'button dispatch/guards changed'
    guard = re.search(r'^\s*if \([^\n]+\) \{\s*' + BUTTON + r'\(\);\s*}', dispatcher, re.M)
    assert guard, 'missing actual mayor caller guard'
    for term in ('gv_alivePlayers', 'gv_chatPrivilege', 'gv_gameOver == false',
                 'gv_dayActions == true', 'gv_isNight == false',
                 'gv_activated[EventPlayer()] == false',
                 'gv_roles[EventPlayer()][1] == 1', 'gv_roles[EventPlayer()][0] == 12'):
        assert term in guard[0], ('missing button guard', term)

    card = function(source, CARD)
    append = (r'^\s*gv_roleBoxText\[lv_a\]\[2\]\s*=\s*\(?'
              r'gv_roleBoxText\[lv_a\]\[2\]\s*\+\s*'
              r'StringExternal\("Param/Value/BHFMAYORTRAIT"\)\)?;[^\S\n]*\n')
    restored, count = re.subn(append, '\n', card, flags=re.M)
    assert count == 1 and normalized(restored) == normalized(function(baseline, CARD)), 'card changed beyond trait append'
    branch = mayor_card(source)
    assert branch.count('Param/Value/BHFMAYORTRAIT') == 1, 'trait outside mayor branch'
    assert branch.index('Param/Value/BHFMAYORTRAIT') > branch.index('Param/Value/D312D3AC'), 'trait must follow old traits'
    helper = function(source, HELPER)
    assert helper.split('{', 1)[0].strip() + ';' in source, 'helper forward declaration'
    assert not re.search(r'\bgv_\w+(?:\[[^\]\n]+\])*\s*(?:[+\-*/]?=(?!=)|\+\+|--)', mask(helper)), 'announcement helper must not mutate game state'
    assert strings['Param/Value/BHFMAYORTRAIT'] == '<n/>- ' + TRAIT
    for key, value in (('BHFMAYORPREFIX', '市长'), ('BHFMAYORMAFIA', '是一个黑手党成员！'),
                       ('BHFMAYORTRIAD', '是一个三合会成员！')):
        assert re.sub(r'<[^>]*>', '', strings['Param/Value/' + key]) == value, ('wrong new text', key)


def harness(source: str, baseline: str, strings: dict[str, str]) -> str:
    bodies = [function(source, name) for name in NAMES]
    # Branch wrappers only bind the original function's local actor alias; no
    # mayor condition, option, assignment or message expression is rewritten.
    bodies += [f'void actualCard(int lp_player) {{ int lv_a=lp_player;\n{mayor_card(source)}\n}}',
               f'void baselineCard(int lp_player) {{ int lv_a=lp_player;\n{mayor_card(baseline)}\n}}']
    code = '\n\n'.join(bodies)
    engine = {'if', 'for', 'while', 'return', 'EventPlayer', 'PlayerGroupHasPlayer',
              'PlayerGroupNextPlayer', 'PlayerGroupSingle', 'PlayerGroupAll',
              'DialogControlSetEnabled', 'gf_CBSystemMessage', 'StringExternal',
              'StringToText', 'IntToText', 'IntToString', 'TextWithColor',
              'libNtve_gf_ConvertPlayerColorToColor', 'Color', 'SoundLink',
              'SoundStop', 'SoundPlay', 'SoundLastPlayed'}
    calls = set(re.findall(r'\b(\w+)\s*\(', mask(code)))
    assert not calls - engine - set(NAMES) - {'actualCard', 'baselineCard'}, ('unknown actual dependency', calls - engine - set(NAMES) - {'actualCard', 'baselineCard'})
    assert not re.findall(r'\bc_\w+', mask(code)), 'unhandled engine constants'
    globals_text = missing_actual_globals(source, bodies, '')
    names = re.findall(r'\bgv_\w+(?=\[|;)', globals_text)
    resets = '\n'.join(f'    clearValue({name});' for name in names)
    prototypes = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    table = ',\n'.join('{' + json.dumps(key, ensure_ascii=False) + ', ' + json.dumps(value, ensure_ascii=False) + '}'
                        for key, value in sorted(strings.items()))
    translated = re.sub(r'\b(int|bool|playergroup)\s+((?:lv_|auto)\w+)\s*;', r'\1 \2{};', translate(code))
    return r'''
#include <algorithm>
#include <cassert>
#include <climits>
#include <iostream>
#include <map>
#include <regex>
#include <string>
#include <vector>
using std::string;
using text=string;
using playergroup=unsigned;
using soundlink=string;
using sound=int;
struct color { double r{},g{},b{}; };
''' + globals_text + r'''
long checks=0;
void check(bool ok) { ++checks; assert(ok); }
template<class T> void clearValue(T& x) { x=T{}; }
template<class T,size_t N> void clearValue(T (&x)[N]) { for(auto& y:x) clearValue(y); }
struct Message { text value; int to,from,votes; soundlink sound; };
std::vector<Message> messages;
int actor=8,stops=0,plays=0,disables=0;
std::map<string,string> strings={
''' + table + r'''
};
text StringExternal(const char* key) {
    auto found=strings.find(key);
    if(found!=strings.end()) return found->second;
    if(string(key)=="Param/Value/9D1CF31D") return "<s val=\"ModLeftSize16\">";
    if(string(key)=="Param/Value/258B2E40") return "</s>";
    return "{"+string(key)+"}";
}
text StringToText(string s) { return s; }
text IntToText(int p) { return std::to_string(p); }
string IntToString(int p) { return std::to_string(p); }
color Color(double r,double g,double b) { return {r,g,b}; }
color libNtve_gf_ConvertPlayerColorToColor(int p) { return {double(p),0,0}; }
text TextWithColor(text s,color c) { return "<pc"+std::to_string(int(c.r))+">"+s+"</pc>"; }
soundlink SoundLink(const char* name,int i) { check(i==-1); return name; }
int EventPlayer() { return actor; }
playergroup PlayerGroupSingle(int p) { check(p>=1 && p<=15); return 1u<<p; }
playergroup PlayerGroupAll() { return 0xfffe; }
bool PlayerGroupHasPlayer(playergroup g,int p) { check(p>=1 && p<=15); return (g&(1u<<p))!=0; }
int PlayerGroupNextPlayer(playergroup g,int previous) {
    check(previous>=-1 && previous<=15);
    for(int p=std::max(1,previous+1);p<=15;++p) if(g&(1u<<p)) return p;
    return -1;
}
void SoundStop(sound s,bool fade) { check(s==41 && !fade); ++stops; }
void SoundPlay(soundlink s,playergroup g,double volume,double offset) {
    check(offset==0.0);
    if(s=="GameMusicTerr2222") { check(g==0xfffe && volume==80.0); ++plays; }
    else check(s=="Thor_What" && g==(1u<<actor) && volume==100.0);
}
sound SoundLastPlayed() { return 42; }
void DialogControlSetEnabled(int control,playergroup g,bool enabled) {
    check(control==gv_abilityButtonItem && g==(1u<<actor) && !enabled); ++disables;
}
void gf_CBSystemMessage(text t,int to,int from,int channel,soundlink s,color) {
    check(to>=1 && to<=15 && channel==0);
    messages.push_back({t,to,from,gv_votes[actor],s});
}
''' + prototypes + '\n' + translated + r'''
void reset(int faction=2,int player=8) {
''' + resets + r'''
    actor=player;messages.clear();stops=plays=disables=0;
    gv_alivePlayers=(1u<<actor); // currentPlayers intentionally includes dead recipients
    gv_currentPlayers=(1u<<1)|(1u<<8)|(1u<<15);
    gv_roles[actor][0]=12;gv_roles[actor][1]=1;
    gv_bhFaction[actor]=(faction==1?0:faction);
    gv_chatPrivilege[actor]=true;gv_dayActions=true;
    gv_votes[actor]=1;gv_music[0]=41;gv_abilityButtonItem=31;
    gv_name[actor]="测试名字";gv_playerColor[actor]=13;
    gv_playerSpot[actor]=(actor==15?1:15); // never engine ID
}
string plain(string s) { return std::regex_replace(s,std::regex("<[^>]*>"),""); }
bool factionMessage(const Message& m) { return plain(m.value).find("市长")==0; }
void noReveal() {
    check(!gv_activated[actor] && gv_votes[actor]==1 && gv_music[0]==41);
    check(stops==0 && plays==0 && disables==0);
    for(const auto& m:messages) check(!factionMessage(m));
    for(int p=0;p<16;++p) for(int c=0;c<11;++c) check(!gv_e78AAFE7BDAAE4BA8BE5AE9E[p][c]);
}
void success(int faction,bool button,bool christmas,int options) {
    check(gv_activated[actor]);
    check(gv_votes[actor]==((options&4)?4:((options&2)?3:2)));
    check(disables==1 && plays==!christmas && stops==!christmas);
    check(gv_music[0]==(christmas?41:42));
    for(int p=0;p<16;++p) for(int c=0;c<11;++c)
        check(gv_e78AAFE7BDAAE4BA8BE5AE9E[p][c]==(p==actor && c==7));
    int expectedRecipients=__builtin_popcount(gv_currentPlayers);
    check(int(messages.size())==expectedRecipients*(faction==1?1:2));
    int index=0;
    for(int p:{1,8,15}) if(gv_currentPlayers&(1u<<p)) {
        const auto& m=messages[index++];
        check(m.to==p && m.from==actor && m.votes==1 && m.sound=="UI_ObjectiveComplete");
        check(m.value.find(button?"Param/Value/521DD82D":"Param/Value/B1519496")!=string::npos);
        check(m.value.find("<pc13>测试名字</pc>")!=string::npos);
    }
    for(int p:{1,8,15}) if(faction!=1 && (gv_currentPlayers&(1u<<p))) {
        const auto& m=messages[index++];
        string expected="市长"+std::to_string(gv_playerSpot[actor])+".测试名字是一个"+(faction==2?"黑手党":"三合会")+"成员！";
        check(m.to==p && m.from==actor && m.votes==1 && m.sound=="Silent" && plain(m.value)==expected);
        check(m.value.find("<pc13>")!=string::npos);
        check(m.value.find("测试名字</pc>")!=string::npos);
    }
}
void successfulPaths() {
    for(int faction:{1,2,5}) for(int a:{1,8,15}) for(bool button:{false,true})
    for(bool christmas:{false,true}) for(int options=0;options<16;++options) {
        reset(faction,a);gv_iTSCHRISTMAS=christmas;
        for(int i=0;i<4;++i) gv_roleOptions[1][12][i]=(options&(1<<i));
        check(gf_BHFaction(a)==faction);
        if(button) gf_SKY_1_shizhang(); else check(gt_ASMayorAction_Func(true,true));
        success(faction,button,christmas,options);
        // The actual chat entry rejects both kinds of earlier successful reveal.
        auto before=messages.size();int votes=gv_votes[a];
        check(!gt_ASMayorAction_Func(true,true));
        check(messages.size()==before && gv_votes[a]==votes && disables==1);
        check(!gt_ASMayorAction_Func(true,false));
    }
    for(bool button:{false,true}) {
        reset(5);gv_currentPlayers=0;
        if(button) gf_SKY_1_shizhang(); else check(gt_ASMayorAction_Func(true,true));
        success(5,button,false,0);
    }
}
void conditions() {
    for(int bad=0;bad<8;++bad) for(bool actions:{false,true}) {
        reset();
        if(bad==0) gv_alivePlayers=0;
        if(bad==1) gv_chatPrivilege[actor]=false;
        if(bad==2) gv_gameOver=true;
        if(bad==3) gv_dayActions=false;
        if(bad==4) gv_isNight=true;
        if(bad==5) gv_roles[actor][1]=2;
        if(bad==6) gv_roles[actor][0]=11;
        if(bad==7) gv_roles[actor][1]=5;
        check(!gt_ASMayorAction_Func(true,actions));noReveal();check(messages.empty());
    }
    reset();check(gt_ASMayorAction_Func(true,false));noReveal();check(messages.empty());
    reset();gv_gameOver=true;check(gt_ASMayorAction_Func(false,false));noReveal();
    // testConds=false intentionally preserves the original bypass semantics.
    reset();gv_gameOver=true;check(gt_ASMayorAction_Func(false,true));success(2,false,false,0);
}
void silenceAndVoting() {
    for(bool button:{false,true}) for(bool silenced:{false,true})
    for(bool onTrial:{false,true}) for(bool trial:{false,true}) for(bool voted:{false,true})
    for(int switches=0;switches<16;++switches) {
        reset();gv_silenced[actor][0]=silenced;gv_onTrial=onTrial?actor:1;
        gv_trialOn=trial;gv_playerVote[actor]=voted?15:0;
        gv_roleOptions[2][7][1]=switches&1;gv_roleOptions[2][7][10]=switches&2;
        gv_roleOptions[5][7][1]=switches&4;gv_roleOptions[5][7][10]=switches&8;
        bool silenceBlocked=silenced && (!onTrial || (!(switches&1) && (switches&2)) || (!(switches&4) && (switches&8)));
        bool voteBlocked=voted && !(onTrial && trial);
        if(button) gf_SKY_1_shizhang(); else check(gt_ASMayorAction_Func(true,true));
        if(!silenceBlocked && !voteBlocked) { success(2,button,false,0); continue; }
        noReveal();check(messages.size()==1);
        string key=silenceBlocked?(button?"69E6BA00":"92A44CD7"):(button?"F4CB279E":"270C897C");
        check(messages[0].value=="{Param/Value/"+key+"}" && messages[0].to==actor);
    }
}
void helperBoundaries() {
    for(int bad:{INT_MIN,-1,0,16,INT_MAX}) { reset();gf_BHMayorRevealFaction(bad);check(messages.empty()); }
    for(int faction:{1,2,3,5}) for(int pool:{1,2,3,5}) for(int role:{1,11,12,13,33}) for(bool active:{false,true}) {
        reset(faction);gv_roles[actor][1]=pool;gv_roles[actor][0]=role;gv_activated[actor]=active;
        gf_BHMayorRevealFaction(actor);
        bool expected=pool==1 && role==12 && active && (faction==2 || faction==5);
        check(messages.size()==(expected?3u:0u));
        check(gv_votes[actor]==1 && disables==0 && plays==0 && stops==0);
    }
    for(int spot:{INT_MIN,-1,0,1,8,15,16,INT_MAX}) {
        reset();gv_activated[actor]=true;gv_playerSpot[actor]=spot;
        gf_BHMayorRevealFaction(actor);check(messages.size()==3);
        string expected="市长"+std::to_string(spot>=1 && spot<=15?spot:actor)+".测试名字是一个黑手党成员！";
        for(const auto& m:messages) check(plain(m.value)==expected);
    }
    for(int recipient=1;recipient<=15;++recipient) {
        reset(5);gv_activated[actor]=true;gv_currentPlayers=1u<<recipient;gv_alivePlayers=0;
        gf_BHMayorRevealFaction(actor);
        check(messages.size()==1 && messages[0].to==recipient && messages[0].sound=="Silent");
    }
    reset();gv_activated[actor]=true;gv_currentPlayers=0xfffe;
    gf_BHMayorRevealFaction(actor);check(messages.size()==15);
    reset();gv_activated[actor]=true;gv_gkRole[actor]=33;gv_gkFaction[actor]=3;
    check(gf_BHFaction(actor)==3);gf_BHMayorRevealFaction(actor);check(messages.empty());
    reset();gv_activated[actor]=true;gv_currentPlayers=0;
    gf_BHMayorRevealFaction(actor);check(messages.empty());
}
void cards() {
    for(int options=0;options<16;++options) for(int faction:{1,2,5}) {
        reset(faction);
        for(int i=0;i<4;++i) gv_roleOptions[1][12][i]=options&(1<<i);
        for(auto& field:gv_roleBoxText[actor]) field="sentinel";
        baselineCard(actor);std::vector<text> old(std::begin(gv_roleBoxText[actor]),std::end(gv_roleBoxText[actor]));
        for(auto& field:gv_roleBoxText[actor]) field="sentinel";
        actualCard(actor);
        for(size_t i=0;i<old.size();++i)
            check(gv_roleBoxText[actor][i]==old[i]+(i==2?strings.at("Param/Value/BHFMAYORTRAIT"):""));
        check(gv_roleBoxText[actor][2].find("若你的阵营发生了转变，在你揭示自己的身份时，其他人会知道你是什么阵营。")!=string::npos);
    }
}
int main() {
    successfulPaths();conditions();silenceAndVoting();helperBoundaries();cards();
    std::cout<<"PASS mayor faction reveal: "<<checks<<" checks (engine doubles, not SC2)\n";
}
'''


def main() -> None:
    compiler = shutil.which('g++')
    assert compiler, 'missing dependency: g++ (C++17 and UBSan required)'
    baseline = subprocess.run(['git', 'show', BASELINE + ':work/blackhand/CustomLogic.galaxy'],
                              cwd=ROOT, check=True, capture_output=True, text=True).stdout
    source = SCRIPT.read_text()
    strings = {}
    for line in STRINGS.read_text().splitlines():
        if not line.startswith('Param/Value/'):
            continue

        key, value = line.split('=', 1)
        assert key not in strings, ('duplicate text key', key)
        strings[key] = value

    integration(source, baseline, strings)
    generated = harness(source, baseline, strings)
    with tempfile.TemporaryDirectory(prefix='bh-mayor-reveal-') as directory:
        cpp, executable = Path(directory) / 'mayor.cpp', Path(directory) / 'mayor'
        cpp.write_text(generated)
        subprocess.run([compiler, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra',
                        '-Wno-unused-variable', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)

    print('PASS pinned baseline: reveal bodies + card append only; complete button guards unchanged')


if __name__ == '__main__':
    main()
