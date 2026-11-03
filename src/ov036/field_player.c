#include "types.h"
#include "constants/flags.h"
#include "constants/obj_codes.h"
#include "field/field.h"
#include "field/field_actor.h"
#include "field/field_camera.h"
#include "field/field_controller.h"
#include "field/field_effect.h"
#include "field/field_g3d_mapper.h"
#include "field/field_map.h"
#include "field/field_nogrid_mapper.h"
#include "field/field_player.h"
#include "field/field_player_core.h"
#include "field/field_player_grid.h"
#include "field/field_player_nogrid.h"
#include "field/field_rail.h"
#include "field/player_state.h"
#include "field/zone.h"
#include "gfl/heap.h"
#include "gfl/key.h"
#include "nitro/fx.h"
#include "save/event_work.h"
#include "system/game_data.h"
#include "system/game_system.h"

// The field's player: the core, and the grid and rail movement that the map's controller sets up

struct FieldPlayer {
    Field *field;
    FieldPlayerCore *core;
    FieldPlayerGrid *grid;
    FieldPlayerNoGrid *nogrid;
    FieldEffectTask *cloud; // FLIGHT: the cloud under the player on free flight
    BOOL dismountRequested; // FLIGHT: the player is at the bottom with L held, for the event provider to land them
    u32 dismountCooldown;
};

// The controller types that Field_GetResolvedControllerTypeID returns
#define CONTROLLER_GRID 0

#define GRID_TO_FX32(n) ((n) * FX32_CONST(16))

// How far below the player the water may be for them to start surfing
#define SURF_HEIGHT_MAX FX32_CONST(20)

typedef struct {
    u16 objCode;
    u16 exState;
} PlayerSprite;

// The object code and extra state of each form of the player, by sex
// clang-format off
static const PlayerSprite PLAYER_SPRITE_MAP[2][PLAYER_FORM_COUNT] = {
    {
        {OBJ_CODE_HERO, FLD_PLAYER_EXSTATE_NONE},
        {OBJ_CODE_232, FLD_PLAYER_EXSTATE_CYCLING},
        {OBJ_CODE_233, FLD_PLAYER_EXSTATE_SURF},
        {OBJ_CODE_233, FLD_PLAYER_EXSTATE_DIVE},
        {OBJ_CODE_234, 4},
        {OBJ_CODE_235, 4},
        {OBJ_CODE_236, 4},
        {OBJ_CODE_238, 4},
        {OBJ_CODE_239, 4},
        {OBJ_CODE_237, 4},
    },
    {
        {OBJ_CODE_HEROINE, FLD_PLAYER_EXSTATE_NONE},
        {OBJ_CODE_241, FLD_PLAYER_EXSTATE_CYCLING},
        {OBJ_CODE_242, FLD_PLAYER_EXSTATE_SURF},
        {OBJ_CODE_242, FLD_PLAYER_EXSTATE_DIVE},
        {OBJ_CODE_243, 4},
        {OBJ_CODE_244, 4},
        {OBJ_CODE_245, 4},
        {OBJ_CODE_247, 4},
        {OBJ_CODE_248, 4},
        {OBJ_CODE_246, 4},
    },
};

// clang-format on

FieldPlayer *FieldPlayer_Create(PlayerState *state, Field *field, const VecFx32 *pos, u32 sex, HeapID heapId) {
    FieldPlayer *player = GFL_HeapAllocate(heapId, sizeof(FieldPlayer), TRUE, "field_player.c", 76);

    player->field = field;
    player->core = FieldPlayerCore_Create(state, field, pos, sex, heapId);
    return player;
}

void FieldPlayer_Free(FieldPlayer *player) {
    if (player->grid != NULL) {
        FieldPlayerGrid_Free(player->grid);
    }
    if (player->nogrid != NULL) {
        FieldPlayerRail_Delete(player->nogrid);
    }
    FieldPlayerCore_Free(player->core);
    GFL_HeapFree(player);
}

void FieldPlayer_SyncState(FieldPlayer *player) {
    VecFx32 pos;
    RailPosition railPos;
    PlayerState *state = FieldPlayerCore_GetPlayerState(player->core);
    FieldActor *actor = FieldPlayerCore_GetActor(player->core);

    CopyActorWPos(actor, &pos);
    PlayerState_SetWPos(state, &pos);
    PlayerState_SetRotationByDir(state, GetActorFaceDir(actor));
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        PlayerState_SetIsRail(state, FALSE);
    } else {
        GetActorRailPos(actor, &railPos);
        PlayerState_SetRailPos(state, &railPos);
        PlayerState_SetIsRail(state, TRUE);
    }
}

// FLIGHT: the free flight, in which the player rides a cloud and moves in every direction, up and down, over any
// terrain. It sets the player's wPos itself, so the grid movement doesn't run, and the actor stays off the ground.
// How far the player moves in a frame, flat and with B held, and up and down
#define FLIGHT_SPEED FX32_CONST(3)
#define FLIGHT_SPEED_FAST FX32_CONST(6)
#define FLIGHT_CLIMB_SPEED FX32_CONST(2)
// How far above the ground the player flies, at least and at most
#define FLIGHT_HEIGHT_MIN FX32_CONST(12)
#define FLIGHT_HEIGHT_MAX FX32_CONST(480)

BOOL FieldPlayer_IsFlying(FieldPlayer *player) {
    return PlayerState_IsFlying(FieldPlayerCore_GetPlayerState(player->core));
}

// Whether free flight may start where the player is: anywhere, on foot. On the maps that move the player along rails
// it is not made to work, and the camera and the player may not agree there
BOOL FieldPlayer_CanStartFlight(FieldPlayer *player) {
    PlayerState *state = FieldPlayerCore_GetPlayerState(player->core);

    return FieldPlayerState_GetExState(state) == FLD_PLAYER_EXSTATE_NONE;
}

// What the actor and the camera do while the player flies: no ground height or tile, and no limits for the camera
static void FieldPlayer_SetFlightActorFlags(FieldPlayer *player, BOOL flying) {
    FieldActor *actor = FieldPlayerCore_GetActor(player->core);

    FldAct_SetHeightCalcDisabled(actor, flying);
    FldAct_SetMapAttrDisabled(actor, flying);
}

static void FieldPlayer_SetFlightCamera(FieldPlayer *player, BOOL flying) {
    FieldCamera *camera = Field_GetCameraSystem(player->field);

    if (camera == NULL) {
        return;
    }
    FieldCamera_SetUseBoundaryEnable(camera, !flying);
    if (flying) {
        FieldCamera_DisableDelay(camera);
    }
}

BOOL FieldPlayer_StartFlight(FieldPlayer *player) {
    if (!FieldPlayer_CanStartFlight(player)) {
        return FALSE;
    }
    PlayerState_SetFlying(FieldPlayerCore_GetPlayerState(player->core), TRUE);
    FieldPlayer_SetFlightActorFlags(player, TRUE);
    FieldPlayer_SetFlightCamera(player, TRUE);
    return TRUE;
}

// Lands on the tile center under the player, if it is ground the player can stand on
BOOL FieldPlayer_EndFlight(FieldPlayer *player) {
    FieldActor *actor = FieldPlayerCore_GetActor(player->core);
    VecFx32 pos;
    fx32 height;
    u32 tileType;

    FieldPlayerCore_GetWPos(player->core, &pos);
    ConvGXZToVector((s16)(((pos.x) >> 4) / FX32_ONE), (s16)(((pos.z) >> 4) / FX32_ONE), &pos);
    if (!GetHeightFromMap(actor, &pos, &height)) {
        return FALSE;
    }
    pos.y = height;
    tileType = GetTileTypeAtPos(Field_GetG3DMapper(player->field), &pos);
    if (tileType == TILE_TYPE_NONE || MapTile_BlocksCollision(tileType) ||
        (GetTileFlags(tileType) & TILE_FLAG_WATER) != 0) {
        return FALSE;
    }
    FieldPlayerCore_SetWPos(player->core, &pos);
    if (player->cloud != NULL) {
        FieldEffects_DeleteObject(player->cloud);
        player->cloud = NULL;
    }
    PlayerState_SetFlying(FieldPlayerCore_GetPlayerState(player->core), FALSE);
    FieldPlayer_SetFlightActorFlags(player, FALSE);
    FieldPlayer_SetFlightCamera(player, FALSE);
    return TRUE;
}

// Called as the player is made on a map load: the actor's flags don't outlast a warp, so they are set again if the
// flight goes on
void FieldPlayer_RestoreFlight(FieldPlayer *player) {
    FieldPlayer_SetFlightActorFlags(player, PlayerState_IsFlying(FieldPlayerCore_GetPlayerState(player->core)));
}

// Whether the player asked to get off the cloud since the last call
BOOL FieldPlayer_TakeDismountRequest(FieldPlayer *player) {
    BOOL requested = player->dismountRequested;

    player->dismountRequested = FALSE;
    return requested;
}

void FieldPlayer_UpdateFlight(FieldPlayer *player, u32 heldKeys) {
    FieldActor *actor = FieldPlayerCore_GetActor(player->core);
    FieldG3DMapper *mapper = Field_GetG3DMapper(player->field);
    fx32 speed = (heldKeys & PAD_BUTTON_B) ? FLIGHT_SPEED_FAST : FLIGHT_SPEED;
    VecFx32 pos;
    VecFx32 test;
    fx32 ground;
    u16 dir = DIR_NONE;

    FieldPlayerCore_GetWPos(player->core, &pos);
    test = pos;
    if (heldKeys & PAD_KEY_UP) {
        test.z -= speed;
        dir = DIR_UP;
    } else if (heldKeys & PAD_KEY_DOWN) {
        test.z += speed;
        dir = DIR_DOWN;
    }
    if (heldKeys & PAD_KEY_LEFT) {
        test.x -= speed;
        dir = DIR_LEFT;
    } else if (heldKeys & PAD_KEY_RIGHT) {
        test.x += speed;
        dir = DIR_RIGHT;
    }
    if (heldKeys & PAD_BUTTON_R) {
        pos.y += FLIGHT_CLIMB_SPEED;
    } else if (heldKeys & PAD_BUTTON_L) {
        pos.y -= FLIGHT_CLIMB_SPEED;
    }

    // Each axis on its own, so that the player slides along the edge of the map
    test.y = pos.y;
    if (!FieldG3DMapper_IsPosOutOfBounds(mapper, &test)) {
        pos = test;
    } else {
        VecFx32 axis = pos;

        axis.x = test.x;
        if (!FieldG3DMapper_IsPosOutOfBounds(mapper, &axis)) {
            pos.x = test.x;
        }
        axis = pos;
        axis.z = test.z;
        if (!FieldG3DMapper_IsPosOutOfBounds(mapper, &axis)) {
            pos.z = test.z;
        }
    }

    if (player->dismountCooldown != 0) {
        player->dismountCooldown--;
    }
    if (GetHeightFromMap(actor, &pos, &ground)) {
        if (pos.y < ground + FLIGHT_HEIGHT_MIN) {
            pos.y = ground + FLIGHT_HEIGHT_MIN;
        } else if (pos.y > ground + FLIGHT_HEIGHT_MAX) {
            pos.y = ground + FLIGHT_HEIGHT_MAX;
        }
        // Down to the lowest the player flies, with L still held: get off
        if ((heldKeys & PAD_BUTTON_L) && pos.y <= ground + FLIGHT_HEIGHT_MIN && player->dismountCooldown == 0) {
            player->dismountRequested = TRUE;
            player->dismountCooldown = 30;
        }
    }
    if (player->cloud == NULL) {
        player->cloud = FldeffCloud_Start(actor, Field_GetFieldEffects(player->field));
    }
    if (dir != DIR_NONE) {
        FieldPlayerCore_SetDirection(player->core, dir);
    }
    FieldPlayerCore_SetWPos(player->core, &pos);
    FieldPlayer_SetFlightCamera(player, TRUE);
}

GameEvent *FieldPlayer_CheckObjContactEvent(FieldPlayer *player, u32 pressedKeys, u32 heldKeys, u32 flags) {
    GameEvent *event = NULL;

    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        event = FieldPlayerGrid_CheckObjContactEvent(player->grid, pressedKeys, heldKeys, flags);
    }
    return event;
}

void FieldPlayer_SetSpecialSeq(FieldPlayer *player, u32 seq) {
    FieldPlayerCore_SetSpecialSeq(player->core, seq);
}

BOOL FieldPlayer_StepFormChange(FieldPlayer *player) {
    return FieldPlayerCore_StepFormChange(player->core);
}

void FieldPlayer_FinishFormChange(FieldPlayer *player) {
    FieldPlayerCore_FinishFormChange(player->core);
}

void FieldPlayer_ForceBrake(FieldPlayer *player) {
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        FieldPlayerGrid_ForceBrake(player->grid);
    } else {
        FieldPlayerRail_EndBlockedWalk(player->nogrid);
    }
}

void FieldPlayer_SetRideEffect(FieldPlayer *player, FieldEffectTask *task) {
    FieldPlayerCore_SetRideEffect(player->core, task);
}

FieldEffectTask *FieldPlayer_GetRideEffect(FieldPlayer *player) {
    return FieldPlayerCore_GetTerrainEffectTCB(player->core);
}

u16 FieldPlayer_GetMoveDirByKey(FieldPlayer *player, u32 heldKeys) {
    return FieldPlayerCore_GetMoveDirByKey(player->core, heldKeys);
}

BOOL FieldPlayer_CheckMoveBusy(FieldPlayer *player) {
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        return FieldPlayerGrid_IsBraking(player->grid);
    }
    return FieldPlayerRail_IsBlocked(player->nogrid);
}

void FieldPlayer_ChangeToNormalForm(FieldPlayer *player) {
    FieldPlayerCore_SetSpecialSeq(player->core, 1);
    FieldPlayerCore_FinishFormChange(player->core);
}

void FieldPlayer_UpdateActionStatusObserver(FieldPlayer *player) {
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        if (FieldPlayerGrid_IsConstMoving(player->grid) == TRUE) {
            FieldPlayerCore_ForceMoveObserveStatus(player->core, 2);
            return;
        }
        if (FieldPlayerGrid_IsCatwalkExiting(player->grid) == TRUE) {
            FieldPlayerCore_ForceMoveObserveStatus(player->core, 2);
            return;
        }
    } else if (FieldPlayerRail_IsForcedMove(player->nogrid) == TRUE) {
        FieldPlayerCore_ForceMoveObserveStatus(player->core, 2);
        return;
    }
    FieldPlayerCore_UpdateActionStatusObserver(player->core);
}

void FieldPlayer_GetWPos(FieldPlayer *player, VecFx32 *pos) {
    FieldPlayerCore_GetWPos(player->core, pos);
}

void FieldPlayer_SetWPos(FieldPlayer *player, const VecFx32 *pos) {
    FieldPlayerCore_SetWPos(player->core, pos);
}

u16 FieldPlayer_GetFaceDir(FieldPlayer *player) {
    return FieldPlayerCore_GetFaceDir(player->core);
}

void FieldPlayer_SetDirection(FieldPlayer *player, u16 dir) {
    FieldPlayerCore_SetDirection(player->core, dir);
}

Field *FieldPlayer_GetField(FieldPlayer *player) {
    return FieldPlayerCore_GetField(player->core);
}

FieldActor *FieldPlayer_GetActor(FieldPlayer *player) {
    return FieldPlayerCore_GetActor(player->core);
}

u32 FieldPlayer_GetMoveStatus(FieldPlayer *player) {
    return FieldPlayerCore_GetMoveStatus(player->core);
}

u32 FieldPlayer_GetMoveObserveStatus(FieldPlayer *player) {
    return FieldPlayerCore_GetMoveObserveStatus(player->core);
}

u32 FieldPlayer_GetExState(FieldPlayer *player) {
    return FieldPlayerCore_GetExState(player->core);
}

void FieldPlayer_SetSpecialState(FieldPlayer *player, u32 state) {
    FieldPlayerCore_SetExState(player->core, state);
}

u32 FieldPlayer_GetSex(FieldPlayer *player) {
    return FieldPlayerCore_GetSex(player->core);
}

GameSystem *FieldPlayer_GetGameSystem(FieldPlayer *player) {
    return FieldPlayerCore_GetGameSystem(player->core);
}

u32 FieldPlayer_GetTileTypeUnder(FieldPlayer *player) {
    fx32 height;

    return FieldPlayer_GetTileTypeInDirEx(player, PLAYER_DIR_NONE, &height);
}

u32 FieldPlayer_GetTileTypeInDir(FieldPlayer *player, u16 direction) {
    fx32 height;

    return FieldPlayer_GetTileTypeInDirEx(player, direction, &height);
}

u32 FieldPlayer_GetTileTypeInDirEx(FieldPlayer *player, u16 direction, fx32 *height) {
    VecFx32 pos;
    MapTerrainBuf terrain;
    RailPosition railPos;

    *height = 0;
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        FieldG3DMapper *mapper = Field_GetG3DMapper(player->field);

        if (direction == PLAYER_DIR_NONE) {
            FieldPlayer_GetWPos(player, &pos);
        } else {
            FieldPlayer_GetWPosInDir(player, direction, &pos);
        }
        if (FieldG3DMapper_GetTerrain(mapper, &pos, &terrain) == TRUE) {
            *height = terrain.height;
            return terrain.tileType;
        }
        return TILE_TYPE_NONE;
    } else {
        FieldActor *actor = FieldPlayer_GetActor(player);
        NoGridMapper *mapper = Field_GetNoGridMapper(player->field);
        FieldRailSystem *rail = FieldNoGridMapper_GetRailSystem(mapper);

        if (direction == PLAYER_DIR_NONE) {
            GetActorRailPos(actor, &railPos);
        } else if (!GetActorRailPosForDir(actor, direction, &railPos)) {
            return TILE_TYPE_NONE;
        }
        FieldRailSystem_GetLocationPos(rail, &railPos, &pos);
        *height = pos.y;
        return FieldNoGridMapper_GetTileAtPos(mapper, &railPos);
    }
}

u16 FieldPlayer_GetObjCodeByForme(u32 sex, u32 forme) {
    return PLAYER_SPRITE_MAP[sex][forme].objCode;
}

u16 FieldPlayer_GetObjCodeByExState(u32 sex, u32 exState) {
    const PlayerSprite *sprite;
    int i;

    for (i = 0, sprite = PLAYER_SPRITE_MAP[sex]; i < PLAYER_FORM_COUNT; i++, sprite++) {
        if (sprite->exState == exState) {
            return sprite->objCode;
        }
    }
    return OBJ_CODE_HERO;
}

// The form with the object code, PLAYER_FORM_COUNT if it isn't one of the player's
u32 FieldPlayer_GetExStateByObjCode(u32 objCode) {
    int sex, i;

    for (sex = 0; sex < 2; sex++) {
        const PlayerSprite *sprite = PLAYER_SPRITE_MAP[sex];

        for (i = 0; i < PLAYER_FORM_COUNT; i++, sprite++) {
            if (sprite->objCode == objCode) {
                return i;
            }
        }
    }
    return PLAYER_FORM_COUNT;
}

BOOL FieldPlayer_CheckNotWaterForm(FieldPlayer *player) {
    switch (FieldPlayer_GetExState(player)) {
    case FLD_PLAYER_EXSTATE_SURF:
    case FLD_PLAYER_EXSTATE_DIVE:
        return FALSE;
    }
    return TRUE;
}

void FieldPlayer_ForceObjCode(FieldPlayer *player, u16 objCode) {
    FieldPlayerCore_ForceObjCode(player->core, objCode);
}

void FieldPlayer_ClearObjCode(FieldPlayer *player) {
    FieldPlayerCore_ClearObjCode(player->core);
}

u32 FieldPlayer_CheckFormModel(FieldPlayer *player) {
    return FieldPlayerCore_CheckFormModel(player->core);
}

BOOL FieldPlayer_CheckAnimePaused(FieldPlayer *player) {
    return FieldPlayerCore_CheckAnimePaused(player->core);
}

FieldActor *FieldPlayer_GetActorInFront(FieldPlayer *player) {
    s16 x, y, z;
    RailPosition railPos;
    MMSys *system = Field_GetActorSystem(player->field);

    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        FieldPlayer_GetGPosInFront(player, &x, &y, &z);
        return GetFirstActorOnGPos(system, x, z, FALSE);
    }
    RailActor_GetFrontLocation(FieldPlayerCore_GetActor(player->core), &railPos);
    return FindActorByRailPos(system, &railPos, FALSE);
}

FieldActor *FieldPlayer_GetActorInFrontEx(FieldPlayer *player, fx32 maxHeightDiff) {
    s16 x, y, z;
    RailPosition railPos;
    MMSys *system = Field_GetActorSystem(player->field);

    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        FieldPlayer_GetGPosInFront(player, &x, &y, &z);
        return FindActorByGPos(system, x, z, GRID_TO_FX32(y), maxHeightDiff, FALSE);
    }
    RailActor_GetFrontLocation(FieldPlayerCore_GetActor(player->core), &railPos);
    return FindActorByRailPos(system, &railPos, FALSE);
}

void GetPlayerGPosPlusDir(FieldPlayer *player, u16 dir, s16 *x, s16 *y, s16 *z) {
    FieldActor *actor = FieldPlayer_GetActor(player);

    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        *x = GetGPosX(actor);
        *y = FldAct_GetGPosY(actor);
        *z = GetGPosZ(actor);
        *x += GetDirectionVectorCompX(dir);
        *z += GetDirectionVectorCompZ(dir);
    }
}

void FieldPlayer_GetWPosInDir(FieldPlayer *player, u16 direction, VecFx32 *position) {
    VecFx32 pos;
    VecFx16 dirVec;
    RailPosition railPos;
    s16 x, y, z;
    FieldActor *actor = FieldPlayerCore_GetActor(player->core);

    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        GetPlayerGPosPlusDir(player, direction, &x, &y, &z);
        ConvGXZToVector(x, z, position);
        position->y = GRID_TO_FX32(y);
    } else {
        FieldRailSystem *rail = FieldNoGridMapper_GetRailSystem(Field_GetNoGridMapper(player->field));
        fx32 step;

        GetActorRailPos(actor, &railPos);
        FieldRailSystem_GetLocationPos(rail, &railPos, &pos);
        RailActor_GetDrawOffsetByDir(actor, direction, &dirVec);
        step = FieldRailSystem_GetUnitScale(rail);
        position->x = pos.x + FX_Mul(dirVec.x, step);
        position->y = pos.y + FX_Mul(dirVec.y, step);
        position->z = pos.z + FX_Mul(dirVec.z, step);
    }
}

void FieldPlayer_GetGPosInFront(FieldPlayer *player, s16 *x, s16 *y, s16 *z) {
    GetPlayerGPosPlusDir(player, GetActorFaceDir(FieldPlayer_GetActor(player)), x, y, z);
}

void FieldPlayer_GetMoveOffsetInDir(FieldPlayer *player, u16 dir, VecFx32 *vec) {
    VecFx16 dirVec;
    FieldActor *actor = FieldPlayerCore_GetActor(player->core);

    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        vec->y = 0;
        vec->x = GetDirectionVectorCompX(dir);
        vec->z = GetDirectionVectorCompZ(dir);
        vec->x = GRID_TO_FX32(vec->x);
        vec->z = GRID_TO_FX32(vec->z);
        VEC_Normalize(vec, vec);
    } else {
        RailActor_GetDrawOffsetByDir(actor, dir, &dirVec);
        VEC_Set(vec, dirVec.x, dirVec.y, dirVec.z);
    }
}

u32 FieldPlayer_DeriveExState(FieldPlayer *player) {
    return FieldPlayerCore_DeriveExState(player->core);
}

BOOL FieldPlayer_WaitModelReady(FieldPlayer *player) {
    return FieldPlayerCore_WaitModelReady(player->core);
}

// Whether the player can start surfing onto the tile in the direction: they aren't surfing or diving, the tiles allow
// it, and the water is level with them or less than SURF_HEIGHT_MAX below
BOOL CheckSurfHeightAllow(FieldPlayer *player, u32 direction) {
    fx32 height;
    fx32 frontHeight;
    u32 tileUnder;
    u32 exState = FieldPlayer_GetExState(player);

    if (exState == FLD_PLAYER_EXSTATE_SURF || exState == FLD_PLAYER_EXSTATE_DIVE) {
        return FALSE;
    }
    tileUnder = FieldPlayer_GetTileTypeInDirEx(player, PLAYER_DIR_NONE, &height);
    if (!CheckSurfBeginTiles(tileUnder, FieldPlayer_GetTileTypeInDirEx(player, direction, &frontHeight))) {
        return FALSE;
    }
    height -= frontHeight;
    if (height < 0 || height >= SURF_HEIGHT_MAX) {
        return FALSE;
    }
    return TRUE;
}

BOOL CheckCanInteractWaterfall(FieldPlayer *player, u32 tileUnder, u32 tileInFront) {
    u32 exState = FieldPlayer_GetExState(player);

    if (MapTile_BlocksCollision(tileUnder) || exState != FLD_PLAYER_EXSTATE_SURF) {
        return FALSE;
    }
    return IsTileWaterfall(GetTileClass(tileInFront));
}

void FieldPlayer_InterruptCatwalkBalance(FieldPlayer *player, BOOL keep) {
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        FieldPlayerGrid_InterruptCatwalkBalance(player->grid, keep);
    }
}

void FieldPlayer_StopGridForcedMove(FieldPlayer *player) {
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        FieldPlayerGrid_StopForcedMove(player->grid);
    }
}

BOOL FieldPlayer_GetVerticalMoveOnlyFlag(FieldPlayer *player) {
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        return FieldPlayerGrid_GetVerticalMoveOnlyFlag(player->grid);
    }
    return FALSE;
}

void FieldPlayer_SetGridHopLanded(FieldPlayer *player) {
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID) {
        FieldPlayerGrid_SetVerticalMoveOnlyFlag(player->grid);
    }
}

BOOL FieldPlayer_CheckRunningShoesFlag(FieldPlayer *player) {
    EventWork *eventWork = GameData_GetEventWork(GSYS_GetGameData(FieldPlayer_GetGameSystem(player)));

    if (EventWork_FlagGet(eventWork, EVENT_FLAG_RUNNING_SHOES)) {
        return TRUE;
    }
    return FALSE;
}

void FieldPlayer_InitGrid(FieldPlayer *player, HeapID heapId) {
    player->grid = FieldPlayerGrid_Create(player->core, heapId);
}

void FieldPlayer_UpdateGridMovement(FieldPlayer *player, u32 pressedKeys, u32 heldKeys, u32 flags) {
    FieldPlayerGrid_UpdateMovement(player->grid, pressedKeys, heldKeys, flags);
}

void FieldPlayer_GetGPos(FieldPlayer *player, s16 *x, s16 *y, s16 *z) {
    FieldActor *actor = FieldPlayerCore_GetActor(player->core);

    *x = GetGPosX(actor);
    *y = FldAct_GetGPosY(actor);
    *z = GetGPosZ(actor);
}

BOOL FieldPlayer_IsGridHopping(FieldPlayer *player) {
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID &&
        FieldPlayerGrid_IsCatwalkExiting(player->grid) == TRUE) {
        return TRUE;
    }
    return FALSE;
}

void FieldPlayer_FinishGridHop(FieldPlayer *player) {
    if (Field_GetResolvedControllerTypeID(player->field) == CONTROLLER_GRID &&
        FieldPlayerGrid_IsCatwalkExiting(player->grid) == TRUE) {
        FieldPlayerGrid_SanitizeHeightMismatch(player->grid);
    }
}

void FieldPlayer_CreateNogrid(FieldPlayer *player, HeapID heapId) {
    player->nogrid = FieldPlayerRail_Create(player->core, heapId);
}

void FieldPlayer_UpdateRailMovement(FieldPlayer *player, u32 pressedKeys, u32 heldKeys) {
    FieldPlayerRail_UpdateMovement(player->nogrid, pressedKeys, heldKeys);
}

void FieldPlayer_AttachNogridActor(FieldPlayer *player, const RailPosition *pos) {
    FieldPlayerRail_AttachActor(player->nogrid, pos);
}

void FieldPlayer_ResetNogrid(FieldPlayer *player) {
    FieldPlayerRail_ClearRailWork(player->nogrid);
}

BOOL FieldPlayer_IsNogridForcedMove(FieldPlayer *player) {
    return FieldPlayerRail_IsForcedMove(player->nogrid);
}

RailUnit *FieldPlayer_GetNogridRailWork(FieldPlayer *player) {
    return FieldPlayerRail_GetRailWork(player->nogrid);
}

void FieldPlayer_SetRailPos(FieldPlayer *player, const RailPosition *pos) {
    FieldPlayerRail_SetRailPos(player->nogrid, pos);
}

void FieldPlayer_GetNogridNextRailLocation(FieldPlayer *player, RailPosition *pos) {
    FieldPlayerCore_GetRailPos(player->nogrid, pos);
}

void FieldPlayer_GetNogridLocationByDir(FieldPlayer *player, u16 dir, RailPosition *pos) {
    FieldPlayerRail_GetRailLocationByDir(player->nogrid, dir, pos);
}

void FieldPlayer_GetRailWorldPos(FieldPlayer *player, VecFx32 *pos) {
    FieldPlayerRail_GetWorldPos(player->nogrid, pos);
}

FieldPlayerGrid *FieldPlayer_GetGrid(FieldPlayer *player) {
    return player->grid;
}
