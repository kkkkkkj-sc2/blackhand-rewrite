#!/usr/bin/env python3
"""Execute actual GS binding/selection/settlement source, with engine UI doubles.

Not an SC2 compiler or game-rendering test. No staging fragments are required.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from test_egun import function, mask, translate

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
NAMES = ('gf_GSIs', 'gf_GSActive', 'gf_GSPlayerLabel', 'gf_GSBind',
         'gf_GSSetShield', 'gf_GSSelectStrike', 'gf_SKN_3_gongshengti',
         'gf_SKA_3_gongshengti', 'gf_SKW_3_gongshengti', 'gt_GSStrike_Func',
         'gf_GSShareWin', 'gf_GSActions', 'gf_BHRoleFitsKind', 'gf_BHHistFaction',
         'gf_OSRandomizeMatrix')

PREFIX = r'''
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
using string=std::string;
using text=std::string;
using fixed=double;
fixed gv_finalWeights[9][36];
int gv_rolesArray[16];
int gv_townMax=35, gv_mafiaTriadMax=21;
bool alive[16], current[16], gv_won[16], gv_diedAtNight[16];
int gv_alivePlayers=1, gv_currentPlayers=2;
int gv_gsHost[16], gv_gsStrike[16], gv_gsResult[16];
bool gv_gsUsed[16], gv_gsShield[16], gv_gsSacrificed[16];
int gv_roles[16][2], gv_bhFeignRole[16], gv_jailed[16], gv_action[16][2], gv_visitation[16];
int gv_playerColor[16], gv_variableOptions[16][2], gv_bankGeneralIntegers[16][48];
string gv_number[16], gv_name[16], gv_variant;
text gv_roleNameArray[9][36];
bool gv_gameOver=false, gv_isNight=true, gv_nightProcessingPhase=false, gv_nightSequence=true;
int gv_dayNumber=1, eventPlayer=1, gv_endButtonItem=1, gv_unit[16], gv_nameTag[16], gv_hat[16][2];
int refreshes=0, joins=0, pictures=0, rosterRefreshes=0;
int gv_actionDialogItem[16][7], gv_switchButtonItem=999;
bool visible[16][160], switchEnabled[16], gv_roleOptions[9][36][12];
bool gf_BHListHas(int,int) { return false; }
string eventMessage;
std::vector<int> notified;
int SoundLink(string,int) { return 0; }
int Color(double,double,double) { return 0; }
text StringToText(string s) { return s; }
string IntToString(int n) { return std::to_string(n); }
text StringExternal(string s) { return s; }
text TextWithColor(text s,int) { return s; }
int libNtve_gf_ConvertPlayerColorToColor(int) { return 0; }
bool PlayerGroupHasPlayer(int group,int p) { assert(p>=1&&p<=15); return group==1?alive[p]:current[p]; }
int PlayerGroupSingle(int p) { assert(p>=1&&p<=15); return p; }
int PlayerGroupAll() { return 99; }
void gf_BHVisitSelf(int p) { gv_visitation[p]=p; }
void gf_BHNotify(text,int p,int) { assert(p>=1&&p<=15); notified.push_back(p); }
void DialogControlSetEnabled(int control,int player,bool enabled) {
    assert(control==999); switchEnabled[player]=enabled;
}
void DialogControlSetVisible(int control,int player,bool show) {
    assert(control>=0 && control<160); visible[player][control]=show;
}
void libNtve_gf_SetDialogItemTooltip(int,text,int) {}
void libNtve_gf_SetDialogItemColor(int,int,int) {}
void DialogControlSetSize(int,int,int,int) {}
void libNtve_gf_SetDialogItemImage(int,string,int) {}
void libNtve_gf_SetDialogItemImage2(int,string,int) {}
void gf_RefreshRoleBox() { ++rosterRefreshes; }
void gf_GSRefreshChat() { ++refreshes; }
void gf_GSChatJoin(int) { ++joins; }
int EventPlayer() { return eventPlayer; }
string EventChatMessage(bool) { return eventMessage; }
string StringCase(string s,bool upper) {
    for(char& c:s) c=upper?std::toupper((unsigned char)c):std::tolower((unsigned char)c);
    return s;
}
int StringLength(string s) { return s.size(); }
string StringSub(string s,int first,int last) {
    if(first<1||last<first||first>int(s.size())) return "";
    return s.substr(first-1,last-first+1);
}
string StringWord(string s,int word) {
    assert(word==1); auto begin=s.find_first_not_of(' ');
    if(begin==string::npos) return "";
    auto end=s.find(' ',begin); return s.substr(begin,end-begin);
}
void SoundPlay(int,int,double,double) {}
void gf_FlashScreen(int,int,double,double) {}
void libNtve_gf_SetDialogItemText(int,text,int) {}
void libNtve_gf_ShowHideUnit(int,bool) {}
void TextTagShow(int,int,bool) {}
void ActorSend(int,string) {}
void gf_WinScreen(string,int) { ++pictures; }
'''

CASES = r'''
void reset(int sym=1,int host=2,int pool=1) {
    gv_gameOver=false; gv_isNight=true; gv_nightProcessingPhase=false;
    gv_nightSequence=true; gv_dayNumber=1; eventPlayer=sym;
    refreshes=joins=pictures=rosterRefreshes=0; notified.clear(); eventMessage="";
    for(int p=0;p<=15;++p) {
        alive[p]=current[p]=(p>0); gv_won[p]=gv_diedAtNight[p]=false;
        gv_gsHost[p]=gv_gsStrike[p]=gv_gsResult[p]=0;
        gv_gsUsed[p]=gv_gsShield[p]=gv_gsSacrificed[p]=false;
        gv_roles[p][0]=gv_roles[p][1]=1;
        gv_bhFeignRole[p]=gv_jailed[p]=gv_action[p][0]=gv_action[p][1]=gv_visitation[p]=0;
        gv_number[p]=std::to_string(16-p); gv_name[p]="player"; gv_playerColor[p]=0;
        for(int j=0;j<48;++j) gv_bankGeneralIntegers[p][j]=0;
        for(int j=0;j<160;++j) visible[p][j]=false;
        for(int j=0;j<7;++j) gv_actionDialogItem[p][j]=p*10+j;
        switchEnabled[p]=false;
    }
    for(int poolId=0;poolId<9;++poolId) for(int role=0;role<36;++role) for(int bit=0;bit<12;++bit) gv_roleOptions[poolId][role][bit]=false;
    gv_roles[sym][0]=29; gv_roles[sym][1]=3; gv_roles[host][1]=pool;
}
int main() {
    int checks=0;
    // Immediate first-night binding, immutable identity and immediate conversation.
    for(int sym=1;sym<=15;++sym) for(int host=1;host<=15;++host) if(sym!=host) {
        for(int pool: {1,2,3,5}) {
            reset(sym,host,pool); gf_GSBind(sym,host);
            assert(gv_gsHost[sym]==host && gv_visitation[sym]==sym);
            assert(joins==1 && refreshes==1 && rosterRefreshes==1 && switchEnabled[sym]==(pool!=3));
            gf_GSBind(sym,host); assert(joins==1);
            gf_GSBind(sym,sym); assert(gv_gsHost[sym]==host);
            ++checks;
        }
    }
    for(int mode=0;mode<12;++mode) {
        reset();
        if(mode==0) gv_isNight=false;
        if(mode==1) gv_nightProcessingPhase=true;
        if(mode==2) gv_dayNumber=2;
        if(mode==3) alive[1]=false;
        if(mode==4) alive[2]=false;
        if(mode==5) gv_jailed[1]=3;
        if(mode==6) gv_bhFeignRole[1]=1;
        if(mode==7) gv_bhFeignRole[2]=1;
        if(mode==8) gv_gameOver=true;
        if(mode==9) { gv_roles[2][1]=3; gv_roles[2][0]=29; }
        if(mode==10) { gv_roles[1][0]=1; }
        gf_GSBind(1,mode==11?16:2); assert(!gv_gsHost[1] && !joins); ++checks;
    }
    // Action buttons expose legal first-night hosts only, then disappear on binding.
    reset(); gv_roles[3][1]=3; gv_roles[3][0]=29; alive[4]=false;
    gf_GSActions(1);
    assert(!visible[1][15] && visible[1][25] && !visible[1][35] && !visible[1][45]);
    assert(!switchEnabled[1]); gf_GSBind(1,2);
    for(int target=1;target<=15;++target) assert(!visible[1][target*10+5]);
    assert(switchEnabled[1]); gv_gsUsed[1]=true; gf_GSActions(1); assert(!switchEnabled[1]);
    // Default weight is 0.5; only eligible benign random kinds can draw the role.
    for(int kind=1;kind<=22;++kind) {
        reset(); assert(gf_BHRoleFitsKind(kind,3,29)==(kind==1 || kind==14 || kind==19));
    }
    // Exercise the complete production weight-to-role mapper across the 0.5-wide GS interval.
    for(int role=29;role<36;++role) gv_finalWeights[3][role]=0.5;
    for(int kind=1;kind<=22;++kind) for(double roll: {-0.001,0.0,0.25,0.499999,0.5}) {
        reset(); gv_rolesArray[1]=kind;
        gf_OSRandomizeMatrix(3,1,roll);
        bool eligible=(kind==1 || kind==14 || kind==19) && roll>=0.0 && roll<0.5;
        assert((gv_roles[3][1]==3 && gv_roles[3][0]==29)==eligible); ++checks;
    }

    reset(); gv_roleOptions[4][1][3]=true; gv_roleOptions[4][19][2]=true;
    assert(!gf_BHRoleFitsKind(1,3,29) && !gf_BHRoleFitsKind(19,3,29) && gf_BHRoleFitsKind(14,3,29));
    assert(gf_BHHistFaction(3,29)==6);
    // Shield arming is separate from spending; no host action/own role switch collision.
    for(int pool: {1,2,3,5}) {
        reset(1,2,pool); gv_gsHost[1]=2; gv_action[2][0]=7; gv_action[2][1]=8;
        gf_GSSetShield(1,true); assert(gv_gsShield[1]==(pool!=3));
        assert(!gv_gsUsed[1] && gv_action[2][0]==7 && gv_action[2][1]==8);
        gf_GSSetShield(1,false); assert(!gv_gsShield[1]);
        gv_gsUsed[1]=true; gf_GSSetShield(1,true); assert(!gv_gsShield[1]); ++checks;
    }
    // Host seat numbers differ from player IDs; extra strike cannot replace host action.
    reset(1,2,3); gv_gsHost[1]=2; gv_action[2][0]=6; gv_action[2][1]=7;
    gf_GSSelectStrike(2,gv_number[5]); assert(gv_gsStrike[1]==5 && gv_action[1][0]==5);
    assert(gv_action[2][0]==6 && gv_action[2][1]==7 && !gv_gsUsed[1]);
    gf_GSSelectStrike(2,""); assert(!gv_gsStrike[1] && !gv_action[1][0]);
    for(int mode=0;mode<9;++mode) {
        reset(1,2,3); gv_gsHost[1]=2;
        if(mode==0) gv_isNight=false;
        if(mode==1) gv_nightProcessingPhase=true;
        if(mode==2) gv_jailed[1]=3;
        if(mode==3) gv_jailed[2]=3;
        if(mode==4) gv_gsUsed[1]=true;
        if(mode==5) alive[1]=false;
        if(mode==6) alive[2]=false;
        if(mode==7) alive[5]=false;
        if(mode==8) gv_roles[2][1]=1;
        gf_GSSelectStrike(2,gv_number[5]); assert(!gv_gsStrike[1]); ++checks;
    }
    reset(1,2,3); gv_gsHost[1]=2; eventPlayer=2;
    eventMessage="-symb "+gv_number[5]; assert(gt_GSStrike_Func(true,true)); assert(gv_gsStrike[1]==5);
    eventMessage="-symb"; assert(gt_GSStrike_Func(true,true)); assert(!gv_gsStrike[1]);
    eventMessage="-symbiotic"; assert(!gt_GSStrike_Func(true,true));
    eventMessage="-symb non-seat"; assert(gt_GSStrike_Func(true,true)); assert(!gv_gsStrike[1]);
    // New-night setup never replenishes Used or forgets the relationship/result.
    reset(); gv_gsHost[1]=2; gv_gsUsed[1]=true; gv_gsShield[1]=true; gv_gsStrike[1]=5;
    gv_gsResult[1]=2; gv_dayNumber=2; gf_SKN_3_gongshengti(1);
    assert(gv_gsHost[1]==2 && gv_gsUsed[1] && gv_gsResult[1]==2);
    assert(!gv_gsShield[1] && !gv_gsStrike[1]);
    // Full player-order, alive/dead and win/lose cross-product, idempotent statistics.
    for(int sym=1;sym<=15;++sym) for(int host=1;host<=15;++host) if(sym!=host) {
        for(int dead=0;dead<2;++dead) for(int won=0;won<2;++won) {
            reset(sym,host); gv_gsHost[sym]=host; alive[sym]=!dead; gv_won[host]=won;
            gf_GSShareWin("WinTown.dds"); gf_GSShareWin("");
            assert(gv_won[sym]==bool(won)); assert(gv_gsResult[sym]==(won?2:1));
            assert(gv_bankGeneralIntegers[sym][6]==won && gv_bankGeneralIntegers[sym][7]==1-won);
            assert(pictures==1); ++checks;
        }
    }
    // Late DQ sharing upgrades one loss into one win, never two total games.
    reset(); gv_gsHost[1]=2; gf_GSShareWin("WinTown.dds");
    gv_won[2]=true; gf_GSShareWin(""); gf_GSShareWin("");
    assert(gv_won[1] && gv_bankGeneralIntegers[1][6]==1 && gv_bankGeneralIntegers[1][7]==0);
    for(int host: {-1,0,16,99}) {
        reset(); gv_gsHost[1]=host; gf_GSShareWin("");
        assert(!gv_won[1] && gv_bankGeneralIntegers[1][7]==1); ++checks;
    }
    std::cout<<"PASS "<<checks<<" GS binding/command/shield/settlement scenarios\n";
}
'''


def main():
    source = SCRIPT.read_text()
    values = dict(line.split('=', 1) for line in (ROOT / 'work/blackhand/strings-gs.txt').read_text().splitlines()
                  if line.startswith('Param/Value/'))
    assert values['Param/Value/GSBOX6'] == '与你的宿主一同胜利，即使你已死亡'
    assert values['Param/Value/GSCRIME'] == '谋杀'
    for weight in ('gv_roleWeights[3][29]', 'gv_bankSaveWeights[0][3][29]'):
        assert re.findall(re.escape(weight) + r'\s*=\s*([^;]+);', mask(source)) == ['0.5']

    bodies = [function(source, name) for name in NAMES]
    select = mask(function(source, 'gf_GSSelectStrike'))
    assert not re.search(r'gv_action\[lp_host\][^;]*=', select)
    assert not re.search(r'gv_gs(?:Used|Host)\[[^][]]+\]\s*=(?!=)', select)
    assert 'gv_nightSequence' not in mask(function(source, 'gf_GSBind'))
    assert 'gv_nightProcessingPhase' in mask(function(source, 'gf_GSBind'))

    terminals = []
    for match in re.finditer(r'^void (gf_ET\w+) \(\) \{', source, re.M):
        body = function(source, match[1])
        if 'gf_EGWon(lv_a)' not in body:
            continue

        assert body.count('gf_GSShareWin(') >= 1
        assert body.index('if ((gf_GSIs(lv_a) == true))') < body.index('gf_EGWon(lv_a)')
        assert body.index('gf_GSShareWin(') > body.rindex('gf_WinScreen(')
        terminals.append(match[1])

    assert len(terminals) == 25, terminals
    assert function(source, 'gf_DQShareWin').count('gf_GSShareWin("");') == 1
    declarations = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    code = PREFIX + declarations + '\n' + translate('\n\n'.join(bodies)) + CASES
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'C++ compiler required'
    with tempfile.TemporaryDirectory(prefix='bh-gs-ui-') as tmp:
        source_path = Path(tmp) / 'test.cpp'
        executable = Path(tmp) / 'test'
        source_path.write_text(code)
        subprocess.run([compiler, '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(source_path), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)

    print('PASS 25 terminal hooks, post-DQ sharing and immutable host action state')


if __name__ == '__main__':
    main()
