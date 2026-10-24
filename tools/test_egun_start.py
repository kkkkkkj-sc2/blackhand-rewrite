#!/usr/bin/env python3
"""Execute actual startup loop and 恶棍 night wrapper with GCC/Clang UBSan.

Role-card rendering and RA panel work are explicit boundary doubles. Consumption
is simulated, not an attack compilation; no SC2 compiler/renderer claim is made.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from test_egun import SCRIPT, function, mask


def harness(source: str) -> str:
    startup = function(source, 'gf_DisplayRoles')
    live = mask(startup)
    loops = list(re.finditer(r'\bfor\s*\([^{}]*\)\s*\{', live))
    assert len(loops) == 4, 'startup loop layout changed'
    loop = loops[1]
    assert 'auto74C8A26A' in loop[0], 'wrong startup loop'
    end, depth = loop.end(), 1
    while depth:
        assert end < len(live), 'unbalanced startup loop'
        depth += (live[end] == '{') - (live[end] == '}')
        end += 1

    init = re.search(r'lv_a\s*=\s*1\s*;\s*$', live[:loop.start()])
    assert init, 'missing actual loop initialization'
    declarations = re.findall(r'const int auto74C8A26A_(?:ae|ai)\s*=\s*-?\d+\s*;', live)
    assert len(declarations) == 2, 'missing loop bound/step declarations'
    fragment = startup[init.start():end]
    assert 'gf_RTRoleCard' in fragment and 'gv_immuneChance' in fragment
    night = function(source, 'gf_SKN_3_egun')
    assert 'gv_immune' not in mask(night), 'night setup must never refill'
    ra = mask(function(source, 'gf_RAEgunActions'))
    assert 'gv_immune' not in ra, 'RA boundary must not touch shields'
    assert re.findall(r'\bgf_DisplayRoles\s*\([^;{}]*\)\s*;', mask(source)) == [
        'gf_DisplayRoles ();', 'gf_DisplayRoles();'
    ], 'expected one declaration and one runtime startup call'
    # Card preview paths must not initialize shields; inspect actual card bodies.
    for name in ('gf_RTRoleCard', 'gf_RTTownRoleText', 'gf_RTMafiaRoleText',
                 'gf_RTNeutralRoleText', 'gf_RTTriadRoleText'):
        assert 'gv_immuneChance' not in mask(function(source, name)), ('card preview grant', name)

    code = fragment + '\n' + night
    calls = set(re.findall(r'\b(\w+)\s*\(', mask(code)))
    allowed = {'for', 'if', 'PlayerGroupHasPlayer', 'gf_RTRoleCard',
               'gf_SKN_3_egun', 'gf_RAEgunActions'}
    assert not calls - allowed, ('unknown dependency', calls - allowed)
    required = set(re.findall(r'\bgv_\w+', mask(code)))
    assert required == {'gv_alivePlayers', 'gv_roles', 'gv_immuneChance'}, required
    globals_text = []
    for name in sorted(required):
        found = re.findall(r'^(int|playergroup)((?:\[\d+\])*)\s+' + name + r'\s*;', source, re.M)
        assert len(found) == 1, ('missing/changed declaration', name)
        kind, dims = found[0]
        globals_text.append(f'{kind} {name}{dims};')

    return r'''
#include <cassert>
#include <iostream>
using playergroup = unsigned;
''' + '\n'.join(globals_text) + r'''
int cards[16], raCalls[16], checks=0, gv_dayNumber=0;
void check(bool b) { ++checks; assert(b); }
bool PlayerGroupHasPlayer(playergroup group,int p) {
    check(p>=1 && p<=15); return (group & (1u<<p))!=0;
}
void gf_RTRoleCard(int p) { check(p>=1 && p<=15); ++cards[p]; }
void gf_RAEgunActions(int p) { check(p>=1 && p<=15); ++raCalls[p]; }
void actualStartupLoop() {
    int lv_a;
''' + '\n'.join(declarations) + '\n' + fragment + '\n}\n' + night + r'''
int main() {
    int cases=0;
    for(int actor: {1,8,15}) for(int pool=0;pool<=5;++pool)
    for(int role=0;role<=35;++role) for(bool living: {false,true}) {
        gv_alivePlayers=0xfffe;
        if(!living) gv_alivePlayers &= ~(1u<<actor);
        for(int p=0;p<=15;++p) {
            gv_roles[p][0]=1; gv_roles[p][1]=1;
            gv_immuneChance[p]=70+p; cards[p]=raCalls[p]=0;
        }
        gv_roles[actor][0]=role; gv_roles[actor][1]=pool;
        actualStartupLoop();
        for(int p=0;p<=15;++p) {
            bool grant=p==actor && living && pool==3 &&
                       (role==16 || role==23 || role==28);
            check(gv_immuneChance[p]==(grant ? 1 : 70+p));
            bool card=p>0 && (p!=actor || (living &&
                      (pool==1 || pool==2 || pool==3 || pool==5)));
            check(cards[p]==int(card));
        }
        if(living && pool==3 && role==28) {
            gv_immuneChance[actor]=0; // emulate the one shield being consumed
            for(int day: {1,2,3}) {
                gv_dayNumber=day;
                for(int repeat=0;repeat<30;++repeat) gf_SKN_3_egun(actor);
                check(gv_immuneChance[actor]==0);
            }
            check(raCalls[actor]==90);
            for(int p=0;p<=15;++p) if(p!=actor) {
                check(gv_immuneChance[p]==70+p); check(raCalls[p]==0);
            }
        }
        ++cases;
    }
    std::cout << "PASS " << cases << " startup cases; " << checks
              << " checks; consumed shields stay zero across days 1/2/3\n";
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', help='One compiler; default runs available GCC and Clang')
    args = parser.parse_args()
    code = harness(args.script.read_text())
    compilers = [args.cxx] if args.cxx else [c for c in ('g++', 'clang++') if shutil.which(c)]
    assert compilers, 'no C++ compiler available'
    with tempfile.TemporaryDirectory(prefix='bh-egun-start-') as tmp:
        cpp = Path(tmp) / 'start.cpp'
        cpp.write_text(code)
        for index, cxx in enumerate(compilers):
            exe = Path(tmp) / f'start-{index}'
            warnings = ['-Wno-parentheses-equality'] if 'clang' in cxx else []
            command = [cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                       *warnings, '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                       str(cpp), '-o', str(exe)]
            print('Compile:', cxx, flush=True)
            subprocess.run(command, check=True)
            subprocess.run([str(exe)], check=True, env={**os.environ,
                           'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})


if __name__ == '__main__':
    main()
