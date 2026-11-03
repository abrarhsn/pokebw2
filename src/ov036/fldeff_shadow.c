// The shadow under each field actor: a billboard that follows the actor and hides while it can't have one. The name is
// the ROM's own, from GFL_HeapAllocate's file argument. Function names from swan
// (https://github.com/ds-pokemon-hacking/swan, GPL-3.0)
#include "types.h"
#include "field/field.h"
#include "field/field_actor.h"
#include "field/field_effect.h"
#include "field/field_player.h"
#include "field/zone.h"
#include "gfl/billboard_actor.h"
#include "gfl/g3d.h"
#include "gfl/heap.h"
#include "gfl/key.h"
#include "nitro/fx.h"

typedef struct {
    FieldEffects *effects;
    VecFx32 scale;
    BillboardActorSys *billboardActor;
    BillboardActorScene *scene;
    u32 matIndex;
    FieldColorPostFX *postFx;
    u32 cloudMatIndex; // FLIGHT
    u32 sparkleMatIndex; // FLIGHT
} FieldEffectShadow;

// FLIGHT: the cloud under the player on free flight, which the shadow's effect keeps the textures of: the cloud and
// the sparkles that circle it
#define CLOUD_SPARKLES 3

typedef struct {
    FieldEffectShadow *shadow;
    FieldActor *actor;
    FieldActorIdentity identity;
    u32 actorIndex;
    u32 frame;
    u32 sparkleActors[CLOUD_SPARKLES];
    VecFx32 cloudPos;
} CloudState;

// A field effect task's work is 0xa0 bytes, so the cloud's state is on the heap, which the task points to
typedef struct {
    CloudState *state;
} CloudTask;

typedef struct {
    CloudState *state;
} CloudTaskParams;

// FLIGHT: the members of the field effects' archive that hold the textures, how much larger than the shadow the cloud
// is drawn, and how far it sits below the player's feet and behind them
#define CLOUD_ARC_MEMBER 159
#define SPARKLE_ARC_MEMBER 160
#define CLOUD_SCALE FX32_CONST(2)
#define CLOUD_DROP FX32_CONST(1)
#define CLOUD_BEHIND FX32_CONST(1)

// What the task of an actor's shadow starts from
typedef struct {
    FieldEffectShadow *shadow;
    FieldActor *actor;
} ShadowTaskParams;

typedef struct {
    BOOL hidden;
    FieldEffectShadow *shadow;
    FieldActor *actor;
    FieldActorIdentity identity;
    u32 actorIndex;
} ShadowTask;

static void FldeffShadow_CreateSlot(FieldEffectShadow *shadow);
static void FldeffShadow_DeleteSlot(FieldEffectShadow *shadow);
static void FldeffShadow_Init(FieldEffectTask *task, void *work);
static void FldeffShadow_Exit(FieldEffectTask *task, void *work);
static void FldeffShadow_Update(FieldEffectTask *task, void *work);
static void FldeffShadow_Draw(FieldEffectTask *task, void *work);
static void FldeffCloud_Init(FieldEffectTask *task, void *work);
static void FldeffCloud_Exit(FieldEffectTask *task, void *work);
static void FldeffCloud_Update(FieldEffectTask *task, void *work);
static void FldeffCloud_Draw(FieldEffectTask *task, void *work);

static const VecFx32 SHADOW_SCALE = { FX32_ONE, FX32_ONE, FX32_CONST(0.75) };

// clang-format off
static const FieldEffectTaskVTable SHADOW_TASK_VTABLE = {
    sizeof(ShadowTask),
    FldeffShadow_Init,
    FldeffShadow_Exit,
    FldeffShadow_Update,
    FldeffShadow_Draw,
};

static const FieldEffectTaskVTable CLOUD_TASK_VTABLE = {
    sizeof(CloudTask),
    FldeffCloud_Init,
    FldeffCloud_Exit,
    FldeffCloud_Update,
    FldeffCloud_Draw,
};

// clang-format on

void *FieldEffect_Shadow_Create(FieldEffects *effects, HeapID heapId) {
    Field *field;
    FieldEffectShadow *shadow = GFL_HeapAllocate(heapId, sizeof(FieldEffectShadow), TRUE, "fldeff_shadow.c", 95);

    shadow->effects = effects;
    shadow->scale = SHADOW_SCALE;
    field = FieldEffects_GetField(effects);
    shadow->billboardActor = Field_GetEffectBillboardActor(field);
    shadow->scene = BillboardActorSys_GetScene(shadow->billboardActor);
    shadow->postFx = Field_GetColorPostFX(field);
    FldeffShadow_CreateSlot(shadow);
    return shadow;
}

void FieldEffect_Shadow_Free(FieldEffects *effects, void *data) {
    FldeffShadow_DeleteSlot(data);
    GFL_HeapFree(data);
}

static void FldeffShadow_CreateSlot(FieldEffectShadow *shadow) {
    BillboardActorMatRequest request;
    G3DResource *texture = GFL_G3DSysReadArcToolResource(FieldEffects_GetArc(shadow->effects), 47);

    FieldColorPostFX_Apply(shadow->postFx, texture);
    request.texResource = texture;
    request.format = 2;
    request.size = 17;
    request.faceWidth = 16;
    request.faceHeight = 16;
    request.mode = BILLBOARD_ACTOR_LOAD_TRIM;
    shadow->matIndex = BillboardActorSys_ExecMatLoadRequests(shadow->billboardActor, &request, 1);

    // FLIGHT
    texture = GFL_G3DSysReadArcToolResource(FieldEffects_GetArc(shadow->effects), CLOUD_ARC_MEMBER);
    FieldColorPostFX_Apply(shadow->postFx, texture);
    request.texResource = texture;
    shadow->cloudMatIndex = BillboardActorSys_ExecMatLoadRequests(shadow->billboardActor, &request, 1);
    texture = GFL_G3DSysReadArcToolResource(FieldEffects_GetArc(shadow->effects), SPARKLE_ARC_MEMBER);
    FieldColorPostFX_Apply(shadow->postFx, texture);
    request.texResource = texture;
    shadow->sparkleMatIndex = BillboardActorSys_ExecMatLoadRequests(shadow->billboardActor, &request, 1);
}

static void FldeffShadow_DeleteSlot(FieldEffectShadow *shadow) {
    BillboardActorSys_FreeMaterials(shadow->billboardActor, shadow->sparkleMatIndex, 1); // FLIGHT
    BillboardActorSys_FreeMaterials(shadow->billboardActor, shadow->cloudMatIndex, 1);
    BillboardActorSys_FreeMaterials(shadow->billboardActor, shadow->matIndex, 1);
}

// Give the actor a shadow
void FldeffShadow_Start(FieldActor *actor, FieldEffects *effects) {
    ShadowTaskParams params;

    params.shadow = FieldEffects_GetHandleData(effects, FLDEFF_SHADOW);
    params.actor = actor;
    FieldEffects_TCBCreate(effects, &SHADOW_TASK_VTABLE, NULL, 0, &params, 0);
}

static void FldeffShadow_Init(FieldEffectTask *task, void *work) {
    ShadowTask *shadowTask = work;
    const ShadowTaskParams *params = FieldEffects_GetObjectParam(task);
    BillboardActorRequest request;
    u8 polygonId;

    shadowTask->shadow = params->shadow;
    shadowTask->actor = params->actor;
    FldAct_GetIdentity(params->actor, &shadowTask->identity);
    request.texMat = 0;
    request.scaleX = FX32_ONE;
    request.scaleY = FX32_ONE;
    request.alpha = 19;
    request.visible = TRUE;
    request.lights = 1;
    request.pos = (VecFx32){ 0, 0, 0 };
    request.callback = NULL;
    request.callbackData = shadowTask;
    shadowTask->actorIndex = BillboardActorSys_ExecActorRequests(shadowTask->shadow->billboardActor,
                                                                 shadowTask->shadow->matIndex, &request, 1, 3);
    if (shadowTask->actorIndex == BILLBOARD_ACTOR_NONE) {
        FieldEffects_DeleteObject(task);
        return;
    }
    polygonId = 2;
    BillboardActorScene_SetActorPolygonId(shadowTask->shadow->scene, shadowTask->actorIndex, &polygonId);
    FieldEffects_UpdateObject(task);
}

static void FldeffShadow_Exit(FieldEffectTask *task, void *work) {
    ShadowTask *shadowTask = work;

    if (shadowTask->actorIndex != BILLBOARD_ACTOR_NONE) {
        BillboardActorSys_DeleteActors(shadowTask->shadow->billboardActor, (u16)shadowTask->actorIndex, 1);
    }
}

// End with the actor; hide while the actor is hidden or its shadow is
static void FldeffShadow_Update(FieldEffectTask *task, void *work) {
    ShadowTask *shadowTask = work;

    if (!FldAct_CheckIdentity(shadowTask->actor, &shadowTask->identity)) {
        FieldEffects_DeleteObject(task);
        return;
    }
    if (!FldActSys_AreShadowsEnabled(GetActorMModelSystem(shadowTask->actor))) {
        FieldEffects_DeleteObject(task);
        return;
    }
    if (IsActorHidden(shadowTask->actor) == TRUE ||
        CheckActorMovementFlag(shadowTask->actor, ACTOR_MOVEMENT_FLAG_HIDE_SHADOW)) {
        shadowTask->hidden = TRUE;
    } else {
        shadowTask->hidden = FALSE;
    }
}

// Follow the actor, a little above its feet
static void FldeffShadow_Draw(FieldEffectTask *task, void *work) {
    VecFx32 pos;
    VecFx32 offset;
    BOOL visible;
    ShadowTask *shadowTask = work;
    u32 actorIndex = shadowTask->actorIndex;
    const FieldActorConfig *config = GetActorMdlInfo(shadowTask->actor);

    if (!shadowTask->hidden) {
        visible = TRUE;
        CopyActorWPos(shadowTask->actor, &pos);
        CopyActorPosOffset(shadowTask->actor, &offset);
        VEC_Add(&pos, &offset, &pos);
        if (config->sceneNodeType == 10 || config->sceneNodeType == 11) {
            if (GetZoneIsEntreeForest(GetActorZoneID(shadowTask->actor))) {
                CopyActorWPosOffset(shadowTask->actor, &offset);
                offset.y = 0;
            } else {
                offset.x = 0;
                offset.y = 0;
                offset.z = 0;
            }
            if (config->billboardSize == ACTOR_BILLBOARD_SIZE_32) {
                offset.y = FX32_CONST(-0.5);
            }
            VEC_Add(&pos, &offset, &pos);
        }
        BillboardActorScene_SetActorHidden(shadowTask->shadow->scene, actorIndex, &visible);
        // FLIGHT: the player's shadow stays on the ground below the cloud
        {
            FieldPlayer *player = Field_GetPlayer(GetMMSysField(GetActorMModelSystem(shadowTask->actor)));
            fx32 ground;

            if (player != NULL && FieldPlayer_GetActor(player) == shadowTask->actor && FieldPlayer_IsFlying(player) &&
                GetHeightFromMap(shadowTask->actor, &pos, &ground)) {
                pos.y = ground;
            }
        }
        pos.y += FX32_ONE;
        BillboardActorScene_SetActorPos(shadowTask->shadow->scene, actorIndex, &pos);
    } else {
        BOOL hidden = FALSE;

        BillboardActorScene_SetActorHidden(shadowTask->shadow->scene, actorIndex, &hidden);
    }
}

// FLIGHT: give the actor the cloud of the free flight. The caller keeps the task and deletes it on landing; NULL if
// there is none
FieldEffectTask *FldeffCloud_Start(FieldActor *actor, FieldEffects *effects) {
    CloudTaskParams params;
    FieldEffectTask *task;

    params.state = GFL_HeapAllocate(Field_GetHeapID(FieldEffects_GetField(effects)), sizeof(CloudState), TRUE,
                                    "fldeff_shadow.c", 330);
    params.state->shadow = FieldEffects_GetHandleData(effects, FLDEFF_SHADOW);
    params.state->actor = actor;
    task = FieldEffects_TCBCreate(effects, &CLOUD_TASK_VTABLE, NULL, 0, &params, 0);
    if (task == NULL) {
        GFL_HeapFree(params.state);
    } else if (!task->active) {
        return NULL;
    }
    return task;
}

// A billboard of the cloud's effects on a material, or BILLBOARD_ACTOR_NONE if none is free
static u32 FldeffCloud_NewBillboard(CloudState *cloudTask, u32 matIndex, s16 scale, u8 alpha, u8 polygonId) {
    BillboardActorRequest request;
    u32 actorIndex;

    request.texMat = 0;
    request.scaleX = scale;
    request.scaleY = scale;
    request.alpha = alpha;
    request.visible = TRUE;
    request.lights = 1;
    request.pos = (VecFx32){ 0, 0, 0 };
    request.callback = NULL;
    request.callbackData = cloudTask;
    actorIndex = BillboardActorSys_ExecActorRequests(cloudTask->shadow->billboardActor, matIndex, &request, 1, 3);
    if (actorIndex != BILLBOARD_ACTOR_NONE) {
        BillboardActorScene_SetActorPolygonId(cloudTask->shadow->scene, actorIndex, &polygonId);
    }
    return actorIndex;
}

static void FldeffCloud_Init(FieldEffectTask *task, void *work) {
    CloudTask *cloud = work;
    const CloudTaskParams *params = FieldEffects_GetObjectParam(task);
    CloudState *cloudTask = params->state;
    u32 i;

    cloud->state = cloudTask;
    FldAct_GetIdentity(cloudTask->actor, &cloudTask->identity);
    for (i = 0; i < CLOUD_SPARKLES; i++) {
        cloudTask->sparkleActors[i] = BILLBOARD_ACTOR_NONE;
    }
    cloudTask->actorIndex = FldeffCloud_NewBillboard(cloudTask, cloudTask->shadow->cloudMatIndex, CLOUD_SCALE, 31, 2);
    if (cloudTask->actorIndex == BILLBOARD_ACTOR_NONE) {
        FieldEffects_DeleteObject(task);
        return;
    }
    for (i = 0; i < CLOUD_SPARKLES; i++) {
        cloudTask->sparkleActors[i] = FldeffCloud_NewBillboard(cloudTask, cloudTask->shadow->sparkleMatIndex, 0, 31, 5);
    }
    FieldEffects_UpdateObject(task);
}

static void FldeffCloud_Exit(FieldEffectTask *task, void *work) {
    CloudTask *cloud = work;
    CloudState *cloudTask = cloud->state;
    BillboardActorSys *sys = cloudTask->shadow->billboardActor;
    u32 i;

    for (i = 0; i < CLOUD_SPARKLES; i++) {
        if (cloudTask->sparkleActors[i] != BILLBOARD_ACTOR_NONE) {
            BillboardActorSys_DeleteActors(sys, (u16)cloudTask->sparkleActors[i], 1);
        }
    }
    if (cloudTask->actorIndex != BILLBOARD_ACTOR_NONE) {
        BillboardActorSys_DeleteActors(sys, (u16)cloudTask->actorIndex, 1);
    }
    GFL_HeapFree(cloudTask);
}

// End with the actor; wobble the cloud and circle the sparkles
static void FldeffCloud_Update(FieldEffectTask *task, void *work) {
    CloudState *cloudTask = ((CloudTask *)work)->state;
    BillboardActorScene *scene = cloudTask->shadow->scene;
    u32 held = GCTX_HIDGetHeldKeys();
    int moveX = ((held & PAD_KEY_RIGHT) != 0) - ((held & PAD_KEY_LEFT) != 0);
    int moveZ = ((held & PAD_KEY_DOWN) != 0) - ((held & PAD_KEY_UP) != 0);
    BOOL moving = moveX != 0 || moveZ != 0;
    BOOL sprint = moving && (held & PAD_BUTTON_B) != 0;
    VecFx32 offset;
    fx32 wobble;
    fx32 bob;
    s16 scaleX;
    s16 scaleY;
    u32 i;

    if (!FldAct_CheckIdentity(cloudTask->actor, &cloudTask->identity)) {
        FieldEffects_DeleteObject(task);
        return;
    }
    cloudTask->frame++;

    // The cloud breathes slowly and a little, a little more at a sprint, and bobs
    wobble = FX_SinIdx((u16)(cloudTask->frame * (sprint ? 0x0380 : 0x0240)));
    scaleX = CLOUD_SCALE + (CLOUD_SCALE * wobble >> 12) / (sprint ? 12 : 20);
    scaleY = CLOUD_SCALE - (CLOUD_SCALE * wobble >> 12) / (sprint ? 16 : 28);
    bob = FX_SinIdx((u16)(cloudTask->frame * 0x0200)) * FX32_CONST(0.75) >> 12;
    BillboardActorScene_SetActorScale(scene, cloudTask->actorIndex, &scaleX, &scaleY);

    CopyActorWPos(cloudTask->actor, &cloudTask->cloudPos);
    CopyActorPosOffset(cloudTask->actor, &offset);
    VEC_Add(&cloudTask->cloudPos, &offset, &cloudTask->cloudPos);
    cloudTask->cloudPos.y += bob - CLOUD_DROP;
    cloudTask->cloudPos.z -= CLOUD_BEHIND;

    // The sparkles circle the cloud and twinkle
    for (i = 0; i < CLOUD_SPARKLES; i++) {
        VecFx32 pos = cloudTask->cloudPos;
        u16 angle = cloudTask->frame * (sprint ? 0x0300 : 0x0180) + i * 0x5555;
        fx16 twinkle = FX_SinIdx((u16)(cloudTask->frame * 0x0400 + i * 0x3000));
        s16 scale = FX32_CONST(0.2) + (twinkle > 0 ? twinkle / 4 : 0);

        if (cloudTask->sparkleActors[i] == BILLBOARD_ACTOR_NONE) {
            continue;
        }
        pos.x += FX_CosIdx(angle) * FX32_CONST(9) >> 12;
        pos.y += FX32_CONST(5) + (FX_SinIdx(angle) * FX32_CONST(2) >> 12);
        pos.z += FX32_CONST(2);
        BillboardActorScene_SetActorPos(scene, cloudTask->sparkleActors[i], &pos);
        BillboardActorScene_SetActorScale(scene, cloudTask->sparkleActors[i], &scale, &scale);
    }
}

// Put the cloud at the player's feet
static void FldeffCloud_Draw(FieldEffectTask *task, void *work) {
    CloudState *cloudTask = ((CloudTask *)work)->state;
    BOOL visible = !IsActorHidden(cloudTask->actor);

    BillboardActorScene_SetActorHidden(cloudTask->shadow->scene, cloudTask->actorIndex, &visible);
    BillboardActorScene_SetActorPos(cloudTask->shadow->scene, cloudTask->actorIndex, &cloudTask->cloudPos);
}
