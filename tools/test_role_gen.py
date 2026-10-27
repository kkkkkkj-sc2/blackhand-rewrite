#!/usr/bin/env python3
"""Regression tests for pool-anchored role definitions and saved default weights."""
from pathlib import Path
import tempfile
import unittest

from role_gen import Script


class DefinitionBlockTests(unittest.TestCase):
    def test_saved_default_weight_preserves_pool_and_slot_boundaries(self):
        source = """void gf_InitializeVariables () {
    gv_roleWeights[3][30] = 0.0;
    gv_bankSaveWeights[0][3][30] = 0.0;
    gv_bankSaveWeights[1][3][30] = 9.0;
    gv_bankSaveWeights[0][2][30] = 8.0;
    gv_roleWeights[3][31] = 7.0;
    gv_bankSaveWeights[0][3][31] = 6.0;
    gv_roleNameArray[1][1] = StringExternal("Param/Value/TOWN");
    gv_roleInvestigatorArray[8][1][1] = StringExternal("Param/Value/OTHER");
    gv_bankSaveWeights[0][1][1] = 1.0;
    gv_bankSaveWeights[8][1][1] = 5.0;
}
void gf_DefaultRoleOptions () {
    gv_roleOptions[3][30][10] = false;
    gv_roleOptions[1][1][0] = true;
}
"""
        with tempfile.TemporaryDirectory(prefix='role-gen-regression-') as directory:
            path = Path(directory) / 'definitions.galaxy'
            path.write_text(source, encoding='utf-8')
            script = Script(path)
            prophet = script.def_block(3, 30)
            citizen = script.def_block(1, 1)

        self.assertEqual(prophet.splitlines(), [
            '    gv_roleWeights[3][30] = 0.0;',
            '    gv_bankSaveWeights[0][3][30] = 0.0;',
            '    gv_roleOptions[3][30][10] = false;',
        ])
        self.assertEqual(citizen.splitlines(), [
            '    gv_roleNameArray[1][1] = StringExternal("Param/Value/TOWN");',
            '    gv_bankSaveWeights[0][1][1] = 1.0;',
            '    gv_roleOptions[1][1][0] = true;',
        ])

    def test_production_prophet_has_both_zero_default_weights(self):
        block = Script().def_block(3, 30)
        self.assertIn('gv_roleWeights[3][30] = 0.0;', block)
        self.assertIn('gv_bankSaveWeights[0][3][30] = 0.0;', block)


if __name__ == '__main__':
    unittest.main()
