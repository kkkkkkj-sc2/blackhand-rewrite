# 报纸店老板 1/38 第一步：注册 / 卡面 / 命令 / 信息日志 / 基础事件
import io

p = 'work/blackhand/CustomLogic.galaxy'
s = io.open(p, encoding='utf-8').read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:70])
    s = s.replace(old, new, cnt)


# 1) 全局
rep('text gv_investigatorVUINV2;\n', '''text gv_investigatorVUINV2;
text[64] gv_bpLog;           // 报纸店老板(1/38)：昨夜的信息
int gv_bpLogN;
bool gv_bpPublic;            // 报纸是否已公示
bool[16] gv_bpRead;          // 该玩家今天是否已读过报
text gv_investigatorBPINV1;
text gv_investigatorBPINV2;
trigger gt_BPPaper;
''')

# 2) 城镇上界
rep('    gv_townMax = 37; // 流动摊贩(1/37)：城镇权重、选项保存与累计抽签上界',
    '    gv_townMax = 38; // 报纸店老板(1/38)：城镇权重、选项保存与累计抽签上界')

# 3) 注册
rep('''    gv_roleWeights[1][37] = 1.0;
''', '''    gv_roleWeights[1][37] = 1.0;

// 报纸店老板（城镇 1/38）
    gv_roleNameArray[1][38] = StringExternal("Param/Value/BPNAME");
    gv_roleDescriptionArray[1][38] = StringExternal("Param/Value/BPDESC");
    gv_investigatorBPINV1 = StringExternal("Param/Value/BPINV1");
    gv_investigatorBPINV2 = StringExternal("Param/Value/BPINV2");
    gv_roleInvestigatorArray[1][38][0] = gv_investigatorBPINV1;
    gv_roleInvestigatorArray[1][38][1] = gv_investigatorBPINV2;
    gv_e78AAFE7BDAAE58FAFE883BD[1][38] = StringExternal("Param/Value/BPCRIME");
    gv_bankSaveWeights[0][1][38] = 1.0;
    gv_roleWeights[1][38] = 1.0;
''')

# 4) 拼音
rep('    gv_roleNameInput[1][37] = "liudongtanfan";\n',
    '    gv_roleNameInput[1][37] = "liudongtanfan";\n    gv_roleNameInput[1][38] = "baozhidianlaoban";\n')

# 5) 原型
rep('void gf_VUMorning ();\n', '''void gf_VUMorning ();
void gf_BPAdd (text lp_line);
void gf_BPClear ();
void gf_BPDayStart ();
void gf_BPEventAttack (int lp_victim, int lp_killer);
void gf_BPEventHeal (int lp_victim, int lp_healer);
void gf_BPEventBlock (int lp_victim, int lp_blocker);
void gf_BPDraw (int lp_reader);
text gf_BPRoleName (int lp_player);
token gf_BPNameOf (int lp_player);
void gt_BPPaper_Init ();
''')

# 6) 卡面
rep('''        gv_roleBoxText[lv_a][2] = (gv_roleBoxText[lv_a][2] + StringExternal("Param/Value/VUBOX2F"));
        SoundPlay(SoundLink("Hellion_What", -1), PlayerGroupSingle(lv_a), 100.0, 0.0);
    }
''', '''        gv_roleBoxText[lv_a][2] = (gv_roleBoxText[lv_a][2] + StringExternal("Param/Value/VUBOX2F"));
        SoundPlay(SoundLink("Hellion_What", -1), PlayerGroupSingle(lv_a), 100.0, 0.0);
    }

    if ((gv_roles[lv_a][1] == 1) && (gv_roles[lv_a][0] == 38)) {
        gv_roleBoxText[lv_a][0] = StringExternal("Param/Value/BPALIGN");
        gv_roleBoxText[lv_a][4] = StringExternal("Param/Value/BPBOX4");
        gv_roleBoxText[lv_a][1] = StringExternal("Param/Value/BPBOX1");
        gv_roleBoxText[lv_a][2] = StringExternal("Param/Value/BPBOX2A");
        gv_roleBoxText[lv_a][2] = (gv_roleBoxText[lv_a][2] + StringExternal("Param/Value/BPBOX2B"));
        gv_roleBoxText[lv_a][2] = (gv_roleBoxText[lv_a][2] + StringExternal("Param/Value/BPBOX2C"));
        gv_roleBoxText[lv_a][2] = (gv_roleBoxText[lv_a][2] + StringExternal("Param/Value/BPBOX2D"));
        gv_roleBoxText[lv_a][2] = (gv_roleBoxText[lv_a][2] + StringExternal("Param/Value/BPBOX2E"));
        SoundPlay(SoundLink("Hellion_What", -1), PlayerGroupSingle(lv_a), 100.0, 0.0);
    }
''')

# 7) 审查页猜身份映射
rep('''        else if ((lp_index == 34)) {
            lv_role = 37;
        }
        else if ((lp_index >= 35)) {
            lv_role = 0;
        }
''', '''        else if ((lp_index == 34)) {
            lv_role = 37;
        }
        else if ((lp_index == 35)) {
            lv_role = 38;
        }
        else if ((lp_index >= 36)) {
            lv_role = 0;
        }
''')
rep('    const int auto1E31EC9C_ae = 34;\n', '    const int auto1E31EC9C_ae = 35;\n')

# 8) 函数体（放在流动摊贩块前面）
anchor = '''// 新增角色（非原图抽取）：城镇 1/37 流动摊贩。
// 一次性次数型能力是否已经用掉（义警子弹、天选者雷击）。
'''
assert s.count(anchor) == 1

body = '''// 新增角色（非原图抽取）：城镇 1/38 报纸店老板。
text gf_BPRoleName (int lp_player) {
    return gv_roleNameArray[gv_roles[lp_player][1]][gv_roles[lp_player][0]];
}

token gf_BPNameOf (int lp_player) {
    return StringToText("");
}

void gf_BPAdd (text lp_line) {
    if ((gv_bpLogN >= 64)) {
        return;
    }

    gv_bpLog[gv_bpLogN] = lp_line;
    gv_bpLogN += 1;
}

void gf_BPClear () {
    gv_bpLogN = 0;
}

void gf_BPEventAttack (int lp_victim, int lp_killer) {
    if ((lp_victim < 1) || (lp_victim > 15) || (lp_killer < 1) || (lp_killer > 15)) {
        return;
    }

    gf_BPAdd((StringExternal("Param/Value/BPATK1") + gf_BPRoleName(lp_victim) + StringExternal("Param/Value/BPATK2") + gf_BPRoleName(lp_killer) + StringExternal("Param/Value/BPATK3")));
}

void gf_BPEventHeal (int lp_victim, int lp_healer) {
    if ((lp_victim < 1) || (lp_victim > 15) || (lp_healer < 1) || (lp_healer > 15)) {
        return;
    }

    gf_BPAdd((StringExternal("Param/Value/BPHEAL1") + gf_BPRoleName(lp_victim) + StringExternal("Param/Value/BPHEAL2") + gf_BPRoleName(lp_healer) + StringExternal("Param/Value/BPHEAL3")));
}

void gf_BPEventBlock (int lp_victim, int lp_blocker) {
    if ((lp_victim < 1) || (lp_victim > 15) || (lp_blocker < 1) || (lp_blocker > 15)) {
        return;
    }

    gf_BPAdd((StringExternal("Param/Value/BPBLK1") + gf_BPRoleName(lp_victim) + StringExternal("Param/Value/BPBLK2") + gf_BPRoleName(lp_blocker) + StringExternal("Param/Value/BPBLK3")));
}

// 白天开场：重置领报额度，并把昨晚的访问补进报纸
void gf_BPDayStart () {
    int lv_p;
    int lv_v;

    lv_p = 1;
    while ((lv_p <= 15)) {
        gv_bpRead[lv_p] = false;
        if ((PlayerGroupHasPlayer(gv_currentPlayers, lv_p) == true)) {
            lv_v = gv_visitation[lv_p];
            if ((lv_v >= 1) && (lv_v <= 15) && (lv_v != lv_p)) {
                gf_BPAdd((StringExternal("Param/Value/BPVIS1") + gf_BPRoleName(lv_p) + StringExternal("Param/Value/BPVIS2") + gf_BPRoleName(lv_v) + StringExternal("Param/Value/BPVIS3")));
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
    gf_CBSystemMessage((StringExternal("Param/Value/BPNEWS") + gv_bpLog[lv_i]), lp_reader, lp_reader, 0, SoundLink("UI_TipSelect", -1), Color(0.00, 0.00, 0.00));
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

s = s.replace(anchor, body + anchor, 1)

# 9) 命令初始化调用
rep('    gt_ASMayorAction_Init();\n', '    gt_ASMayorAction_Init();\n    gt_BPPaper_Init();\n')

# 10) 夜里清空报纸 + 白天补访问、重置额度
rep('''    // Implementation
    gv_dqTag[lp_player] = 0;
''', '''    // Implementation
    gv_dqTag[lp_player] = 0;
''', 1)

# gf_SequencePrep 顶部清空报纸
i = s.index('void gf_SequencePrep () {')
j = s.index('    // Implementation\n', i)
s = s[:j] + '    gf_BPClear();\n' + s[j:]

# 白天开场
rep('''void gf_FDMorning () {
    int lv_a;
    int lv_p;
    text lv_line;

    gf_VUMorning();
''', '''void gf_FDMorning () {
    int lv_a;
    int lv_p;
    text lv_line;

    gf_VUMorning();
    gf_BPDayStart();
''')

# 11) 事件钩子：限制
rep('''void gf_BHSetBlocker (int lp_target, int lp_blocker) {
    gv_roleblocked[lp_target] = lp_blocker;
}
''', '''void gf_BHSetBlocker (int lp_target, int lp_blocker) {
    gv_roleblocked[lp_target] = lp_blocker;
    if ((lp_blocker > 0) && (lp_target > 0)) {
        gf_BPEventBlock(lp_target, lp_blocker);
    }
}
''')

# 12) 事件钩子：救治
rep('''            gv_healing[gv_visitation[lv_a]] += 1;
            gf_DEBUG(("healing is set to: " + IntToString(gv_healing[gv_visitation[lv_a]])));
''', '''            gf_BPEventHeal(gv_visitation[lv_a], lv_a);
            gv_healing[gv_visitation[lv_a]] += 1;
            gf_DEBUG(("healing is set to: " + IntToString(gv_healing[gv_visitation[lv_a]])));
''')

# 13) 事件钩子：攻击（夜里的杀）
rep('''    // Implementation
    gv_dqTag[lp_player] = 0;
    if ((PlayerGroupHasPlayer(gv_alivePlayers, lp_player) == true) || (lp_gsStaged == true)) {
''', '''    // Implementation
    gv_dqTag[lp_player] = 0;
    if ((gv_isNight == true) && (gv_bhNightKiller[lp_player] > 0) && (gv_bhNightKiller[lp_player] != lp_player)) {
        gf_BPEventAttack(lp_player, gv_bhNightKiller[lp_player]);
    }

    if ((PlayerGroupHasPlayer(gv_alivePlayers, lp_player) == true) || (lp_gsStaged == true)) {
''')

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('bp step1 patched')
