#!/usr/bin/env python3
"""Structural peripheral checks for 恶棍 (3/28); not an SC2 runtime test."""
import ast
import json
import re
from pathlib import Path

from role_gen import Script, load_gamestrings

ROOT = Path(__file__).resolve().parent.parent


def main():
    script = Script()
    source = "\n".join(script.lines)
    spec = json.loads((ROOT / "roles/egun.json").read_text())
    strings = dict(
        line.split("=", 1)
        for line in (ROOT / "work/blackhand/strings-eg.txt").read_text().splitlines()
        if line.startswith("Param/Value/")
    )
    builder = ast.parse((ROOT / "tools/boot2_build.py").read_text())
    required = next(
        ast.literal_eval(node.value)
        for node in builder.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "MUST_HAVE_KEYS" for t in node.targets)
    )
    assert set(strings) <= set(required)
    assert spec["options"] == [] and spec["flag10"] is False
    assert spec["investigator"] == ["E4B88DE696ADE7A7BBE58AA81", "E4B88DE696ADE7A7BBE58AA82"]
    assert strings["Param/Value/EGBOX1"] == "每晚选择一个人，他负伤。"
    traits = [
        "负伤者被访问后会死亡。",
        "负伤效果对有夜间无敌者无效，且他会知道你是谁。",
        "负伤会从获得该效果的第二天开始生效。",
        "医生会治愈负伤状态。",
        "被你选择的人知道他负伤了。",
        "你的访问不会导致负伤者死亡。",
        "你拥有一次夜间无敌机会。",
    ]
    assert strings["Param/Value/EGBOX2"] == "".join("<n/>- " + trait for trait in traits)
    assert strings["Param/Value/EGBOX6"] == "存活并看到城镇全部死亡。"
    assert strings["Param/Value/EGCRIME"] == "破坏治安"
    assert strings["Param/Value/EGTIP"] == "使其负伤"
    assert strings["Param/Value/EGCANCELTIP"] == "取消"
    assert strings["Param/Value/EGNIGHT"] == '<s val="ModLeftSize16"><c val="FF0000">你听见痛苦的呻吟声...</c></s>'
    merged = load_gamestrings()
    assert "保镖" in merged["Param/Value/D9495B72"] and "恶棍" in merged["Param/Value/D9495B72"]
    assert all("恶棍" in value for key, value in merged.items()
               if key.startswith("Param/Value/") and value.startswith("- 那暗示他会是个巴士司机、保镖"))
    assert 'gv_roleWeights[3][28] = 0.0;' in source
    assert 'gv_bankSaveWeights[0][3][28] = 0.0;' in source
    assert 'gv_bankRoleAchievements[lv_a][3][28]' not in source

    panel = "\n".join(script.body("gf_RAEgunActions"))
    click = "\n".join(script.body("gf_SKA_3_egun"))
    prep = "\n".join(script.body("gf_SKP_3_egun"))
    setup = "\n".join(script.body("gf_SKN_3_egun"))
    assert '(lv_a != lp_player)' in panel and 'autoEGRA_ae = 15;' in panel
    assert 'DialogControlSetEnabled(gv_switchButtonItem, PlayerGroupSingle(lp_player), false)' in panel
    assert '(lv_source == lv_target)' in click
    assert 'gv_action[lv_source][0] = 0;' in click
    assert 'gf_BHVisitAction(lv_a);' in prep and 'gf_BHCrime' not in prep
    assert 'gv_immune' not in setup
    startup = "\n".join(script.body("gf_DisplayRoles"))
    assert 'if ((gv_roles[lv_a][1] == 3)) {' in startup
    assert ('if ((gv_roles[lv_a][0] == 23) || (gv_roles[lv_a][0] == 28)) {\n'
            '                    gv_immuneChance[lv_a] = 1;\n'
            '                }') in startup
    for name in ("gf_RAEgunActions", "gf_SKA_3_egun", "gf_SKP_3_egun", "gf_EGPrepareNight", "gf_EGResolveNight"):
        body = "\n".join(script.body(name))
        assert not re.search(r'\bgv_immuneChance\[[^\]]+\]\s*(?:=(?!=)|[+*/-]=|\+\+|--)', body), name

    data = json.loads((ROOT / "work/roles-list.json").read_text())
    neutral = [s for s in data["sections"] if s["category"] == 3]
    assert neutral and all(sum(e["role"] == 28 for e in s["entries"]) == 1 for s in neutral)
    assert 'lv_role = 28;' in "\n".join(script.body("gf_ASGuessRole"))
    print("✓ 恶棍外围：文案打包键、无选项/开局一次免疫、探员组、零权重、无越界银行索引、单目标/取消/访问、列表与审查接线")


if __name__ == "__main__":
    main()
