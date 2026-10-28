#!/usr/bin/env python3
"""Static 裁决者 3/38 wording/wiring contract, NOT gameplay or SC2 validation.

Run: python3 tools/test_adjudicator_contract.py
Read the actual gf_RTNeutralRoleText 38 branch, follow its StringExternal keys
through preset_gen.load_strings(), and compare final card fields 1/2/4/6.
Missing production files/branches fail normally (never skip or wait for them).
Only layout whitespace, visual bullet prefixes and valid style tags are ignored.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from preset_gen import load_strings
from test_egun import function, mask
from test_recruiter_modes import balanced_end

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work' / 'blackhand' / 'CustomLogic.galaxy'
ABILITY = '每两晚，你可以选择两个人，他们中的其中之一需要在明天白天被处决。否则，明天夜晚你可以选择一个人，他死亡。'
TRAITS = (
    '所有人都会知道你是谁和你选择了谁。',
    '你无法在白天被处决。',
    '在你胜利后，你会离开小镇（视作死亡）。',
    '你拥有一次夜间无敌机会。',
    '你的能力无视无敌和救治。',
)
VICTORY = '有两个被你选择的人死于处决，然后你离开小镇。'
BACKGROUND = '一位凌驾于法律之上的专横法官，利用其不可撼动的特权强迫全镇执行他的处决命令，并秘密处死敢于违抗他意志的人。'
INTRODUCTION = '每两晚，这个角色可以选择两个人，这两个人的其中之一需要在白天被处决。否则，裁决者会展开报复，当晚裁决者可以选择一个未被他选择的过的人，其死亡。'
FIELDS = (1, 2, 4, 6)


def visible_text(value: str) -> str:
    """Ignore presentation only; unknown/broken markup cannot hide wrong prose."""
    stack = []

    def replace_tag(match):
        tag = match[0]
        if re.fullmatch(r'<n\s*/>', tag):
            return '\n'

        closing = re.fullmatch(r'</(s|c|b|i|u)>', tag)
        if closing:
            assert stack and stack.pop() == closing[1], f'unbalanced style: {tag}'
            return ''

        opening = re.fullmatch(r'<(s|c)\s+val="([^"<>]+)">|<(b|i|u)>', tag)
        assert opening, f'unknown/invalid style tag: {tag}'
        name = opening[1] or opening[3]
        if name == 'c':
            assert re.fullmatch(r'(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{8})?)',
                                opening[2]), f'invalid SC2 color: {tag}'

        stack.append(name)
        return ''

    plain = re.sub(r'<[^>]*>', replace_tag, value)
    assert not stack, f'unclosed styles: {stack}'
    assert '<' not in plain and '>' not in plain, 'unparsed markup'
    lines = []
    for line in plain.splitlines():
        line = re.sub(r'^\s*(?:[-*•·●▪‣–—]\s*)+', '', line).strip()
        if line:
            lines.append(re.sub(r'\s+', '', line))

    return ''.join(lines)


def actual_role_branch(source: str) -> tuple[str, str]:
    """Use masked brace boundaries so comments/string contents are not code."""
    body = function(source, 'gf_RTNeutralRoleText')
    live = mask(body)
    matches = []
    for match in re.finditer(r'\bif\s*\(([^{};]+)\)\s*\{', live):
        condition = match[1]
        role = re.search(r'gv_roles\[(\w+)\]\[0\]\s*==\s*38\b', condition)
        if not role:
            continue

        player = role[1]
        # Explicitly reject extra guards such as && false: the final wording
        # must be the unconditional card wording for this role, not dead code.
        atoms = re.sub(r'[\s()]', '', condition).split('&&')
        required = {f'gv_roles[{player}][0]==38', f'gv_roles[{player}][1]==3'}
        assert set(atoms) in (required, {f'gv_roles[{player}][0]==38'}), \
            f'unsupported/conditional 3/38 card guard: {condition.strip()}'
        opening = live.index('{', match.start())
        # Reject a matching branch nested in another conditional/dead block.
        depth = live[:match.start()].count('{') - live[:match.start()].count('}')
        assert depth == 1, '3/38 card branch must be direct, not nested/dead code'
        end = balanced_end(live, opening)
        matches.append((body[opening + 1:end - 1], player))

    assert len(matches) == 1, \
        f'尚未实现或重复：gf_RTNeutralRoleText 的 3/38 分支数量={len(matches)}'
    branch, player = matches[0]
    assert not re.search(r'\b(?:if|else|switch|for|while|return|TriggerExecute)\b', mask(branch)), \
        'static contract only supports unconditional, directly wired card text'
    return branch, player


def text_expression(expression: str, player: str, values: dict, strings: dict) -> tuple[str, list[str]]:
    """Evaluate only external keys, prior field values, parentheses and concat.

    Unsupported expressions fail closed instead of extracting an isolated key
    while silently ignoring an extra dynamic/contradictory text fragment.
    """
    token = re.compile(
        r'\s*(?:StringExternal\(\s*"(?P<key>Param/Value/[^"\n]+)"\s*\)'
        + r'|gv_roleBoxText\[\s*' + re.escape(player) + r'\s*\]\[\s*(?P<field>\d+)\s*\]'
        + r'|(?P<op>[()+]))')
    tokens, position = [], 0
    while position < len(expression):
        if not expression[position:].strip():
            break

        match = token.match(expression, position)
        assert match, f'unsupported card expression at: {expression[position:]}'
        if match['key'] is not None:
            key = match['key']
            assert key in strings, f'actual card references missing GameStrings key: {key}'
            tokens.append(('value', strings[key], [key]))
        elif match['field'] is not None:
            field = int(match['field'])
            assert field in values, f'card reads uninitialized field [{field}]'
            tokens.append(('value', values[field][0], values[field][1]))
        else:
            tokens.append((match['op'], '', []))

        position = match.end()

    index = 0

    def atom():
        nonlocal index
        assert index < len(tokens), 'incomplete card expression'
        kind, value, keys = tokens[index]
        index += 1
        if kind == 'value':
            return value, keys

        assert kind == '(', f'expected text value, got {kind}'
        value, keys = concat()
        assert index < len(tokens) and tokens[index][0] == ')', 'missing closing parenthesis'
        index += 1
        return value, keys

    def concat():
        nonlocal index
        value, keys = atom()
        while index < len(tokens) and tokens[index][0] == '+':
            index += 1
            addition, used = atom()
            value, keys = value + addition, keys + used

        return value, keys

    result = concat()
    assert index == len(tokens), 'unconsumed card expression tokens'
    return result


def wired_fields(branch: str, player: str, strings: dict) -> dict:
    values = {}
    live = mask(branch)
    target = re.compile(r'\bgv_roleBoxText\[\s*' + re.escape(player)
                        + r'\s*\]\[\s*(\d+)\s*\]\s*=(?!=)')
    for match in target.finditer(live):
        field = int(match[1])
        if field not in FIELDS:
            continue

        end = live.index(';', match.end())
        expression = branch[match.end():end]
        values[field] = text_expression(expression, player, values, strings)

    assert set(values) == set(FIELDS), f'actual 3/38 card fields missing: {set(FIELDS) - values.keys()}'
    # Do not overlook += or other unsupported writes after a correct assignment.
    for match in re.finditer(r'\bgv_roleBoxText\[\s*' + re.escape(player)
                             + r'\s*\]\[\s*([1246])\s*\]\s*([+*/-]=|\+\+|--)', live):
        raise AssertionError(f'unsupported mutation of actual field [{match[1]}]')

    return values


def assert_card_wording(fields: dict) -> None:
    """Exact expectations shared by positive checks and in-memory mutations."""
    expected = {1: ABILITY, 2: ''.join(TRAITS), 4: '裁决者', 6: VICTORY}
    for field, text in expected.items():
        actual = visible_text(fields[field][0])
        assert actual == text, f'actual card field [{field}] differs: {actual!r} != {text!r}'


class ActualAdjudicatorContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert SCRIPT.exists(), '尚未实现：缺实际 CustomLogic.galaxy'
        cls.source = SCRIPT.read_text(encoding='utf-8')
        cls.strings = load_strings()
        branch, player = actual_role_branch(cls.source)
        cls.fields = wired_fields(branch, player, cls.strings)
        for field, (_, keys) in cls.fields.items():
            print(f'actual 3/38 gv_roleBoxText[{player}][{field}] -> {keys}')

    def test_actual_ability_field_1(self):
        self.assertEqual(visible_text(self.fields[1][0]), ABILITY)

    def test_actual_five_traits_field_2_in_order(self):
        self.assertEqual(visible_text(self.fields[2][0]), ''.join(TRAITS))

    def test_actual_white_role_name_field_4(self):
        # Field 4 is the white role-name text; background/introduction belong
        # to spec.desc_key and are verified separately, not invented here.
        self.assertEqual(visible_text(self.fields[4][0]), '裁决者')

    def test_negative_actual_referenced_word_changed(self):
        assert_card_wording(self.fields)
        branch, player = actual_role_branch(self.source)
        changed = dict(self.strings)
        key = next(key for key in self.fields[1][1] if '每两晚' in changed[key])
        changed[key] = changed[key].replace('每两晚', '每三晚', 1)
        # Correct but unused prose cannot rescue a changed live reference.
        changed['Param/Value/CONTRACT_ORPHAN_CORRECT_ABILITY'] = ABILITY
        with self.assertRaisesRegex(AssertionError, r'field \[1\] differs'):
            assert_card_wording(wired_fields(branch, player, changed))

    def test_negative_actual_card_rewired_while_correct_key_remains_orphaned(self):
        branch, player = actual_role_branch(self.source)
        key = 'Param/Value/CONTRACT_WRONG_LIVE_ABILITY'
        changed = dict(self.strings)
        changed[key] = ABILITY.replace('每两晚', '每三晚', 1)
        target = re.compile(r'(gv_roleBoxText\[\s*' + re.escape(player)
                            + r'\s*\]\[\s*1\s*\]\s*=\s*)[^;]+;')
        rewired, count = target.subn(lambda m: m[1] + f'StringExternal("{key}");', branch)
        self.assertGreater(count, 0)
        for original_key in self.fields[1][1]:
            self.assertEqual(changed[original_key], self.strings[original_key])

        with self.assertRaisesRegex(AssertionError, r'field \[1\] differs'):
            assert_card_wording(wired_fields(rewired, player, changed))

    def test_negative_actual_extra_contradictory_trait(self):
        branch, player = actual_role_branch(self.source)
        changed = dict(self.strings)
        key = self.fields[2][1][-1]
        changed[key] += '<n/>- 你的能力可以被救治。'
        with self.assertRaisesRegex(AssertionError, r'field \[2\] differs'):
            assert_card_wording(wired_fields(branch, player, changed))

    def test_negative_actual_branch_removed_but_correct_strings_survive(self):
        # Mutate code in memory only; all correct GameStrings remain present.
        source, count = re.subn(r'(gv_roles\[\w+\]\[0\]\s*==\s*)38\b',
                                r'\g<1>39', self.source)
        self.assertGreater(count, 0)
        self.assertTrue(all(key in self.strings for _, keys in self.fields.values() for key in keys))
        with self.assertRaisesRegex(AssertionError, '尚未实现'):
            actual_role_branch(source)

    def test_actual_victory_field_6(self):
        self.assertEqual(visible_text(self.fields[6][0]), VICTORY)

    def test_actual_spec_description_and_registration(self):
        specs = []
        for path in sorted((ROOT / 'roles').glob('*.json')):
            spec = json.loads(path.read_text(encoding='utf-8'))
            if (spec.get('pool'), spec.get('role')) == (3, 38):
                specs.append((path, spec))

        self.assertEqual(len(specs), 1, '尚未实现或重复：需要唯一 pool=3 role=38 spec')
        path, spec = specs[0]
        self.assertIn('desc_key', spec, f'{path.name} 缺 desc_key')
        key = spec['desc_key']
        key = key if key.startswith('Param/Value/') else 'Param/Value/' + key
        self.assertIn(key, self.strings, f'实际 spec.desc_key 缺文案：{key}')
        self.assertEqual(visible_text(self.strings[key]), BACKGROUND + INTRODUCTION)
        # The spec key must also be wired into the actual role registration.
        registered = re.search(
            r'gv_roleDescriptionArray\s*\[\s*3\s*\]\s*\[\s*38\s*\]\s*=\s*'
            r'StringExternal\(\s*"' + re.escape(key) + r'"\s*\)\s*;', self.source)
        self.assertIsNotNone(registered, 'spec.desc_key is not used by actual 3/38 description array')
        self.assertIn('gv_roleDescriptionArray', mask(self.source)[registered.start():registered.end()])


class ContractParserSafety(unittest.TestCase):
    def test_layout_only_normalization(self):
        self.assertEqual(visible_text('<s val="ModLeftSize16"><c val="BBDDFF">'
                                      '<n/>- ' + TRAITS[0] + '<n/>• ' + TRAITS[1]
                                      + '</c></s>'), ''.join(TRAITS[:2]))
        for invalid in ('<unknown>extra</unknown>', '<c val="FFFF99-FF8800">wrong</c>', '<s val="X">unclosed'):
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                visible_text(invalid)

        self.assertNotEqual(visible_text(ABILITY + '<n/>- 你的能力可以被救治。'), ABILITY)

    def test_orphan_strings_and_dead_guards_cannot_satisfy_contract(self):
        with self.assertRaisesRegex(AssertionError, '尚未实现'):
            actual_role_branch('void gf_RTNeutralRoleText(int p) {\n'
                               '// if ((gv_roles[p][0] == 38)) { }\n}')

        for guard in ('(gv_roles[p][0] == 38) && false',
                      '(gv_roles[p][0] == 38) || true'):
            with self.subTest(guard=guard), self.assertRaises(AssertionError):
                actual_role_branch('void gf_RTNeutralRoleText(int p) { if (' + guard + ') {} }')

    def test_keys_followed_and_extra_expression_cannot_be_ignored(self):
        strings = {'Param/Value/A': 'first', 'Param/Value/B': 'second'}
        value, keys = text_expression('(StringExternal("Param/Value/A") + '
                                      'StringExternal("Param/Value/B"))', 'p', {}, strings)
        self.assertEqual((value, keys), ('firstsecond', list(strings)))
        with self.assertRaises(AssertionError):
            text_expression('StringExternal("Param/Value/A") + arbitraryExtraText', 'p', {}, strings)


if __name__ == '__main__':
    unittest.main(verbosity=2)
