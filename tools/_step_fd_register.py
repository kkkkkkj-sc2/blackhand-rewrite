# -*- coding: utf-8 -*-
"""饭店老板（城镇 1/36）第一步：注册 + 全局变量。

只做「让角色号存在且不报错」的部分；夜间逻辑/面板/票权/死亡在后续步骤。
每一步都断言锚点唯一，改完打印落点。
"""
import io
import re

G = r"I:\大肥鱼\外部项目\blackhand-rewrite-main\work\blackhand\CustomLogic.galaxy"

def load():
    return io.open(G, encoding="utf-8").read()

def save(s):
    io.open(G, "w", encoding="utf-8", newline="").write(s)

def must(s, needle, count=1):
    n = s.count(needle)
    assert n == count, f"锚点出现 {n} 次（期望 {count}）：{needle[:60]}"
    return n

s = load()
if "fandianlaoban" in s:
    print("脚本里已经有 fandianlaoban，先看看是不是重复执行")
    raise SystemExit

# 1) 城镇上界 35 -> 36
must(s, "gv_townMax = 35;")
s = s.replace("gv_townMax = 35;",
              "gv_townMax = 36;", 1)

# 2) 注册块：接在主教的 gv_bankSaveWeights[0][1][35] = 0.0; 之后
anchor = chr(10).join(["    gv_e78AAFE7BDAAE58FAFE883BD[1][35] = StringExternal(" + chr(34) + "Param/Value/ZJCRIME" + chr(34) + ");", "    gv_bankSaveWeights[0][1][35] = 0.0;"])
must(s, anchor)
block = anchor + """

// 饭店老板（城镇 1/36）
    gv_roleNameArray[1][36] = StringExternal("Param/Value/FDNAME");
    gv_roleDescriptionArray[1][36] = StringExternal("Param/Value/FDDESC");
    gv_roleInvestigatorArray[1][36][0] = StringExternal("Param/Value/FDINV1");
    gv_roleInvestigatorArray[1][36][1] = StringExternal("Param/Value/FDINV2");
    gv_e78AAFE7BDAAE58FAFE883BD[1][36] = StringExternal("Param/Value/FDCRIME");
    gv_bankSaveWeights[0][1][36] = 1.0;
    gv_roleWeights[1][36] = 1.0;"""
s = s.replace(anchor, block, 1)

# 3) 拼音表
anchor2 = 'gv_roleNameInput[1][35] = "zhujiao";'
must(s, anchor2)
s = s.replace(anchor2, anchor2 + '\n    gv_roleNameInput[1][36] = "fandianlaoban";', 1)

# 4) 全局变量：跟在 gv_fdFood 之前不存在，挂在 GF 区（找 gv_votes 定义处附近）
glob_anchor = "int[16] gv_votes;"
must(s, glob_anchor)
glob_block = """int[16] gv_votes;
// 饭店老板（1/36）：食物
int gv_fdStock;              // 老板手上还有几份
int[16] gv_fdFood;           // 每人手上几份
bool[16] gv_fdGrace;         // 生存者恩惠是否已用
bool gv_fdLootCried;         // 夺取播报是否已喊过
bool gv_fdRecoverCried;      // 回收播报是否已喊过"""
s = s.replace(glob_anchor, glob_block, 1)

save(s)

# 落点核对
s2 = load()
print("gv_townMax:", "36" if "gv_townMax = 36;" in s2 else "没改")
print("[1][36] 注册行:", s2.count("[1][36]"))
print("拼音行:", s2.count('"fandianlaoban"'))
print("新变量:", s2.count("gv_fdFood"), s2.count("gv_fdStock"))
print("花括号差:", s2.count("{") - s2.count("}"))
