#!/usr/bin/env python3
"""Static regression for town roles 31–35: strings, help tiles and packaging.

Run: python3 -B tools/test_town_role_colors.py
Reads actual merged GameStrings and Galaxy; this is NOT an SC2 engine/rendering
test. WCAG sRGB contrast against black is a numeric readability sanity check,
not a claim about the game's texture, opacity, font or final rendered contrast.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import unittest
from pathlib import Path

# Keep this read-only regression from creating imported modules' __pycache__.
sys.dont_write_bytecode = True

from preset_gen import load_strings
from test_recruiter_modes import balanced_end, function

ROOT = Path(__file__).resolve().parent.parent
ROLES = (
    (31, 'GCZ', 'TAG', '80BFA3', 'guanchazhe'),
    (32, 'SQ', 'TAG', 'B4D65C', 'renkoupuchaguan'),
    (33, 'FENG', 'TAG', '4DFF29', 'fengzi'),
    (34, 'JJ', 'TAG', '5CE0BD', 'jijiuzhuanjia'),
    (35, 'ZJ', 'ALIGN', '37A866', 'zhujiao'),
)


def compact(text: str) -> str:
    return re.sub(r'\s+', '', text)


def rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def contrast_on_black(hex_color: str) -> float:
    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    luminance = sum(weight * linear(channel)
                    for weight, channel in zip((0.2126, 0.7152, 0.0722), rgb(hex_color)))
    return (luminance + 0.05) / 0.05


class TownRoleColorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strings = load_strings()
        cls.source = (ROOT / 'work/blackhand/CustomLogic.galaxy').read_text(encoding='utf-8')
        cls.help_menu = function(cls.source, 'gf_MakeHelpMenu')

    def value(self, suffix: str) -> str:
        key = 'Param/Value/' + suffix
        self.assertIn(key, self.strings, f'missing GameStrings key: {key}')
        return self.strings[key]

    def test_name_tag_and_card_colors(self):
        for role, prefix, tag, expected, _ in ROLES:
            for suffix in ('NAME', tag, 'CARD'):
                with self.subTest(role=role, key=prefix + suffix):
                    value = self.value(prefix + suffix)
                    self.assertEqual(re.findall(r'<c val="([^"]+)">', value), [expected])
                    if suffix == 'CARD':
                        self.assertEqual(value, f'<c val="{expected}">')

    def test_distinct_readable_greens(self):
        colors = []
        for role, prefix, _, _, _ in ROLES:
            with self.subTest(role=role):
                match = re.fullmatch(r'<c val="([0-9A-Fa-f]{6})">.*</c>', self.value(prefix + 'NAME'))
                self.assertIsNotNone(match, 'role NAME must use one solid RGB color')
                color = match.group(1).upper()
                colors.append(color)
                red, green, blue = rgb(color)
                self.assertGreater(green, max(red, blue), 'green must be the largest channel')
                self.assertGreaterEqual(contrast_on_black(color), 4.5, 'contrast on black must be >= 4.5:1')

        self.assertEqual(len(set(colors)), len(ROLES), 'five roles must have distinct greens')

    def test_bishop_option_punctuation_only(self):
        for suffix, text in (('OPT2', '投下的票相当于两人'), ('OPT3', '投下的票相当于三人')):
            with self.subTest(key='ZJ' + suffix):
                value = self.value('ZJ' + suffix)
                self.assertEqual(value, text)
                self.assertNotRegex(value, r'[。．.]')

        for suffix, text in (
            ('BOX2A', '<n/>- 获得教区支持的人，在次日投下的票相当于两人。'),
            ('BOX2B', '<n/>- 获得教区支持的人，在次日投下的票相当于三人。'),
            ('NEWS2', '人。'),
        ):
            with self.subTest(key='ZJ' + suffix):
                self.assertEqual(self.value('ZJ' + suffix), text)

    def test_help_tiles_guards_controls_rgb_and_initials(self):
        menu = self.help_menu
        lawyer = re.search(r'if\s*\(\(lv_category\s*==\s*2\)\s*&&\s*\(lv_role\s*==\s*21\)\)\s*\{', menu)
        self.assertIsNotNone(lawyer, 'existing lawyer override must remain present')

        for role, prefix, _, expected, pinyin in ROLES:
            with self.subTest(role=role):
                guard = rf'if\s*\(\(lv_category\s*==\s*1\)\s*&&\s*\(lv_role\s*==\s*{role}\)\)\s*\{{'
                matches = list(re.finditer(guard, menu))
                self.assertEqual(len(matches), 1, 'need one explicit category AND role guard')
                match = matches[0]
                start = menu.index('{', match.start())
                end = balanced_end(menu, start)
                self.assertLess(end, lawyer.start(), 'town overrides must precede lawyer override')
                body = compact(menu[start + 1:end - 1])
                color_call = re.search(
                    r'libNtve_gf_SetDialogItemColor\(gv_roleHelpPanelItem\[lv_x\]\[0\],'
                    r'Color\(([\d.]+),([\d.]+),([\d.]+)\),PlayerGroupAll\(\)\);', body)
                self.assertIsNotNone(color_call, 'recolor existing tile [lv_x][0] for all players')
                for actual, channel in zip(color_call.groups(), rgb(expected)):
                    self.assertAlmostEqual(float(actual), channel * 100 / 255, delta=0.0051)

                text_call = compact(
                    'libNtve_gf_SetDialogItemText(gv_roleHelpPanelItem[lv_x][1], '
                    f'(StringExternal("Param/Value/{prefix}CARD") + '
                    'StringToText(StringCase(StringSub(gv_roleNameInput[lv_category][lv_role], 1, 1), true)) '
                    '+ StringExternal("Param/Value/01EDEAB5")), PlayerGroupAll());')
                self.assertEqual(body, color_call.group(0) + text_call,
                                 'only recolor tile [0] and replace initial label [1]; preserve order')
                self.assertEqual(menu.count(f'"Param/Value/{prefix}CARD"'), 1,
                                 'CARD reference must occur only in its guarded branch')
                names = re.findall(rf'gv_roleNameInput\[1\]\[{role}\]\s*=\s*"([^"]+)";', self.source)
                self.assertEqual(names, [pinyin], 'initial must come from the intended role pinyin')
                self.assertEqual(self.value('01EDEAB5'), '</c>', 'initial color must close correctly')

    def required_keys(self):
        tree = ast.parse((ROOT / 'tools/boot2_build.py').read_text(encoding='utf-8'))
        assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'MUST_HAVE_KEYS'
                               for target in node.targets)]
        self.assertEqual(len(assignments), 1)
        return ast.literal_eval(assignments[0].value)

    def test_card_keys_registered_for_packaging(self):
        required = self.required_keys()
        for _, prefix, _, _, _ in ROLES:
            with self.subTest(key=prefix + 'CARD'):
                self.assertIn('Param/Value/' + prefix + 'CARD', required)

    def test_bishop_shares_pastor_public_places_investigator_group(self):
        spec = json.loads((ROOT / 'roles/zhujiao.json').read_text(encoding='utf-8'))
        expected = ['E585ACE585B1E59CBAE689801', 'E585ACE585B1E59CBAE689802']
        with self.subTest(layer='role spec'):
            self.assertEqual(spec['investigator'], expected)

        initialization = function(self.source, 'gf_InitializeVariables')
        for index, investigator in enumerate(expected):
            with self.subTest(layer='Galaxy initialization', field=index):
                assignments = []
                for role in (25, 35):
                    matches = re.findall(
                        rf'gv_roleInvestigatorArray\[1\]\[{role}\]\[{index}\]\s*=\s*(\w+)\s*;',
                        initialization)
                    self.assertEqual(matches, ['gv_investigator' + investigator])
                    assignments.append(matches[0])

                self.assertEqual(assignments[0], assignments[1], 'bishop must share pastor globals')

        for investigator, key in zip(expected, ('B6220326', '4F1EBF4B')):
            with self.subTest(layer='shared text binding', key=key):
                matches = re.findall(
                    rf'gv_investigator{investigator}\s*=\s*StringExternal\("Param/Value/([^\"]+)"\);',
                    self.source)
                self.assertEqual(matches, [key])

        with self.subTest(layer='shared first sentence'):
            self.assertEqual(self.value('B6220326'), '你的目标常出入公共场所')

        candidates = ('3051C3D7', '4F1EBF4B', '72BB7C73', 'A51EA15F', 'B7F2DBC2',
                      'C84927BC', 'C8AB6DDE', 'CF0DFBAB', 'CWINV2')
        zj = (ROOT / 'work/blackhand/strings-zj.txt').read_text(encoding='utf-8')
        shw = (ROOT / 'work/blackhand/strings-shw.txt').read_text(encoding='utf-8')
        required = self.required_keys()
        for key in candidates:
            with self.subTest(layer='public-place candidates', key=key):
                text = self.value(key)
                self.assertIn('牧师', text)
                self.assertIn('主教', text)
                overrides = shw if key in ('4F1EBF4B', 'CWINV2') else zj
                self.assertRegex(overrides, rf'(?m)^Param/Value/{key}=')
                self.assertIn('Param/Value/' + key, required)

        for key in ('C0685A17', '6E101407', '77A27769', 'BAFE0763'):
            with self.subTest(layer='old charisma group', key=key):
                self.assertNotRegex(zj, rf'(?m)^Param/Value/{key}=')
                self.assertNotIn('主教', self.value(key))
                self.assertNotIn('Param/Value/' + key, required)


if __name__ == '__main__':
    unittest.main(verbosity=2)
