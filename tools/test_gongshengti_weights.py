#!/usr/bin/env python3
"""Exercise actual shared-board weight application with string-native doubles.

C++17 UBSan/bounds test, not an SC2 compiler or live preset-UI test.
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile

from test_egun import function, mask

SCRIPT = Path(__file__).resolve().parents[1] / 'work/blackhand/CustomLogic.galaxy'
NAMES = ('gf_VOptions', 'gf_BHApplyOneBoardWeight', 'gf_BHApplyBoardWeights')
PREFIX = r'''
#include <cassert>
#include <iostream>
#include <sstream>
#include <string>
using string = std::string;
using fixed = double;
const string null = "";
string StringWord(string source, int index) {
    assert(index >= 1);
    std::istringstream input(source);
    string word;
    for (int i = 1; i <= index; ++i) if (!(input >> word)) return "";
    return word;
}
fixed StringToFixed(string word) {
    assert(!word.empty());
    return std::stod(word);
}
'''
CASES = r'''
int main() {
    for (int pool = 0; pool < 9; ++pool) for (int role = 0; role < 41; ++role) {
        gv_roleWeights[pool][role] = -7;
        for (int player = 0; player < 16; ++player) gv_bankSaveWeights[player][pool][role] = -9;
    }

    gf_VOptions();
    assert(StringToFixed(StringWord(gv_neutralWeights, 29)) == 0.5);
    assert(!StringWord(gv_neutralWeights, 38).empty() && StringWord(gv_neutralWeights, 39).empty());
    assert(gv_roleWeights[3][29] == -7); // VOptions defines strings, not active weights.
    for (fixed prior : {0.0, 0.5, 1.0}) {
        // Simulate a preset load replacing the default; the real shared apply restores it.
        gv_roleWeights[3][29] = gv_bankSaveWeights[0][3][29] = prior;
        gf_BHApplyBoardWeights();
        assert(gv_roleWeights[3][29] == 0.5 && gv_bankSaveWeights[0][3][29] == 0.5);
        for (int pool : {1, 2, 3, 5}) {
            const string weights = pool == 1 ? gv_townWeights : pool == 2 ? gv_mafiaWeights
                                   : pool == 3 ? gv_neutralWeights : gv_triadWeights;
            const int limit = pool == 3 ? 38 : 32;
            for (int role = 1; role <= limit; ++role) {
                const string word = StringWord(weights, role);
                const fixed expected = word.empty() ? 0 : StringToFixed(word);
                assert(gv_roleWeights[pool][role] == expected);
                assert(gv_bankSaveWeights[0][pool][role] == expected);
            }

            for (int role = limit + 1; role < 41; ++role) {
                // Existing town33 explicit reset is not permission to widen every pool.
                const fixed expected = pool == 1 && role == 33 ? 0 : -7;
                assert(gv_roleWeights[pool][role] == expected);
                assert(gv_bankSaveWeights[0][pool][role] == (expected == 0 ? 0 : -9));
            }
        }

        assert(gv_roleWeights[3][27] == 0 && gv_roleWeights[3][28] == 0);
        assert(gv_roleWeights[3][30] == 0 && gv_roleWeights[3][31] == 1 && gv_roleWeights[3][32] == 0);
        for (int role = 33; role <= 38; ++role) assert(gv_roleWeights[3][role] == 0);
        assert(gv_roleWeights[3][25] == 0 && gv_roleWeights[3][38] == 0);
        assert(gv_roleWeights[3][0] == -7 && gv_roleWeights[3][39] == -7);
        assert(gv_roleWeights[4][29] == -7); // unrelated random-kind pool untouched
        for (int player = 1; player < 16; ++player) for (int pool = 0; pool < 9; ++pool)
            for (int role = 0; role < 41; ++role) assert(gv_bankSaveWeights[player][pool][role] == -9);
    }

    gv_roleWeights[3][29] = gv_bankSaveWeights[0][3][29] = 0;
    gf_BHApplyOneBoardWeight(3, gv_neutralWeights);
    assert(gv_roleWeights[3][29] == 0.5 && gv_bankSaveWeights[0][3][29] == 0.5);
    std::cout << "PASS shared-board GS 0.5, 38 neutral entries, other-pool bounds and personal-bank isolation\n";
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    source = parser.parse_args().script.read_text()
    for weight in ('gv_roleWeights[3][29]', 'gv_bankSaveWeights[0][3][29]'):
        assert re.findall(re.escape(weight) + r'\s*=\s*([^;]+);', mask(source)) == ['0.5']

    bodies = [function(source, name) for name in NAMES]
    required = set(re.findall(r'\b(?:gv_|c_bh)\w+', mask('\n'.join(bodies))))
    declarations = {}
    for match in re.finditer(r'^(const\s+)?(\w+)((?:\[\d+\])*)\s+((?:gv_|c_bh)\w+)\s*(?:=([^;]*))?;', source, re.M):
        const, kind, dims, name, initial = match.groups()
        declarations[name] = f'{const or ""}{kind} {name}{dims}' + (f' = {initial}' if const else '') + ';'

    assert not required - declarations.keys(), required - declarations.keys()
    for name, body in zip(NAMES, bodies):
        first = source.count('\n', 0, source.index(body)) + 1
        print(f'{name}: lines {first}..{first + body.count(chr(10))}', flush=True)

    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'C++17 compiler required'
    with tempfile.TemporaryDirectory(prefix='gs-board-weights-') as tmp:
        cpp, binary = Path(tmp) / 'test.cpp', Path(tmp) / 'test'
        cpp.write_text(PREFIX + '\n'.join(declarations[name] for name in sorted(required))
                       + '\n\n' + '\n\n'.join(bodies) + CASES)
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
