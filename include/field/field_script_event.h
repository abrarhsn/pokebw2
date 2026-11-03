#ifndef POKEBW2_FIELD_FIELD_SCRIPT_EVENT_H
#define POKEBW2_FIELD_FIELD_SCRIPT_EVENT_H

#include "types.h"
#include "gfl/heap.h"
#include "struct_decls.h"
#include "system/game_event.h"

struct EventScriptCallData {
    ScriptWork *work;
    FieldScriptSupervisor *supervisor;
};

GameEvent *EventScriptCall_Create(GameSystem *gsys, u16 scriptId, FieldActor *actor, HeapID heapId);
GameEvent *FieldEventScriptCall_CreateForZone(GameSystem *gsys, u16 scriptId, FieldActor *actor, u16 zoneId);
GameEventReturnCode EventScriptCall_Callback(GameEvent *event, u32 *state, void *data);
GameEvent *EventScriptCall_CreateCore(GameSystem *gsys, HeapID heapId, u16 scriptId, FieldActor *actor, u32 param);

#endif // POKEBW2_FIELD_FIELD_SCRIPT_EVENT_H
