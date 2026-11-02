// Move Yes (SANDBOX): the script of the old member 560, played when another move calls Yes

#include "asm/btlv_effvm.inc"

    ScriptHeader 1
    ScriptVariant MoveYes

MoveYes:
    CameraMovePreset 1, 11, 16, 0, 8
    Wait EFFVM_WAIT_ALL
    ParticleLoad 165
    EmitterAdd 165, 0, EFFVM_EMIT_DEFENDER, 8, 0x2000, 0, 0, 0x1000, 0x1000, 0x1000, 0x1000
    EmitterAdd 165, 1, EFFVM_EMIT_DEFENDER, 8, 0x2000, 0, 0, 0x1000, 0x1000, 0x1000, 0x1000
    SetYield FALSE
    PlaySE SEQ_SE_W001_01, 1, EFFVM_DEFENDER, 0, 0, 115, 0, 0, 0
    PlaySE SEQ_SE_W001_01, 2, EFFVM_DEFENDER, 8, 300, 100, 0, 0, 0
    SetYield TRUE
    McssSetVanish EFFVM_DEFENDER, TRUE
    McssScale EFFVM_DEFENDER, 2, 0x19a, -0x19a, 2, 0, 1
    Wait EFFVM_WAIT_ALL
    McssSetVanish EFFVM_DEFENDER, FALSE
    CameraMovePreset 1, 8, 16, 0, 8
    Wait EFFVM_WAIT_ALL
    End
