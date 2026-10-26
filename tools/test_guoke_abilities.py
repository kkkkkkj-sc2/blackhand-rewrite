#!/usr/bin/env python3
"""Bounded checks of production Guoke Galaxy helpers (NOT SC2 runtime).

Reads the repository's production script by default, or --script PATH. It never
loads/appends temporary fragments or substitutes gf_GKIs with a simplified model.
Only the synchronous helper bodies under test are translated into Python; engine
services are stubs, not an SC2 compiler, scheduler, or general Galaxy emulator.
"""
import argparse
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--script', type=Path, default=ROOT / 'work/blackhand/CustomLogic.galaxy', help='Production Galaxy source; defaults to the repository script.')
options, remaining = parser.parse_known_args()
sys.argv[1:] = remaining
SOURCE = options.script.read_text()
print('Guoke test source:', options.script, '; helpers and gf_GKIs: actual production bodies (engine stubs; NOT SC2 runtime)', file=sys.stderr)


def body(name):
    match = re.search(r'^\w+ ' + name + r'\s*\(([^)]*)\)\s*\{', SOURCE, re.M)
    assert match, name
    start = match.end()
    depth = 1
    end = start
    while depth:
        depth += (SOURCE[end] == '{') - (SOURCE[end] == '}')
        end += 1
    return match.group(1), SOURCE[start:end - 1]


def translate(name):
    params, code = body(name)
    names = [p.strip().split()[-1] for p in params.split(',') if p.strip()]
    out = ['def ' + name + '(' + ', '.join(names) + '):']
    globals_written = sorted(set(re.findall(r'\b(gv_\w+)\s*=(?!=)', code)))
    if globals_written:
        out.append('    global ' + ', '.join(globals_written))

    indent = 1
    for raw in code.splitlines():
        line = raw.split('//', 1)[0].strip()
        if not line:
            continue
        if line == '}':
            indent -= 1
            continue
        if re.fullmatch(r'(?:int|bool|text|string|color) \w+;', line):
            continue

        line = line.replace('&&', ' and ').replace('||', ' or ')
        line = re.sub(r'!(?!=)', 'not ', line)
        for old, new in [('true', 'True'), ('false', 'False'), ('null', 'None')]:
            line = re.sub(r'\b' + old + r'\b', new, line)
        line = line.replace('else if ', 'elif ')
        if line.endswith('{'):
            line = line[:-1].rstrip() + ':'
            out.append('    ' * indent + line)
            indent += 1
        else:
            out.append('    ' * indent + line.rstrip(';'))
    return '\n'.join(out)


HELPERS = '''gf_GKLive gf_GKRole gf_GKDayCan gf_GKNightRole gf_GKNightSelectable
    gf_GKPrepareVisits gf_GKResolveEarly gf_GKWitnessSnapshot gf_GKPuppetToggle
    gf_GKSubstitute gf_GKMailSet gf_GKMailFreeze gf_GKMailMember gf_GKMailWindow
    gf_GKMailReady gf_GKMailPeer gf_GKMailHidden gf_GKMailIntercept
    gf_GKParseFloor gf_GKAtFloor gf_GSGRPartner
    gt_GKCommand_Func gt_GKPanel_Func'''.split()


def state():
    n = 16
    env = {
        'gv_currentPlayers': set(range(1, n)), 'gv_alivePlayers': set(range(1, n)),
        'gv_players': set(range(1, n)), 'gv_roles': [[0, 0] for _ in range(n)],
        'gv_gkRole': [0] * n, 'gv_xrLifeDid': [False] * n,
        'gv_grParent': [0] * n, 'gv_grChild': [0] * n,
        'gv_bhFeignRole': [0] * n, 'gv_action': [[0, 0] for _ in range(n)],
        'gv_visitation': [0] * n, 'gv_visitation2': [0] * n,
        'gv_gkUsed': [False] * n, 'gv_gkPuppet': [False] * n,
        'gv_gkWitnessTarget': [0] * n, 'gv_gkWitnessCount': [-1] * n,
        'gv_jailed': [0] * n, 'gv_jailing': [0] * n,
        'gv_privateChannel': [0] * n, 'gv_silenced': [[False, False] for _ in range(n)],
        'gv_immuneChance': [0] * n, 'gv_immune': [[False] * 4 for _ in range(n)],
        'gv_roleblocked': [0] * n, 'gv_gkVoteDay': [0] * n,
        'gv_gkPair': [[0, 0] for _ in range(n)], 'gv_gkPairDay': [0] * n,
        'gv_gkMailLink': [[False] * n for _ in range(n)], 'gv_gkMailDay': 0,
        'gv_mute': [[False] * n for _ in range(n)], 'gv_chatPrivilege': [True] * n,
        'gv_gameStarted': True, 'gv_gameOver': False, 'gv_isNight': False,
        'gv_nightProcessingPhase': False, 'gv_dayActions': True, 'gv_dayOver': False,
        'gv_trialOn': False, 'gv_onTrial': 0, 'gv_nightEvents': False,
        'gv_dayNumber': 3, 'gv_bhFactionChatOpen': False,
        'gv_playerSpot': list(range(n)), 'gv_gkPanel': 100,
        'gv_gkPanelClear': 101, 'gv_gkPanelClose': 102,
        'gv_gkPanelButton': list(range(110, 126)), 'gv_gkPanelDay': [3] * n,
        'PlayerGroupHasPlayer': lambda group, p: p in group,
        'RandomInt': lambda low, high: low,
        'StringExternal': lambda key: key,
        'StringToText': str,
        'IntToString': str,
        'StringToInt': lambda s: int(s) if re.fullmatch(r'[+-]?\d+', s or '') else 0,
        'StringWord': lambda s, i: s.split()[i - 1] if len(s.split()) >= i else '',
        'gf_GKNotice': lambda *args: None,
        'gf_GKLabel': lambda p: str(p),
        'gf_GKPanelRefresh': lambda p: None,
        'DialogIsVisible': lambda *args: True,
        'DialogControlIsVisible': lambda *args: True,
        'DialogControlIsEnabled': lambda *args: True,
        'DialogSetVisible': lambda *args: None,
        'PlayerGroupSingle': lambda p: {p},
    }
    exec(translate('gf_GKIs'), env)
    env['gf_BHVisitAction'] = lambda p: env['gv_visitation'].__setitem__(p, env['gv_action'][p][0])
    env['gf_BHWentTo'] = lambda p, target: target != 0 and target in (env['gv_visitation'][p], env['gv_visitation2'][p])
    env['gf_GKMailRoute'] = lambda *args: None
    env['EventPlayer'] = lambda: 1
    env['EventDialogControl'] = lambda: 111
    env['EventChatMessage'] = lambda full: '-pair 2 3'
    for name in HELPERS:
        exec(translate(name), env)
    return env


class Abilities(unittest.TestCase):
    def setUp(self):
        self.s = state()

    def call(self, name, *args):
        return self.s['gf_GK' + name](*args)

    def role(self, p, role):
        self.s['gv_roles'][p] = [role, 3]

    def test_constructor_snapshot_wins_over_changed_raw_role(self):
        self.s['gv_gkRole'][1] = 35
        self.s['gv_roles'][1] = [1, 1]
        self.assertTrue(self.s['gf_GKIs'](1))
        self.assertTrue(self.call('Role', 1, 35))
        self.assertFalse(self.call('Role', 1, 33))
        self.assertTrue(self.call('DayCan', 1, 35))

    def test_shield_uses_swapped_visit_and_is_one_charge(self):
        self.role(1, 36)
        self.s['gv_action'][1][0] = 2
        self.s['gv_visitation'][1] = 3
        self.call('ResolveEarly')
        self.assertEqual(self.s['gv_immuneChance'][2:4], [0, 1])
        self.assertTrue(self.s['gv_gkUsed'][1])
        self.assertFalse(self.s['gv_immune'][3][0])
        self.call('ResolveEarly')
        self.assertEqual(self.s['gv_immuneChance'][3], 1)

    def test_restriction_and_jail_do_not_consume(self):
        for field in ('gv_roleblocked', 'gv_jailed'):
            self.role(1, 36)
            self.s['gv_visitation'][1] = 2
            self.s[field][1] = 9
            self.call('ResolveEarly')
            self.assertFalse(self.s['gv_gkUsed'][1])
            self.assertEqual(self.s['gv_immuneChance'][2], 0)
            self.s[field][1] = 0

    def test_witness_self_and_dual_visit_deduplication(self):
        self.role(1, 33)
        self.s['gv_action'][1][0] = 1
        self.call('PrepareVisits')
        self.call('ResolveEarly')
        self.s['gv_visitation'][2] = 1
        self.s['gv_visitation2'][2] = 1
        self.s['gv_visitation2'][3] = 1
        self.call('WitnessSnapshot')
        self.assertEqual(self.s['gv_gkWitnessCount'][1], 2)

    def test_vote_day_is_next_day_and_block_does_not_consume(self):
        self.role(1, 37)
        self.s['gv_visitation'][1] = 2
        self.s['gv_roleblocked'][1] = 9
        self.call('ResolveEarly')
        self.assertFalse(self.s['gv_gkUsed'][1])
        self.s['gv_roleblocked'][1] = 0
        self.call('ResolveEarly')
        self.assertEqual(self.s['gv_gkVoteDay'][2], 4)
        self.assertTrue(self.s['gv_gkUsed'][1])

    def test_atomic_pair_validation_and_self_allowed(self):
        self.role(1, 34)
        self.assertTrue(self.call('MailSet', 1, 1, 2))
        before = self.s['gv_gkPair'][1][:]
        for first, second in [(1, 1), (2, 16), (0, 3)]:
            self.assertFalse(self.call('MailSet', 1, first, second))
            self.assertEqual(self.s['gv_gkPair'][1], before)

    def test_freeze_direct_adjacency_dead_messenger_and_no_auto_join(self):
        self.role(1, 34)
        self.role(2, 34)
        self.call('MailSet', 1, 3, 4)
        self.call('MailSet', 2, 3, 5)
        self.s['gv_alivePlayers'].remove(1)
        self.call('MailFreeze')
        self.s.update(gv_isNight=True, gv_bhFactionChatOpen=True)
        self.assertTrue(self.call('MailPeer', 3, 4))
        self.assertTrue(self.call('MailPeer', 4, 3))
        self.assertTrue(self.call('MailPeer', 3, 5))
        self.assertFalse(self.call('MailPeer', 4, 5))
        self.assertFalse(self.call('MailMember', 1))
        self.assertFalse(self.call('MailMember', 2))
        self.assertTrue(self.call('MailHidden', 4, 7))
        self.assertTrue(self.call('MailHidden', 7, 4))
        self.s['gv_mute'][4][3] = True
        self.assertFalse(self.call('MailPeer', 3, 4))
        self.assertTrue(self.call('MailPeer', 4, 3))
        self.s['gv_bhFactionChatOpen'] = False
        self.assertFalse(self.call('MailPeer', 3, 5))
        self.assertTrue(self.call('MailIntercept', 3, 'closed-window message'))
        self.s['gv_jailed'][3] = 9
        self.assertFalse(self.call('MailIntercept', 3, 'jail path wins'))

    def test_dead_messenger_changed_to_witness_still_freezes_today_pair(self):
        self.role(1, 34)
        self.assertTrue(self.call('MailSet', 1, 2, 3))
        self.s['gv_alivePlayers'].remove(1)
        self.role(1, 33)
        self.s['gv_gkRole'][1] = 33
        self.call('MailFreeze')
        self.assertTrue(self.s['gv_gkMailLink'][2][3])
        self.assertTrue(self.s['gv_gkMailLink'][3][2])
        self.assertFalse(self.call('MailMember', 1))
        # Neither the retained pair nor a changed profession revives a dead
        # endpoint, and yesterday's pair must never carry into another night.
        self.s['gv_alivePlayers'].remove(2)
        self.s['gv_gkMailDay'] = 0
        self.call('MailFreeze')
        self.assertFalse(self.s['gv_gkMailLink'][2][3])
        self.s['gv_alivePlayers'].add(2)
        self.s['gv_dayNumber'] += 1
        self.call('MailFreeze')
        self.assertFalse(self.s['gv_gkMailLink'][2][3])

    def test_old_gr_partner_rejects_guoke_self_parent_and_child(self):
        partner = self.s['gf_GSGRPartner']
        self.assertEqual(partner(0), 0)
        self.assertEqual(partner(16), 0)
        self.s['gv_grChild'][1] = 2
        self.s['gv_grParent'][2] = 1
        self.assertEqual(partner(1), 2)
        self.assertEqual(partner(2), 1)
        self.role(2, 33)
        self.s['gv_gkRole'][2] = 33
        self.assertEqual(partner(1), 0)
        self.assertEqual(partner(2), 0)
        self.assertEqual(self.s['gv_grChild'][1], 2)
        self.assertEqual(self.s['gv_grParent'][2], 1)
        # Independently cover an ordinary child's GK parent (reverse edge).
        self.s['gv_gkRole'][2] = 0
        self.s['gv_roles'][2] = [22, 3]
        self.s['gv_gkRole'][1] = 35
        self.role(1, 35)
        self.assertEqual(partner(1), 0)
        self.assertEqual(partner(2), 0)

    def test_reborn_gambler_loses_old_gr_chat_but_keeps_lineage(self):
        partner = self.s['gf_GSGRPartner']
        self.s['gv_grChild'][1] = 2
        self.s['gv_grParent'][2] = 1
        for reborn in (1, 2):
            with self.subTest(reborn=reborn):
                self.s['gv_xrLifeDid'][reborn] = True
                self.role(reborn, 17)
                self.assertEqual(partner(1), 0)
                self.assertEqual(partner(2), 0)
                self.assertEqual(self.s['gv_grChild'][1], 2)
                self.assertEqual(self.s['gv_grParent'][2], 1)
                self.s['gv_xrLifeDid'][reborn] = False
                self.assertEqual(partner(1), 2)
                self.assertEqual(partner(2), 1)

    def test_floor_mapping_and_commands_are_strict_atomic(self):
        self.role(1, 34)
        self.s['gv_playerSpot'][2:4] = [3, 2]
        self.assertEqual(self.call('AtFloor', 2), 3)
        for word in ('', '0', '16', '2x', '+2', '02', '-1'):
            self.assertEqual(self.call('ParseFloor', word), 0)
        command = self.s['gt_GKCommand_Func']
        self.assertTrue(command(True, True))
        self.assertEqual(self.s['gv_gkPair'][1], [3, 2])
        self.s['EventChatMessage'] = lambda full: '-pair 2 3 trailing'
        self.assertFalse(command(True, True))
        self.assertEqual(self.s['gv_gkPair'][1], [3, 2])

    def test_puppet_candidates_exclude_original_feigned_dead_absent(self):
        for p in range(1, 7):
            self.role(p, 35)
            self.s['gv_gkPuppet'][p] = True
        self.s['gv_bhFeignRole'][3] = 7
        self.s['gv_alivePlayers'].remove(4)
        self.s['gv_currentPlayers'].remove(5)
        self.assertEqual(self.call('Substitute', 6), 2)
        self.s['gv_isNight'] = True
        self.assertEqual(self.call('Substitute', 6), 6)

    def test_panel_unknown_stale_and_clear_both_slots(self):
        self.role(1, 34)
        self.call('MailSet', 1, 2, 3)
        callback = self.s['gt_GKPanel_Func']
        self.s['EventDialogControl'] = lambda: 999
        self.assertFalse(callback(True, True))
        self.s['EventDialogControl'] = lambda: 101
        self.s['gv_gkPanelDay'][1] = 2
        self.assertFalse(callback(True, True))
        self.assertEqual(self.s['gv_gkPair'][1], [2, 3])
        self.s['gv_gkPanelDay'][1] = 3
        self.assertTrue(callback(True, False))
        self.assertEqual(self.s['gv_gkPair'][1], [2, 3])
        self.assertTrue(callback(True, True))
        self.assertEqual(self.s['gv_gkPair'][1], [0, 0])


if __name__ == '__main__':
    unittest.main()
