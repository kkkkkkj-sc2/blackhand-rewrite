import io

G = r"I:\大肥鱼\外部项目\blackhand-饭店老板\work\blackhand\CustomLogic.galaxy"
s = io.open(G, encoding="utf-8").read()

if 'gv_roleBoxText[lv_a][0] == 36' in s or "Param/Value/FDBOX1" in s:
    print("卡面块已经加过")
    raise SystemExit

anchor = """        gv_roleBoxText[lv_a][2] = (StringToText("调查次数：") + IntToText(gv_shots[lv_a]));
        SoundPlay(SoundLink("Raven_What", -1), PlayerGroupSingle(lv_a), 100.0, 0.0);
    }
"""
assert s.count(anchor) == 1, "锚点出现 %d 次" % s.count(anchor)

block = anchor + """
    if ((gv_roles[lv_a][1] == 1) && (gv_roles[lv_a][0] == 36)) {
        gv_roleBoxText[lv_a][0] = (gv_roleBoxText[lv_a][0] + StringExternal("Param/Value/FDNAME"));
        gv_roleBoxText[lv_a][4] = StringExternal("Param/Value/FDBOX4");
        gv_roleBoxText[lv_a][1] = StringExternal("Param/Value/FDBOX1");
        gv_roleBoxText[lv_a][2] = StringExternal("Param/Value/FDBOX2A");
        gv_roleBoxText[lv_a][2] = (gv_roleBoxText[lv_a][2] + StringExternal("Param/Value/FDBOX2B"));
        gv_roleBoxText[lv_a][2] = (gv_roleBoxText[lv_a][2] + StringExternal("Param/Value/FDBOX2C"));
        gv_roleBoxText[lv_a][2] = (gv_roleBoxText[lv_a][2] + StringExternal("Param/Value/FDBOX2D"));
        SoundPlay(SoundLink("Hellion_What", -1), PlayerGroupSingle(lv_a), 100.0, 0.0);
    }
"""

s = s.replace(anchor, block, 1)
io.open(G, "w", encoding="utf-8", newline="").write(s)

i = s.index("Param/Value/FDBOX1")
print("插入落在字符", i, "；花括号差", s.count("{") - s.count("}"))
