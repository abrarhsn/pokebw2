#!/usr/bin/env python3
"""Test corridor inspection against simple ground and raised geometry."""

import struct
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from chunk_geometry_corridor import contains_xz, inspect_tile


class ChunkGeometryCorridorTest(unittest.TestCase):
    def test_projected_triangle_contains_point(self):
        triangle = ((0, 0, 0), (16, 0, 0), (0, 0, 16))
        self.assertTrue(contains_xz(triangle, 4, 4))
        self.assertTrue(contains_xz(triangle, 8, 8))
        self.assertFalse(contains_xz(triangle, 12, 12))
        self.assertFalse(contains_xz((triangle[0], triangle[0], triangle[1]), 0, 0))

    def test_detects_ground_and_conservative_obstacle(self):
        vertices = [(-256, 0, 256), (-240, 0, 256), (-256, 0, 240),
                    (-252, 0, 252), (-252, 20, 252), (-244, 20, 244)]
        binary = b"".join(struct.pack("<3f", *p) for p in vertices)
        binary += struct.pack("<3H", 0, 1, 2) + struct.pack("<3H", 3, 4, 5)
        doc = {
            "buffers": [{"byteLength": len(binary)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0},
                            {"buffer": 0, "byteOffset": 72},
                            {"buffer": 0, "byteOffset": 78}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "type": "VEC3", "count": 6},
                          {"bufferView": 1, "componentType": 5123, "type": "SCALAR", "count": 3},
                          {"bufferView": 2, "componentType": 5123, "type": "SCALAR", "count": 3}],
            "materials": [{"name": "ground"}, {"name": "tree"}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0},
                                       {"attributes": {"POSITION": 0}, "indices": 2, "material": 1}]}],
        }
        ground, obstacles = inspect_tile(doc, binary, 0, 0, 0, 0)
        self.assertEqual(ground, {"ground"})
        self.assertEqual(obstacles, {"tree"})


if __name__ == "__main__":
    unittest.main()
