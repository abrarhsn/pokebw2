#!/usr/bin/env python3
"""Inspect model triangles over a world-grid corridor without changing collision or assets.

Usage: python3 tools/data/chunk_geometry_corridor.py MODEL CHUNK_X CHUNK_Z X Z [X Z ...]

The report lists horizontal ground under each tile center and triangle bounding boxes intersecting
the tile above walking height. Bounding-box intersections are conservative, not proof of collision.
"""

import argparse
from pathlib import Path

from map_model_data import accessor_values, read_glb


ROOT = Path(__file__).resolve().parents[2]


def contains_xz(triangle, x, z):
    """Whether the projected triangle contains a point, including its boundary."""
    def cross(a, b):
        return (b[0] - a[0]) * (z - a[2]) - (b[2] - a[2]) * (x - a[0])

    a, b, c = triangle
    signs = (cross(a, b), cross(b, c), cross(c, a))
    area = (b[0] - a[0]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[0] - a[0])
    return abs(area) > 1e-6 and (all(v >= -1e-6 for v in signs) or all(v <= 1e-6 for v in signs))


def inspect_tile(doc, binary, chunk_x, chunk_z, grid_x, grid_z):
    # GLB coordinates are centered in the chunk; the exporter reverses the world Z axis.
    x = (grid_x - chunk_x * 32 - 16) * 16 + 8
    z = -((grid_z - chunk_z * 32 - 16) * 16 + 8)
    ground = set()
    obstacles = set()
    for primitive in doc["meshes"][0]["primitives"]:
        vertices = accessor_values(doc, binary, primitive["attributes"]["POSITION"])
        indices = [value[0] for value in accessor_values(doc, binary, primitive["indices"])]
        name = doc["materials"][primitive["material"]].get("name", "")
        for i in range(0, len(indices), 3):
            tri = [vertices[index] for index in indices[i:i + 3]]
            ys = [p[1] for p in tri]
            if max(abs(y) for y in ys) <= 3 and contains_xz(tri, x, z):
                ground.add(name)
            if (max(ys) > 4 and min(p[0] for p in tri) < x + 8 and max(p[0] for p in tri) > x - 8
                    and min(p[2] for p in tri) < z + 8 and max(p[2] for p in tri) > z - 8):
                obstacles.add(name)
    return ground, obstacles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("chunk_x", type=int)
    parser.add_argument("chunk_z", type=int)
    parser.add_argument("coordinates", type=int, nargs="+")
    args = parser.parse_args()
    if len(args.coordinates) % 2:
        parser.error("coordinates must be X Z pairs")
    doc, binary = read_glb(ROOT / "res/field/maps/models" / args.model / "model.glb")
    for x, z in zip(args.coordinates[::2], args.coordinates[1::2]):
        ground, obstacles = inspect_tile(doc, binary, args.chunk_x, args.chunk_z, x, z)
        print(f"({x}, {z}): ground={','.join(sorted(ground)) or '-'} "
              f"possible_obstacles={','.join(sorted(obstacles)) or '-'}")


if __name__ == "__main__":
    main()
