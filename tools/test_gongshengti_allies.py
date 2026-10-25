#!/usr/bin/env python3
"""Execute real symbiote ally-list integration, with explicit engine/UI doubles.

Extracts RefreshRoleBox, GSBaseAlly, GSAllyFor, GSRefreshAllies, GSIs and
XRNeutralFatal verbatim from the maintained source. The no-GS reference is the
real pre-integration RefreshRoleBox in git (HEAD before integration, otherwise
its introducing commit's parent; no pinned revision or staging patches).
Only the reference function's name changes to permit side-by-side execution.
Requires a C++ compiler; this is not an SC2 compiler or rendering test.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from test_egun import function, mask, translate

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
NAMES = ('gf_GSIs', 'gf_XRNeutralFatal', 'gf_GSBaseAlly', 'gf_GSAllyFor',
         'gf_GSRefreshAllies', 'gf_RefreshRoleBox')


def block_end(live, opening):
    depth = 1
    cursor = opening + 1
    while depth:
        assert cursor < len(live), 'unbalanced source block'
        depth += (live[cursor] == '{') - (live[cursor] == '}')
        cursor += 1

    return cursor


def check_wiring(source):
    refresh = mask(function(source, 'gf_RefreshRoleBox'))
    calls = list(re.finditer(r'\bgf_GSRefreshAllies\s*\(\s*\)\s*;', refresh))
    assert len(calls) == 1, 'RefreshRoleBox must call GSRefreshAllies exactly once'
    call = calls[0]
    assert refresh[:call.start()].count('{') - refresh[:call.start()].count('}') == 1, \
        'GSRefreshAllies must run outside the per-viewer loop'
    assert refresh[call.end():].strip() == '}', 'inherit only the fully finished host rosters, at function end'

    member_loops = []
    for match in re.finditer(r'\bfor\s*\([^{}]*\)\s*\{', refresh):
        opening = match.end() - 1
        if re.search(r'\blv_b\b', match[0]):
            member_loops.append(refresh[opening:block_end(refresh, opening)])

    hook = r'\|\|\s*\(\s*gf_GSAllyFor\s*\(\s*lv_a\s*,\s*lv_b\s*\)\s*==\s*true\s*\)'
    assert len(member_loops) == 6, 'expected FZ/Masons/Mafia/Triad/Cult/XR roster loops'
    assert [len(re.findall(hook, loop)) for loop in member_loops] == [1] * 6, \
        'each of the SIX original roster loops needs exactly one sym membership hook'
    assert len(re.findall(r'\bgf_GSAllyFor\s*\(', refresh)) == 6

    bind = mask(function(source, 'gf_GSBind'))
    assert len(re.findall(r'\bgf_RefreshRoleBox\s*\(\s*\)\s*;', bind)) == 1, 'binding must immediately refresh ally UI'
    bound = re.search(r'gv_gsHost\[lp_player\]\s*=\s*lp_target\s*;', bind)
    refreshed = re.search(r'\bgf_RefreshRoleBox\s*\(\s*\)\s*;', bind)
    assert bound and refreshed and bound.end() < refreshed.start(), 'refresh must follow successful binding'
    assert not re.search(r'\b(?:if|while|for|return)\b', bind[bound.end():refreshed.start()]), \
        'successful binding must reach the refresh unconditionally'

    helpers = '\n'.join(mask(function(source, name)) for name in NAMES[2:5])
    writes = set(re.findall(r'\b(gv_\w+)(?:\s*\[[^;\n]*?\])*\s*(?:[+*/-]?=(?!=)|\+\+|--)', helpers))
    assert writes <= {'gv_roleBoxText'}, ('ally helpers may only change roster text/UI, not host flags, identity or chat', writes)
    for name in NAMES:
        body = function(source, name)
        first = source.count('\n', 0, source.index(body)) + 1
        print(f'{name}: lines {first}..{first + body.count(chr(10))}')

    print('PASS source wiring: six loop hooks, end-of-refresh inheritance, immediate bind refresh, read-only host state')


PREFIX = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <iostream>
#include <random>
#include <string>
#include <vector>
using string = std::string;
using text = std::string;
int gv_roles[16][2], gv_gsHost[16], gv_fzPool[16], gv_fzLeader[16];
int gv_disguiser[16], gv_bhFeignRole[16], gv_preCultRole[16][2];
int gv_playerColor[16], gv_roleBoxItem[7] = {0,1,2,3,4,5,6};
int gv_alivePlayers=1, gv_currentPlayers=2;
bool alive[16], current[16], gv_minimizedAllies[16], gv_xrGang;
string gv_name[16];
text gv_roleBoxText[16][7], gv_roleNameArray[9][40];
bool visible[16][7];
text rendered[16][7], tooltip[16][7];
int checks=0;
// Explicit doubles: engine text primitives preserve markup and distinguish players.
text StringExternal(string key) { return "{" + key + "}"; }
text StringToText(string value) { return value; }
int libNtve_gf_ConvertPlayerColorToColor(int c) { return c; }
text TextWithColor(text value,int c) { return "<color"+std::to_string(c)+">"+value+"</color>"; }
bool PlayerGroupHasPlayer(int group,int p) {
    assert(p>=1 && p<=15);
    assert(group==gv_alivePlayers || group==gv_currentPlayers);
    return group==gv_alivePlayers ? alive[p] : current[p];
}
int PlayerGroupSingle(int p) { assert(p>=1 && p<=15); return p; }
void DialogControlSetVisible(int item,int p,bool show) {
    assert(p>=1 && p<=15 && item>=0 && item<=6); visible[p][item]=show;
}
void libNtve_gf_SetDialogItemText(int item,text value,int p) {
    assert(p>=1 && p<=15 && item>=0 && item<=6); rendered[p][item]=value;
}
void libNtve_gf_SetDialogItemTooltip(int item,text value,int p) {
    assert(p>=1 && p<=15 && item>=0 && item<=6); tooltip[p][item]=value;
}
// Deliberate presentation doubles, NOT replacements for membership logic.
text gf_DQSeenName(int p) {
    assert(p>=1 && p<=15); return gv_roleNameArray[gv_roles[p][1]][gv_roles[p][0]];
}
// Default-only suite: converted teams are executed separately by test_faction_identity.py.
bool gf_BHConverted(int) { return false; }
int gf_BHFaction(int p) { return gv_roles[p][1]; }
text gf_BHDeathName(int p) { return gf_DQSeenName(p); }
text gf_FZFaceName(int p) {
    assert(p>=1 && p<=15);
    return gv_fzPool[p] ? "FACE("+std::to_string(gv_fzPool[p])+")" : gf_DQSeenName(p);
}
'''

CASES = r'''
void role(int p,int pool,int id) { gv_roles[p][1]=pool; gv_roles[p][0]=id; }
void reset() {
    gv_xrGang=false;
    for(int pool=0;pool<9;++pool) for(int id=0;id<40;++id)
        gv_roleNameArray[pool][id]="ROLE("+std::to_string(pool)+","+std::to_string(id)+")";
    for(int p=0;p<=15;++p) {
        role(p,1,1); alive[p]=current[p]=p>0; gv_minimizedAllies[p]=false;
        gv_gsHost[p]=gv_fzPool[p]=gv_fzLeader[p]=gv_disguiser[p]=gv_bhFeignRole[p]=0;
        gv_preCultRole[p][0]=gv_preCultRole[p][1]=1;
        gv_playerColor[p]=p;
        gv_name[p]="<P"+std::to_string(p)+">";
        for(int item=0;item<7;++item) {
            visible[p][item]=false;
            rendered[p][item]=tooltip[p][item]="initial";
            gv_roleBoxText[p][item]="stale-"+std::to_string(p)+"-"+std::to_string(item);
        }
    }
}
int count(text value,text token) {
    int n=0;
    for(size_t pos=0;(pos=value.find(token,pos))!=string::npos;pos+=token.size()) ++n;
    return n;
}
bool sees(int viewer,int member) { return count(gv_roleBoxText[viewer][5],gv_name[member])>0; }
void show(int p,bool list=true) {
    assert(visible[p][4] && visible[p][6]);
    assert(visible[p][5]==list);
    assert(rendered[p][5]==gv_roleBoxText[p][5]);
}
void hidden(int p) { assert(!visible[p][4] && !visible[p][5] && !visible[p][6]); }
void invariant_refresh() {
    int roles[16][2], hosts[16], faces[16], leaders[16];
    bool living[16], present[16], collapsed[16];
    for(int p=0;p<=15;++p) {
        roles[p][0]=gv_roles[p][0]; roles[p][1]=gv_roles[p][1];
        hosts[p]=gv_gsHost[p]; faces[p]=gv_fzPool[p]; leaders[p]=gv_fzLeader[p];
        living[p]=alive[p]; present[p]=current[p]; collapsed[p]=gv_minimizedAllies[p];
    }
    bool gang=gv_xrGang;
    gf_RefreshRoleBox();
    for(int p=0;p<=15;++p) {
        assert(roles[p][0]==gv_roles[p][0] && roles[p][1]==gv_roles[p][1]);
        assert(hosts[p]==gv_gsHost[p] && faces[p]==gv_fzPool[p] && leaders[p]==gv_fzLeader[p]);
        assert(living[p]==alive[p] && present[p]==current[p] && collapsed[p]==gv_minimizedAllies[p]);
    }
    assert(gang==gv_xrGang); ++checks;
}
struct UI {
    std::array<text,16*7> values, draw, tips;
    std::array<bool,16*7> shown;
    UI() {
        for(int p=0;p<=15;++p) for(int item=0;item<7;++item) {
            int i=p*7+item;
            values[i]=gv_roleBoxText[p][item]; draw[i]=rendered[p][item];
            tips[i]=tooltip[p][item]; shown[i]=visible[p][item];
        }
    }
    void restore() const {
        for(int p=0;p<=15;++p) for(int item=0;item<7;++item) {
            int i=p*7+item;
            gv_roleBoxText[p][item]=values[i]; rendered[p][item]=draw[i];
            tooltip[p][item]=tips[i]; visible[p][item]=shown[i];
        }
    }
    bool operator==(const UI& o) const {
        return values==o.values && draw==o.draw && tips==o.tips && shown==o.shown;
    }
};
void stable() {
    UI first; invariant_refresh();
    assert(UI()==first); ++checks;
}
// 0 Mafia, 1 Triad, 2 Cultist, 3 Witch Doctor, 4 Mason, 5 Elder, 6 XR, 7 FZ.
void faction(int kind,int host,int peer) {
    if(kind==0) { role(host,2,1); role(peer,2,2); }
    if(kind==1) { role(host,5,1); role(peer,5,2); }
    if(kind==2 || kind==3) { role(host,3,kind==2?8:10); role(peer,3,kind==2?10:8); }
    if(kind==4 || kind==5) { role(host,1,kind==4?7:14); role(peer,1,kind==4?14:7); }
    if(kind==6) { gv_xrGang=true; role(host,3,1); role(peer,3,1); }
    if(kind==7) {
        role(host,1,33); gv_fzPool[host]=2; gv_fzLeader[host]=6;
        role(peer,2,2); role(6,2,17);
    }
}
void sym(int p,int host) { role(p,3,29); gv_gsHost[p]=host; }
void base_matches_original() {
    // The independent oracle is rendered original production source, not a copy
    // of GSBaseAlly's condition tree. Doubles encode unique name tokens.
    UI initial;
    gf_RefreshRoleBoxBaseline();
    for(int a=1;a<=15;++a) for(int b=1;b<=15;++b) {
        assert(gf_GSBaseAlly(a,b)==sees(a,b)); ++checks;
    }
    UI baseline;
    initial.restore(); invariant_refresh();
    assert(UI()==baseline); ++checks;
}
void baseline_cases() {
    reset(); base_matches_original();
    for(int kind=0;kind<8;++kind) {
        reset(); faction(kind,2,8);
        role(3,2,3); role(4,5,3); role(5,3,8); role(7,3,10);
        role(9,1,7); role(10,1,14); role(11,3,1); role(12,3,5);
        for(int mode=0;mode<8;++mode) {
            for(int p=1;p<=15;++p) {
                alive[p]=(mode&1)?p%3!=0:true;
                current[p]=(mode&2)?p%4!=0:true;
                gv_minimizedAllies[p]=(mode&4)?p%2!=0:false;
                gv_bhFeignRole[p]=(!alive[p] && p%2==0)?1:0;
                // No stale roster may be mistaken for a visible membership.
                gv_roleBoxText[p][5]="fresh";
            }
            base_matches_original();
        }
    }
    // Disguiser presentation: compare complete original/current UI byte-for-byte.
    reset(); role(1,1,7); role(2,1,14); gv_disguiser[2]=3;
    role(4,3,8); role(5,3,10); gv_disguiser[5]=6;
    for(int dead=0;dead<2;++dead) {
        alive[3]=alive[6]=!dead;
        UI initial; gf_RefreshRoleBoxBaseline(); UI baseline;
        initial.restore(); invariant_refresh(); assert(UI()==baseline); ++checks;
    }
    // Seeded no-GS combinations preserve the full production formatting/UI.
    std::mt19937 rng(290033);
    const int pools[]={1,1,1,2,5,3,3,3,3};
    const int ids[]={1,7,14,3,3,8,10,1,5};
    for(int trial=0;trial<128;++trial) {
        reset(); gv_xrGang=trial%2;
        for(int p=1;p<=15;++p) {
            int k=rng()%9; role(p,pools[k],ids[k]);
            alive[p]=rng()%3; current[p]=rng()%4;
            gv_minimizedAllies[p]=rng()%2; gv_bhFeignRole[p]=rng()%5==0;
            gv_disguiser[p]=rng()%4==0?1+rng()%15:0;
        }
        UI initial; gf_RefreshRoleBoxBaseline(); UI baseline;
        initial.restore(); invariant_refresh(); assert(UI()==baseline); ++checks;
    }
}
void membership_cases() {
    // Exhaustive relative seat ordering: host processed before and after GS.
    for(int kind=0;kind<8;++kind) for(int host: {2,15}) for(int s: {1,14}) {
        reset(); faction(kind,host,8); sym(s,host);
        invariant_refresh();
        show(s); assert(gv_roleBoxText[s][5]==gv_roleBoxText[host][5]);
        assert(sees(host,s) && sees(8,s) && sees(s,host) && sees(s,8));
        assert(count(gv_roleBoxText[host][5],gv_name[s])==1);
        for(int v=1;v<=15;++v) {
            bool expected=gf_GSBaseAlly(host,host) && gf_GSBaseAlly(v,host);
            assert(gf_GSAllyFor(v,s)==expected);
            if(v!=s) assert(sees(v,s)==expected);
            ++checks;
        }
        stable();
    }
    // Distinct factions cannot inherit or inject into each other's roster.
    reset(); role(2,2,1); role(3,5,1); role(4,3,8); role(5,1,7);
    role(6,3,1); gv_xrGang=true; sym(1,2);
    invariant_refresh();
    for(int v: {3,4,5,6,7}) { assert(!sees(v,1) && !gf_GSAllyFor(v,1)); ++checks; }
    assert(sees(2,1) && sees(1,2));
    // All XR lethal roles use CURRENT identities and currentPlayers membership.
    for(int id: {1,5,9,13,14,20,22,26,27,31,32}) {
        reset(); gv_xrGang=true; role(2,3,id); role(3,3,id); role(4,3,id);
        role(5,3,id==1?5:1); current[4]=false; sym(1,2);
        invariant_refresh();
        assert(sees(2,1) && sees(3,1) && !sees(5,1));
        assert(!sees(1,4) && !sees(1,5));
        role(3,3,id==1?5:1); invariant_refresh(); assert(!sees(1,3) && !sees(3,1));
        // Sym current-player status is not an extra condition: membership is
        // inherited from the host, while the host must itself be current.
        current[1]=false; invariant_refresh(); show(1); assert(sees(2,1));
        current[2]=false; invariant_refresh(); hidden(1); assert(!gf_GSAllyFor(2,1));
        current[2]=true;
        gv_xrGang=false; invariant_refresh(); hidden(1);
        assert(!gf_GSAllyFor(2,1)); ++checks;
    }
    // FZ host's hidden leader and a GS attached to that leader stay hidden.
    // The real leader can still see the FZ face and its symbiote normally.
    for(int pool: {2,5}) {
        reset(); role(2,1,33); gv_fzPool[2]=pool; gv_fzLeader[2]=3;
        role(3,pool,17); role(4,pool,2); sym(1,2); sym(5,3);
        invariant_refresh();
        assert(sees(1,2) && sees(1,4) && !sees(1,3) && !sees(1,5));
        assert(sees(3,2) && sees(3,1) && sees(4,1));
        assert(!gf_GSAllyFor(2,5) && gf_GSAllyFor(3,1));
        assert(gv_roleBoxText[1][5]==gv_roleBoxText[2][5]); stable();
    }
}
void lifecycle_cases() {
    for(int kind=0;kind<8;++kind) {
        reset(); faction(kind,7,8); sym(1,7); sym(2,7); sym(15,7);
        gv_minimizedAllies[1]=true; gv_minimizedAllies[7]=false;
        invariant_refresh();
        for(int s: {1,2,15}) {
            show(s,!gv_minimizedAllies[s]);
            assert(gv_roleBoxText[s][5]==gv_roleBoxText[7][5]);
            for(int member: {1,2,15}) assert(count(gv_roleBoxText[s][5],gv_name[member])==1);
        }
        stable();
        gv_minimizedAllies[1]=false; gv_minimizedAllies[2]=true; gv_minimizedAllies[7]=true;
        invariant_refresh(); show(1); show(2,false); show(15);
        // GS death is a normal dead roster entry, NOT hidden by GSActive.
        alive[2]=false; invariant_refresh();
        assert(sees(7,2) && sees(8,2) && gv_roleBoxText[2][5]==gv_roleBoxText[7][5]);
        string deadKey=(kind==1?"418FC635":(kind==2||kind==3)?"27D29C71":
                        (kind==4||kind==5)?"4FA2AD69":"E98F2C17");
        assert(gv_roleBoxText[7][5].find("{Param/Value/"+deadKey+"}"+gv_name[2])!=string::npos);
        stable();
        // A dead non-FZ host still owns its ordinary faction roster.
        if(kind!=7) { alive[7]=false; invariant_refresh(); show(1); assert(sees(8,1)); }
    }
    // A binding follows CURRENT faction conversion, not the original host role.
    reset(); role(2,2,1); role(3,2,2); role(4,5,2); role(5,3,10); role(6,1,14);
    sym(1,2); invariant_refresh(); assert(sees(3,1) && !sees(4,1));
    for(auto next: {std::pair<int,int>{5,1}, {3,8}, {1,7}, {2,1}}) {
        role(2,next.first,next.second); invariant_refresh();
        assert(gv_roleBoxText[1][5]==gv_roleBoxText[2][5]);
        for(int v: {3,4,5,6}) assert(sees(v,1)==gf_GSBaseAlly(v,2));
        stable();
    }
    role(2,1,1); invariant_refresh(); hidden(1);
    for(int v: {2,3,4,5,6}) {
        assert(!gf_GSAllyFor(v,1));
        if(gf_GSBaseAlly(v,v)) assert(!sees(v,1));
        else hidden(v); // Original no-list hosts may retain inaccessible stale text.
    }
}
void rejected_cases() {
    for(int bad: {-99,-1,0,1,16,99}) {
        reset(); role(2,2,1); sym(1,2); invariant_refresh(); show(1);
        gv_gsHost[1]=bad;
        invariant_refresh(); hidden(1); assert(gv_roleBoxText[1][5].empty());
        for(int v=1;v<=15;++v) assert(!gf_GSAllyFor(v,1) && !sees(v,1));
        ++checks;
    }
    // No accidental recursive inheritance through a second symbiote.
    reset(); role(3,2,1); sym(1,2); sym(2,3); invariant_refresh();
    hidden(1); show(2); assert(!sees(3,1) && sees(3,2));
    // A stale binding on a non-GS role must not create a roster entry.
    reset(); role(2,2,1); gv_gsHost[1]=2; invariant_refresh();
    hidden(1); assert(!sees(2,1) && !gf_GSAllyFor(2,1));
    // Benign/lethal solo and ordinary town hosts have no own ally list.
    for(auto hostRole: {std::pair<int,int>{1,1}, {3,1}, {3,3}, {3,23}, {3,29}, {1,33}}) {
        reset(); role(2,hostRole.first,hostRole.second); sym(1,2);
        invariant_refresh(); hidden(1); assert(!gf_GSAllyFor(2,1)); ++checks;
    }
    // A dead FZ has no active face roster; stale text cannot be exposed.
    reset(); faction(7,2,8); sym(1,2); invariant_refresh(); show(1);
    alive[2]=false; invariant_refresh(); hidden(1);
    for(int v=1;v<=15;++v) assert(!gf_GSAllyFor(v,1));
    // Bounds checked before any array/group access (also enforced by UBSan).
    reset(); role(2,2,1); sym(1,2);
    for(int invalid: {-99,-1,0,16,99}) {
        assert(!gf_GSIs(invalid));
        assert(!gf_GSBaseAlly(invalid,2) && !gf_GSBaseAlly(2,invalid));
        assert(!gf_GSAllyFor(invalid,1) && !gf_GSAllyFor(2,invalid)); ++checks;
    }
}
int main() {
    baseline_cases(); membership_cases(); lifecycle_cases(); rejected_cases();
    std::cout<<"PASS "<<checks<<" GS ally-list membership/UI/lifecycle/baseline checks\n";
}
'''


def original_roster():
    path = SCRIPT.relative_to(ROOT).as_posix()

    def git(*args):
        return subprocess.run(['git', *args], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout

    revision = 'HEAD'
    baseline = function(git('show', f'{revision}:{path}'), 'gf_RefreshRoleBox')
    if re.search(r'\bgf_GS(?:AllyFor|RefreshAllies)\s*\(', mask(baseline)):
        # Keep this regression usable after the integration is committed. Find
        # the introducing change by content, never by a hardcoded revision.
        introducing = git('log', '--reverse', '--format=%H',
                          '-S', 'void gf_GSRefreshAllies', 'HEAD', '--', path).splitlines()
        assert introducing, 'cannot locate the original pre-integration roster in git'
        revision = introducing[0] + '^'
        baseline = function(git('show', f'{revision}:{path}'), 'gf_RefreshRoleBox')

    assert not re.search(r'\bgf_GS(?:AllyFor|RefreshAllies)\s*\(', mask(baseline)), \
        'baseline must be actual pre-integration source, never a stripped/rewritten implementation'
    print(f'Original roster reference: git {revision}')
    return baseline.replace('gf_RefreshRoleBox', 'gf_RefreshRoleBoxBaseline', 1)


def main():
    source = SCRIPT.read_text()
    check_wiring(source)
    bodies = [function(source, name) for name in NAMES]
    baseline = original_roster()
    prototypes = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    code = translate(PREFIX + '\n' + prototypes + '\n' + '\n\n'.join(bodies)
                     + '\n' + baseline + '\n' + CASES)
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'a C++ compiler is required'
    with tempfile.TemporaryDirectory(prefix='gs-allies-') as temporary:
        cpp, binary = Path(temporary) / 'allies.cpp', Path(temporary) / 'allies'
        cpp.write_text(code)
        subprocess.run([compiler, '-std=c++17', '-O1', '-g',
                        '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all',
                        str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
