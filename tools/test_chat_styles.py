#!/usr/bin/env python3
"""Actual-body C++17 UBSan/bounds regression for system chat and magnification.

Extracts gf_CBSystemMessage and the complete magnification trigger body without
rewriting logic. StringExternal uses role_gen.load_gamestrings' merged zhCN
values. Engine controls, sounds, debug and event-log are scoped observables;
the gf_CBMagnifyText boundary invokes the actual trigger with its actual args.
This is not an SC2 renderer or Galaxy compiler test. No existing files change.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from role_gen import load_gamestrings
from test_egun import SCRIPT, function, mask, translate

NAMES = ('gf_CBSystemMessage', 'auto_gf_CBMagnifyText_TriggerFunc')
CALLS = {
    *NAMES, 'if', 'for', 'return', 'SoundLink', 'SoundPlay', 'PlayerGroupSingle',
    'StringExternal', 'DialogControlIsVisible', 'DialogControlIsEnabled',
    'DialogControlSetVisible', 'DialogControlSetEnabled',
    'libNtve_gf_SetDialogItemText', 'libNtve_gf_SetDialogItemColor',
    'libNtve_gf_DialogItemText', 'libNtve_gf_DialogItemColor',
    'gf_ELAddMessage', 'TriggerDebugOutput', 'gf_CBMagnifyText', 'TextReplaceWord',
}


def harness(source: str, gs: dict[str, str]) -> str:
    bodies = [function(source, name) for name in NAMES]
    code = '\n\n'.join(bodies)
    live = mask(code)
    calls = set(re.findall(r'\b(\w+)\s*\(', live))
    assert not calls - CALLS, ('unknown call', calls - CALLS)
    replacements = re.findall(r'TextReplaceWord\(lv_t, StringExternal\("([^"]+)"\), StringExternal\("([^"]+)"\), c_stringReplaceAll, c_stringCase\)', code)
    assert len(replacements) == 32, ('actual replacement table changed', len(replacements))
    assert len(set(replacements)) == 32, 'replacement keys must be distinct'
    keys = set(re.findall(r'StringExternal\("([^"]+)"\)', code)) | {
        'Param/Value/EGNIGHT', 'Param/Value/D5208FE7',
    }
    assert not keys - gs.keys(), ('missing merged strings', keys - gs.keys())
    assert gs['Param/Value/EGNIGHT'] == '<s val="ModLeftSize16"><c val="FF0000">你听见痛苦的呻吟声...</c></s>'
    assert gs['Param/Value/D5208FE7'].startswith('<s val="ModLeftSize16"><c val="FF0000">')
    assert gs['Param/Value/D5208FE7'].endswith('</c></s>')
    strings = ',\n'.join('{' + json.dumps(k) + ',' + json.dumps(gs[k], ensure_ascii=False) + '}' for k in sorted(keys))
    required = set(re.findall(r'\b(?:gv_\w+|auto_gf_CBMagnifyText_lp_\w+)\b', live))
    declarations = {}
    for m in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = m.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not required - declarations.keys(), ('missing globals', required - declarations.keys())
    globals_text = '\n'.join(declarations[n] for n in sorted(required))
    resets = '\n'.join(f'    clearValue({n});' for n in sorted(required))
    constants = set(re.findall(r'\bge_Magnify_\w+', live)) | {'ge_Magnify_Unmagnify'}
    constants_text = []
    for name in sorted(constants):
        match = re.search(r'^const int ' + re.escape(name) + r' = (-?\d+);', source, re.M)
        assert match, ('unknown enum', name)
        constants_text.append(match[0])

    assert set(re.findall(r'\bc_\w+', live)) == {'c_stringReplaceAll', 'c_stringCase'}
    prototypes = '\n'.join(b.split('{', 1)[0].strip() + ';' for b in bodies)
    return r'''
#include <array>
#include <cstdlib>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <tuple>
#include <vector>
using std::string;
using text=string;
using soundlink=string;
using playergroup=unsigned;
struct color {
    double r{},g{},b{};
    bool operator==(const color& c) const { return std::tie(r,g,b)==std::tie(c.r,c.g,c.b); }
};
''' + globals_text + '\n' + '\n'.join(constants_text) + r'''
std::map<string,string> gs={
''' + strings + r'''
};
constexpr int c_stringReplaceAll=1,c_stringCase=1;
long checks=0;
void check(bool c,const string& msg="assertion") {
    ++checks;if(!c) { std::cerr<<msg<<std::endl;std::exit(1); }
}
template<class T> void clearValue(T& x) { x=T{}; }
template<class T,size_t N> void clearValue(T (&x)[N]) { for(auto& v:x) clearValue(v); }
struct Control {
    text value="sentinel";
    color tint{-1,-2,-3};
    bool visible=false,enabled=false;
    bool operator==(const Control& x) const {
        return std::tie(value,tint,visible,enabled)==std::tie(x.value,x.tint,x.visible,x.enabled);
    }
};
using UI=std::array<std::array<Control,16>,64>;
UI ui;
int scope=1;
struct Event { text value;int player; color tint;int sender,option; };
std::vector<Event> events;
std::vector<soundlink> sounds;
std::vector<text> debug;
std::set<std::pair<text,text>> replaced;
Control& at(int id,int p) {
    check(id>0 && id<64 && p>0 && p<16,"control bounds");return ui[id][p];
}
Control& scoped(int id,playergroup g) {
    check(g==(1u<<scope),"write escaped target player");return at(id,scope);
}
playergroup PlayerGroupSingle(int p) { check(p>=1 && p<=15);return 1u<<p; }
text StringExternal(const char* k) { check(gs.count(k)==1,string("unknown string ")+k);return gs.at(k); }
text libNtve_gf_DialogItemText(int id,int p) { check(p==scope,"read escaped target player");return at(id,p).value; }
color libNtve_gf_DialogItemColor(int id,int p) { check(p==scope);return at(id,p).tint; }
bool DialogControlIsVisible(int id,int p) { check(p==scope);return at(id,p).visible; }
bool DialogControlIsEnabled(int id,int p) { check(p==scope);return at(id,p).enabled; }
void libNtve_gf_SetDialogItemText(int id,text v,playergroup g) { scoped(id,g).value=v; }
void libNtve_gf_SetDialogItemColor(int id,color c,playergroup g) { scoped(id,g).tint=c; }
void DialogControlSetVisible(int id,playergroup g,bool b) { scoped(id,g).visible=b; }
void DialogControlSetEnabled(int id,playergroup g,bool b) { scoped(id,g).enabled=b; }
soundlink SoundLink(const char* s,int index) { check(index==-1);return s; }
void SoundPlay(soundlink s,playergroup g,double volume,double offset) {
    check(g==(1u<<scope) && volume==100 && offset==0,"sound route changed");sounds.push_back(s);
}
void gf_ELAddMessage(text v,int p,color c,int sender,int option) {
    check(p==scope,"event-log player leaked");events.push_back({v,p,c,sender,option});
}
void TriggerDebugOutput(int channel,text v,bool flag) { check(channel==1 && !flag);debug.push_back(v); }
text TextReplaceWord(text v,text from,text to,int all,int sensitive) {
    check(all==c_stringReplaceAll && sensitive==c_stringCase && !from.empty());
    replaced.insert({from,to});
    size_t offset=0;
    while((offset=v.find(from,offset))!=string::npos) { v.replace(offset,from.size(),to);offset+=to.size(); }
    return v;
}
''' + prototypes + r'''
// Only the engine trigger invocation is doubled, not magnification logic.
void gf_CBMagnifyText(int player,int mode) {
    auto_gf_CBMagnifyText_lp_player=player;auto_gf_CBMagnifyText_lp_magnify=mode;
    check(auto_gf_CBMagnifyText_TriggerFunc(false,false));
}
''' + translate(code) + r'''
const std::array<std::array<string,3>,8> families={{
    {{"LastWill","LastWillBig","LastWillBigger"}},
    {{"International17","CustomInternational","ChatBarRecipient"}},
    {{"ModLeftSize16","ModLeftSize20","ModLeftSize24"}},
    {{"ModCenterSize16","ModCenterSize20","ModCenterSize24"}},
    {{"ModRightSize16","ModRightSize20","ModRightSize24"}},
    {{"ModLeftSize16Bold","ModLeftSize20Bold","ModLeftSize24Bold"}},
    {{"ModCenterSize16Bold","ModCenterSize20Bold","ModCenterSize24Bold"}},
    {{"ModRightSize16Bold","ModRightSize20Bold","ModRightSize24Bold"}}
}};
string tag(const string& s) { return "<s val=\""+s+"\">"; }
// Independent oracle parses complete style tags and maps semantic families.
// Magnify/super ONLY consume base styles, not previously enlarged history.
text expected(text input,int mode) {
    string result;size_t pos=0;
    while(pos<input.size()) {
        auto start=input.find("<s val=\"",pos);
        if(start==string::npos) { result+=input.substr(pos);break; }
        result+=input.substr(pos,start-pos);
        auto end=input.find('>',start);check(end!=string::npos);
        string token=input.substr(start,end-start+1),output=token;
        for(const auto& f:families) for(int i=0;i<3;++i) if(token==tag(f[i])) {
            if(mode==ge_Magnify_Unmagnify) output=tag(f[0]);
            else if(i==0) output=tag(f[mode==ge_Magnify_Magnify?1:2]);
        }
        result+=output;pos=end+1;
    }
    return result;
}
int rowid(int row,int col=0) { return gv_chatBoxItem[row][col]; }
void reset(int p) {
''' + resets + r'''
    ui=UI{};events.clear();sounds.clear();debug.clear();scope=p;
    for(int row=0;row<=20;++row) for(int col=0;col<3;++col) gv_chatBoxItem[row][col]=row*3+col+1;
    // Row20 column2 has ID63; all accessed row text/background IDs remain <64.
    for(int sender=0;sender<18;++sender) gv_eventLogChatEquivalent[sender]=1000+sender;
    for(int other=1;other<=15;++other) if(other!=p) {
        gv_chatColorBoolean[other]=other%2;
        gv_magnified[other][0]=other%2;gv_magnified[other][1]=!(other%2);
    }
}
void isolated(const UI& before,int p) {
    for(int id=1;id<64;++id) for(int other=1;other<=15;++other) if(other!=p)
        check(ui[id][other]==before[id][other],"other player's UI changed");
    for(int other=1;other<=15;++other) if(other!=p) {
        check(gv_chatColorBoolean[other]==bool(other%2));
        check(gv_magnified[other][0]==bool(other%2) && gv_magnified[other][1]==!bool(other%2));
    }
}
void magnify(int p,int mode) {
    auto before=ui;gf_CBMagnifyText(p,mode);
    for(int row=1;row<=20;++row) {
        int id=rowid(row),bg=rowid(row,1);
        auto want=before[id][p];want.value=expected(want.value,mode);
        check(ui[id][p]==want,"magnify text/color/visibility/enabled changed unexpectedly");
        check(ui[bg][p]==before[bg][p],"magnify background changed");
    }
    isolated(before,p);
}
void insertion() {
    std::vector<text> inputs={"plain中文",StringExternal("Param/Value/EGNIGHT"),
        "<s val=\"LastWill\"><c val=\"FF0000\"><b>legacy</b></c></s>",
        "<s val=\"ModCenterSize20Bold\"><c val=\"00FF00\">nested</c></s>"};
    for(int p:{1,8,15}) for(int occupied:{0,7,20}) for(int mode:{-1,0,1})
    for(int sender:{0,1,8,15,16,17}) for(const auto& input:inputs)
    for(const auto& sound:std::vector<string>{"Silent","30SecondSilence","CivilianDeath"}) {
        reset(p);
        for(int row=21-occupied;row<=20;++row) {
            auto& c=at(rowid(row),p);auto& bg=at(rowid(row,1),p);
            c.value=tag(families[row%8][row%3])+"<c val=\"FF0000\"><b>history"+std::to_string(row)+"</b></c></s>";
            c.visible=bg.visible=true;c.enabled=bg.enabled=row%2;
            bg.tint={double(row),double(row+1),double(row+2)};
        }
        gv_magnified[p][0]=mode>=0;gv_magnified[p][1]=mode==1;
        auto before=ui;
        int option=sender%2==0?-1:sender;
        color tint{10,20,30};
        gf_CBSystemMessage(input,p,sender,option,sound,tint);
        int inserted=occupied==20?1:20-occupied;
        text wrapped=tag("ModLeftSize16")+input+"</s>";
        for(int row=1;row<=20;++row) {
            auto want=before[rowid(row)][p],bg=before[rowid(row,1)][p];
            if(row==inserted) {
                want.value=wrapped;want.enabled=true;bg.enabled=true;bg.tint=tint;
                if(occupied<20) want.visible=bg.visible=true;
            } else if(occupied==20) {
                want.value=before[rowid(row-1)][p].value;
                want.enabled=before[rowid(row-1)][p].enabled;
                bg.tint=before[rowid(row-1,1)][p].tint;
                bg.enabled=before[rowid(row-1)][p].enabled;
            }
            if(mode>=0) want.value=expected(want.value,mode);
            check(ui[rowid(row)][p]==want,"insert/shift text row mismatch");
            check(ui[rowid(row,1)][p]==bg,"insert/shift background mismatch");
        }
        check(gv_chatColorBoolean[p],"chat color boolean not toggled");
        check(events.size()==1 && events[0].value==input && events[0].player==p && events[0].tint==tint
              && events[0].sender==1000+sender && events[0].option==option,"raw event-log routing changed");
        check(sounds.size()==size_t(sound=="CivilianDeath"),"sound suppression changed");
        if(!sounds.empty()) check(sounds[0]==sound);
        check(debug.size()==size_t(option==-1));if(option==-1) check(debug[0]==input);
        isolated(before,p);
        // Normalization + switching modes is the existing OnOff contract.
        magnify(p,ge_Magnify_Unmagnify);auto normal=ui;
        for(int next:{ge_Magnify_Magnify,ge_Magnify_SuperMagnify}) {
            magnify(p,next);magnify(p,ge_Magnify_Unmagnify);
            check(ui==normal,"red/nested/mixed-style history did not round-trip");
        }
    }
}
void allFamilies() {
    for(int p:{1,8,15}) {
        reset(p);
        for(const auto& f:families) for(int size=0;size<3;++size) {
            auto& c=at(rowid(20),p);
            c.value=tag(f[size])+"<c val=\"FF0000\"><i>red</i></c>"+tag(f[0])+"nested</s></s>";
            for(int mode:{ge_Magnify_Magnify,ge_Magnify_SuperMagnify,ge_Magnify_Unmagnify}) {
                text original=c.value;magnify(p,mode);c.value=original;
            }
        }
    }
    check(replaced.size()==32,"not all 32 actual replacement pairs exercised");
}
int main() {
    insertion();allFamilies();
    std::cout<<"PASS: actual system body + actual 32-pair magnify body; merged zhCN; seats1/8/15; "
             <<"empty/partial/full shift; all8families; normal/magnify/super; raw eventlog/sound/debug routes; "
             <<checks<<" checks; UBSan/bounds"<<std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', help='One compiler; default runs available GCC and Clang')
    args = parser.parse_args()
    code = harness(args.script.read_text(), load_gamestrings())
    compilers = [args.cxx] if args.cxx else [c for c in ('g++', 'clang++') if shutil.which(c)]
    assert compilers, 'no C++ compiler'
    print(f'Actual bodies: {args.script}; merged strings: role_gen.load_gamestrings', flush=True)
    with tempfile.TemporaryDirectory(prefix='bh-chat-styles-') as tmp:
        cpp = Path(tmp) / 'chat.cpp'
        cpp.write_text(code)
        for index, cxx in enumerate(compilers):
            exe = Path(tmp) / f'chat-{index}'
            warnings = ['-Wno-parentheses-equality'] if 'clang' in cxx else []
            command = [cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                       '-Wno-unused-parameter', *warnings, '-fsanitize=undefined,bounds',
                       '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)]
            print('Compile:', ' '.join(command), flush=True)
            subprocess.run(command, check=True)
            subprocess.run([str(exe)], check=True, env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})


if __name__ == '__main__':
    main()
