#!/usr/bin/env python3
"""Execute Baron/Taido immunity grants and real investigation feedback.

Extends test_baron_leaders in memory. Uses whole production BR, sheriff,
investigator/federal Prep+feedback, crime trigger, DQ and FZ rendering functions.
Jailed setup executes the whole actual jail branch under every enclosing actual
if guard, extracted with balanced braces. The night reset's four actual immunity
assignments execute separately; their owning loop and reset/setup/FZ ordering
are checked, not the full scheduler. Unrelated jailed-Godfather and non-Baron FZ
branches are fail-fast boundaries, never permissive logic doubles. Existing
investigation body hashes remain enforced by test_faction_investigation.

Deletion mutants live only in generated C++ and must compile, then fail business
assertions (not sanitizers). No production edits, SC2 compilation, rendering,
multiplayer or complete night scheduling are claimed.
"""
from __future__ import annotations

import argparse
import re
import resource
import subprocess
import tempfile
from pathlib import Path

import test_baron_leaders as baron
import test_faction_investigation as investigation
from test_egun import SCRIPT, function, mask, translate

NAMES = (
    'gf_DQHidden', 'gf_DQSeenPool', 'gf_DQSeenRole', 'gf_DQSeenName',
    'gf_SKP_1_tanyuan', 'gf_SKP_1_lianbangtanyuan', 'gf_BHVisitAction',
    'gf_SKF_1_tanyuan', 'gf_SKF_1_lianbangtanyuan',
    'gt_E78AAFE7BDAAE8AEB0E5BD95_Func', 'gf_BHCrime',
    'gf_RAFengziActions', 'gf_FZRefreshActions',
)


def jailed_branch(source: str, owner: str, pool: int) -> str:
    """Keep the complete jail body AND each actual enclosing if predicate."""
    body = function(source, owner)
    live = mask(body)
    marker = 'if ((gv_jailed[lv_a] != 0)) {'
    assert live.count(marker) == 1, ('ambiguous jail branch', owner)
    start = live.index(marker)
    brace = live.index('{', start)
    end = baron.core.block_end(body, brace)
    ancestors = []
    for match in re.finditer(r'\bif\s*\([^\n{]+\)\s*\{', live[:start]):
        opening = live.index('{', match.start())
        if baron.core.block_end(body, opening) > end:
            ancestors.append(body[match.start():opening + 1])

    assert len(ancestors) == 2, ('jail guard ancestry changed', owner, ancestors)
    assert 'PlayerGroupHasPlayer(gv_alivePlayers, lv_a)' in ancestors[0]
    assert 'gv_bhFeignRole[lv_a]' in ancestors[0]
    assert ancestors[1] == f'if ((gv_roles[lv_a][1] == {pool})) {{'
    assert re.match(r'\s*else\s*\{', live[end:]), ('jail else missing', owner)
    else_brace = live.index('{', end)
    else_end = baron.core.block_end(body, else_brace)
    actual_else = live[else_brace:else_end]
    assert re.search(r'if \(\(gv_roles\[lv_a\]\[0\] == 22\)\) \{\s*gf_BRSetup\(lv_a\);\s*}', actual_else)
    assert 'gf_BRSetup(' not in live[brace:end], ('jail must not grant by drawing/setup', owner)
    line = source[:source.index(body)].count('\n') + 1
    print(f'Extracted {owner}:{line}-{line + body.count(chr(10))}: complete jail branch, 2 actual ancestor guards; checked real nonjail role22 setup', flush=True)
    return f'void jail{pool}(int lv_a) {{\n' + '\n'.join(ancestors) + '\n' + body[start:end] + '\n}\n}\n}'


def reset_body(source: str) -> str:
    night = function(source, 'auto_gf_NightTransition_TriggerFunc')
    live = mask(night)
    match = re.search(r'gv_immune\[lv_a\]\[0\] = false;\s*gv_immune\[lv_a\]\[1\] = false;\s*gv_immune\[lv_a\]\[2\] = false;\s*gv_immune\[lv_a\]\[3\] = false;', live)
    assert match, 'actual nightly immunity reset changed'
    # The source reset is owned by the player loop, not a conditional role path.
    loops = []
    for loop in re.finditer(r'\bfor\s*\([^\n{]+\)\s*\{', live[:match.start()]):
        brace = live.index('{', loop.start())
        if baron.core.block_end(night, brace) > match.end():
            loops.append(loop)

    assert len(loops) == 1 and 'lv_a' in loops[0][0], 'immunity reset player-loop ownership changed'
    assert match.end() < live.index('gf_RSMafiaSetup2();') < live.index('gf_RSTriadSetup();') < live.index('gf_FZRefreshActions();')
    assert 'gf_BRSetup' not in mask(function(source, 'gf_RAFengziActions'))
    print('PASS host order: actual player-loop reset -> Mafia setup -> Triad setup -> FZ refresh; FZ renderer never calls BRSetup', flush=True)
    return 'void actualNightImmunityReset(int lv_a) {\n' + night[match.start():match.end()] + '\n}'


def harness(source: str) -> str:
    investigation.check_wiring(source)
    base = baron.harness(source)
    base = base.replace(function(base, 'main'), '')
    base = base.replace(function(base, 'gf_DQSeenName'), '')
    bodies = [function(source, name) for name in NAMES]
    bodies += [jailed_branch(source, 'gf_RSMafiaSetup2', 2), jailed_branch(source, 'gf_RSTriadSetup', 5), reset_body(source)]
    raw = '\n\n'.join(bodies)
    used = set(re.findall(r'\bgv_\w+', mask(raw)))
    needed = used - set(re.findall(r'\bgv_\w+', base))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not needed - declarations.keys(), ('missing actual globals', needed - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(needed))
    resets = '\n'.join(f'    clearValue({name});' for name in sorted(needed))
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    base = base.replace('struct Message {', globals_text + '\n' + headers + '\nstruct Message {', 1)
    code = translate(raw)
    code = re.sub(r'\bfixed((?:\[\d+\])+)\s+(\w+)', r'fixed \2\1', code)
    code = re.sub(r'\bnull\b', 'text{}', code)
    code = re.sub(r'^(\s+(?:int|bool|fixed|text)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', code, flags=re.M)
    supported = set(re.findall(r'\b(?:gf_|gt_)\w+\s*\(', mask(base)))
    supported = {re.sub(r'\s*\($', '', name) for name in supported}
    supported |= set(NAMES) | {'jail2', 'jail5', 'actualNightImmunityReset', 'gf_SKM_2_jiaofu_2', 'gf_SKT_5_longtou_2', 'gf_YSButtons', 'gf_YSDraw', 'gf_RABihuzheActions', 'gf_RADragonHeadActions', 'gf_RAGodfatherActions'}
    calls = set(re.findall(r'\b((?:gf_|gt_)\w+)\s*\(', mask(code)))
    assert not calls - supported, ('unexpected logic dependency', calls - supported)
    boundary = r'''
constexpr int gt_E78AAFE7BDAAE8AEB0E5BD95=991;
int crimeTriggerCalls=0;
void TriggerExecute(int id,bool test,bool wait) {
    CHECK(id==gt_E78AAFE7BDAAE8AEB0E5BD95 && !test && !wait);
    ++crimeTriggerCalls;
    CHECK(gt_E78AAFE7BDAAE8AEB0E5BD95_Func(false,true));
}
// Unrelated branches are forbidden, not implemented as fake role algorithms.
void gf_SKM_2_jiaofu_2(int) { CHECK(false && "unexpected jailed Godfather branch"); }
void gf_SKT_5_longtou_2(int) { CHECK(false && "unexpected jailed Dragonhead branch"); }
void gf_YSButtons(int) { CHECK(false && "unexpected FZ Beast branch"); }
void gf_YSDraw(int) { CHECK(false && "unexpected FZ Beast draw branch"); }
void gf_RABihuzheActions(int) { CHECK(false && "unexpected FZ refuge branch"); }
void gf_RADragonHeadActions(int) { CHECK(false && "unexpected FZ Dragonhead branch"); }
void gf_RAGodfatherActions(int) { CHECK(false && "unexpected FZ Godfather branch"); }
'''
    tests = r'''
void immunityReset(int pool) {
    brReset("Baron immunity pool="+std::to_string(pool),pool);
''' + resets + r'''
    clearValue(gv_roleInvestigatorArray); clearValue(gv_immune);
    crimeTriggerCalls=0;
    for(int category=0;category<9;++category) for(int role=0;role<41;++role) {
        gv_roleInvestigatorArray[category][role][0]="CLUE:"+std::to_string(category)+":"+std::to_string(role);
    }
    gv_roleInvestigatorArray[1][1][1]="CITIZEN-SECOND";
    clearEffects();
}
void expectMessages(int actor,std::vector<text> values) {
    CHECK(messages.size()==values.size());
    for(size_t i=0;i<values.size();++i) {
        CHECK(messages[i].target==actor && messages[i].sender==actor);
        CHECK(messages[i].value==values[i]);
    }
}
text key(string suffix) { return StringExternal("Param/Value/"+suffix); }
void sheriff(int actor,int target,bool guilty) {
    role(actor,1,2); gv_visitation[actor]=target; gv_roleOptions[1][2][0]=true;
    clearEffects();
    gf_SKF_1_jingzhang(actor);
    // Crime notices precede the immunity gate and must still be emitted.
    expectMessages(actor,{key(guilty?"33FE9712":"D903D005"),key("93CC8036")});
    CHECK(gv_seqAfterWait[2]);
}
void testNightlyAndSheriff() {
    for(int pool:{2,5}) {
        immunityReset(pool);
        for(int night=0;night<4;++night) {
            context="nightly regrant + actual sheriff pool="+std::to_string(pool)+" night="+std::to_string(night);
            actualNightImmunityReset(1);
            CHECK(!gv_immune[1][0] && !gv_immune[1][2]);
            gf_BRSetup(1);
            gv_e78AAFE7BDAAE4BA8BE5AE9E[1][10]=(night%2)!=0;
            // Real feedback assertion comes first so deleted grants cannot pass
            // by merely preserving a field or by breaking compilation.
            sheriff(2,1,(night%2)!=0);
            CHECK(gv_immune[1][0] && gv_immune[1][2]);
            CHECK(!gv_immune[1][1] && !gv_immune[1][3]);
            CHECK(gv_roles[1][0]==22 && gv_roles[1][1]==pool);
        }
    }
}
void testJail() {
    for(int pool:{2,5}) {
        immunityReset(pool);
        context="actual jailed grant + sheriff pool="+std::to_string(pool);
        gv_jailed[1]=15;
        for(int night=0;night<3;++night) {
            actualNightImmunityReset(1);
            CHECK(!gv_immune[1][0] && !gv_immune[1][2]);
            if(pool==2) jail2(1); else jail5(1);
            sheriff(2,1,false);
            CHECK(gv_immune[1][0] && gv_immune[1][2]);
            CHECK(gv_e78AAFE7BDAAE4BA8BE5AE9E[15][8]);
            CHECK(gv_variableOptions[1][0]==0); // Jail never ran BRSetup/draw.
        }
        actualNightImmunityReset(1); gv_jailed[1]=0;
        if(pool==2) jail2(1); else jail5(1);
        CHECK(!gv_immune[1][0] && !gv_immune[1][2]);
        gv_jailed[1]=15; role(1,1,22); gv_bhFaction[1]=pool;
        if(pool==2) jail2(1); else jail5(1);
        CHECK(!gv_immune[1][0] && !gv_immune[1][2]); // Not a native leader.
        role(1,pool,22); gv_bhFaction[1]=0; gv_alivePlayers&=~(1u<<1);
        if(pool==2) jail2(1); else jail5(1);
        CHECK(!gv_immune[1][0] && !gv_immune[1][2]);
    }
}
void testInvestigatorAndFederal() {
    for(int pool:{2,5}) for(bool truth:{false,true}) for(bool plague:{false,true}) {
        immunityReset(pool); gf_BRSetup(1);
        context="actual investigator immune/plague pool="+std::to_string(pool);
        role(2,1,4); gv_action[2][0]=1; gf_SKP_1_tanyuan(2);
        CHECK(gv_visitation[2]==1);
        gv_roleOptions[1][4][0]=truth; gv_seqAfterPlagueInteract[1]=plague;
        clearEffects(); gf_SKF_1_tanyuan(2);
        if(truth) expectMessages(2,{key(plague?"373E8EF6":"DCF20712")+gv_roleNameArray[plague?pool:1][plague?22:1]+key(plague?"385D6DB5":"DC4B7DB1")});
        else if(plague) expectMessages(2,{key("A22D1588")+gv_roleInvestigatorArray[pool][22][0]+key("745ADE02")});
        else expectMessages(2,{key("63C1FF88")+gv_roleInvestigatorArray[1][1][0]+key("CE19A5B4"),key("11D2EEE9")+gv_roleInvestigatorArray[1][1][1]+key("5AC819B0")});
        CHECK(gv_seqAfterWait[2] && gv_immune[1][0] && gv_immune[1][2]);
    }
    for(int pool:{2,5}) for(bool truth:{false,true}) for(bool pierce:{false,true}) for(bool plague:{false,true}) {
        immunityReset(pool); gf_BRSetup(1);
        context="actual federal first/revisit/options/plague pool="+std::to_string(pool);
        role(2,1,27); gv_action[2][0]=1; gf_SKP_1_lianbangtanyuan(2);
        CHECK(gv_visitation[2]==1);
        gv_roleOptions[1][27][0]=truth; gv_roleOptions[1][27][1]=pierce;
        gv_seqAfterPlagueInteract[1]=plague; gf_BHCrime(1,0); gf_BHCrime(1,10);
        clearEffects(); gf_SKF_1_lianbangtanyuan(2);
        if(truth) expectMessages(2,{key("14230C7D")+gv_roleNameArray[pool][22]+key("3004D2CB")});
        else if(!pierce) expectMessages(2,{key("8CADCDD0")+key("A5CC6E1A")+gv_e78AAFE7BDAAE8AEB0E5BD95[0]+key("ACCC5A47")});
        else expectMessages(2,{key("E820B4D2")+key("C3858513")+key("99AEA75A")+key("ZCCRJ1")+key("D88D8066")+key("E795F349")});
        CHECK(crimeTriggerCalls==1 && gv_e69FA5E8BF87E4BA86[2][1]);
        clearEffects(); gf_SKF_1_lianbangtanyuan(2);
        if(truth) expectMessages(2,{key("14230C7D")+gv_roleNameArray[pool][22]+key("3004D2CB")});
        else if(plague) expectMessages(2,{key("E6681CEB")+gv_roleNameArray[1][3]+key("310DC0A4")});
        else if(!pierce) expectMessages(2,{key("5630260B")+gv_roleNameArray[1][1]+key("270AC812")});
        else expectMessages(2,{key("D88882E8")+gv_roleNameArray[pool][22]+key("F84562C4")});
        CHECK(crimeTriggerCalls==2 && gv_immune[1][0] && gv_immune[1][2]);
    }
}
void testRecruitsAndFZ() {
    for(int pool:{2,5}) {
        immunityReset(pool); gf_BRSetup(1);
        context="actual recruitment does not inherit leader immunity pool="+std::to_string(pool);
        gf_BRClick(1,3,true); gf_BRClick(1,4,true);
        commitAtNightEntry();
        for(int p:{3,4}) CHECK(gf_BHFaction(p)==pool && gv_roles[p][1]==1 && gv_roles[p][0]==1 && !gv_immune[p][0] && !gv_immune[p][2]);
        CHECK(gv_brDone && gv_immune[1][0] && gv_immune[1][2]);
        for(bool talk:{false,true}) for(bool preexisting:{false,true}) {
            context="actual FZ Baron render preserves, never grants immunity pool="+std::to_string(pool);
            role(3,1,33); gv_fzPool[3]=pool; gv_fzRole[3]=22; gv_fzLeader[3]=1;
            gv_immune[3][0]=preexisting; gv_immune[3][2]=preexisting;
            gv_variableOptions[3][0]=7; gv_variableOptions[3][1]=8; gv_variableOptions[3][2]=9;
            gf_RAFengziActions(3,talk);
            CHECK(gv_roles[3][1]==1 && gv_roles[3][0]==33 && gv_roles[1][1]==pool && gv_roles[1][0]==22);
            CHECK(gv_immune[3][0]==preexisting && gv_immune[3][2]==preexisting);
            CHECK(gv_variableOptions[3][0]==7 && gv_variableOptions[3][1]==8 && gv_variableOptions[3][2]==9);
            gf_FZRefreshActions();
            CHECK(gv_immune[3][0]==preexisting && gv_immune[3][2]==preexisting);
        }
    }
}
int main(int argc,char** argv) {
    string selected=argc>1?argv[1]:"all";
    if(selected=="all" || selected=="setup") testNightlyAndSheriff();
    if(selected=="all" || selected=="jail") testJail();
    if(selected=="all" || selected=="investigation") testInvestigatorAndFederal();
    if(selected=="all" || selected=="isolation") testRecruitsAndFZ();
    std::cout << "PASS Baron/Taido immunity [" << selected << "]: " << fixtures << " fixtures, " << checks << " assertions; real setup/jail/reset/sheriff/investigator/federal/crime/recruit/FZ; UBSan/bounds" << std::endl;
}
'''
    return base + '\n' + boundary + '\n' + code + '\n' + tests


def without_grant(code: str, name: str, player: str) -> str:
    body = function(code, name)
    assignment = f'gv_immune[{player}][2] = true;'
    if name.startswith('jail'):
        live = mask(body)
        match = re.search(r'if \(\(gv_roles\[lv_a\]\[0\] == 22\)\)\s*\{', live)
        assert match, ('missing role22 jailed grant', name)
        end = baron.core.block_end(body, live.index('{', match.start()))
        branch = body[match.start():end]
        assert branch.count(assignment) == 1
        changed = body[:match.start()] + branch.replace(assignment, '') + body[end:]
    else:
        assert body.count(assignment) == 1
        changed = body.replace(assignment, '')

    assert code.count(body) == 1
    return code.replace(body, changed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--skip-negative', action='store_true', help='Diagnostic only; default also tests three deletion mutants')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    code = harness(args.script.read_text(encoding='utf-8'))
    variants = [('actual', code, 'all')]
    if not args.skip_negative:
        variants += [(name, without_grant(code, name, player), case) for name, player, case in (
            ('gf_BRSetup', 'lp_player', 'setup'), ('jail2', 'lv_a', 'jail'), ('jail5', 'lv_a', 'jail'),
        )]

    with tempfile.TemporaryDirectory(prefix='bh-baron-immunity-') as directory:
        for label, generated, case in variants:
            cpp, exe = Path(directory) / f'{label}.cpp', Path(directory) / label
            cpp.write_text(generated, encoding='utf-8')
            warnings = ['-Wno-parentheses-equality'] if 'clang' in args.cxx else []
            subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-parameter', '-Wno-unused-variable', *warnings,
                            '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
            if label == 'actual':
                subprocess.run([str(exe), case], check=True)
                continue

            result = subprocess.run([str(exe), case], text=True, capture_output=True)
            assert result.returncode != 0, ('deletion mutant survived', label)
            assert 'FAIL [' in result.stderr and 'messages[i].value==values[i]' in result.stderr, ('must fail real sheriff business feedback assertion', label, result.stderr)
            assert 'runtime error:' not in result.stderr and 'Sanitizer' not in result.stderr
            print(f'PASS deletion mutant {label}: compiled successfully, actual sheriff feedback rejected missing immunity: {result.stderr.strip()}', flush=True)


if __name__ == '__main__':
    main()
