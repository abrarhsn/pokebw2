#!/usr/bin/env python3
"""Check Dreamyard's mainland placement while its entrance still uses a warp."""

import csv
import json
import math
import struct
import sys
import unittest
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/data"))
from chunk_geometry_corridor import inspect_tile
from gen_constants import ordered_names
from map_model_data import (accessor_values, canonical_indices, decoded_positions, dictionary_offsets,
                            draw_calls, model_bytes, prop_section, read_glb, u32)
from map_terrain_data import terrain_ranges
from narc import read_narc


class DreamyardPlacementTest(unittest.TestCase):
    def test_corridor_avoids_placed_prop_bounds(self):
        sections = (
            ("overworld_2_map25_18", "striaton_city", 25,
             {(805, z) for z in range(580, 603)} | {(x, 602) for x in range(805, 832)}),
            ("dreamyard_m_dun0101_00_00", "dreamyard", 26, {(x, 602) for x in range(832, 841)}),
        )
        for model, area, chunk_x, tiles in sections:
            doc, _ = read_glb(ROOT / "res/field/maps/models" / model / "model.glb")
            props = [node for node in doc.get("nodes", []) if node.get("name", "").startswith("bw2_prop_")]
            for suffix in ("", "_summer", "_autumn", "_winter"):
                header = json.loads((ROOT / "res/field/areas" / (area + suffix + ".json")).read_text())
                bundle = header["prop_bundle"].removeprefix("FIELD_PROPS_EXTERIOR_").lower()
                directory = ROOT / "res/field/props/exterior/models" / bundle
                entries = {}
                for path in directory.glob("*/data.json"):
                    entry = json.loads(path.read_text())
                    entries[entry["res_id"]] = path.parent / "model.glb"
                for prop in props:
                    resource_id = int(prop["name"].rsplit("_", 1)[1])
                    self.assertIn(resource_id, entries, (area, suffix))
                    prop_doc, binary = read_glb(entries[resource_id])
                    positions = []
                    for mesh in prop_doc.get("meshes", []):
                        for primitive in mesh["primitives"]:
                            positions.extend(accessor_values(prop_doc, binary, primitive["attributes"]["POSITION"]))
                    qx, qy, qz, qw = prop.get("rotation", (0, 0, 0, 1))
                    self.assertAlmostEqual(qx, 0)
                    self.assertAlmostEqual(qz, 0)
                    angle = 2 * math.atan2(qy, qw)
                    cos, sin = math.cos(angle), math.sin(angle)
                    px, _, pz = prop.get("translation", (0, 0, 0))
                    xs = [px + x * cos + z * sin for x, _, z in positions]
                    zs = [pz - x * sin + z * cos for x, _, z in positions]
                    for x, z in tiles:
                        local_x = (x - chunk_x * 32 - 16) * 16 + 8
                        local_z = -((z - 18 * 32 - 16) * 16 + 8)
                        overlaps = (min(xs) < local_x + 8 and max(xs) > local_x - 8
                                    and min(zs) < local_z + 8 and max(zs) > local_z - 8)
                        self.assertFalse(overlaps, (model, suffix, prop["name"], x, z))

    def test_built_models_fit_and_keep_unchanged_shapes(self):
        names = ordered_names("map_models")
        models = ("MAP_MODEL_OVERWORLD_2_MAP25_18", "MAP_MODEL_DREAMYARD_M_DUN0101_00_00")

        def shape_streams(chunk):
            nitro = model_bytes(chunk)
            block = u32(nitro, 16)
            model = block + dictionary_offsets(nitro, block + 8)[0]
            shape_dict = model + u32(nitro, model + 12)
            shapes = [shape_dict + offset for offset in dictionary_offsets(nitro, shape_dict)]
            streams = []
            for index, _ in draw_calls(nitro, model):
                shape = shapes[index]
                start = shape + u32(nitro, shape + 8)
                streams.append(nitro[start:start + u32(nitro, shape + 12)])
            return streams

        for version in ("b2_us", "w2_us"):
            original_path = ROOT / "extract" / version / "files/a/0/0/8"
            built_path = ROOT / "build" / version / "files/a/0/0/8"
            if not original_path.exists() or not built_path.exists():
                self.skipTest("packed and original map archives are not available")
            original = read_narc(original_path.read_bytes())
            built = read_narc(built_path.read_bytes())
            for model in models:
                with self.subTest(version=version, model=model):
                    index = names.index(model)
                    self.assertLessEqual(len(built[index]), 0x1b008)
                    before, after = shape_streams(original[index]), shape_streams(built[index])
                    self.assertEqual(len(before), len(after))
                    unchanged = sum(a == b for a, b in zip(before, after))
                    self.assertGreaterEqual(unchanged, 1)
                    if model == "MAP_MODEL_DREAMYARD_M_DUN0101_00_00":
                        self.assertGreater(unchanged, len(before) // 2)
                    self.assertTrue(any(a != b for a, b in zip(before, after)))

    def test_packed_collision_and_prop_records(self):
        names = ordered_names("map_models")
        sections = (
            ("MAP_MODEL_OVERWORLD_2_MAP25_18", 25,
             {(805, z) for z in range(580, 603)} | {(x, 602) for x in range(805, 832)}),
            ("MAP_MODEL_DREAMYARD_M_DUN0101_00_00", 26, {(x, 602) for x in range(832, 841)}),
        )
        for version in ("b2_us", "w2_us"):
            original_path = ROOT / "extract" / version / "files/a/0/0/8"
            built_path = ROOT / "build" / version / "files/a/0/0/8"
            if not original_path.exists() or not built_path.exists():
                self.skipTest("packed and original map archives are not available")
            original, built = read_narc(original_path.read_bytes()), read_narc(built_path.read_bytes())
            for name, chunk_x, tiles in sections:
                index = names.index(name)
                chunk = built[index]
                start, _ = terrain_ranges(chunk)[0]
                width, height = struct.unpack_from("<HH", chunk, start)
                self.assertEqual((width, height), (32, 32))
                for x, z in tiles:
                    tile = (z - 18 * 32) * width + (x - chunk_x * 32)
                    shape_slope, offset, flags = struct.unpack_from("<HHI", chunk, start + 4 + tile * 8)
                    self.assertEqual((shape_slope, offset, flags), (0, 3, 8388608), (version, name, x, z))
                old_offset, _, _ = prop_section(original[index])
                new_offset, _, _ = prop_section(chunk)
                self.assertEqual(original[index][old_offset:], chunk[new_offset:], (version, name))

    def test_packed_model_triangles_match_source_geometry(self):
        names = ordered_names("map_models")
        for version in ("b2_us", "w2_us"):
            path = ROOT / "build" / version / "files/a/0/0/8"
            if not path.exists():
                self.skipTest("packed map archive is not available")
            archive = read_narc(path.read_bytes())
            for model in ("overworld_2_map25_18", "dreamyard_m_dun0101_00_00"):
                name = "MAP_MODEL_" + model.upper()
                nitro = model_bytes(archive[names.index(name)])
                block = u32(nitro, 16)
                model_offset = block + dictionary_offsets(nitro, block + 8)[0]
                shape_dict = model_offset + u32(nitro, model_offset + 12)
                shapes = [shape_dict + offset for offset in dictionary_offsets(nitro, shape_dict)]
                order = [shape for shape, _ in draw_calls(nitro, model_offset)]
                _, triangles = canonical_indices(nitro, shapes, order)
                positions = decoded_positions(nitro, shapes, order, u32(nitro, model_offset + 28) / 4096)
                doc, binary = read_glb(ROOT / "res/field/maps/models" / model / "model.glb")
                for primitive, packed_indices in zip(doc["meshes"][0]["primitives"], triangles):
                    source_indices = [i[0] for i in accessor_values(doc, binary, primitive["indices"])]
                    source_positions = accessor_values(doc, binary, primitive["attributes"]["POSITION"])
                    self.assertEqual(len(source_indices), len(packed_indices), (version, model))
                    for source, packed in zip(source_indices, packed_indices):
                        for actual, expected in zip(positions[packed], source_positions[source]):
                            self.assertAlmostEqual(actual, expected, delta=0.02, msg=f"{version} {model}")

    def test_experimental_corridor_has_ground_and_open_collision(self):
        sections = (
            ("overworld_2_map25_18", 25, {(805, z) for z in range(580, 603)}
             | {(x, 602) for x in range(805, 832)}),
            ("dreamyard_m_dun0101_00_00", 26, {(x, 602) for x in range(832, 841)}),
        )
        for name, chunk_x, tiles in sections:
            directory = ROOT / "res/field/maps/models" / name
            doc, binary = read_glb(directory / "model.glb")
            with (directory / "terrain_0.csv").open(newline="") as stream:
                rows = {(chunk_x * 32 + int(row["x"]), 18 * 32 + int(row["z"])): row
                        for row in csv.DictReader(stream)}
            for pos in sorted(tiles):
                with self.subTest(model=name, tile=pos):
                    row = rows[pos]
                    self.assertEqual((row["shape"], row["slope"], row["offset"], row["tile_type"]),
                                     ("0", "0", "3", "8388608"))
                    ground, obstacles = inspect_tile(doc, binary, chunk_x, 18, *pos)
                    self.assertIn("grass01ax", ground)
                    self.assertFalse(obstacles)

    def test_entrance_stays_warped_until_terrain_is_connected(self):
        matrix = json.loads((ROOT / "res/field/matrices/overworld.json").read_text())
        city = json.loads((ROOT / "res/field/events/striaton_city.json").read_text())
        yard = json.loads((ROOT / "res/field/events/dreamyard.json").read_text())
        cells = {}
        for chunk_z in range(17, 21):
            for chunk_x in range(24, 28):
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

        def passable(pos):
            tile = cells.get(pos)
            if tile is None:
                return False
            kind, height, shape = tile
            return (kind != 0xffffffff and kind & 0xffff != 0xffff and not (kind >> 16) & 1
                    and height == 3 and shape == 0)

        city_warp, yard_warp = city["warps"][6], yard["warps"][2]
        city_pos = (city_warp["grid"]["x"] // 16, city_warp["grid"]["z"] // 16)
        yard_pos = (yard_warp["grid"]["x"] // 16, yard_warp["grid"]["z"] // 16)
        # Start at any passable tile bordering the city warp, and look for a tile bordering the yard warp.
        def around(pos):
            x, z = pos
            return ((x, z), (x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1))

        visited = {pos for pos in around(city_pos) if passable(pos)}
        queue = deque(visited)
        while queue:
            for pos in around(queue.popleft()):
                if pos not in visited and passable(pos):
                    visited.add(pos)
                    queue.append(pos)
        if not visited.intersection(pos for pos in around(yard_pos) if passable(pos)):
            self.assertEqual(city_warp["zone"], "ZONE_DREAMYARD")
            self.assertEqual(yard_warp["zone"], "ZONE_STRIATON_CITY")

    def test_matrix_warps_and_script_positions(self):
        def load(path):
            return json.loads((ROOT / path).read_text())

        matrix = load("res/field/matrices/overworld.json")
        dreamyard = load("res/field/matrices/dreamyard.json")
        zone = load("res/field/zones/dreamyard.json")
        events = load("res/field/events/dreamyard.json")
        city = load("res/field/events/striaton_city.json")
        basement = load("res/field/events/dreamyard_2.json")
        self.assertEqual((zone["matrix"], zone["map_type"]), ("MAP_MATRIX_OVERWORLD", 0))
        self.assertEqual((zone["fly"]["x"], zone["fly"]["z"]), (837, 580))
        for z in range(2):
            for x in range(2):
                self.assertEqual(matrix["maps"][18 + z][26 + x], dreamyard["maps"][z][x])
                self.assertEqual(matrix["zones"][18 + z][26 + x], "ZONE_DREAMYARD")
        self.assertEqual((city["warps"][6]["zone"], city["warps"][6]["warp"]), ("ZONE_DREAMYARD", 2))
        self.assertEqual((events["warps"][2]["zone"], events["warps"][2]["warp"]), ("ZONE_STRIATON_CITY", 6))
        for index in (0, 1, 3):
            self.assertEqual(events["warps"][index]["zone"], "ZONE_DREAMYARD_2")
            self.assertEqual(basement["warps"][events["warps"][index]["warp"]]["zone"], "ZONE_DREAMYARD")
        self.assertEqual((events["triggers"][0]["grid"]["x"], events["triggers"][0]["grid"]["z"]), (842, 602))
        script = (ROOT / "res/field/scripts/dreamyard.s").read_text()
        self.assertIn("ActorSetGPos 7, 851, 0, 0x8023, 2", script)
        self.assertIn("ActorMoveLinear 7, 858, 2, 598, 48", script)
        self.assertIn("VMStackPush 0x8022\n    VMStackPushConst 858", script)
        self.assertIn("VMStackPush 0x8020\n    VMStackPushConst 23", script)


if __name__ == "__main__":
    unittest.main()
