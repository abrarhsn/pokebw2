#!/usr/bin/env python3
"""Check the Route 4 connection to the northern Castelia street."""

import csv
import json
import unittest
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CasteliaSeamTest(unittest.TestCase):
    def test_matrix_events_and_flat_corridor(self):
        def load(path):
            return json.loads((ROOT / path).read_text())

        matrix = load("res/field/matrices/overworld.json")
        zone = load("res/field/zones/castelia_city_4.json")
        route = load("res/field/events/route_4.json")
        route_alternate = load("res/field/events/route_4_16.json")
        street = load("res/field/events/castelia_city_4.json")
        rush = load("res/field/castelia_rush/castelia_rush.json")
        self.assertEqual(zone["matrix"], "MAP_MATRIX_OVERWORLD")
        self.assertEqual(zone["map_type"], 0)
        self.assertEqual(matrix["maps"][19][13], "MAP_MODEL_CASTELIA_CITY_4_C03_C00_00")
        self.assertEqual(matrix["maps"][20][13], "MAP_MODEL_CASTELIA_CITY_4_C03_C00_01")
        self.assertEqual(matrix["zones"][19][13], "ZONE_CASTELIA_CITY_4")
        self.assertEqual(matrix["zones"][20][13], "ZONE_CASTELIA_CITY_4")
        self.assertEqual(route["warps"][5]["zone"], 65535)
        self.assertEqual(route_alternate["warps"][5]["zone"], 65535)
        self.assertEqual(street["warps"][0]["zone"], 65535)
        self.assertEqual(street["warps"][4]["zone"], "ZONE_CASTELIA_CITY_2")
        self.assertEqual((street["npcs"][0]["grid"]["x"], street["npcs"][0]["grid"]["z"]), (434, 664))
        street_crowd = next(crowd for crowd in rush["crowds"] if crowd["zone"] == "ZONE_CASTELIA_CITY_4")
        self.assertEqual((street_crowd["lanes"][0]["x_min"], street_crowd["lanes"][0]["z_min"]), (432, 624))
        self.assertEqual((street_crowd["lanes"][1]["x_min"], street_crowd["lanes"][1]["z_min"]), (429, 671))

        cells = {}
        for chunk_z in (17, 18, 19, 20):
            model = matrix["maps"][chunk_z][13].removeprefix("MAP_MODEL_").lower()
            terrain = ROOT / "res/field/maps/models" / model / "terrain_0.csv"
            with terrain.open(newline="") as stream:
                for row in csv.DictReader(stream):
                    pos = (13 * 32 + int(row["x"]), chunk_z * 32 + int(row["z"]))
                    cells[pos] = (int(row["tile_type"]), int(row["offset"]), int(row["shape"]))
        start_warp = route["warps"][5]["grid"]
        end_warp = street["warps"][0]["grid"]
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
