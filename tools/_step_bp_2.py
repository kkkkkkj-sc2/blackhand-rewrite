# 报纸店老板 1/38 第二步：把调查结果也记进信息库
import io

p = 'work/blackhand/CustomLogic.galaxy'
s = io.open(p, encoding='utf-8').read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:70])
    s = s.replace(old, new, cnt)


# 1) 原型
rep('void gf_BPEventBlock (int lp_victim, int lp_blocker);\n',
    'void gf_BPEventBlock (int lp_victim, int lp_blocker);\nvoid gf_BPEventLook (int lp_investigator);\n')

# 2) 函数体：放在 gf_BPEventBlock 后面
rep('''void gf_BPEventBlock (int lp_victim, int lp_blocker) {
    if ((lp_victim < 1) || (lp_victim > 15) || (lp_blocker < 1) || (lp_blocker > 15)) {
        return;
    }

    gf_BPAdd((StringExternal("Param/Value/BPBLK1") + gf_BPRoleName(lp_victim) + StringExternal("Param/Value/BPBLK2") + gf_BPRoleName(lp_blocker) + StringExternal("Param/Value/BPBLK3")));
}
''', '''void gf_BPEventBlock (int lp_victim, int lp_blocker) {
    if ((lp_victim < 1) || (lp_victim > 15) || (lp_blocker < 1) || (lp_blocker > 15)) {
        return;
    }

    gf_BPAdd((StringExternal("Param/Value/BPBLK1") + gf_BPRoleName(lp_victim) + StringExternal("Param/Value/BPBLK2") + gf_BPRoleName(lp_blocker) + StringExternal("Param/Value/BPBLK3")));
}

// 调查结果原样抄一份进信息库：一名X查到了（调查免疫时显示阵营）角色
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

    gf_BPAdd((StringExternal("Param/Value/BPLOOK1") + gf_BPRoleName(lp_investigator) + StringExternal("Param/Value/BPLOOK2") + lv_seen + StringExternal("Param/Value/BPLOOK3")));
}
''')

# 3) 各调查角色的结果函数顶部挂钩
hooks = [
    'void gf_SKF_1_fushou (int lv_a) {',
    'void gf_SKF_1_jingzhang (int lv_a) {',
    'void gf_SKF_1_guanchazhe (int lv_a) {',
    'void gf_SKF_1_tanyuan (int lv_a) {',
    'void gf_SKF_1_lianbangtanyuan (int lv_a) {',
    'void gf_SKF_1_jiandie (int lv_a) {',
    'void gf_SKF_1_zhentan (int lv_a) {',
    'void gf_SKF_1_jianshizhe (int lv_a) {',
]
for h in hooks:
    assert s.count(h) == 1, h
    s = s.replace(h, h + '\n    gf_BPEventLook(lv_a);', 1)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('look hooks added')
