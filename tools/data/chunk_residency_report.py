#!/usr/bin/env python3
"""Report how many area resource sets overlap in a field matrix's chunk windows.

This is a static upper-bound survey, not a measurement of runtime memory or VRAM.
Cells without a zone cannot be assigned an area from the matrix alone.
"""

import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path, help="matrix JSON to inspect")
    parser.add_argument("--zones", type=Path, default=ROOT / "res/field/zones")
    parser.add_argument("--window", type=int, default=2, help="square window width, in chunks")
    args = parser.parse_args()
    if args.window < 1:
        parser.error("--window must be positive")

    matrix = load_json(args.matrix)
    maps, zones = matrix["maps"], matrix["zones"]
    height = len(maps)
    width = len(maps[0]) if maps else 0
    if not width or len(zones) != height or any(len(row) != width for row in maps + zones):
        parser.error("maps and zones must be nonempty, equally sized rectangular grids")

    area_by_zone = {}
    for row in zones:
        for zone in row:
            if zone is not None and zone not in area_by_zone:
                path = args.zones / (zone.removeprefix("ZONE_").lower() + ".json")
                if not path.is_file():
                    parser.error(f"zone data not found for {zone}: {path}")
                area_by_zone[zone] = load_json(path)["area"]

    counts = Counter()
    unknown_windows = 0
    max_areas = 0
    examples = []
    for z in range(height):
        for x in range(width):
            areas = set()
            unknown = False
            for dz in range(args.window):
                for dx in range(args.window):
                    xx, zz = x + dx, z + dz
                    if xx >= width or zz >= height or maps[zz][xx] is None:
                        continue
                    zone = zones[zz][xx]
                    if zone is None:
                        unknown = True
                    else:
                        areas.add(area_by_zone[zone])
            if not areas and not unknown:
                continue
            counts[len(areas)] += 1
            unknown_windows += unknown
            if len(areas) > max_areas:
                max_areas = len(areas)
                examples = [(x, z, sorted(areas))]
            elif len(areas) == max_areas:
                examples.append((x, z, sorted(areas)))

    print(f"Matrix: {args.matrix} ({width} x {height}); window: {args.window} x {args.window}")
    print(f"Populated cells: {sum(cell is not None for row in maps for cell in row)}")
    print(f"Referenced zones: {len(area_by_zone)}; referenced areas: {len(set(area_by_zone.values()))}")
    for count, windows in sorted(counts.items()):
        print(f"Windows with {count} known areas: {windows}")
    print(f"Windows containing populated cells without a zone: {unknown_windows}")
    for x, z, areas in examples[:5]:
        print(f"Maximum known-area window at ({x}, {z}): {', '.join(areas)}")


if __name__ == "__main__":
    main()
