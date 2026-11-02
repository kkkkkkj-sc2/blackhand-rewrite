# 报纸店老板 1/38 第三步：同一事件合并计数 + 巴士司机调换进库
import io

p = 'work/blackhand/CustomLogic.galaxy'
s = io.open(p, encoding='utf-8').read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:70])
    s = s.replace(old, new, cnt)


# 1) 全局：正文 + 去重标签 + 计数
rep('''text[64] gv_bpLog;           // 报纸店老板(1/38)：昨夜的信息
int gv_bpLogN;
''', '''text[64] gv_bpLog;           // 报纸店老板(1/38)：昨夜的信息正文
int[64] gv_bpTag;            // 去重标签：同标签合并计数
int[64] gv_bpCount;
int gv_bpLogN;
''')

# 2) 整个函数块替换（从存档标记到流动摊贩块之前）
start = s.index('// 新增角色（非原图抽取）：城镇 1/38 报纸店老板。\n')
end = s.index('// 新增角色（非原图抽取）：城镇 1/37 流动摊贩。\n')
new_block = '''// 新增角色（非原图抽取）：城镇 1/38 报纸店老板。
text gf_BPRoleName (int lp_player) {
    return gv_roleNameArray[gv_roles[lp_player][1]][gv_roles[lp_player][0]];
}

// 1 名 / 2 名 / ... 的前缀
text gf_BPCountName (int lp_n) {
    if ((lp_n == 1)) {
        return StringExternal("Param/Value/BPNUM1");
    }

    if ((lp_n == 2)) {
        return StringExternal("Param/Value/BPNUM2");
    }

    if ((lp_n == 3)) {
        return StringExternal("Param/Value/BPNUM3");
    }

    if ((lp_n == 4)) {
        return StringExternal("Param/Value/BPNUM4");
    }

    if ((lp_n == 5)) {
        return StringExternal("Param/Value/BPNUM5");
    }
    return (IntToText(lp_n) + StringExternal("Param/Value/BPNUMMORE"));
}

// 同标签合并：已有就把计数 +1，否则追加一条
void gf_BPAdd (int lp_tag, text lp_body) {
    int lv_i;

    lv_i = 0;
    while ((lv_i < gv_bpLogN)) {
        if ((gv_bpTag[lv_i] == lp_tag)) {
            gv_bpCount[lv_i] += 1;
            return;
        }

        lv_i += 1;
    }

    if ((gv_bpLogN >= 64)) {
        return;
    }

    gv_bpTag[gv_bpLogN] = lp_tag;
    gv_bpCount[gv_bpLogN] = 1;
    gv_bpLog[gv_bpLogN] = lp_body;
    gv_bpLogN += 1;
}

void gf_BPClear () {
    int lv_i;

    lv_i = 0;
    while ((lv_i < 64)) {
        gv_bpTag[lv_i] = 0;
        gv_bpCount[lv_i] = 0;
        lv_i += 1;
    }

    gv_bpLogN = 0;
}

void gf_BPEventAttack (int lp_victim, int lp_killer) {
    if ((lp_victim < 1) || (lp_victim > 15) || (lp_killer < 1) || (lp_killer > 15)) {
        return;
    }

    gf_BPAdd((1000000 + (gv_roles[lp_victim][1] * 100000) + (gv_roles[lp_victim][0] * 1000) + (gv_roles[lp_killer][1] * 100) + gv_roles[lp_killer][0]), (gf_BPRoleName(lp_victim) + StringExternal("Param/Value/BPATK2") + gf_BPRoleName(lp_killer) + StringExternal("Param/Value/BPATK3")));
}

void gf_BPEventHeal (int lp_victim, int lp_healer) {
    if ((lp_victim < 1) || (lp_victim > 15) || (lp_healer < 1) || (lp_healer > 15)) {
        return;
    }

    gf_BPAdd((2000000 + (gv_roles[lp_victim][1] * 100000) + (gv_roles[lp_victim][0] * 1000) + (gv_roles[lp_healer][1] * 100) + gv_roles[lp_healer][0]), (gf_BPRoleName(lp_victim) + StringExternal("Param/Value/BPHEAL2") + gf_BPRoleName(lp_healer) + StringExternal("Param/Value/BPHEAL3")));
}

void gf_BPEventBlock (int lp_victim, int lp_blocker) {
    if ((lp_victim < 1) || (lp_victim > 15) || (lp_blocker < 1) || (lp_blocker > 15)) {
        return;
    }

    gf_BPAdd((3000000 + (gv_roles[lp_victim][1] * 100000) + (gv_roles[lp_victim][0] * 1000) + (gv_roles[lp_blocker][1] * 100) + gv_roles[lp_blocker][0]), (gf_BPRoleName(lp_victim) + StringExternal("Param/Value/BPBLK2") + gf_BPRoleName(lp_blocker) + StringExternal("Param/Value/BPBLK3")));
}

void gf_BPEventVisit (int lp_victim, int lp_visitor) {
    if ((lp_victim < 1) || (lp_victim > 15) || (lp_visitor < 1) || (lp_visitor > 15)) {
        return;
    }

    gf_BPAdd((4000000 + (gv_roles[lp_victim][1] * 100000) + (gv_roles[lp_victim][0] * 1000) + (gv_roles[lp_visitor][1] * 100) + gv_roles[lp_visitor][0]), (gf_BPRoleName(lp_victim) + StringExternal("Param/Value/BPVIS2") + gf_BPRoleName(lp_visitor) + StringExternal("Param/Value/BPVIS3")));
}

// 调查结果原样抄一份进信息库（调查免疫时显示阵营）
void gf_BPEventLook (int lp_investigator) {
    int lv_t;
    int lv_pool;
    int lv_role;
    text lv_seen;

    if ((lp_investigator < 1) || (lp_investigator > 15)) {
        return;
    }

    lv_t = gv_visitation[lp_investigator];
    if ((lv_t < 1) || (lv_t > 15) || (lv_t == lp_investigator)) {
        return;
    }

    if ((PlayerGroupHasPlayer(gv_alivePlayers, lp_investigator) == false)) {
        return;
    }

    lv_pool = gf_DQSeenPool(lv_t);
    lv_role = gf_DQSeenRole(lv_t);
    if ((gf_BHSeenFaction(lv_t) == 2)) {
        lv_seen = StringExternal("Param/Value/BPFAC2M");
    }
    else if ((gf_BHSeenFaction(lv_t) == 5)) {
        lv_seen = StringExternal("Param/Value/BPFAC5M");
    }
    else {
        lv_seen = gv_roleInvestigatorArray[lv_pool][lv_role][0];
    }

    gf_BPAdd((5000000 + (gv_roles[lp_investigator][1] * 100000) + (gv_roles[lp_investigator][0] * 1000) + (lv_pool * 100) + lv_role), (gf_BPRoleName(lp_investigator) + StringExternal("Param/Value/BPLOOK2") + lv_seen + StringExternal("Param/Value/BPLOOK3")));
}

void gf_BPEventBus (int lp_player) {
    if ((lp_player < 1) || (lp_player > 15)) {
        return;
    }

    gf_BPAdd((6000000 + (gv_roles[lp_player][1] * 100000) + (gv_roles[lp_player][0] * 1000)), (gf_BPRoleName(lp_player) + StringExternal("Param/Value/BPBUS2")));
}

// 白天开场：重置领报额度，把昨晚的访问和巴士调换补进报纸
void gf_BPDayStart () {
    int lv_p;
    int lv_v;

    lv_p = 1;
    while ((lv_p <= 15)) {
        gv_bpRead[lv_p] = false;
        if ((PlayerGroupHasPlayer(gv_currentPlayers, lv_p) == true)) {
            lv_v = gv_visitation[lv_p];
            if ((lv_v >= 1) && (lv_v <= 15) && (lv_v != lv_p)) {
                gf_BPEventVisit(lv_p, lv_v);
            }

            // 巴士司机：两名被调换的人各记一条
            if ((gv_roles[lv_p][1] == 1) && (gv_roles[lv_p][0] == 9)) {
                if ((gv_visitation[lv_p] >= 1) && (gv_visitation[lv_p] <= 15)) {
                    gf_BPEventBus(gv_visitation[lv_p]);
                }

                if ((gv_visitation2[lv_p] >= 1) && (gv_visitation2[lv_p] <= 15)) {
                    gf_BPEventBus(gv_visitation2[lv_p]);
                }
            }
        }

        lv_p += 1;
    }
}

// 读者取一条
void gf_BPDraw (int lp_reader) {
    int lv_i;

    if ((gv_bpPublic == false)) {
        gf_CBSystemMessage(StringExternal("Param/Value/BPCMDNONE"), lp_reader, lp_reader, 0, SoundLink("Silent", -1), Color(0.00, 0.00, 0.00));
        return;
    }

    if ((gv_bpRead[lp_reader] == true)) {
        gf_CBSystemMessage(StringExternal("Param/Value/BPCMDDONE"), lp_reader, lp_reader, 0, SoundLink("Silent", -1), Color(0.00, 0.00, 0.00));
        return;
    }

    if ((gv_bpLogN <= 0)) {
        gf_CBSystemMessage(StringExternal("Param/Value/BPNONEWS"), lp_reader, lp_reader, 0, SoundLink("Silent", -1), Color(0.00, 0.00, 0.00));
        return;
    }

    gv_bpRead[lp_reader] = true;
    lv_i = RandomInt(0, gv_bpLogN - 1);
    gf_CBSystemMessage((StringExternal("Param/Value/BPNEWS") + gf_BPCountName(gv_bpCount[lv_i]) + gv_bpLog[lv_i]), lp_reader, lp_reader, 0, SoundLink("UI_TipSelect", -1), Color(0.00, 0.00, 0.00));
}

bool gt_BPPaper_Func (bool testConds, bool runActions) {
    int lv_p;
    playergroup lv_g;

    lv_p = EventPlayer();
    if ((gv_gameOver == true) || (lv_p < 1) || (lv_p > 15)) {
        return false;
    }

    if ((gv_roles[lv_p][1] == 1) && (gv_roles[lv_p][0] == 38)) {
        if ((gv_dayNumber < 2)) {
            gf_CBSystemMessage(StringExternal("Param/Value/BPCMDEARLY"), lv_p, lv_p, 0, SoundLink("Silent", -1), Color(0.00, 0.00, 0.00));
            return false;
        }

        if ((gv_bpPublic == false)) {
            gv_bpPublic = true;
            lv_g = gv_currentPlayers;
            lv_p = -1;
            while (true) {
                lv_p = PlayerGroupNextPlayer(lv_g, lv_p);
                if (lv_p < 0) { break; }
                gf_CBSystemMessage(StringExternal("Param/Value/BPCMDOK"), lv_p, lv_p, 0, SoundLink("UI_TipSelect", -1), Color(0.00, 0.00, 0.00));
            }
        }
        else {
            gf_CBSystemMessage(StringExternal("Param/Value/BPCMDDONE"), EventPlayer(), EventPlayer(), 0, SoundLink("Silent", -1), Color(0.00, 0.00, 0.00));
        }
        return false;
    }

    gf_BPDraw(EventPlayer());
    return false;
}

void gt_BPPaper_Init () {
    gt_BPPaper = TriggerCreate("gt_BPPaper_Func");
    TriggerAddEventChatMessage(gt_BPPaper, c_playerAny, "-paper", true);
}

'''
s = s[:start] + new_block + s[end:]

# 3) 原型补 gf_BPEventLook / gf_BPEventVisit / gf_BPEventBus / gf_BPCountName
rep('void gf_BPEventLook (int lp_investigator);\n',
    'void gf_BPEventLook (int lp_investigator);\nvoid gf_BPEventVisit (int lp_victim, int lp_visitor);\nvoid gf_BPEventBus (int lp_player);\ntext gf_BPCountName (int lp_n);\n')

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('bp step3 patched')
