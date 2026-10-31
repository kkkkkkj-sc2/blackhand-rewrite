# -*- coding: utf-8 -*-
"""饭店老板（城镇 1/36）第 10-14 步：夜间做饭/送饭、发放、面板、死亡三路、白天报数。

锚点全部唯一断言；改完打印落点与括号配平。跑完必须 python tools/galaxy_lint.py。
"""
import io
import sys

G = r"I:\大肥鱼\外部项目\blackhand-饭店老板\work\blackhand\CustomLogic.galaxy"
T = r"I:\大肥鱼\外部项目\blackhand-饭店老板\work\blackhand\strings-fd.txt"

s = io.open(G, encoding="utf-8").read()
DRY = "--dry" in sys.argv


def rep_once(old, new, tag):
    global s
    n = s.count(old)
    assert n == 1, "[%s] 锚点出现 %d 次（期望 1）" % (tag, n)
    s = s.replace(old, new, 1)
    print("  ok %-28s +%d 字符" % (tag, len(new) - len(old)))


def insert_after_line(needle, text, tag):
    global s
    n = s.count(needle)
    assert n == 1, "[%s] 行锚点出现 %d 次（期望 1）: %s" % (tag, n, needle[:50])
    idx = s.index(needle)
    eol = s.index("\n", idx)
    s = s[:eol + 1] + text + s[eol + 1:]
    print("  ok %-28s +%d 字符" % (tag, len(text)))


if "fandianlaoban" not in s:
    raise SystemExit("脚本里没有 fandianlaoban，先跑注册步骤")

if "void gf_SKK_1_fandianlaoban" in s:
    raise SystemExit("夜间函数已经写过，先看看是不是重复执行")

# ---------------------------------------------------------------- 0) 全局变量
insert_after_line("bool gv_fdRecoverCried;", """int gv_fdCorpse;             // 待收的尸：处刑时记下，下一夜写进老板的访问
int[16] gv_fdCorpseTell;     // 今夜老板以「收尸」名义去过谁家（侦探播报用）
""", "全局变量")

# ---------------------------------------------------------------- 1) 开局初始化
rep_once("""void gf_InitializeVariables () {
    // Automatic Variable Declarations
    // Implementation""",
         """void gf_InitializeVariables () {
    // Automatic Variable Declarations
    int lv_fdInit;

    // Implementation""", "初始化-声明")

rep_once("""    gf_GSReset();
    gf_BHFactionReset();
    gf_BRReset();
""",
         """    gf_GSReset();
    gf_BHFactionReset();
    gf_BRReset();
    // 饭店老板（城镇 1/36）：开局两份食物
    gv_fdStock = 2;
    gv_fdCorpse = 0;
    gv_fdLootCried = false;
    gv_fdRecoverCried = false;
    lv_fdInit = 0;
    while ((lv_fdInit <= 15)) {
        gv_fdFood[lv_fdInit] = 0;
        gv_fdGrace[lv_fdInit] = false;
        gv_fdCorpseTell[lv_fdInit] = 0;
        lv_fdInit += 1;
    }
""", "初始化-赋值")

# ---------------------------------------------------------------- 2) 前向声明
rep_once("void gf_SKK_1_zhujiao (int lv_a);\n",
         """void gf_SKK_1_zhujiao (int lv_a);
void gf_RAFDLaobanActions (int lp_player);
void gf_SKR_1_fandianlaoban (int lv_a);
void gf_SKA_1_fandianlaoban (int lv_source, int lv_target);
void gf_SKP_1_fandianlaoban_2 (int lv_a);
void gf_SKK_1_fandianlaoban (int lv_a);
int gf_FDOwner ();
int gf_FDStage (int lp_player);
bool gf_FDIsSurvivor (int lp_player);
void gf_FDVisitorsClaim (int lp_owner);
void gf_FDOnDeath (int lp_player);
void gf_FDMorning ();
void gf_FDMorningDefer ();
void gt_FDMorning_Init ();
""", "前向声明")

# ---------------------------------------------------------------- 3) 触发器变量
insert_after_line("trigger gt_ZJMorning;", "trigger gt_FDMorning;\n", "触发器变量")

# ---------------------------------------------------------------- 4) 访问写入口（ClusterFuck 造访段）
rep_once("""            if ((gv_roles[lv_a][1] == 1) && (gv_roles[lv_a][0] == 34) && (gv_action[lv_a][0] > 0)) {
                gf_SKP_1_jijiuzhuanjia_2(lv_a);
            }
""",
         """            if ((gv_roles[lv_a][1] == 1) && (gv_roles[lv_a][0] == 34) && (gv_action[lv_a][0] > 0)) {
                gf_SKP_1_jijiuzhuanjia_2(lv_a);
            }

            if ((gv_roles[lv_a][1] == 1) && (gv_roles[lv_a][0] == 36)) {
                gf_SKP_1_fandianlaoban_2(lv_a);
            }
""", "访问写入")

# ---------------------------------------------------------------- 5) 夜间行动面板分发
rep_once("""                    if ((gv_roles[lv_a][0] == 35)) {
                        gf_SKR_1_zhujiao(lv_a);
                    }
""",
         """                    if ((gv_roles[lv_a][0] == 35)) {
                        gf_SKR_1_zhujiao(lv_a);
                    }

                    if ((gv_roles[lv_a][0] == 36)) {
                        gf_SKR_1_fandianlaoban(lv_a);
                    }
""", "面板分发")

# ---------------------------------------------------------------- 6) 面板点击分发
rep_once("""        if ((gv_roles[lv_source][1] == 1) && (gv_roles[lv_source][0] == 13) && (gv_action[lv_source][0] != lv_target) && (gv_variableOptions[lv_source][0] == 1)) {
            gf_SKA_1_yujing(lv_source, lv_target);
        }

        gf_BHConvertedActionNotice(lv_source, lv_old0, lv_old1);
""",
         """        if ((gv_roles[lv_source][1] == 1) && (gv_roles[lv_source][0] == 13) && (gv_action[lv_source][0] != lv_target) && (gv_variableOptions[lv_source][0] == 1)) {
            gf_SKA_1_yujing(lv_source, lv_target);
        }

        if ((gv_roles[lv_source][1] == 1) && (gv_roles[lv_source][0] == 36)) {
            gf_SKA_1_fandianlaoban(lv_source, lv_target);
        }

        gf_BHConvertedActionNotice(lv_source, lv_old0, lv_old1);
""", "点击分发")

# ---------------------------------------------------------------- 7) 夜间结算调用
rep_once("""        if ((gv_roles[lv_a][1] == 1) && (gv_roles[lv_a][0] == 35)) {
            gf_SKK_1_zhujiao(lv_a);
        }
""",
         """        if ((gv_roles[lv_a][1] == 1) && (gv_roles[lv_a][0] == 35)) {
            gf_SKK_1_zhujiao(lv_a);
        }

        if ((gv_roles[lv_a][1] == 1) && (gv_roles[lv_a][0] == 36)) {
            gf_SKK_1_fandianlaoban(lv_a);
        }
""", "夜间结算")

# ---------------------------------------------------------------- 8) 死亡钩子
rep_once("""    gv_dqTag[lp_player] = 0;
    if ((PlayerGroupHasPlayer(gv_alivePlayers, lp_player) == true) || (lp_gsStaged == true)) {
        lv_intensity = gv_dayNumber;
""",
         """    gv_dqTag[lp_player] = 0;
    if ((PlayerGroupHasPlayer(gv_alivePlayers, lp_player) == true) || (lp_gsStaged == true)) {
        gf_FDOnDeath(lp_player);
        lv_intensity = gv_dayNumber;
""", "死亡钩子")

# ---------------------------------------------------------------- 9) 侦探看收尸访问
rep_once("""                lv_go = gv_visitation[lp_target];
                lv_plan = gv_action[lp_target][0];
""",
         """                if (((gv_roles[lp_target][1] == 1) && (gv_roles[lp_target][0] == 36)) && (gv_fdCorpseTell[lp_target] > 0)) {
                    if ((gv_visitation2[lp_target] > 0) && (gv_visitation2[lp_target] != gv_visitation[lp_target])) {
                        gf_CBSystemMessage((StringExternal("Param/Value/FDDET2") + gf_BHDetName(gv_visitation[lp_target]) + StringExternal("Param/Value/FDDET3") + gf_BHDetName(gv_visitation2[lp_target]) + StringExternal("Param/Value/DTEND")), lp_observer, lp_observer, 0, SoundLink("UI_TipSelect", -1), Color(0,0,0));
                    }
                    else {
                        gf_CBSystemMessage((StringExternal("Param/Value/FDDET1") + gf_BHDetName(gv_fdCorpseTell[lp_target]) + StringExternal("Param/Value/FDDET4")), lp_observer, lp_observer, 0, SoundLink("UI_TipSelect", -1), Color(0,0,0));
                    }
                    return;
                }

                lv_go = gv_visitation[lp_target];
                lv_plan = gv_action[lp_target][0];
""", "侦探收尸")

# ---------------------------------------------------------------- 10) 触发器注册
insert_after_line("    gt_ZJMorning_Init();", "    gt_FDMorning_Init();\n", "触发器注册")

# ---------------------------------------------------------------- 11) 白天私发
insert_after_line("    gf_ZJMorningDefer();", "    gf_FDMorningDefer();\n", "白天私发调用")

# ---------------------------------------------------------------- 12) 新函数块
FUNCS = r"""
// ===== 饭店老板（城镇 1/36）：食物 = 手上每份 +1 票（老板自己那份不算，见 gf_BHVoteWeight）=====

int gf_FDOwner () {
    int lv_a;

    lv_a = 1;
    while ((lv_a <= 15)) {
        if ((gv_roles[lv_a][1] == 1) && (gv_roles[lv_a][0] == 36) && (PlayerGroupHasPlayer(gv_alivePlayers, lv_a) == true)) {
            return lv_a;
        }

        lv_a += 1;
    }
    return 0;
}

// 发放优先级：城镇 1 → 黑手党 2 → 三合会 3 → 中立 4
int gf_FDStage (int lp_player) {
    int lv_f;

    lv_f = gf_BHFaction(lp_player);
    if ((lv_f == 1)) {
        return 1;
    }

    if ((lv_f == 2)) {
        return 2;
    }

    if ((lv_f == 5)) {
        return 3;
    }

    return 4;
}

bool gf_FDIsSurvivor (int lp_player) {
    if ((lp_player < 1) || (lp_player > 15)) {
        return false;
    }

    return ((gv_roles[lp_player][1] == 3) && (gv_roles[lp_player][0] == 2));
}

// 夜里出门送饭写到目标家；在家做饭写自己家。处刑收来的尸首先去一趟再回家/再送饭。
void gf_SKP_1_fandianlaoban_2 (int lv_a) {
    int lv_t;
    int lv_dead;

    if ((lv_a < 1) || (lv_a > 15)) {
        return;
    }

    lv_dead = gv_fdCorpse;
    gv_fdCorpse = 0;
    if ((gv_jailed[lv_a] != 0)) {
        gf_BHVisitNone(lv_a);
        return;
    }

    lv_t = gv_action[lv_a][0];
    if ((lv_t < 1) || (lv_t > 15) || (lv_t == lv_a)) {
        lv_t = 0;
    }

    if ((lv_dead > 0) && (lv_dead <= 15) && (lv_dead != lv_a)) {
        gv_fdCorpseTell[lv_a] = lv_dead;
        gf_BHVisit(lv_a, lv_dead);
        if ((lv_t > 0)) {
            gf_BHVisit2(lv_a, lv_t);
        }
    }
    else {
        if ((lv_t > 0)) {
            gf_BHVisit(lv_a, lv_t);
        }
        else {
            gf_BHVisitSelf(lv_a);
        }
    }
}

// 上门领饭：生存者白贴一份（不扣库存、记恩惠）；其余按阵营排档，同档超额随机抽。
void gf_FDVisitorsClaim (int lp_owner) {
    int lv_p;
    int lv_s;
    int lv_n;
    int lv_pick;
    int[16] lv_list;

    if ((lp_owner < 1) || (lp_owner > 15)) {
        return;
    }

    if ((gv_jailed[lp_owner] != 0)) {
        return;
    }

    lv_p = 1;
    while ((lv_p <= 15)) {
        if ((lv_p != lp_owner) && (PlayerGroupHasPlayer(gv_alivePlayers, lv_p) == true) && (gv_jailed[lv_p] == 0) && (gv_visitation[lv_p] == lp_owner) && (gf_FDIsSurvivor(lv_p) == true)) {
            gv_fdFood[lv_p] += 1;
            if ((gv_fdGrace[lv_p] == false)) {
                gv_fdGrace[lv_p] = true;
            }
        }

        lv_p += 1;
    }

    lv_s = 1;
    while ((lv_s <= 4)) {
        lv_n = 0;
        lv_p = 1;
        while ((lv_p <= 15)) {
            if ((lv_p != lp_owner) && (PlayerGroupHasPlayer(gv_alivePlayers, lv_p) == true) && (gv_jailed[lv_p] == 0) && (gv_visitation[lv_p] == lp_owner) && (gf_FDIsSurvivor(lv_p) == false) && (gf_FDStage(lv_p) == lv_s)) {
                lv_n += 1;
                lv_list[lv_n] = lv_p;
            }

            lv_p += 1;
        }
        while (true) {
            if ((gv_fdStock <= 0) || (lv_n <= 0)) { break; }
            lv_pick = RandomInt(1, lv_n);
            gv_fdFood[lv_list[lv_pick]] += 1;
            gv_fdStock -= 1;
            lv_list[lv_pick] = lv_list[lv_n];
            lv_n -= 1;
        }
        lv_s += 1;
    }
}

// 夜间结算：先出门送那一份，再收上门来领的；被限制只能在家做饭。
void gf_SKK_1_fandianlaoban (int lv_a) {
    int lv_t;
    int lv_go;

    if ((lv_a < 1) || (lv_a > 15)) {
        return;
    }

    if ((gv_diedAtNight[lv_a] == true) || (PlayerGroupHasPlayer(gv_alivePlayers, lv_a) == false)) {
        gv_fdCorpseTell[lv_a] = 0;
        return;
    }

    if ((gv_jailed[lv_a] != 0)) {
        gv_fdCorpseTell[lv_a] = 0;
        return;
    }

    if ((gv_roleblocked[lv_a] != 0)) {
        gv_fdCorpseTell[lv_a] = 0;
        gv_fdStock += 1;
        gf_FDVisitorsClaim(lv_a);
        return;
    }

    lv_t = gv_action[lv_a][0];
    if ((lv_t < 1) || (lv_t > 15) || (lv_t == lv_a)) {
        lv_t = 0;
    }

    lv_go = gv_visitation[lv_a];
    if ((gv_visitation2[lv_a] > 0)) {
        lv_go = gv_visitation2[lv_a];
    }
    if ((lv_go < 1) || (lv_go > 15) || (lv_go == lv_a)) {
        lv_go = 0;
    }

    if ((lv_t > 0) && (gv_fdStock > 0) && (lv_go > 0) && (PlayerGroupHasPlayer(gv_alivePlayers, lv_go) == true)) {
        gv_fdStock -= 1;
        gv_fdFood[lv_go] += 1;
    }
    else {
        gv_fdStock += 1;
    }

    gf_FDVisitorsClaim(lv_a);
}

// 死亡三路：击杀→凶手夺走；自杀/处刑（以及其他白天死）→回老板手里；两句各只喊一次。
void gf_FDOnDeath (int lp_player) {
    int lv_food;
    int lv_killer;
    int lv_owner;
    int lv_p;
    playergroup lv_g;

    if ((lp_player < 1) || (lp_player > 15)) {
        return;
    }

    if ((gv_roles[lp_player][1] == 1) && (gv_roles[lp_player][0] == 36)) {
        gv_fdCorpseTell[lp_player] = 0;
    }

    lv_food = gv_fdFood[lp_player];
    if ((lv_food <= 0)) {
        return;
    }

    gv_fdFood[lp_player] = 0;
    lv_killer = gv_bhNightKiller[lp_player];
    if ((gv_isNight == true) && (lv_killer > 0) && (lv_killer != lp_player)) {
        gv_fdFood[lv_killer] += lv_food;
        if ((gv_fdLootCried == false)) {
            gv_fdLootCried = true;
            lv_g = gv_currentPlayers;
            lv_p = -1;
            while (true) {
                lv_p = PlayerGroupNextPlayer(lv_g, lv_p);
                if (lv_p < 0) { break; }
                gf_CBSystemMessage(StringExternal("Param/Value/FDLOOT"), lv_p, 0, 0, SoundLink("UI_TipSelect", -1), Color(0,0,0));
            }
        }
        return;
    }

    lv_owner = gf_FDOwner();
    if ((lv_owner > 0) && (lv_owner != lp_player)) {
        gv_fdStock += lv_food;
        if ((gv_fdRecoverCried == false)) {
            gv_fdRecoverCried = true;
            lv_g = gv_currentPlayers;
            lv_p = -1;
            while (true) {
                lv_p = PlayerGroupNextPlayer(lv_g, lv_p);
                if (lv_p < 0) { break; }
                gf_CBSystemMessage(StringExternal("Param/Value/FDRECOVER"), lv_p, 0, 0, SoundLink("UI_TipSelect", -1), Color(0,0,0));
            }
        }
    }
    if ((gv_isNight == false)) {
        gv_fdCorpse = lp_player;
    }
}

// 白天私发：每个活人手上几份食物。
void gf_FDMorning () {
    int lv_a;
    int lv_p;
    bool lv_any;
    text lv_line;

    lv_p = 1;
    while ((lv_p <= 15)) {
        gv_fdCorpseTell[lv_p] = 0;
        lv_p += 1;
    }

    lv_a = gf_FDOwner();
    if ((lv_a <= 0)) {
        return;
    }

    lv_any = false;
    lv_p = 1;
    while ((lv_p <= 15)) {
        if ((lv_p != lv_a) && (PlayerGroupHasPlayer(gv_alivePlayers, lv_p) == true) && (gv_fdFood[lv_p] > 0)) {
            lv_any = true;
        }

        lv_p += 1;
    }
    if ((lv_any == false)) {
        return;
    }

    gf_CBSystemMessage(StringExternal("Param/Value/FDCOUNT"), lv_a, 0, 0, SoundLink("UI_ObjectiveUpdate", -1), Color(0,0,0));
    lv_p = 1;
    while ((lv_p <= 15)) {
        if ((lv_p != lv_a) && (PlayerGroupHasPlayer(gv_alivePlayers, lv_p) == true) && (gv_fdFood[lv_p] > 0)) {
            lv_line = (TextWithColor((StringToText(gv_number[lv_p]) + StringToText(".") + StringToText(gv_name[lv_p])), libNtve_gf_ConvertPlayerColorToColor(gv_playerColor[lv_p])) + StringToText(" ") + IntToText(gv_fdFood[lv_p]) + StringExternal("Param/Value/FDCOUNTEND"));
            gf_CBSystemMessage(lv_line, lv_a, 0, 0, SoundLink("Silent", -1), Color(0,0,0));
        }

        lv_p += 1;
    }
}

// 行动面板：别人身上是「出门送饭」，自己身上是「取消」（回做饭）。
void gf_RAFDLaobanActions (int lp_player) {
    int lv_a;
    bool lv_deliver;

    gf_RANoActions(lp_player);
    if ((gv_jailed[lp_player] != 0) || (gv_fdStock <= 0)) {
        return;
    }

    lv_deliver = ((gv_action[lp_player][0] > 0) && (gv_action[lp_player][0] != lp_player));
    lv_a = 1;
    while ((lv_a <= 15)) {
        if ((lv_a == lp_player)) {
            if ((lv_deliver == true)) {
                libNtve_gf_SetDialogItemText(gv_actionDialogItem[lv_a][5], StringExternal("Param/Value/FDCANCEL"), PlayerGroupSingle(lp_player));
                libNtve_gf_SetDialogItemTooltip(gv_actionDialogItem[lv_a][5], StringExternal("Param/Value/FDCOOKTIP"), PlayerGroupSingle(lp_player));
                libNtve_gf_SetDialogItemColor(gv_actionDialogItem[lv_a][5], Color(50.20, 50.20, 50.20), PlayerGroupSingle(lp_player));
                DialogControlSetSize(gv_actionDialogItem[lv_a][5], PlayerGroupSingle(lp_player), 120, 30);
                libNtve_gf_SetDialogItemImage(gv_actionDialogItem[lv_a][5], "ActionNormal.dds", PlayerGroupSingle(lp_player));
                libNtve_gf_SetDialogItemImage2(gv_actionDialogItem[lv_a][5], "ActionHighlight.dds", PlayerGroupSingle(lp_player));
                DialogControlSetVisible(gv_actionDialogItem[lv_a][5], PlayerGroupSingle(lp_player), true);
            }
        }
        else {
            if ((PlayerGroupHasPlayer(gv_alivePlayers, lv_a) == true) && (gv_action[lp_player][0] != lv_a)) {
                libNtve_gf_SetDialogItemText(gv_actionDialogItem[lv_a][5], StringExternal("Param/Value/FDDELIVER"), PlayerGroupSingle(lp_player));
                libNtve_gf_SetDialogItemTooltip(gv_actionDialogItem[lv_a][5], StringExternal("Param/Value/FDDELIVERTIP"), PlayerGroupSingle(lp_player));
                libNtve_gf_SetDialogItemColor(gv_actionDialogItem[lv_a][5], Color(21.57, 65.88, 40.00), PlayerGroupSingle(lp_player));
                DialogControlSetSize(gv_actionDialogItem[lv_a][5], PlayerGroupSingle(lp_player), 120, 30);
                libNtve_gf_SetDialogItemImage(gv_actionDialogItem[lv_a][5], "ActionNormal.dds", PlayerGroupSingle(lp_player));
                libNtve_gf_SetDialogItemImage2(gv_actionDialogItem[lv_a][5], "ActionHighlight.dds", PlayerGroupSingle(lp_player));
                DialogControlSetVisible(gv_actionDialogItem[lv_a][5], PlayerGroupSingle(lp_player), true);
            }
        }

        lv_a += 1;
    }
}

// 夜里开场：目标死了就回到做饭；没食物只提示一句。
void gf_SKR_1_fandianlaoban (int lv_a) {
    int lv_t;

    if ((lv_a < 1) || (lv_a > 15)) {
        return;
    }

    lv_t = gv_action[lv_a][0];
    if ((lv_t > 0) && ((lv_t == lv_a) || (PlayerGroupHasPlayer(gv_alivePlayers, lv_t) == false))) {
        gv_action[lv_a][0] = 0;
    }

    if ((gv_jailed[lv_a] == 0) && (gv_fdStock <= 0)) {
        gf_CBSystemMessage(StringExternal("Param/Value/FDNOFOOD"), lv_a, lv_a, 0, SoundLink("Silent", -1), Color(0,0,0));
    }

    gf_RAFDLaobanActions(lv_a);
}

void gf_SKA_1_fandianlaoban (int lv_source, int lv_target) {
    if ((lv_source < 1) || (lv_source > 15) || (lv_target < 1) || (lv_target > 15)) {
        return;
    }

    if ((gv_jailed[lv_source] != 0) || (PlayerGroupHasPlayer(gv_alivePlayers, lv_source) == false)) {
        return;
    }

    if ((lv_target == lv_source)) {
        gv_action[lv_source][0] = 0;
        gf_RAFDLaobanActions(lv_source);
        return;
    }

    if ((PlayerGroupHasPlayer(gv_alivePlayers, lv_target) == false)) {
        return;
    }

    if ((gv_fdStock <= 0)) {
        gf_CBSystemMessage(StringExternal("Param/Value/FDNOFOOD"), lv_source, lv_source, 0, SoundLink("Silent", -1), Color(0,0,0));
        return;
    }

    if ((gv_action[lv_source][0] != lv_target)) {
        gv_action[lv_source][0] = lv_target;
        gf_CBSystemMessage((StringExternal("Param/Value/FDPICK") + TextWithColor((StringToText(gv_number[lv_target]) + StringToText(".") + StringToText(gv_name[lv_target])), libNtve_gf_ConvertPlayerColorToColor(gv_playerColor[lv_target])) + StringExternal("Param/Value/FDPICKEND")), lv_source, lv_source, 0, SoundLink("UI_TipSelect", -1), Color(0,0,0));
    }

    gf_RAFDLaobanActions(lv_source);
}

// 白天私发延迟到开场消息之后（同主教那套，避免被夜间转场压暗）。
trigger gt_FDMorning = null;

bool gt_FDMorning_Func (bool testConds, bool runActions) {
    if (!runActions) {
        return true;
    }

    Wait(1.5, c_timeGame);
    gf_FDMorning();
    return true;
}

void gt_FDMorning_Init () {
    gt_FDMorning = TriggerCreate("gt_FDMorning_Func");
}

void gf_FDMorningDefer () {
    TriggerExecute(gt_FDMorning, false, false);
}
"""

rep_once("""void gf_ZJMorningDefer () {
    TriggerExecute(gt_ZJMorning, false, false);
}
""",
         """void gf_ZJMorningDefer () {
    TriggerExecute(gt_ZJMorning, false, false);
}
""" + FUNCS, "函数块")

# ---------------------------------------------------------------- 13) 文案
strings = io.open(T, encoding="utf-8").read()
if "FDDET1" in strings:
    raise SystemExit("strings-fd 里已经有 FDDET，先看看是不是重复执行")
if not strings.endswith("\n"):
    strings += "\n"
strings += """// 侦探看「老板去收尸」：单访问（做饭）与双访问（送饭）
Param/Value/FDDET1=<s val="ModLeftSize16Bold"><c val="DDBB44">你的目标访问了 </c>
Param/Value/FDDET4=<c val="DDBB44">，然后又回来了……</c></s>
Param/Value/FDDET2=<s val="ModLeftSize16Bold"><c val="DDBB44">你的目标同时访问了 </c>
Param/Value/FDDET3=<c val="DDBB44"> 和 </c>
"""
if not DRY:
    io.open(T, "w", encoding="utf-8", newline="").write(strings)

# ---------------------------------------------------------------- 落点核对
opens = s.count("{")
closes = s.count("}")
print("大括号: { %d } %d 差 %d" % (opens, closes, opens - closes))

for tag in ("gf_SKP_1_fandianlaoban_2(lv_a);", "gf_SKR_1_fandianlaoban(lv_a);",
            "gf_SKA_1_fandianlaoban(lv_source, lv_target);", "gf_SKK_1_fandianlaoban(lv_a);",
            "gf_FDOnDeath(lp_player);", "gf_FDMorningDefer();", "gt_FDMorning_Init();"):
    print("  调用点 %-40s %d 次" % (tag, s.count(tag)))

print("  定义 gf_FDOwner %d / gf_FDOnDeath %d / gt_FDMorning %d" % (
    s.count("int gf_FDOwner () {"), s.count("void gf_FDOnDeath (int lp_player) {"),
    s.count("trigger gt_FDMorning = null;")))

if not DRY:
    io.open(G, "w", encoding="utf-8", newline="").write(s)
    print("写入完成")
else:
    print("DRY RUN：没有写文件")
