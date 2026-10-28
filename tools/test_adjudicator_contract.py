#!/usr/bin/env python3
"""Static 裁决者 3/38 wording/wiring contract, NOT gameplay or SC2 validation.

Run: python3 tools/test_adjudicator_contract.py
Read the actual gf_RTNeutralRoleText 38 branch, follow its StringExternal keys
through preset_gen.load_strings(), and compare final card fields 0/1/2/4/6.
Missing production files/branches fail normally (never skip or wait for them).
Prose comparison ignores style/bullets; trait layout additionally requires five
separate rendered lines, so concatenating the five sentences cannot pass.
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
FIELDS = (0, 1, 2, 4, 6)
ROLE_COLOR = '8FAADC'
INVESTIGATOR = '你的目标是一个堕落的法官，他早已扭曲 - 你的目标是一个裁决者。'
DEATH = '他暴毙于家中，胸口被法槌和铁钉贯穿。'
NIGHT = '你听见深夜的街上传来急促沉重的破门声，伴随着冰冷的宣判与窒息的闷响……'


def visible_lines(value: str) -> tuple[str, ...]:
    """Preserve rendered line boundaries; reject unknown or broken markup."""
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

    return tuple(lines)


def visible_text(value: str) -> str:
    return ''.join(visible_lines(value))


def assert_trait_layout(value: str) -> None:
    lines = visible_lines(value)
    assert lines == TRAITS, f'trait layout must be five separate lines: {lines!r}'


def live_match(source: str, pattern: str):
    """A matching string/comment alone cannot satisfy a production wiring check."""
    live = mask(source)
    matches = [match for match in re.finditer(pattern, source)
               if live[match.start():match.start() + 1].strip()]
    assert len(matches) == 1, f'expected unique live wiring for {pattern!r}, got {len(matches)}'
    return matches[0]


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
                             + r'\s*\]\[\s*([01246])\s*\]\s*([+*/-]=|\+\+|--)', live):
        raise AssertionError(f'unsupported mutation of actual field [{match[1]}]')

    return values


def assert_card_wording(fields: dict) -> None:
    """Exact expectations shared by positive checks and in-memory mutations."""
    expected = {0: '无（混乱）', 1: ABILITY, 2: ''.join(TRAITS), 4: '裁决者', 6: VICTORY}
    for field, text in expected.items():
        actual = visible_text(fields[field][0])
        assert actual == text, f'actual card field [{field}] differs: {actual!r} != {text!r}'

    assert_trait_layout(fields[2][0])


def assert_announcement_timing(source: str) -> None:
    """Verify both real phase entrypoints, outside their complete dim loops."""
    sequence = function(source, 'gt_DaySequence_Func')
    live = mask(sequence)
    calls = list(re.finditer(r'\bgf_CJAnnounceMorning\(\)\s*;', live))
    assert len(calls) == 2, 'need discussion and no-discussion announcement entrypoints'
    freeze = live_match(sequence, r'\bgf_CJMorning\(\)\s*;')
    assert freeze.start() < calls[0].start()
    assert not re.search(r'\bWait\s*\(', live[:freeze.start()]), 'freeze must precede day action yield'

    discussion = live_match(sequence, r'\bif\s*\([^{};]*\bgv_startDayWithDiscussion\b[^{};]*\)\s*\{')
    opening = live.index('{', discussion.start())
    end = balanced_end(live, opening)
    body = sequence[opening + 1:end - 1]
    local_call = live_match(body, r'\bgf_CJAnnounceMorning\(\)\s*;')
    timer = live_match(body, r'\bgf_TBStartTimer2\(\(60\.0\s*\*\s*gv_discussionLength\),[^;]+;')
    wait = live_match(body, r'\bWait\(\(60\.0\s*\*\s*gv_discussionLength\),\s*c_timeGame\)\s*;')
    assert timer.end() <= local_call.start() < wait.start(), 'announce only after discussion timer and before its wait'
    assert calls[0].start() == opening + 1 + local_call.start()

    def dim_loops_before(text: str, position: int):
        code, loops = mask(text), []
        for loop in re.finditer(r'\bwhile\s*\(true\)\s*\{', code):
            loop_end = balanced_end(code, code.index('{', loop.start()))
            inner = code[loop.start():loop_end]
            if loop_end <= position and re.search(r'\bgf_CBDimChat\s*\(', inner):
                assert 'PlayerGroupNextPlayer' in inner
                loops.append((loop.start(), loop_end))

        assert loops, 'announcement must follow a completed dim loop'
        _, loop_end = loops[-1]
        assert not re.search(r'\b(?:Wait|gf_CBDimChat)\s*\(', code[loop_end:position]), \
            'no yield or extra dim between completed dim loop and announcement'

    dim_loops_before(body, local_call.start())
    fallback = calls[1]
    assert fallback.start() > end, 'fallback must be outside the discussion branch'
    dim_loops_before(sequence, fallback.start())
    assert re.match(r'\s*gf_ASStartVote\(\)\s*;', live[fallback.end():]), \
        'fallback must immediately precede real voting start'
    # Both calls are below death report / revival and the pre-day CheckEnd gate.
    transition = function(source, 'auto_gf_DayTransition_TriggerFunc')
    assert transition.index('gf_JJResolve();') < transition.rindex('gf_CheckEnd()') \
        < transition.index('TriggerExecute(gt_DaySequence, false, false);')


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
        assert_trait_layout(self.fields[2][0])

    def test_negative_actual_traits_collapsed_to_one_line(self):
        branch, player = actual_role_branch(self.source)
        changed = dict(self.strings)
        for key in self.fields[2][1]:
            changed[key] = visible_text(changed[key])

        with self.assertRaisesRegex(AssertionError, 'trait layout'):
            assert_card_wording(wired_fields(branch, player, changed))

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

    def test_actual_role_type_and_name_colors(self):
        self.assertEqual(visible_text(self.fields[0][0]), '无（混乱）')
        for key, text in (('CJNAME', '裁决者'), ('CJHEAD', '无（混乱）'), ('CJCARD', 'C')):
            with self.subTest(key=key):
                self.assertEqual(self.strings['Param/Value/' + key],
                                 f'<c val="{ROLE_COLOR}">{text}</c>')

    def test_actual_investigator_complete_sentence_then_null_not_empty(self):
        spec = json.loads((ROOT / 'roles' / 'caijuezhe.json').read_text(encoding='utf-8'))
        self.assertEqual(spec['investigator'], ['CJINV1', 'CJINV2'])
        self.assertEqual(self.strings['Param/Value/CJINV1'], INVESTIGATOR)
        self.assertNotIn('Param/Value/CJINV2', self.strings, 'unused duplicate prose must be removed')
        for slot, key in enumerate(spec['investigator']):
            live_match(self.source, r'gv_roleInvestigatorArray\[3\]\[38\]\[' + str(slot)
                       + r'\]\s*=\s*gv_investigator' + key + r'\s*;')

        live_match(self.source, r'gv_investigatorCJINV1\s*=\s*StringExternal\("Param/Value/CJINV1"\)\s*;')
        live_match(self.source, r'gv_investigatorCJINV2\s*=\s*null\s*;')
        # Actual ordinary/framed bodies dispatch slot 0 once and guard slot 1 by
        # null, not emptiness. Executable coverage is in test_adjudicator.py.
        investigator = function(self.source, 'gf_SKF_1_tanyuan')
        for prefix, suffix in (('A22D1588', '745ADE02'), ('D3E28725', '33DEC688')):
            live_match(investigator, r'gf_CBSystemMessage\(\(StringExternal\("Param/Value/'
                       + prefix + r'"\)[^;]+StringExternal\("Param/Value/' + suffix + r'"\)\)')
            self.assertEqual(visible_text(self.strings['Param/Value/' + prefix]
                                         + INVESTIGATOR + self.strings['Param/Value/' + suffix]),
                             visible_text(INVESTIGATOR))

    def test_actual_crime_description_registration(self):
        self.assertEqual(self.strings['Param/Value/CJCRIME'], '操纵审判，谋杀')
        live_match(self.source, r'gv_e78AAFE7BDAAE58FAFE883BD\[3\]\[38\]\s*=\s*'
                   r'StringExternal\("Param/Value/CJCRIME"\)\s*;')

    def test_actual_death_narrative_is_not_night_announcement(self):
        attack = function(self.source, 'gf_CJAttack')
        self.assertEqual(self.strings['Param/Value/CJDEATH'], f'<c val="FFFFFF">{DEATH}</c>')
        self.assertEqual(self.strings['Param/Value/CJDM'],
                         '<c val="FFFFFF">这具尸体死于裁决者的秘密处决。</c>')
        live_match(attack, r'gv_deathText\[target\]\s*=\s*\(gv_deathText\[target\]\s*\+\s*'
                   r'StringExternal\("Param/Value/CJDEATH"\)\)\s*;')
        self.assertNotRegex(attack, r'gv_deathText\[target\][^;]*Param/Value/CJNIGHT')

    def test_actual_night_announcement_stays_red(self):
        self.assertEqual(self.strings['Param/Value/CJNIGHT'], f'<c val="FF0000">{NIGHT}</c>')
        attack = function(self.source, 'gf_CJAttack')
        # The public role-color wrapper must not repaint the red killing cue.
        self.assertNotRegex(attack, r'gf_CJTellAll\([^;]*Param/Value/CJNIGHT')
        live_match(attack, r'StringExternal\("Param/Value/CJNIGHT"\)')

    def test_split_public_announcements_are_plain_individual_messages(self):
        messages = {
            'CJINTRO2': '亮明了他作为「裁决者」的特权身份。',
            'CJINTRO3': '他手握凌驾于律法之上的绝对豁免权——他无法被处决。',
            'CJDAWN2': '。',
            'CJDAWNONE': '。',
            'CJDAWNREQ': '今天日落之前，他们二人中必须有一人被处决！',
            'CJDAWNFAIL': '若天黑前两人均未被处决，今夜必将有一名违逆者在暗夜中被清除。',
            'CJDAWNONEREQ': '今天日落之前，此人必须被处决！',
            'CJDAWNONEFAIL': '若天黑前此人未被处决，今夜必将有一名违逆者在暗夜中被清除。',
        }
        for key, text in messages.items():
            with self.subTest(key=key):
                self.assertEqual(self.strings['Param/Value/' + key], text)

        start = function(self.source, 'gf_CJInitPlayer')
        live_match(start, r'gf_CJTellAll\(StringExternal\("Param/Value/CJINTRO3"\)\)\s*;')
        announce = function(self.source, 'gf_CJAnnounceMorning')
        for key in ('CJDAWNREQ', 'CJDAWNFAIL', 'CJDAWNONEREQ', 'CJDAWNONEFAIL'):
            live_match(announce, r'gf_CJTellAll\(StringExternal\("Param/Value/' + key + r'"\)\)\s*;')

    def test_actual_morning_freeze_and_phase_announcement_are_separate(self):
        morning, announce = (function(self.source, name) for name in
                             ('gf_CJMorning', 'gf_CJAnnounceMorning'))
        self.assertNotRegex(mask(morning), r'\bgf_(?:CJTellAll|CBSystemMessage|BHNotify)\s*\(')
        self.assertNotRegex(mask(morning), r'\bWait\s*\(')
        self.assertNotRegex(mask(announce), r'\bgv_cj(?:List|ListDay|RestNight|Satisfied|Score|Pending|PendingNight)\b(?:\[[^\]]+\])+\s*(?:=(?!=)|[+*/-]=|\+\+|--)')
        self.assertNotRegex(mask(announce), r'\b(?:gf_GKLive|Wait)\s*\(')
        live_match(announce, r'gv_cjAnnouncedDay\[p\]\s*=\s*gv_dayNumber\s*;')
        live_match(function(self.source, 'gf_CJClearRound'), r'gv_cjAnnouncedDay\[p\]\s*=\s*0\s*;')
        assert_announcement_timing(self.source)

    def test_negative_announcement_before_discussion_timer_or_after_voting(self):
        sequence = function(self.source, 'gt_DaySequence_Func')
        pattern = (r'(gf_TBStartTimer2\(\(60\.0\s*\*\s*gv_discussionLength\),[^;]+;)'
                   r'\s*(gf_CJAnnounceMorning\(\);)')
        changed, count = re.subn(pattern, r'\2\n        \1', sequence)
        self.assertEqual(count, 1)
        with self.assertRaisesRegex(AssertionError, 'after discussion timer'):
            assert_announcement_timing(self.source.replace(sequence, changed))

        changed, count = re.subn(r'(gf_CJAnnounceMorning\(\);)\s*(gf_ASStartVote\(\);)',
                                 r'\2\n        \1', sequence)
        self.assertEqual(count, 1)
        with self.assertRaisesRegex(AssertionError, 'immediately precede'):
            assert_announcement_timing(self.source.replace(sequence, changed))

    def test_negative_announcement_without_completed_discussion_dim(self):
        sequence = function(self.source, 'gt_DaySequence_Func')
        match = live_match(sequence, r'\bif\s*\([^{};]*\bgv_startDayWithDiscussion\b[^{};]*\)\s*\{')
        opening = sequence.index('{', match.start())
        end = balanced_end(mask(sequence), opening)
        body = sequence[opening + 1:end - 1]
        changed, count = re.subn(r'gf_CBDimChat\(\w+\);', '', body)
        self.assertEqual(count, 1)
        changed_sequence = sequence[:opening + 1] + changed + sequence[end - 1:]
        with self.assertRaisesRegex(AssertionError, 'completed dim loop'):
            assert_announcement_timing(self.source.replace(sequence, changed_sequence))

    def test_actual_help_menu_background_uses_role_blue(self):
        help_menu = function(self.source, 'gf_MakeHelpMenu')
        branch = live_match(help_menu, r'if\s*\(\(lv_category\s*==\s*3\)\s*&&\s*\(lv_role\s*==\s*38\)\)\s*\{')
        opening = help_menu.index('{', branch.start())
        end = balanced_end(mask(help_menu), opening)
        body = help_menu[opening + 1:end - 1]
        live_match(body, r'lv_t\[5\]\s*=\s*StringExternal\("Param/Value/CJCARD"\)\s*;')
        color = live_match(body, r'libNtve_gf_SetDialogItemColor\(gv_roleHelpPanelItem\[lv_x\]\[0\],\s*'
                           r'Color\(([\d.]+),\s*([\d.]+),\s*([\d.]+)\),\s*PlayerGroupAll\(\)\)\s*;')
        actual = ''.join(f'{int(float(component) * 255 / 100 + 0.5):02X}' for component in color.groups())
        self.assertEqual(actual, ROLE_COLOR)


class ContractParserSafety(unittest.TestCase):
    def test_layout_only_normalization(self):
        self.assertEqual(visible_text('<s val="ModLeftSize16"><c val="BBDDFF">'
                                      '<n/>- ' + TRAITS[0] + '<n/>• ' + TRAITS[1]
                                      + '</c></s>'), ''.join(TRAITS[:2]))
        for invalid in ('<unknown>extra</unknown>', '<c val="FFFF99-FF8800">wrong</c>', '<s val="X">unclosed'):
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                visible_text(invalid)

        self.assertNotEqual(visible_text(ABILITY + '<n/>- 你的能力可以被救治。'), ABILITY)

    def test_trait_layout_rejects_collapsed_sentences_without_changing_words(self):
        assert_trait_layout('<n/>'.join('- ' + trait for trait in TRAITS))
        for collapsed in (''.join(TRAITS), '<n/>'.join(TRAITS[:3]) + ''.join(TRAITS[3:])):
            with self.subTest(collapsed=collapsed), self.assertRaisesRegex(AssertionError, 'five separate lines'):
                assert_trait_layout(collapsed)

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
