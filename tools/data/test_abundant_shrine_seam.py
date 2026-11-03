#!/usr/bin/env python3
"""Validate the Route 14 and Abundant Shrine matrix and collision seam."""

import csv
import json
import unittest
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class AbundantShrineSeamTest(unittest.TestCase):
    def test_matrix_events_scripts_and_flat_corridor(self):
        def load(path):
            return json.loads((ROOT / path).read_text())

        matrix = load("res/field/matrices/overworld.json")
        original = load("res/field/matrices/abundant_shrine.json")
        zone = load("res/field/zones/abundant_shrine.json")
        route = load("res/field/events/route_14.json")
        shrine = load("res/field/events/abundant_shrine.json")
        self.assertEqual((zone["matrix"], zone["map_type"]), ("MAP_MATRIX_OVERWORLD", 0))
        self.assertEqual((zone["fly"]["x"], zone["fly"]["z"]), (613, 324))
        for dz in range(2):
            for dx in range(2):
                self.assertEqual(matrix["maps"][10 + dz][19 + dx], original["maps"][dz][dx])
                self.assertEqual(matrix["zones"][10 + dz][19 + dx], "ZONE_ABUNDANT_SHRINE")
        self.assertEqual(route["warps"][0]["zone"], 65535)
        self.assertEqual(shrine["warps"][0]["zone"], 65535)
        self.assertEqual(shrine["warps"][1]["zone"], "ZONE_ABUNDANT_SHRINE_2")
        self.assertEqual((shrine["triggers"][0]["grid"]["x"], shrine["triggers"][0]["grid"]["z"]), (629, 337))
        script = (ROOT / "res/field/scripts/abundant_shrine.s").read_text()
        self.assertIn("ActorWalkRoute 11, 630, 333, 1, 8, 0", script)
        self.assertIn("EvCameraMoveTo 9688, 0, 0xed000, 0x2938000, 32795, 0x1718000, 40", script)

        cells = {}
        for chunk_z in range(10, 13):
            for chunk_x in range(19, 23):
                name = matrix["maps"][chunk_z][chunk_x]
                if name is None:
                    continue
                path = ROOT / "res/field/maps/models" / name.removeprefix("MAP_MODEL_").lower() / "terrain_0.csv"
                if not path.exists():
                    continue
                with path.open(newline="") as stream:
                    for row in csv.DictReader(stream):
                        pos = (chunk_x * 32 + int(row["x"]), chunk_z * 32 + int(row["z"]))
                        cells[pos] = (int(row["tile_type"]), int(row["offset"]), int(row["shape"]))
        a, b = route["warps"][0]["grid"], shrine["warps"][0]["grid"]
        start, end = (a["x"] // 16, a["z"] // 16), (b["x"] // 16, b["z"] // 16)
        queue, visited = deque([start]), {start}
        while queue:
            x, z = queue.popleft()
            for neighbor in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                tile = cells.get(neighbor)
                if tile is None or neighbor in visited:
                    continue
                kind, height, shape = tile
                if kind == 0xffffffff or kind & 0xffff == 0xffff or (kind >> 16) & 1:
                    continue
                if height != 3 or shape != 0:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
        self.assertIn(end, visited)


if __name__ == "__main__":
    unittest.main()
