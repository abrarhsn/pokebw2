#!/usr/bin/env python3
"""Exercise the grid warp boundary path using the field's actual C functions."""

import unittest
from pathlib import Path

from tools.data import test_chunk_actor_residency as residency


ROOT = Path(__file__).resolve().parents[2]


class EventBoundaryTest(unittest.TestCase):
    def test_quicksand_neighbor_script_and_activation(self):
        source = (ROOT / "src/ov036/fieldmap_event.c").read_text()
        function = residency.extract_function(source, "CheckQuicksandEvent", "static GameEvent *")
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef uint16_t u16;
typedef uint32_t u32;
typedef struct { int x, y, z; } VecFx32;
typedef struct { int x, z, width, height; } ZoneTriggerGridPosition;
typedef struct { int isRail, scrId; struct { ZoneTriggerGridPosition grid; } pos; } ZoneTrigger;
typedef struct { u16 zoneId; ZoneTrigger *trigger; } EventData;
typedef struct { VecFx32 pos; int state, acmd; } FieldPlayer;
typedef struct { EventData *neighbor; FieldPlayer player; int quicksand; } Field;
typedef struct { int unused; } EventWork;
typedef struct { int zone, script; } GameEvent;
typedef struct { Field *gsys; void *gameData; EventData *eventData; int heapId; } FieldInteractWk;
#define TRUE 1
#define PLAYER_DIR_NONE 4
#define FX32_SHIFT 12
#define GRID_UNITS 16U
#define FLD_PLAYER_EXSTATE_NONE 0
#define ACMD_DASH 10
#define ACMD_DASH_UPHILL 20
#define DIR_UP 0
#define DIR_DOWN 1
#define DIR_LEFT 2
#define DIR_RIGHT 3
static GameEvent result;
static EventWork work;
static Field *GSYS_GetField(Field *f) { return f; }
static FieldPlayer *Field_GetPlayer(Field *f) { return &f->player; }
static void FieldPlayer_GetWPos(FieldPlayer *p, VecFx32 *pos) { *pos = p->pos; }
static Field *Field_GetG3DMapper(Field *f) { return f; }
static int GetTileTypeAtPos(Field *f, VecFx32 *p) { (void)p; return f->quicksand; }
static int GetTileClass(int type) { return type; }
static int MapTile_IsQuicksand(int type) { return type; }
static EventWork *GameData_GetEventWork(void *g) { (void)g; return &work; }
static ZoneTrigger *FindQuicksandTrigger(EventData *e, EventWork *w, VecFx32 *p, int dir) {
    (void)w; (void)p; (void)dir; return e->trigger;
}
static EventData *Field_GetNeighborEventsAtPosition(Field *f, VecFx32 *p) { (void)p; return f->neighbor; }
static int FieldPlayer_GetExState(FieldPlayer *p) { return p->state; }
static FieldPlayer *FieldPlayer_GetActor(FieldPlayer *p) { return p; }
static int FldAct_GetAcmd(FieldPlayer *p) { return p->acmd; }
static GameEvent *EventScriptCall_Create(Field *f, int script, void *actor, int heap) {
    (void)f; (void)actor; (void)heap; result.zone = 1; result.script = script; return &result;
}
static GameEvent *FieldEventScriptCall_CreateForZone(Field *f, int script, void *actor, int zone) {
    (void)f; (void)actor; result.zone = zone; result.script = script; return &result;
}
'''
        checks = r'''
int main(void) {
    ZoneTrigger trigger = {0, 7, {{5, 6, 2, 2}}};
    EventData active = {1, NULL}, neighbor = {2, &trigger};
    Field field = {&neighbor, {{6 * 16 * 4096, 0, 7 * 16 * 4096}, 0, 0}, 1};
    FieldInteractWk wk = {&field, NULL, &active, 0};
    GameEvent *event = CheckQuicksandEvent(&wk);
    assert(event && event->zone == 2 && event->script == 7);
    field.player.pos.x = 5 * 16 * 4096;
    assert(CheckQuicksandEvent(&wk) == NULL);
    field.player.acmd = ACMD_DASH + DIR_LEFT;
    event = CheckQuicksandEvent(&wk);
    assert(event && event->zone == 2);
    active.trigger = &trigger;
    event = CheckQuicksandEvent(&wk);
    assert(event && event->zone == 1);
    active.trigger = NULL; trigger.isRail = 1;
    assert(CheckQuicksandEvent(&wk) == NULL);
    trigger.isRail = 0; field.quicksand = 0;
    assert(CheckQuicksandEvent(&wk) == NULL);
    return 0;
}
'''
        residency.ActorResidencyTest().run_harness(harness + function + checks)

    def test_trigger_uses_owning_zone(self):
        source = (ROOT / "src/ov036/fieldmap_event.c").read_text()
        function = residency.extract_function(source, "CheckTriggerScrEvent", "static GameEvent *")
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef uint16_t u16;
typedef struct { int x, y, z; } VecFx32;
typedef struct { u16 zoneId, script; } EventData;
typedef struct { EventData *neighbor; } Field;
typedef struct { int unused; } EventWork;
typedef struct { int zone, script; } GameEvent;
typedef struct { Field *gsys; void *gameData, *player; EventData *eventData; int heapId; } FieldInteractWk;
#define SCRID_NONE 65535
#define TRUE 1
static GameEvent result;
static EventWork eventWork;
static Field *GSYS_GetField(Field *field) { return field; }
static EventWork *GameData_GetEventWork(void *game) { (void)game; return &eventWork; }
static void FieldPlayer_GetWPos(void *player, VecFx32 *pos) { (void)player; *pos = (VecFx32){0}; }
static void *Field_GetG3DMapper(Field *field) { return field; }
static int GetTileTypeAtPos(void *mapper, VecFx32 *pos) { (void)mapper; (void)pos; return 0; }
static int GetTileClass(int tile) { return tile; }
static int MapTile_IsQuicksand(int tile) { (void)tile; return 0; }
static u16 GetTriggerSCRIDAtPosGrid(EventData *data, EventWork *work, VecFx32 *pos, u16 dir) {
    (void)work; (void)pos; (void)dir; return data->script;
}
static EventData *Field_GetNeighborEventsAtPosition(Field *field, VecFx32 *pos) {
    (void)pos; return field->neighbor;
}
static GameEvent *EventScriptCall_Create(Field *gsys, u16 script, void *actor, int heap) {
    (void)gsys; (void)actor; (void)heap; result.zone = 1; result.script = script; return &result;
}
static GameEvent *FieldEventScriptCall_CreateForZone(Field *gsys, u16 script, void *actor, u16 zone) {
    (void)gsys; (void)actor; result.zone = zone; result.script = script; return &result;
}
'''
        checks = r'''
int main(void) {
    EventData active = {1, SCRID_NONE}, neighbor = {2, 7};
    Field field = {&neighbor};
    FieldInteractWk wk = {&field, NULL, NULL, &active, 0};
    GameEvent *event = CheckTriggerScrEvent(&wk, 0);
    assert(event && event->zone == 2 && event->script == 7);
    active.script = 4;
    event = CheckTriggerScrEvent(&wk, 0);
    assert(event && event->zone == 1 && event->script == 4);
    active.script = SCRID_NONE; field.neighbor = NULL;
    assert(CheckTriggerScrEvent(&wk, 0) == NULL);
    return 0;
}
'''
        residency.ActorResidencyTest().run_harness(harness + function + checks)

    def test_step_warp_preserves_owner_and_index(self):
        source = (ROOT / "src/ov036/fieldmap_event.c").read_text()
        function = residency.extract_function(source, "CheckWarpMapChangeEvent", "static GameEvent *")
        remember = residency.extract_function(source, "RememberOutboundWarp")
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef uint32_t u32;
typedef struct { int x, y, z; } VecFx32;
typedef struct { int disabled, step; } ZoneWarp;
typedef struct { int zoneId; ZoneWarp warps[2]; } EventData;
typedef struct { EventData *neighbor; } Field;
typedef struct { int zone, index; } ZoneSpawnInfo;
typedef struct { EventData *eventData; void *gameData; } FieldInteractWk;
typedef struct { int zone, index; } GameEvent;
#define WARP_ID_NONE 65535
static GameEvent result;
static int rememberedZone, rememberedIndex;
static u32 GetWarpForWalkIn(FieldInteractWk *wk, VecFx32 *pos) {
    (void)pos; return wk->eventData->warps[1].step ? 1 : WARP_ID_NONE;
}
static ZoneWarp *GetZoneWarpByID(EventData *data, u32 id) { return &data->warps[id]; }
static int IsWarpZoneOrWarpID0xFFFF(ZoneWarp *warp) { return warp->disabled; }
static int IsStepOnWarp(ZoneWarp *warp) { return warp->step == 1; }
static EventData *Field_GetNeighborEventsAtPosition(Field *field, VecFx32 *pos) {
    (void)pos; return field->neighbor;
}
static void SetupZoneWarpArrivalGrid(ZoneSpawnInfo *spawn, int zone, u32 id, int a, int b, int x, int y, int z) {
    (void)a; (void)b; (void)x; (void)y; (void)z; spawn->zone = zone; spawn->index = id;
}
static void SetGameDataOutboundWarpRememberInfo(void *game, ZoneSpawnInfo *spawn) {
    (void)game; rememberedZone = spawn->zone; rememberedIndex = spawn->index;
}
static GameEvent *CreateWarpMapChangeEvent(FieldInteractWk *wk, Field *field, u32 id, VecFx32 *pos) {
    (void)field; (void)pos; result.zone = wk->eventData->zoneId; result.index = id; return &result;
}
'''
        checks = r'''
int main(void) {
    EventData active = {1, {{0, 0}, {0, 0}}};
    EventData neighbor = {2, {{0, 0}, {0, 1}}};
    Field field = {&neighbor};
    FieldInteractWk wk = {&active, NULL};
    VecFx32 pos = {0};
    GameEvent *event = CheckWarpMapChangeEvent(&wk, &field, &pos);
    assert(event && event->zone == 2 && event->index == 1);
    assert(rememberedZone == 2 && rememberedIndex == 1 && wk.eventData == &active);
    active.warps[1].step = 1;
    event = CheckWarpMapChangeEvent(&wk, &field, &pos);
    assert(event && event->zone == 1 && rememberedZone == 1);
    active.warps[1].disabled = 1; neighbor.warps[1].disabled = 1;
    assert(CheckWarpMapChangeEvent(&wk, &field, &pos) == NULL);
    neighbor.warps[1].disabled = 0; neighbor.warps[1].step = 2;
    assert(CheckWarpMapChangeEvent(&wk, &field, &pos) == NULL);
    return 0;
}
'''
        residency.ActorResidencyTest().run_harness(harness + remember + function + checks)


if __name__ == "__main__":
    unittest.main()
