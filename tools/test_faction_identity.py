#!/usr/bin/env python3
"""Execute actual faction UI/name/channel/ally helpers with explicit UI doubles.

Only tools/test_egun.py's extraction/array-syntax translation and the allies
harness's engine PREFIX are reused. No copied membership or identity algorithm
is the oracle: fixtures specify observable rosters, color, and channel results.
The unconverted reference is a complete historical production RefreshRoleBox.
FZBind and the actual FZ render/click functions are executed too. Once Baron
integration is present, --require-baron enforces the FZ22 extension and actual
Town A/B events; BRDraw/BRClick are explicit NEW integration boundary doubles,
whose internal recruitment/permission logic belongs to test_baron_leaders.
This is a C++/UBSan regression, not an SC2 compiler or rendering test.
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile

from test_egun import function, mask, translate
from test_faction_conversion import with_guoke_dependencies, missing_actual_globals
from test_gongshengti_allies import PREFIX as ALLY_PREFIX

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'
NAMES = (
    'gf_BHConverted', 'gf_BHFaction', 'gf_BHRoleName', 'gf_BHDeathName',
    'gf_BHFactionCard', 'gf_BHRefreshFactionChat', 'gf_GSChatReady',
    'gf_BHConvertFaction', 'gf_RTRoleCard',
    'gf_DQHidden', 'gf_DQSeenPool', 'gf_DQSeenRole', 'gf_DQSeenName',
    'gf_FZFaceName', 'gf_GSIs', 'gf_XRNeutralFatal', 'gf_GSBaseAlly',
    'gf_GSAllyFor', 'gf_GSRefreshAllies', 'gf_RefreshRoleBox',
    'gf_GSActive', 'gf_GSChatPeer', 'gf_GSChatRoot', 'gf_GSGRPartner',
    'gf_GSChatXR', 'gf_GSEffectiveChannel', 'gf_FZChatHidden',
    'gf_GSChatHidden', 'gf_GSChatRecipient', 'gf_FZClick', 'gf_RAFengziActions',
    'gf_FZBind', 'gf_BHSpyActive', 'gf_BHSeenFaction',
    'gf_BHInvestigatedRoleName', 'gf_BHPrivateRoleName',
)
BARON_NAMES = ('gf_BRFake', 'gt_ASActionButtonATown_Func', 'gt_ASActionButtonBTown_Func')


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True,
                          text=True, capture_output=True).stdout


def reference():
    path = SCRIPT.relative_to(ROOT).as_posix()
    revision = 'HEAD'
    source = git('show', f'{revision}:{path}')
    if re.search(r'^bool gf_BHConverted\s*\([^;]*\)\s*\{', mask(source), re.M):
        changes = git('log', '--reverse', '--format=%H', '-S',
                      'bool gf_BHConverted', 'HEAD', '--', path).splitlines()
        assert changes, 'cannot locate pre-faction production reference'
        revision = changes[0] + '^'
        source = git('show', f'{revision}:{path}')

    roster = function(source, 'gf_RefreshRoleBox')
    assert 'gf_BHFaction' not in mask(roster), 'reference must predate this feature'
    print(f'Unconverted roster reference: git {revision}', flush=True)
    return source, roster.replace('gf_RefreshRoleBox', 'gf_RefreshRoleBoxBaseline', 1)


def check_wiring(source, old):
    night = mask(function(source, 'auto_gf_NightTransition_TriggerFunc'))
    assert re.search(r'gf_FZRefreshActions\s*\(\s*\)\s*;\s*'
                     r'gf_BHRefreshFactionChat\s*\(\s*\)\s*;\s*'
                     r'gf_GSRefreshChat\s*\(\s*\)\s*;', night), 'night hook order'
    assert re.search(r'gv_bhFactionChatOpen\s*=\s*true\s*;\s*'
                     r'gf_FZRefreshActions\s*\(\s*\)\s*;', night), 'open before FZ/faction/GS refresh'
    close = re.search(r'gv_bhFactionChatOpen\s*=\s*false\s*;', night)
    clear = re.search(r'gf_CBAssignUnassignChatChannel\s*\(\s*auto1D25B969_var\s*,\s*0\s*,', night)
    disallow = re.search(r'gf_CBAllowDisallowChatting\s*\(\s*auto1D25B969_var\s*,\s*ge_Allow_Disallow\s*\)', night)
    late_wait = re.search(r'Wait\s*\(\s*2\.0\s*,\s*c_timeGame\s*\)', night[close.end():]) if close else None
    assert close and clear and disallow and late_wait, 'night close, lock, and late wait must remain present'
    assert close.start() < clear.start() < disallow.start() < close.end() + late_wait.start(), 'close gate before channel clear/Disallow AND the final wait'
    reset = mask(function(source, 'gf_BHFactionReset'))
    assert re.search(r'gv_bhFactionChatOpen\s*=\s*false\s*;', reset), 'reset must close faction chat'

    # Compare the real old death-context call sites by owning function, not
    # hardcoded line numbers (which move whenever another feature is added).
    old_headers = list(re.finditer(r'^(?:void|bool|int|text)\s+(\w+)\s*\([^;{}]*\)\s*\{', mask(old), re.M))
    death_owners = []
    for index, header in enumerate(old_headers):
        name = header[1]
        end = old_headers[index + 1].start() if index + 1 < len(old_headers) else len(old)
        body = old[header.start():end]
        if 'gf_DQSeenName' in body and ('gv_deadPlayerRole' in body or 'gv_graveyard' in body):
            death_owners.append(name)

    # The huge transition functions use localized graveyard control names;
    # identify their actual old presentation statements by graveyard markers.
    for name in ('auto_gf_DayTransition_TriggerFunc', 'auto_gf_CheckVoteWin_TriggerFunc', 'gt_DaySequence_Func'):
        try:
            body = function(old, name)
        except AssertionError:
            continue

        if 'gf_DQSeenName' in body:
            death_owners.append(name)

    death_owners = sorted(set(death_owners))
    assert len(death_owners) >= 3, 'night/ordinary execution/day-sequence death contexts must all be found'
    for name in death_owners:
        live = mask(function(source, name))
        assert 'gf_BHDeathName' in live, ('death context not wired', name)
        assert not re.search(r'\bgf_DQSeenName\s*\(', live), ('old uncolored death name remains', name)

    # Observer still sees profession-only names. Real-identity investigation is
    # the narrowly permitted exception; ordinary clues must remain unchanged.
    body = mask(function(source, 'gf_SKF_1_guanchazhe'))
    assert 'gf_DQSeenName' in body, 'observer must retain seen profession names'
    assert not re.search(r'\bgf_BH(?:Role|Death|InvestigatedRole)Name\s*\(', body), 'observer leaks alignment color'
    from test_faction_investigation import check_wiring as check_investigation_wiring
    check_investigation_wiring(source)

    card = mask(function(source, 'gf_RTRoleCard'))
    assert re.search(r'gf_BHFactionCard\s*\(\s*lp_player\s*\)\s*;\s*(?:gf_GKCard\(lp_player\);\s*)?\}', card), 'faction card override must precede only the passer card overlay'
    assert 'gf_BHConverted' in card, 'temporary FZ template must exclude actual converts'
    convert = mask(function(source, 'gf_BHConvertFaction'))
    assert re.search(r'if\s*\(\s*\(\s*gv_roles\[lp_player\]\[0\]\s*==\s*33\s*\)\s*\)\s*\{\s*'
                     r'gf_RTRoleCard\s*\(\s*lp_player\s*\)\s*;\s*\}\s*else\s*\{\s*'
                     r'gf_BHFactionCard\s*\(\s*lp_player\s*\)\s*;', convert), 'rebuild FZ true-profession card only; ordinary Town keeps original ability text'
    town = function(source, 'gf_RTTownRoleText')
    for slot, key in ((1, 'FENGBOX1'), (2, 'FENGBOX2'), (4, 'FENGBOX4')):
        assert re.search(r'gv_roleBoxText\[lv_a\]\[' + str(slot) + r'\]\s*=\s*StringExternal\("Param/Value/' + key + r'"\)', town), ('true FZ card text missing', slot, key)

    # Header labels are private per-player UI; do not replace nickname/seat color.
    owner_text = '\n'.join(mask(function(source, name)) for name in NAMES)
    assert not re.search(r'\bgv_(?:name|playerColor|number|playerSpot)\s*\[[^;\n]*\]\s*=(?!=)', owner_text), 'identity helpers must not recolor/rename players'
    assert source.count('gf_FZFaceName(lv_a)') >= 2, 'both own-card header paths must keep the presentation entry'
    print('PASS source wiring: night order, death contexts, identity-only investigation color, private card', flush=True)


def check_baron_wiring(source):
    render = mask(function(source, 'gf_RAFengziActions'))
    assert re.search(r'gf_GKSetRoleField\(lp_player,\s*0,\s*gv_fzRole\[lp_player\]\);\s*'
                     r'if\s*\(\(gv_fzRole\[lp_player\]\s*==\s*22\)\)\s*\{\s*'
                     r'gf_BRDraw\(lp_player\);', render), '22 draw must see temporary profession'
    assert 'gf_BRSetup' not in render, 'FZ must never receive real setup/immunity'
    click = mask(function(source, 'gf_FZClick'))
    assert re.search(r'gf_BRFake\(lv_source\)\s*==\s*true\)\s*&&\s*'
                     r'\(gv_ysClickSlot\s*==\s*1\)\)\s*\{\s*'
                     r'gf_BRClick\(lv_source,\s*lv_target,\s*true\);\s*return;', click), 'recruit path must return before fake attack'
    assert click.count('gf_BRClick(') == 1, 'one fake recruit boundary per click'
    for slot, name in ((5, 'gt_ASActionButtonATown_Func'), (6, 'gt_ASActionButtonBTown_Func')):
        event = mask(function(source, name))
        assert event.count('gf_FZClick(') == 1, ('exactly one FZ dispatch', name)
        assert re.search(r'gv_actionDialogItem\[lv_a\]\[' + str(slot) + r'\]\s*==\s*EventDialogControl\(\)', event)
        assert not re.search(r'gv_actionDialogItem\[lv_a\]\[' + str(11 - slot) + r'\]\s*==\s*EventDialogControl\(\)', event), 'A/B must never match the same control'
    print('PASS Baron/FZ wiring: temporary identity, no setup, B-only recruit and disjoint A/B controls', flush=True)


def prefix():
    code = ALLY_PREFIX
    for name in NAMES:
        if re.search(r'^(?:void|bool|int|text)\s+' + re.escape(name) + r'\s*\(', mask(code), re.M):
            code = code.replace(function(code, name), '')

    code = code.replace(function(code, 'DialogControlSetVisible'), r'''
void DialogControlSetVisible(int item,int p,bool show) {
    assert(p>=1 && p<=15);
    if(item>=100) { assert(item<=211); return; }
    assert(item>=0 && item<=6); visible[p][item]=show;
}
''')

    return code + r'''
#define null ""
int gv_bhFaction[16], gv_fzRole[16], gv_channel[16];
int gv_jailed[16], gv_jailing[16], gv_privateChannel[16];
bool gv_silenced[16][2], gv_dqRevealed[16];
bool gv_diedAtNight[16], gv_grPrivateChat[16], gv_crying[16], gv_mute[16][16];
int gv_grChild[16], gv_grParent[16];
bool gv_isNight, gv_gameOver, gv_nightProcessingPhase, gv_bhFactionChatOpen, gv_gameStarted;
bool allowed[16], active[16];
int gv_host=15, gv_action[16][2], roleRenders[16], gsRefreshes, fakeRenders, ysPicks;
int gv_variableOptions[16][3], gv_actionDialogItem[16][7], gv_playerSpot[16];
bool gv_immune[16][5];
struct ActionRender {
    string kind;
    int player,pool,role,option0,option1,option2,leaderPool,leaderRole;
};
std::vector<ActionRender> actionRenders, picks;
const int ge_Clear_DoNotClear=0, ge_Allow_Allow=1, c_playerStatusActive=1, c_anchorTopRight=0;
std::vector<std::pair<int,int>> channelWrites;
std::vector<std::pair<text,int>> messages;
int Color(double r,double g,double b) {
    return int(r*10000+g*100+b);
}
string IntToString(int n) { return std::to_string(n); }
void gf_CBAssignUnassignChatChannel(int p,int channel,int clear) {
    assert(p>=1 && p<=15 && clear==ge_Clear_DoNotClear);
    gv_channel[p]=channel; channelWrites.push_back({p,channel});
}
void gf_CBAllowDisallowChatting(int p,int mode) {
    assert(p>=1 && p<=15 && mode==ge_Allow_Allow); allowed[p]=true;
}
// Explicit external presentation double, not a faction or membership oracle.
text gf_RTMakeWinList(int pool,int role) {
    return "WINLIST("+std::to_string(pool)+","+std::to_string(role)+")";
}
string SoundLink(string name,int index) { assert(index==-1); return name; }
void gf_CBSystemMessage(text message,int player,int,int,string,int) {
    assert(player>=1 && player<=15); messages.push_back({message,player});
}
void gf_GSRefreshChat() { ++gsRefreshes; }
void gf_RTTownRoleText(int p) {
    ++roleRenders[p];
    // Explicit renderer double: encode which profession reached the real
    // dispatcher. No faction/name/setup/ability state is implemented here.
    for(int item: {1,2,4}) gv_roleBoxText[p][item]="TOWN_RENDER("+std::to_string(gv_roles[p][0])+","+std::to_string(item)+")";
}
void gf_RTMafiaRoleText(int) { assert(false && "Town convert must not render mafia profession"); }
void gf_RTTriadRoleText(int) { assert(false && "Town convert must not render triad profession"); }
void gf_RTNeutralRoleText(int) { assert(false && "Town convert must not render neutral profession"); }
int PlayerStatus(int p) { assert(p>=1 && p<=15); return active[p]?c_playerStatusActive:0; }
ActionRender actionSnapshot(string kind,int p) {
    int lead=gv_fzLeader[p];
    return {kind,p,gv_roles[p][1],gv_roles[p][0],
            gv_variableOptions[p][0],gv_variableOptions[p][1],gv_variableOptions[p][2],
            lead>=1 && lead<=15?gv_roles[lead][1]:0,
            lead>=1 && lead<=15?gv_roles[lead][0]:0};
}
// Renderer doubles record the real dispatcher's temporary identity and inherited
// options. They do not implement any target/faction selection algorithm.
void drawAction(string kind,int p) { ++fakeRenders; actionRenders.push_back(actionSnapshot(kind,p)); }
void gf_RANoActions(int p) { drawAction("none",p); }
void gf_YSButtons(int p) { drawAction("ysbuttons",p); gv_immune[p][0]=!gv_immune[p][0]; }
void gf_YSDraw(int p) { drawAction("ysdraw",p); gv_immune[p][0]=!gv_immune[p][0]; }
void gf_RABihuzheActions(int p) { drawAction("leader",p); }
void gf_RAGodfatherActions(int p) { drawAction("mafia",p); }
void gf_RADragonHeadActions(int p) { drawAction("triad",p); }
void DialogControlSetPosition(int item,int p,int anchor,int,int) {
    assert(item>=100 && item<=211 && p>=1 && p<=15 && anchor==c_anchorTopRight);
}
void gf_YSPick(int p,int) { ++ysPicks; picks.push_back(actionSnapshot("pick",p)); }
#ifdef BH_BARON
int gv_ysClickSlot, eventPlayer=2, eventControl;
bool gv_uITemp[16], eventVisible=true;
const int c_timeGame=0;
int EventPlayer() { return eventPlayer; }
int EventDialogControl() { return eventControl; }
bool DialogControlIsVisible(int item,int p) {
    assert(item==eventControl && p==eventPlayer); return eventVisible;
}
void Wait(double duration,int clock) { assert(duration==0 && clock==c_timeGame); }
// Explicit NEW integration boundaries: the Baron suite owns BRDraw/BRClick's
// internal selection/eligibility/permissions. Here we record only dispatch,
// arguments and temporary identity. No recruit algorithm is copied into a stub.
struct BRCall { int player,target; bool recruit; ActionRender identity; };
std::vector<BRCall> brCalls;
void gf_BRDraw(int p) { drawAction("brdraw",p); }
void gf_BRClick(int p,int target,bool recruit) {
    brCalls.push_back({p,target,recruit,actionSnapshot("brclick",p)});
}
#endif
'''


CASES = r'''
void check(bool condition) { ++checks; assert(condition); }
void role(int p,int pool,int id) { gv_roles[p][1]=pool; gv_roles[p][0]=id; }
void reset() {
    gv_xrGang=false; gv_isNight=gv_bhFactionChatOpen=gv_gameStarted=true;
    gv_gameOver=gv_nightProcessingPhase=false; gv_host=15;
    gsRefreshes=fakeRenders=ysPicks=0;
    channelWrites.clear(); messages.clear(); actionRenders.clear(); picks.clear();
#ifdef BH_BARON
    gv_ysClickSlot=0; eventPlayer=2; eventControl=0; eventVisible=true; brCalls.clear();
#endif
    for(int pool=0;pool<9;++pool) for(int id=0;id<40;++id)
        gv_roleNameArray[pool][id]="ROLE("+std::to_string(pool)+","+std::to_string(id)+")";
    for(int p=0;p<=15;++p) {
        role(p,1,1); alive[p]=current[p]=p>0; gv_minimizedAllies[p]=false;
        gv_gsHost[p]=gv_fzPool[p]=gv_fzRole[p]=gv_fzLeader[p]=0;
        gv_disguiser[p]=gv_bhFeignRole[p]=gv_bhFaction[p]=0;
        gv_jailed[p]=gv_jailing[p]=gv_privateChannel[p]=gv_channel[p]=0;
        gv_silenced[p][0]=gv_silenced[p][1]=gv_dqRevealed[p]=allowed[p]=false;
        gv_diedAtNight[p]=gv_grPrivateChat[p]=gv_crying[p]=false; active[p]=p>0;
        gv_grChild[p]=gv_grParent[p]=roleRenders[p]=gv_action[p][0]=gv_action[p][1]=0;
        for(int other=0;other<=15;++other) gv_mute[p][other]=false;
        gv_preCultRole[p][0]=gv_preCultRole[p][1]=1;
        gv_playerColor[p]=p; gv_name[p]="<P"+std::to_string(p)+">"; gv_playerSpot[p]=p;
        for(int option=0;option<3;++option) gv_variableOptions[p][option]=10+option;
        for(int immunity=0;immunity<5;++immunity) gv_immune[p][immunity]=false;
        for(int item=0;item<7;++item) {
            gv_actionDialogItem[p][item]=100+p*7+item;
            visible[p][item]=false; rendered[p][item]=tooltip[p][item]="initial";
            gv_roleBoxText[p][item]="stale-"+std::to_string(p)+"-"+std::to_string(item);
        }
    }
}
text expectedName(int id,int faction) {
    // Declarative output contract: the source supplies the logic and key lookup.
    int color=faction==2?Color(85.10,62.75,56.08):Color(56.08,74.90,81.96);
    return "<color"+std::to_string(color)+">{Param/Value/BHFROLE"+std::to_string(id)+"}</color>";
}
bool sees(int viewer,int member) {
    return visible[viewer][5] && gv_roleBoxText[viewer][5].find(gv_name[member])!=string::npos;
}
void refresh() {
    auto names=std::array<string,16>{}; auto colors=std::array<int,16>{};
    for(int p=0;p<=15;++p) { names[p]=gv_name[p]; colors[p]=gv_playerColor[p]; }
    gf_RefreshRoleBox();
    for(int p=0;p<=15;++p) {
        check(names[p]==gv_name[p] && colors[p]==gv_playerColor[p]);
        check(rendered[p][5]==gv_roleBoxText[p][5] || !visible[p][5]);
    }
}
struct UI {
    std::array<text,16*7> values,draw,tips;
    std::array<bool,16*7> shown;
    UI() {
        for(int p=0;p<=15;++p) for(int item=0;item<7;++item) {
            int i=p*7+item; values[i]=gv_roleBoxText[p][item]; draw[i]=rendered[p][item];
            tips[i]=tooltip[p][item]; shown[i]=visible[p][item];
        }
    }
    void restore() const {
        for(int p=0;p<=15;++p) for(int item=0;item<7;++item) {
            int i=p*7+item; gv_roleBoxText[p][item]=values[i]; rendered[p][item]=draw[i];
            tooltip[p][item]=tips[i]; visible[p][item]=shown[i];
        }
    }
    bool operator==(const UI& other) const {
        return values==other.values && draw==other.draw && tips==other.tips && shown==other.shown;
    }
};
void identity_cases() {
    for(int faction: {2,5}) for(int id=1;id<=35;++id) {
        if(id==28 || id==29) continue;
        reset(); role(2,1,id); gv_bhFaction[2]=faction;
        check(gf_BHConverted(2) && gf_BHFaction(2)==faction);
        check(gv_roles[2][1]==1 && gv_roles[2][0]==id);
        check(gf_BHRoleName(2)==expectedName(id,faction));
        check(gf_FZFaceName(2)==expectedName(id,faction));
        check(gf_BHDeathName(2)==(id==8?gv_roleNameArray[1][8]:expectedName(id,faction)));
        check(gf_BHInvestigatedRoleName(2)==(id==8?gv_roleNameArray[1][8]:expectedName(id,faction)));
        check(gf_BHPrivateRoleName(2)==expectedName(id,faction));
        check(gf_DQSeenName(2)==gv_roleNameArray[1][id]);
        auto before=std::array<text,7>{};
        for(int item=0;item<7;++item) before[item]=gv_roleBoxText[2][item];
        gf_BHFactionCard(2);
        for(int item: {1,2,4,5}) check(before[item]==gv_roleBoxText[2][item]);
        check(gv_roleBoxText[2][3]=="{Param/Value/BHFGOAL"+std::to_string(faction)+"}");
        check(gv_roleBoxText[2][6]=="WINLIST("+std::to_string(faction)+",0)");
    }
    reset(); role(1,1,4); role(2,1,4); role(3,1,4);
    gv_bhFaction[1]=2; gv_bhFaction[2]=5;
    check(gf_FZFaceName(1)==expectedName(4,2));
    check(gf_FZFaceName(2)==expectedName(4,5));
    check(gf_FZFaceName(3)=="ROLE(1,4)");
    for(int p: {1,2,3}) check(gf_DQSeenName(p)=="ROLE(1,4)");
    alive[1]=alive[2]=false;
    check(gf_BHDeathName(1)==expectedName(4,2)); check(gf_BHDeathName(2)==expectedName(4,5));
    reset(); role(2,1,33); gv_fzPool[2]=5; gv_fzRole[2]=17;
    check(gf_FZFaceName(2)=="ROLE(5,17)");
    gv_bhFaction[2]=2; check(gf_FZFaceName(2)==expectedName(33,2));
    reset(); role(2,3,21); gv_bhFaction[2]=2;
    check(!gf_BHConverted(2) && gf_BHFaction(2)==3);
    check(gf_FZFaceName(2)=="ROLE(1,6)");
    alive[2]=false; check(gf_BHDeathName(2)=="ROLE(3,21)");
    for(int p: {0,16,-1}) check(!gf_BHConverted(p) && gf_BHFaction(p)==0);
    reset(); role(2,1,4); auto before=gv_roleBoxText[2][3]; gf_BHFactionCard(2);
    check(gv_roleBoxText[2][3]==before && gf_BHDeathName(2)=="ROLE(1,4)");
    std::cout<<"PASS identity: soft Mafia/blue profession, own/death vs investigation, DQ/FZ, private card\n";
}
void conversion_card_cases() {
    for(int faction: {2,5}) for(int id: {4,33}) {
        reset(); role(2,1,id); gv_fzPool[2]=faction==2?5:2; gv_fzRole[2]=17;
        auto before=std::array<text,7>{};
        for(int item=0;item<7;++item) before[item]=gv_roleBoxText[2][item];
        check(gf_BHConvertFaction(2,faction));
        check(gf_FZFaceName(2)==expectedName(id,faction));
        check(gv_roles[2][1]==1 && gv_roles[2][0]==id);
        check(roleRenders[2]==(id==33?1:0));
        for(int item: {1,2,4}) {
            if(id==33) check(gv_roleBoxText[2][item]=="TOWN_RENDER(33,"+std::to_string(item)+")");
            else check(gv_roleBoxText[2][item]==before[item]);
        }
        check(gv_roleBoxText[2][3]=="{Param/Value/BHFGOAL"+std::to_string(faction)+"}");
    }
    // Exact formerly-buggy interval: night is still true, processing still false,
    // but lockchat has started. Both entry AND repeated refresh must do nothing.
    for(int faction: {2,5}) {
        reset(); role(2,1,4); gv_bhFactionChatOpen=false;
        gv_channel[2]=0; gv_action[2][0]=9;
        check(!gf_BHConvertFaction(2,faction));
        check(gv_bhFaction[2]==0 && gv_channel[2]==0 && !allowed[2]);
        check(channelWrites.empty() && messages.empty() && gsRefreshes==0);
        check(gv_action[2][0]==9 && roleRenders[2]==0);
        gv_bhFaction[2]=faction; gv_channel[2]=3;
        gf_BHRefreshFactionChat();
        check(gv_channel[2]==3 && !allowed[2] && channelWrites.empty());
    }
    std::cout<<"PASS conversion: FZ true-card dispatcher, Town cache preservation, closed-night entry/refresh guards\n";
}
void fz_action_render_cases() {
    for(int converted: {0,1}) for(int fakeTeam: {2,5}) for(int fake: {2,17,19})
    for(bool talk: {false,true}) for(int leader: {0,3}) for(bool immune: {false,true}) {
        reset(); role(2,1,33); gv_fzPool[2]=fakeTeam; gv_fzRole[2]=fake; gv_fzLeader[2]=leader;
        int expectedTeam=converted?(fakeTeam==2?5:2):fakeTeam;
        if(converted) gv_bhFaction[2]=expectedTeam;
        role(3,fakeTeam,17);
        for(int option=0;option<3;++option) gv_variableOptions[3][option]=23+option;
        gv_action[2][0]=4; gv_action[2][1]=7; gv_immune[2][0]=immune;
        gf_RAFengziActions(2,talk);
        check(actionRenders.size()==1 && fakeRenders==1);
        auto seen=actionRenders[0];
        string expectedKind=fake==19?(talk?"ysbuttons":"ysdraw"):
                            fake==17?"leader":expectedTeam==2?"mafia":"triad";
        check(seen.kind==expectedKind && seen.player==2 && seen.pool==expectedTeam && seen.role==fake);
        if(leader) {
            check(seen.option0==23 && seen.option1==24 && seen.option2==25);
            check(seen.leaderPool==1 && seen.leaderRole==1);
        } else {
            check(seen.option0==1 && seen.option1==0 && seen.option2==0);
        }
        check(gv_roles[2][1]==1 && gv_roles[2][0]==33);
        check(gv_roles[3][1]==fakeTeam && gv_roles[3][0]==17);
        check(gv_variableOptions[2][0]==10 && gv_variableOptions[2][1]==11 && gv_variableOptions[2][2]==12);
        check(gv_variableOptions[3][0]==23 && gv_variableOptions[3][1]==24 && gv_variableOptions[3][2]==25);
        check(gv_bhFaction[2]==(converted?expectedTeam:0));
        check(gv_fzPool[2]==fakeTeam && gv_fzRole[2]==fake && gv_fzLeader[2]==leader);
        check(gv_immune[2][0]==immune && gv_action[2][0]==4 && gv_action[2][1]==7);
    }
    std::cout<<"PASS FZ action rendering: real team vs legacy fake team, 2/17/19, inherited options and full restoration\n";
}
void fz_notification_cases() {
    for(int converted: {0,1}) for(int faction: {2,5}) {
        reset(); role(2,1,33); gv_fzPool[2]=faction==2?5:2; gv_fzRole[2]=17;
        if(converted) gv_bhFaction[2]=faction;
        role(3,faction,1); role(4,gv_fzPool[2],1);
        role(5,1,4); gv_bhFaction[5]=faction;
        role(6,1,4); gv_bhFaction[6]=gv_fzPool[2];
        role(7,converted?faction:gv_fzPool[2],1); active[7]=false;
        gf_FZClick(2,9);
        check(gv_action[2][0]==9 && fakeRenders==1 && ysPicks==0);
        std::vector<int> recipients;
        for(auto& message: messages) if(message.first.find("{Param/Value/FENGATK}")!=string::npos)
            recipients.push_back(message.second);
        std::sort(recipients.begin(),recipients.end());
        // Real converts notify the real faction (including converted members),
        // NEVER old fake team or off-team host. Legacy FZ keeps its exact raw
        // fake-team dispatch plus historical offline-to-host fallback.
        check(recipients==(converted?std::vector<int>{3,5}:std::vector<int>{4,15}));
    }
    for(int faction: {2,5}) for(int fake: {2,17,19}) for(int target: {2,3,4}) {
        reset(); role(2,1,33); gv_bhFaction[2]=faction;
        gv_fzPool[2]=faction==2?5:2; gv_fzRole[2]=fake; gv_fzLeader[2]=3;
        role(3,faction,1); role(4,gv_fzPool[2],1); gv_action[2][0]=6;
        gf_FZClick(2,target);
        check(gv_roles[2][1]==1 && gv_roles[2][0]==33 && gv_bhFaction[2]==faction);
        if(target==3 && fake!=17) {
            check(ysPicks==0 && fakeRenders==0 && messages.empty() && gv_action[2][0]==6);
        } else if(fake==19) {
            check(ysPicks==1 && fakeRenders==0 && messages.empty());
            check(picks.size()==1 && picks[0].pool==faction && picks[0].role==19);
        } else if(target==2) {
            check(ysPicks==0 && fakeRenders==1 && gv_action[2][0]==0);
        } else {
            check(ysPicks==0 && fakeRenders==1 && gv_action[2][0]==target);
        }
    }
    std::cout<<"PASS FZClick: real-team notifications/filtering, fake19 dispatch, self-cancel, legacy fallback\n";
}
void channel_cases() {
    for(int faction: {2,5}) for(int guard=0;guard<11;++guard) {
        reset(); role(2,1,4); gv_bhFaction[2]=faction;
        gv_channel[2]=2; gv_channel[3]=3;
        if(guard==1) gv_jailed[2]=1;
        if(guard==2) gv_jailing[2]=1;
        if(guard==3) gv_privateChannel[2]=7;
        if(guard==4) gv_silenced[2][0]=true;
        if(guard==5) alive[2]=false;
        if(guard==6) current[2]=false;
        if(guard==7) gv_bhFeignRole[2]=1;
        if(guard==8) gv_isNight=false;
        if(guard==9) gv_gameOver=true;
        if(guard==10) gv_nightProcessingPhase=true;
        gf_BHRefreshFactionChat();
        check(gv_channel[3]==3 && !allowed[3]);
        if(guard==0) {
            check(gv_channel[2]==(faction==2?1:4) && allowed[2]);
        } else if(guard>=8) {
            check(gv_channel[2]==2 && !allowed[2] && channelWrites.empty());
        } else {
            check(gv_channel[2]==0 && !allowed[2]);
        }
    }
    // Former FZ/Mason channels must be removed even when speaking is guarded.
    for(int former: {1,2,4}) {
        reset(); role(2,1,33); gv_fzPool[2]=2; gv_bhFaction[2]=5;
        gv_channel[2]=former; gv_privateChannel[2]=99;
        gf_BHRefreshFactionChat(); check(gv_channel[2]==0 && !allowed[2]);
    }
    // Execute the real GS routing chain, not an inferred channel oracle.
    for(int faction: {2,5}) for(int guard=0;guard<8;++guard) {
        reset(); role(2,1,4); gv_bhFaction[2]=faction;
        role(1,3,29); gv_gsHost[1]=2;
        role(3,faction,1); gv_channel[3]=faction==2?1:4;
        role(4,faction==2?5:2,1); gv_channel[4]=faction==2?4:1;
        if(guard==1) gv_jailed[2]=1;
        if(guard==2) gv_privateChannel[2]=7;
        if(guard==3) gv_silenced[1][0]=true;
        if(guard==4) alive[2]=false;
        if(guard==5) gv_mute[3][1]=true;
        if(guard==6) gv_grPrivateChat[2]=true, gv_grChild[2]=3;
        if(guard==7) gv_crying[2]=true;
        gf_BHRefreshFactionChat();
        if(guard==0) {
            check(gf_GSEffectiveChannel(1)==(faction==2?1:4));
            check(gf_GSChatRecipient(1,3) && gf_GSChatRecipient(3,1));
            check(!gf_GSChatRecipient(1,4) && !gf_GSChatRecipient(4,1));
        } else if(guard==5) {
            check(!gf_GSChatRecipient(1,3) && gf_GSChatRecipient(3,1));
        } else {
            check(gf_GSEffectiveChannel(1)==0);
            check(!gf_GSChatRecipient(1,3) && !gf_GSChatRecipient(3,1));
        }
    }
    std::cout<<"PASS channels: readiness/stale-team guards, GS inherited channel and actual bidirectional routing\n";
}
void roster_cases() {
    for(int faction: {2,5}) for(int host: {2,15}) for(int sym: {1,14}) {
        reset(); role(host,1,4); gv_bhFaction[host]=faction;
        role(8,faction,1); role(9,faction==2?5:2,1);
        role(sym,3,29); gv_gsHost[sym]=host;
        refresh();
        for(int viewer: {host,8,sym}) {
            check(sees(viewer,host) && sees(viewer,8) && sees(viewer,sym));
            check(!sees(viewer,9));
            check(gv_roleBoxText[viewer][5].find(expectedName(4,faction))!=string::npos);
            check(gv_roleBoxText[viewer][5].find("<color"+std::to_string(host)+">"+gv_name[host]+"</color>")!=string::npos);
        }
        check(!sees(9,host) && !sees(9,sym));
        check(gv_roleBoxText[sym][5]==gv_roleBoxText[host][5]);
        check(gf_GSBaseAlly(host,8) && gf_GSBaseAlly(8,host));
        check(gf_GSAllyFor(8,sym) && !gf_GSAllyFor(9,sym));
    }
    for(int faction: {2,5}) for(int id: {7,14}) {
        reset(); role(2,1,id); role(3,1,7); role(4,faction,1);
        role(1,3,29); gv_gsHost[1]=2;
        refresh(); check(sees(2,3) && sees(3,2) && sees(1,3));
        gv_bhFaction[2]=faction; refresh();
        check(!sees(3,2) && !sees(3,1));
        check(!sees(2,3) && !sees(1,3));
        check(sees(2,4) && sees(4,2) && sees(4,1));
    }
    // A genuinely converted FZ joins ONLY the new team, never its old fake one.
    for(int faction: {2,5}) {
        reset(); role(2,1,33); gv_fzPool[2]=(faction==2?5:2); gv_fzRole[2]=17;
        gv_fzLeader[2]=3; role(3,gv_fzPool[2],17); role(4,gv_fzPool[2],2);
        role(5,faction,1); role(1,3,29); gv_gsHost[1]=2;
        gv_bhFaction[2]=faction; refresh();
        for(int viewer: {1,2,5}) {
            check(sees(viewer,2) && sees(viewer,5));
            check(!sees(viewer,3) && !sees(viewer,4));
        }
        check(!sees(3,2) && !sees(4,2) && !sees(4,1));
        check(gv_roleBoxText[1][5]==gv_roleBoxText[2][5]);
        check(gv_roleBoxText[2][5].find(expectedName(33,faction))!=string::npos);
    }
    std::cout<<"PASS rosters: bidirectional Mafia/Triad, names, GS ordering/inheritance, Mason/FZ isolation\n";
}
void unchanged_cases() {
    std::mt19937 rng(306029);
    const int pools[]={1,1,1,2,5,3,3,3,3,1};
    const int ids[]={1,7,14,3,3,8,10,1,5,33};
    for(int trial=0;trial<192;++trial) {
        reset(); gv_xrGang=trial%2;
        for(int p=1;p<=15;++p) {
            int k=rng()%10; role(p,pools[k],ids[k]);
            alive[p]=rng()%3; current[p]=rng()%4;
            gv_minimizedAllies[p]=rng()%2; gv_bhFeignRole[p]=rng()%5==0;
            gv_disguiser[p]=rng()%4==0?1+rng()%15:0;
            if(k==9) { gv_fzPool[p]=rng()%2?2:5; gv_fzRole[p]=17; gv_fzLeader[p]=1+rng()%15; }
        }
        UI initial; gf_RefreshRoleBoxBaseline(); UI baseline;
        initial.restore(); refresh(); check(UI()==baseline);
    }
    std::cout<<"PASS unchanged: 192 seeded legacy roster/UI snapshots against production reference\n";
}
#ifdef BH_BARON
void fz_baron_binding_cases() {
    for(int pool: {2,5}) for(int id: {2,17,18,19,22}) for(int status: {0,1,2}) {
        reset(); role(2,1,33); role(3,pool,id);
        alive[3]=status==0; gv_bhFeignRole[3]=status==1?17:0;
        gf_FZBind();
        check(gv_fzLeader[2]==(status==2?0:3));
        check(gv_fzPool[2]==(status==2?0:pool));
        check(gv_fzRole[2]==(status==2?0:id));
        check(gv_roles[2][1]==1 && gv_roles[2][0]==33);
        check(gv_roles[3][1]==pool && gv_roles[3][0]==id);
        check(gv_immune[2][0]==false);
    }
    for(int pool: {1,2,3,5}) for(int id: {1,20,21,22,33}) {
        reset(); role(2,1,33); role(3,pool,id); gf_FZBind();
        bool binds=(pool==2 || pool==5) && id==22;
        check(gv_fzLeader[2]==(binds?3:0));
        check(gf_BRFake(2)==binds);
        check(!gf_BRFake(3));
    }
    reset(); role(2,1,33); role(3,5,22); role(4,2,22); role(5,2,19); gf_FZBind();
    check(gv_fzPool[2]==2 && gv_fzRole[2]==19 && gv_fzLeader[2]==5);
    reset(); role(2,1,33); role(3,2,19); role(4,5,22); role(5,2,22); gf_FZBind();
    check(gv_fzPool[2]==2 && gv_fzRole[2]==22 && gv_fzLeader[2]==5);
    check(!gf_BRFake(-1) && !gf_BRFake(0) && !gf_BRFake(16));
    for(int rawPool: {1,2,3,5}) for(int rawRole: {1,22,33})
    for(int facePool: {0,1,2,3,5}) for(int faceRole: {0,19,22}) {
        reset(); role(2,rawPool,rawRole); gv_fzPool[2]=facePool; gv_fzRole[2]=faceRole;
        check(gf_BRFake(2)==(rawPool==1 && rawRole==33 && (facePool==2 || facePool==5) && faceRole==22));
    }
    std::cout<<"PASS FZBind: 22 in both pools, alive/feign gates, priority, invalid and nonleader rejection\n";
}
void fz_baron_render_cases() {
    for(int converted: {0,1}) for(int fakeTeam: {2,5}) for(bool talk: {false,true})
    for(int leader: {0,3}) for(bool immune: {false,true}) {
        reset(); role(2,1,33); gv_fzPool[2]=fakeTeam; gv_fzRole[2]=22; gv_fzLeader[2]=leader;
        int expectedTeam=converted?(fakeTeam==2?5:2):fakeTeam;
        if(converted) gv_bhFaction[2]=expectedTeam;
        role(3,fakeTeam,22);
        for(int option=0;option<3;++option) gv_variableOptions[3][option]=23+option;
        gv_action[2][0]=4; gv_action[2][1]=7;
        for(int bit=0;bit<5;++bit) gv_immune[2][bit]=immune;
        gf_RAFengziActions(2,talk);
        check(actionRenders.size()==1 && fakeRenders==1 && brCalls.empty());
        auto seen=actionRenders[0];
        check(seen.kind=="brdraw" && seen.player==2 && seen.pool==expectedTeam && seen.role==22);
        check(seen.option0==(leader?23:1) && seen.option1==(leader?24:0) && seen.option2==(leader?25:0));
        check(seen.leaderPool==(leader?1:0) && seen.leaderRole==(leader?1:0));
        check(gv_roles[2][1]==1 && gv_roles[2][0]==33 && gv_roles[3][1]==fakeTeam && gv_roles[3][0]==22);
        check(gv_variableOptions[2][0]==10 && gv_variableOptions[2][1]==11 && gv_variableOptions[2][2]==12);
        check(gv_variableOptions[3][0]==23 && gv_variableOptions[3][1]==24 && gv_variableOptions[3][2]==25);
        check(gv_action[2][0]==4 && gv_action[2][1]==7);
        check(gv_fzPool[2]==fakeTeam && gv_fzRole[2]==22 && gv_fzLeader[2]==leader);
        check(gv_bhFaction[2]==(converted?expectedTeam:0));
        for(int bit=0;bit<5;++bit) check(gv_immune[2][bit]==immune);
    }
    std::cout<<"PASS FZ22 render: actual temporary dispatch, inherited options, full restoration, no immunity\n";
}
void fz_baron_click_cases() {
    for(int pool: {2,5}) for(int converted: {0,1}) for(int target=1;target<=15;++target) {
        reset(); role(2,1,33); role(3,pool,22); gv_fzPool[2]=pool; gv_fzRole[2]=22; gv_fzLeader[2]=3;
        if(converted) gv_bhFaction[2]=pool==2?5:2;
        gv_action[2][0]=7; gv_action[2][1]=8; gv_ysClickSlot=1;
        gf_FZClick(2,target);
        check(brCalls.size()==1 && messages.empty() && fakeRenders==0 && ysPicks==0);
        auto call=brCalls[0];
        check(call.player==2 && call.target==target && call.recruit);
        check(call.identity.pool==1 && call.identity.role==33);
        check(gv_roles[2][1]==1 && gv_roles[2][0]==33 && gv_action[2][0]==7 && gv_action[2][1]==8);
        check(!gv_immune[2][0] && gv_bhFaction[2]==(converted?(pool==2?5:2):0));
    }
    for(int pool: {2,5}) for(int converted: {0,1}) for(int target: {2,3,4,9}) {
        reset(); role(2,1,33); gv_fzPool[2]=pool; gv_fzRole[2]=22; gv_fzLeader[2]=3;
        int team=converted?(pool==2?5:2):pool;
        if(converted) gv_bhFaction[2]=team;
        role(3,pool,22); role(4,team,1); gv_action[2][0]=7; gv_ysClickSlot=0;
        gf_FZClick(2,target);
        check(brCalls.empty() && ysPicks==0);
        bool rejected=target==4 || (converted && target==3 && pool==team);
        check(gv_action[2][0]==(target==2?0:rejected?7:target));
        if(target==9) {
            int own=0,attack=0;
            for(auto& message: messages) {
                own+=message.second==2 && message.first.find("{Param/Value/BZWILL}")!=string::npos;
                attack+=message.first.find("{Param/Value/FENGATK}")!=string::npos;
            }
            check(own==1 && attack>=1);
        }
        check(gv_roles[2][1]==1 && gv_roles[2][0]==33 && !gv_immune[2][0]);
    }
    std::cout<<"PASS FZ22 click: B invokes BR boundary exactly once; A retains fake attack/cancel/messages\n";
}
void fz_baron_event_cases() {
    for(int pool: {2,5}) for(int fake: {19,22}) for(int slot: {5,6}) for(int guard=0;guard<5;++guard) {
        reset(); role(2,1,33); role(3,pool,fake); gv_fzPool[2]=pool; gv_fzRole[2]=fake; gv_fzLeader[2]=3;
        eventControl=gv_actionDialogItem[9][slot]; gv_action[2][0]=7;
        if(guard==1) alive[2]=false;
        if(guard==2) gv_isNight=false;
        if(guard==3) eventVisible=false;
        bool run=guard!=4;
        bool result=slot==5?gt_ASActionButtonATown_Func(true,run):gt_ASActionButtonBTown_Func(true,run);
        check(result==(guard==0 || guard==4));
        if(guard) {
            check(brCalls.empty() && picks.empty() && messages.empty() && gv_action[2][0]==7);
        } else if(fake==19) {
            check(picks.size()==1 && brCalls.empty() && messages.empty());
            check(picks[0].pool==pool && picks[0].role==19 && gv_ysClickSlot==slot-5);
        } else if(slot==6) {
            check(brCalls.size()==1 && picks.empty() && messages.empty() && gv_action[2][0]==7);
            check(brCalls[0].player==2 && brCalls[0].target==9 && brCalls[0].recruit);
        } else {
            check(brCalls.empty() && picks.empty() && gv_action[2][0]==9 && gv_ysClickSlot==0);
            int own=0;
            for(auto& message: messages) own+=message.second==2 && message.first.find("{Param/Value/BZWILL}")!=string::npos;
            check(own==1);
        }
        check(gv_roles[2][1]==1 && gv_roles[2][0]==33 && !gv_immune[2][0]);
    }
    std::cout<<"PASS FZ22 actual Town A/B events: independent slots, single dispatch and original guards\n";
}
#endif
int main() {
    identity_cases(); conversion_card_cases(); fz_action_render_cases(); fz_notification_cases();
    channel_cases(); roster_cases(); unchanged_cases();
    std::cout<<"PASS "<<checks<<" original faction identity/UI/channel/ally assertions\n";
#ifdef BH_BARON
    fz_baron_binding_cases(); fz_baron_render_cases(); fz_baron_click_cases(); fz_baron_event_cases();
    std::cout<<"PASS "<<checks<<" total faction identity/FZ22 integration assertions\n";
#endif
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    parser.add_argument('--require-baron', action='store_true',
                        help='fail unless the integrated FZ22 source is present')
    args = parser.parse_args()
    source = args.script.read_text()
    old, baseline = reference()
    check_wiring(source, old)
    has_baron = bool(re.search(r'^bool gf_BRFake\s*\([^;]*\)\s*\{', mask(source), re.M))
    assert has_baron or not args.require_baron, 'FZ22 source not integrated yet'
    names = list(NAMES)
    if has_baron:
        check_baron_wiring(source)
        names.extend(BARON_NAMES)
    else:
        print('SKIP FZ22 extension: BRFake not yet integrated (use --require-baron after integration)', flush=True)

    names = list(with_guoke_dependencies(source, names))
    bodies = [function(source, name) for name in names]
    # Pull any newly factored name helper from production too, never stub it.
    cursor = 0
    while cursor < len(bodies):
        for called in re.findall(r'\b(gf_BH\w+)\s*\(', mask(bodies[cursor])):
            if called not in names:
                names.append(called)
                bodies.append(function(source, called))

        cursor += 1

    prototypes = '\n'.join(body.split('{', 1)[0].strip() + ';' for body in bodies)
    boundaries = ''
    if has_baron:
        # The actual Town event functions retain every other profession branch.
        # Those unreachable, non-FZ handlers are explicit assertion doubles.
        handlers = sorted(set(re.findall(r'\b(gf_SK[AB]_1_\w+)\s*\(', '\n'.join(bodies))))
        boundaries = '\n'.join(f'void {name}(int,int) {{ assert(false && "non-FZ action boundary"); }}'
                               for name in handlers)

    prelude = prefix()
    prelude += '\n' + missing_actual_globals(source, bodies, prelude) + '\n'
    code = translate(('#define BH_BARON 1\n' if has_baron else '') + prelude
                     + '\n' + boundaries + '\n' + prototypes + '\n' + '\n\n'.join(bodies)
                     + '\n' + baseline + '\n' + CASES)
    compiler = shutil.which('g++') or shutil.which('clang++')
    assert compiler, 'a C++ compiler is required'
    for name, body in zip(names, bodies):
        line = source.count('\n', 0, source.index(body)) + 1
        print(f'{name}: lines {line}..{line + body.count(chr(10))}', flush=True)

    with tempfile.TemporaryDirectory(prefix='faction-identity-') as temporary:
        cpp, binary = Path(temporary) / 'identity.cpp', Path(temporary) / 'identity'
        cpp.write_text(code)
        subprocess.run([compiler, '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
