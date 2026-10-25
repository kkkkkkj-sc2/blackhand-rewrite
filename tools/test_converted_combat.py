#!/usr/bin/env python3
"""Execute converted Vigilante guilt and existing Forester traps, UBSan/bounds.

Complete production kill/role-setup/trap bodies execute using the faction suite's
explicit object, UI, sound, wait and death-delivery doubles. The Vigilante action
renderer is a recording boundary; availability is computed by actual SKR code.
Includes public Spy disguise versus true-faction trap eligibility. This is not
SC2 compiler/rendering/timing/multiplayer verification.
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

import test_faction_interactions as legacy
from test_egun import SCRIPT, function


def harness(source: str) -> str:
    original, original_base = legacy.EXTRA, legacy.core.harness
    legacy.EXTRA += ('gf_ESVigilanteKill', 'gf_SKR_1_yijing')
    boundary = 'void gf_RAVigilanteActions(int p) { events.push_back("vigilante-ui:"+std::to_string(p)); }\n'
    legacy.core.harness = lambda text: original_base(text) + boundary
    try:
        code = legacy.harness(source)
    finally:
        legacy.EXTRA, legacy.core.harness = original, original_base
    code = code.replace(function(code, 'main'), '')
    town, neutral = function(source, 'gf_RTTownRoleText'), function(source, 'gf_RTNeutralRoleText')
    for key in ('BHFAPPTRAIT', 'BHFVIGTRAIT', 'BHFFORTRAIT', 'BHFMEDTRAIT'):
        assert town.count('Param/Value/' + key) == 1, ('Town trait', key)

    assert neutral.count('Param/Value/BHFMEMTRAIT') == 1
    print('PASS card wiring: four Town traits and amnesiac faction trait', flush=True)
    for name in ('gf_ESVigilanteKill', 'gf_SKR_1_yijing', 'gf_HLResolveOne'):
        body = function(source, name)
        line = source[:source.index(body)].count('\n') + 1
        print(f'{name}: {line}..{line + body.count(chr(10))}', flush=True)

    return code + r'''
void vigilanteMatrix() {
    for(int team:{0,2,5}) for(int pool:{1,2,3,5}) for(int victimTeam:{0,2,5}) for(int bits=0;bits<8;++bits) {
        interactionReset("Vigilante true faction disables guilt regardless of switch");
        converted(1,team,6); role(8,pool,4); gv_bhFaction[8]=victimTeam;
        bool option=bits&1, immune=bits&2, healed=bits&4;
        gv_roleOptions[1][6][0]=option; gv_cooldown[1]=0;
        gv_immuneChance[8]=0; gv_immune[8][0]=immune; gv_healing[8]=healed?1:0;
        gf_ESVigilanteKill(8,1);
        CHECK(gv_cooldown[1]==(!immune && team==0 && pool==1 && option?3:0));
        CHECK(gf_BHFaction(1)==(team?team:1));
        CHECK(gv_roles[1][1]==1 && gv_roles[1][0]==6);
        CHECK(killed==(!immune && !healed?std::vector<int>{8}:std::vector<int>{}));
        CHECK(gv_healing[8]==(healed && !immune?0:int(healed)));
        CHECK(gv_bhFaction[8]==victimTeam && gv_roles[8][1]==pool);
    }
    for(int team:{0,2,5}) for(int cooldown=0;cooldown<=4;++cooldown) for(int shots:{0,1,3}) {
        interactionReset("Old guilt no longer locks a converted Vigilante action panel");
        converted(1,team,6); gv_cooldown[1]=cooldown; gv_shots[1]=shots;
        gf_SKR_1_yijing(1);
        CHECK(gv_cooldown[1]==(team?0:cooldown));
        CHECK(gv_variableOptions[1][0]==int(shots>0 && (team!=0 || cooldown==0)));
        CHECK(gv_shots[1]==shots && eventCount("vigilante-ui:1")==1);
    }
}
void existingTrapMatrix() {
    for(int team:{2,5}) for(int slot:{0,1}) for(bool second:{false,true}) for(bool dead:{false,true}) for(int scenario=0;scenario<4;++scenario) {
        interactionReset("Old Town trap follows converted owner, sparing true teammates and guards");
        converted(1,team,22); gv_hlHouse[1][slot]=15; gv_hlLeft[1][slot]=2;
        gv_hlFaction[1][slot]=1; // Placed BEFORE conversion.
        if(dead) { PlayerGroupRemove(gv_alivePlayers,1); gv_diedAtNight[1]=true; }
        converted(2,team,8); // Publicly Town Spy, but actually our gang.
        if(second) gv_visitation2[2]=15; else gv_visitation[2]=15;
        if(scenario>=1) { role(3,team==2?5:2,1); gv_visitation[3]=15; }
        if(scenario>=2) { role(4,1,4); gv_visitation[4]=15; }
        if(scenario==3) { converted(5,team,11); gv_guarded[4]=5; }
        gf_HLResolveOne(1,slot);
        CHECK(gv_hlFaction[1][slot]==team);
        CHECK(gv_hlLeft[1][slot]==(scenario==0?1:0));
        CHECK(killed==(scenario==1?std::vector<int>{3}:scenario==2?std::vector<int>{4}:std::vector<int>{}));
        CHECK(gv_alivePlayers&(1u<<2));
        CHECK(gv_damage[2]==0 && !gv_diedAtNight[2]);
        if(scenario>=2) CHECK(gv_alivePlayers&(1u<<3)); // Town has higher priority than opposite gang.
        if(scenario==3) CHECK((gv_alivePlayers&(1u<<5)) && gv_damage[5]==0);
    }
    for(int team:{2,5}) {
        interactionReset("New Forester traps still record actual faction and spare native gang");
        converted(1,team,22); gv_shots[1]=2; gv_visitation[1]=15;
        role(2,team,1); gv_visitation[2]=15;
        role(3,1,4); gv_visitation2[3]=15;
        gf_HLForesterNight();
        CHECK(gv_shots[1]==1 && gv_hlFaction[1][0]==team);
        CHECK(killed==std::vector<int>{3} && (gv_alivePlayers&(1u<<2)));
    }
}
int main() {
    vigilanteMatrix(); existingTrapMatrix();
    std::cout << "PASS converted combat: " << fixtures << " fixtures, " << checks
              << " assertions; actual guilt/availability/trap bodies; UBSan/bounds" << std::endl;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=SCRIPT)
    args = parser.parse_args()
    code = harness(args.script.read_text())
    with tempfile.TemporaryDirectory(prefix='bh317-combat-') as directory:
        cpp, binary = Path(directory) / 'combat.cpp', Path(directory) / 'combat'
        cpp.write_text(code)
        subprocess.run(['g++', '-std=c++17', '-O1', '-g', '-fsanitize=undefined,bounds',
                        '-fno-sanitize-recover=all', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
