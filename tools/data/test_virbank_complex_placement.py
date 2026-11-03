#!/usr/bin/env python3
"""Check the inner Virbank Complex placement and its retained entrance warp."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class VirbankComplexPlacementTest(unittest.TestCase):
    def test_matrix_warps_and_scene_positions(self):
        def load(path):
            return json.loads((ROOT / path).read_text())

        matrix = load("res/field/matrices/overworld.json")
        inner_matrix = load("res/field/matrices/virbank_complex_2.json")
        inner = load("res/field/events/virbank_complex_2.json")
        outer = load("res/field/events/virbank_complex.json")
        zone = load("res/field/zones/virbank_complex_2.json")
        self.assertEqual(zone["matrix"], "MAP_MATRIX_OVERWORLD")
        self.assertEqual((zone["fly"]["x"], zone["fly"]["z"]), (197, 708))
        for z in range(2):
            self.assertEqual(matrix["maps"][22 + z][6], inner_matrix["maps"][z][0])
            self.assertEqual(matrix["zones"][22 + z][6], "ZONE_VIRBANK_COMPLEX_2")
        self.assertEqual((outer["warps"][0]["zone"], outer["warps"][0]["warp"]),
                         ("ZONE_VIRBANK_COMPLEX_2", 0))
        self.assertEqual((inner["warps"][0]["zone"], inner["warps"][0]["warp"]),
                         ("ZONE_VIRBANK_COMPLEX", 0))
        self.assertEqual((inner["warps"][0]["grid"]["x"], inner["warps"][0]["grid"]["z"]),
                         (3336, 11544))
        script = (ROOT / "res/field/scripts/virbank_complex_2.s").read_text()
        self.assertEqual(script.count("ActorSetGPos 7, 221, 0, 736, 0"), 2)
        self.assertEqual(script.count("ActorSetGPos 7, 200, 0, 751, 2"), 2)
        self.assertEqual(script.count("ActorSetGPos 7, 212, 65535, 762, 3"), 2)


if __name__ == "__main__":
    unittest.main()
