#!/usr/bin/env python3
"""Execute the actual extra-rule announcer and its real opening recipient loop.

Engine messaging is an explicit recording double, not an SC2 rendering test.
Checks all eight rule combinations alongside both existing red announcements.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import tempfile
from pathlib import Path

from test_egun import ROOT, SCRIPT, function, mask


RULES = (('Life', 'LIFE', '转世重生'), ('Gang', 'GANG', '团伙作案'),
         ('Dead', 'DEAD', '亡灵小镇'))


def recipient_loop(start: str) -> str:
    live = mask(start)
    loops = []
    for match in re.finditer(r'^\s*for\s*\([^\n]*\)\s*\{', live, re.M):
        end, depth = match.end(), 1
        while depth:
            assert end < len(live)
            depth += (live[end] == '{') - (live[end] == '}')
            end += 1

        body = start[match.start():end]
        if 'gf_XRAnnounce(lv_a);' in body:
            loops.append(body)

    assert len(loops) == 1, 'one real startup recipient loop must own the call'
    return loops[0]


def harness(source: str) -> str:
    helper = function(source, 'gf_XRAnnounce')
    start = function(source, 'gt_Start_Func')
    assert helper.split('{', 1)[0].strip() + ';' in source
    assert start.count('gf_XRAnnounce(lv_a);') == 1
    assert len(re.findall(r'\bgf_XRAnnounce\s*\(', mask(source))) == 3, 'only declaration, definition and the single startup call'
    call = start.index('gf_XRAnnounce(lv_a);')
    assert start.index('if (!runActions)') < start.index('TriggerEnable(TriggerGetCurrent(), false);') < call
    assert start.index('gf_CBClearChat(lv_a);') < start.index('UIClearMessages(PlayerGroupAll(), c_messageAreaDirective);') < call
    assert start.index('Param/Value/BHJANN') < start.index('Param/Value/BHEANN') < call < start.index('Param/Value/93A0DCA8')
    loop = recipient_loop(start)
    assert 'PlayerGroupHasPlayer(gv_currentPlayers, lv_a) == true' in loop
    assert 'gv_alivePlayers' not in loop
    assert 'Wait(' not in loop and 'gf_CBClearChat(' not in loop
    assert 'gv_roleOptions[3][3][1] == true' in loop
    assert 'gv_roleOptions[3][6][4] == true' in loop
    assert not re.search(r'\bgv_\w+(?:\[[^\]]*\])*\s*=(?!=)', mask(helper))
    system = function(source, 'gf_CBSystemMessage')
    assert '(StringExternal("Param/Value/9D1CF31D") + lp_message + StringExternal("Param/Value/258B2E40"))' in system
    assert 'gf_CBMagnifyText(lp_player,' in system and 'gf_ELAddMessage(lp_message,' in system

    labels = dict(line.split('=', 1) for line in (ROOT / 'work/blackhand/strings-shw.txt').read_text().splitlines() if line.startswith('Param/Value/'))
    keys = ['XRANNHEADER', *(f'XRANN{suffix}' for _, suffix, _ in RULES), 'BHJANN', 'BHEANN']
    assert labels['Param/Value/XRANNHEADER'] == '本局游戏启用了以下额外规则：'
    for _, suffix, name in RULES:
        value = labels[f'Param/Value/XRANN{suffix}']
        description = labels[f'Param/Value/XR{suffix}LAB'].split('<n/>', 1)[1]
        assert value == f'「<c val="FFFF00">{name}</c>」：{description}'

    tree = ast.parse((ROOT / 'tools/boot2_build.py').read_text())
    must = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'MUST_HAVE_KEYS' for target in node.targets))
    assert all(f'Param/Value/{key}' in must for key in keys[:4])
    declarations = []
    for name in ('gv_xrLife', 'gv_xrGang', 'gv_xrDead', 'gv_currentPlayers', 'gv_roleOptions'):
        match = re.search(r'^(\w+)((?:\[\d+\])*)\s+' + name + r'\s*(?:=[^;]*)?;', source, re.M)
        assert match, name
        declarations.append(f'{match[1]} {name}{match[2]};')

    constants = []
    for name in sorted(set(re.findall(r'\bauto\w+_(?:ae|ai)\b', loop))):
        match = re.search(r'const int ' + re.escape(name) + r' = -?\d+;', start)
        assert match, name
        constants.append(match[0])

    entries = ',\n'.join('{' + json.dumps('Param/Value/' + key) + ',' + json.dumps(labels['Param/Value/' + key], ensure_ascii=False) + '}' for key in keys)
    print('PASS source: after name/chat reset; existing red rules preserved; current-player loop; yellow labels/shipping keys; scalable chat/log entry', flush=True)
    return r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <map>
#include <string>
#include <vector>
using text = std::string;
using soundlink = std::string;
using playergroup = uint32_t;
''' + '\n'.join(declarations) + r'''
int checks=0, fixtures=0;
#define CHECK(x) do { ++checks; if (!(x)) { std::cerr << "FAIL " << __LINE__ << ": " << #x << '\n'; std::abort(); } } while (0)
const std::map<std::string,text> labels={
''' + entries + r'''
};
text StringExternal(std::string key) { CHECK(labels.count(key)); return labels.at(key); }
int Color(int r,int g,int b) { CHECK(r==0 && g==0 && b==0); return 0; }
soundlink SoundLink(std::string name,int revision) { CHECK(revision==-1); return name; }
bool PlayerGroupHasPlayer(playergroup group,int p) { CHECK(p>=1 && p<=15); return (group&(1u<<p))!=0; }
struct Message { text value; int player; soundlink sound; };
std::vector<Message> messages;
void gf_CBSystemMessage(text value,int player,int sender,int option,soundlink sound,int color) {
    CHECK(player>=1 && player<=15 && sender==0 && option==0 && color==0);
    messages.push_back({value,player,sound});
}
''' + helper + '\nvoid actualOpeningLoop() {\nint lv_a;\n' + '\n'.join(constants) + '\nlv_a = 1;\n' + loop + '\n}\n' + r'''
int main() {
    for(int flags=0;flags<8;++flags) for(int red=0;red<4;++red) for(playergroup group:{0u,1u<<15,(1u<<1)|(1u<<8)|(1u<<15),0xfffeu}) {
        ++fixtures;
        gv_xrLife=(flags&1)!=0; gv_xrGang=(flags&2)!=0; gv_xrDead=(flags&4)!=0;
        gv_roleOptions[3][3][1]=(red&1)!=0; gv_roleOptions[3][6][4]=(red&2)!=0;
        gv_currentPlayers=group; messages.clear(); actualOpeningLoop();
        size_t index=0;
        for(int p=1;p<=15;++p) if(group&(1u<<p)) {
            std::vector<std::string> expected;
            if(red&1) expected.push_back("BHJANN");
            if(red&2) expected.push_back("BHEANN");
            if(flags) expected.push_back("XRANNHEADER");
            if(flags&1) expected.push_back("XRANNLIFE");
            if(flags&2) expected.push_back("XRANNGANG");
            if(flags&4) expected.push_back("XRANNDEAD");
            for(const auto& key:expected) {
                CHECK(index<messages.size());
                const auto& message=messages.at(index++);
                CHECK(message.player==p && message.value==labels.at("Param/Value/"+key));
                CHECK(message.sound==(key=="XRANNLIFE" || key=="XRANNGANG" || key=="XRANNDEAD"?"Silent":"UI_TipSelect"));
            }
        }
        CHECK(index==messages.size());
        CHECK(gv_currentPlayers==group && gv_xrLife==bool(flags&1) && gv_xrGang==bool(flags&2) && gv_xrDead==bool(flags&4));
        CHECK(gv_roleOptions[3][3][1]==bool(red&1) && gv_roleOptions[3][6][4]==bool(red&2));
        messages.clear(); gf_XRAnnounce(0); gf_XRAnnounce(16); CHECK(messages.empty());
    }
    std::cout << "PASS actual announcer + actual startup loop: " << fixtures << " fixtures, " << checks << " checks; UBSan/bounds; all rule/red-switch combinations and recipient masks" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    code = harness(args.script.read_text())
    with tempfile.TemporaryDirectory(prefix='bh-extra-rule-announce-') as directory:
        cpp, executable = Path(directory) / 'announcements.cpp', Path(directory) / 'announcements'
        cpp.write_text(code)
        subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all', str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    main()
