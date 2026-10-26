#!/usr/bin/env python3
"""Execute integrated 共生体 chat Galaxy definitions under ASan/UBSan.

Uses only the maintained main script and merged role strings. No temporary patch
scripts or role fragments are imported. Engine rendering APIs are explicit doubles;
all chat helpers, GS identity/activity/label, FZ and XR predicates run verbatim.
No SC2 build, deployment, or source writes are performed.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_faction_conversion import with_guoke_dependencies, missing_actual_globals

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "work/blackhand/CustomLogic.galaxy"
SOURCE = SCRIPT.read_text()
RAW = ("gf_CBAddChatE8AF95E8AF95E79C8BE883BDE4B88DE883BDE794A8", "gf_CBAddChat")
CHAT_NAMES = (
    "gf_GSChatReady", "gf_GSChatPeer", "gf_GSChatRoot", "gf_GSGRPartner",
    "gf_GSChatXR", "gf_GSChatPublic", "gf_GSEffectiveChannel", "gf_GSChatColor",
    "gf_GSChatHidden", "gf_GSChatRecipient", "gf_GSSpecialRecipient",
    "gf_GSSpecialSay", "gf_GSChatSay", "gf_GSRefreshChat", "gf_GSChatJoin",
)
SUPPORT_NAMES = ("gf_BHConverted", "gf_BHSpyActive", "gf_GSIs", "gf_GSActive", "gf_GSPlayerLabel", "gf_FZChatHidden", "gf_XRNeutralFatal")


def mask(source: str) -> str:
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: re.sub(r"[^\n]", " ", m.group()), source)


def function(source: str, name: str) -> str:
    clean = mask(source)
    matches = list(re.finditer(r"(?m)^(?:void|bool|int|text)\s+" + re.escape(name) +
                               r"\s*\([^;{}]*\)\s*\{", clean))
    assert len(matches) == 1, (name, "expected exactly one definition", len(matches))
    begin, end, depth = matches[0].start(), matches[0].end(), 1
    while depth:
        assert end < len(clean), (name, "unbalanced body")
        depth += (clean[end] == "{") - (clean[end] == "}")
        end += 1
    return source[begin:end]


def extracted(names):
    return "\n\n".join(function(SOURCE, name) for name in names)


def prototypes(names):
    return "\n".join(function(SOURCE, name).split("{", 1)[0].strip() + ";" for name in names) + "\n"


PRELUDE = r'''
#include <cassert>
#include <cstdio>
#include <string>
#include <vector>
using string = std::string;
using text = std::string;
bool gv_isNight=true, gv_gameOver=false, gv_xrGang=false;
int gv_currentPlayers=1, gv_alivePlayers=2;
bool current[16], alive[16];
int gv_roles[16][2], gv_gsHost[16], gv_channel[16], gv_bhFeignRole[16], gv_bhFaction[16];
int gv_jailed[16], gv_jailing[16], gv_privateChannel[16];
int gv_grChild[16], gv_grParent[16], gv_fzLeader[16];
bool gv_grPrivateChat[16], gv_crying[16], gv_silenced[16][2];
bool gv_mute[16][16], gv_chatPrivilege[16], gv_gsUsed[16], gv_diedAtNight[16];
string gv_number[16], gv_name[16];
int gv_playerColor[16];
int ge_Allow_Allow=1, crimes=0;
struct Record { text line; int recipient; int source; };
std::vector<Record> records;
bool PlayerGroupHasPlayer(int g,int p) {
    assert(p>=1 && p<=15);
    return g==gv_currentPlayers ? current[p] : alive[p];
}
text StringToText(string s) { return s; }
string IntToString(int p) { return std::to_string(p); }
text TextWithColor(text t,int) { return t; }
int libNtve_gf_ConvertPlayerColorToColor(int c) { return c; }
text StringExternal(string s) {
    if (s=="Param/Value/GSCHNAME") return "共生体";
    if (s=="Param/Value/GSCHJOIN") return "一位共生体跟随着你们的成员来到了你们的集会地。";
    return s;
}
int SoundLink(string,int) { return 0; }
int Color(double,double,double) { return 0; }
void gf_CBSystemMessage(text t,int p,int source,int,int,int) { records.push_back({t,p,source}); }
void gf_CBAllowDisallowChatting(int p,int allow) { gv_chatPrivilege[p]=(allow==ge_Allow_Allow); }
void gf_BHCrime(int,int) { ++crimes; }
void gf_CBAddChat(int,string,text,bool);
bool gf_FZChatHidden(int,int);
'''

HARNESS = r'''
void gf_CBAddChat(int s,string message,text title,bool named) {
    assert(title=="共生体" && named);
    for(int p=1;p<=15;++p) if(gf_GSChatRecipient(s,p)) records.push_back({message,p,s});
}
void reset() {
    records.clear(); crimes=0;
    gv_isNight=true; gv_gameOver=false; gv_xrGang=false;
    for(int p=0;p<16;++p) {
        current[p]=alive[p]=gv_chatPrivilege[p]=true;
        gv_diedAtNight[p]=false;
        gv_number[p]=std::to_string(p); gv_name[p]="secret-name"+std::to_string(p); gv_playerColor[p]=p;
        gv_roles[p][1]=1; gv_roles[p][0]=1;
        gv_gsHost[p]=gv_channel[p]=gv_bhFeignRole[p]=0;
        gv_jailed[p]=gv_jailing[p]=gv_privateChannel[p]=0;
        gv_grChild[p]=gv_grParent[p]=gv_fzLeader[p]=0;
        gv_grPrivateChat[p]=gv_crying[p]=gv_gsUsed[p]=false;
        gv_silenced[p][0]=gv_silenced[p][1]=false;
        for(int q=0;q<16;++q) gv_mute[p][q]=false;
    }
    gv_roles[1][1]=3; gv_roles[1][0]=29; gv_gsHost[1]=2; gv_gsUsed[1]=true;
}
void second(int host) { gv_roles[5][1]=3; gv_roles[5][0]=29; gv_gsHost[5]=host; }
bool received(int p) { for(auto r:records) if(r.recipient==p) return true; return false; }
void block(int p,int state) {
    switch(state) {
        case 1: alive[p]=false; break;
        case 2: gv_bhFeignRole[p]=1; break;
        case 3: gv_jailed[p]=7; break;
        case 4: gv_jailing[p]=7; break;
        case 5: gv_silenced[p][0]=true; break;
        case 6: gv_privateChannel[p]=7; break;
        case 7: current[p]=false; break;
    }
}
int main() {
    // Whole-group bidirectionality, all four ordinary channels and mismatch.
    for(int ch=1;ch<=4;++ch) for(int other=0;other<=4;++other) {
        reset(); gv_channel[2]=gv_channel[3]=ch; gv_channel[4]=other;
        assert(gf_GSEffectiveChannel(1)==ch && gv_channel[1]==0);
        assert(gf_GSChatRecipient(1,2) && gf_GSChatRecipient(1,3));
        assert(gf_GSChatRecipient(2,1) && gf_GSChatRecipient(3,1));
        assert(gf_GSChatRecipient(1,4)==(ch==other));
        assert(gf_GSChatSay(1,"ordinary") && received(3));
        second(6); gv_channel[6]=other;
        assert(gf_GSChatRecipient(1,5)==(ch==other));
        assert(gf_GSChatRecipient(5,1)==(ch==other));
        // Host faction/channel changes are immediately reflected without refresh.
        gv_channel[2]=other;
        assert(gf_GSEffectiveChannel(1)==other);
    }
    // Active GS edges must reject every jail/silence/death/interrogation state.
    for(int who: {1,2,3}) for(int state=1;state<=7;++state) {
        reset(); gv_channel[2]=gv_channel[3]=1; block(who,state);
        assert(!gf_GSChatRecipient(1,3));
        assert(!gf_GSChatRecipient(3,1));
        if(who!=3) assert(!gf_GSChatPeer(1));
    }
    // Actual GSActive rejects pending night deaths before alive-group removal.
    for(int who: {1,2}) {
        reset(); gv_channel[2]=gv_channel[3]=1; gv_diedAtNight[who]=true;
        assert(!gf_GSActive(1) && !gf_GSChatPeer(1) && !gf_GSChatRecipient(3,1));
    }
    reset(); assert(gf_GSPlayerLabel(2)=="2.secret-name2");
    gv_number[2]=""; assert(gf_GSPlayerLabel(2)=="2.secret-name2");
    // Spy1/4 listening; no hidden leader bypass through sym/host aliasing.
    for(int ch=1;ch<=4;++ch) {
        reset(); gv_channel[2]=ch; gv_roles[3][0]=8;
        assert(gf_GSChatRecipient(1,3)==(ch==1 || ch==4));
        gv_silenced[3][0]=true; assert(!gf_GSChatRecipient(1,3));
    }
    reset(); gv_channel[2]=gv_channel[3]=1; gv_roles[2][0]=33; gv_fzLeader[2]=3;
    assert(!gf_GSChatRecipient(1,3) && !gf_GSChatRecipient(3,1));
    reset(); gv_channel[2]=gv_channel[3]=4; gv_roles[3][0]=33; gv_fzLeader[3]=2;
    assert(!gf_GSChatRecipient(1,3) && !gf_GSChatRecipient(3,1));
    // Two isolated pairs, also when two symbiotes share a host.
    reset(); second(6);
    assert(gf_GSChatSay(1,"private"));
    assert(received(1) && received(2) && !received(3) && !received(5) && !received(6));
    records.clear(); assert(gf_GSChatSay(2,"reply")); assert(received(1) && received(2) && !received(5));
    second(2); records.clear(); gf_GSChatSay(1,"private"); assert(!received(5));
    records.clear(); gf_GSChatSay(2,"reply"); assert(received(1) && received(5) && !received(3));
    // Previously-enabled host input must not fall back to public channel zero.
    for(int state=1;state<=7;++state) {
        reset(); block(1,state); assert(gf_GSChatSay(2,"blocked-pair")); assert(!received(3));
    }
    // XR existing speaker -> extra GS only; GS -> entire actual-role group.
    reset(); gv_xrGang=true; gv_roles[2][1]=gv_roles[3][1]=3;
    gv_roles[2][0]=gv_roles[3][0]=1; second(6); gv_roles[6][1]=3; gv_roles[6][0]=14;
    gf_GSSpecialSay(2,"xr incoming",1,true); assert(received(1) && !received(2) && !received(5));
    records.clear(); assert(gf_GSChatSay(1,"xr outgoing")); assert(received(1) && received(2) && received(3) && !received(5));
    gv_silenced[3][0]=true; records.clear(); gf_GSChatSay(1,"xr outgoing"); assert(!received(3));
    // GR exact endpoints, no parent/child-group transitive leakage.
    reset(); gv_grPrivateChat[2]=true; gv_grChild[2]=3; gv_grParent[3]=2; second(6);
    gf_GSSpecialSay(2,"gr incoming",2,true); assert(received(1) && !received(5));
    records.clear(); gf_GSChatSay(1,"gr outgoing"); assert(received(1) && received(2) && received(3) && !received(5));
    gv_jailed[3]=9; records.clear(); gf_GSChatSay(1,"gr jailed"); assert(records.empty());
    // Public GS label is anonymous for both actual judge and crier hosts.
    for(int pool: {1,3}) {
        reset(); gv_roles[2][1]=pool; gv_roles[2][0]=(pool==1 ? 20 : 12); gv_crying[2]=true;
        assert(gf_GSChatPublic(1)); assert(!gf_GSChatRecipient(3,1));
        assert(gf_GSChatSay(1,"public")); assert(received(15) && crimes==1);
        for(auto r:records) { assert(r.line.find("共生体")!=string::npos); assert(r.line.find("secret-name")==string::npos); assert(r.source==16); }
        assert(!gv_crying[1] && gv_roles[1][0]==29 && gv_channel[1]==0);
    }
    // Private-channel precedence: no inherited receiver on either side.
    reset(); gv_channel[2]=1; gv_privateChannel[2]=3;
    assert(!gf_GSChatRecipient(1,2) && !gf_GSSpecialRecipient(2,1,1));
    // Existing-channel join announces once; new two-person chat has no meeting-place announcement.
    reset(); gv_channel[2]=gv_channel[3]=2; gf_GSChatJoin(1);
    int joinCount=0; for(auto r:records) if(r.line=="一位共生体跟随着你们的成员来到了你们的集会地。") ++joinCount;
    assert(joinCount==3 && records.size()==3 && !received(4));
    reset(); gf_GSChatJoin(1); assert(records.empty());
    reset(); gv_chatPrivilege[1]=gv_chatPrivilege[2]=false; gf_GSRefreshChat();
    assert(gv_chatPrivilege[1] && gv_chatPrivilege[2] && gv_channel[1]==0);
    // Mute and invalid bounds; color index never escapes [0,4].
    reset(); gv_channel[2]=1; gv_mute[3][1]=true; gv_channel[3]=1;
    assert(!gf_GSChatRecipient(1,3));
    for(int p=-2;p<=18;++p) assert(gf_GSChatColor(p)>=0 && gf_GSChatColor(p)<=4);
    for(int h: {-1,0,16,999}) { gv_gsHost[1]=h; assert(!gf_GSChatPeer(1) && gf_GSEffectiveChannel(1)==0); }
    // Day and endgame retain the exact raw original predicate, including spies.
    for(int night=0;night<2;++night) for(int over=0;over<2;++over) if(!night || over) {
        reset(); gv_isNight=night; gv_gameOver=over; gv_channel[1]=gv_channel[3]=2;
        assert(!gf_GSChatSay(1,"unchanged")); assert(gf_GSChatRecipient(1,3));
        assert(gf_GSEffectiveChannel(1)==2);
    }
    std::puts("real Galaxy functions: ordinary/private/public/XR/GR/guards/FZ/spy/bounds PASS");
}
'''


class GongshengtiChat(unittest.TestCase):
    def test_exact_wiring(self):
        for name in RAW:
            body = function(SOURCE, name)
            self.assertEqual(body.count("gf_GSChatRecipient(lp_player, lv_a)"), 1)
            self.assertNotIn("gv_channel[lp_player]", body)
            self.assertNotIn("gv_channel[lv_a]", body)
            self.assertIn('lp_title = StringExternal("Param/Value/GSCHNAME");', body)
            self.assertIn("gf_GSChatColor(lv_a)", body)
            self.assertIn("gf_GSEffectiveChannel(lp_player)", body)
        self.assertNotRegex(mask(SOURCE), r"(?m)^void gf_AddDefaultChat\s*\(")
        body = function(SOURCE, "gf_BHPlayerChat")
        self.assertEqual(body.count("gf_GSChatSay(lp_player, lp_message)"), 1)
        self.assertLess(body.index("gv_ttHush"), body.index("gf_GSChatSay("))
        self.assertLess(body.index("gf_GSChatSay("), body.index("gf_XRGangSay("))
        self.assertLess(body.index("gf_XRGangSay("), body.index("gv_grPrivateChat"))
        self.assertEqual(body.count("gf_GSSpecialSay(lp_player, lp_message, 2, true);"), 1)
        xr = function(SOURCE, "gf_XRGangSay")
        self.assertEqual(xr.count("gf_GSSpecialSay(lp_player, lp_message, 1, true);"), 1)
        self.assertIn("gv_roles[lv_a][0] == gv_roles[lp_player][0]", xr)
        chat = extracted(CHAT_NAMES)
        self.assertNotRegex(chat, r"gv_(?:channel|roles|crying)\[[^\n;]+(?<![=!<>])=(?!=)")
        self.assertIn("gf_GSChatJoin(lp_player)", function(SOURCE, "gf_GSBind"))
        self.assertIn("gf_GSRefreshChat()", function(SOURCE, "gf_GSBind"))
        # Show exact integrated hook locations rather than assuming old offsets.
        for name in (*RAW, "gf_BHPlayerChat", "gf_XRGangSay"):
            body = function(SOURCE, name)
            begin = SOURCE.index(body)
            first = SOURCE.count("\n", 0, begin) + 1
            print(f"{name}: L{first}-L{first + body.count(chr(10))}")

    def test_extracted_galaxy(self):
        names = with_guoke_dependencies(SOURCE, (*SUPPORT_NAMES, *CHAT_NAMES))
        bodies = [function(SOURCE, name) for name in names]
        globals_text = missing_actual_globals(SOURCE, bodies, PRELUDE)
        harness = PRELUDE + '\n' + globals_text + '\n' + prototypes(names) + extracted(names) + "\n" + HARNESS
        with tempfile.TemporaryDirectory(prefix="gs-chat-test-") as directory:
            source, binary = Path(directory) / "chat.cpp", Path(directory) / "chat-test"
            source.write_text(harness)
            subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer", str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_galaxy_lint(self):
        subprocess.run(["python3", str(ROOT / "tools/galaxy_lint.py"), str(SCRIPT)], check=True)

    def test_string_contract(self):
        values = dict(line.removeprefix("Param/Value/").split("=", 1)
                      for line in (ROOT / "work/blackhand/strings-gs.txt").read_text().splitlines()
                      if line.startswith("Param/Value/") and "=" in line)
        keys = set(re.findall(r'Param/Value/(GS\w+)', extracted(CHAT_NAMES)))
        self.assertFalse(keys - values.keys(), ("unmerged chat strings", keys - values.keys()))
        self.assertEqual(values["GSCHJOIN"], "一位共生体跟随着你们的成员来到了你们的集会地。")
        self.assertEqual(values["GSCHNAME"], "共生体")


if __name__ == "__main__":
    unittest.main()
