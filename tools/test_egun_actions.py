#!/usr/bin/env python3
"""Execute actual 恶棍 panel/helper/neutral dispatcher bodies under C++17 UBSan.

Only Galaxy declarations are translated (including Galaxy's zero-initialized
locals). Engine UI calls are observable per-player doubles, not SC2 rendering.
Unrelated dispatcher role helpers fail if reached; unknown dependencies fail
closed. No game, strings, existing tests, or build files are written.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from test_egun import SCRIPT, function, mask, translate

NAMES = ('gf_RAEgunActions', 'gf_SKA_3_egun', 'gt_ASActionButtonANeutral_Func')
BOUNDARIES = {
    'gf_SKA_3_' + name for name in (
        'lianhuanshashou', 'kaitangshou', 'ganranzhe', 'tiaotingzhe', 'limao',
        'yanluo', 'tianxuanzhe', 'wenyisanbuzhe', 'shengcunzhe', 'xiaochou',
        'nvwu', 'ximingren', 'zonghuozhe', 'shiyizhe', 'xiejiaotu',
        'sharenkuang', 'wuyi', 'shenjiguan', 'cuanweizhe', 'duoluoshenpanzhe',
        'yingwuzhe', 'dugui', 'yuanhun')
} | {'gf_SKA_1_yijing'}
ENGINE = {
    'if', 'for', 'while', 'return', 'PlayerGroupSingle', 'PlayerGroupHasPlayer',
    'DialogControlSetEnabled', 'DialogControlSetVisible', 'DialogControlIsVisible',
    'DialogControlSetSize', 'libNtve_gf_SetDialogItemTooltip',
    'libNtve_gf_SetDialogItemColor', 'libNtve_gf_SetDialogItemImage',
    'libNtve_gf_SetDialogItemImage2', 'StringExternal', 'Color', 'SoundLink',
    'gf_CBSystemMessage', 'TextWithColor', 'StringToText',
    'libNtve_gf_ConvertPlayerColorToColor', 'EventPlayer', 'EventDialogControl', 'Wait',
}


def harness(source: str) -> str:
    bodies = [function(source, name) for name in NAMES]
    code = '\n\n'.join(bodies)
    live = mask(code)
    calls = set(re.findall(r'\b(\w+)\s*\(', live))
    assert not calls - ENGINE - BOUNDARIES - set(NAMES), ('unknown dependency', calls - ENGINE - BOUNDARIES - set(NAMES))
    constants = set(re.findall(r'\bc_\w+', live))
    assert constants <= {'c_timeGame'}, ('unknown constants', constants)
    required = set(re.findall(r'\bgv_\w+', live)) | {
        'gv_roles', 'gv_action', 'gv_alivePlayers', 'gv_actionDialogItem',
        'gv_switchButtonItem', 'gv_isNight', 'gv_name', 'gv_number', 'gv_playerColor',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not required - declarations.keys(), ('missing globals', required - declarations.keys())
    globals_text = '\n'.join(declarations[n] for n in sorted(required))
    resets = '\n'.join(f'    clearValue({n});' for n in sorted(required))
    prototypes = '\n'.join(b.split('{', 1)[0].strip() + ';' for b in bodies)
    stubs = '\n'.join(f'void {name}(int, int) {{ fail("unrelated {name}"); }}' for name in sorted(BOUNDARIES))
    # Galaxy numeric/bool locals have default values; C++ otherwise leaves them
    # indeterminate. No expressions, guards, assignments or calls are rewritten.
    translated = re.sub(r'\b(int|bool)\s+(lv_\w+)\s*;', r'\1 \2{};', translate(code))
    return r'''
#include <algorithm>
#include <array>
#include <climits>
#include <cstdlib>
#include <iostream>
#include <random>
#include <string>
#include <tuple>
#include <vector>
using std::string;
using text = string;
using playergroup = unsigned;
using soundlink = string;
struct color {
    double r{},g{},b{};
    bool operator==(const color& x) const { return std::tie(r,g,b)==std::tie(x.r,x.g,x.b); }
};
''' + globals_text + r'''
[[noreturn]] void fail(const string& s) { std::cerr << s << std::endl; std::abort(); }
long checks=0;
void check(bool b, const string& why="assertion") { ++checks; if(!b) fail(why); }
template<class T> void clearValue(T& x) { x=T{}; }
template<class T,size_t N> void clearValue(T (&x)[N]) { for(auto& y:x) clearValue(y); }
struct Control {
    bool visible=true,enabled=true;
    string tip="sentinel",image="sentinel",highlight="sentinel";
    color tint{-1,-2,-3};
    int width=-1,height=-1;
    bool operator==(const Control& x) const {
        return std::tie(visible,enabled,tip,image,highlight,tint,width,height)==
               std::tie(x.visible,x.enabled,x.tip,x.image,x.highlight,x.tint,x.width,x.height);
    }
};
using UI = std::array<std::array<Control,16>,64>;
UI ui;
struct Message { text value; int player; };
std::vector<Message> messages;
int eventPlayer=1,eventControl=1,scope=1,writes=0;
constexpr int c_timeGame=0;
playergroup PlayerGroupSingle(int p) { check(p>=1 && p<=15,"single group bounds"); return 1u<<p; }
bool PlayerGroupHasPlayer(playergroup group,int p) {
    check(p>=1 && p<=15,"membership bounds"); return (group & (1u<<p))!=0;
}
Control& control(int id,playergroup group) {
    check(id>=1 && id<64,"control bounds");
    check(scope>=1 && scope<=15 && group==(1u<<scope),"UI escaped actor's player group");
    ++writes; return ui[id][scope];
}
void DialogControlSetVisible(int id,playergroup g,bool v) { control(id,g).visible=v; }
void DialogControlSetEnabled(int id,playergroup g,bool v) { control(id,g).enabled=v; }
void DialogControlSetSize(int id,playergroup g,int w,int h) { auto& c=control(id,g); c.width=w;c.height=h; }
void libNtve_gf_SetDialogItemTooltip(int id,text tip,playergroup g) { control(id,g).tip=tip; }
void libNtve_gf_SetDialogItemColor(int id,color v,playergroup g) { control(id,g).tint=v; }
void libNtve_gf_SetDialogItemImage(int id,string v,playergroup g) { control(id,g).image=v; }
void libNtve_gf_SetDialogItemImage2(int id,string v,playergroup g) { control(id,g).highlight=v; }
bool DialogControlIsVisible(int id,int p) { check(id>=1 && id<64 && p>=1 && p<=15); return ui[id][p].visible; }
int EventPlayer() { return eventPlayer; }
int EventDialogControl() { return eventControl; }
void Wait(double t,int clock) { check(t==0.0 && clock==c_timeGame); }
color Color(double r,double g,double b) { return {r,g,b}; }
color libNtve_gf_ConvertPlayerColorToColor(int p) { return {double(p),0,0}; }
text TextWithColor(text t,color) { return t; }
text StringToText(string t) { return t; }
text StringExternal(const char* key) {
    string s=key;
    if(s=="Param/Value/EGTIP") return "使其负伤";
    if(s=="Param/Value/EGCANCELTIP") return "取消";
    return "{"+s+"}";
}
soundlink SoundLink(const char* s,int index) { check(index==-1); return s; }
void gf_CBSystemMessage(text t,int sender,int receiver,int channel,soundlink sound,color) {
    check(sender==scope && receiver==scope && channel==0 && sound=="Silent","message leaked");
    messages.push_back({t,receiver});
}
''' + stubs + '\n' + prototypes + '\n' + translated + r'''
int primary(int p) { return gv_actionDialogItem[p][5]; }
int secondary(int p) { return gv_actionDialogItem[p][6]; }
bool alive(int p) { return (gv_alivePlayers & (1u<<p))!=0; }
int cancellations() {
    return std::count_if(messages.begin(),messages.end(),[](const Message& m) {
        return m.value=="{Param/Value/EGCANCEL}";
    });
}
void reset(int a) {
''' + resets + r'''
    ui=UI{}; messages.clear(); writes=0; scope=eventPlayer=a; eventControl=1;
    gv_alivePlayers=0xfffe; gv_isNight=true; gv_switchButtonItem=31;
    for(int p=1;p<=15;++p) {
        gv_actionDialogItem[p][5]=p; gv_actionDialogItem[p][6]=p+15;
        gv_roles[p][0]=1; gv_roles[p][1]=1;
        gv_name[p]="P"+std::to_string(p); gv_number[p]=std::to_string(p); gv_playerColor[p]=p;
        gv_action[p][1]=70+p;
    }
    gv_roles[a][0]=28;gv_roles[a][1]=3;
}
void panel(int a,int selected) {
    check(gv_action[a][0]==selected,"selected action differs");
    check(!ui[gv_switchButtonItem][a].enabled,"switch enabled");
    for(int p=1;p<=15;++p) {
        const auto& c=ui[primary(p)][a];
        bool expected=alive(p) && (p==a ? selected!=0 : p!=selected);
        check(c.visible==expected,"primary visibility p="+std::to_string(p));
        check(!ui[secondary(p)][a].visible,"secondary visible");
        if(expected) {
            check(c.tip==(p==a?"取消":"使其负伤"),"exact tooltip");
            check(c.width==120 && c.height==30,"button size");
            check(c.image=="ActionNormal.dds" && c.highlight=="ActionHighlight.dds","button images");
            check(c.tint==(p==a?Color(50.20,50.20,50.20):Color(76.86,47.84,26.67)),"button color");
        }
    }
    for(int p=1;p<=15;++p) {
        check(gv_action[p][1]==70+p,"secondary action mutated");
        if(p!=a) check(gv_action[p][0]==0,"other player's action mutated");
    }
}
void render(int a) {
    UI before=ui; scope=a;gf_RAEgunActions(a);
    for(int id=1;id<64;++id) for(int p=1;p<=15;++p) if(p!=a)
        check(ui[id][p]==before[id][p],"render leaked to another player");
}
bool click(int a,int target,bool conds=true,bool actions=true) {
    scope=eventPlayer=a; eventControl=primary(target);
    UI before=ui;
    bool result=gt_ASActionButtonANeutral_Func(conds,actions);
    for(int id=1;id<64;++id) for(int p=1;p<=15;++p) if(p!=a)
        check(ui[id][p]==before[id][p],"dispatch leaked to another player");
    return result;
}
void noOp(int a,int t,bool direct) {
    auto before=ui;auto count=messages.size();int old[16][2];
    for(int p=0;p<16;++p) for(int i=0;i<2;++i) old[p][i]=gv_action[p][i];
    scope=a;
    if(direct) gf_SKA_3_egun(a,t); else click(a,t);
    check(ui==before && messages.size()==count,"invalid/no-op changed UI or messages");
    for(int p=0;p<16;++p) for(int i=0;i<2;++i) check(old[p][i]==gv_action[p][i],"invalid/no-op changed action");
}
void examples() {
    for(int a:{1,8,15}) {
        int t=a==8?15:8,other=a==1?15:1;
        reset(a);render(a);panel(a,0);
        noOp(a,a,true);noOp(a,a,false);
        check(click(a,t));panel(a,t);
        noOp(a,t,false);noOp(a,t,true);
        render(a);panel(a,t);
        check(click(a,other));panel(a,other);
        check(click(a,a));panel(a,0);check(cancellations()==1,"cancel count");
        noOp(a,a,true);noOp(a,a,false);check(cancellations()==1);
        render(a);panel(a,0);
        for(int bad:{INT_MIN,-1,0,16,INT_MAX}) { noOp(a,bad,true);noOp(bad,t,true); }
        gv_alivePlayers &= ~(1u<<t);render(a);panel(a,0);
        noOp(a,t,true);noOp(a,t,false);
        // The helper must reject a dead source even with a nonzero action.
        gv_action[a][0]=other;gv_alivePlayers &= ~(1u<<a);
        noOp(a,other,true);noOp(a,a,true);noOp(a,other,false);
        // Panel cleans every malformed selection, including a dead selection.
        reset(a);
        for(int bad:{INT_MIN,-1,16,INT_MAX,a,t}) {
            gv_action[a][0]=bad;
            if(bad==t) gv_alivePlayers &= ~(1u<<t);
            render(a);panel(a,0);
        }
        // Actual dispatcher gates: condition-only, hidden, wrong pool, daytime.
        reset(a);render(a);
        check(click(a,t,true,false));panel(a,0);check(messages.empty());
        gv_roles[a][1]=1;noOp(a,t,false);
        gv_roles[a][1]=3;gv_isNight=false;noOp(a,t,false);
        gv_isNight=true;ui[primary(t)][a].visible=false;noOp(a,t,false);
        // Conditions return false for blocked requests, not merely no mutation.
        check(!click(a,t));ui[primary(t)][a].visible=true;
        gv_isNight=false;check(!click(a,t));gv_isNight=true;
        gv_roles[a][1]=2;check(!click(a,t));
    }
}
void randomized() {
    std::mt19937 rng(0xE628AC71);
    for(int a:{1,8,15}) for(int fixture=0;fixture<100;++fixture) {
        reset(a);
        for(int p=1;p<=15;++p) if(p!=a && rng()%5==0) gv_alivePlayers &= ~(1u<<p);
        render(a);int selected=0,cancelCount=0;
        for(int step=0;step<100;++step) {
            int t=1+rng()%15;
            if(rng()%7==0) { render(a);panel(a,selected);continue; }
            bool direct=rng()%3==0;
            bool allowed=alive(t) && (direct || ui[primary(t)][a].visible);
            if(allowed) {
                if(t==a && selected) { selected=0;++cancelCount; }
                else if(t!=a && t!=selected) selected=t;
            }
            if(direct) { scope=a;gf_SKA_3_egun(a,t); } else click(a,t);
            panel(a,selected);check(cancellations()==cancelCount,"random cancel count");
        }
    }
}
int main() {
    examples();randomized();
    std::cout << "PASS: actual panel/helper/full neutral dispatcher; seats 1/8/15; "
              << "30000 seeded steps; scoped visibility/tooltip/color/size/images; "
              << checks << " checks; UBSan/bounds" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--strings', type=Path, default=SCRIPT.parent / 'strings-eg.txt')
    parser.add_argument('--cxx', help='One compiler; default runs every available GCC/Clang')
    args = parser.parse_args()
    strings = args.strings.read_text()
    for key, value in (('EGTIP', '使其负伤'), ('EGCANCELTIP', '取消')):
        matches = re.findall(r'^Param/Value/' + key + r'=(.*)$', strings, re.M)
        assert matches == [value], (key, 'exact unique string required', matches)

    source = args.script.read_text()
    code = harness(source)
    compilers = [args.cxx] if args.cxx else [c for c in ('g++', 'clang++') if shutil.which(c)]
    assert compilers, 'no C++ compiler available'
    print(f'Actual bodies: {args.script}; strings: {args.strings}', flush=True)
    with tempfile.TemporaryDirectory(prefix='bh-egun-actions-') as tmp:
        cpp = Path(tmp) / 'actions.cpp'
        cpp.write_text(code)
        for index, cxx in enumerate(compilers):
            exe = Path(tmp) / f'actions-{index}'
            warnings = ['-Wno-parentheses-equality'] if 'clang' in cxx else []
            command = [cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                       '-Wno-unused-variable', '-Wno-unused-parameter', *warnings,
                       '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                       str(cpp), '-o', str(exe)]
            print('Compile:', ' '.join(command), flush=True)
            subprocess.run(command, check=True)
            subprocess.run([str(exe)], check=True, env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})


if __name__ == '__main__':
    main()
