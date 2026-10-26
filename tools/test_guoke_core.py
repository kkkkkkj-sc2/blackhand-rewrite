#!/usr/bin/env python3
"""Execute real Guoke Galaxy core in a C++17 engine-stub harness.

Extracts complete core/CheckEnd/rebirth/nomination functions and every ET*Win
main winner predicate from --script. Only Galaxy array syntax/default local
initialization is translated. Role/winner/count/reset guards execute verbatim;
engine/UI, trigger scheduling and callback effects are explicit stubs. This is
NOT an SC2 compile/play test.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from test_bishop_votes import balanced_end, function

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'


def winner_predicates(source: str) -> list[tuple[str, int, str]]:
    rows = []
    for name in re.findall(r'^void (gf_ET\w+)\s*\([^;\n]*\)\s*\{', source, re.M):
        original = function(source, name)
        matches = re.findall(r'^\s*if \((.*gf_GKWon\(lv_a,\s*(\d+)\).*?)\)\s*\{\s*$', original, re.M)
        assert len(matches) == 1, (name, 'requires exactly one real Guoke-aware winner predicate', len(matches))
        expression, faction = matches[0]
        assert 'gf_GKIs(lv_a) == false' in expression, name
        # The psychiatric ending deliberately shares only its own/rogue wins.
        # Every other current ending must retain normal gambler co-win syntax;
        # deriving expected presence from source alone would miss its removal.
        if name != 'gf_ETJingshenWin':
            assert 'gv_e8B58CE9ACBCE782B9E695B0[lv_a] >= 3' in expression, name + ': lost gambler >=3 co-win'

        wrapper = f'bool winner_{name}(int lv_a) {{ int lv_ci=0, lv_shw=0, lv_tx=0; return ({expression}); }}'
        rows.append((name, int(faction), wrapper))

    assert len(rows) >= 24, ('unexpected ET winner coverage', len(rows))
    return rows


def nomination_threshold(source: str) -> str:
    day = function(source, 'gt_DaySequence_Func')
    match = re.search(r'\bif \(\(gv_lynchType == 0\) && \(gv_marshalled == false\) && \(gv_court == false\)\)\s*\{', day)
    assert match, 'real ordinary-majority threshold branch'
    opening = day.index('{', match.start())
    block = day[match.start():balanced_end(day, opening)]
    declarations = '\n'.join(re.findall(r'^\s*const int auto\w+_(?:ae|ai) = [^;]+;', day, re.M))
    assert 'gf_BHNoVoteOrCount(lv_a) == false' in block
    assert 'gv_votesNeeded' in block
    return 'void realNominationThreshold() { int lv_a=0, lv_x=0;\n' + declarations + '\n' + block + '\n}'


def harness(source: str) -> tuple[str, int]:
    names = (
        'gf_GKIs', 'gf_BHNoVoteOrCount', 'gf_GKSetRoleField', 'gf_GKAliveCount', 'gf_GKWon',
        'gf_BHConverted', 'gf_BHFaction', 'gf_LMCat', 'gf_LMRole',
        'gf_CheckEnd', 'gf_GKInit', 'gf_GKAbilityResetPlayer',
        'gf_GKLive', 'gf_GKMailFreeze', 'gf_XRLifeNote', 'gf_XRLifeFlush',
        'gf_XRTryRebirth', 'gf_XRLifeGamblerInit', 'gf_BHVoteWeight',
        'gf_BHWithdrawVotes', 'gt_ASVote_Func', 'gf_CheckVoteWin',
        'gt_ASTrialVote_Func', 'gt_ASSkip_Func', 'gt_ASSkipButton_Func',
        'gf_GSGRPartner', 'gf_GRChatToggle',
        'gf_EGWon', 'gf_JSIs', 'gf_JSWon', 'gf_XRGangShare', 'gf_SKN_3_dugui',
        'gf_BHVisitNone', 'gf_BHVisit', 'gf_BHVisit2', 'gf_BHUnblock', 'gf_BHSetBlocker',
    )
    winners = winner_predicates(source)
    bodies = [function(source, name) for name in names]
    bodies += [nomination_threshold(source)] + [row[2] for row in winners]
    code = '\n\n'.join(bodies)
    # Galaxy arrays precede the variable; C++ arrays follow it. Galaxy locals
    # default to zero; preserve that rather than using C++ uninitialized locals.
    code = re.sub(r'\b(int|bool|text|string|fixed)((?:\[\d+\])+)( +)(\w+)', r'\1\3\4\2', code)
    code = re.sub(r'(?m)^(\s*)(int|bool|text|string|fixed|playergroup|unit|trigger|unitgroup) (\w+(?:\[\d+\])*)\s*;', r'\1\2 \3 = {};', code)
    tests = TESTS.replace('WINNER_MATRIX', '\n'.join(
        f'    testWinner("{name}", {faction}, winner_{name}, {str("gv_e8B58CE9ACBCE782B9E695B0" in wrapper).lower()});'
        for name, faction, wrapper in winners))
    tests = tests.replace('REBORN_WINNER_CHECKS', '\n'.join(
        f'            assert(!winner_{name}(p));' for name, _, _ in winners))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +((?:gv_|gt_|auto_gf_)\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dimensions, name = match.groups()
        declarations[name] = (kind, dimensions)

    defined = set(re.findall(r'^(?:void|bool|int) (\w+)\s*\(', code, re.M))
    identifiers = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"', '', code + tests, flags=re.S)
    used = set(re.findall(r'\b(?:gv_|gt_|auto_gf_)\w+', identifiers)) - defined
    assert not used - declarations.keys(), ('missing production globals', used - declarations.keys())
    globals_text = '\n'.join(f'{declarations[name][0]} {name}{declarations[name][1]};' for name in sorted(used))
    reset = '\n'.join(f'    clearValue({name});' for name in sorted(used))
    kinds = {declarations[name][0] for name in used} - {'void', 'bool', 'int', 'string', 'text', 'fixed'}
    aliases = '\n'.join(f'using {kind} = int;' for kind in sorted(kinds))
    headers = '\n'.join(body[:body.index('{')] + ';' for body in bodies)
    calls = set(re.findall(r'\b(\w+)\s*\(', re.sub(r'//[^\n]*|"(?:\\.|[^"\\])*"', '', code)))
    native = {
        'EventPlayer', 'EventDialogControl', 'PlayerGroupAll', 'PlayerGroupSingle',
        'PlayerGroupHasPlayer', 'PlayerGroupNextPlayer', 'PlayerGroupRemove',
        'PlayerGroupAdd', 'PlayerGroupCount', 'StringExternal', 'StringToText',
        'IntToText', 'TextWithColor', 'IntToFixed', 'CeilingI', 'ModI',
        'RandomInt',
    }
    # Never silently turn a newly introduced gameplay helper into return 0.
    # Only these engine-facing UI/chat callbacks are intentionally isolated.
    allowed_gf_stubs = {
        'gf_CBSystemMessage', 'gf_CBAllowDisallowChatting',
        'gf_CBAssignUnassignChatChannel', 'gf_RefreshRoleBox', 'gf_RTRoleCard',
        'gf_GKAnnounce', 'gf_XRLifeAnnounce', 'gf_BHRefreshFactionChat', 'gf_RAGambler',
        'gf_ASFlashLine', 'gf_ASReEnableButtons',
    }
    unknown_gf = {name for name in calls - defined if name.startswith('gf_')} - allowed_gf_stubs
    assert not unknown_gf, ('unreviewed gameplay gf_ calls would be stubbed', sorted(unknown_gf))
    stubs = '\n'.join(f'template<class... A> int {name}(A... args) {{ ++calls["{name}"]; return 0; }}'
                      for name in sorted(calls - defined - native - {'if', 'else', 'for', 'while', 'return'}))
    constants = '\n'.join(f'constexpr int {name} = {i};' for i, name in enumerate(sorted(set(re.findall(r'\b(?:c_|ge_)\w+', code))), 1))
    return (PREAMBLE + aliases + '\n' + constants + '\n' + globals_text + NATIVE + stubs + '\n' + headers + '\n' + code
            + '\nvoid reset() {\n' + reset + RESET + tests, len(winners))


PREAMBLE = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>
using std::string;
using text = string;
using fixed = double;
constexpr int null = 0;
'''

NATIVE = r'''
std::map<string,int> calls;
std::vector<int> randomChoices;
size_t randomIndex = 0;
int eventPlayer = 1, eventControl = 0;
template<class T> void clearValue(T &x) { x = {}; }
template<class T, size_t N> void clearValue(T (&x)[N]) { for (auto &v: x) clearValue(v); }
int EventPlayer() { return eventPlayer; }
int EventDialogControl() { return eventControl; }
int PlayerGroupAll() { return 65534; }
int PlayerGroupSingle(int p) { return 1 << p; }
bool PlayerGroupHasPlayer(int g, int p) { assert(p>=0 && p<=15); return (g & (1<<p)) != 0; }
int PlayerGroupNextPlayer(int g, int p) { for (++p; p<16; ++p) if (PlayerGroupHasPlayer(g,p)) return p; return -1; }
void PlayerGroupAdd(int &g, int p) { assert(p>=0 && p<=15); g |= 1<<p; }
void PlayerGroupRemove(int &g, int p) { assert(p>=0 && p<=15); g &= ~(1<<p); }
int PlayerGroupCount(int g) { return __builtin_popcount(unsigned(g)); }
string StringExternal(string s) { return s; }
string StringToText(string s) { return s; }
string IntToText(int v) { return std::to_string(v); }
string TextWithColor(string s, int) { return s; }
fixed IntToFixed(int v) { return v; }
int CeilingI(fixed v) { return int(std::ceil(v)); }
int ModI(int a, int b) { return a%b; }
int RandomInt(int low, int high) {
    int result = randomIndex < randomChoices.size() ? randomChoices[randomIndex++] : low;
    assert(result>=low && result<=high); return result;
}
'''

RESET = r'''
    calls.clear(); randomChoices.clear(); randomIndex=0;
    eventPlayer=1; eventControl=0;
    gv_gameStarted=true; gv_dayNumber=3;
    for (int p=1; p<=15; ++p) {
        gv_votes[p]=1; gv_roles[p][1]=1; gv_roles[p][0]=4;
        gv_name[p]=std::to_string(p);
        for (int j=0; j<7; ++j) gv_actionDialogItem[p][j]=100*p+j;
    }
}
'''

TESTS = r'''
void add(int p,int pool,int role,bool alive=true) {
    gv_roles[p][1]=pool; gv_roles[p][0]=role;
    PlayerGroupAdd(gv_players,p); PlayerGroupAdd(gv_currentPlayers,p);
    if (alive) PlayerGroupAdd(gv_alivePlayers,p);
}
void guoke(int p,int faction=3,bool alive=true,int role=33) {
    add(p,3,role,alive); gf_GKInit(p,faction);
}
void rebornGambler(int p,bool alive=true) {
    add(p,3,17,alive);
    gv_xrLifeDid[p]=true;
    gf_XRLifeGamblerInit(p);
}
void testWinner(const char* name,int winningFaction,bool (*predicate)(int),bool gamblerCoWin) {
    int checked=0;
    for (int profession=33; profession<=37; ++profession) {
        for (int faction: {1,2,3,5}) for (bool alive: {false,true}) {
            reset(); guoke(1,faction,alive,profession);
            // Force stale ordinary-role victory flags true; none may leak past
            // the real ET predicate's Guoke exclusion on its legacy side.
            gv_jsKills[1]=9; gv_ttWon[1]=true; gv_executionWin[1]=true;
            gv_executed[1]=true; gv_e8B58CE9ACBCE782B9E695B0[1]=3;
            bool expected=faction==3 ? alive : faction==winningFaction;
            assert(predicate(1)==expected);
            ++checked;
        }
    }
    // Ordinary and reborn gamblers use the ordinary >=3 win expression, NOT
    // the GK inherited-faction/living-neutral co-win branch.
    for (bool reborn: {false,true}) for (bool alive: {false,true}) {
        reset();
        if (reborn) rebornGambler(1,alive); else add(1,3,17,alive);
        assert(!gf_GKIs(1) && !gf_GKWon(1,winningFaction));
        for (int won: {0,2,3,4}) {
            gv_e8B58CE9ACBCE782B9E695B0[1]=won;
            if (predicate(1)!=(gamblerCoWin && won>=3)) {
                std::cerr << name << " gambler predicate mismatch: reborn=" << reborn << " alive=" << alive << " wins=" << won << "\n";
                assert(false);
            }
        }
        ++checked;
    }
    std::cout << name << ": " << checked << " native-GK/gambler cases\n";
}
int main() {
    reset();
    assert(!gf_GKIs(-1) && !gf_GKIs(0) && !gf_GKIs(16));
    assert(!gf_BHNoVoteOrCount(-1) && !gf_BHNoVoteOrCount(0) && !gf_BHNoVoteOrCount(16));
    add(1,3,17);
    assert(!gf_GKIs(1) && !gf_BHNoVoteOrCount(1));
    gv_xrLifeDid[1]=true;
    assert(!gf_GKIs(1) && gf_BHNoVoteOrCount(1));
    for (int profession=33; profession<=37; ++profession) {
        reset(); guoke(1,2,true,profession);
        assert(gf_GKIs(1) && gf_BHFaction(1)==2 && gf_LMCat(1)==2 && gf_LMRole(1)==0);
        for (int pool: {1,2,3,5}) for (int role: {1,4,15,32,37}) {
            gf_GKSetRoleField(1,1,pool); gf_GKSetRoleField(1,0,role);
            assert(gv_roles[1][1]==3 && gv_roles[1][0]==profession);
        }
        // Snapshot still identifies the profession if raw state was corrupted.
        gv_roles[1][1]=1; gv_roles[1][0]=4; assert(gf_GKIs(1));
    }
    reset(); gf_GKSetRoleField(1,1,2); gf_GKSetRoleField(1,0,7);
    assert(gv_roles[1][1]==2 && gv_roles[1][0]==7);
    gf_GKSetRoleField(-1,1,3); gf_GKSetRoleField(16,1,3);
    gf_GKSetRoleField(1,-1,3); gf_GKSetRoleField(1,2,3);
    assert(gv_roles[1][1]==2 && gv_roles[1][0]==7);
    std::cout << "immutable profession and real affiliation: OK\n";

    // Native five-profession constructor remains independently supported.
    // Real GKInit -> real AbilityResetPlayer must retain today's committed pair.
    int constructorCases=0;
    for (int profession=33; profession<=37; ++profession) for (int offset: {-3,-1,0}) {
        reset(); gv_xrLife=true;
        add(1,3,34,false); add(2,1,4); add(3,1,4);
        gv_gkRole[1]=34; gv_gkFaction[1]=2;
        gv_gkPair[1][0]=2; gv_gkPair[1][1]=3;
        gv_gkPairDay[1]=gv_dayNumber+offset;
        gv_gkUsed[1]=true; gv_gkPuppet[1]=true;
        gv_gkWitnessTarget[1]=2; gv_gkWitnessCount[1]=7;
        gv_gkPanelDay[1]=gv_dayNumber; gv_gkPanel=9;
        gv_grPrivateChat[1]=true;
        gv_grChild[1]=4; gv_grParent[4]=1;
        gv_grParent[1]=5; gv_grChild[5]=1;
        gv_roles[1][0]=profession;
        gf_GKInit(1,2);
        assert(gv_gkRole[1]==profession && gv_roles[1][0]==profession);
        assert(!gv_gkUsed[1] && !gv_gkPuppet[1]);
        assert(gv_gkWitnessTarget[1]==0 && gv_gkWitnessCount[1]==-1 && gv_gkPanelDay[1]==0);
        assert(!gv_grPrivateChat[1]);
        assert(gv_grChild[1]==4 && gv_grParent[4]==1 && gv_grParent[1]==5 && gv_grChild[5]==1);
        if (offset==0) {
            assert(gv_gkPair[1][0]==2 && gv_gkPair[1][1]==3 && gv_gkPairDay[1]==gv_dayNumber);
        } else {
            assert(gv_gkPair[1][0]==0 && gv_gkPair[1][1]==0 && gv_gkPairDay[1]==0);
        }
        // Freeze uses the preserved fact, never the constructor's new job.
        gf_GKMailFreeze();
        assert(gv_gkMailLink[2][3]==(offset==0) && gv_gkMailLink[3][2]==(offset==0));
        ++constructorCases;
    }
    std::cout << "real constructor + real ability reset: " << constructorCases << " profession/day cases; current-day pair retained, stale pair dropped, other ability state reset; GR graph preserved\n";

    // Real GR partner and toggle: historical relationship edges remain for
    // lineage accounting, but neither endpoint may route private chat via GK.
    reset(); add(1,3,22); add(2,3,22);
    gv_grChild[1]=2; gv_grParent[2]=1; gv_isNight=true;
    assert(gf_GSGRPartner(1)==2 && gf_GSGRPartner(2)==1);
    gf_GRChatToggle(1,true); assert(gv_grPrivateChat[1]);
    guoke(2,3,true,33);
    assert(gv_grChild[1]==2 && gv_grParent[2]==1);
    assert(gf_GSGRPartner(1)==0 && gf_GSGRPartner(2)==0);
    gv_grPrivateChat[1]=false; gf_GRChatToggle(1,true); gf_GRChatToggle(2,true);
    assert(!gv_grPrivateChat[1] && !gv_grPrivateChat[2]);
    reset(); add(1,3,22); add(2,3,22);
    gv_grParent[1]=2; gv_grChild[2]=1; gv_isNight=true;
    guoke(2,3,true,35);
    assert(gf_GSGRPartner(1)==0 && gf_GSGRPartner(2)==0);
    gf_GRChatToggle(1,true); assert(!gv_grPrivateChat[1]);
    assert(gv_grParent[1]==2 && gv_grChild[2]==1);
    for (bool parentEdge: {false,true}) {
        reset(); add(1,3,22); add(2,3,22); gv_isNight=true;
        if (parentEdge) { gv_grParent[1]=2; gv_grChild[2]=1; }
        else { gv_grChild[1]=2; gv_grParent[2]=1; }
        assert(gf_GSGRPartner(1)==2 && gf_GSGRPartner(2)==1);
        rebornGambler(2);
        assert(!gf_GKIs(2) && gf_GSGRPartner(1)==0 && gf_GSGRPartner(2)==0);
        gf_GRChatToggle(1,true); gf_GRChatToggle(2,true);
        assert(!gv_grPrivateChat[1] && !gv_grPrivateChat[2]);
        if (parentEdge) assert(gv_grParent[1]==2 && gv_grChild[2]==1);
        else assert(gv_grChild[1]==2 && gv_grParent[2]==1);
    }
    std::cout << "real GR partner/toggle reject GK and reborn self/parent/child without erasing lineage: OK\n";

    // Ordinary native gambler counts and votes normally. Native five-role GK
    // AND reborn gamblers are excluded from counts/actors; only native GK
    // are immune to nomination (reborn gamblers remain valid targets).
    reset();
    for (int p=1; p<=4; ++p) add(p,1,4);
    add(5,3,17);
    guoke(6,1); guoke(7,2,true,34);
    for (int p=8; p<=11; ++p) rebornGambler(p);
    gv_lynchType=0; gv_voteOn=true;
    realNominationThreshold();
    assert(gf_GKAliveCount()==5 && gv_votesNeeded==3);
    for (int p: {1,3,4}) {
        eventPlayer=p; eventControl=gv_actionDialogItem[2][2];
        assert(gt_ASVote_Func(true,true));
    }
    assert(gv_voteCount[2]==3 && gv_playerVote[1]==2 && gv_playerVote[3]==2 && gv_playerVote[4]==2);
    for (int p: {6,7,8,9,10,11}) {
        eventPlayer=p; eventControl=gv_actionDialogItem[2][2];
        assert(!gt_ASVote_Func(true,true));
        assert(!gt_ASVote_Func(false,true));
        for (bool testConds: {false,true}) {
            gv_trialOn=true; gv_onTrial=2; eventControl=gv_actionDialogItem[2][3];
            assert(!gt_ASTrialVote_Func(testConds,true));
            gv_trialOn=false; eventControl=gv_skipButtonItem;
            assert(!gt_ASSkip_Func(testConds,true) && !gt_ASSkipButton_Func(testConds,true));
        }
        eventPlayer=5; gv_transientMessages[5]=0; eventControl=gv_actionDialogItem[p][2];
        assert(gt_ASVote_Func(true,true));
        assert(gv_voteCount[p]==(p>=8 ? 1 : 0));
        gf_BHWithdrawVotes(5);
        gv_votes[p]=9; gv_gkVoteDay[p]=gv_dayNumber;
        gv_zjSupportDay[p]=gv_dayNumber; gv_zjSupportVotes[p]=12;
        assert(gf_BHVoteWeight(p)==0);
    }
    eventPlayer=5; gv_transientMessages[5]=0; eventControl=gv_actionDialogItem[2][2];
    assert(gt_ASVote_Func(true,true) && gv_playerVote[5]==2 && gv_voteCount[2]==4);
    assert(gf_BHVoteWeight(5)==1 && !gf_BHNoVoteOrCount(5));
    // Today's fixed three outranks both Mayor four and Bishop nine; never
    // restores voting rights to a Guoke.
    gv_gkVoteDay[1]=gv_dayNumber; gv_votes[1]=4;
    gv_zjSupportDay[1]=gv_dayNumber; gv_zjSupportVotes[1]=9;
    assert(gf_BHVoteWeight(1)==3);
    gv_gkVoteDay[6]=gv_dayNumber; gv_votes[6]=9;
    assert(gf_BHVoteWeight(6)==0);
    gv_isNight=true; assert(gf_BHVoteWeight(1)==4);
    gv_isNight=false; ++gv_dayNumber; assert(gf_BHVoteWeight(1)==4);
    std::cout << "five ordinary + two Guoke threshold, voting exclusion, fixed three: OK\n";

WINNER_MATRIX

    // CheckEnd must be invariant under appending live/dead Guoke regardless
    // of their inherited faction or same-number/old-role remnants.
    int states=0;
    for (int town=0; town<=3; ++town) for (int mafia=0; mafia<=3; ++mafia)
    for (int triad=0; triad<=2; ++triad) for (int sk=0; sk<=1; ++sk) {
        reset(); int p=1;
        for (int n=0; n<town; ++n) add(p++,1,4);
        for (int n=0; n<mafia; ++n) add(p++,2,1);
        for (int n=0; n<triad; ++n) add(p++,5,1);
        for (int n=0; n<sk; ++n) add(p++,3,1);
        int original=gf_CheckEnd();
        guoke(12,1,true,33); guoke(13,2,false,34);
        guoke(14,5,true,35); guoke(15,3,false,36);
        assert(gf_CheckEnd()==original);
        // Same ordinary board, now append four live reborn gamblers with zero
        // won bets. Must not alter parity, two-player cases, or blocking lists.
        for (int q=12; q<=15; ++q) rebornGambler(q);
        assert(gf_GKAliveCount()==town+mafia+triad+sk);
        assert(gf_CheckEnd()==original);
        ++states;
    }
    for (int fatal: {1,5,9,13,14,15,19,20,22,26,27,31,32})
    for (int town=0; town<=2; ++town) for (int gang=0; gang<=2; ++gang) {
        reset(); int p=1;
        add(p++,3,fatal);
        for (int n=0; n<town; ++n) add(p++,1,4);
        for (int n=0; n<gang; ++n) add(p++,n==0 ? 2 : 5,1);
        int original=gf_CheckEnd();
        for (int q=12; q<=15; ++q) rebornGambler(q);
        assert(gf_CheckEnd()==original);
        ++states;
    }
    reset(); int emptyResult=gf_CheckEnd();
    for (int p=1; p<=5; ++p) guoke(p,p==1 ? 1 : p==2 ? 2 : p==3 ? 5 : 3,true,32+p);
    assert(gf_GKAliveCount()==0 && gf_CheckEnd()==emptyResult);
    assert(gf_CheckEnd()!=1 && gf_CheckEnd()!=2 && gf_CheckEnd()!=13);
    std::cout << "real CheckEnd invariant across " << states << " ordinary-faction states; only-Guoke matches empty result " << emptyResult << ": OK\n";

    // Real Note -> Flush -> TryRebirth -> GamblerInit, with mixed prior
    // professions/factions and deliberately poisoned old ability/win caches.
    int rebirthCases=0;
    for (bool shield: {false,true}) for (bool leave: {false,true}) {
        reset(); gv_xrLife=true; gv_roleOptions[3][17][0]=shield;
        add(1,1,4,false); add(2,1,8,false); gv_bhFaction[2]=2;
        add(3,5,1,false); add(4,3,34,false); add(5,3,17,false);
        for (int p=1; p<=4; ++p) {
            gv_gkRole[p]=34; gv_gkFaction[p]=2;
            gv_fzPool[p]=1; gv_fzRole[p]=8;
            gv_votes[p]=9; gv_gkVoteDay[p]=gv_dayNumber;
            gv_immuneChance[p]=7; gv_immune[p][0]=true;
            gv_lmWin[p][0]=20; gv_lmWin[p][1]=3; gv_lmFaction[p]=5;
            gv_ttWon[p]=true; gv_executionWin[p]=true; gv_executed[p]=true;
            gv_e8B58CE9ACBCE782B9E695B0[p]=9;
            gv_e8B58CE7A59EE782B9E695B0[p]=11;
            gv_cooldown[p]=8; gv_shots[p]=8; gv_skillCount[p]=8;
            gv_visitation[p]=6; gv_visitation2[p]=7; gv_suicide[p]=true;
            gv_roleblocked[p]=2;
            gv_gkUsed[p]=true; gv_gkPuppet[p]=true;
            gv_grPrivateChat[p]=true;
            gv_e7BB99E4BA86E697A0E6958CE4BA86[p]=true;
            gv_e9BB98E8AEA4E9A39FE789A9[p]=true;
            gv_playerVote[p]=5; gv_bhNominationWeight[p]=2; gv_voteCount[5]+=2;
            gv_skipVote[p]=true; gv_bhSkipWeight[p]=2; gv_skipVotes+=2;
        }
        // Same-day fact survives even though former messenger becomes gambler.
        gv_gkPair[1][0]=6; gv_gkPair[1][1]=7; gv_gkPairDay[1]=gv_dayNumber;
        add(6,1,4); add(7,1,4);
        int deathOrder[4]={2,1,4,3};
        for (int i=0; i<4; ++i) {
            int p=deathOrder[i];
            gf_XRLifeNote(p,false); gf_XRLifeNote(p,false);
            assert(gv_xrLifeN==i+1 && gv_xrLifeOrder[i+1]==p);
            if (i<3) {
                gf_XRLifeFlush();
                assert(!gv_xrLifeDone);
                for (int q=1; q<=4; ++q) assert(!gv_xrLifeDid[q]);
            }
        }
        gf_XRLifeNote(5,false); assert(gv_xrLifeN==4);
        if (leave) PlayerGroupRemove(gv_currentPlayers,2);
        int callbacks=calls["gf_RTRoleCard"];
        gf_XRLifeFlush();
        assert(gv_xrLifeDone && randomIndex==0);
        assert(calls["gf_RTRoleCard"]-callbacks==(leave ? 3 : 4));
        for (int p=1; p<=4; ++p) {
            if (leave && p==2) {
                assert(!gv_xrLifeDid[p] && !PlayerGroupHasPlayer(gv_alivePlayers,p));
                continue;
            }
            assert(gv_xrLifeDid[p] && PlayerGroupHasPlayer(gv_alivePlayers,p));
            assert(gv_roles[p][1]==3 && gv_roles[p][0]==17);
            assert(!gf_GKIs(p) && gf_BHNoVoteOrCount(p));
            assert(gv_gkRole[p]==0 && gv_gkFaction[p]==0);
            assert(gf_BHFaction(p)==3 && gf_LMCat(p)==3 && gf_LMRole(p)==17);
            assert(gv_lmWin[p][0]==0 && gv_lmWin[p][1]==0 && gv_lmFaction[p]==0 && gv_bhFaction[p]==0);
            assert(gv_fzPool[p]==0 && gv_fzRole[p]==0);
            assert(!gv_ttWon[p] && !gv_executionWin[p] && !gv_executed[p]);
            assert(gv_e8B58CE9ACBCE782B9E695B0[p]==0 && gv_e8B58CE7A59EE782B9E695B0[p]==0);
            assert(gv_cooldown[p]==0 && gv_shots[p]==-1 && gv_skillCount[p]==0);
            assert(gv_visitation[p]==0 && gv_visitation2[p]==0 && !gv_suicide[p] && gv_roleblocked[p]==0);
            assert(!gv_gkUsed[p] && !gv_gkPuppet[p] && !gv_grPrivateChat[p]);
            assert(!gv_immune[p][0] && !gv_e9BB98E8AEA4E9A39FE789A9[p]);
            assert(gv_playerVote[p]==0 && !gv_skipVote[p] && gf_BHVoteWeight(p)==0);
REBORN_WINNER_CHECKS
            gf_SKN_3_dugui(p);
            assert(gv_immuneChance[p]==(shield ? 1 : 0));
            if (shield) {
                gv_immuneChance[p]=0; gf_SKN_3_dugui(p);
                assert(gv_immuneChance[p]==0); // once only, not refill per night
            }
            PlayerGroupRemove(gv_alivePlayers,p);
            assert(!gf_XRTryRebirth(p,false));
            assert(gv_xrLifeDid[p] && !PlayerGroupHasPlayer(gv_alivePlayers,p));
            gf_XRLifeNote(p,false);
        }
        gf_GKMailFreeze();
        assert(gv_gkMailLink[6][7] && gv_gkMailLink[7][6]);
        assert(!gv_xrLifeDid[5] && !PlayerGroupHasPlayer(gv_alivePlayers,5));
        assert(gv_voteCount[5]==(leave ? 2 : 0) && gv_skipVotes==(leave ? 2 : 0));
        gf_XRLifeFlush(); assert(gv_xrLifeN==4 && !gv_xrLifeDid[5]);
        ++rebirthCases;
    }
    // Fake death and departed players do not consume a first-four position;
    // disabled/finished games and out-of-range constructors have no effects.
    reset(); add(1,1,4,false); gv_xrLife=false;
    gf_XRLifeNote(1,false); gf_XRLifeFlush();
    assert(gv_xrLifeN==0 && !gf_XRTryRebirth(1,false));
    gv_xrLife=true; gv_bhFeignRole[1]=4;
    gf_XRLifeNote(1,false); assert(gv_xrLifeN==0 && !gf_XRTryRebirth(1,false));
    gv_bhFeignRole[1]=0; PlayerGroupRemove(gv_currentPlayers,1);
    gf_XRLifeNote(1,false); assert(gv_xrLifeN==0 && !gf_XRTryRebirth(1,false));
    for (int p: {-1,0,16}) {
        gf_XRLifeNote(p,false); assert(!gf_XRTryRebirth(p,false));
    }
    assert(gv_xrLifeN==0);
    // A fake death leaves the first slot free for the next real victim.
    add(2,1,4,false); gv_bhFeignRole[1]=4; PlayerGroupAdd(gv_currentPlayers,1);
    gf_XRLifeNote(1,false); gf_XRLifeNote(2,false);
    assert(gv_xrLifeN==1 && gv_xrLifeOrder[1]==2);
    for (int p=3; p<=5; ++p) { add(p,1,4,false); gf_XRLifeNote(p,false); }
    assert(gv_xrLifeN==4);
    gv_gameOver=true; gf_XRLifeFlush();
    assert(!gv_xrLifeDone && !gv_xrLifeDid[2] && !gf_XRTryRebirth(2,false));
    gv_gameOver=false; gv_xrLife=false; gf_XRLifeFlush();
    assert(!gv_xrLifeDone && !gv_xrLifeDid[2]);
    gv_xrLife=true; gf_XRLifeFlush();
    assert(gv_xrLifeDone && gv_xrLifeDid[2] && !gv_xrLifeDid[1]);

    // Gambler constructor preserves today's messenger pairing but drops old
    // facts independently of the still-supported native five-GK constructor.
    for (int offset: {-3,-1,0}) {
        reset(); add(1,3,17); add(2,1,4); add(3,1,4);
        gv_xrLifeDid[1]=true;
        gv_gkPair[1][0]=2; gv_gkPair[1][1]=3; gv_gkPairDay[1]=gv_dayNumber+offset;
        gf_XRLifeGamblerInit(1); gf_GKMailFreeze();
        assert(gv_xrLifeDid[1] && !gf_GKIs(1));
        assert(gv_gkMailLink[2][3]==(offset==0) && gv_gkMailLink[3][2]==(offset==0));
        assert(gv_gkPairDay[1]==(offset==0 ? gv_dayNumber : 0));
    }
    // Excluded population must still close an empty board immediately; earned
    // gambler wins are checked outside the alive-population gate.
    for (bool native: {false,true}) for (bool alive: {false,true}) for (int wins: {0,2,3,4}) {
        reset();
        for (int p=1; p<=4; ++p) {
            if (native) add(p,3,17,alive); else rebornGambler(p,alive);
        }
        gv_e8B58CE9ACBCE782B9E695B0[1]=wins;
        if (!native || !alive) assert(gf_CheckEnd()==(wins>=3 ? 20 : 4));
    }
    std::cout << "real rebirth chain: " << rebirthCases << " shield/leave boards; first-four dedup, no shuffle/fifth replacement, neutral reset, one-shot revival, native gambler shield: OK\n";
    std::cout << "Guoke core source-extraction tests PASS (engine stubs; not SC2 runtime).\n";
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--emit-cpp', type=Path)
    args = parser.parse_args()
    source = args.script.read_text()
    code, count = harness(source)
    if args.emit_cpp:
        args.emit_cpp.write_text(code)

    with tempfile.TemporaryDirectory(prefix='guoke-core-') as directory:
        cpp, binary = Path(directory) / 'core.cpp', Path(directory) / 'core'
        cpp.write_text(code)
        subprocess.run(['g++', '-std=c++17', '-O1', '-fsanitize=undefined,bounds', '-fno-sanitize-recover=all', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)

    print(f'ET winner predicate coverage: {count}; source: {args.script}')


if __name__ == '__main__':
    main()
