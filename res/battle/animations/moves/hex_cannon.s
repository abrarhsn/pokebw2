// MOVE_HEX_CANNON's animation: member 560 of a/0/6/5

#include "asm/btlv_effvm.inc"

    ScriptHeader 1
    ScriptVariant HexCannon

HexCannon:
    CameraMove 2, 0x3000, 0, 0x3000, 0, 0, 0, 16, 0, 12
    McssSetVanish EFFVM_ATTACKER, TRUE
    PlaySE SEQ_SE_W014_01, 1, EFFVM_ATTACKER, 0, -1200, 127, 0, 0, 0
    SetYield FALSE
    PlaySE SEQ_SE_W221_NOISE, 1, EFFVM_ATTACKER, 100, 500, 127, 0, 0, 0
    PlaySE SEQ_SE_DUMMY5, 1, EFFVM_ATTACKER, 80, 0, 0, 0, 0, 0
    MoveSE 1, 0, 0, 500, 1000, 100, 20, 0, 0
    MoveSE 1, 0, 1, 127, 0, 100, 20, 0, 0
    PanSE 1, 0, EFFVM_ATTACKER, EFFVM_DEFENDER, 95, 30, 0, 0
    SetYield TRUE
    SetYield FALSE
    PlaySE SEQ_SE_W054_01, 2, EFFVM_DEFENDER, 110, 0, 120, 0, 0, 0
    SetYield TRUE
    ParticleLoad 418
    ParticleLoad 431
    EmitterAddAt 418, 0, 0, 0x4000, 0, 0, 0, 0, 0, 0, 0, 0x1000, 0x1000, 0x1000, 0x1000
    EmitterAddAt 418, 1, 0, 0x4000, 0, 0, 0, 0, 0, 0, 0, 0x1000, 0x1000, 0x1000, 0x1000
    EmitterAddAt 418, 2, 0, 0x4000, 0, 0, 0, 0, 0, 0, 0, 0x1000, 0x1000, 0x1000, 0x1000
    WaitFrames 80
    CameraMovePreset 1, 11, 16, 0, 12
    EmitterMoveFrom 418, 3, 1, 0, 0x2000, 0, EFFVM_EMIT_DEFENDER, 0x2000, 0x14000, 0, 0x1000, 0x1000, 0
    EmitterMove 431, 0, 1, EFFVM_EMIT_ATTACKER, EFFVM_EMIT_DEFENDER, 0x2000, 0, 0, 0x1000, 0x1000, 0
    WaitFrames 10
    EmitterAdd 418, 4, EFFVM_EMIT_DEFENDER, 8, 0x2000, 0, 0, 0x1000, 0x1000, 0x1000, 0x1000
    EmitterAdd 431, 1, EFFVM_EMIT_DEFENDER, 8, 0x2000, 0, 0, 0x1000, 0x1000, 0x1000, 0x1000
    McssSetVanish EFFVM_DEFENDER, TRUE
    McssPalFade EFFVM_DEFENDER, 0, 16, 0, 0x7c18
    McssMoveXY EFFVM_DEFENDER, 2, 0x4cd, 0, 1, 2, 3
    WaitFrames 20
    McssPalFade EFFVM_DEFENDER, 16, 0, 1, 0x7c18
    Wait EFFVM_WAIT_ALL
    McssSetVanish EFFVM_ATTACKER, FALSE
    McssSetVanish EFFVM_DEFENDER, FALSE
    CameraMovePreset 1, 8, 16, 0, 12
    Wait EFFVM_WAIT_ALL
    End
    .balign 4
