#!/usr/bin/env python3
"""Execute production night-click events and gang action announcements with UBSan.

Town A/A2/B, their profession handlers, FZClick/YSPick and native gang click
functions are extracted verbatim. Only engine UI/message/status and card render
boundaries are doubles. BRClick is an explicit fake-recruit UI boundary (its
real recruitment resolution has its own suite). No action/visit algorithm is
reimplemented here. This is NOT an SC2 compiler, renderer or multiplayer test.
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile

from test_egun import function, mask, translate
from test_faction_conversion import block_end, missing_actual_globals

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
# shw323 immediately before this repair; dynamic HEAD would invalidate the
# receiver-only/profession-dispatch proof as soon as the repair is committed.
REFERENCE = '55a5deea463b02bfb5048f7c44dbd7859785f6d1'
EVENTS = ('gt_ASActionButtonATown_Func', 'gt_ASActionButtonATown2_Func',
          'gt_ASActionButtonBTown_Func')
BOUNDARIES = {'gf_CBSystemMessage', 'gf_DEBUG', 'gf_RAFengziActions',
              'gf_RAZhujiaoActions', 'gf_RABihuzheActions', 'gf_BRClick'}


def native_names(source):
    return list(dict.fromkeys(re.findall(
        r'^void (gf_SK(?:A|A2|B)_[25]_\w+)\s*\([^;]*\)\s*\{', mask(source), re.M)))


def source_checks(source):
    old = subprocess.run(['git', 'show', REFERENCE + ':work/blackhand/CustomLogic.galaxy'],
                         cwd=ROOT, text=True, capture_output=True, check=True).stdout
    guard = (r'\(gv_roles\[lv_a\]\[1\] == [25]\) && '
             r'\(PlayerGroupHasPlayer\(gv_alivePlayers, lv_a\) == true\) && '
             r'\(gv_jailed\[lv_a\] == 0\)')
    edited, guards = [], 0
    for name in native_names(source):
        before, after = function(old, name), function(source, name)
        expected, count = re.subn(guard, '(gf_BHGangActionRecipient(lv_source, lv_a) == true)', before)
        assert after == expected, ('native non-recipient change', name)
        if count:
            edited.append(name)
            guards += count

    assert (len(edited), guards) == (25, 93), (len(edited), guards)
    for name in EVENTS:
        after = function(source, name)
        assert after.count('gf_BHConvertedActionNotice(') == 1
        assert after.index('lv_old0 = gv_action') < after.index('gf_SK')
        assert after.index('lv_old1 = gv_action') < after.index('gf_SK')
        after = after.replace('    int lv_old0;\n    int lv_old1;\n', '')
        after = after.replace('        lv_old0 = gv_action[lv_source][0];\n'
                              '        lv_old1 = gv_action[lv_source][1];\n\n', '')
        after = after.replace('        gf_BHConvertedActionNotice(lv_source, lv_old0, lv_old1);\n\n', '')
        assert after == function(old, name), ('changed profession dispatch', name)

    notice = mask(function(source, 'gf_BHConvertedActionNotice'))
    assert not re.search(r'\bgv_\w+(?:\[[^;\n]+?\])*\s*(?:[+*/-]?=(?!=)|\+\+|--)', notice)
    for name in ('gf_SequencePrep', 'gf_SequenceBullshit', 'gf_SequenceKills',
                 'gf_SequenceAfter', 'gf_CheckEnd', 'gf_BHConvertFaction'):
        assert function(old, name) == function(source, name), ('changed resolution', name)

    definitions = '\n'.join(function(source, name) for name in (
        'gf_BHGangActionReady', 'gf_BHGangActionRecipient', 'gf_BHConvertedActionNotice'))
    keys = set(re.findall(r'Param/Value/(BHFAC\w+)', definitions))
    strings = (ROOT / 'work/blackhand/strings-gang-action.txt').read_text().splitlines()
    assert keys == {line.split('=', 1)[0].removeprefix('Param/Value/') for line in strings}
    assert len(strings) == len(keys) == 5
    assert '造访了' not in '\n'.join(strings), 'intent must not claim resolved visits'
    print('PASS structure: 25 native functions / 93 receiver guards only; original '
          'profession dispatch, conversion and night resolution unchanged', flush=True)
    return edited


PREFIX = r'''
#include <algorithm>
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
using std::string;
using text=string;
using soundlink=string;
using color=int;
using playergroup=unsigned;
using trigger=int;
#define null ""
const int c_playerStatusActive=1, c_timeGame=0;
struct Message { text line; int recipient, sender; };
std::vector<Message> messages;
int checks=0, cases=0, sourcePlayer=1, clicked=0;
int status[16], fakeRecruitCalls=0;
bool visible[16][128];
template<class T> void clearValue(T& x) { x=T{}; }
template<class T,size_t N> void clearValue(T (&x)[N]) { for(auto& e:x) clearValue(e); }
void checked(bool b,int line) { ++checks; if(!b) { std::cerr<<"FAILED case="<<cases<<" check="<<checks<<" line="<<line<<"\n"; std::abort(); } }
#define check(b) checked((b),__LINE__)
bool PlayerGroupHasPlayer(playergroup group,int p) { assert(p>=0 && p<=15); return group&(1u<<p); }
int PlayerGroupSingle(int p) { assert(p>=0 && p<=15); return p; }
int PlayerStatus(int p) { assert(p>=1 && p<=15); return status[p]; }
int EventPlayer() { return sourcePlayer; }
int EventDialogControl() { return clicked; }
text StringExternal(const char* s) { return string("{")+s+"}"; }
text StringToText(const string& s) { return s; }
text IntToText(int n) { return std::to_string(n); }
string IntToString(int n) { return std::to_string(n); }
int Color(double,double,double) { return 0; }
int libNtve_gf_ConvertPlayerColorToColor(int c) { return c; }
text TextWithColor(const text& s,int c) { return "<c"+std::to_string(c)+">"+s+"</c>"; }
soundlink SoundLink(const char* s,int n) { assert(n==-1); return s; }
void gf_CBSystemMessage(text line,int recipient,int sender,int,soundlink,color) {
    assert(recipient>=0 && recipient<=15); messages.push_back({line,recipient,sender});
}
bool DialogControlIsVisible(int item,int p) { assert(item>=0 && item<128); return visible[p][item]; }
void DialogControlSetVisible(int item,int p,bool yes) { assert(item>=0 && item<128); visible[p][item]=yes; }
void libNtve_gf_SetDialogItemTooltip(int,text,int) {}
void libNtve_gf_SetDialogItemText(int,text,int) {}
void libNtve_gf_SetDialogItemColor(int,int,int) {}
void gf_DEBUG(string) {}
void gf_RAFengziActions(int,bool) {} // Presentation only; no action writes.
void gf_RAZhujiaoActions(int) {}
void gf_RABihuzheActions(int) {}
void gf_BRClick(int,int,bool) { ++fakeRecruitCalls; }
void Wait(double,int) {}
void TriggerExecute(int,bool,bool) {}
'''

CASES = r'''
void role(int p,int pool,int id) { gv_roles[p][1]=pool; gv_roles[p][0]=id; }
void reset(int team=2,int id=3) {
    ++cases;
    RESET_GLOBALS
    clearValue(visible); clearValue(status); messages.clear(); fakeRecruitCalls=0;
    sourcePlayer=1;
    gv_gameStarted=true; gv_isNight=true; gv_bhFactionChatOpen=true; gv_dayNumber=3;
    for(int p=1;p<=15;++p) {
        role(p,1,4); gv_name[p]="P"+std::to_string(p); gv_number[p]=std::to_string(p);
        gv_playerColor[p]=p; status[p]=1;
        gv_currentPlayers|=1u<<p; gv_alivePlayers|=1u<<p;
        for(int s=0;s<7;++s) {
            gv_actionDialogItem[p][s]=p*7+s;
            for(int viewer=1;viewer<=15;++viewer) visible[viewer][p*7+s]=true;
        }
        gv_variableOptions[p][0]=gv_variableOptions[p][1]=gv_variableOptions[p][2]=gv_variableOptions[p][3]=1;
        gv_shots[p]=3;
    }
    role(1,1,id); gv_bhFaction[1]=team;
    role(2,team,4); role(3,1,15); gv_bhFaction[3]=team;
    role(4,team==2?5:2,4); role(5,1,7);
    for(int p: {1,2,3}) gv_channel[p]=team==2?1:4;
    gv_channel[4]=team==2?4:1; // Another valid gang channel is still NOT a recipient.
    gv_host=15;
}
void click(int target,int slot=5) {
    clicked=gv_actionDialogItem[target][slot];
    // These are separate real triggers on the SAME UI event, not a copied dispatch.
    gt_ASActionButtonATown_Func(true,true);
    gt_ASActionButtonATown2_Func(true,true);
    gt_ASActionButtonBTown_Func(true,true);
}
std::vector<int> intentRecipients() {
    std::vector<int> result;
    for(auto& m:messages) if(m.line.find("Param/Value/BHFAC")!=string::npos) result.push_back(m.recipient);
    std::sort(result.begin(),result.end()); return result;
}
void expectIntent(std::vector<int> expected,const string& key="",int t0=0,int t1=0) {
    check(intentRecipients()==expected);
    for(auto& m:messages) if(m.line.find("Param/Value/BHFAC")!=string::npos) {
        check(key.empty() || m.line.find("Param/Value/"+key)!=string::npos);
        check(m.sender==1 && m.line.find("<c1>P1</c>")!=string::npos);
        if(t0) check(m.line.find("<c"+std::to_string(t0)+">P"+std::to_string(t0)+"</c>")!=string::npos);
        if(t1) check(m.line.find("<c"+std::to_string(t1)+">P"+std::to_string(t1)+"</c>")!=string::npos);
    }
}
void single_cases() {
    for(int team:{2,5}) for(int id:{2,3,4,5,6,10,11,14,15,16,21,22,23,24,25,26,27,31,35}) {
        reset(team,id); gv_zmMode[1]=1;
        click(9); check(gv_action[1][0]==9); expectIntent({2,3},"BHFACWANT",9);
        messages.clear(); click(14); check(gv_action[1][0]==14); expectIntent({2,3},"BHFACCHANGE",14);
        // Same-target behaviour is role-owned: some toggle off, others ignore.
        int old0=gv_action[1][0]; messages.clear(); click(14);
        if(gv_action[1][0]==old0) expectIntent({});
        else { check(gv_action[1][0]==0); expectIntent({2,3},"BHFACCANCEL"); }
        if(gv_action[1][0]!=0) {
            messages.clear(); click(1); check(gv_action[1][0]==0); expectIntent({2,3},"BHFACCANCEL");
        }
        // Neither helper nor UI intention emission may materialize a visit.
        check(gv_visitation[1]==0 && gv_visitation2[1]==0);
    }
    // A converted elder must not notify old Masons, including converted-away Masons.
    for(int team:{2,5}) {
        reset(team,14); role(6,1,14); role(7,1,7); gv_bhFaction[7]=team==2?5:2;
        click(9);
        for(auto& m:messages) check(m.recipient!=5 && m.recipient!=6 && m.recipient!=7);
        // Native elder retains native Town-only notification.
        reset(team,14); gv_bhFaction[1]=0; gv_variableOptions[1][1]=1; click(9);
        bool seen=false; for(auto& m:messages) if(m.recipient==5) seen=true;
        check(seen); expectIntent({});
    }
}
void bus_cases() {
    for(int team:{2,5}) {
        reset(team,9);
        click(9); expectIntent({2,3},"BHFACWANT",9);
        messages.clear(); click(14,6); expectIntent({2,3},"BHFACCHANGE",9,14);
        messages.clear(); click(4); expectIntent({2,3},"BHFACCHANGE",4,14);
        messages.clear(); click(4,6); expectIntent({}); // duplicate endpoint rejected
        check(gv_action[1][0]==4 && gv_action[1][1]==14);
        messages.clear(); click(4); expectIntent({2,3},"BHFACCHANGE",14);
        check(gv_action[1][0]==0 && gv_action[1][1]==14);
        messages.clear(); click(14,6); expectIntent({2,3},"BHFACCANCEL");
        check(gv_action[1][0]==0 && gv_action[1][1]==0);
    }
}
void rejected_cases() {
    for(int team:{2,5}) {
        reset(team,6); gv_dayNumber=1; click(9); expectIntent({}); check(gv_action[1][0]==0);
        reset(team,22); gv_shots[1]=0; click(9); expectIntent({});
        reset(team,23); gv_zmMode[1]=0; click(9); expectIntent({});
        reset(team,35); gv_cooldown[1]=1; click(9); expectIntent({});
        reset(team,34); gv_jjLeft[1]=1; click(9); expectIntent({}); // living revival target
        gv_alivePlayers&=~(1u<<9); messages.clear(); click(9);
        check(gv_action[1][0]==9); expectIntent({2,3},"BHFACWANT",9);
        reset(team,3); gv_bhFaction[1]=0; click(9); expectIntent({}); // ordinary Town
        reset(team,3); clicked=127; gt_ASActionButtonATown_Func(true,true); expectIntent({});
        reset(team,3); clicked=gv_actionDialogItem[9][5];
        gt_ASActionButtonATown_Func(true,false); expectIntent({}); check(gv_action[1][0]==0);
    }
}
void apply_guard(int p,int guard) {
    switch(guard) {
    case 1: gv_alivePlayers&=~(1u<<p); break;
    case 2: gv_currentPlayers&=~(1u<<p); break;
    case 3: status[p]=0; break; // engine says left before membership cleanup
    case 4: gv_jailed[p]=5; break;
    case 5: gv_jailing[p]=5; break;
    case 6: gv_silenced[p][0]=true; break;
    case 7: gv_privateChannel[p]=7; break;
    case 8: gv_bhFeignRole[p]=17; break;
    case 9: gv_channel[p]=0; break;
    case 10: gv_grPrivateChat[p]=true; gv_grChild[p]=5; break;
    case 11: gv_crying[p]=true; break;
    case 12: gv_gkMailDay=gv_dayNumber; gv_gkMailLink[p][5]=true; break;
    case 13: gv_gkRole[p]=33; gv_gkFaction[p]=2; break;
    case 14: gv_gameOver=true; break;
    case 15: gv_bhFactionChatOpen=false; break;
    case 16: gv_nightProcessingPhase=true; break;
    case 17: gv_isNight=false; break;
    }
}
void isolation_cases() {
    for(int team:{2,5}) for(int guard=0;guard<=17;++guard) for(int endpoint:{1,2}) {
        reset(team,3); apply_guard(endpoint,guard); click(9);
        if(guard==0) expectIntent({2,3},"BHFACWANT",9);
        else if(endpoint==1 || guard>=14) expectIntent({});
        else expectIntent({3},"BHFACWANT",9);
    }
    for(int team:{2,5}) {
        reset(team,3);
        // Stale channel alone never makes spies, old Masons/parents, GS or hidden passers members.
        for(int p=4;p<=15;++p) gv_channel[p]=team==2?1:4;
        role(4,1,8); role(6,3,29); gv_gsHost[6]=1;
        role(7,1,33); gv_fzPool[7]=team;
        role(8,team,4); gv_gkRole[8]=33; gv_gkFaction[8]=team;
        click(9); expectIntent({2,3},"BHFACWANT",9);
    }
}
void fz_cases() {
    for(int team:{2,5}) for(int fake:{2,17,19,22}) {
        reset(team,33); gv_fzPool[1]=team==2?5:2; gv_fzRole[1]=fake; gv_fzLeader[1]=4;
        click(9); expectIntent({2,3},"BHFACWANT",9);
        check(gv_roles[1][1]==1 && gv_roles[1][0]==33 && gv_action[1][0]==9);
        int own=0,oldTeam=0;
        for(auto& m:messages) { own+=m.recipient==1; oldTeam+=m.recipient==4 || m.recipient==15; }
        check(own==1 && oldTeam==0); // role-specific confirmation, not duplicated generic self line
        for(int member: {2,3}) {
            check(std::count_if(messages.begin(),messages.end(),[member](const Message& message) {
                return message.recipient==member;
            })==1); // Count every text family, including the old FENGATK broadcast.
        }
        messages.clear();
        if(fake==19) { click(14,6); expectIntent({2,3},"BHFACCHANGE",9,14); }
        else { click(14); expectIntent({2,3},"BHFACCHANGE",14); }
        messages.clear(); click(fake==19?9:1); // FZ19 re-click toggles; others self cancels
        if(fake==19) { expectIntent({2,3},"BHFACCHANGE",14); messages.clear(); click(14,6); }
        expectIntent({2,3},"BHFACCANCEL");
    }
    // Native non-converted FZ legacy path remains in its separate historical suite.
}
void native_cases() {
    NATIVE_FIXTURES
}
int main() {
    single_cases(); bus_cases(); rejected_cases(); isolation_cases(); fz_cases(); native_cases();
    std::cout<<"PASS gang intention: "<<cases<<" fixtures / "<<checks<<" assertions; actual production functions, engine/UI doubles, NOT SC2 engine tested\n";
}
'''


def harness(source, natives):
    names = list(EVENTS) + natives + ['gf_FZClick', 'gf_YSPick',
             'gf_BHConvertedActionNotice', 'gf_BHGangActionRecipient']
    cursor = 0
    while cursor < len(names):
        for called in re.findall(r'\b(gf_\w+)\s*\(', mask(function(source, names[cursor]))):
            if called not in names and called not in BOUNDARIES:
                names.append(called)
        cursor += 1

    bodies = [function(source, name) for name in names]
    declarations = missing_actual_globals(source, bodies, PREFIX)
    # Include visit state only to prove clicks/notices do not synthesize visits.
    declarations += '\nint gv_visitation[16];\nint gv_visitation2[16];\nint gv_gsHost[16];\n'
    globals_names = re.findall(r'^\w+\s+(gv_\w+)', declarations, re.M)
    resets = '\n    '.join(f'clearValue({name});' for name in globals_names)
    prototypes = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    fixtures = []
    for name in natives:
        at = source.index(function(source, name))
        pool, role = map(int, re.findall(r'([25])/(\d+) ←', source[:at].splitlines()[-1])[0])
        body = function(source, name)
        team_keys = set()
        for match in re.finditer(r'if \(\(gf_BHGangActionRecipient\(lv_source, lv_a\) == true\)[^{]*\{', body):
            brace = match.end() - 1
            team_keys.update(re.findall(r'Param/Value/(\w+)', body[brace:block_end(body, brace)]))
        key_filter = ' || '.join(f'm.line.find("Param/Value/{key}")!=string::npos' for key in sorted(team_keys))
        assert key_filter, ('no actual team announcement keys', name)
        expected = '2,3' if role == 9 else '1,2,3'
        fixtures.append(f'''for(int sourceMode=0;sourceMode<5;++sourceMode) for(int phase=0;phase<3;++phase) {{
        reset({pool},3); role(1,{pool},{role}); gv_bhFaction[1]=0;
        if({role}==9 || sourceMode==1) {{ gv_jailing[1]=5; gv_channel[1]=0; }}
        if(sourceMode==2) {{ gv_silenced[1][0]=true; gv_channel[1]=0; }}
        if(sourceMode==3) {{ gv_privateChannel[1]=7; gv_channel[1]=0; }}
        if(sourceMode==4) {{ gv_grPrivateChat[1]=true; gv_grChild[1]=5; gv_channel[1]=0; }}
        gv_action[1][0]=phase?9:0;
        {name}(1,phase==2?1:14);
        std::vector<int> recipients;
        // Classify the actual team-message text, not unchanged prison/spy messages.
        for(auto& m:messages) if({key_filter}) recipients.push_back(m.recipient);
        std::sort(recipients.begin(),recipients.end());
        check(recipients==(sourceMode || {role}==9 ? std::vector<int>({{2,3}}) : std::vector<int>({{{expected}}})));
        check(gv_action[1][0]==(phase==2?0:14));
        check(gv_visitation[1]==0 && gv_visitation2[1]==0);
    }}''')
        fixtures.append(f'''for(int endpoint: {{1,3}}) for(int guard=1;guard<=17;++guard) {{
        if(endpoint==1 && (guard==4 || guard==5 || guard==6 || guard==7 || guard==9 || guard==10 || guard==11)) continue;
        reset({pool},3); role(1,{pool},{role}); gv_bhFaction[1]=0;
        if({role}==9) {{ gv_jailing[1]=5; gv_channel[1]=0; }}
        apply_guard(endpoint,guard);
        {name}(1,14);
        std::vector<int> recipients;
        for(auto& m:messages) if({key_filter}) recipients.push_back(m.recipient);
        std::sort(recipients.begin(),recipients.end());
        if(endpoint==1 || guard>=14) check(recipients.empty());
        else check(recipients==({role}==9?std::vector<int>({{2}}):std::vector<int>({{1,2}})));
        check(gv_visitation[1]==0 && gv_visitation2[1]==0);
    }}''')
    cases = CASES.replace('RESET_GLOBALS', resets).replace('NATIVE_FIXTURES', '\n'.join(fixtures))
    code = translate(PREFIX + declarations + '\n' + prototypes + '\n' + '\n\n'.join(bodies) + '\n#line 1 "gang-action-cases"\n' + cases)
    # Galaxy initializes locals to their default value; C++ does not.
    code = re.sub(r'^(\s+)(int|bool|playergroup|trigger) (\w+);$', r'\1\2 \3{};', code, flags=re.M)
    return code, names


def mutation_codes(code):
    def changed(name, old, new, count):
        body = function(code, name)
        assert body.count(old) == count, (name, old)
        return code.replace(body, body.replace(old, new))

    yield 'missing converted notice', changed('gf_BHConvertedActionNotice',
        '    int lv_a{};', '    int lv_a{};\n    return;', 1)
    yield 'cross-gang recipient', changed('gf_BHGangActionRecipient',
        ' && (gf_BHFaction(lp_source) == gf_BHFaction(lp_recipient))', '', 1)
    yield 'native excludes recruited recipients', changed('gf_SKA2_2_canmou',
        '(gf_BHGangActionRecipient(lv_source, lv_a) == true)',
        '(gv_roles[lv_a][1] == 2) && (PlayerGroupHasPlayer(gv_alivePlayers, lv_a) == true) && (gv_jailed[lv_a] == 0)', 3)
    yield 'elder sends old Mason channel', changed('gf_SKA2_1_gongjihuizhanglao',
        ' && (gf_BHConverted(lv_source) == false)', '', 3)
    yield 'duplicate converted FZ legacy broadcast', changed('gf_FZClick',
        '(lv_converted == false) && (((lv_converted == true)', '(((lv_converted == true)', 1)
    yield 'old parent private-chat leak', changed('gf_BHGangActionReady',
        ' || ((gv_grPrivateChat[lp_player] == true) && (gf_GSGRPartner(lp_player) != 0))', '', 1)
    body = function(code, 'gf_BHGangActionSourceReady')
    yield 'native jailer intent suppressed', code.replace(body,
        'bool gf_BHGangActionSourceReady(int lp_source) { return gf_BHGangActionReady(lp_source); }')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--mutations', action='store_true', help='require seven regressions to fail business assertions')
    args = parser.parse_args()
    source = args.script.read_text()
    natives = source_checks(source)
    code, names = harness(source, natives)
    print(f'Extracted {len(names)} complete production functions', flush=True)
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'C++ compiler required'
    with tempfile.TemporaryDirectory(prefix='gang-action-') as temporary:
        cpp, binary = Path(temporary) / 'test.cpp', Path(temporary) / 'test'
        cpp.write_text(code)
        subprocess.run([compiler, '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        if args.mutations:
            for index, (label, mutant) in enumerate(mutation_codes(code)):
                mutant_cpp, mutant_bin = Path(temporary) / f'mutant{index}.cpp', Path(temporary) / f'mutant{index}'
                mutant_cpp.write_text(mutant)
                subprocess.run([compiler, '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                                '-fno-sanitize-recover=all', str(mutant_cpp), '-o', str(mutant_bin)], check=True)
                result = subprocess.run([str(mutant_bin)], text=True, capture_output=True)
                assert result.returncode != 0 and 'FAILED case=' in result.stderr, ('mutant survived or failed outside business assertions', label, result.stdout, result.stderr)
                print('PASS rejected mutant:', label, flush=True)


if __name__ == '__main__':
    main()
