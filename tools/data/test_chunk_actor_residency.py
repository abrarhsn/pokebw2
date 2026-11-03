#!/usr/bin/env python3
"""Exercise the actual field residency helpers against a bounded fake actor pool."""

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def extract_function(source, name, signature="static void "):
    start = source.index(f"{signature}{name}(")
    brace = source.index("{", start)
    while ";" in source[start:brace]:
        start = source.index(f"{signature}{name}(", start + 1)
        brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


class ActorResidencyTest(unittest.TestCase):
    def test_script_add_reuses_zone_actor_and_checks_capacity(self):
        source = (ROOT / "src/ov036/scrcmd_field_actor.c").read_text()
        function = extract_function(source, "FieldScript_AddZoneActor", "static FieldActor *")
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef uint16_t u16;
typedef uint32_t u32;
typedef struct { int active; u16 uid, zone; } FieldActor;
typedef struct { FieldActor actors[4]; u16 limit; } MMSys;
typedef struct { u16 uid, scrId, spawnFlag; } ZoneNPC;
typedef struct { ZoneNPC npcs[2]; u32 count; } EventData;
typedef struct { int flags[4]; } EventWork;
static int spawns;
static int NextActor(MMSys *sys, FieldActor **out, u32 *i) {
    while (*i < sys->limit) { *out = &sys->actors[(*i)++]; if ((*out)->active) return 1; }
    return 0;
}
static u16 GetActorUID(FieldActor *a) { return a->uid; }
static u16 GetActorZoneID(FieldActor *a) { return a->zone; }
static u16 GetActorLimit(MMSys *s) { return s->limit; }
static ZoneNPC *GetZoneNPCs(EventData *e) { return e->npcs; }
static u32 GetZoneNPCsCount(EventData *e) { return e->count; }
static int EventWork_FlagGet(EventWork *work, u16 flag) { return work->flags[flag]; }
static FieldActor *SpawnZoneNPCByUID(MMSys *s, ZoneNPC *npc, u16 zone, u32 count, EventWork *w, u16 uid) {
    u32 i; (void)w; assert(count == 1 && npc->uid == uid); spawns++;
    for (i = 0; i < s->limit; i++) if (!s->actors[i].active) {
        s->actors[i] = (FieldActor){1, uid, zone}; return &s->actors[i];
    }
    assert(0); return NULL;
}
'''
        checks = r'''
int main(void) {
    MMSys system = {{{1, 4, 1}, {1, 4, 2}, {0}, {0}}, 3};
    EventData events = {{{4, 1, 0}, {5, 1, 1}}, 2};
    EventWork work = {{0}};
    assert(FieldScript_AddZoneActor(&system, &events, &work, 2, 4) == &system.actors[1]);
    assert(spawns == 0);
    assert(FieldScript_AddZoneActor(&system, &events, &work, 2, 99) == NULL);
    work.flags[1] = 1;
    assert(FieldScript_AddZoneActor(&system, &events, &work, 2, 5) == NULL);
    work.flags[1] = 0; events.npcs[1].scrId = 0xffff;
    assert(FieldScript_AddZoneActor(&system, &events, &work, 2, 5) == NULL);
    events.npcs[1].scrId = 1;
    assert(FieldScript_AddZoneActor(&system, &events, &work, 2, 5) == &system.actors[2]);
    assert(spawns == 1);
    assert(FieldScript_AddZoneActor(&system, &events, &work, 1, 5) == NULL);
    assert(FieldScript_AddZoneActor(&system, NULL, &work, 2, 99) == NULL);
    assert(spawns == 1);
    return 0;
}
'''
        self.run_harness(harness + function + checks)

    def test_neighbor_events_follow_target_cell(self):
        source = (ROOT / "src/ov036/fieldmap.c").read_text()
        functions = "\n".join(extract_function(source, name, "EventData *") for name in (
            "Field_GetResidentZoneEvents", "Field_GetNeighborEventsAtPosition"))
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef uint16_t u16;
typedef struct { int x, z; } VecFx32;
typedef struct { u16 zoneId; } EventData;
typedef struct { u16 zone; } MapMatrix;
typedef struct { int retainRecentChunk; MapMatrix *matrix; } FieldG3DMapper;
typedef struct { EventData active; } GameData;
typedef struct {
    GameData *gameData;
    EventData *prefetchedEvents;
    int prefetchedEventsValid;
    u16 prefetchedZone;
    FieldG3DMapper *g3DMapper;
    struct { u16 zoneId; } playerZoneState;
} Field;
#define MATRIX_ZONE_NONE 65535
static EventData *GameData_GetEventData(GameData *g) { return &g->active; }
static int RangeCheckChunkCoordinateWorld(MapMatrix *m, int x, int z) {
    (void)m; return x >= 0 && z >= 0;
}
static u16 GetZoneIDAtMatrixXZWorld(MapMatrix *m, int x, int z) {
    (void)x; (void)z; return m->zone;
}
'''
        checks = r'''
int main(void) {
    GameData game = {{1}};
    EventData neighbor = {2};
    MapMatrix matrix = {2};
    FieldG3DMapper mapper = {1, &matrix};
    Field field = {&game, &neighbor, 1, 2, &mapper, {1}};
    VecFx32 pos = {1, 1};
    assert(Field_GetNeighborEventsAtPosition(&field, &pos) == &neighbor);
    matrix.zone = 1;
    assert(Field_GetNeighborEventsAtPosition(&field, &pos) == NULL);
    matrix.zone = 3;
    assert(Field_GetNeighborEventsAtPosition(&field, &pos) == NULL);
    matrix.zone = MATRIX_ZONE_NONE;
    assert(Field_GetNeighborEventsAtPosition(&field, &pos) == NULL);
    matrix.zone = 2; pos.x = -1;
    assert(Field_GetNeighborEventsAtPosition(&field, &pos) == NULL);
    pos.x = 1; mapper.retainRecentChunk = 0;
    assert(Field_GetNeighborEventsAtPosition(&field, &pos) == NULL);
    return 0;
}
'''
        self.run_harness(harness + functions + checks)

    def test_event_buffers_swap_and_rebind(self):
        source = (ROOT / "src/ov036/fieldmap.c").read_text()
        functions = "\n".join(extract_function(source, name) for name in (
            "Field_CopyPrefetchedEvents", "Field_ExchangeResidentEvents"))
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef struct { u32 value; } ZoneBGEntity;
typedef struct { u32 value; } ZoneNPC;
typedef struct { u32 value; } ZoneWarp;
typedef struct { u32 value; } ZoneTrigger;
typedef struct {
    u16 zoneId, entityCount, npcCount, warpCount, triggerCount;
    u16 prevEntityCount, prevNpcCount, prevWarpCount, prevTriggerCount;
    ZoneBGEntity *entities;
    ZoneNPC *npcs;
    ZoneWarp *warps;
    ZoneTrigger *triggers;
    void *initScript;
    u32 initScriptOffset;
    u8 cache[64], rest[16];
} EventData;
typedef struct { int heapId; EventData *prefetchedEvents; u16 prefetchedZone; } Field;
#define TRUE 1
static void MI_CpuCopy8(const void *a, void *b, size_t n) { memcpy(b, a, n); }
static void *GFL_HeapAllocate(int heap, size_t n, int clear, const char *file, int line) {
    (void)heap; (void)clear; (void)file; (void)line;
    return calloc(1, n);
}
static void GFL_HeapFree(void *p) { free(p); }
static void EventData_Reset(EventData *data) { memset(data->cache, 0, sizeof(data->cache)); }
'''
        checks = r'''
int main(void) {
    EventData active = {0}, neighbor = {0};
    Field field = {0, &neighbor, 2};
    active.zoneId = 1; active.initScriptOffset = 20;
    active.cache[0] = 1; active.cache[1] = 1; active.cache[4] = 17; active.rest[0] = 31;
    neighbor.zoneId = 2; neighbor.initScriptOffset = 24;
    neighbor.cache[2] = 1; neighbor.cache[4] = 42; neighbor.rest[0] = 64;
    Field_ExchangeResidentEvents(&field, &active);
    assert(active.zoneId == 2 && active.warpCount == 1 && active.cache[4] == 42 && active.rest[0] == 64);
    assert(neighbor.zoneId == 1 && field.prefetchedZone == 1 && neighbor.cache[4] == 17 && neighbor.rest[0] == 31);
    assert(active.warps == (ZoneWarp *)(active.cache + 4));
    assert(neighbor.entities == (ZoneBGEntity *)(neighbor.cache + 4));
    assert(neighbor.npcs == (ZoneNPC *)(neighbor.cache + 8));
    assert(neighbor.initScript == neighbor.cache + 20);
    Field_ExchangeResidentEvents(&field, &active);
    assert(active.zoneId == 1 && neighbor.zoneId == 2 && field.prefetchedZone == 2);
    return 0;
}
'''
        self.run_harness(harness + functions + checks)

    def test_zone_scoped_actor_lookup(self):
        actors = (ROOT / "src/ov012/field_actor.c").read_text()
        scripts = (ROOT / "src/ov012/scrcmd_work.c").read_text()
        functions = "\n".join((
            extract_function(actors, "FindFieldActorInZone", "FieldActor *"),
            extract_function(scripts, "FieldScriptEnv_FindActor", "FieldActor *"),
        ))
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define ACTOR_UID_FIRST_RESERVED 0xf1
typedef struct { u16 uid, zone; int hidden; } FieldActor;
typedef struct { FieldActor actors[3]; } MMSys;
typedef struct { u16 zoneId; } Args;
typedef struct { MMSys *system; Args args; } FieldScriptEnv;
static BOOL NextActor(MMSys *s, FieldActor **a, u32 *index) {
    if (*index >= 3) return FALSE;
    *a = &s->actors[(*index)++];
    return TRUE;
}
static int checkBit11Set(FieldActor *a) { return a->hidden; }
static u16 GetActorUID(FieldActor *a) { return a->uid; }
static u16 GetActorZoneID(FieldActor *a) { return a->zone; }
static MMSys *GetScrEnvActorSys(FieldScriptEnv *e) { return e->system; }
static FieldActor *FindFieldActor(MMSys *s, u16 id) {
    u32 i;
    for (i = 0; i < 3; i++) if (s->actors[i].uid == id) return &s->actors[i];
    return NULL;
}
'''
        checks = r'''
int main(void) {
    MMSys system = {{{0, 1, 0}, {0, 2, 0}, {255, 1, 0}}};
    FieldScriptEnv env = {&system, {2}};
    assert(FieldScriptEnv_FindActor(&env, 0) == &system.actors[1]);
    env.args.zoneId = 1;
    assert(FieldScriptEnv_FindActor(&env, 0) == &system.actors[0]);
    assert(FieldScriptEnv_FindActor(&env, 255) == &system.actors[2]);
    env.args.zoneId = 3;
    assert(FieldScriptEnv_FindActor(&env, 0) == NULL);
    system.actors[1].hidden = 1;
    env.args.zoneId = 2;
    assert(FieldScriptEnv_FindActor(&env, 0) == NULL);
    return 0;
}
'''
        self.run_harness(harness + functions + checks)

    def run_harness(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "residency.c"
            binary = Path(directory) / "residency"
            path.write_text(source)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", str(path), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_preload_retain_evict_and_capacity(self):
        source = (ROOT / "src/ov036/fieldmap.c").read_text()
        helpers = "\n".join((extract_function(source, "Field_RemoveZoneActors"),
                             extract_function(source, "Field_HasZoneActor", "static BOOL "),
                             extract_function(source, "Field_PrefetchNeighborActors")))
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define ACTOR_UID_PLAYER 255
typedef struct { int active; u16 uid, zone; u32 flags; } FieldActor;
typedef struct { FieldActor actors[64]; u16 limit; } MMSys;
typedef struct { u16 uid; } ZoneNPC;
typedef struct { u32 count; ZoneNPC npcs[2]; } EventData;
typedef struct { int unused; } GameData;
typedef GameData EventWork;
typedef struct { u16 zoneId; } ZoneSpawnInfo;
typedef struct {
    MMSys *actorSystem;
    EventData *prefetchedEvents;
    GameData *gameData;
    ZoneSpawnInfo playerZoneState;
    u16 residentNeighborZone;
    BOOL residentNeighborValid;
} Field;
static BOOL NextActor(MMSys *s, FieldActor **a, u32 *index) {
    while (*index < s->limit) {
        *a = &s->actors[(*index)++];
        if ((*a)->active) return TRUE;
    }
    return FALSE;
}
static u16 GetActorUID(FieldActor *a) { return a->uid; }
static u16 GetActorZoneID(FieldActor *a) { return a->zone; }
static BOOL CheckActorFlag(FieldActor *a, u32 flag) { return (a->flags & flag) != 0; }
static void DeleteActor(FieldActor *a) { a->active = FALSE; }
static u32 GetZoneNPCsCount(EventData *e) { return e->count; }
static ZoneNPC *GetZoneNPCs(EventData *e) { return e->npcs; }
static EventWork *GameData_GetEventWork(GameData *g) { return g; }
static u16 GetActorLimit(MMSys *s) { return s->limit; }
static void SpawnAllZoneNPCs(MMSys *s, ZoneNPC *npcs, u16 zone, u32 count, EventWork *work) {
    u32 i, j;
    (void)work;
    for (i = 0; i < count; i++) {
        for (j = 0; j < s->limit && s->actors[j].active; j++) {}
        assert(j < s->limit);
        s->actors[j] = (FieldActor){TRUE, npcs[i].uid, zone, 0};
    }
}
'''
        checks = r'''
static u32 count_zone(MMSys *s, u16 zone) {
    u32 i, n = 0;
    for (i = 0; i < s->limit; i++)
        if (s->actors[i].active && s->actors[i].zone == zone) n++;
    return n;
}
int main(void) {
    MMSys system = {0};
    EventData events = {2, {{0}, {1}}};
    GameData game = {0};
    Field field = {0};
    system.limit = 64;
    system.actors[0] = (FieldActor){TRUE, ACTOR_UID_PLAYER, 1, 0};
    system.actors[1] = (FieldActor){TRUE, 0, 1, 0};
    system.actors[2] = (FieldActor){TRUE, 1, 1, 0x20};
    field.actorSystem = &system;
    field.prefetchedEvents = &events;
    field.gameData = &game;
    field.playerZoneState.zoneId = 1;
    Field_PrefetchNeighborActors(&field, 2);
    assert(field.residentNeighborValid && field.residentNeighborZone == 2);
    assert(count_zone(&system, 2) == 2);
    Field_PrefetchNeighborActors(&field, 2);
    assert(count_zone(&system, 2) == 2);
    /* Crossing preserves both zones and makes the old zone the neighbor. */
    field.residentNeighborZone = 1;
    field.playerZoneState.zoneId = 2;
    Field_PrefetchNeighborActors(&field, 1);
    assert(count_zone(&system, 1) == 3 && count_zone(&system, 2) == 2);
    /* Replacing the neighbor retires only ordinary old-zone actors. */
    Field_PrefetchNeighborActors(&field, 3);
    assert(count_zone(&system, 1) == 2 && count_zone(&system, 3) == 2);
    assert(system.actors[0].active && system.actors[2].active);
    /* Re-entering a zone does not duplicate its surviving persistent NPC. */
    Field_PrefetchNeighborActors(&field, 1);
    assert(field.residentNeighborValid && field.residentNeighborZone == 1);
    assert(count_zone(&system, 1) == 3 && count_zone(&system, 3) == 0);
    assert(system.actors[2].active && system.actors[2].uid == 1);
    /* An undersized pool never calls the unchecked actor constructor. */
    memset(&system, 0, sizeof(system));
    system.limit = 2;
    system.actors[0] = (FieldActor){TRUE, ACTOR_UID_PLAYER, 2, 0};
    field.residentNeighborValid = FALSE;
    Field_PrefetchNeighborActors(&field, 3);
    assert(!field.residentNeighborValid && count_zone(&system, 3) == 0);
    /* Count only missing NPCs when persistent actors already occupy slots. */
    system.limit = 3;
    system.actors[1] = (FieldActor){TRUE, 1, 3, 0x20};
    Field_PrefetchNeighborActors(&field, 3);
    assert(field.residentNeighborValid && count_zone(&system, 3) == 2);
    assert(system.actors[1].active && system.actors[1].uid == 1);
    return 0;
}
'''
        self.run_harness(harness + helpers + checks)


if __name__ == "__main__":
    unittest.main()
