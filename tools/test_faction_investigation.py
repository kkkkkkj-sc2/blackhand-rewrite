#!/usr/bin/env python3
"""Execute actual investigator/Prep/identity helpers with UBSan and bounds.

Extracts complete production Galaxy bodies, including the federal crime-report
trigger invoked by TriggerExecute. Only engine text/color/message/group/trigger
boundaries are doubles. No investigator, faction, disguise, or visit logic is
stubbed. This is not SC2 compiler, rendering, multiplayer, or engine validation.
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
    'gf_BHConverted', 'gf_BHFaction', 'gf_BHRoleName',
    'gf_DQHidden', 'gf_DQSeenPool', 'gf_DQSeenRole', 'gf_DQSeenName',
    'gf_BHInvestigatedRoleName', 'gf_BHVisit', 'gf_BHVisitAction',
    'gf_SKP_1_tanyuan', 'gf_SKP_1_lianbangtanyuan',
    'gt_E78AAFE7BDAAE8AEB0E5BD95_Func',
    'gf_SKF_1_tanyuan', 'gf_SKF_1_lianbangtanyuan',
    'gf_BHSeenFaction', 'gf_BHDeathName', 'gf_GKIs',
)
# Exact original bodies, before the identity-color exception. Canonicalizing
# ONLY the new name call must recover these; this protects ordinary group clues,
# framing, immunity, plague substitution, crime reporting and query bookkeeping.
ORIGINAL_HASHES = {
    'gf_SKF_1_tanyuan': '8e2a4c5c121b49b6757fdafe4e045c7afbe862b8ee473ab719d893b0937b0ee2',
    'gf_SKF_1_lianbangtanyuan': '9430e6bff9b7d296a3dbe8fe64c519ba10b07256eb05b490304cf9a968978a08',
    'gf_DQSeenName': '1754e68b61339935dd41220e4f36898b030fbe6bb683c1b1397de8f4b58a204e',
    'gf_DQSeenPool': '5a38c69693c67325e690aafcea6fe8b3e7ee92fcdd4295d8f83bbdec8b638498',
    'gf_DQSeenRole': '3bc4ebc77c023465784f59fc942d40bda377e5336998e4ac48a0a0940d9b08d3',
    'gf_DQHidden': '94b1e58810ad988c89884b1fd1893db2b1b61fe10dc5c606a6a300364c2cae3a',
    'gf_SKP_1_tanyuan': 'f48e6690a62ca0d10e3494e0caa8b7da5fe4ef4fee0388bbc903f88e6b369afc',
    'gf_SKP_1_lianbangtanyuan': '13244cb325efffe23cf48019c9173528f66dc0c14255be71c58ca4d82b044e5b',
}


def check_wiring(source: str) -> None:
    for name, digest in ORIGINAL_HASHES.items():
        body = function(source, name)
        expected_calls = {'gf_SKF_1_tanyuan': 1, 'gf_SKF_1_lianbangtanyuan': 2}.get(name, 0)
        assert body.count('gf_BHInvestigatedRoleName(') == expected_calls, ('identity call scope', name)
        canonical = body.replace('gf_BHInvestigatedRoleName(', 'gf_DQSeenName(')
        assert hashlib.sha256(canonical.encode()).hexdigest() == digest, ('unexpected clue/disguise/control-flow change', name)

    signature = function(source, 'gf_BHInvestigatedRoleName').split('{', 1)[0].strip()
    assert signature + ';' in source, 'missing helper forward declaration'
    helper = mask(function(source, 'gf_BHInvestigatedRoleName'))
    assert not re.search(r'\bgv_\w+\s*\[', helper), 'helper must reuse faction and seen-name APIs'
    print('PASS wiring: exactly 3 identity calls; original group/framed/immune/plague paths, Prep and global seen APIs preserved', flush=True)


def harness(source: str) -> str:
    check_wiring(source)
    bodies = [function(source, name) for name in NAMES]
    code = '\n\n'.join(bodies)
    used = set(re.findall(r'\bgv_\w+', mask(code))) | {'gv_fzPool', 'gv_fzRole'}
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not used - declarations.keys(), ('missing actual globals', used - declarations.keys())
    global_text = '\n'.join(declarations[name] for name in sorted(used))
    reset = '\n'.join(f'    clearValue({name});' for name in sorted(used) if name not in ('gv_roleNameArray', 'gv_roleInvestigatorArray'))
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    code = translate(code)
    code = re.sub(r'\bfixed((?:\[\d+\])+)\s+(\w+)', r'fixed \2\1', code)
    # Galaxy locals start zeroed; C++ defaults must reflect that, including the
    # complete actual crime-report trigger's local arrays.
    code = re.sub(r'^(\s+(?:int|bool|fixed|text)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', code, flags=re.M)
    supported = set(NAMES) | {
        'if', 'for', 'return', 'Color', 'TextWithColor', 'IntToString',
        'StringExternal', 'PlayerGroupHasPlayer', 'gf_CBSystemMessage',
        'SoundLink', 'TriggerExecute',
    }
    calls = set(re.findall(r'\b(\w+)\s*\(', mask(code)))
    assert not calls - supported, ('unexpected unstubbed logic call', calls - supported)
    print(f'Extracted {len(bodies)} complete production functions and {len(used)} actual global declarations', flush=True)

    return r'''
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <string>
#include <vector>
using std::string;
using text = string;
using fixed = double;
using playergroup = unsigned int;
#define null ""
int checks=0, fixtures=0, triggerCalls=0;
string context;
#define CHECK(...) do { ++checks; if(!(__VA_ARGS__)) { std::cerr << "FAIL [" << context << "] line " << __LINE__ << ": " << #__VA_ARGS__ << '\n'; std::abort(); } } while(0)
''' + global_text + '\n' + headers + r'''
string Color(double r,double g,double b) {
    std::ostringstream out;
    out << std::uppercase << std::hex << std::setfill('0');
    for(double n: {r,g,b}) out << std::setw(2) << int(std::lround(n*255.0/100.0));
    return out.str();
}
text TextWithColor(text value,string color) { return "<c val=\""+color+"\">"+value+"</c>"; }
text StringExternal(string key) {
    const string prefix="Param/Value/";
    CHECK(key.rfind(prefix,0)==0);
    string suffix=key.substr(prefix.size());
    if(suffix.rfind("BHFROLE",0)==0) return "profession-"+suffix.substr(7);
    return "["+suffix+"]";
}
string IntToString(int n) { return std::to_string(n); }
string SoundLink(string name,int index) { CHECK(index==-1); return name; }
bool PlayerGroupHasPlayer(playergroup group,int p) { CHECK(p>=1 && p<=15); return (group&(1u<<p))!=0; }
struct Message { text value; int recipient,sender; };
std::vector<Message> messages;
void gf_CBSystemMessage(text value,int recipient,int sender,int unused,string sound,string color) {
    CHECK(recipient>=1 && recipient<=15 && recipient==sender && unused==0);
    CHECK(sound=="Silent" || sound=="UI_TipSelect");
    CHECK(color=="000000");
    messages.push_back({value,recipient,sender});
}
const int gt_E78AAFE7BDAAE8AEB0E5BD95=1;
void TriggerExecute(int id,bool test,bool wait) {
    CHECK(id==gt_E78AAFE7BDAAE8AEB0E5BD95 && !test && !wait);
    ++triggerCalls;
    CHECK(gt_E78AAFE7BDAAE8AEB0E5BD95_Func(false,true));
}
template<class T> void clearValue(T& value) { value=T{}; }
template<class T,size_t N> void clearValue(T (&value)[N]) { for(auto& item:value) clearValue(item); }
''' + code + r'''
text key(string value) { return "["+value+"]"; }
text expectedColored(int role,int faction) {
    return "<c val=\""+string(faction==2?"D9A08F":"8FBFD1")+"\">profession-"+std::to_string(role)+"</c>";
}
void reset(int investigatorPool,int investigatorRole,int targetPool,int targetRole,int faction) {
''' + reset + r'''
    messages.clear(); triggerCalls=0;
    gv_alivePlayers=(1u<<1)|(1u<<2);
    gv_roles[1][1]=investigatorPool; gv_roles[1][0]=investigatorRole;
    gv_roles[2][1]=targetPool; gv_roles[2][0]=targetRole;
    gv_bhFaction[2]=faction;
    gv_action[1][0]=2;
    if(investigatorRole==27) gf_SKP_1_lianbangtanyuan(1);
    else gf_SKP_1_tanyuan(1);
    CHECK(gv_visitation[1]==2);
    CHECK(gv_roles[2][1]==targetPool && gv_roles[2][0]==targetRole);
}
void expect(std::vector<text> values) {
    CHECK(messages.size()==values.size());
    for(size_t i=0;i<values.size();++i) {
        CHECK(messages[i].value==values[i]);
        CHECK(messages[i].recipient==1 && messages[i].sender==1);
    }
    ++fixtures;
}
void ordinaryMatrix() {
    // Four actual profession investigators (Town, both gang counterparts, and
    // federal), every named convertible Town profession, both faction colors,
    // and the full switch/frame/immunity/plague/revisit option cross-product.
    for(int role=1;role<=35;++role) {
        if(role==28 || role==29) continue;
        for(int faction: {0,2,5}) for(int actor: {1,2,5,27}) for(int bits=0;bits<64;++bits) {
            int pool=actor==27?1:actor;
            bool truth=bits&1, immune=bits&2, plague=bits&4, frame=bits&8, seen=bits&16, pierce=bits&32;
            context="matrix role="+std::to_string(role)+" faction="+std::to_string(faction)+" actor="+std::to_string(actor)+" bits="+std::to_string(bits);
            reset(pool,actor==27?27:4,1,role,faction);
            gv_roleOptions[pool][actor==27?27:4][pool==1?0:1]=truth;
            gv_roleOptions[1][27][1]=pierce;
            gv_immune[2][2]=immune;
            gv_seqAfterPlagueInteract[2]=plague;
            gv_e69FA5E8BF87E4BA86[1][2]=seen;
            if(frame) { gv_framed[2][1]=5; gv_framed[2][0]=4; }
            text identity=faction && role!=8?expectedColored(role,faction):gv_roleNameArray[1][role];
            CHECK(gf_BHDeathName(2)==identity);
            CHECK(gf_BHFaction(2)==(faction?faction:1));
            if(actor==27) {
                // Federal has no framing branch. The direct-identity switch
                // precedes and bypasses immunity/plague/revisit as before.
                gf_SKF_1_lianbangtanyuan(1);
                if(truth) expect({key("14230C7D")+identity+key("3004D2CB")});
                else if(seen && plague) expect({key("E6681CEB")+gv_roleNameArray[1][3]+key("310DC0A4")});
                else if(seen && immune && !pierce) expect({key("5630260B")+gv_roleNameArray[1][1]+key("270AC812")});
                else if(seen) expect({key("D88882E8")+identity+key("F84562C4")});
                else if(immune && !pierce) expect({key("8CADCDD0")+key("A5CC6E1A")+gv_e78AAFE7BDAAE8AEB0E5BD95[0]+key("ACCC5A47")});
                else expect({key("E820B4D2")+key("C3858513")+key("3790D922")+key("E795F349")});
                CHECK(triggerCalls==1 && gv_e69FA5E8BF87E4BA86[1][2]);
            }
            else {
                gf_SKF_1_tanyuan(1);
                bool blocked=immune && !plague;
                bool framed=frame && pool==1 && !blocked;
                if(truth && blocked) expect({key("DCF20712")+gv_roleNameArray[1][1]+key("DC4B7DB1")});
                else if(truth && framed) expect({key("A10FCC35")+gv_roleNameArray[5][4]+key("7F1398F2")});
                else if(truth) expect({key("373E8EF6")+identity+key("385D6DB5")});
                else {
                    int cluePool=blocked?1:(framed?5:1), clueRole=blocked?1:(framed?4:role);
                    string a=blocked?"63C1FF88":(framed?"D3E28725":"A22D1588");
                    string b=blocked?"CE19A5B4":(framed?"33DEC688":"745ADE02");
                    string c=blocked?"11D2EEE9":(framed?"B85DDF50":"D294E2B2");
                    string d=blocked?"5AC819B0":(framed?"E2BA7A11":"FA50C39B");
                    std::vector<text> expected={key(a)+gv_roleInvestigatorArray[cluePool][clueRole][0]+key(b)};
                    if(!gv_roleInvestigatorArray[cluePool][clueRole][1].empty()) expected.push_back(key(c)+gv_roleInvestigatorArray[cluePool][clueRole][1]+key(d));
                    expect(expected);
                }
                CHECK(gv_seqAfterWait[2] && triggerCalls==0);
            }
            CHECK(gv_roles[2][0]==role && gv_roles[2][1]==1 && gv_bhFaction[2]==faction);
            // The global seen API must remain profession-only even when the
            // dedicated true-identity output is faction-colored.
            CHECK(gf_DQSeenName(2)==gv_roleNameArray[1][role]);
            if(!truth && (actor!=27 || !seen)) for(auto message:messages) {
                CHECK(message.value.find("D9A08F")==string::npos);
                CHECK(message.value.find("8FBFD1")==string::npos);
            }
        }
    }
}
void disguiseAndNativeCases() {
    for(int targetPool: {1,2,3,5}) for(int targetRole: {1,4,8,21,22,33}) for(int faction: {0,2,5}) {
        for(bool federal: {false,true}) for(int state=0;state<3;++state) {
            context="native/disguise pool="+std::to_string(targetPool)+" role="+std::to_string(targetRole)+" faction="+std::to_string(faction)+" state="+std::to_string(state);
            reset(1,federal?27:4,targetPool,targetRole,faction);
            gv_dqRevealed[2]=state==1;
            if(state==2) gv_alivePlayers&=~(1u<<2);
            gv_fzPool[2]=5; gv_fzRole[2]=22; // Fake leader is NOT the investigated profession.
            bool hidden=targetPool==3 && targetRole==21 && state==0;
            bool converted=targetPool==1 && faction!=0 && targetRole!=8;
            text name=hidden?gv_roleNameArray[1][6]:(converted?expectedColored(targetRole,faction):gv_roleNameArray[targetPool][targetRole]);
            gv_roleOptions[1][federal?27:4][0]=true;
            if(federal) gf_SKF_1_lianbangtanyuan(1); else gf_SKF_1_tanyuan(1);
            expect({key(federal?"14230C7D":"373E8EF6")+name+key(federal?"3004D2CB":"385D6DB5")});
            if(federal) {
                messages.clear(); gv_roleOptions[1][27][0]=false;
                gv_e69FA5E8BF87E4BA86[1][2]=false;
                gf_SKF_1_lianbangtanyuan(1);
                expect({key("E820B4D2")+key("C3858513")+key("3790D922")+key("E795F349")});
                messages.clear();
                gf_SKF_1_lianbangtanyuan(1);
                expect({key("D88882E8")+name+key("F84562C4")});
                CHECK(triggerCalls==3);
            }
            else {
                messages.clear(); gv_roleOptions[1][4][0]=false;
                gf_SKF_1_tanyuan(1);
                int pool=hidden?1:targetPool, role=hidden?6:targetRole;
                std::vector<text> expected={key("A22D1588")+gv_roleInvestigatorArray[pool][role][0]+key("745ADE02")};
                if(!gv_roleInvestigatorArray[pool][role][1].empty()) expected.push_back(key("D294E2B2")+gv_roleInvestigatorArray[pool][role][1]+key("FA50C39B"));
                expect(expected);
            }
        }
    }
}
void federalRevisitAndCrime() {
    for(int faction: {0,2,5}) {
        context="federal real first visit, crime synthesis, second identity visit";
        reset(1,27,1,4,faction);
        gv_e78AAFE7BDAAE4BA8BE5AE9E[2][0]=true;
        gv_e78AAFE7BDAAE4BA8BE5AE9E[2][10]=true;
        gf_SKF_1_lianbangtanyuan(1);
        expect({key("E820B4D2")+key("C3858513")+key("99AEA75A")+key("ZCCRJ1")+key("D88D8066")+key("E795F349")});
        CHECK(gv_e69FA5E8BF87E4BA86[1][2]);
        messages.clear();
        gf_SKF_1_lianbangtanyuan(1);
        expect({key("D88882E8")+(faction?expectedColored(4,faction):gv_roleNameArray[1][4])+key("F84562C4")});
        CHECK(triggerCalls==2);
    }
}
int main() {
    for(int pool=0;pool<9;++pool) for(int role=0;role<41;++role) {
        string color=pool==1?"40C080":(pool==2?"C96B78":(pool==5?"A0A0FF":"DDAA11"));
        gv_roleNameArray[pool][role]="<c val=\""+color+"\">profession-"+std::to_string(pool)+"/"+std::to_string(role)+"</c>";
        gv_roleInvestigatorArray[pool][role][0]="GROUP("+std::to_string(pool)+","+std::to_string(role)+",0)";
        if(role%2) gv_roleInvestigatorArray[pool][role][1]="GROUP("+std::to_string(pool)+","+std::to_string(role)+",1)";
    }
    ordinaryMatrix(); disguiseAndNativeCases(); federalRevisitAndCrime();
    CHECK(gf_BHInvestigatedRoleName(0)==gv_roleNameArray[0][0]);
    std::cout << "PASS: " << fixtures << " actual investigation fixtures, " << checks << " assertions; UBSan/bounds; Town/native/converted colors; switches, grouped clues, immunity, framing, plague, DQ, FZ, full crime trigger and real revisit" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    source = args.script.read_text(encoding='utf-8')
    code = harness(source)
    with tempfile.TemporaryDirectory(prefix='bh-investigation-') as tmp:
        cpp, exe = Path(tmp) / 'investigation.cpp', Path(tmp) / 'investigation'
        cpp.write_text(code, encoding='utf-8')
        warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
        subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
