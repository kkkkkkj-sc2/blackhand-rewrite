#!/usr/bin/env python3
"""Static Guoke hook regressions against real production Galaxy source.

Checks function-local guards, dispatch arguments and textual call order. These
are STRUCTURAL assertions, not executed chat/runtime/engine tests or proofs of
all possible control-flow paths. No temporary fragments or source edits.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from test_bishop_votes import balanced_end, function

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'work/blackhand/CustomLogic.galaxy'


def compact(code: str) -> str:
    return re.sub(r'\s+', '', code)


def uncomment(code: str) -> str:
    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"', lambda m: m.group() if m.group().startswith('"') else '', code, flags=re.S)


def paren_end(code: str, start: int) -> int:
    depth = 0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|[()]', code[start:]):
        if token.group() == '(':
            depth += 1
        elif token.group() == ')':
            depth -= 1
            if depth == 0:
                return start + token.end()

    raise AssertionError('unbalanced condition')


def blocks(code: str) -> list[tuple[str, str, int, int]]:
    """Return real if condition/body ranges; comments are already stripped."""
    result = []
    for match in re.finditer(r'\bif\s*\(', code):
        opening = code.index('(', match.start())
        closing = paren_end(code, opening)
        brace = closing
        while brace < len(code) and code[brace].isspace():
            brace += 1

        if brace < len(code) and code[brace] == '{':
            end = balanced_end(code, brace)
            result.append((compact(code[opening + 1:closing - 1]), code[brace + 1:end - 1], match.start(), end))

    return result


class Hooks:
    def __init__(self, source: str):
        self.source = source
        self.cache: dict[str, str] = {}
        self.checked = 0

    def get(self, name: str) -> str:
        if name not in self.cache:
            self.cache[name] = uncomment(function(self.source, name))

        return self.cache[name]

    def check(self, condition: bool, message: str) -> None:
        assert condition, message
        self.checked += 1

    def guard(self, name: str, needle: str) -> tuple[str, str, int, int]:
        matches = [block for block in blocks(self.get(name)) if compact(needle) in block[0]]
        self.check(len(matches) == 1, f'{name}: expected one guard containing {needle}, got {len(matches)}')
        return matches[0]

    def before(self, name: str, earlier: str, later: str) -> None:
        code = compact(self.get(name))
        self.check(earlier in code and later in code and code.index(earlier) < code.index(later), f'{name}: require {earlier} before {later}')


def audit(source: str) -> int:
    hooks = Hooks(source)
    # Both the live chat implementation and legacy copied implementation must
    # consume mail before any native title/recipient routing can run.
    for name in ('gf_CBAddChat', 'gf_CBAddChatE8AF95E8AF95E79C8BE883BDE4B88DE883BDE794A8'):
        condition, body, _, end = hooks.guard(name, 'gf_GKMailMember(lp_player)==true')
        hooks.check('gv_isNight==true' in condition and 'gv_gameOver==false' in condition, name + ': night/endgame mail gate')
        hooks.check(compact(body) == 'gf_GKMailRoute(lp_player,lp_message);return;', name + ': mail must route then return without old-chat fallthrough')
        implementation = compact(uncomment(function(source, name).split('// Implementation', 1)[1]))
        hooks.check(implementation.startswith('if(' + condition + '){'), name + ': mail interception is the first implementation branch')
        hooks.before(name, 'gf_GKMailRoute(lp_player,lp_message);', 'gf_GSChatRecipient(lp_player,lv_a)')
        hooks.check('gf_GSChatRecipient' in hooks.get(name)[end:], name + ': old recipients remain behind interception')

    # General chat recipients, special XR/GR/public inherited recipients, and
    # direct whisper must deny OLD routing first when either endpoint is mail.
    for name, needle, result in (
        ('gf_GSChatRecipient', 'gf_GKMailHidden(speaker,listener)==true', 'returnfalse;'),
        ('gf_GSSpecialRecipient', 'gf_GKMailHidden(speaker,listener)==true', 'returnfalse;'),
        ('gf_CBWhisper', 'gf_GKMailHidden(lp_player,lp_recipient)==true', 'return;'),
    ):
        _, body, start, _ = hooks.guard(name, needle)
        hooks.check(compact(body) == result, name + ': isolation branch must immediately reject')
        prefix = hooks.get(name)[:start]
        hooks.check(not re.search(r'\breturn\b', prefix) and 'gf_CBSystemMessage(' not in prefix, name + ': no early fallback/delivery before isolation')

    hooks.check('gf_GKMailHidden' not in hooks.get('gf_CBSystemMessage'), 'Generic system messages must not be filtered by old-chat isolation')
    condition, body, _, _ = hooks.guard('gf_XRGangSay', 'gf_GKMailHidden(lp_player,lv_a)==false')
    hooks.check('PlayerGroupHasPlayer(gv_alivePlayers,lv_a)==true' in condition and 'gv_mute[lv_a][lp_player]==false' in condition and 'gf_CBSystemMessage(' in body, 'XR live/mute recipient gate must include isolation')

    router = 'gf_BHPlayerChat'
    _, body, _, _ = hooks.guard(router, 'gf_GKMailIntercept(lp_player,lp_message)==true')
    hooks.check(compact(body) == 'return;', 'BHPlayerChat mail intercept must consume input')
    hooks.before(router, 'gv_transientMessages[lp_player]+=7;', 'gf_GKMailIntercept(lp_player,lp_message)')
    hooks.before(router, 'gv_ttHush!=0', 'gf_GKMailIntercept(lp_player,lp_message)')
    hooks.before(router, 'gf_GKMailIntercept(lp_player,lp_message)', 'gf_GSChatSay(lp_player,lp_message)')
    condition, _, _, _ = hooks.guard(router, 'gf_GSChatSay(lp_player,lp_message)==true')
    hooks.check('(gv_isNight==false)||(gf_GKMailMember(lp_player)==false)' in condition, 'GS pre-router must not bypass native jail/silence priority for mail members')
    for needle, call in (('gf_XRNeutralFatal(', 'gf_XRGangSay(lp_player,lp_message);'), ('gv_grPrivateChat[lp_player]==true', 'gf_GSSpecialSay(lp_player,lp_message,2,true);')):
        condition, body, _, _ = hooks.guard(router, needle)
        hooks.check('gf_GKMailMember(lp_player)==false' in condition and call in compact(body), 'XR/GR pre-router must exclude mail sender: ' + needle)

    # Raw lineage edges survive reincarnation; old GR routing and its toggle
    # must both use the GK-aware shared partner resolver, never raw graph reads.
    _, gr_body, _, _ = hooks.guard(router, 'gv_grPrivateChat[lp_player]==true')
    hooks.check('lv_partner=gf_GSGRPartner(lp_player);' in compact(gr_body), 'BHPlayerChat GR route must use shared partner helper')
    hooks.check('gv_grChild' not in gr_body and 'gv_grParent' not in gr_body, 'BHPlayerChat GR route cannot bypass helper via raw lineage graph')
    partner_branches = [block for block in blocks(gr_body) if block[0] == '(lv_partner!=0)']
    hooks.check(len(partner_branches) == 1 and 'GRCHATMSG' in partner_branches[0][1], 'GR delivery requires nonzero validated partner')
    hooks.before('gf_GRChatToggle', 'lv_partner=gf_GSGRPartner(lp_player);', 'gv_grPrivateChat[lp_player]=lp_on;')
    _, unavailable, _, _ = hooks.guard('gf_GRChatToggle', 'lv_partner==0')
    hooks.check('return;' in compact(unavailable), 'GR toggle must reject unavailable/GK endpoints')
    hooks.check('gv_grChild' not in hooks.get('gf_GRChatToggle') and 'gv_grParent' not in hooks.get('gf_GRChatToggle'), 'GR toggle cannot read raw graph instead of validated partner')
    _, no_self, _, _ = hooks.guard('gf_GSGRPartner', 'gf_GKIs(p)==true')
    hooks.check(compact(no_self) == 'return0;', 'GK self must have no old GR partner')
    for edge in ('gv_grChild[p]', 'gv_grParent[p]'):
        condition, body, _, _ = hooks.guard('gf_GSGRPartner', 'gf_GKIs(' + edge + ')==false')
        hooks.check(edge + '>=1' in condition and edge + '<=15' in condition and compact(body) == 'return' + edge + ';', 'GR partner validates bounds and excludes GK edge: ' + edge)

    # The parent's/child's DIRECT GR partner delivery does not pass through
    # GSSpecialRecipient and therefore still requires mail isolation as well.
    _, partner_body, _, _ = hooks.guard(router, 'gf_GKMailHidden(lp_player,lv_partner)==false')
    hooks.check('GRCHATMSG' in partner_body and ',lv_partner,lp_player,' in compact(partner_body), 'GR direct-partner delivery must be inside isolated branch')
    crying = [block for block in blocks(hooks.get(router)) if block[0] == '(gv_crying[lp_player]==true)']
    hooks.check(len(crying) == 1, 'Find unique native night-cry branch')
    receiver = [block for block in blocks(crying[0][1]) if 'PlayerGroupHasPlayer(gv_currentPlayers,lv_a)==true' in block[0]]
    hooks.check(len(receiver) == 1 and 'gf_GKMailHidden(lp_player,lv_a)==false' in receiver[0][0], 'Night cry recipient loop must exclude mail participants')

    # Four observer branches are distinct from actual prisoner<->jailer lines.
    observers = [block for block in blocks(hooks.get(router)) if 'gf_BHFaction(lv_a)' in block[0] and 'gv_jailing[lv_a]!=' in block[0]]
    hooks.check(len(observers) == 4, 'Expected jail/kidnap observer gates: Mafia and Triad in both directions')
    for condition, body, _, _ in observers:
        hooks.check('gf_GKMailHidden(lp_player,lv_a)==false' in condition and 'gf_GKIs(lv_a)==false' in condition, 'Every jail faction observer must exclude mail and inherited-faction Guoke')
        hooks.check('gf_CBSystemMessage(' in body, 'Observer gate must own real delivery')

    hooks.check(sum('gv_roles[gv_jailed[lp_player]]' in block[0] for block in observers) == 2, 'Both captive->faction observer gates are covered')
    hooks.check(sum('gv_roles[lp_player][0]==9' in block[0] for block in observers) == 2, 'Both jailer->faction observer gates are covered')
    _, direct_jail, _, _ = hooks.guard(router, 'gv_jailing[lv_a]==lp_player')
    hooks.check('gf_CBSystemMessage(' in direct_jail and 'gf_GKMailHidden' not in direct_jail, 'Actual prisoner->jailer messages retain native priority')

    # A symbiote cannot inherit an original channel through either a Guoke or
    # a paired host; check both self and host for both identity and membership.
    condition, body, start, _ = hooks.guard('gf_GSChatPeer', 'gf_GKIs(sym)==true')
    hooks.check(compact(body) == 'returnfalse;', 'GS peer identity/mail guard must reject')
    for guard in ('gf_GKIs(sym)==true', 'gf_GKIs(gv_gsHost[sym])==true', 'gf_GKMailMember(sym)==true', 'gf_GKMailMember(gv_gsHost[sym])==true'):
        hooks.check(guard in condition, 'GS peer must exclude self/host identity and membership: ' + guard)

    hooks.check('return true' not in hooks.get('gf_GSChatPeer')[:start], 'GS must not accept a peer before GK/mail rejection')
    hooks.before('gf_GSChatPeer', 'gf_GKIs(sym)', 'gf_GSChatReady(sym)')

    # Constructor reset preserves only this day's committed pairing. Freeze
    # consumes that fact even after the original messenger dies/changes job.
    init = 'gf_GKInit'
    for saved in ('lv_pairFirst=gv_gkPair[lp_player][0];', 'lv_pairSecond=gv_gkPair[lp_player][1];', 'lv_pairDay=gv_gkPairDay[lp_player];'):
        hooks.before(init, saved, 'gf_GKAbilityResetPlayer(lp_player);')

    condition, restore, _, _ = hooks.guard(init, 'lv_pairDay==gv_dayNumber')
    hooks.check('lv_pairDay>0' in condition, 'Only an existing current-day pairing survives constructor reset')
    for assignment in ('gv_gkPair[lp_player][0]=lv_pairFirst;', 'gv_gkPair[lp_player][1]=lv_pairSecond;', 'gv_gkPairDay[lp_player]=lv_pairDay;'):
        hooks.check(assignment in compact(restore), 'Constructor restores preserved pairing field: ' + assignment)
        hooks.before(init, 'gf_GKAbilityResetPlayer(lp_player);', assignment)

    hooks.check('gv_grPrivateChat[lp_player]=false;' in compact(hooks.get(init)), 'Constructor clears active old GR private-chat toggle')
    condition, freeze, _, _ = hooks.guard('gf_GKMailFreeze', 'gv_gkPairDay[p]==gv_dayNumber')
    hooks.check('gv_gkPairDay[p]>0' in condition and 'gf_GKLive(first)==true' in condition and 'gf_GKLive(second)==true' in condition, 'Freeze requires a current committed pairing and two live endpoints')
    hooks.check('gf_GKRole(p' not in condition and 'gf_GKLive(p)' not in condition and 'gv_roles[p]' not in condition, 'Freeze cannot require original messenger current job/alive state')
    hooks.check('gv_gkMailLink[first][second]=true;' in compact(freeze) and 'gv_gkMailLink[second][first]=true;' in compact(freeze), 'Preserved pairing creates symmetric direct adjacency')

    # Inter-function call order is structural only; these assertions do not
    # execute the trigger scheduler, party branches, or role swap algorithms.
    night = 'gt_NightSequence_Func'
    prep = hooks.get('gf_SequencePrep')
    hooks.check(compact(prep).count('gf_GKPrepareVisits();') == 1, 'Visit preparation hook appears exactly once in real SequencePrep')
    hooks.before(night, 'gf_SequencePrep();', 'gf_SequenceBullshit();')
    hooks.before(night, 'gf_SequenceBullshit();', 'gf_SequenceKills();')
    for swap in ('gf_SKU_3_nvwu(lv_a);', 'gf_SKU_1_bashisiji(lv_a);', 'gf_SKU_1_bashisiji_2(lv_a);'):
        hooks.check(swap in compact(hooks.get('gf_SequenceBullshit')), 'Real swap stage still owns ' + swap)

    kills = function(source, 'gf_SequenceKills')
    hooks.check('// Implementation' in kills, 'Kills has explicit implementation boundary')
    implementation = uncomment(kills.split('// Implementation', 1)[1]).lstrip()
    hooks.check(implementation.startswith('gf_GKResolveEarly();'), 'Early Guoke resolution must be the FIRST Kills implementation statement')
    hooks.before('gf_SequenceKills', 'gf_GKResolveEarly();', 'gf_GSApplyShield();')
    hooks.check(compact(hooks.get('gf_SequenceKills')).count('gf_GKResolveEarly();') == 1, 'Early resolve hook appears exactly once')
    hooks.before(night, 'gf_SequenceAfter2();', 'gf_GKWitnessSnapshot();')
    hooks.before(night, 'gf_GKWitnessSnapshot();', 'gv_dayNumber+=1;')

    # Lawyer immunity precedes substitution. Deferred execution receives ONLY
    # the chosen actual victim, and cannot recurse through substitution again.
    execution = 'gf_EExecution'
    _, body, _, _ = hooks.guard(execution, 'gf_LSTrySpare(lp_player,0)==true')
    hooks.check(compact(body) == 'return;', 'Successful lawyer immunity must return without substituting')
    hooks.before(execution, 'gf_LSTrySpare(lp_player,0)', 'gf_GKSubstitute(lp_player)')
    wrapper = compact(hooks.get(execution))
    hooks.check(wrapper.count('gf_GKSubstitute(lp_player)') == 1, 'Substitute is selected exactly once')
    hooks.check('auto_gf_EExecution_lp_player=lv_actual;' in wrapper and 'auto_gf_EExecution_lp_player=lp_player;' not in wrapper, 'Deferred execution must receive actual victim, not original target')
    hooks.before(execution, 'auto_gf_EExecution_lp_player=lv_actual;', 'TriggerExecute(auto_gf_EExecution_Trigger,false,false);')
    callback = compact(hooks.get('auto_gf_EExecution_TriggerFunc'))
    hooks.check('intlp_player=auto_gf_EExecution_lp_player;' in callback, 'Deferred callback binds the actual victim')
    hooks.check(callback.count('gf_KillPlayer(lp_player,false);') == 1 and 'gv_executed[lp_player]=true;' in callback, 'Only actual deferred victim is killed and marked executed')
    hooks.check('gf_GKSubstitute(' not in callback and 'gf_EExecution(' not in callback, 'Execution callback must not recursively substitute another puppet')
    hooks.check('gf_KillPlayer(' not in wrapper, 'Wrapper must not additionally kill original target')
    return hooks.checked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    options = parser.parse_args()
    checks = audit(options.script.read_text())
    print(f'Guoke integration: {checks} STATIC structural assertions passed; source: {options.script}')
    print('Static hook coverage is NOT runtime chat delivery, trigger scheduling, or SC2 engine validation.')


if __name__ == '__main__':
    main()
