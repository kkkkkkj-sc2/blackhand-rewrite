#!/usr/bin/env python3
"""Execute actual detective/deputy/agent/pioneer Galaxy feedback as C++.

Only array syntax and zero-initialized Galaxy locals are translated. Engine
text/color/groups/trigger execution are doubles; actual visitation, blocking,
crime trigger, disguise and faction name logic run unchanged. Dispatch executes
exact source guard lines, not the rest of SequenceAfter or its scheduling.
No SC2 compiler, engine, rendering or multiplayer validation is claimed.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from test_egun import SCRIPT, function, mask, translate

ROOT = Path(__file__).resolve().parent.parent
BEFORE = ROOT / 'tools/fixtures/detective-feedback-before.galaxy'
FEEDBACK = ('gf_SKF_1_zhentan', 'gf_SKF_1_fushou', 'gf_SKF_2_mitan', 'gf_SKF_5_xianfeng')
NAMES = (
    'gf_BHDetName', 'gf_BHDetectiveFeedback', *FEEDBACK,
    'gf_BHVisit', 'gf_BHVisit2', 'gf_BHVisitAction', 'gf_BHVisitNone',
    'gf_BHWentTo', 'gf_BHSetBlocker', 'gf_BHBlock',
    'gf_SKP_1_zhentan', 'gf_SKP_1_fushou', 'gf_SKP_2_mitan', 'gf_SKP_5_xianfeng',
    'gt_E78AAFE7BDAAE8AEB0E5BD95_Func',
    'gf_BHConverted', 'gf_BHFaction', 'gf_BHRoleName',
    'gf_DQHidden', 'gf_DQSeenPool', 'gf_DQSeenRole', 'gf_DQSeenName',
)


def check_wiring(source: str, before: str) -> str:
    for name in FEEDBACK[2:]:
        old, new = function(before, name), function(source, name)
        marker = '\nlv_c = false;'
        assert old[old.index(marker):] == new[new.index(marker):], ('watch/crime/cooldown tail changed', name)
        assert new.count('gf_BHDetectiveFeedback(') == 1
        assert 'gf_BHDetectiveFeedback(lv_a, gv_visitation[lv_a], false);' in new

    deputy_old, deputy_new = function(before, FEEDBACK[1]), function(source, FEEDBACK[1])
    old_condition = '((gv_visitation[gv_visitation[lv_a]] == 0) || (gv_visitation[gv_visitation[lv_a]] == gv_visitation[lv_a]) || (gv_immune[gv_visitation[lv_a]][2] == true))'
    new_condition = '((gv_immune[gv_visitation[lv_a]][2] == true) || (((gv_visitation[gv_visitation[lv_a]] == 0) || (gv_visitation[gv_visitation[lv_a]] == gv_visitation[lv_a])) && ((gv_visitation2[gv_visitation[lv_a]] == 0) || (gv_visitation2[gv_visitation[lv_a]] == gv_visitation[lv_a]))))'
    assert deputy_old.replace(old_condition, new_condition) == deputy_new
    assert 'gf_BHDetectiveFeedback(lv_a, gv_visitation[lv_a], gv_roleOptions[1][15][0]);' in function(source, FEEDBACK[0])
    for name in ('gf_BHDetName', 'gf_BHDetectiveFeedback'):
        assert function(source, name).split('{', 1)[0].strip() + ';' in source

    # The fixture carries exact production guards captured before the fix.
    old_guards = re.findall(r'^// GUARD (.*)$', before, re.M)
    actual_guards, dispatch = [], []
    lines = function(source, 'gf_SequenceAfter').splitlines()
    for i, line in enumerate(lines):
        for name in FEEDBACK:
            if line.strip() == name + '(lv_a);':
                guard = lines[i - 1].strip()
                assert guard.startswith('if (') and guard.endswith('{')
                actual_guards.append(guard)
                dispatch.append(guard + '\n    ' + line.strip() + '\n}')

    assert actual_guards == old_guards, 'feedback qualification/skill/cooldown/faction guard drift'
    assert len(dispatch) == 4
    print('PASS wiring: one detailed helper; exact gang tails; deputy coarse-only delta; all four actual dispatch guards unchanged', flush=True)
    return 'void dispatch(int lv_a) {\n' + '\n'.join(dispatch) + '\n}'


def harness(source: str, before: str) -> str:
    dispatch = check_wiring(source, before)
    bodies = [function(source, name) for name in NAMES]
    old_code = '\n\n'.join(function(before, name) for name in FEEDBACK)
    for name in FEEDBACK:
        old_code = old_code.replace(name, 'old_' + name)

    code = '\n\n'.join(bodies) + '\n' + old_code + '\n' + dispatch
    used = set(re.findall(r'\bgv_\w+', mask(code)))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not used - declarations.keys(), ('missing actual globals', used - declarations.keys())
    global_text = '\n'.join(declarations[name] for name in sorted(used))
    reset = '\n'.join(f'    clearValue({name});' for name in sorted(used))
    headers = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    code = translate(code)
    code = re.sub(r'\bfixed((?:\[\d+\])+)\s+(\w+)', r'fixed \2\1', code)
    code = re.sub(r'^(\s+(?:int|bool|fixed|text)\s+\w+(?:\[\d+\])*)\s*;', r'\1 = {};', code, flags=re.M)
    supported = set(NAMES) | {'old_' + n for n in FEEDBACK} | {
        'dispatch', 'if', 'while', 'for', 'return', 'Color', 'TextWithColor',
        'StringToText', 'IntToString', 'StringExternal', 'PlayerGroupHasPlayer',
        'gf_CBSystemMessage', 'SoundLink', 'TriggerExecute',
        'libNtve_gf_ConvertPlayerColorToColor',
    }
    calls = set(re.findall(r'\b(\w+)\s*\(', mask(code)))
    assert not calls - supported, ('unstubbed logic call', calls - supported)
    print(f'Extracted {len(bodies)} current complete functions, 4 old functions, {len(used)} actual globals and 4 exact guard lines', flush=True)

    return r'''
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
using std::string;
using text = string;
using fixed = double;
using playergroup = unsigned int;
#define null ""
long checks=0, fixtures=0;
int triggerCalls=0;
string context;
#define CHECK(...) do { ++checks; if(!(__VA_ARGS__)) { std::cerr << "FAIL [" << context << "] line " << __LINE__ << ": " << #__VA_ARGS__ << '\n'; std::abort(); } } while(0)
''' + global_text + '\n' + headers + r'''
text StringExternal(string key) { CHECK(key.rfind("Param/Value/",0)==0); return "["+key.substr(12)+"]"; }
text StringToText(string value) { return value; }
string IntToString(int n) { return std::to_string(n); }
int Color(double,double,double) { return 0; }
int libNtve_gf_ConvertPlayerColorToColor(int color) { return color; }
text TextWithColor(text value,int color) { return "<"+std::to_string(color)+">"+value+"</>"; }
string SoundLink(string name,int index) { CHECK(index==-1); return name; }
bool PlayerGroupHasPlayer(playergroup group,int p) { CHECK(p>=1 && p<=15); return (group&(1u<<p))!=0; }
struct Message { text value; int recipient,sender; string sound; bool operator==(const Message& b) const { return value==b.value && recipient==b.recipient && sender==b.sender && sound==b.sound; } };
std::vector<Message> messages;
void gf_CBSystemMessage(text value,int recipient,int sender,int unused,string sound,int color) {
    CHECK(recipient>=1 && recipient<=15 && (recipient==sender || sender==0) && unused==0 && color==0);
    CHECK(sound=="Silent" || sound=="UI_TipSelect");
    messages.push_back({value,recipient,sender,sound});
}
const int gt_E78AAFE7BDAAE8AEB0E5BD95=1;
void TriggerExecute(int id,bool test,bool wait) {
    CHECK(id==gt_E78AAFE7BDAAE8AEB0E5BD95 && !test && wait);
    ++triggerCalls;
    CHECK(gt_E78AAFE7BDAAE8AEB0E5BD95_Func(false,true));
}
template<class T> void clearValue(T& value) { value=T{}; }
template<class T,size_t N> void clearValue(T (&value)[N]) { for(auto& item:value) clearValue(item); }
''' + code + r'''
text key(string value) { return "["+value+"]"; }
text name(int p) { CHECK(p>=1 && p<=15); return std::to_string(p)+key("C1652170")+"<"+std::to_string(p)+">P"+std::to_string(p)+"</>"; }
void reset(int role=15,int pool=1,int target=2) {
''' + reset + r'''
    messages.clear(); triggerCalls=0;
    gv_alivePlayers=gv_players=0xfffe;
    gv_roles[1][1]=pool; gv_roles[1][0]=role;
    gv_action[1][0]=target;
    gv_visitation[1]=target;
    for(int p=1;p<=15;++p) {
        gv_name[p]="P"+std::to_string(p); gv_number[p]=std::to_string(p); gv_playerColor[p]=p;
    }
}
void expect(std::vector<text> values) {
    CHECK(messages.size()==values.size());
    for(size_t i=0;i<values.size();++i) { CHECK(messages[i].value==values[i]); CHECK(messages[i].recipient==1 && messages[i].sender==1); }
    ++fixtures;
}
// Independent specification of the modern information priority. No production
// control-flow text is regenerated from this oracle.
std::vector<text> oracle(int target,int go,int second,int plan,bool jailed,bool blocked,bool immune,bool moved,bool ignore) {
    if(jailed) return {key("276B0C60")};
    if(blocked) return {key("DTBLOCK"),key("DTBECAUSE"),key("DTWHYB")};
    if(immune && !ignore) return {key("DTNONE"),key("DTBECAUSE"),key("DTWHY5")};
    std::vector<int> visits;
    if(go) visits.push_back(go);
    if(second && (visits.empty() || visits[0]!=second)) visits.push_back(second);
    if(visits.size()==2) return {key("DTDBL1")+name(visits[0])+key("DTTHEN")+name(visits[1])+key("DTEND"),key("DTBECAUSE"),key("DTWHY4")};
    int actual=visits.empty()?0:visits[0];
    if(moved && actual!=plan) {
        text first=actual==0?key("DTPLAN")+name(plan)+key("DTSTAY"):
            plan==0?key("DTNOPLAN")+name(actual)+key("DTEND"):
            key("DTPLAN")+name(plan)+key("DTBUT")+name(actual)+key("DTEND");
        return {first,key("DTBECAUSE"),key("DTWHY3")};
    }
    if(actual==target) return {key("DTSELF"),key("DTBECAUSE"),key("DTWHY2")};
    if(actual) return {key("E5532DC0")+name(actual)+key("EF7F1D1F")};
    return {key("DTNONE"),key("DTBECAUSE"),key("DTWHY5")};
}
void detailedMatrix() {
    for(int target: {2,15}) for(int go: {0,target,3,14}) for(int second: {0,target,3,14}) for(int plan: {0,target,3,14}) for(int bits=0;bits<32;++bits) {
        bool jailed=bits&1,blocked=bits&2,immune=bits&4,moved=bits&8,ignore=bits&16;
        context="detailed t="+std::to_string(target)+" go="+std::to_string(go)+" vis2="+std::to_string(second)+" plan="+std::to_string(plan)+" bits="+std::to_string(bits);
        reset(15,1,target);
        gv_visitation[target]=go; gv_visitation2[target]=second; gv_action[target][0]=plan;
        gv_jailed[target]=jailed; gv_roleblocked[target]=blocked; gv_immune[target][2]=immune;
        gv_bhVisitMoved[target]=moved; gv_roleOptions[1][15][0]=ignore;
        gf_SKF_1_zhentan(1);
        expect(oracle(target,go,second,plan,jailed,blocked,immune,moved,ignore));
        CHECK(gv_seqAfterWait[2]);
        auto modern=messages;
        // Only intentionally changed legacy-modern case: isolated second slot.
        if(go || !second) {
            messages.clear(); old_gf_SKF_1_zhentan(1);
            CHECK(messages==modern); ++fixtures;
        }
        for(int pool: {2,5}) {
            messages.clear(); triggerCalls=0;
            if(pool==2) gf_SKF_2_mitan(1); else gf_SKF_5_xianfeng(1);
            auto detail=oracle(target,go,second,plan,jailed,blocked,immune,moved,false);
            CHECK(messages.size()>=detail.size()+2);
            for(size_t i=0;i<detail.size();++i) CHECK(messages[i].value==detail[i]);
            CHECK(triggerCalls==1 && gv_seqAfterWait[2]);
            auto current=messages;
            messages.clear(); triggerCalls=0;
            if(pool==2) old_gf_SKF_2_mitan(1); else old_gf_SKF_5_xianfeng(1);
            // Exact unchanged monitoring/crime suffix; find first monitor line.
            string visitor=key(pool==2?"B34CDE3A":"72E64164"), none=key(pool==2?"AB89B69A":"3B4C962D");
            auto suffix=[&](const std::vector<Message>& values) {
                auto it=std::find_if(values.begin(),values.end(),[&](const Message& m){ return m.value.rfind(visitor,0)==0 || m.value==none; });
                CHECK(it!=values.end()); return std::vector<Message>(it,values.end());
            };
            CHECK(suffix(messages)==suffix(current)); CHECK(triggerCalls==1); ++fixtures;
        }
    }
}
void privacyAndLegacyRegressions() {
    reset(); gv_action[2][0]=7; gf_BHBlock(2,9);
    gf_SKF_2_mitan(1); CHECK(messages[0].value==key("DTBLOCK"));
    auto now=messages; messages.clear(); old_gf_SKF_2_mitan(1);
    CHECK(messages[0].value.find("P7")!=string::npos);
    CHECK(now[0].value.find("P7")==string::npos); ++fixtures;
    reset(); gf_SKF_5_xianfeng(1); CHECK(messages[0].value==key("DTNONE"));
    messages.clear(); old_gf_SKF_5_xianfeng(1); CHECK(messages[0].value==key("3C49BE72")); ++fixtures;
    reset(); gf_BHVisit(2,3); gf_BHVisit2(2,14); gv_action[2][0]=3;
    gf_SKF_2_mitan(1); CHECK(messages[0].value.find("P14")!=string::npos);
    messages.clear(); old_gf_SKF_2_mitan(1); CHECK(messages[0].value.find("P14")==string::npos); ++fixtures;
    reset(); gv_immune[2][2]=true; gv_roleOptions[1][15][0]=true; gf_BHVisit(2,7);
    gf_SKF_2_mitan(1); CHECK(messages[0].value==key("DTNONE"));
    messages.clear(); old_gf_SKF_2_mitan(1); CHECK(std::any_of(messages.begin(),messages.end(),[](const Message& m){ return m.value.find("P7")!=string::npos; })); ++fixtures;
    reset(); gf_BHDetectiveFeedback(1,0,true); gf_BHDetectiveFeedback(1,16,true); CHECK(messages.empty()); ++fixtures;
}
void deputyAndEligibility() {
    for(int go: {0,2,3}) for(int second: {0,2,3}) for(bool immune: {false,true}) for(bool learned: {false,true}) {
        reset(21); gv_visitation[2]=go; gv_visitation2[2]=second; gv_immune[2][2]=immune;
        gv_e6B395E5B888E68A80E883BD[1][3]=learned;
        dispatch(1);
        if(learned) expect(oracle(2,go,second,0,false,false,immune,false,false));
        else expect({key(!immune && ((go && go!=2) || (second && second!=2))?"BBABB1F7":"E338915A")});
    }
    // Feedback dispatch uses profession pool, not converted true faction. The
    // exact production guards are exercised for wrong pools, death, no visit,
    // cooldown and deputy skill; no scheduling or day-end learning is simulated.
    for(int pool: {1,2,3,5}) for(int role: {4,10,15,21}) for(int bits=0;bits<16;++bits) {
        reset(role,pool); gv_diedAtNight[1]=bits&1; gv_visitation[1]=(bits&2)?0:2;
        gv_cooldown[1]=(bits&4)?1:0; gv_e6B395E5B888E68A80E883BD[1][3]=bits&8;
        bool alive=!(bits&1),visit=!(bits&2),cool=!(bits&4),learned=bits&8;
        bool qualifies=alive && visit && ((pool==1 && (role==21 || role==15)) || (cool && (pool==2 || pool==5) && role==10));
        dispatch(1); CHECK(messages.empty()!=qualifies); ++fixtures;
        if(pool==1 && role==21 && alive && visit && learned) CHECK(messages.size()==3);
    }
    for(int pool: {2,5}) for(int bits=0;bits<4;++bits) {
        reset(10,pool); gv_roleOptions[pool][10][1]=bits&1; gv_roleOptions[pool][10][2]=bits&2;
        dispatch(1); CHECK(gv_cooldown[1]==((bits&2)?3:(bits&1)?2:0)); ++fixtures;
    }
    // Upper-tier deputy keeps roster, identity, visit-clearing and achievement
    // behavior, including existing option semantics. This repair doesn't alter it.
    for(int tier: {0,4,5,6}) for(bool option: {false,true}) {
        reset(21); gv_e6B395E5B888E58FA0E5B182[1]=tier; gv_roleOptions[1][21][3]=option;
        gf_SKF_1_fushou(1); auto current=messages; int visit=gv_visitation[1],achievement=gv_specialCasePlayer[1][63];
        messages.clear(); gv_visitation[1]=2; gv_specialCasePlayer[1][63]=0;
        old_gf_SKF_1_fushou(1); CHECK(messages==current && gv_visitation[1]==visit && gv_specialCasePlayer[1][63]==achievement); ++fixtures;
    }
}
void actualVisitAndWatch() {
    for(int actor: {15,21,2,5}) {
        reset(actor==2 || actor==5?10:actor,actor==2 || actor==5?actor:1);
        gf_BHVisitNone(1);
        if(actor==15) gf_SKP_1_zhentan(1); else if(actor==21) gf_SKP_1_fushou(1); else if(actor==2) gf_SKP_2_mitan(1); else gf_SKP_5_xianfeng(1);
        CHECK(gv_visitation[1]==2 && gv_visitation2[1]==0);
        gf_BHVisit2(1,14); gf_BHBlock(1,3); CHECK(gv_visitation[1]==0 && gv_visitation2[1]==0 && gv_roleblocked[1]==3);
        if(actor==21) gv_e6B395E5B888E68A80E883BD[1][3]=true;
        dispatch(1); CHECK(messages.empty()); ++fixtures;
    }
    for(int pool: {1,2,5}) {
        reset(pool==1?15:10,pool); gf_BHVisit(1,15);
        gf_BHVisit(2,7); gf_BHVisit(15,3); gv_action[15][0]=3;
        dispatch(1); CHECK(messages[0].value.find("P3")!=string::npos);
        CHECK(messages[0].value.find("P7")==string::npos); ++fixtures;
    }
    for(int pool: {2,5}) {
        reset(10,pool); gf_BHVisit2(3,2); gf_BHVisit(4,2); gv_immune[4][2]=true; gf_BHVisit2(5,2); gf_BHVisit(5,2);
        gv_e78AAFE7BDAAE4BA8BE5AE9E[2][10]=true; dispatch(1);
        string prefix=key(pool==2?"B34CDE3A":"72E64164"); int visitors=0;
        for(const auto& m:messages) if(m.value.rfind(prefix,0)==0) { ++visitors; CHECK(m.value.find("P4")==string::npos); }
        CHECK(visitors==2); CHECK(messages.back().value.find(key("ZCCRJ0"))!=string::npos); ++fixtures;
    }
}
int main() {
    detailedMatrix(); privacyAndLegacyRegressions(); deputyAndEligibility(); actualVisitAndWatch();
    std::cout<<"PASS "<<fixtures<<" fixtures / "<<checks<<" checks; actual Galaxy bodies + UBSan/bounds; no engine claim\n";
}
'''


def run_cpp(cpp: str, *, expect_failure: bool = False) -> None:
    with tempfile.TemporaryDirectory(prefix='bh-detective-test-') as tmp:
        src, exe = Path(tmp) / 'test.cpp', Path(tmp) / 'test'
        src.write_text(cpp)
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all', str(src), '-o', str(exe)], check=True)
        result = subprocess.run([str(exe)], capture_output=expect_failure, text=True)
        if expect_failure:
            assert result.returncode != 0 and 'FAIL [' in result.stderr, 'mutation survived or failed outside assertion boundary'
        else:
            result.check_returncode()


def negative_tests(source: str, before: str) -> None:
    # All mutations exist only in memory/C++ temp files, never in production.
    static = [
        ('restore old parallel gang body', function(source, FEEDBACK[2]), function(before, FEEDBACK[2])),
        ('steal Town immunity option', 'gf_BHDetectiveFeedback(lv_a, gv_visitation[lv_a], false);', 'gf_BHDetectiveFeedback(lv_a, gv_visitation[lv_a], gv_roleOptions[1][15][0]);'),
        ('change gang cooldown tail', 'gv_cooldown[lv_a] = 3;', 'gv_cooldown[lv_a] = 4;'),
    ]
    for label, old, new in static:
        assert old in source
        try:
            check_wiring(source.replace(old, new), before)
        except AssertionError:
            print('PASS rejected static mutation:', label, flush=True)
        else:
            raise AssertionError('static mutation survived: ' + label)

    helper = function(source, 'gf_BHDetectiveFeedback')
    dynamic = [
        ('drop second visit', 'gv_visitation2[lp_target]', '0'),
        ('infer interference from action mismatch', 'gv_bhVisitMoved[lp_target] == true', 'true'),
        ('wrong restricted-target reason', 'Param/Value/DTBLOCK', 'Param/Value/DTSELF'),
    ]
    for label, old, new in dynamic:
        assert old in helper
        mutant = source.replace(helper, helper.replace(old, new))
        run_cpp(harness(mutant, before), expect_failure=True)
        print('PASS rejected behavioral mutation:', label, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--script', type=Path, default=SCRIPT)
    ap.add_argument('--before', type=Path, default=BEFORE)
    ap.add_argument('--negative-tests', action='store_true')
    args = ap.parse_args()
    source, before = args.script.read_text(), args.before.read_text()
    run_cpp(harness(source, before))
    if args.negative_tests:
        negative_tests(source, before)


if __name__ == '__main__':
    main()
