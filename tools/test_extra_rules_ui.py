#!/usr/bin/env python3
"""Source-only guards for extra-rules popup layering, not an SC2 render test."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from test_egun import function, mask

ROOT = Path(__file__).resolve().parents[1]


def check(source: str) -> None:
    build = mask(function(source, 'gf_XRBuild'))
    slot = mask(function(source, 'gf_BHSaveSlotBuild'))
    click = mask(function(source, 'gt_XR_Func'))

    # Apply the priority to the parent dialog, after capturing its handle and
    # before creating its children. Raising only the background image is wrong.
    priorities = list(re.finditer(
        r'\bDialogSetRenderPriority\(gv_xrPanel,\s*(\d+)\);', build))
    assert len(priorities) == 1, 'extra-rules popup needs one parent-dialog priority'

    priority = int(priorities[0][1])
    assert priority == 700, 'keep the extra-rules popup in its elevated UI layer'
    assert (build.index('gv_xrPanel = DialogLastCreated();')
            < priorities[0].start()
            < build.index('libNtve_gf_CreateDialogItemImage(gv_xrPanel,'))

    # A future explicit save-slot layer must remain below the popup.
    slot_priorities = re.findall(
        r'\bDialogSetRenderPriority\(gv_saveSlotFrame,\s*(\d+)\);', slot)
    assert all(int(value) < priority for value in slot_priorities)

    # Preserve independent open/close behavior and all three host-only options.
    assert ('DialogSetVisible(gv_xrPanel, PlayerGroupSingle(EventPlayer()), '
            '(DialogIsVisible(gv_xrPanel, EventPlayer()) == false));') in click
    assert 'DialogSetVisible(gv_xrPanel, PlayerGroupSingle(EventPlayer()), false);' in click
    assert 'EventPlayer() != gv_host' in click
    assert 'DialogSetVisible(gv_saveSlotFrame,' not in click
    assert build.count('libNtve_gf_CreateDialogItemCheckBox(gv_xrPanel,') == 3
    for control in ('gv_xrDeadBox', 'gv_xrGangBox', 'gv_xrLifeBox', 'gv_xrClose'):
        assert f'{control} = DialogControlLastCreated();' in build


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path,
                        default=ROOT / 'work/blackhand/CustomLogic.galaxy')
    args = parser.parse_args()

    check(args.script.read_text(encoding='utf-8'))
    print('PASS: extra-rules parent-dialog layering and UI wiring (source only)')


if __name__ == '__main__':
    main()
