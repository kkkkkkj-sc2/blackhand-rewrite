import io
import re

G = r"I:\大肥鱼\外部项目\blackhand-饭店老板\work\blackhand\CustomLogic.galaxy"
s = io.open(G, encoding="utf-8").read()

if "gv_fdFood[lp_player]" in s:
    print("已经加过")
    raise SystemExit

head = "int gf_BHVoteWeight (int lp_player) {"
i = s.index(head)

# 用花括号配平找函数结尾
depth = 0
j = i
while j < len(s):
    ch = s[j]
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            break
    j += 1
end = j  # 指向收尾的 }

body = s[i:end]
pos = body.rfind("return lv_weight;")
assert pos > 0, "没找到 return lv_weight;"

# 回退到该行行首
line_start = body.rfind("\n", 0, pos) + 1
inject = ("      // 饭店老板（1/36）：手上每份食物 +1 票；这份加成对老板本人无效。\n"
          "      if (((gv_roles[lp_player][1] != 1) || (gv_roles[lp_player][0] != 36)) && (gv_fdFood[lp_player] > 0)) {\n"
          "          lv_weight += gv_fdFood[lp_player];\n"
          "      }\n\n")

new_body = body[:line_start] + inject + body[line_start:]
s2 = s[:i] + new_body + s[end:]

io.open(G, "w", encoding="utf-8", newline="").write(s2)
print("插入完成；花括号差", s2.count("{") - s2.count("}"))
print("落在函数内:", s2.count("gv_fdFood[lp_player]"))
