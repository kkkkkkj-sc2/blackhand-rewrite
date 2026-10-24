#!/usr/bin/env python3
"""Run actual lawyer Galaxy bodies in a C++17 engine-stub harness.

Requires g++; uses undefined/bounds sanitizers. This is a logic/wiring test, not
an SC2 compiler or rendering test. --core PATH explicitly tests a draft core
against the script's engine declarations, without claiming integration coverage.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from test_trap_roles import balanced_end, function

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
CORE = (
    'gf_LSIs', 'gf_RALawyerActions', 'gf_LSPick', 'gf_LSNight',
    'gf_LSProtected', 'gf_LSConsume', 'gf_LSRelease', 'gf_LSEndDay',
    'gf_LSEndDayThread', 'gf_LSTrySpare',
)
CALLBACKS = {
    'auto_gf_CheckVoteWin_TriggerFunc': 4,
    'auto_gf_Trial_TriggerFunc': 2,
    'auto_gf_TrialVoteResults_TriggerFunc': 1,
    'gt_Exeq_Func': 1,
    'gt_DaySequence_Func': 1,
}


def blocks(body: str, token: str) -> list[tuple[int, str]]:
    """Return actual if blocks whose condition contains token (not comments)."""
    result = []
    for match in re.finditer(r'\bif\s*\([^\n{]*' + re.escape(token) + r'[^\n{]*\)\s*\{', body):
        start = body.index('{', match.start())
        result.append((match.start(), body[match.start():balanced_end(body, start)]))

    return result


def integration(source: str) -> tuple[list[str], list[tuple[str, int]]]:
    """Audit all nine execution sites; compile their real early-return guards."""
    fragments, cases = [], []
    total = 0
    for name, expected in CALLBACKS.items():
        body = function(source, name)
        executions = list(re.finditer(r'\bgf_EExecution\((\w+)\);', body))
        assert len(executions) == expected, (name, len(executions), expected)
        total += len(executions)
        guards = blocks(body, 'gf_LSTrySpare(')
        assert guards, f'{name}: missing lawyer guard'
        for index, execution in enumerate(executions):
            lower = executions[index - 1].end() if index else 0
            candidates = [(pos, block) for pos, block in guards if lower <= pos < execution.start()]
            assert candidates, f'{name}: unguarded execution {index + 1}'
            pos, guard = candidates[-1]
            call = re.search(r'gf_LSTrySpare\((\w+),\s*([0-3])\)', guard)
            assert call, (name, guard)
            target, mode = call.group(1), int(call.group(2))
            assert target == execution.group(1), (name, target, execution.group(1))
            assert re.search(r'return\s+true\s*;', guard), (name, 'must return enclosing callback')
            chosen = body.rfind('gf_TXProtected(', lower, execution.start())
            js = body.rfind('gf_JSCommitExecute(', lower, execution.start())
            assert chosen > pos and js > pos, (name, 'lawyer must precede chosen/JS')
            assert 'gf_TXProtected' not in guard, (name, 'do not skip chosen targets')
            expected_mode = 0 if name == 'gt_Exeq_Func' else 2 if 'TrialVoteResults' in name else 3 if name == 'gt_DaySequence_Func' else 1
            assert mode == expected_mode, (name, index, mode, expected_mode)
            label = f'hook_{len(cases)}'
            fragments.append(f'bool {label}(int {target}) {{\n{guard}\n++calls["fallback"]; return false;\n}}')
            cases.append((label, mode))

        if name == 'auto_gf_CheckVoteWin_TriggerFunc':
            first_guard = guards[0][0]
            assert first_guard < body.index('gv_executionCount += 1;'), 'marshal guard must precede execution count'
            assert first_guard < body.index('gv_executionList[gv_executionCount]'), 'marshal must not record spared execution'

        if name == 'auto_gf_TrialVoteResults_TriggerFunc':
            guilty = next((block for _, block in guards if 'gv_trialVotes[0] > gv_trialVotes[1]' in block.split('{', 1)[0]), None)
            if guilty is None:
                # A small enclosing guilty-only if may contain the early-return guard.
                guilty = next((block for _, block in blocks(body, 'gv_trialVotes[0] > gv_trialVotes[1]')
                               if 'gf_LSTrySpare' in block and 'gf_TXProtected' not in block), None)
            assert guilty, 'guilty-only lawyer guard must precede chosen redirection'
            assert body.index(guilty) < body.index('gf_TXProtected('), 'chosen redirection ran before lawyer'
            fragments.append('bool guiltyHook(int lp_player) {\n' + guilty + '\n++calls["fallback"]; return false;\n}')

    dispatcher = function(source, 'gf_EExecution')
    guard_pos, guard = blocks(dispatcher, 'gf_LSTrySpare(')[0]
    assert 'gf_LSTrySpare(lp_player, 0)' in guard and re.search(r'return\s*;', guard)
    assert guard_pos < dispatcher.index('auto_gf_EExecution_lp_player ='), 'dispatcher must guard before publishing argument'
    fragments.append('void dispatcherHook(int lp_player) {\n' + guard + '\n++calls["fallback"];\n}')

    assert total == 9
    all_calls = len(re.findall(r'^\s+gf_EExecution\(', source, re.M))
    assert all_calls == total, ('new execution site needs lawyer coverage', all_calls)
    for setup in ('gf_RSMafiaSetup2', 'gf_RSTriadSetup'):
        assert 'gf_RALawyerActions(lv_a)' in function(source, setup), setup

    for click in ('gt_ASActionButtonAMafia2_Func', 'gt_ASActionButtonATriad2_Func'):
        assert 'gf_LSPick(lv_source, lv_target)' in function(source, click), click

    night = function(source, 'gf_SequenceKills')
    assert 'gf_LSNight(' in night, 'night dispatcher missing lawyer'
    assert 'gf_BHVisitAction' in source
    for pool in (2, 5):
        assert re.search(rf'gv_roleNameInput\[{pool}\]\[21\]', source), ('role registration', pool)
        assert re.search(rf'gv_roleWeights\[{pool}\]\[21\]\s*=\s*0(?:\.0+)?\s*;', source), ('default weight', pool)
        assert f'gf_BHRoleFitsKind(gv_rolesArray[lv_x], {pool}, 21)' in function(source, 'gf_OSRandomizeMatrix')

    assert not re.search(r'gv_bankRoleAchievements\[[^;\n]+\]\[21\]', source), 'role21 bank array out of bounds'
    for card in ('gf_RTMafiaRoleText', 'gf_RTTriadRoleText'):
        role_blocks = blocks(function(source, card), 'gv_roles[lv_a][0] == 21')
        assert len(role_blocks) == 1, (card, 'missing/duplicate lawyer card')
        assert 'gv_bankRoleAchievements' not in role_blocks[0][1], (card, 'role21 bank access')

    print('PASS: nine execution guards, marshal pre-count, guilty-before-chosen, setup/click/night/random wiring', flush=True)
    return fragments, cases


def transition_contract(core: str) -> None:
    """The dedicated thread freezes daylight; only NightTransition may darken it."""
    body = function(core, 'gf_LSEndDayThread')
    live = re.sub(r'//[^\n]*', '', body)
    assert not re.search(r'\b(?:CinematicFade|gf_CBDimChat)\s*\(', live), 'defense feedback must remain bright'
    assert not re.search(r'\bgv_tempLength\s*=(?!=)', live), 'do not overwrite saved daylight length'
    assert 'gv_trialPausesDay' not in live and 'gv_marshalled' not in live, 'freeze daylight unconditionally'
    ordered = (
        r'TriggerStop\(gt_DaySequence\)',
        r'TimerPause\(gv_overtimer,\s*true\)',
        r'GameTimeOfDaySetLength\(90001\.0\)',
        r'gf_LSRelease\(lp_player\)',
        r'gf_ASEndActions\(\)',
        r'gf_CBAllowDisallowChatting\(lv_a,\s*ge_Allow_Disallow\)',
        r'gf_CheckEnd\(\)',
        r'Wait\(5\.0,\s*c_timeGame\)',
        r'TimerPause\(gv_overtimer,\s*false\)',
        r'gf_NightTransition\(\)',
    )
    cursor = 0
    for pattern in ordered:
        match = re.search(pattern, live[cursor:])
        assert match, ('missing/out-of-order transition boundary', pattern)
        cursor += match.end()

    after_wait = live[live.index('Wait(5.0,'):live.index('gf_NightTransition()')]
    guards = blocks(after_wait, 'gv_gameOver')
    assert any('gv_isNight' in guard and re.search(r'return\s+true\s*;', guard)
               for _, guard in guards), 'recheck game-over/night after yielding'
    assert len(re.findall(r'\bWait\s*\(', live)) == 1, 'exactly one five-second feedback delay'


def harness(source: str, core: str, integrated: bool) -> str:
    transition_contract(core)
    bodies = [function(core, name) for name in CORE]
    # Galaxy callbacks interleave only at yielding calls. The claim/cache write
    # must stay atomic; OS threads would model a different execution engine.
    for name in ('gf_LSProtected', 'gf_LSConsume'):
        assert not re.search(r'\b(?:Wait|TriggerExecute)\s*\(', function(core, name)), (name, 'yield inside claim')

    assert re.search(r'gf_LSTrySpare\s*\(int \w+,\s*int \w+\)', bodies[-1]), 'gf_LSTrySpare requires int mode'
    bodies += [function(source, name) for name in ('gf_RANoActions', 'gf_TXResumeDay', 'gf_BHCrime', 'gf_TBEndTimer')]
    hooks, hook_cases = integration(source) if integrated else ([], [])
    bodies += hooks
    if integrated:
        # Keep the complete function: extracting role clauses would hide an early
        # return false accidentally inserted before the newly registered roles.
        bodies.append(function(source, 'gf_BHRoleFitsKind'))

    code = '\n\n'.join(bodies)
    code = re.sub(r'\b(int|bool|text|string)((?:\[\d+\])+)( +)(\w+)', r'\1\3\4\2', code)
    used = set(re.findall(r'\b(?:(?:gv|gt)_\w+|auto_gf_\w+_Trigger)\b', code)) | {
        'gv_roles', 'gv_alivePlayers', 'gv_currentPlayers', 'gv_action', 'gv_visitation',
        'gv_dayNumber', 'gv_isNight', 'gv_gameOver', 'gv_nightProcessingPhase',
        'gv_dayActions', 'gv_dayOver', 'gv_voteOn', 'gv_trialOn', 'gv_onTrial',
        'gv_trialVotes', 'gv_executionCount', 'gv_unit', 'gv_playerLocation',
        'gv_lsUsed', 'gv_lsTarget', 'gv_lsDay', 'gv_lsSparedDay',
        'gv_lsEndDay', 'gv_lsEndPlayer', 'gv_lsEndTrigger', 'gt_DaySequence',
        'gv_timer', 'gv_overtimer', 'gv_tempLength', 'gv_trialPausesDay', 'gv_marshalled',
    }
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +((?:gv|gt)_\w+|auto_gf_\w+_Trigger)\s*(?:=[^;]*)?;', source + '\n' + core, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    if not integrated:
        for kind, name, dims in (
            ('bool', 'gv_lsUsed', '[16]'), ('int', 'gv_lsTarget', '[16]'),
            ('int', 'gv_lsDay', '[16]'), ('int', 'gv_lsSparedDay', '[16]'),
            ('int', 'gv_lsEndDay', ''), ('int', 'gv_lsEndPlayer', ''),
            ('trigger', 'gv_lsEndTrigger', ''),
        ):
            declarations.setdefault(name, f'{kind} {name}{dims};')

    assert not used - declarations.keys(), ('missing globals', used - declarations.keys())
    globals_text = '\n'.join(declarations[n] for n in sorted(used))
    resets = '\n'.join(f'    clearValue({n});' for n in sorted(used))
    headers = '\n'.join(b.split('{', 1)[0] + ';' for b in bodies)
    stripped = re.sub(r'//[^\n]*|"(?:\\.|[^"\\])*"', '', code)
    called = set(re.findall(r'\b(\w+)\s*\(', stripped))
    defined = set(re.findall(r'^(?:void|bool|int) (\w+)\s*\(', code, re.M))
    special = {
        'if', 'for', 'while', 'return', 'StringExternal', 'StringToText', 'IntToText',
        'TextWithColor', 'PlayerGroupSingle', 'PlayerGroupAll', 'PlayerGroupHasPlayer',
        'PlayerGroupNextPlayer', 'DialogControlSetVisible', 'gf_CBSystemMessage',
        'TriggerCreate', 'TriggerExecute', 'TriggerStop', 'gf_CheckEnd', 'gf_EndGame',
        'gf_NightTransition', 'gf_ASStartVote', 'gf_CBAllowDisallowChatting', 'Wait',
        'TimerPause', 'GameTimeOfDaySetLength', 'CinematicFade', 'gf_CBDimChat',
    }
    stubs = '\n'.join(f'template<class... A> int {n}(A...) {{ ++calls["{n}"]; return 0; }}' for n in sorted(called - defined - special))
    constants = '\n'.join(f'constexpr int {n} = {i};' for i, n in enumerate(sorted(set(re.findall(r'\b(?:c|ge)_\w+', code)) | {'ge_Allow_Allow', 'ge_Allow_Disallow'}), 1))
    hook_tests = '\n'.join(f'    checkHook({label}, {mode});' for label, mode in hook_cases)
    if integrated:
        hook_tests += r'''
    arm(); dispatcherHook(15); assert(usedCount()==1 && !calls["fallback"]);
    reset(); gv_isNight=false; dispatcherHook(15); assert(calls["fallback"]==1 && messages.empty());
    for (auto votes: {std::pair<int,int>{0,0}, {0,1}, {1,1}, {2,1}}) {
        arm(); gv_trialVotes[0] = votes.first; gv_trialVotes[1] = votes.second;
        bool guilty=votes.first>votes.second;
        assert(guiltyHook(15) == guilty);
        assert(gv_lsUsed[1] == guilty);
        assert(gv_e78AAFE7BDAAE4BA8BE5AE9E[1][10]==guilty);
        if (!guilty) assert(messages.empty() && pending.empty() && calls["fallback"] == 1);
    }
    for (int pool: {2, 5}) {
        reset(pool);
        assert(gf_BHRoleFitsKind(1,pool,21));
        assert(gf_BHRoleFitsKind(pool==2?3:15,pool,21));
        assert(gf_BHRoleFitsKind(pool==2?10:17,pool,21));
        assert(!gf_BHRoleFitsKind(pool==2?9:16,pool,21));
        assert(!gf_BHRoleFitsKind(pool==2?11:18,pool,21));
        // Excluding killers must not exclude this nonlethal supporting role.
        gv_roleOptions[4][1][0]=true;
        assert(gf_BHRoleFitsKind(1,pool,21));
    }
'''

    return r'''
#include <algorithm>
#include <cassert>
#include <iostream>
#include <map>
#include <numeric>
#include <string>
#include <tuple>
#include <vector>
using std::string;
using text = string;
using playergroup = int;
using trigger = int;
using unit = int;
using point = int;
using timer = int;
using soundlink = int;
using sound = int;
using color = int;
using fixed = double;
constexpr int null = 0;
std::map<string,int> calls;
std::map<std::pair<int,int>,bool> visible;
std::map<int,int> chatting;
std::vector<std::pair<string,int>> messages;
std::vector<int> pending;
std::vector<string> events;
std::map<int,bool> timerPaused, dimmed;
std::vector<int> stopped;
int nextTrigger = 100, endResult = 0, releaseWaits = 0;
bool expireOnWait = false, gameOverOnWait = false, nightOnWait = false;
bool inEndDayThread = false, feedbackWaitCompleted = false, fadedOut = false;
fixed daylightLength = 0.0, savedTempLength = 0.0, feedbackElapsed = 0.0;
string StringExternal(string s) { return s; }
string StringToText(string s) { return s; }
string IntToText(int i) { return std::to_string(i); }
string TextWithColor(string s, int) { return s; }
int PlayerGroupSingle(int p) { assert(p>=1 && p<=15); return 1<<p; }
int PlayerGroupAll() { return 65534; }
bool PlayerGroupHasPlayer(int group, int p) { assert(p>=1 && p<=15); return (group & (1<<p)) != 0; }
int PlayerGroupNextPlayer(int group, int p) {
    for (p=std::max(1,p+1); p<=15; ++p) if(PlayerGroupHasPlayer(group,p)) return p;
    return -1;
}
void DialogControlSetVisible(int control, int group, bool value) {
    for(int p=1; p<=15; ++p) if(PlayerGroupHasPlayer(group,p)) visible[{control,p}] = value;
}
template<class... A> void gf_CBSystemMessage(string value, int p, A...) {
    assert(!dimmed[p] && !fadedOut);
    messages.emplace_back(value,p);
    events.push_back("message:"+std::to_string(p));
}
int TriggerCreate(string name) { assert(name=="gf_LSEndDayThread"); ++calls["TriggerCreate"]; return ++nextTrigger; }
void TriggerExecute(int id, bool, bool) { assert(id); ++calls["TriggerExecute"]; pending.push_back(id); }
void TriggerStop(int id) {
    ++calls["TriggerStop"]; stopped.push_back(id);
    events.push_back("stop:"+std::to_string(id));
}
int gf_CheckEnd() { ++calls["gf_CheckEnd"]; events.push_back("checkEnd"); return endResult; }
void gf_EndGame(int result) { assert(result==endResult); ++calls["gf_EndGame"]; events.push_back("endGame"); }
void gf_CBAllowDisallowChatting(int p, int mode) {
    chatting[p]=mode;
    events.push_back("chat:"+std::to_string(p));
}
void TimerPause(int id, bool value);
void GameTimeOfDaySetLength(fixed length);
template<class... A> void CinematicFade(bool fadeIn, A...) {
    ++calls["CinematicFade"]; fadedOut=!fadeIn;
    events.push_back(fadeIn?"fadeIn":"fadeOut");
}
void gf_CBDimChat(int p) {
    ++calls["gf_CBDimChat"]; dimmed[p]=true;
    events.push_back("dim:"+std::to_string(p));
}
template<class T> void clearValue(T &v) { v=T{}; }
template<class T, size_t N> void clearValue(T (&v)[N]) { for(auto &x:v) clearValue(x); }
''' + globals_text + '\n' + constants + r'''
void gf_ASStartVote() { ++calls["gf_ASStartVote"]; gv_voteOn=true; }
void TimerPause(int id, bool value) {
    if(inEndDayThread && id==gv_overtimer) {
        assert(stopped==std::vector<int>({gt_DaySequence,auto_gf_Trial_Trigger,auto_gf_TrialVoteResults_Trigger}));
        if(!value) {
            assert(feedbackWaitCompleted && feedbackElapsed==5.0 && !gv_gameOver && !gv_isNight);
            assert(events.back()=="wait5:end");
        }
    }

    if(inEndDayThread && id==gv_timer) assert(timerPaused[gv_overtimer] && daylightLength==90001.0);
    ++calls["TimerPause"]; timerPaused[id]=value;
    events.push_back("timer:"+std::to_string(id)+(value?":pause":":resume"));
}
void GameTimeOfDaySetLength(fixed length) {
    if(inEndDayThread) assert(length==90001.0 && timerPaused[gv_overtimer]);
    ++calls["GameTimeOfDaySetLength"]; daylightLength=length;
    events.push_back("daylight:"+std::to_string(length));
}
void assertBrightFeedback() {
    assert(!fadedOut && !calls["CinematicFade"] && !calls["gf_CBDimChat"]);
    assert(messages.size()==15);
    for(int p=1; p<=15; ++p) {
        assert(messages[p-1].second==p && !dimmed[p]);
        assert(messages[p-1].first=="Param/Value/LSDEFENSE" || messages[p-1].first=="Param/Value/LSBLOCK");
    }
}
void assertFrozenDaylight() {
    assert(timerPaused[gv_overtimer] && timerPaused[gv_timer]);
    assert(daylightLength==90001.0 && gv_tempLength==savedTempLength);
    assert(stopped==std::vector<int>({gt_DaySequence,auto_gf_Trial_Trigger,auto_gf_TrialVoteResults_Trigger}));
    assertBrightFeedback();
}
void gf_NightTransition() {
    assert(calls["protectionDelay5"]==1 && feedbackWaitCompleted && feedbackElapsed==5.0);
    assert(!gv_gameOver && !gv_isNight && !timerPaused[gv_overtimer]);
    assert(timerPaused[gv_timer] && daylightLength==90001.0 && gv_tempLength==savedTempLength);
    assert(events.back()=="timer:"+std::to_string(gv_overtimer)+":resume");
    assertBrightFeedback();
    ++calls["gf_NightTransition"]; events.push_back("nightTransition");
}
void Wait(fixed duration, int clock) {
    assert(clock==c_timeGame);
    ++calls["Wait"];
    if (duration==5.0) {
        assert(inEndDayThread && gv_dayOver && !gv_dayActions && !gv_voteOn && !gv_trialOn);
        assert(!calls["gf_NightTransition"] && !calls["protectionDelay5"]);
        assert(calls["gf_ASEndActions"]==1 && calls["gf_CheckEnd"]==1);
        assertFrozenDaylight();
        for(int p=1; p<=15; ++p) assert(chatting[p]==ge_Allow_Disallow);
        events.push_back("wait5:begin");
        ++calls["protectionDelay5"]; feedbackElapsed+=duration;
        if(gameOverOnWait) gv_gameOver=true;
        if(nightOnWait) gv_isNight=true;
        assertFrozenDaylight();
        feedbackWaitCompleted=true;
        events.push_back("wait5:end");
        return;
    }

    assert(duration==0.4);
    ++releaseWaits;
    assert(gv_trialOn && !gv_voteOn && !calls["gf_ASStartVote"]);
    assert(timerPaused[gv_timer]);
    if(inEndDayThread) {
        assertFrozenDaylight();
        assert(!calls["protectionDelay5"] && !feedbackWaitCompleted);
    }

    events.push_back("wait0.4");
    if(expireOnWait) { gv_dayOver=true; expireOnWait=false; }
}
''' + stubs + '\n' + headers + '\n' + code + r'''
void reset(int pool=2) {
''' + resets + r'''
    calls.clear(); visible.clear(); messages.clear(); chatting.clear(); pending.clear(); endResult=0; nextTrigger=100;
    events.clear(); timerPaused.clear(); dimmed.clear(); stopped.clear();
    expireOnWait=false; gameOverOnWait=false; nightOnWait=false; releaseWaits=0;
    inEndDayThread=false; feedbackWaitCompleted=false; fadedOut=false; feedbackElapsed=0.0;
    gv_timer=91; gv_overtimer=92; gv_tempLength=123.0;
    savedTempLength=gv_tempLength; daylightLength=gv_tempLength;
    gv_alivePlayers=PlayerGroupAll(); gv_currentPlayers=PlayerGroupAll();
    gv_dayNumber=2; gv_isNight=true; gv_dayActions=true; gv_voteOn=true; gt_DaySequence=77;
    auto_gf_Trial_Trigger=78; auto_gf_TrialVoteResults_Trigger=79;
    for(int p=1;p<=15;++p) {
        gv_roles[p][0]=1; gv_roles[p][1]=1; gv_unit[p]=p; gv_playerLocation[p]=p;
        for(int i=0;i<7;++i) gv_actionDialogItem[p][i]=p*10+i;
    }
    gv_roles[1][0]=21; gv_roles[1][1]=pool;
}
void arm(int pool=2) {
    reset(pool); gv_visitation[1]=15; gf_LSNight(1);
    assert(gv_lsDay[1]==3 && gv_lsTarget[1]==15 && !gv_lsUsed[1]);
    for(int p=1;p<=15;++p) for(int i=0;i<=10;++i) assert(!gv_e78AAFE7BDAAE4BA8BE5AE9E[p][i]);
    gv_dayNumber=3; gv_isNight=false; calls.clear(); messages.clear();
}
void trial(int target=15) { gv_trialOn=true; gv_onTrial=target; gv_voteOn=false; }
int usedCount() {
    // Success records only the provider, never the target or unused co-provider.
    for(int p=1;p<=15;++p) {
        assert(gv_e78AAFE7BDAAE4BA8BE5AE9E[p][10]==gv_lsUsed[p]);
        for(int i=0;i<10;++i) assert(!gv_e78AAFE7BDAAE4BA8BE5AE9E[p][i]);
    }

    return std::count(gv_lsUsed+1,gv_lsUsed+16,true);
}
void expectMessage(string key) {
    assert(usedCount()==1);
    assert(messages.size()==15);
    for(int p=1;p<=15;++p) assert(messages[p-1]==std::make_pair("Param/Value/"+key,p));
}
void drain() {
    assert(pending.size()==1); pending.clear();
    inEndDayThread=true;
    assert(gf_LSEndDayThread(false,true));
    inEndDayThread=false;
}
using Hook = bool(*)(int);
void checkHook(Hook hook, int mode) {
    arm(); trial(); assert(hook(15)); assert(!calls["fallback"] && usedCount()==1);
    expectMessage(mode==2?"LSDEFENSE":"LSBLOCK");
    if(mode>=2) { assert(!calls["gf_NightTransition"]); drain(); assert(calls["gf_NightTransition"]==1); }
    reset(); gv_isNight=false; trial();
    auto state=std::make_tuple(gv_dayActions,gv_dayOver,gv_voteOn,gv_trialOn,gv_onTrial,gv_dayNumber);
    assert(!hook(15));
    assert(state==std::make_tuple(gv_dayActions,gv_dayOver,gv_voteOn,gv_trialOn,gv_onTrial,gv_dayNumber));
    assert(calls["fallback"]==1 && messages.empty() && pending.empty() && usedCount()==0);
}
int main() {
    for(int pool: {2,5}) {
        reset(pool); assert(gf_LSIs(1));
        for(int p: {0,16}) { assert(!gf_LSIs(p)); gf_LSPick(p,15); gf_LSNight(p); assert(!gf_LSProtected(p)); assert(!gf_LSConsume(p)); }
        for(int other: {1,3,4}) { gv_roles[1][1]=other; assert(!gf_LSIs(1)); }
        reset(pool); gv_roles[1][0]=20; assert(!gf_LSIs(1));
        // UI includes self, friends and enemies; selection is toggle, never a spend.
        reset(pool); gv_alivePlayers &= ~PlayerGroupSingle(14);
        gv_roles[2][1]=pool; gv_roles[15][1]=pool==2?5:2;
        gf_RALawyerActions(1);
        for(int p=1;p<=15;++p) assert(visible[std::make_pair(p*10+5,1)]==(p!=14));
        assert(gv_variableOptions[1][0]==1);
        for(int target: {1,2,15}) {
            gf_LSPick(1,target); assert(gv_action[1][0]==target && !gv_lsUsed[1]);
            gf_LSPick(1,target); assert(!gv_action[1][0] && !gv_lsUsed[1]);
        }
        for(int bad: {0,14,16}) { gf_LSPick(1,bad); assert(!gv_action[1][0]); }
        gv_lsUsed[1]=true; gf_RALawyerActions(1);
        for(int p=1;p<=15;++p) assert(!visible[std::make_pair(p*10+5,1)]);
        gf_LSPick(1,15); assert(!gv_action[1][0]);
        for(int state=0;state<5;++state) {
            reset(pool);
            if(state==0) gv_isNight=false;
            if(state==1) gv_gameOver=true;
            if(state==2) gv_nightProcessingPhase=true;
            if(state==3) gv_alivePlayers &= ~PlayerGroupSingle(1);
            if(state==4) gv_jailed[1]=2;
            gf_LSPick(1,15); assert(!gv_action[1][0]);
        }
        // Cast follows actual visitation (bus/witch), stamps next day, not clicked target.
        reset(pool); gf_LSPick(1,14); gv_visitation[1]=15; gf_LSNight(1);
        assert(gv_lsTarget[1]==15 && gv_lsDay[1]==3 && !gv_lsUsed[1]);
        assert(!gf_LSProtected(15)); gv_dayNumber=3;
        assert(!gf_LSProtected(15) && !gf_LSConsume(15) && !gv_lsUsed[1]);
        gv_isNight=false; assert(gf_LSProtected(15) && !gv_lsUsed[1]);
        gv_dayNumber=0; assert(!gf_LSProtected(15)); gv_dayNumber=3;
        gv_gameOver=true; assert(!gf_LSProtected(15)); gv_gameOver=false;
        gv_dayNumber=4; assert(!gf_LSProtected(15) && !gv_lsUsed[1]);
        // Failed actors/targets clear stale casts without spending their lifetime use.
        for(int reason=0;reason<11;++reason) {
            reset(pool); gv_lsDay[1]=2; gv_lsTarget[1]=14; gv_visitation[1]=15;
            if(reason==0) gv_jailed[1]=2;
            if(reason==1) gv_roleblocked[1]=2;
            if(reason==2) gv_diedAtNight[1]=true;
            if(reason==3) gv_veteraned[1]=true;
            if(reason==4) gv_alivePlayers &= ~PlayerGroupSingle(1);
            if(reason==5) gv_roles[1][0]=20;
            if(reason==6) gv_visitation[1]=0;
            if(reason==7) gv_visitation[1]=16;
            if(reason==8) gv_alivePlayers &= ~PlayerGroupSingle(15);
            if(reason==9) gv_diedAtNight[15]=true;
            if(reason==10) gv_lsUsed[1]=true;
            gf_LSNight(1); assert(!gv_lsTarget[1] && !gv_lsDay[1] && gv_lsUsed[1]==(reason==10));
        }
        arm(pool); gv_dayNumber=4; gv_isNight=true; gv_visitation[1]=0; gf_LSNight(1);
        gv_dayNumber=5; gv_isNight=false; assert(!gf_LSProtected(15) && !gv_lsUsed[1]);
        // A no-execution day spends nothing; a fresh next-night choice protects only its new target.
        arm(pool); gv_dayNumber=3; gv_isNight=true; gv_visitation[1]=14; gf_LSNight(1);
        gv_dayNumber=4; gv_isNight=false;
        assert(!gf_LSProtected(15) && gf_LSProtected(14) && !gv_lsUsed[1]);
        reset(pool); gv_visitation[1]=1; gf_LSNight(1); gv_dayNumber=3; gv_isNight=false;
        assert(gf_LSConsume(1) && gv_lsUsed[1]);
        // Protection survives owner death/conversion and target faction is unrestricted.
        for(int owner=0;owner<3;++owner) for(int faction: {1,2,3,5}) {
            arm(pool); gv_roles[15][1]=faction;
            if(owner==0) gv_alivePlayers &= ~PlayerGroupSingle(1);
            if(owner==1) { gv_roles[1][0]=1; gv_roles[1][1]=3; }
            if(owner==2) { gv_roleblocked[1]=2; gv_jailed[1]=2; }
            assert(gf_LSConsume(15) && gv_lsUsed[1] && gf_LSProtected(15));
        }
        arm(pool); gv_alivePlayers &= ~PlayerGroupSingle(15); assert(!gf_LSConsume(15) && !gv_lsUsed[1]);
        // Serialized Galaxy callbacks racing the same target consume exactly one provider.
        arm(pool); gv_lsTarget[2]=15; gv_lsDay[2]=3;
        for(int i=0;i<100;++i) assert(gf_LSConsume(15));
        assert(usedCount()==1 && gv_lsSparedDay[15]==3);
        int remaining=gv_lsUsed[1]?2:1;
        gv_lsTarget[remaining]=14;
        assert(gf_LSConsume(14) && usedCount()==2 && gv_lsSparedDay[14]==3);
        gv_dayNumber=4; assert(!gf_LSConsume(15) && usedCount()==2);
        gv_isNight=true; gv_dayNumber=4; gv_visitation[1]=14; gf_LSNight(1);
        assert(!gv_lsTarget[1]); gv_dayNumber=5; gv_isNight=false; assert(!gf_LSProtected(14));
        // Every mode is inert without protection, including invalid targets and night.
        for(int mode=0;mode<=3;++mode) for(int target: {0,15,16}) {
            reset(pool); gv_isNight=false; trial();
            assert(!gf_LSTrySpare(target,mode));
            assert(gv_trialOn && !gv_voteOn && !gv_dayOver && gv_dayActions);
            assert(messages.empty() && calls.empty() && pending.empty());
        }
        // Admin bypass preserves unrelated active trial; ordinary direct execution resumes day.
        for(int mode: {0,1}) {
            arm(pool); assert(gf_LSTrySpare(15,mode)); expectMessage("LSBLOCK");
            assert(!gv_trialOn && gv_voteOn && gv_dayActions && !gv_dayOver && pending.empty());
            arm(pool); trial(14); assert(gf_LSTrySpare(15,mode));
            if(mode==0) assert(gv_trialOn && gv_onTrial==14 && !gv_voteOn && !calls["gf_ASStartVote"]);
            arm(pool); trial(); assert(gf_LSTrySpare(15,mode)); expectMessage("LSBLOCK");
            assert(!gv_trialOn && gv_voteOn && !gv_dayOver && gv_dayActions);
            assert(calls["gf_ASStartVote"]==1 && !calls["gf_NightTransition"] && pending.empty());
            for(int p=1;p<=15;++p) assert(chatting[p]==ge_Allow_Allow);
        }
        // Mode1 cannot resume voting if the day expired before it was called,
        // or expires while the defendant is lowered from either burrow pose.
        for(int pose: {0,1}) for(bool duringWait: {false,true}) {
            arm(pool); trial(); gv_e59F8BE59CB0[15][pose]=true;
            gv_dayOver=!duringWait; expireOnWait=duringWait;
            assert(gf_LSTrySpare(15,1)); expectMessage("LSBLOCK");
            assert(usedCount()==1 && !gv_voteOn && !gv_dayActions && gv_dayOver);
            assert(!calls["gf_ASStartVote"] && !calls["gf_NightTransition"] && pending.size()==1);
            assert(releaseWaits==(duringWait?1:0));
            drain();
            assert(!gv_trialOn && !gv_voteOn && !calls["gf_ASStartVote"]);
            assert(calls["gf_NightTransition"]==1 && usedCount()==1 && pending.empty());
            gf_LSEndDay(15);
            assert(pending.empty() && calls["gf_NightTransition"]==1);
        }
        for(int mode: {2,3}) {
            arm(pool); trial(); gv_executionCount=2;
            assert(gf_LSTrySpare(15,mode)); expectMessage(mode==2?"LSDEFENSE":"LSBLOCK");
            assert(usedCount()==1 && gv_executionCount==2);
            assert(!calls["gf_NightTransition"] && pending.size()==1);
            assert(!gv_voteOn && gv_dayOver && !gv_dayActions);
            // Another callback arriving before the dedicated trigger runs must
            // abort without charging another provider or reopening the day.
            gv_lsTarget[2]=14; gv_lsDay[2]=gv_dayNumber;
            assert(gf_LSTrySpare(14,1) && usedCount()==1 && pending.size()==1);
            assert(messages.size()==15 && !gv_voteOn && !gv_dayActions);
            auto beforeNoActions=calls;
            assert(gf_LSEndDayThread(false,false) && calls==beforeNoActions && pending.size()==1);
            drain(); assert(!gv_trialOn && calls["gf_NightTransition"]==1 && !calls["gf_EndGame"]);
            gf_LSEndDay(15); assert(pending.empty() && calls["gf_NightTransition"]==1);
            arm(pool); trial(); endResult=7;
            assert(gf_LSTrySpare(15,mode)); drain();
            assert(calls["gf_EndGame"]==1 && !calls["gf_NightTransition"]);
        }
        // Exercise the actual end-day body for every entry mode, both timer
        // policies, both marshal states, both burrow poses (also simultaneously),
        // and each termination phase. Muting never dims the feedback messages.
        for(int mode=0; mode<=3; ++mode) for(bool pauses: {false,true})
        for(bool marshal: {false,true}) for(int pose=0; pose<4; ++pose)
        for(int phase=0; phase<5; ++phase) {
            arm(pool); trial();
            gv_trialPausesDay=pauses; gv_marshalled=marshal;
            timerPaused[gv_overtimer]=pauses || marshal;
            daylightLength=(pauses || marshal)?90001.0:gv_tempLength;
            gv_e59F8BE59CB0[15][0]=(pose & 1)!=0;
            gv_e59F8BE59CB0[15][1]=(pose & 2)!=0;
            if(mode<2) gv_dayOver=true;
            assert(gf_LSTrySpare(15,mode));
            expectMessage(mode==2?"LSDEFENSE":"LSBLOCK");
            assert(!calls["gf_NightTransition"] && !calls["Wait"]);
            if(phase==1) endResult=7;
            if(phase==2) gv_gameOver=true; // Already ended before feedback wait.
            gameOverOnWait=phase==3; nightOnWait=phase==4;
            drain();
            assert(usedCount()==1 && pending.empty() && !gv_trialOn && !gv_voteOn && !gv_dayActions);
            assert(releaseWaits==((pose & 1)!=0)+((pose & 2)!=0));
            assert(timerPaused[gv_timer] && gv_tempLength==savedTempLength);
            assertBrightFeedback();
            for(int p=1; p<=15; ++p) assert(chatting[p]==ge_Allow_Disallow);
            if(phase==1) {
                assert(calls["gf_EndGame"]==1 && !calls["protectionDelay5"]);
                assert(!feedbackWaitCompleted && feedbackElapsed==0.0 && !calls["gf_NightTransition"]);
                assertFrozenDaylight();
            }
            else {
                assert(calls["protectionDelay5"]==1 && feedbackWaitCompleted && feedbackElapsed==5.0);
                assert(!calls["gf_EndGame"] && calls["gf_NightTransition"]==(phase==0));
                assert(calls["Wait"]==releaseWaits+1);
                if(phase!=0) {
                    assertFrozenDaylight();
                    assert(events.back()=="wait5:end");
                }
            }
        }
    }
''' + hook_tests + r'''
    std::cout << "PASS: actual lawyer bodies, bounds, picks/UI, visit/expiry, blockers, lifetime, duplicates, success-only provider crime, modes, five-second transition, release-wait expiry" << std::endl;
    std::cout << "PASS: 640 bright-feedback cases (both pools, all modes, trial-pause/marshal, four burrow poses, five termination phases); real UI timer pause, frozen daylight, no fade/dim, no duplicate night" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--core', type=Path, help='draft core only; skips integration checks explicitly')
    args = parser.parse_args()
    source = args.script.read_text()
    core = args.core.read_text() if args.core else source
    if args.core:
        print(f'DRAFT CORE ONLY: {args.core}; integration not tested', flush=True)

    values = dict(line.split('=', 1) for line in (ROOT / 'work/blackhand/strings-lawyers.txt').read_text().splitlines()
                  if line.startswith('Param/Value/'))
    assert values['Param/Value/DZCONVERT'] == '<n/>- 若己方没有杀人角色，你会变为暴徒。'

    code = harness(source, core, integrated=args.core is None)
    with tempfile.TemporaryDirectory(prefix='bh-lawyer-tests-') as tmp:
        cpp, exe = Path(tmp) / 'lawyers.cpp', Path(tmp) / 'lawyers'
        cpp.write_text(code)
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
