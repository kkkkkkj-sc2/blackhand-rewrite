#!/usr/bin/env python3
"""Execute production Spy abilities/chat routing with explicit engine/UI doubles.

Actual Galaxy helpers, both complete CBAddChat bodies, CBWhisper and all three
Spy callbacks are translated only for array declarations and run under UBSan.
Large SequencePrep/After functions are NOT emulated: their exact enclosing if
conditions are extracted and executed around the actual callbacks. Every one
of the twelve presentation/log guards is also executed independently.

Doubles: player groups, text/color primitives, chat UI storage, event-log sink,
channel assignment/permission sinks, sound, magnification, deterministic RNG,
and CBSystemMessage's rendering sink. No Spy/faction/GS routing helper is a
double. This is not an SC2 compiler, renderer, or native chat-delivery test.

Whisper audit: the legacy option is disabled by default and not allowed. Its
only runtime read is card text; CBWhisper sends content ONLY to its endpoints.
The suite verifies this existing behavior with the option both on and off;
it does not invent the unimplemented native-Spy whisper-eavesdropping ability.
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile

from test_egun import function, mask, translate

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
CHAT_NAMES = ('gf_CBAddChat', 'gf_CBAddChatE8AF95E8AF95E79C8BE883BDE4B88DE883BDE794A8')
CALLBACKS = ('gf_SKP_1_jiandie', 'gf_SKP_1_jiandie_2', 'gf_SKF_1_jiandie')
NAMES = (
    'gf_BHConverted', 'gf_BHSpyActive', 'gf_BHFaction',
    'gf_BHRefreshFactionChat', 'gf_GSIs', 'gf_GSActive', 'gf_GSPlayerLabel',
    'gf_GSChatReady', 'gf_GSChatPeer', 'gf_GSChatRoot', 'gf_GSGRPartner',
    'gf_GSChatXR', 'gf_XRNeutralFatal', 'gf_FZChatHidden',
    'gf_GSEffectiveChannel', 'gf_GSChatColor', 'gf_GSChatHidden',
    'gf_GSChatRecipient', *CHAT_NAMES, 'gf_CBWhisper', *CALLBACKS,
)


def end_pair(live, opening, left='(', right=')'):
    depth, cursor = 1, opening + 1
    while depth:
        assert cursor < len(live), 'unbalanced source block'
        depth += (live[cursor] == left) - (live[cursor] == right)
        cursor += 1

    return cursor


def conditions(body):
    live = mask(body)
    for match in re.finditer(r'\bif\s*\(', live):
        opening = live.index('(', match.start())
        end = end_pair(live, opening)
        brace = end
        while live[brace].isspace():
            brace += 1

        assert live[brace] == '{', 'expected braced Galaxy if'
        yield opening, end, brace, end_pair(live, brace, '{', '}')


def source_guards(source):
    wrappers = []
    for name in CHAT_NAMES:
        body = function(source, name)
        guards = [body[start:end] for start, end, _, _ in conditions(body)
                  if 'gf_BHSpyActive' in body[start:end]]
        assert len(guards) == 6, (name, 'all six presentation/log paths', len(guards))
        assert not re.search(r'gv_roles\[lv_a\]\[0\]\s*==\s*8', mask(body))
        for guard in guards:
            index = len(wrappers)
            wrappers.append(f'bool displayGuard{index}(int lp_player,int lv_a) {{ return {guard}; }}')

    for owner, callback in zip(('gf_SequencePrep', 'gf_SequencePrep', 'gf_SequenceAfter'), CALLBACKS):
        body = function(source, owner)
        call = re.search(r'\b' + callback + r'\s*\(lv_a\);', mask(body))
        assert call and len(re.findall(r'\b' + callback + r'\s*\(', mask(body))) == 1
        guards = [body[start:end] for start, end, brace, finish in conditions(body)
                  if brace < call.start() < finish]
        assert any('gf_BHSpyActive' in guard for guard in guards), (owner, callback)
        predicate = ' && '.join(guards)
        wrappers.append(f'void routed_{callback}(int lv_a) {{ if ({predicate}) {callback}(lv_a); }}')
        print(f'EXECUTE {owner} -> {callback}: {predicate}', flush=True)

    whisper = mask(function(source, 'gf_CBWhisper'))
    assert not re.search(r'\b(?:gv_roles|gv_roleOptions|gf_BHSpyActive)\b', whisper), 'new whisper listener route needs actual coverage'
    endpoints = set(re.findall(r'PlayerGroupSingle\((\w+)\)', whisper))
    assert endpoints == {'lp_player', 'lp_recipient'}, ('whisper content endpoints', endpoints)
    option_reads = []
    headers = list(re.finditer(r'^(?:void|bool|int|text)\s+(\w+)\s*\([^;{}]*\)\s*\{', mask(source), re.M))
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(source)
        if re.search(r'gv_roleOptions\[1\]\[8\]\[3\]\s*==', mask(source[header.start():end])):
            option_reads.append(header[1])

    assert option_reads == ['gf_RTTownRoleText'], ('whisper switch runtime readers changed', option_reads)
    assert re.search(r'gv_roleOptions\[1\]\[8\]\[3\]\s*=\s*false;', source)
    assert re.search(r'gv_roleOptionAllowed\[1\]\[8\]\[3\]\s*=\s*false;', source)
    print('PASS whisper audit: disabled/not-allowed option; card-only read; sender/recipient-only content', flush=True)
    return '\n'.join(wrappers)


PREFIX = r'''
#include <algorithm>
#include <cassert>
#include <iostream>
#include <string>
#include <tuple>
#include <vector>
using string=std::string;
using text=string;
using color=int;
using playergroup=unsigned;
using soundlink=string;
using fixed=double;
#define null ""
const int ge_Magnify_Magnify=0, ge_Magnify_SuperMagnify=1;
const int ge_Clear_DoNotClear=0, ge_Allow_Allow=1;
int checks=0, randomCursor=0;
text uiText[16][64];
color uiColor[16][64];
bool uiShown[16][64], uiEnabled[16][64], allowed[16];
struct Log { text value; int player,equivalent; };
std::vector<Log> logs;
std::vector<std::pair<text,int>> messages;
void check(bool result) { ++checks; assert(result); }
template<class T> void clearValue(T& value) { value=T{}; }
template<class T,size_t N> void clearValue(T (&value)[N]) { for(auto& x:value) clearValue(x); }
playergroup PlayerGroupEmpty() { return 0; }
playergroup PlayerGroupSingle(int p) { assert(p>=1 && p<=15); return 1u<<p; }
bool PlayerGroupHasPlayer(playergroup group,int p) { assert(p>=1 && p<=15); return (group&(1u<<p))!=0; }
void PlayerGroupAdd(playergroup& group,int p) { group|=PlayerGroupSingle(p); }
int player(playergroup group) { for(int p=1;p<=15;++p) if(group==(1u<<p)) return p; assert(false); return 0; }
text StringExternal(string key) { return "{"+key+"}"; }
text StringToText(string value) { return value; }
text IntToText(int value) { return std::to_string(value); }
string IntToString(int value) { return std::to_string(value); }
text PlayerName(int p) { return "PLAYER"+std::to_string(p); }
color Color(double r,double g,double b) { return int(r*10000+g*100+b); }
color libNtve_gf_ConvertPlayerColorToColor(int value) { return value; }
text TextWithColor(text value,color c) { return "<c"+std::to_string(c)+">"+value+"</c>"; }
soundlink SoundLink(string value,int index) { assert(index==-1); return value; }
void SoundPlay(soundlink,playergroup,double,double) {}
int RandomInt(int low,int high) { assert(low==1 && high==15); return ++randomCursor%15+1; }
bool DialogControlIsVisible(int item,int p) { assert(item>=0 && item<64 && p>=1 && p<=15); return uiShown[p][item]; }
bool DialogControlIsEnabled(int item,int p) { assert(item>=0 && item<64 && p>=1 && p<=15); return uiEnabled[p][item]; }
text libNtve_gf_DialogItemText(int item,int p) { assert(item>=0 && item<64 && p>=1 && p<=15); return uiText[p][item]; }
color libNtve_gf_DialogItemColor(int item,int p) { assert(item>=0 && item<64 && p>=1 && p<=15); return uiColor[p][item]; }
void libNtve_gf_SetDialogItemText(int item,text value,playergroup group) { assert(item>=0 && item<64); uiText[player(group)][item]=value; }
void libNtve_gf_SetDialogItemColor(int item,color value,playergroup group) { assert(item>=0 && item<64); uiColor[player(group)][item]=value; }
void DialogControlSetEnabled(int item,playergroup group,bool value) { assert(item>=0 && item<64); uiEnabled[player(group)][item]=value; }
void DialogControlSetVisible(int item,playergroup group,bool value) { assert(item>=0 && item<64); uiShown[player(group)][item]=value; }
void gf_ELAddMessage(text value,int p,color,int equivalent,int) { logs.push_back({value,p,equivalent}); }
void gf_CBMagnifyText(int,int) {}
void gf_CBSystemMessage(text value,int p,int,int,soundlink,color) { assert(p>=1 && p<=15); messages.push_back({value,p}); }
'''


CASES = r'''
void role(int p,int pool,int id) { gv_roles[p][1]=pool; gv_roles[p][0]=id; }
void helper_cases() {
    for(int p: {-100,-1,0,16,17,100}) check(!gf_BHSpyActive(p));
    for(int p: {1,15}) for(int pool: {1,2,3,5}) for(int id: {1,8,33}) for(int faction: {0,2,5}) {
        reset(); role(p,pool,id); gv_bhFaction[p]=faction;
        check(gf_BHSpyActive(p)==(pool==1 && id==8 && faction==0));
        check(gv_roles[p][1]==pool && gv_roles[p][0]==id && gv_bhFaction[p]==faction);
    }
    std::cout<<"PASS helper: legal seats, non-Spy professions/pools, native and both converts\n";
}
void chat_route_cases() {
    for(int faction: {0,2,5}) for(int channel: {0,1,2,3,4}) for(int gs: {0,1}) {
        reset(); role(2,1,8); gv_bhFaction[2]=faction;
        role(1,2,1); gv_channel[1]=channel;
        int speaker=1;
        if(gs) { role(3,3,29); gv_gsHost[3]=1; speaker=3; }
        bool publicMembership=channel==0 && !gs;
        bool spyListening=!faction && (channel==1 || channel==4);
        check(gf_GSChatRecipient(speaker,2)==(publicMembership || spyListening));
    }
    // Ordinary same-channel membership is independent of every Spy-only guard.
    for(int faction: {2,5}) for(int gs: {0,1}) for(int muted: {0,1}) {
        reset(); role(2,1,8); gv_bhFaction[2]=faction;
        gf_BHRefreshFactionChat();
        int channel=faction==2?1:4;
        check(gv_channel[2]==channel && allowed[2] && !gf_BHSpyActive(2));
        role(1,faction,1); gv_channel[1]=channel;
        role(4,faction==2?5:2,1); gv_channel[4]=channel==1?4:1;
        int speaker=1;
        if(gs) { role(3,3,29); gv_gsHost[3]=1; speaker=3; }
        gv_mute[2][speaker]=muted;
        check(gf_GSChatRecipient(speaker,2)==!muted);
        check(!gf_GSChatRecipient(4,2));
        check(gf_GSChatRecipient(2,1));
    }
    // Legacy non-GS eavesdropping ignores mute, but retains alive/jail checks.
    for(int faction: {0,2,5}) for(int gs: {0,1}) for(int state=0;state<8;++state) {
        reset(); role(2,1,8); gv_bhFaction[2]=faction; gv_channel[1]=4;
        int speaker=1;
        if(gs) { role(3,3,29); gv_gsHost[3]=1; speaker=3; }
        if(state==1) gv_jailed[2]=1;
        if(state==2) gv_alivePlayers&=~(1u<<2);
        if(state==3) gv_mute[2][speaker]=true;
        if(state==4) gv_silenced[2][0]=true;
        if(state==5) gv_jailing[2]=1;
        if(state==6) gv_privateChannel[2]=7;
        if(state==7) gv_currentPlayers&=~(1u<<2);
        bool originalGuard=gs?state==0:(state==0 || state>=3);
        check(gf_GSChatRecipient(speaker,2)==(!faction && originalGuard));
    }
    std::cout<<"PASS routing: native hears channels1/4; converts retain own-team chat only; original jail/alive/mute/GS guards\n";
}
void display_cases() {
    using Chat=void(*)(int,string,text,bool);
    for(Chat chat: {gf_CBAddChat,gf_CBAddChatE8AF95E8AF95E79C8BE883BDE4B88DE883BDE794A8})
    for(int faction: {0,2,5}) for(int channel: {1,4}) for(bool filled: {false,true}) for(bool op: {false,true}) {
        reset(); role(2,1,8); gv_bhFaction[2]=faction;
        gv_channel[1]=channel; gv_chatOp[1]=op;
        if(faction) gf_BHRefreshFactionChat();
        gv_chatPrivilege[1]=true;
        for(int p=1;p<=15;++p) for(int item=0;item<64;++item) uiShown[p][item]=filled;
        chat(1,"BODY_TOKEN","TITLE",true);
        std::vector<Log> received;
        for(auto& log:logs) if(log.player==2) received.push_back(log);
        bool shouldReceive=!faction || channel==(faction==2?1:4);
        check(received.size()==size_t(shouldReceive));
        if(shouldReceive) {
            auto& log=received[0];
            check((log.value.find(gv_name[1])!=string::npos)==bool(faction));
            check(log.equivalent==gv_eventLogChatEquivalent[faction?1:2]);
            if(chat==gf_CBAddChat || !faction) check(log.value.find("BODY_TOKEN")!=string::npos);
        }
    }
    // Both copies must use ordinary formatting in other membership channels.
    for(Chat chat: {gf_CBAddChat,gf_CBAddChatE8AF95E8AF95E79C8BE883BDE4B88DE883BDE794A8}) for(int channel: {0,2,3}) {
        reset(); role(2,1,8); gv_channel[1]=gv_channel[2]=channel; gv_chatPrivilege[1]=true;
        chat(1,"BODY_TOKEN","TITLE",true);
        int found=0;
        for(auto& log:logs) if(log.player==2) { ++found; check(log.value.find(gv_name[1])!=string::npos); check(log.equivalent==gv_eventLogChatEquivalent[1]); }
        check(found==1);
    }
    std::cout<<"PASS complete chat bodies: both copies, filled/new rows, highlighted/plain, no anonymizing converted teammates or channels0/2/3\n";
}
void callback_cases() {
    using Callback=void(*)(int);
    for(Callback callback: {gf_SKP_1_jiandie,gf_SKP_1_jiandie_2,gf_SKF_1_jiandie}) for(int faction: {0,2,5}) {
        reset(); role(2,1,8); gv_bhFaction[2]=faction;
        role(3,2,1); role(4,5,1); gv_visitation[3]=7; gv_visitation[4]=8;
        callback(2);
        check(messages.size()==size_t(faction?0:callback==gf_SKF_1_jiandie?2:1));
        if(faction) check(!gv_seqAfterWait[2]);
        for(auto& msg:messages) check(msg.second==2);
    }
    for(Callback callback: {gf_SKP_1_jiandie,gf_SKP_1_jiandie_2,gf_SKF_1_jiandie}) for(int p: {-1,0,16,99}) {
        reset(); callback(p); check(messages.empty());
    }
    for(int faction: {0,2,5}) for(int callback=0;callback<3;++callback) for(int guard=0;guard<5;++guard) {
        reset(); role(2,1,8); gv_bhFaction[2]=faction;
        role(3,2,1); role(4,5,1); gv_visitation[3]=7; gv_visitation[4]=8;
        gv_roleOptions[1][8][1]=gv_roleOptions[1][8][2]=true;
        if(guard==1) gv_alivePlayers&=~(1u<<2);
        if(guard==2) gv_roleOptions[1][8][1]=gv_roleOptions[1][8][2]=false;
        if(guard==3) gv_diedAtNight[2]=true;
        if(guard==4) gv_jailed[2]=1; // old intelligence callbacks had no jail gate
        if(callback==0) routed_gf_SKP_1_jiandie(2);
        if(callback==1) routed_gf_SKP_1_jiandie_2(2);
        if(callback==2) routed_gf_SKF_1_jiandie(2);
        bool expected=!faction && guard!=1 && guard!=2 && !(callback==2 && guard==3);
        check(messages.size()==size_t(expected?(callback==2?2:1):0));
    }
    for(int pool: {1,2,3,5}) for(Callback callback: {gf_SKP_1_jiandie,gf_SKP_1_jiandie_2,gf_SKF_1_jiandie}) {
        reset(); role(2,pool,pool==1?7:8); callback(2); check(messages.empty());
    }
    for(int callback=0;callback<2;++callback) for(int missing: {0,1}) {
        reset(); role(2,1,8); gv_roleOptions[1][8][2]=true;
        if(callback==0) {
            if(missing==0) gv_mafiaTarget=0; else gv_mafiaHitman=0;
            routed_gf_SKP_1_jiandie(2);
        } else {
            if(missing==0) gv_triadTarget=0; else gv_triadHitman=0;
            routed_gf_SKP_1_jiandie_2(2);
        }
        check(messages.empty());
    }
    for(int pool: {2,5}) for(int visitMode=0;visitMode<4;++visitMode) {
        reset(); role(2,1,8); role(3,pool,1);
        gv_visitation[3]=visitMode==0?0:visitMode==1?3:7;
        gv_immune[3][2]=visitMode==3;
        gf_SKF_1_jiandie(2);
        bool expected=visitMode==1 || visitMode==2;
        check(messages.size()==size_t(expected));
        check(gv_seqAfterWait[2]);
        if(expected) {
            string key=pool==2?(visitMode==1?"6506AF91":"7EE95F8C"):(visitMode==1?"11663752":"FEE302F4");
            check(messages[0].first.find(key)!=string::npos);
            if(visitMode==2) check(messages[0].first.find(gv_name[7])!=string::npos);
        }
    }
    std::cout<<"PASS actual callbacks and extracted Sequence guards: both target notices, visits, options/death/alive and unchanged jail semantics\n";
}
void whisper_cases() {
    for(int faction: {0,2,5}) for(bool option: {false,true}) for(bool filled: {false,true}) for(bool muted: {false,true}) {
        reset(); role(2,1,8); gv_bhFaction[2]=faction; role(3,1,8);
        gv_roleOptions[1][8][3]=option; gv_mute[2][1]=muted;
        for(int p=1;p<=15;++p) for(int item=0;item<64;++item) uiShown[p][item]=filled;
        gf_CBWhisper(1,2,"PRIVATE_BODY",gv_name[1]);
        int sender=0,recipient=0;
        for(auto& log:logs) {
            check(log.player==1 || log.player==2);
            check(log.value.find("PRIVATE_BODY")!=string::npos);
            sender+=log.player==1; recipient+=log.player==2;
        }
        check(sender==1 && recipient==!muted);
        check(uiText[3][filled?2:40].empty());
    }
    std::cout<<"PASS whispers: both switch values, native/converted direct recipients, mute preserved; no third-party content listener\n";
}
int main() {
    helper_cases(); chat_route_cases(); display_cases(); callback_cases(); whisper_cases();
    display_guard_cases();
    std::cout<<"PASS "<<checks<<" Spy conversion assertions (UBSan/bounds)\n";
}
'''


def harness(source):
    guards = source_guards(source)
    bodies = [function(source, name) for name in NAMES]
    code = '\n\n'.join(bodies)
    required = set(re.findall(r'\bgv_\w+', mask(code + guards)))
    declarations = {}
    for match in re.finditer(r'^(\w+)((?:\[\d+\])*)\s+(gv_\w+)\s*(?:=[^;]*)?;', source, re.M):
        kind, dims, name = match.groups()
        declarations[name] = f'{kind} {name}{dims};'

    assert not required - declarations.keys(), ('missing globals', required - declarations.keys())
    globals_text = '\n'.join(declarations[name] for name in sorted(required))
    resets = '\n'.join(f'    clearValue({name});' for name in sorted(required))
    prototypes = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    display_tests = '\n'.join(f'        check(displayGuard{i}(1,2)==(!faction && (channel==1 || channel==4)));' for i in range(12))
    display_cases = '''
void display_guard_cases() {
    for(int faction: {0,2,5}) for(int channel=0;channel<=4;++channel) {
        reset(); role(2,1,8); gv_bhFaction[2]=faction; gv_channel[1]=channel;
''' + display_tests + '''
    }
    std::cout<<"PASS all twelve independent production presentation/log guards\\n";
}
'''
    setup = '''
void gf_CBAssignUnassignChatChannel(int p,int channel,int clear) {
    assert(p>=1 && p<=15 && clear==ge_Clear_DoNotClear); gv_channel[p]=channel;
}
void gf_CBAllowDisallowChatting(int p,int mode) { assert(mode==ge_Allow_Allow); allowed[p]=true; }
void reset() {
''' + resets + '''
    clearValue(uiText); clearValue(uiColor); clearValue(uiShown); clearValue(uiEnabled); clearValue(allowed);
    logs.clear(); messages.clear(); randomCursor=0;
    gv_isNight=gv_bhFactionChatOpen=true;
    for(int p=1;p<=15;++p) {
        gv_roles[p][0]=gv_roles[p][1]=1;
        PlayerGroupAdd(gv_alivePlayers,p); PlayerGroupAdd(gv_currentPlayers,p);
        gv_name[p]="<NAME"+std::to_string(p)+">"; gv_number[p]=std::to_string(p);
        gv_playerColor[p]=p; gv_eventLogChatEquivalent[p]=100+p;
    }
    for(int row=0;row<=20;++row) { gv_chatBoxItem[row][0]=row*2; gv_chatBoxItem[row][1]=row*2+1; }
    gv_mafiaTarget=7; gv_mafiaHitman=3; gv_triadTarget=8; gv_triadHitman=4;
}
'''
    # Target/hitman globals are referenced only by the extracted Sequence guards.
    needed = {'gv_mafiaTarget', 'gv_mafiaHitman', 'gv_triadTarget', 'gv_triadHitman'} - required
    globals_text += '\n' + '\n'.join(declarations[name] for name in sorted(needed))
    return translate(PREFIX + '\n' + globals_text + '\n' + setup + '\n' + prototypes
                     + '\n' + code + '\n' + guards + '\nvoid role(int,int,int);\n'
                     + display_cases + '\n' + CASES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    source = args.script.read_text()
    code = harness(source)
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'C++ compiler required'
    for name in NAMES:
        body = function(source, name)
        first = source.count('\n', 0, source.index(body)) + 1
        print(f'{name}: lines {first}..{first + body.count(chr(10))}', flush=True)

    with tempfile.TemporaryDirectory(prefix='spy-conversion-') as temporary:
        cpp, binary = Path(temporary) / 'spy.cpp', Path(temporary) / 'spy'
        cpp.write_text(code)
        subprocess.run([compiler, '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
