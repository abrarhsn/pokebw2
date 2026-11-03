#include "types.h"
#include "constants/sound.h"
#include "constants/zones.h"
#include "field/event_fishing.h"
#include "field/event_mapchange.h"
#include "field/event_sweet_scent.h"
#include "field/field.h"
#include "field/field_acmd.h"
#include "field/field_actor.h"
#include "field/field_map.h"
#include "field/field_player.h"
#include "field/field_surf.h"
#include "field/intrude_work.h"
#include "field/itemuse_event.h"
#include "field/player_action.h"
#include "field/player_state.h"
#include "field/subscreen.h"
#include "field/zone.h"
#include "gfl/sound.h"
#include "gfl/std.h"
#include "system/game_data.h"
#include "system/game_event.h"
#include "system/game_system.h"

typedef FieldActionResult (*FieldActionBlockCheck)(GameData *gameData, Field *field, PlayerState *state);

typedef struct {
    GameEvent *(*create)(Field *field, GameSystem *gsys);
    // The field action the event takes, 0xff for none
    u32 action;
} FieldCommonEvent;

typedef struct {
    GameSystem *gsys;
    u32 timer;
} EventFieldToggleCyclingWork;

typedef struct {
    GameSystem *gsys;
    Field *field;
} EventFieldToggleDowsingWork;

typedef struct {
    GameSystem *gsys;
} EventFieldToggleFlightWork;

static FieldActionResult CheckFieldActionBlocked(u32 action, GameSystem *gsys, Field *field);
static FieldActionResult FieldActionBlockCheck_Cycling(GameData *gameData, Field *field, PlayerState *state);
static FieldActionResult FieldActionBlockCheck_EscapeRope(GameData *gameData, Field *field, PlayerState *state);
static FieldActionResult FieldActionBlockCheck_NormalZone(GameData *gameData, Field *field, PlayerState *state);
static FieldActionResult FieldActionBlockCheck_Surf(GameData *gameData, Field *field, PlayerState *state);
static FieldActionResult FieldActionBlockCheck_NormalZoneNotRoyalUnova(GameData *gameData, Field *field,
                                                                       PlayerState *state);
static FieldActionResult FieldActionBlockCheck_Flight(GameData *gameData, Field *field, PlayerState *state);
static GameEventReturnCode EventFieldToggleFlight_Callback(GameEvent *event, u32 *state, void *data);
static GameEventReturnCode EventFlightDismount_Callback(GameEvent *event, u32 *state, void *data);
static GameEventReturnCode EventFieldToggleCycling_Callback(GameEvent *event, u32 *state, void *data);
static GameEventReturnCode EventFieldToggleDowsing_Callback(GameEvent *event, u32 *state, void *data);

static const FieldCommonEvent FIELD_COMMON_EVENTS[FIELD_COMMON_EVENT_COUNT] = {
    { EventFieldToggleCycling_Create, PLAYER_ACTION_BICYCLE },
    { EventEntralinkWarpIn_CreateDefault, 0xff },
    { EventMapChangeEscapeRope_Create, PLAYER_ACTION_ESCAPE_ROPE },
    { EventSweetScent_Create, 0xff },
    { EventFieldFishing_Create, PLAYER_ACTION_FISHING },
    { EventFieldToggleDowsing_Create, PLAYER_ACTION_DOWSING },
    { EventFieldToggleFlight_Create, PLAYER_ACTION_FLIGHT },
};

static const FieldActionBlockCheck FIELD_ACTION_BLOCK_CHECKS[PLAYER_ACTION_COUNT] = {
    FieldActionBlockCheck_Cycling,
    NULL,
    NULL,
    FieldActionBlockCheck_EscapeRope,
    FieldActionBlockCheck_NormalZone,
    FieldActionBlockCheck_Surf,
    FieldActionBlockCheck_NormalZoneNotRoyalUnova,
    FieldActionBlockCheck_Flight,
    NULL,
    FieldActionBlockCheck_NormalZoneNotRoyalUnova,
    FieldActionBlockCheck_NormalZoneNotRoyalUnova,
    FieldActionBlockCheck_NormalZoneNotRoyalUnova,
};

void PlayerActionPerms_Create(PlayerActionPerms *perms, GameSystem *gsys, Field *field) {
    GameData *gameData = GSYS_GetGameData(gsys);
    PlayerState *state = GameData_GetPlayerState(gameData);
    int i;

    MI_CpuFill8(perms, 0, sizeof(PlayerActionPerms));
    for (i = 0; i < PLAYER_ACTION_COUNT; i++) {
        PlayerActionPerms_SetActionBlocked(perms, i, CheckFieldActionBlocked(i, gsys, field));
    }
    perms->exState = FieldPlayerState_GetExState(state);
    perms->paired = GameData_CheckPairFlag(gameData);
}

static FieldActionResult CheckFieldActionBlocked(u32 action, GameSystem *gsys, Field *field) {
    GameData *gameData = GSYS_GetGameData(gsys);
    PlayerState *state = GameData_GetPlayerState(gameData);

    // FLIGHT: not the bike, the rope, the honey or the rod in the air
    if (PlayerState_IsFlying(state) &&
        (action == PLAYER_ACTION_BICYCLE || action == PLAYER_ACTION_ESCAPE_ROPE || action == PLAYER_ACTION_HONEY ||
         action == PLAYER_ACTION_FISHING)) {
        return FIELD_ACTION_BLOCKED;
    }
    if (FIELD_ACTION_BLOCK_CHECKS[action] == NULL) {
        return FIELD_ACTION_ALLOWED;
    }
    return FIELD_ACTION_BLOCK_CHECKS[action](gameData, field, state);
}

GameEvent *CallFieldCommonEventFunc(u32 id, GameSystem *gsys, Field *field) {
    return FIELD_COMMON_EVENTS[id].create(field, gsys);
}

static FieldActionResult FieldActionBlockCheck_Cycling(GameData *gameData, Field *field, PlayerState *state) {
    u16 zoneId = PlayerState_GetZoneID(state);
    u8 exState = FieldPlayerState_GetExState(state);
    BOOL tileBlocks = MapTile_IsBlocksCycling(GetTileClass(FieldPlayer_GetTileTypeUnder(Field_GetPlayer(field))));

    if (exState == FLD_PLAYER_EXSTATE_CYCLING) {
        if (tileBlocks) {
            return FIELD_ACTION_BLOCKED;
        }
        return FIELD_ACTION_ALLOWED;
    }
    if (!GetZoneFlagsEnableCycling(zoneId)) {
        return FIELD_ACTION_BLOCKED;
    }
    if (exState != FLD_PLAYER_EXSTATE_NONE) {
        return FIELD_ACTION_BLOCKED;
    }
    if (tileBlocks) {
        return FIELD_ACTION_BLOCKED;
    }
    if (GameData_CheckPairFlag(gameData)) {
        return FIELD_ACTION_ALLOWED_PAIRED;
    }
    return FIELD_ACTION_ALLOWED;
}

static FieldActionResult FieldActionBlockCheck_EscapeRope(GameData *gameData, Field *field, PlayerState *state) {
    u16 zoneId = PlayerState_GetZoneID(state);

    if (!IsZoneNormal(zoneId)) {
        return FIELD_ACTION_BLOCKED;
    }
    if (!GetZoneFlagsEnableEscapeRope(zoneId)) {
        return FIELD_ACTION_BLOCKED;
    }
    if (GameData_CheckPairFlag(gameData)) {
        return FIELD_ACTION_ALLOWED_PAIRED;
    }
    return FIELD_ACTION_ALLOWED;
}

static FieldActionResult FieldActionBlockCheck_NormalZone(GameData *gameData, Field *field, PlayerState *state) {
    if (IsZoneNormal(PlayerState_GetZoneID(state))) {
        return FIELD_ACTION_ALLOWED;
    }
    return FIELD_ACTION_BLOCKED;
}

static FieldActionResult FieldActionBlockCheck_Surf(GameData *gameData, Field *field, PlayerState *state) {
    if (!IsZoneNormal(PlayerState_GetZoneID(state))) {
        return FIELD_ACTION_BLOCKED;
    }
    if (!CreateSurfPos(gameData, field, NULL)) {
        return FIELD_ACTION_BLOCKED;
    }
    if (GameData_CheckPairFlag(gameData)) {
        return FIELD_ACTION_ALLOWED_PAIRED;
    }
    return FIELD_ACTION_ALLOWED;
}

static FieldActionResult FieldActionBlockCheck_NormalZoneNotRoyalUnova(GameData *gameData, Field *field,
                                                                       PlayerState *state) {
    u16 zoneId = PlayerState_GetZoneID(state);

    if (IsZoneRoyalUnova(zoneId)) {
        return FIELD_ACTION_BLOCKED;
    }
    if (IsZoneNormal(zoneId)) {
        return FIELD_ACTION_ALLOWED;
    }
    return FIELD_ACTION_BLOCKED;
}

// FLIGHT: landing is always asked for, and refused in the event if the tile below can't be stood on
static FieldActionResult FieldActionBlockCheck_Flight(GameData *gameData, Field *field, PlayerState *state) {
    if (PlayerState_IsFlying(state) || FieldPlayer_CanStartFlight(Field_GetPlayer(field))) {
        return FIELD_ACTION_ALLOWED;
    }
    return FIELD_ACTION_BLOCKED;
}

// FLIGHT: takes off, or lands
static GameEventReturnCode EventFieldToggleFlight_Callback(GameEvent *event, u32 *state, void *data) {
    EventFieldToggleFlightWork *work = data;
    FieldPlayer *player = Field_GetPlayer(GSYS_GetField(work->gsys));

    if (FieldPlayer_IsFlying(player)) {
        if (!FieldPlayer_EndFlight(player)) {
            GFL_SndSEPlay(SEQ_SE_CANCEL1);
        }
    } else if (FieldPlayer_StartFlight(player)) {
        GFL_SndSEPlay(SEQ_SE_BICYCLE);
    }
    return GAMEEVENT_DONE;
}

GameEvent *EventFieldToggleFlight_Create(Field *field, GameSystem *gsys) {
    GameEvent *event =
        GameEvent_Create(gsys, NULL, EventFieldToggleFlight_Callback, sizeof(EventFieldToggleFlightWork));
    EventFieldToggleFlightWork *work = GameEvent_GetData(event);

    work->gsys = gsys;
    return event;
}

// FLIGHT: gets off the cloud at the bottom, with a hop onto the tile in front if the player can stand there
static GameEventReturnCode EventFlightDismount_Callback(GameEvent *event, u32 *state, void *data) {
    EventFieldToggleFlightWork *work = data;
    FieldPlayer *player = Field_GetPlayer(GSYS_GetField(work->gsys));
    FieldActor *actor = FieldPlayer_GetActor(player);

    switch (*state) {
    case 0: {
        u16 dir;
        u32 tileInFront;

        if (!FieldPlayer_EndFlight(player)) {
            GFL_SndSEPlay(SEQ_SE_CANCEL1);
            return GAMEEVENT_DONE;
        }
        dir = FieldPlayer_GetFaceDir(player);
        tileInFront = FieldPlayer_GetTileTypeInDir(player, dir);
        if (tileInFront == TILE_TYPE_NONE || MapTile_BlocksCollision(tileInFront) ||
            (GetTileFlags(tileInFront) & TILE_FLAG_WATER) != 0) {
            return GAMEEVENT_DONE;
        }
        FldAct_SetAcmd(actor, GetAcmdForDir(dir, ACMD_JUMP_1));
        GFL_SndSEPlay(SEQ_SE_DANSA);
        (*state)++;
        break;
    }
    case 1:
        if (FldAct_CheckAcmdEnd(actor)) {
            FldAct_EndAcmd(actor);
            return GAMEEVENT_DONE;
        }
        break;
    }
    return GAMEEVENT_CONTINUE;
}

GameEvent *EventFlightDismount_Create(Field *field, GameSystem *gsys) {
    GameEvent *event =
        GameEvent_Create(gsys, NULL, EventFlightDismount_Callback, sizeof(EventFieldToggleFlightWork));
    EventFieldToggleFlightWork *work = GameEvent_GetData(event);

    work->gsys = gsys;
    return event;
}

static GameEventReturnCode EventFieldToggleCycling_Callback(GameEvent *event, u32 *state, void *data) {
    EventFieldToggleCyclingWork *work = data;
    Field *field = GSYS_GetField(work->gsys);
    GameCommSys *commSys;

    Field_GetActorSystem(field);
    switch (*state) {
    case 0:
        commSys = GSYS_GetGameCommSystem(work->gsys);
        work->timer++;
        if (Intrude_IsSessionEndPending(commSys) == TRUE && work->timer < 30) {
            break;
        }
        Field_ToggleCycling(field);
        (*state)++;
    case 1:
        if (FieldPlayer_StepFormChange(Field_GetPlayer(field)) == TRUE) {
            (*state)++;
        }
        break;
    case 2:
        if (FieldPlayer_WaitModelReady(Field_GetPlayer(field)) == TRUE) {
            return GAMEEVENT_DONE;
        }
        break;
    }
    return GAMEEVENT_CONTINUE;
}

GameEvent *EventFieldToggleCycling_Create(Field *field, GameSystem *gsys) {
    GameEvent *event =
        GameEvent_Create(gsys, NULL, EventFieldToggleCycling_Callback, sizeof(EventFieldToggleCyclingWork));
    EventFieldToggleCyclingWork *work = GameEvent_GetData(event);

    work->gsys = gsys;
    work->timer = 0;
    return event;
}

GameEvent *EventEntralinkWarpIn_CreateDefault(Field *field, GameSystem *gsys) {
    VecFx32 pos;

    pos.x = FX32_CONST(512);
    pos.y = 32;
    pos.z = FX32_CONST(488);
    return EventEntralinkWarpIn_Create(gsys, ZONE_ENTRALINK, &pos, 0);
}

static GameEventReturnCode EventFieldToggleDowsing_Callback(GameEvent *event, u32 *state, void *data) {
    EventFieldToggleDowsingWork *work = data;
    FieldSubscreen *subscreen = Field_GetSubscreen(work->field);

    if (FieldSubscreen_GetScreenID(subscreen) == FLD_SUBSCREEN_ID_DOWSING) {
        FieldSubscreen_ReqChange(subscreen, FLD_SUBSCREEN_ID_DEFAULT);
    } else {
        FieldSubscreen_ReqChange(subscreen, FLD_SUBSCREEN_ID_DOWSING);
    }
    return GAMEEVENT_DONE;
}

GameEvent *EventFieldToggleDowsing_Create(Field *field, GameSystem *gsys) {
    GameEvent *event =
        GameEvent_Create(gsys, NULL, EventFieldToggleDowsing_Callback, sizeof(EventFieldToggleDowsingWork));
    EventFieldToggleDowsingWork *work = GameEvent_GetData(event);

    work->gsys = gsys;
    work->field = field;
    return event;
}
