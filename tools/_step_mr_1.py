# 城镇 商户 随机槽（池4/23）：名字/描述/抽签 + 自设列表条目
import io

# ---- 1) 文案 ----
p = 'work/blackhand/strings-bp.txt'
s = io.open(p, encoding='utf-8').read()
add = '''Param/Value/MRNAME=<c val="00FF00">城镇</c> <c val="88FFCC">商户</c>
Param/Value/MRDESC=只会出现城镇·商户分类的角色：饭店老板、流动摊贩、报纸店老板等。新增商户角色会自动进入这个槽位。
'''
if 'MRNAME' not in s:
    s = s.rstrip() + '\n' + add
io.open(p, 'w', encoding='utf-8', newline='').write(s)

# ---- 2) 星系脚本 ----
p = 'work/blackhand/CustomLogic.galaxy'
g = io.open(p, encoding='utf-8').read()


def rep(old, new, cnt=1):
    global g
    assert g.count(old) == cnt, (g.count(old), old[:70])
    g = g.replace(old, new, cnt)


# 名称/描述（挂在池4 22 号后面）
rep('''    gv_roleNameArray[4][22] = StringExternal("Param/Value/QLLEAD");
''', '''    gv_roleNameArray[4][22] = StringExternal("Param/Value/QLLEAD");
    gv_roleNameArray[4][23] = StringExternal("Param/Value/MRNAME");
    gv_roleDescriptionArray[4][23] = StringExternal("Param/Value/MRDESC");
''')

# 原型
rep('bool gf_VUInGame ();\n', 'bool gf_VUInGame ();\nvoid gf_BHPickMerchant ();\n')

# 抽签函数：新增商户角色在这里加一行
rep('''int gf_SQBucket (int lp_pool, int lp_role) {
''', '''// 城镇 商户 随机槽（池 4/23）：从商户角色里随机抽一个。新增商户角色时在表里加一行。
void gf_BHPickMerchant () {
    int[16] lv_list;
    int lv_n;

    lv_n = 3;
    lv_list[0] = 36;
    lv_list[1] = 37;
    lv_list[2] = 38;
    gv_bhPickPool = 1;
    gv_bhPickRole = lv_list[RandomInt(0, lv_n - 1)];
}

int gf_SQBucket (int lp_pool, int lp_role) {
''')

# 抽签分支：21/22/23 一起处理，23 走商户表
rep('''                                    if (((gv_rolesArray[lv_x] == 21) || (gv_rolesArray[lv_x] == 22))) {
                                        gf_BHPickLeader(gv_rolesArray[lv_x]);
''', '''                                    if (((gv_rolesArray[lv_x] == 21) || (gv_rolesArray[lv_x] == 22) || (gv_rolesArray[lv_x] == 23))) {
                                        if ((gv_rolesArray[lv_x] == 23)) {
                                            gf_BHPickMerchant();
                                        }
                                        else {
                                            gf_BHPickLeader(gv_rolesArray[lv_x]);
                                        }

''')

io.open(p, 'w', encoding='utf-8', newline='').write(g)

# ---- 3) 自设列表 ----
import json
p = 'work/roles-list.json'
d = json.load(io.open(p, encoding='utf-8'))
sec = d['sections'][9]
assert sec['category'] == 4, sec['category']
roles = [e['role'] for e in sec['entries']]
if 23 not in roles:
    sec['entries'].append({'role': 23, 'prefix': '83B203DA', 'suffix': '4CDB7830'})
    io.open(p, 'w', encoding='utf-8', newline='').write(json.dumps(d, ensure_ascii=False, indent=1))
print('merchant slot patched')
