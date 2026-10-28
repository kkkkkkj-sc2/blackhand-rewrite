#!/usr/bin/env python3
"""Execute shipping CJ/JS weighted random paths with C++17 UBSan/bounds.

Complete Matrix/RoleFitsKind/ListHas/DefaultRoleOptions/shared-board functions
are extracted unchanged. GenerateChances/OSRandomize contribute their complete
cumulative loop and actual random-range-to-Matrix call block, NOT their complete
seat retry/simulation functions. Initialization and chaos preset contribute only
strictly verified top-level weight assignments (plus shared-board application).
Engine string/RNG APIs and role-field writes are explicit doubles. fixed=double,
not Galaxy 19.12 emulation; this is not an SC2 compiler/UI/live-client test.
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile

from test_egun import SCRIPT, function, mask, translate
from test_gongshengti_weights import PREFIX

NAMES = ('gf_BHListHas', 'gf_BHRoleFitsKind', 'gf_OSRandomizeMatrix',
         'gf_DefaultRoleOptions', 'gf_VOptions', 'gf_BHApplyOneBoardWeight',
         'gf_BHApplyBoardWeights')


def balanced_end(live, opening):
    assert live[opening] == '{'
    depth, end = 1, opening + 1
    while depth:
        assert end < len(live), 'unbalanced extracted block'
        depth += (live[end] == '{') - (live[end] == '}')
        end += 1

    return end


def report(source, name, body):
    first = source.count('\n', 0, source.index(body)) + 1
    print(f'{name}: lines {first}..{first + body.count(chr(10))}', flush=True)


def weight_assignments(source, name):
    """Only top-level literal CJ/JS writes; reject conditional/hidden overrides."""
    body = function(source, name)
    live = mask(body)
    pattern = r'gv_(?:roleWeights\[3\]|bankSaveWeights\[0\]\[3\])\[(?:25|38)\]\s*=\s*[^;]+;'
    rows = list(re.finditer(pattern, live))
    assert len(rows) == 4, (name, 'expected active + bank defaults for CJ and JS', len(rows))
    for row in rows:
        prefix = live[:row.start()]
        assert prefix.count('{') - prefix.count('}') == 1, (name, 'conditional assignment')
        assert re.fullmatch(r'[^=]+\s*=\s*(?:0\.25|1\.0);', row[0]), row[0]

    report(source, name + ' [four weight assignments only]', body)
    return '\n'.join(body[row.start():row.end()] for row in rows)


def cumulative(source, name):
    body = function(source, name)
    live = mask(body)
    start = live.index('lv_aaa = 1;')
    loop = re.search(r'\bfor\s*\(', live[start:])
    assert loop
    opening = live.index('{', start + loop.start())
    end = balanced_end(live, opening)
    block = body[start:end]
    clean = mask(block)
    assert set(re.findall(r'\bgv_\w+', clean)) == {
        'gv_townMax', 'gv_mafiaTriadMax', 'gv_roleOptions',
        'gv_finalWeights', 'gv_roleWeights'}, name
    assert 'c_bhNeutralDrawMax' in clean
    assert re.findall(r'lv_a\s*=\s*(\d+);', clean) == ['1', '2', '5', '3'], name
    assert not re.search(r'\b(?:return|break|continue|gf_\w+)\b', clean), name
    # Every cumulative write stays inside the extracted outer loop.
    assert len(re.findall(r'gv_finalWeights(?:\[[^\]\n]+\]){2}\s*=(?!=)', live)) == len(
        re.findall(r'gv_finalWeights(?:\[[^\]\n]+\]){2}\s*=(?!=)', clean)), name
    variables = set(re.findall(r'\b(?:auto\w+|lv_\w+)\b', clean))
    declarations = []
    for line in body.splitlines():
        match = re.fullmatch(r'\s*(?:const )?(?:int|fixed|bool) (\w+)(?:\s*=\s*[^;]+)?;\s*(?://.*)?', line)
        if match and match[1] in variables:
            declarations.append(line)

    assert len(declarations) == len(variables), (name, variables, declarations)
    report(source, name + ' [complete cumulative loop]', block)
    return f'void cumulative_{name}() {{\n' + '\n'.join(declarations) + '\n' + block + '\n}'


def draw_callsite(source, name):
    body = function(source, name)
    start = body.index('if ((gv_rolesArray[lv_x] == 1)) {')
    call = 'gf_OSRandomizeMatrix(lv_a, lv_x, lv_y);'
    end = body.index(call, start) + len(call)
    block = body[start:end]
    clean = mask(block)
    assert clean.count('RandomFixed(') == 5, name
    assert clean.count('gf_OSRandomizeMatrix(') == 1, name
    assert clean.count('{') == clean.count('}') == 5, name
    assert 'RandomFixed(0.0, gv_finalWeights[3][c_bhNeutralDrawMax])' in clean
    assert 'RandomFixed(gv_finalWeights[5][gv_mafiaTriadMax], gv_finalWeights[3][c_bhNeutralDrawMax])' in clean
    assert re.search(r'gv_rolesArray\[lv_x\] == 20[^;]+RandomFixed\(gv_finalWeights\[5\]\[gv_mafiaTriadMax\], gv_finalWeights\[3\]\[c_bhNeutralDrawMax\]\)', clean), name
    report(source, name + ' [actual range selection + Matrix call]', block)
    return f'void draw_{name}() {{ int lv_a=1, lv_x=1; fixed lv_y=0;\n' + block + '\n}'


CASES = r'''
int checks = 0;
#define CHECK(x) do { ++checks; if (!(x)) { std::cerr << "FAIL " << __LINE__ << ": " << #x << '\n'; std::abort(); } } while (0)
template<class T> void clearValue(T& value) { value = T{}; }
template<class T, size_t N> void clearValue(T (&value)[N]) { for (auto& item : value) clearValue(item); }
void reset() {
    clearValue(gv_roleOptions); clearValue(gv_roleWeights); clearValue(gv_finalWeights);
    clearValue(gv_roles); clearValue(gv_rolesArray); clearValue(gv_categoriesArray);
    gv_townMax = productionTownMax; gv_mafiaTriadMax = productionGangMax;
}
void checkDefaults() {
    reset();
    initWeightAssignments();
    for (int role : {25, 38}) {
        CHECK(gv_roleWeights[3][role] == 0.25);
        CHECK(gv_bankSaveWeights[0][3][role] == 0.25);
        gv_roleWeights[3][role] = gv_bankSaveWeights[0][3][role] = 19;
    }

    gf_VOptions();
    for (int turn = 0; turn < 3; ++turn) {
        chaosWeightTail();
        for (int role : {25, 38}) {
            CHECK(gv_roleWeights[3][role] == 1);
            CHECK(gv_bankSaveWeights[0][3][role] == 1);
            gv_roleWeights[3][role] = gv_bankSaveWeights[0][3][role] = 91;
        }

        gf_BHApplyBoardWeights();
        for (int role : {25, 38}) {
            CHECK(gv_roleWeights[3][role] == 0);
            CHECK(gv_bankSaveWeights[0][3][role] == 0);
        }
    }

    std::cout << "PASS draw intervals, closed 32..37, init/chaos/shared-board weights; checking dirty default reset\n" << std::flush;
    for (int role : {25, 38}) gv_roleWeights[3][role] = gv_bankSaveWeights[0][3][role] = 19;
    gf_DefaultRoleOptions();
    for (int role : {25, 38}) {
        CHECK(gv_roleWeights[3][role] == 0.25);
        CHECK(gv_bankSaveWeights[0][3][role] == 0.25);
    }
}
void checkKinds() {
    reset();
    for (int kind = 0; kind <= 23; ++kind) for (int role : {25, 38}) {
        CHECK(gf_BHRoleFitsKind(kind, 3, role) == (kind == 20));
    }
}
void checkDraws(void (*cumulative)(), void (*draw)()) {
    for (int selectedRole : {25, 38}) for (fixed weight : {0.0, 0.25, 1.0, 3.0}) {
        reset();
        gv_roleWeights[3][selectedRole] = weight;
        // Poison every newly traversed but deliberately closed role.
        for (int role = 32; role <= 37; ++role) gv_roleWeights[3][role] = 100;
        cumulative();
        for (int role = 32; role <= 37; ++role) {
            CHECK(gv_finalWeights[3][role] == gv_finalWeights[3][31]);
        }

        CHECK(gv_finalWeights[3][38] == weight);
        for (int kind = 1; kind <= 23; ++kind) {
            gv_rolesArray[1] = kind;
            for (fixed fraction : {0.0, 0.125, 0.5, 0.875, 0.999}) {
                rngFraction = fraction;
                clearValue(gv_roles);
                draw();
                CHECK(gv_roles[1][0] == (weight > 0 && kind == 20 ? selectedRole : 0));
                CHECK(gv_roles[1][1] == (weight > 0 && kind == 20 ? 3 : 0));
            }
        }
    }

    reset();
    gv_roleWeights[1][2] = 2; // Nonzero cross-pool cumulative offset.
    gv_roleWeights[3][25] = 1; gv_roleWeights[3][38] = 1;
    cumulative();
    CHECK(gv_finalWeights[3][24] == 2 && gv_finalWeights[3][25] == 3);
    CHECK(gv_finalWeights[3][37] == 3 && gv_finalWeights[3][38] == 4);
    for (int kind = 1; kind <= 23; ++kind) {
        gv_rolesArray[1] = kind;
        for (fixed y : {2.0, 2.5, 2.999, 3.0, 3.5, 3.999, 4.0}) {
            clearValue(gv_roles);
            gf_OSRandomizeMatrix(1, 1, y);
            CHECK(gv_roles[1][0] == (kind != 20 || y == 4 ? 0 : y < 3 ? 25 : 38));
        }
    }

    // Deliberately stale cumulative cells cannot survive either production loop.
    for (int role = 32; role <= 38; ++role) gv_finalWeights[3][role] = -101;
    gv_roleWeights[3][38] = 0;
    cumulative();
    for (int role = 32; role <= 38; ++role) CHECK(gv_finalWeights[3][role] == 3);
}
int main() {
    CHECK(c_bhNeutralDrawMax == 38);
    checkKinds();
    checkDraws(cumulative_gf_OSGenerateChances, draw_gf_OSGenerateChances);
    checkDraws(cumulative_gf_OSRandomize, draw_gf_OSRandomize);
    checkDefaults();
    std::cout << "PASS CJ/JS random paths: " << checks << " checks; UBSan/bounds; cumulative/callsite slices only for outer draw functions\n";
}
'''


def harness(source):
    bodies = [function(source, name) for name in NAMES]
    for name, body in zip(NAMES, bodies):
        report(source, name, body)

    init = weight_assignments(source, 'gf_InitializeVariables')
    chaos = weight_assignments(source, 'gf_VHLZSOptions')
    chaos_body = function(source, 'gf_VHLZSOptions')
    assert chaos_body.index('gf_VLoadSaveSlot(0, 10);') < chaos_body.index('gf_BHApplyBoardWeights();')
    for row in chaos.splitlines():
        assert chaos_body.index(row) > chaos_body.index('gf_BHApplyBoardWeights();')

    bodies += [f'void initWeightAssignments() {{\n{init}\n}}',
               f'void chaosWeightTail() {{ gf_BHApplyBoardWeights();\n{chaos}\n}}']
    for name in ('gf_OSGenerateChances', 'gf_OSRandomize'):
        bodies += [cumulative(source, name), draw_callsite(source, name)]

    raw = '\n\n'.join(bodies)
    required = set(re.findall(r'\b(?:gv_|c_bh)\w+', mask(raw))) | {'gv_roles'}
    declarations = {}
    for match in re.finditer(r'^(const\s+)?(\w+)((?:\[\d+\])*)\s+((?:gv_|c_bh)\w+)\s*(?:=([^;]*))?;', source, re.M):
        const, kind, dims, name, initial = match.groups()
        declarations[name] = f'{const or ""}{kind} {name}{dims}' + (f' = {initial}' if const else '') + ';'

    assert not required - declarations.keys(), required - declarations.keys()
    constants = []
    for variable, alias in (('gv_townMax', 'productionTownMax'), ('gv_mafiaTriadMax', 'productionGangMax')):
        values = re.findall(r'\b' + variable + r'\s*=\s*(\d+);', mask(function(source, 'SH_InitGlobals')))
        assert len(values) == 1, (variable, values)
        constants.append(f'const int {alias} = {values[0]};')

    # Exhaustive explicit dependencies: no automatic inert business stubs.
    calls = set(re.findall(r'\b(\w+)\s*\(', mask(raw)))
    defined = set(re.findall(r'^(?:void|bool) (\w+)\s*\(', raw, re.M))
    assert not calls - defined - {'if', 'for', 'while', 'return', 'StringWord', 'StringToFixed', 'RandomFixed', 'gf_GKSetRoleField'}, calls - defined
    return PREFIX + '\n'.join(declarations[name] for name in sorted(required)) + '\n' + '\n'.join(constants) + r'''
fixed rngFraction = 0;
fixed RandomFixed(fixed lower, fixed upper) {
    assert(lower <= upper);
    return lower + (upper - lower) * rngFraction;
}
void gf_GKSetRoleField(int player, int field, int value) {
    // Assignment double only: production conversion/death side effects are outside initial dealing.
    assert(player >= 0 && player <= 15 && field >= 0 && field <= 1);
    gv_roles[player][field] = value;
}
''' + '\n'.join(body.split('{', 1)[0] + ';' for body in bodies) + '\n' + translate(raw) + CASES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    source = parser.parse_args().script.read_text()
    code = harness(source)
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'C++17 compiler required'
    with tempfile.TemporaryDirectory(prefix='cj-random-') as tmp:
        cpp, binary = Path(tmp) / 'test.cpp', Path(tmp) / 'test'
        cpp.write_text(code)
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
