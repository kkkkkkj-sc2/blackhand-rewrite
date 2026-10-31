import io

G = r"I:\大肥鱼\外部项目\blackhand-rewrite-main\work\blackhand\CustomLogic.galaxy"
s = io.open(G, encoding="utf-8").read()

if "gv_investigatorFDINV1" in s and "text gv_investigatorFDINV1;" in s:
    print("已经声明过")
    raise SystemExit

# 1) 声明（跟 CJINV 放一起）
decl_anchor = "text gv_investigatorCJINV1;"
assert s.count(decl_anchor) == 1, s.count(decl_anchor)
s = s.replace(decl_anchor,
              "text gv_investigatorFDINV1;\ntext gv_investigatorFDINV2;\n" + decl_anchor, 1)

# 2) 赋值（跟 CJINV 的赋值放一起）
asg_anchor = '    gv_investigatorCJINV1 = StringExternal("Param/Value/CJINV1");'
assert s.count(asg_anchor) == 1, s.count(asg_anchor)
s = s.replace(asg_anchor,
              '    gv_investigatorFDINV1 = StringExternal("Param/Value/FDINV1");\n'
              '    gv_investigatorFDINV2 = StringExternal("Param/Value/FDINV2");\n'
              + asg_anchor, 1)

io.open(G, "w", encoding="utf-8", newline="").write(s)
print("声明与赋值都补上了；花括号差:", s.count("{") - s.count("}"))
