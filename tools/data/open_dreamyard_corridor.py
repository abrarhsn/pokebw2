#!/usr/bin/env python3
"""Open a one-tile experimental Dreamyard approach in model trees and flat terrain.

The entrance warps stay enabled until the geometry and movement are verified in game. Only the
two named map models are edited. Tree vertices of triangles touching the corridor are moved below
ground; the original grass ground and all placed props are left intact.
"""

import csv
import io
import struct
from pathlib import Path

from map_model_data import accessor_values, read_glb, write_glb


ROOT = Path(__file__).resolve().parents[2]
MODELS = {
    "overworld_2_map25_18": (25, {(805, z) for z in range(580, 603)} | {(x, 602) for x in range(805, 832)}),
    "dreamyard_m_dun0101_00_00": (26, {(x, 602) for x in range(832, 841)}),
}


def intersects_tile(triangle, chunk_x, x, z):
    local_x = (x - chunk_x * 32 - 16) * 16 + 8
    local_z = -((z - 18 * 32 - 16) * 16 + 8)
    return (min(p[0] for p in triangle) < local_x + 8 and max(p[0] for p in triangle) > local_x - 8
            and min(p[2] for p in triangle) < local_z + 8 and max(p[2] for p in triangle) > local_z - 8)


def open_model(path, chunk_x, tiles):
    doc, data = read_glb(path)
    binary = bytearray(data)
    hidden = {}
    for primitive in doc["meshes"][0]["primitives"]:
        name = doc["materials"][primitive["material"]].get("name", "")
        if not (name.startswith("ki02") or name == "mori01s"):
            continue
        vertices = accessor_values(doc, binary, primitive["attributes"]["POSITION"])
        indices = [value[0] for value in accessor_values(doc, binary, primitive["indices"])]
        positions = primitive["attributes"]["POSITION"]
        selected = hidden.setdefault(positions, set())
        for i in range(0, len(indices), 3):
            triangle = [vertices[index] for index in indices[i:i + 3]]
            if any(intersects_tile(triangle, chunk_x, x, z) for x, z in tiles):
                selected.update(indices[i:i + 3])
    changed = 0
    for index, vertices in hidden.items():
        accessor = doc["accessors"][index]
        view = doc["bufferViews"][accessor["bufferView"]]
        if accessor["componentType"] != 5126 or accessor["type"] != "VEC3":
            raise ValueError(f"{path}: unexpected position accessor")
        offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        stride = view.get("byteStride", 12)
        for vertex in vertices:
            y_offset = offset + vertex * stride + 4
            if struct.unpack_from("<f", binary, y_offset)[0] != -64:
                struct.pack_into("<f", binary, y_offset, -64)
                changed += 1
    if changed:
        write_glb(path, doc, bytes(binary))
    return changed


def open_terrain(path, chunk_x, tiles):
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    changed = 0
    for row in rows:
        pos = (chunk_x * 32 + int(row["x"]), 18 * 32 + int(row["z"]))
        if pos not in tiles:
            continue
        if (row["shape"], row["slope"], row["offset"]) != ("0", "0", "3"):
            raise ValueError(f"{path}: corridor tile {pos} is not level ground")
        if row["tile_type"] == "8454145":
            row["tile_type"] = "8388608"
            changed += 1
        elif row["tile_type"] != "8388608":
            raise ValueError(f"{path}: unexpected terrain at {pos}: {row['tile_type']}")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=rows[0].keys(), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(output.getvalue())
    return changed


def main():
    for name, (chunk_x, tiles) in MODELS.items():
        directory = ROOT / "res/field/maps/models" / name
        hidden = open_model(directory / "model.glb", chunk_x, tiles)
        changed = open_terrain(directory / "terrain_0.csv", chunk_x, tiles)
        print(f"{name}: moved {hidden} tree vertices below ground, opened {changed} collision tiles")


if __name__ == "__main__":
    main()
