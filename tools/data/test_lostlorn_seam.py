#!/usr/bin/env python3
"""Check the mainland placement and collision corridor to Lostlorn Forest."""

import csv
import json
import subprocess
import tempfile
import unittest
from collections import deque
from pathlib import Path

from tools.data.test_chunk_actor_residency import extract_function


ROOT = Path(__file__).resolve().parents[2]


class LostlornSeamTest(unittest.TestCase):
    def test_legacy_save_position_migration(self):
        source = (ROOT / "src/ov036/fieldmap.c").read_text()
        migration = extract_function(source, "Field_MigrateLegacyOutdoorPosition")
        harness = r'''
#include <assert.h>
#include <stdint.h>
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef struct { int32_t x, y, z; } VecFx32;
typedef struct { u16 zoneId; VecFx32 position; } PlayerState;
typedef struct { u16 zone; VecFx32 pos; int x, z, initX, initZ; } FieldActor;
typedef struct { FieldActor actors[2]; } MMSys;
typedef struct { MMSys actors; } GameData;
typedef struct { PlayerState state; GameData game; } GameSystem;
#define ZONE_LOSTLORN_FOREST 42
#define ZONE_CASTELIA_CITY_4 43
#define ZONE_MOOR_OF_ICIRRUS 44
#define ZONE_ABUNDANT_SHRINE 45
#define ZONE_DREAMYARD 46
#define ZONE_VIRBANK_COMPLEX_2 47
#define FX32_CONST(x) ((x) * 4096)
static PlayerState *GSYS_GetPlayerState(GameSystem *g) { return &g->state; }
static GameData *GSYS_GetGameData(GameSystem *g) { return &g->game; }
static MMSys *GameData_GetMMSys(GameData *g) { return &g->actors; }
static u16 PlayerState_GetZoneID(PlayerState *s) { return s->zoneId; }
static int NextActor(MMSys *s, FieldActor **a, u32 *index) {
    if (*index >= 2) return 0;
    *a = &s->actors[(*index)++];
    return 1;
}
static u16 GetActorZoneID(FieldActor *a) { return a->zone; }
static void CopyActorWPos(FieldActor *a, VecFx32 *p) { *p = a->pos; }
static int FldAct_GetInitGPosX(FieldActor *a) { return a->initX; }
static int FldAct_GetInitGPosZ(FieldActor *a) { return a->initZ; }
static int GetGPosX(FieldActor *a) { return a->x; }
static int GetGPosZ(FieldActor *a) { return a->z; }
static void SetActorInitialGPosX(FieldActor *a, int x) { a->initX = x; }
static void SetActorInitialGPosZ(FieldActor *a, int z) { a->initZ = z; }
static void SetActorGPosX(FieldActor *a, int x) { a->x = x; }
static void SetActorGPosZ(FieldActor *a, int z) { a->z = z; }
static void SetActorWPosValue(FieldActor *a, VecFx32 *p) { a->pos = *p; }
'''
        checks = r'''
int main(void) {
    GameSystem game = {0};
    FieldActor *actor = &game.game.actors.actors[0];
    FieldActor *other = &game.game.actors.actors[1];
    game.state.zoneId = ZONE_LOSTLORN_FOREST;
    game.state.position.x = FX32_CONST(5 * 16);
    game.state.position.z = FX32_CONST(4 * 16);
    actor->zone = ZONE_LOSTLORN_FOREST;
    actor->pos = game.state.position;
    actor->x = actor->initX = 5;
    actor->z = actor->initZ = 4;
    other->zone = 1;
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(game.state.position.x == FX32_CONST(485 * 16));
    assert(game.state.position.z == FX32_CONST(324 * 16));
    assert(actor->x == 485 && actor->z == 324);
    assert(actor->initX == 485 && actor->initZ == 324);
    assert(actor->pos.x == game.state.position.x && actor->pos.z == game.state.position.z);
    assert(other->pos.x == 0 && other->x == 0);
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(game.state.position.x == FX32_CONST(485 * 16));
    assert(actor->x == 485);
    game.state.zoneId = ZONE_CASTELIA_CITY_4;
    game.state.position.x = FX32_CONST(12 * 16);
    game.state.position.z = FX32_CONST(16 * 16);
    actor->zone = ZONE_CASTELIA_CITY_4;
    actor->pos = game.state.position;
    actor->x = actor->initX = 12;
    actor->z = actor->initZ = 16;
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(game.state.position.x == FX32_CONST(428 * 16));
    assert(game.state.position.z == FX32_CONST(624 * 16));
    assert(actor->x == 428 && actor->z == 624);
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(actor->x == 428 && actor->z == 624);
    game.state.zoneId = ZONE_MOOR_OF_ICIRRUS;
    game.state.position.x = FX32_CONST(50 * 16);
    game.state.position.z = FX32_CONST(49 * 16);
    actor->zone = ZONE_MOOR_OF_ICIRRUS;
    actor->pos = game.state.position;
    actor->x = actor->initX = 50;
    actor->z = actor->initZ = 49;
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(game.state.position.x == FX32_CONST(242 * 16));
    assert(game.state.position.z == FX32_CONST(145 * 16));
    assert(actor->x == 242 && actor->z == 145);
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(actor->x == 242 && actor->z == 145);
    game.state.zoneId = ZONE_ABUNDANT_SHRINE;
    game.state.position.x = FX32_CONST(50 * 16);
    game.state.position.z = FX32_CONST(54 * 16);
    actor->zone = ZONE_ABUNDANT_SHRINE;
    actor->pos = game.state.position;
    actor->x = actor->initX = 50;
    actor->z = actor->initZ = 54;
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(game.state.position.x == FX32_CONST(658 * 16));
    assert(game.state.position.z == FX32_CONST(374 * 16));
    assert(actor->x == 658 && actor->z == 374);
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(actor->x == 658 && actor->z == 374);
    game.state.zoneId = ZONE_DREAMYARD;
    game.state.position.x = FX32_CONST(50 * 16);
    game.state.position.z = FX32_CONST(54 * 16);
    actor->zone = ZONE_DREAMYARD;
    actor->pos = game.state.position;
    actor->x = actor->initX = 50;
    actor->z = actor->initZ = 54;
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(game.state.position.x == FX32_CONST(882 * 16));
    assert(game.state.position.z == FX32_CONST(630 * 16));
    assert(actor->x == 882 && actor->z == 630);
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(actor->x == 882 && actor->z == 630);
    game.state.zoneId = ZONE_VIRBANK_COMPLEX_2;
    game.state.position.x = FX32_CONST(16 * 16);
    game.state.position.z = FX32_CONST(47 * 16);
    actor->zone = ZONE_VIRBANK_COMPLEX_2;
    actor->pos = game.state.position;
    actor->x = actor->initX = 16;
    actor->z = actor->initZ = 47;
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(game.state.position.x == FX32_CONST(208 * 16));
    assert(game.state.position.z == FX32_CONST(751 * 16));
    assert(actor->x == 208 && actor->z == 751);
    Field_MigrateLegacyOutdoorPosition(&game);
    assert(actor->x == 208 && actor->z == 751);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.c"
            binary = Path(directory) / "migration"
            path.write_text(harness + migration + checks)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", str(path), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_matrix_event_coordinates_and_walkable_corridor(self):
        matrix = json.loads((ROOT / "res/field/matrices/overworld.json").read_text())
        zone = json.loads((ROOT / "res/field/zones/lostlorn_forest.json").read_text())
        route = json.loads((ROOT / "res/field/events/route_16.json").read_text())
        forest = json.loads((ROOT / "res/field/events/lostlorn_forest.json").read_text())
        self.assertEqual(zone["matrix"], "MAP_MATRIX_OVERWORLD")
        self.assertEqual(zone["map_type"], 0)
        self.assertEqual(matrix["maps"][10][15], "MAP_MODEL_LOSTLORN_FOREST_M_DUN2102_00_00")
        self.assertEqual(matrix["maps"][11][15], "MAP_MODEL_LOSTLORN_FOREST_M_DUN2102_00_01")
        self.assertEqual(matrix["maps"][12][15], "MAP_MODEL_LOSTLORN_APPROACH")
        self.assertEqual(matrix["zones"][11][15], "ZONE_LOSTLORN_FOREST")
        self.assertEqual(matrix["zones"][12][15], "ZONE_ROUTE_16")
        self.assertEqual(route["warps"][2]["zone"], 65535)
        self.assertEqual(forest["warps"][0]["zone"], 65535)
        self.assertEqual(zone["fly"]["x"], 485)
        self.assertEqual(zone["fly"]["z"], 324)

        cells = {}
        for chunk_z in (10, 11, 12, 13):
            model = matrix["maps"][chunk_z][15].removeprefix("MAP_MODEL_").lower()
            terrain = ROOT / "res/field/maps/models" / model / "terrain_0.csv"
            with terrain.open(newline="") as stream:
                for row in csv.DictReader(stream):
                    pos = (15 * 32 + int(row["x"]), chunk_z * 32 + int(row["z"]))
                    cells[pos] = (int(row["tile_type"]), int(row["offset"]), int(row["shape"]))

        # Both original warp positions become points on the same flat, passable route.
        start = (route["warps"][2]["grid"]["x"] // 16, route["warps"][2]["grid"]["z"] // 16)
        finish = (forest["warps"][0]["grid"]["x"] // 16, forest["warps"][0]["grid"]["z"] // 16)
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
        self.assertIn(finish, visited)


if __name__ == "__main__":
    unittest.main()
