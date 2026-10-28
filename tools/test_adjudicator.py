#!/usr/bin/env python3
"""Execute production adjudicator, execution, death and guard bodies in C++17.

No Python reimplementation of the role. Galaxy->C++ only changes types/array
syntax and null handles. Explicit engine substitutes below cover rendering,
triggers and external unrelated professions. Real bus/witch dispatch is checked
statically; runtime tests inject its final destinations, not a SC2 simulation.
Requires g++, enables UBSan/bounds; this is NOT an SC2 real-client test.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from preset_gen import load_strings
from test_recruiter_modes import balanced_end


def function(source: str, name: str) -> str:
    match = re.search(r'^\w+ ' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', source, re.M)
    assert match, name
    return source[match.start():balanced_end(source, match.end() - 1)]

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
HELPERS = (
    'gf_GKLive', 'gf_EGCanAct', 'gf_EGName', 'gf_RANoActions',
    'gf_BHVisit', 'gf_BHVisit2', 'gf_BHVisitNone', 'gf_BHVisitAction',
    'gf_BHCrime', 'gf_BHCrimeMurder', 'gf_BHRecordNightKiller',
    'gf_EExecution', 'auto_gf_EExecution_TriggerFunc',
    'gf_KillPlayer', 'auto_gf_KillPlayer_TriggerFunc', 'gf_GSKillPlayerDirect',
    'gf_ESBodyguardKill', 'gf_GKSetRoleField', 'gf_LSProtected', 'gf_LSConsume',
    'gf_LSTrySpare', 'gf_LSRelease', 'gf_LSEndDay', 'gf_LSEndDayThread',
    'gf_TXResumeDay', 'gf_BHNoVoteOrCount', 'auto_gf_CheckVoteWin_TriggerFunc',
    'gf_TXProtected',
)

# Only unrelated role side effects and presentation APIs may be inert. Missing
# dependency is fatal: no implicit fallback stubs or swallowed business logic.
NOOP = '''
ActorSend CameraApplyInfo CameraLockInput CameraSetBounds CameraSetCameraMouseRotation
CinematicFade DialogControlSetEnabled DialogControlSetPosition DialogControlSetSize
DialogSetVisible PlayerSetCameraFollow
SoundPlay SoundSetReverb SoundSetVolume TextTagDestroy TriggerEnable TriggerStop
UIClearMessages UIDisplayMessage UnitIssueOrder UnitRemove UnitSetFacing UnitSetPosition
UnitSetState UnitSetCustomValue UnitSetPropertyFixed UnitSetScale
libNtve_gf_CreateModelAtPoint libNtve_gf_PauseUnit libNtve_gf_PlayAnimation
libNtve_gf_SetAnimationTimeScale libNtve_gf_SetDialogItemImage
libNtve_gf_SetDialogItemImage2 libNtve_gf_SetDialogItemText libNtve_gf_SetDialogItemTooltip
libNtve_gf_ShowHideDoodadsInRegion
libNtve_gf_SetDialogItemChecked libNtve_gf_SetDialogItemTextColor
libNtve_gf_SetDialogItemStyle libNtve_gf_SetPlayerAlliance
libNtve_gf_SetUnitPlayerColor
libNtve_gf_SendActorMessageToUnit
libNtve_gf_SetDialogItemVisible
libNtve_gf_CameraLockCameraInput
libNtve_gf_SetDialogItemTextWriteout
libNtve_gf_SetDialogItemTextWriteoutDuration
libNtve_gf_SetDialogItemTextWriteoutSound
libNtve_gf_SetDialogItemTextWriteoutDurationPerChar
libNtve_gf_SetDialogItemTextWriteoutPause
libNtve_gf_SetDialogItemTextWriteoutCount
libNtve_gf_SetDialogItemTextWriteoutDelay
libNtve_gf_SetDialogItemTextWriteoutSpeed
libNtve_gf_SetDialogItemTextWriteoutEnable
libNtve_gf_SetDialogItemTextWriteoutRestart
libNtve_gf_SetDialogItemTextWriteoutStop
libNtve_gf_SetDialogItemTextWriteoutReset
libNtve_gf_SetDialogItemTextWriteoutClear
libNtve_gf_SetDialogItemTextWriteoutStart
libNtve_gf_SetDialogItemTextWriteoutEnd
libNtve_gf_SetDialogItemTextWriteoutSkip
libNtve_gf_SetDialogItemTextWriteoutFinish
gf_ASStartVote gf_ASEndActions gf_CBAllowDisallowChatting gf_CBHighlightText
gf_CBDimChat gf_CBDeleteChannels gf_CBAssignUnassignChatChannel gf_CBBHClearChannels
gf_CWGainPanic gf_DQOnExecute gf_DQReveal gf_DEBUG gf_ELAddMessage
gf_EndGame gf_ERunDeathType gf_FlashScreen gf_GSHostDied gf_GSDrainDeaths
gf_GSFlushDeaths gf_GSReconcile gf_GSOnDeath gf_GSCheckLinks
gf_LMOnDeath gf_XRLifeNote gf_YSOnDeath gf_GKOnDeath gf_BHDeathNotice
gf_BHRecordSKKill gf_BHHiddenApply gf_JSRestoreCam gf_TBEndTimer gf_TBStartTimer2
CameraPan gf_CAssembleMainBank gf_XRLifeFlush gf_LMSettle gf_RefreshRoleBox gf_ESetupDeathType
gf_JSBanMsg gf_JSAbandon gf_TXBanMsg gf_CameraAction gf_Trial gf_ASTieVote gf_ASStopVote
'''.split()
# Pure graphics/catalog getters. Zero means no units/doodads and no distance to
# execution podium. Death bookkeeping and eligibility are never replaced here.
ZERO = '''
ActorFromDoodad AbilityCommand AngleBetweenPoints CameraInfoFromId DistanceBetweenPoints
Order OrderTargetingPoint PointFromId PointWithOffsetPolar RegionEntireMap RegionFromId
RegionRandomPoint UnitFilter UnitGetPosition UnitGroup UnitGroupCount UnitGroupUnitFromEnd
libNtve_gf_CreateActorAtPoint libNtve_gf_MainActorofUnit libNtve_gf_RandomAngle
libNtve_gf_SetVisibility libNtve_gf_UnitIsPaused
CameraInfoDefault libNtve_gf_ActorLastCreated libNtve_gf_SetTintColor
libNtve_gf_SetRotation libNtve_gf_SetScale libNtve_gf_SetAnimationTime
'''.split()


def integration(source: str) -> list[str]:
    """Check actual production order; return real clock/winner expressions to run."""
    init, night = (function(source, name) for name in (
        'gf_InitializeVariables', 'auto_gf_NightTransition_TriggerFunc'))
    assert 'gf_CJReset();' in init
    assert 'gf_CJNightSetup(lv_a);' in night
    assert night.index('gf_CJDusk();') < night.index('gv_isNight = true;')
    assert 'gf_CJStart();' in function(source, 'gt_Start_Func')
    assert 'gf_CJPrepareVisits();' in function(source, 'gf_SequencePrep')
    swaps = function(source, 'gf_SequenceBullshit')
    assert swaps.index('gf_CJRedirectSecond(lv_a);') < swaps.index('gv_location[lv_a] = gv_visitation[lv_a]')
    kills = function(source, 'gf_SequenceKills')
    assert kills.index('gf_CJResolveNight();') < kills.index('gf_CJRevengeNight();')
    clock = function(source, 'gt_NightSequence_Func')
    # Use the actual increment in the executable test, not a fixed fake date.
    assert clock.index('gf_XZFirstDawn();') < clock.index('gv_dayNumber += 1;')
    assert 'gf_CJMorning();' in function(source, 'gt_DaySequence_Func')
    death = function(source, 'gf_GSKillPlayerDirect')
    assert death.index('PlayerGroupRemove(gv_alivePlayers, lp_player);') < death.index('gf_CJOnDeath(lp_player);')
    assert 'gf_BHVisitNone' not in function(source, 'gf_CJClearRound')
    attack, callback = (function(source, name) for name in ('gf_CJAttack', 'gf_CJOnDeath'))
    assert 'gf_BHCrimeMurder' not in attack, 'attempts must not award murder before a native death'
    assert attack.index('gf_BHRecordNightKiller(target, p);') < attack.index('gf_KillPlayer(target, false);')
    assert callback.index('PlayerGroupHasPlayer(gv_alivePlayers, dead) == false') < callback.index('gf_BHCrimeMurder')
    execute = function(source, 'auto_gf_EExecution_TriggerFunc')
    assert execute.index('gf_ERunDeathType(lp_player);') < execute.index('gv_cjExecution[lp_player] =') < execute.index('gf_KillPlayer(lp_player, false);')
    assert 'gv_deathMethod[gv_visitation[lv_a]]' in function(source, 'gf_SKF_1_fayi')
    assert '== "W"' in function(source, 'gf_SKF_1_fayi')

    # Nine direct callers: every one must stop its own day-end continuation.
    count = 0
    for name in ('auto_gf_CheckVoteWin_TriggerFunc', 'auto_gf_Trial_TriggerFunc',
                 'auto_gf_TrialVoteResults_TriggerFunc', 'gt_Exeq_Func', 'gt_DaySequence_Func'):
        body = function(source, name)
        for call in re.finditer(r'\n\s*gf_EExecution\((\w+)\);', body):
            assert re.search(r'if \(\(gf_CJSpare\(' + call[1] + r'\) == true\)\) \{ return(?: true)?; \}\s*$', body[:call.start()]), name
            count += 1

    assert count == 9, count
    table = json.loads((ROOT / 'work/roles-list.json').read_text())
    assert sum(e['role'] == 38 for sec in table['sections'] if sec['category'] == 3 for e in sec['entries']) == 1
    assert 'c_bhSaveRoleMax = 38;' in source
    assert 'c_bhNeutralDrawMax = 31;' in source
    assert 'gv_bankRoleAchievements[lv_a][3][38]' not in source
    assert 'gv_roleNameInput[3][38] = "caijuezhe";' in source

    results = []
    for match in re.finditer(r'^void (gf_ET\w+)\s*\([^;{}]*\)\s*\{', source, re.M):
        body = function(source, match[1])
        candidates = [line.strip() for line in body.splitlines() if 'gf_CJWon(lv_a)' in line and 'if (' in line]
        assert len(candidates) == 1, match[1]
        expr = candidates[0][4:-3]
        results.append(f'bool winner{len(results)}(int lv_a) {{ int lv_ci=0; int lv_tx=0; int lv_shw=0; return {expr}; }}')

    assert len(results) == 25, len(results)
    results.append('void nativeDawnClock() { gv_dayNumber += 1; gv_isNight = false; gf_CJMorning(); }')
    return results


def harness(source: str) -> str:
    core = re.findall(r'^\w+ (gf_CJ\w+)\s*\([^;{}]*\)\s*\{', source, re.M)
    bodies = [function(source, name) for name in core + list(HELPERS)]
    bodies += integration(source)
    code = '\n\n'.join(bodies)
    code = re.sub(r'\b(\w+)((?:\[\d+\])+)( +)(\w+)', r'\1\3\4\2', code)
    code = re.sub(r'\bnull\b', '0', code)
    # Galaxy locals default to their type's zero; C++ locals do not.
    code = re.sub(r'(?m)^( +(?:int|bool|text|string|fixed|playergroup|unit|unitgroup|point|sound|trigger) +\w+(?:\[\d+\])*)\s*;', r'\1{};', code)
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*) +(\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        if name.startswith(('gv_', 'auto_gf_', 'gt_')):
            declarations[name] = f'{kind} {name}{dims};'

    used = set(re.findall(r'\b(?:gv_|auto_gf_|gt_)\w+', re.sub(r'//[^\n]*|"(?:\\.|[^"\\])*"', '', code)))
    used -= set(core + list(HELPERS))
    extra = {'gv_immune', 'gv_healing', 'gv_bankRoleAchievements', 'gv_gkRole'}
    used |= extra
    assert not used - declarations.keys(), ('globals', used - declarations.keys())
    globals_text = '\n'.join(declarations[n] for n in sorted(used))
    resets = '\n'.join(f'    clearValue({n});' for n in sorted(used))
    headers = '\n'.join(body.split('{', 1)[0] + ';' for body in bodies)
    defined = set(re.findall(r'^(?:void|bool|int|text|fixed) (\w+)\s*\(', code, re.M))
    calls = set(re.findall(r'\b(\w+)\s*\(', re.sub(r'//[^\n]*|"(?:\\.|[^"\\])*"', '', code)))
    explicit = '''if while for return Color SoundLink StringExternal StringToText TextWithColor
DialogControlSetVisible libNtve_gf_SetDialogItemColor
PlayerGroupAll PlayerGroupSingle PlayerGroupHasPlayer PlayerGroupNextPlayer PlayerGroupRemove
PlayerGroupCount PlayerGroupAdd TriggerCreate TriggerExecute Wait RandomInt RandomFixed AbsI ModI
IntToText UnitGetType TimerGetRemaining gf_BHNotify gf_CBSystemMessage gf_GKIs gf_GKLabel
 gf_GKNotice gf_GKSubstitute gf_GSIs gf_CheckEnd gf_EGWon gf_JSWon gf_LMCat gf_LMRole
 gf_GKWon gf_XRGangShare gf_BHHistRoleWritten gf_BHHistRecordRole gf_CJChangingRole
 gf_BHWillAny gf_BHWillMore gf_BHDeathName gf_NightTransition IntToFixed CeilingI libNtve_gf_ConvertPlayerColorToColor
 gf_JSCommitExecute gf_TXSparedToday gf_JSSparedToday gf_TXSpare GameTimeOfDayGetLength GameTimeOfDaySetLength TimerPause SoundLastPlayed
'''.split()
    allowed = set(NOOP + ZERO + explicit)
    assert not calls - defined - allowed, ('new dependency requires explicit stub', calls - defined - allowed)
    noop = '\n'.join(f'template<class... A> void {n}(A...) {{}}' for n in NOOP if n in calls and n not in defined)
    getters = '\n'.join(f'template<class... A> int {n}(A...) {{ return 0; }}' for n in ZERO if n in calls and n not in defined)
    constants = '\n'.join(f'const int {n} = '+('32;' if n in {'c_targetFilterDead', 'c_targetFilterHidden'} else '0;') for n in sorted(set(re.findall(r'\b(?:c_|ge_)\w+', code))))
    strings = load_strings()
    rows = ',\n'.join('{' + json.dumps(k) + ',' + json.dumps(v, ensure_ascii=False) + '}' for k,v in strings.items())
    winner_calls = '\n'.join(f'        assert(winner{i}(1)); assert(!winner{i}(2));' for i in range(25))
    return r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <functional>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>
using std::string;
using text=string; using fixed=double;
using playergroup=int; using color=int; using soundlink=int; using trigger=int;
using doodad=int; using unit=int; using unitgroup=int; using point=int; using actor=int; using region=int;
using timer=int; using dialog=int; using texttag=int; using sound=int;
struct Message { string value; int recipient; };
std::vector<Message> messages;
std::map<string,string> strings={
''' + rows + r'''
};
std::map<std::pair<int,int>,bool> visible;
std::map<std::pair<int,int>,color> buttonColors;
struct TintEvent { string value; color tint; };
std::vector<TintEvent> tintEvents;
const color roleBlue=0x8FAADC, nightRed=0xFF0000, cancelGray=0x808080;
std::map<string,int> triggerNames;
std::map<int,string> triggerIds;
std::vector<int> queue;
int resumes=0, checks=0, substitutes=0, forcedSubstitute=0, animationDeath=0;
bool timerPaused=false, expireOnWait=false; double timeLength=120.0;
std::function<void()> onNextWait;
int Color(double r,double g,double b) {
    return ((int)std::lround(r*255.0/100.0)<<16) | ((int)std::lround(g*255.0/100.0)<<8) | (int)std::lround(b*255.0/100.0);
}
int SoundLink(string,int) {return 0;}
text StringExternal(string key) {assert(strings.count(key)); return strings.at(key);}
text StringToText(string value) {return value;}
text paint(string value,color tint) {
    char hex[7]; std::snprintf(hex,sizeof(hex),"%06X",tint&0xFFFFFF);
    return string("<c val=\"")+hex+"\">"+value+"</c>";
}
text TextWithColor(string value,color tint) {
    tintEvents.push_back({value,tint});
    return paint(value,tint);
}
void DialogControlSetVisible(int control,int group,bool show) {
    for(int p=1;p<=15;++p) if(group&(1<<p)) visible[{control,p}]=show;
}
void libNtve_gf_SetDialogItemColor(int control,color tint,int group) {
    for(int p=1;p<=15;++p) if(group&(1<<p)) buttonColors[{control,p}]=tint;
}
text IntToText(int value) {return std::to_string(value);}
int libNtve_gf_ConvertPlayerColorToColor(int n) {return n;}
int PlayerGroupAll() {return 65534;}
int PlayerGroupSingle(int p) {assert(p>=1 && p<=15); return 1<<p;}
bool PlayerGroupHasPlayer(int g,int p) {assert(p>=1 && p<=15); return (g&(1<<p))!=0;}
int PlayerGroupNextPlayer(int g,int prev) {for(int p=std::max(1,prev+1);p<=15;++p) if(g&(1<<p)) return p; return -1;}
int PlayerGroupCount(int g) {return __builtin_popcount((unsigned)g);}
void PlayerGroupRemove(int &g,int p) {g &= ~PlayerGroupSingle(p);}
void PlayerGroupAdd(int &g,int p) {g |= PlayerGroupSingle(p);}
int RandomInt(int lo,int hi) {assert(lo<=hi); return lo;}
double RandomFixed(double lo,double hi) {assert(lo<=hi); return lo;}
int AbsI(int n) {return std::abs(n);}
int ModI(int x,int y) {return x%y;}
string UnitGetType(int) {return "";}
int TimerGetRemaining(int) {return 60;}
double GameTimeOfDayGetLength() {return timeLength;}
void GameTimeOfDaySetLength(double n) {timeLength=n;}
void TimerPause(int,bool pause) {timerPaused=pause;}
int SoundLastPlayed() {return 0;}
bool gf_JSCommitExecute(int) {return true;}
bool gf_TXSparedToday(int) {return false;}
bool gf_JSSparedToday(int) {return false;}
bool gf_TXSpare(int) {return true;}
int TriggerCreate(string name) {if(!triggerNames.count(name)) {int id=triggerNames.size()+1;triggerNames[name]=id;triggerIds[id]=name;}return triggerNames.at(name);}
void TriggerExecute(int t,bool,bool);
void Wait(double,int);
int gf_CheckEnd() {++checks; return 0;}
bool gf_GKIs(int);
bool gf_GSIs(int) {return false;}
bool gf_EGWon(int) {return false;}
bool gf_JSWon(int) {return false;}
bool gf_XRGangShare(int,int) {return false;}
bool gf_GKWon(int,int) {return false;}
int gf_LMCat(int);
int gf_LMRole(int);
int gf_GKSubstitute(int p) {++substitutes; return forcedSubstitute?forcedSubstitute:p;}
int CeilingI(double n) {return (int)std::ceil(n);}
double IntToFixed(int n) {return n;}
bool gf_BHWillAny(int) {return false;}
template<class... A> bool gf_BHWillMore(A...) {return false;}
string gf_BHDeathName(int p) {return std::to_string(p);}
string gf_GKLabel(int p) {return std::to_string(p);}
void gf_GKNotice(int p,string message) {messages.push_back({message,p});}
template<class... A> void gf_CBSystemMessage(string message,int p,A...) {messages.push_back({message,p});}
void gf_BHNotify(string message,int p,int) {messages.push_back({message,p});}
template<class T> void clearValue(T &v) {v=T{};}
template<class T,size_t N> void clearValue(T (&v)[N]) {for(auto &x:v) clearValue(x);}
''' + globals_text + '\n' + constants + '\n' + headers + '\n' + noop + '\n' + getters + r'''
bool gf_GKIs(int p) {return gv_gkRole[p]>=33 || (gv_roles[p][1]==3 && gv_roles[p][0]>=33 && gv_roles[p][0]<=37);}
int gf_LMCat(int p) {return gv_roles[p][1];}
int gf_LMRole(int p) {return gv_roles[p][0];}
void gf_BHHistRoleWritten(int,int,int) {}
void gf_BHHistRecordRole(int,int,int) {}
void Wait(double,int) {
    if(onNextWait) {auto check=std::move(onNextWait);onNextWait={};check();}
    if(expireOnWait) {expireOnWait=false;gv_dayOver=true;}
    // Optional concurrent non-execution death during a long execution animation.
    if(animationDeath) {int p=animationDeath; animationDeath=0; gf_KillPlayer(p,false);}
}
void TriggerExecute(int t,bool,bool) {
    const auto name=triggerIds.at(t);
    if(name=="auto_gf_KillPlayer_TriggerFunc") auto_gf_KillPlayer_TriggerFunc(false,true);
    else {assert(name=="auto_gf_EExecution_TriggerFunc" || name=="gf_LSEndDayThread"); queue.push_back(t);}
}
void drain() {
    int limit=0;
    while(!queue.empty()) {
        assert(++limit<30); int t=queue.front();queue.erase(queue.begin());
        if(triggerIds.at(t)=="auto_gf_EExecution_TriggerFunc") auto_gf_EExecution_TriggerFunc(false,true);
        else if(triggerIds.at(t)=="gf_LSEndDayThread") gf_LSEndDayThread(false,true);
        else assert(false);
    }
}
void gf_NightTransition();
''' + code + r'''
void gf_NightTransition() {gf_CJDusk();gv_isNight=true;gv_dayOver=false;for(int p=1;p<=15;++p) {gv_action[p][0]=0;gv_action[p][1]=0;gf_CJNightSetup(p);}}
void reset() {
''' + resets + r'''
    messages.clear();queue.clear();triggerNames.clear();triggerIds.clear();visible.clear();buttonColors.clear();tintEvents.clear();
    resumes=checks=substitutes=forcedSubstitute=animationDeath=0;timerPaused=expireOnWait=false;timeLength=120;onNextWait={};
    gv_alivePlayers=gv_currentPlayers=gv_players=PlayerGroupAll();gv_dayNumber=1;gv_isNight=true;
    for(int p=1;p<=15;++p) {
        gv_roles[p][1]=1;gv_roles[p][0]=1;gv_name[p]="镇民"+std::to_string(p);gv_number[p]=std::to_string(p+6);
        gv_actionDialogItem[p][5]=p+100;gv_actionDialogItem[p][6]=p+200;gv_playerSpot[p]=p;
    }
    gv_roles[1][1]=3;gv_roles[1][0]=38;gf_CJStart();gf_CJNightSetup(1);messages.clear();
}
void pick(int p=1,int a=2,int b=3) {gf_CJPick(p,a,0);gf_CJPick(p,b,1);}
void resolve() {gf_CJPrepareVisits();gf_CJResolveNight();gf_CJRevengeNight();}
void morning() {nativeDawnClock();}
void nextNight() {gf_NightTransition();}
void execute(int p) {gf_EExecution(p);drain();}
void prepareRound() {pick();resolve();morning();}
int cases=0;
string key(string suffix) {return strings.at("Param/Value/"+suffix);}
void assertCrimes(int p,std::initializer_list<int> expected) {
    for(int i=0;i<=10;++i) {
        bool wanted=std::find(expected.begin(),expected.end(),i)!=expected.end();
        if(gv_e78AAFE7BDAAE4BA8BE5AE9E[p][i]!=wanted) std::cerr<<"case="<<cases<<" crime="<<i<<" expected="<<wanted<<"\n";
        assert(gv_e78AAFE7BDAAE4BA8BE5AE9E[p][i]==wanted);
    }
}
bool button(int target,int slot,int owner=1) {return visible.at({gv_actionDialogItem[target][5+slot],owner});}
color buttonColor(int target,int slot,int owner=1) {return buttonColors.at({gv_actionDialogItem[target][5+slot],owner});}
void assertBroadcast(const std::vector<string>& lines,color tint=roleBlue) {
    int recipients=0;
    for(int p=1;p<=15;++p) {
        std::vector<string> received;
        for(auto&m:messages) if(m.recipient==p) received.push_back(m.value);
        if(!PlayerGroupHasPlayer(gv_currentPlayers,p)) {assert(received.empty());continue;}
        ++recipients;assert(received.size()==lines.size());
        for(size_t i=0;i<lines.size();++i) {
            assert(received[i]==paint(lines[i],tint));
            assert(received[i].find("<n/>")==string::npos && received[i].find('\n')==string::npos);
        }
    }
    assert(messages.size()==recipients*lines.size());
}
std::vector<string> dawnLines(int first,int second=0) {
    string names=key("CJDAWN1")+gf_EGName(first);
    if(second) names+=key("CJAND")+gf_EGName(second)+key("CJDAWN2");
    else names+=key("CJDAWNONE");
    return {names,key(second?"CJDAWNREQ":"CJDAWNONEREQ"),key(second?"CJDAWNFAIL":"CJDAWNONEFAIL")};
}
void assertCount(int n) {if(gv_cjScore[1]!=n)std::cerr<<"case="<<cases<<" score="<<gv_cjScore[1]<<" expected="<<n<<" day="<<gv_dayNumber<<" night="<<gv_isNight<<"\n";assert(gv_cjScore[1]==n);}
int main() {
    reset();assert(gv_immuneChance[1]==1);gf_CJStart();gf_CJNightSetup(1);assert(gv_immuneChance[1]==1);++cases;

    // A completed real two-target ability records only trial manipulation.
    reset();pick();assertCrimes(1,{});gf_CJPrepareVisits();assertCrimes(1,{});gf_CJResolveNight();assertCrimes(1,{10});gf_CJResolveNight();assertCrimes(1,{10});++cases;
    for(int selection=0;selection<3;++selection) {
        reset();if(selection==1)gf_CJPick(1,2,0);if(selection==2)gf_CJPick(1,3,1);
        resolve();assertCrimes(1,{});assert(gv_cjPendingNight[1]==0);++cases;
    }
    for(int block=0;block<3;++block) {
        reset();pick();if(block==0)gv_roleblocked[1]=2;if(block==1)gv_jailed[1]=2;if(block==2)gv_veteraned[1]=true;
        resolve();assertCrimes(1,{});assert(gv_cjPendingNight[1]==0);++cases;
    }
    reset();pick();gf_CJPrepareVisits();gf_BHVisitNone(1);gf_CJResolveNight();assertCrimes(1,{});++cases;

    // Opening broadcasts are two separate complete rows for every current player,
    // including dead spectators, and exclude disconnected recipients.
    reset();PlayerGroupRemove(gv_currentPlayers,15);PlayerGroupRemove(gv_alivePlayers,14);
    gv_cjInitialized[1]=false;messages.clear();tintEvents.clear();gf_CJStart();
    assertBroadcast({key("CJINTRO1")+gf_EGName(1)+key("CJINTRO2"),key("CJINTRO3")});
    assert(std::count_if(tintEvents.begin(),tintEvents.end(),[](auto&e){return e.tint==roleBlue;})==28);++cases;
    reset();pick();resolve();PlayerGroupRemove(gv_currentPlayers,15);messages.clear();morning();assertBroadcast(dawnLines(2,3));++cases;
    reset();pick();resolve();gf_KillPlayer(3,false);messages.clear();morning();assertBroadcast(dawnLines(2));++cases;

    // Default buttons exclude self; all other candidates remain blue and usable.
    reset();assert(!button(1,0) && !button(1,1));
    for(int target=2;target<=15;++target) for(int slot=0;slot<=1;++slot) {assert(button(target,slot));assert(buttonColor(target,slot)==roleBlue);}++cases;
    reset();gf_CJPick(1,2,0);assert(button(1,0) && !button(1,1));assert(buttonColor(1,0)==cancelGray);
    assert(!button(2,0) && !button(2,1));assert(button(3,0) && button(3,1));++cases;
    reset();pick();assert(button(1,0) && button(1,1));assert(buttonColor(1,0)==cancelGray && buttonColor(1,1)==cancelGray);
    for(int target: {2,3}) for(int slot=0;slot<=1;++slot) assert(!button(target,slot));
    assert(button(4,0) && button(4,1));gf_CJPick(1,3,0);assert(gv_action[1][0]==2 && gv_action[1][1]==3);++cases;
    for(int cancel=0;cancel<=1;++cancel) {
        reset();pick();gf_CJPick(1,1,cancel);assert(gv_action[1][cancel]==0);
        int restored=cancel==0?2:3,other=cancel==0?3:2;
        assert(button(restored,0) && button(restored,1));assert(!button(other,0) && !button(other,1));
        assert(!button(1,cancel) && button(1,1-cancel));assert(buttonColor(1,1-cancel)==cancelGray);
        gf_CJPick(1,4,cancel);assert(gv_action[1][cancel]==4 && gv_action[1][1-cancel]==other);
        gf_CJPick(1,1,0);gf_CJPick(1,1,1);assert(!button(1,0) && !button(1,1));
        for(int target: {2,3,4}) assert(button(target,0) && button(target,1));++cases;
    }
    reset();pick();gf_CJPick(1,4,0);assert(button(2,0) && button(2,1));assert(!button(3,0) && !button(3,1));assert(!button(4,0) && !button(4,1));++cases;
    reset();prepareRound();execute(2);assert(gv_cjMode[1]==0);
    for(int target=1;target<=15;++target) for(int slot=0;slot<=1;++slot) assert(!button(target,slot));++cases;
    reset();prepareRound();nextNight();assert(gv_cjMode[1]==2);
    for(int target=1;target<=15;++target) assert(!button(target,1));
    assert(!button(1,0) && !button(2,0) && !button(3,0) && button(4,0));
    gf_CJPick(1,4,0);assert(button(1,0) && buttonColor(1,0)==cancelGray);assert(!button(4,0));
    gf_CJPick(1,5,1);assert(gv_action[1][1]==0);gf_CJPick(1,1,0);assert(!button(1,0) && button(4,0));++cases;

    // Murder appears only after the native death removal, never at selection,
    // attempted attack, an early callback with attribution, or an invalid redirect.
    reset();prepareRound();nextNight();gv_bhNightKiller[4]=1;gf_CJOnDeath(4);assertCrimes(1,{10});++cases;
    reset();prepareRound();nextNight();gf_CJPick(1,4,0);gv_nightSequence=true;messages.clear();
    onNextWait=[](){assertCrimes(1,{10});assert(PlayerGroupHasPlayer(gv_alivePlayers,4));};
    resolve();assert(!onNextWait);assertCrimes(1,{1,10});assert(!PlayerGroupHasPlayer(gv_alivePlayers,4));
    assert(gv_deathText[4]==key("CJDEATH") && gv_deathText[4].find("FFFFFF")!=string::npos);
    assert(gv_deathText[4].find("FF0000")==string::npos && gv_deathText[4].find("破门声")==string::npos);
    std::vector<Message> attackMessages=messages;messages.clear();
    for(auto&m:attackMessages) if(m.value==paint(key("CJNIGHT"),nightRed)) messages.push_back(m);
    assertBroadcast({key("CJNIGHT")},nightRed);assert(messages.size()==15);
    assert(std::none_of(attackMessages.begin(),attackMessages.end(),[](auto&m){return m.value==paint(key("CJNIGHT"),roleBlue);}));
    assert(std::any_of(attackMessages.begin(),attackMessages.end(),[](auto&m){return m.recipient==4 && m.value==paint(key("CJVICTIM"),roleBlue);}));++cases;
    reset();prepareRound();nextNight();resolve();assertCrimes(1,{10});assert(PlayerGroupHasPlayer(gv_alivePlayers,4));++cases;
    for(int target: {0,1,2,3,15}) {
        reset();prepareRound();nextNight();if(target==15)PlayerGroupRemove(gv_currentPlayers,15);
        gf_CJAttack(1,target);assertCrimes(1,{10});++cases;
    }
    reset();prepareRound();nextNight();gv_guarded[4]=5;gf_BHVisit(5,4);gf_CJPick(1,4,0);gv_nightSequence=true;
    onNextWait=[](){assertCrimes(1,{10});assert(PlayerGroupHasPlayer(gv_alivePlayers,5));};
    resolve();assert(!onNextWait);assert(PlayerGroupHasPlayer(gv_alivePlayers,4));assert(!PlayerGroupHasPlayer(gv_alivePlayers,5));
    assert(gv_bhNightKiller[5]==1);assertCrimes(1,{1,10});++cases;

    reset();prepareRound();assert(gv_dayNumber==2 && gv_cjListDay[1]==2 && gv_cjRestNight[1]==2);assert(gv_cjList[1][0]==2 && gv_cjList[1][1]==3);
    execute(2);assertCount(1);assert(gv_cjSatisfied[1]);nextNight();assert(gv_cjMode[1]==0);resolve();morning();nextNight();assert(gv_dayNumber==3 && gv_cjMode[1]==1);++cases;
    // No selection/incomplete selection: no announcement, no resting round.
    for(int incomplete=0;incomplete<2;++incomplete) {reset();if(incomplete)gf_CJPick(1,2,0);resolve();morning();assert(!gv_cjListDay[1]);nextNight();assert(gv_cjMode[1]==1);++cases;}
    // Actual night deaths, then the real native dawn increment. Empty list retries.
    for(int survivors=0;survivors<=2;++survivors) {
        reset();pick();resolve();if(survivors<2)gf_KillPlayer(3,false);if(survivors<1)gf_KillPlayer(2,false);messages.clear();morning();
        if(survivors==0) {assert(gv_cjListDay[1]==0 && messages.empty());nextNight();assert(gv_cjMode[1]==1);}
        else {assert(gv_cjListDay[1]==2 && gv_cjList[1][0]==2);assert(gv_cjList[1][1]==(survivors==2?3:0));assertBroadcast(dawnLines(2,survivors==2?3:0));}
        ++cases;
    }
    // Per-day tokens: night deaths/admin kill/disconnect never count; duplicate callback inert.
    for(int cause=0;cause<3;++cause) {reset();prepareRound();if(cause==0) {gv_isNight=true;gf_KillPlayer(2,false);}if(cause==1)gf_KillPlayer(2,false);if(cause==2){PlayerGroupRemove(gv_currentPlayers,2);gf_KillPlayer(2,false);}assertCount(0);++cases;}
    reset();prepareRound();execute(2);gf_CJOnDeath(2);assertCount(1);execute(2);assertCount(1);++cases;
    // Same target revived and actually executed again is a new occurrence.
    reset();prepareRound();gv_marshalled=true;gv_executionLimit=3;execute(2);PlayerGroupAdd(gv_alivePlayers,2);execute(2);assertCount(2);assert(gf_CJWon(1));nextNight();assert(!PlayerGroupHasPlayer(gv_alivePlayers,1));assert(gv_roles[1][0]==38);assert(PlayerGroupHasPlayer(gv_alivePlayers,4));++cases;
    // Repeated names across real list -> dawn -> execution -> rest -> list cycles.
    reset();prepareRound();execute(2);assertCount(1);assert(gv_isNight && gv_dayNumber==2 && gv_cjMode[1]==0);
    resolve();morning();nextNight();assert(gv_dayNumber==3 && gv_cjMode[1]==1);PlayerGroupAdd(gv_alivePlayers,2);gf_CJPick(1,2,0);gf_CJPick(1,4,1);
    resolve();morning();assert(gv_dayNumber==4 && gv_cjListDay[1]==4 && gv_cjList[1][0]==2);execute(2);assertCount(2);assert(gf_CJWon(1));assert(!PlayerGroupHasPlayer(gv_alivePlayers,1));++cases;
    // No timeout itself counts; early execution during animation from another source is not execution.
    reset();prepareRound();animationDeath=2;execute(2);assertCount(0);++cases;
    reset();prepareRound();gf_CJDusk();assertCount(0);nextNight();assert(gv_cjMode[1]==2);++cases;
    // Real lawyer protection: consuming it records lawyer crime, never adjudicator score.
    reset();prepareRound();gv_lsTarget[4]=2;gv_lsDay[4]=gv_dayNumber;execute(2);assertCount(0);assert(PlayerGroupHasPlayer(gv_alivePlayers,2));assert(gv_lsUsed[4]);++cases;
    // Substitute actual death, not the requested defendant.
    reset();prepareRound();forcedSubstitute=4;execute(2);assertCount(0);assert(!PlayerGroupHasPlayer(gv_alivePlayers,4));assert(PlayerGroupHasPlayer(gv_alivePlayers,2));++cases;
    reset();prepareRound();forcedSubstitute=2;execute(4);assertCount(1);assert(!PlayerGroupHasPlayer(gv_alivePlayers,2));++cases;
    // CJ immunity before lawyer/substitution; day expiry queues independent native day-end.
    reset();prepareRound();gv_trialOn=true;gv_onTrial=1;execute(1);assert(PlayerGroupHasPlayer(gv_alivePlayers,1));assert(!gv_trialOn && gv_onTrial==0);assert(!gv_isNight);assert(substitutes==0);++cases;
    reset();prepareRound();gv_dayOver=true;execute(1);assert(gv_isNight);assert(PlayerGroupHasPlayer(gv_alivePlayers,1));++cases;
    // Actual Marshal vote resolution refuses CJ before quota/list writes under both pause modes.
    for(bool pauses: {false,true}) {
        reset();prepareRound();gv_voteOn=true;gv_marshalled=true;gv_trialPausesDay=pauses;gv_votesNeeded=8;gv_voteCount[1]=9;gv_executionLimit=3;
        auto_gf_CheckVoteWin_TriggerFunc(false,true);assert(gv_executionCount==0 && gv_executionList[0]==0);assert(!timerPaused && timeLength==120);assert(!gv_isNight);++cases;
    }
    // End-of-day can happen inside the real return-to-podium animation.
    reset();prepareRound();gv_trialOn=true;gv_onTrial=1;gv_unit[1]=1;gv_e59F8BE59CB0[1][1]=true;expireOnWait=true;execute(1);assert(gv_isNight && !timerPaused);++cases;
    // Chosen protection is recognized by actual Marshal gate, not a fake death model.
    reset();prepareRound();gv_roles[2][1]=3;gv_roles[2][0]=32;gv_txBlessDay[2]=gv_dayNumber;gv_voteOn=true;gv_marshalled=true;gv_votesNeeded=8;gv_voteCount[2]=9;gv_executionLimit=3;
    auto_gf_CheckVoteWin_TriggerFunc(false,true);drain();assert(PlayerGroupHasPlayer(gv_alivePlayers,2));assertCount(0);++cases;
    // Final redirected destination forbids self, previous two names, dead and disconnected.
    for(int target: {0,1,2,3,15}) {reset();prepareRound();nextNight();if(target==15)PlayerGroupRemove(gv_currentPlayers,15);gv_action[1][0]=4;gf_CJPrepareVisits();gf_BHVisit(1,target);gf_CJRevengeNight();assert(PlayerGroupHasPlayer(gv_alivePlayers,4));assertCount(0);assert(gv_cjMode[1]==3);++cases;}
    // Morning omits a dead name, but revival does not erase last night's selection.
    reset();pick();resolve();gf_KillPlayer(3,false);morning();nextNight();PlayerGroupAdd(gv_alivePlayers,3);gv_diedAtNight[3]=false;assert(!gf_CJSelectable(1,3));assert(!gf_CJSelectable(1,2));++cases;
    // Older names are not permanently blacklisted once a newer pair was actually selected.
    reset();prepareRound();nextNight();resolve();morning();nextNight();gf_CJPick(1,4,0);gf_CJPick(1,5,1);resolve();morning();nextNight();assert(gf_CJSelectable(1,2) && gf_CJSelectable(1,3));assert(!gf_CJSelectable(1,4) && !gf_CJSelectable(1,5));++cases;
    // Roleblock/jail stop either phase. A failed list can retry the next night.
    for(int mode=1;mode<=2;++mode) for(int block=0;block<3;++block) {
        reset();if(mode==2){prepareRound();nextNight();gf_CJPick(1,4,0);}else pick();
        if(block==0)gv_roleblocked[1]=2;if(block==1)gv_jailed[1]=2;if(block==2)gv_veteraned[1]=true;
        resolve();assert(PlayerGroupHasPlayer(gv_alivePlayers,4));if(mode==1){morning();nextNight();assert(gv_cjMode[1]==1 || gv_jailed[1]);}++cases;
    }
    // Actual bus-final secondary remap and duplicate removal, no independent swap engine.
    reset();pick();gf_CJPrepareVisits();gv_switched[3]=4;gf_CJRedirectSecond(1);assert(gv_visitation[1]==2 && gv_visitation2[1]==4);gf_CJResolveNight();morning();assert(gv_cjList[1][1]==4);++cases;
    reset();pick();gf_CJPrepareVisits();gf_BHVisit(1,3);gf_CJRedirectSecond(1);assert(gv_visitation2[1]==0);gf_CJResolveNight();morning();assert(gv_cjList[1][0]==3 && gv_cjList[1][1]==0);++cases;
    // Revenge bypasses every independent mix of night invulnerability, consumable shields/healing.
    for(int defenses=0;defenses<8;++defenses) {
        reset();prepareRound();nextNight();gv_immune[4][0]=defenses&1;gv_immuneChance[4]=(defenses&2)?3:0;gv_healing[4]=(defenses&4)?2:0;
        int shield=gv_immuneChance[4],heal=gv_healing[4];gf_CJPick(1,4,0);resolve();assert(!PlayerGroupHasPlayer(gv_alivePlayers,4));assert(gv_immuneChance[4]==shield && gv_healing[4]==heal);assert(gv_bhNightKiller[4]==1);assertCount(0);assert(gv_deathMethod[4].find('W')!=string::npos);assert(gv_e78AAFE7BDAAE4BA8BE5AE9E[1][1]);++cases;
    }
    // Real native bodyguard mutual combat: guard takes CJ's bypass, CJ receives normal counterkill.
    for(int defenses=0;defenses<8;++defenses) {
        reset();prepareRound();nextNight();gv_guarded[4]=5;gf_BHVisit(5,4);gv_immune[5][0]=defenses&1;gv_immuneChance[5]=(defenses&2)?2:0;gv_healing[5]=(defenses&4)?2:0;
        int shield=gv_immuneChance[5],heal=gv_healing[5];gf_CJPick(1,4,0);resolve();assert(PlayerGroupHasPlayer(gv_alivePlayers,4));assert(!PlayerGroupHasPlayer(gv_alivePlayers,5));assert(!PlayerGroupHasPlayer(gv_alivePlayers,1));assert(gv_immuneChance[5]==shield && gv_healing[5]==heal);assert(gv_visitation[1]==4);++cases;
    }
    // Owner night death suppresses announcement and all pending operations, but keeps visits.
    reset();pick();resolve();gf_KillPlayer(1,false);assert(gv_visitation[1]==2 && gv_visitation2[1]==3);messages.clear();morning();assert(messages.empty());assert(!gv_cjPendingNight[1]);++cases;
    // Conversion invokes real identity write, clears transient state/score/remaining own shield.
    reset();prepareRound();execute(2);gf_GKSetRoleField(1,0,8);assert(!gv_cjListDay[1] && !gv_cjScore[1] && gv_immuneChance[1]==0);assert(gv_visitation[1]==0);++cases;
    // Every terminal winner function shares the locked flag, including after conversion.
    for(int role: {1,38,33}) {
        reset();gv_cjWon[1]=true;gf_GKSetRoleField(1,0,role);gv_roles[1][1]=3;gv_gkRole[1]=(role==33?33:0);
        gv_roles[2][1]=3;gv_roles[2][0]=38;
''' + winner_calls + r'''
        ++cases;
    }
    // Invalid and conflicting clicks never create array access/duplicate/self lists.
    reset();for(int p: {0,16,-1}) {gf_CJPick(p,2,0);assert(!gf_CJIs(p));}gf_CJPick(1,2,0);gf_CJPick(1,2,1);assert(!gv_action[1][1]);gf_CJPick(1,1,0);assert(!gv_action[1][0]);++cases;
    std::cout<<"PASS: "<<cases<<" production adjudicator scenarios; UBSan/bounds; 25 ET winner expressions\n";
}
'''


def main() -> None:
    source = SCRIPT.read_text()
    code = harness(source)
    with tempfile.TemporaryDirectory(prefix='bh-adjudicator-') as tmp:
        cpp, exe = Path(tmp) / 'test.cpp', Path(tmp) / 'test'
        cpp.write_text(code)
        subprocess.run(['g++','-std=c++17','-O0','-g','-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True,timeout=30)


if __name__ == '__main__':
    main()
