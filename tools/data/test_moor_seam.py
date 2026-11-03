#!/usr/bin/env python3
"""Check the Route 8 connection to the Moor of Icirrus."""

import csv
import json
import unittest
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class MoorSeamTest(unittest.TestCase):
    def test_matrix_events_and_flat_corridor(self):
        def load(path):
            return json.loads((ROOT / path).read_text())

        matrix = load("res/field/matrices/overworld.json")
        moor_matrix = load("res/field/matrices/moor_of_icirrus.json")
        zone = load("res/field/zones/moor_of_icirrus.json")
        route = load("res/field/events/route_8.json")
        moor = load("res/field/events/moor_of_icirrus.json")
        self.assertEqual(zone["matrix"], "MAP_MATRIX_OVERWORLD")
        self.assertEqual(zone["map_type"], 0)
        self.assertEqual((zone["fly"]["x"], zone["fly"]["z"]), (197, 100))
        for dz in range(2):
            for dx in range(2):
                self.assertEqual(matrix["maps"][3 + dz][6 + dx], moor_matrix["maps"][dz][dx])
                self.assertEqual(matrix["zones"][3 + dz][6 + dx], "ZONE_MOOR_OF_ICIRRUS")
        self.assertEqual(route["warps"][1]["zone"], 65535)
        self.assertEqual(moor["warps"][0]["zone"], 65535)
        self.assertEqual((moor["npcs"][0]["grid"]["x"], moor["npcs"][0]["grid"]["z"]), (217, 136))
        self.assertEqual(route["warps"][0]["zone"], "ZONE_BRIDGE_GATE_GATE_2")

        cells = {}
        for chunk_z in range(3, 6):
            for chunk_x in range(5, 9):
                name = matrix["maps"][chunk_z][chunk_x]
                if name is None:
                    continue
                model = name.removeprefix("MAP_MODEL_").lower()
                terrain = ROOT / "res/field/maps/models" / model / "terrain_0.csv"
                if not terrain.exists():
                    continue
                with terrain.open(newline="") as stream:
                    for row in csv.DictReader(stream):
                        pos = (chunk_x * 32 + int(row["x"]), chunk_z * 32 + int(row["z"]))
                        cells[pos] = (int(row["tile_type"]), int(row["offset"]), int(row["shape"]))
        start_warp = route["warps"][1]["grid"]
        end_warp = moor["warps"][0]["grid"]
        start = (start_warp["x"] // 16, start_warp["z"] // 16)
        end = (end_warp["x"] // 16, end_warp["z"] // 16)
        queue = deque([start])
        visited = {start}
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
