#include "app/pokelist.h"
#include "constants/items.h"
#include "dsprot/dsprot.h"
#include "gfl/heap.h"
#include "gfl/proc.h"
#include "save/bag.h"

// The party list's proc. The ROM doesn't name this file: it is named for the proc, which runs the list that
// plist_sys.c sets up, updates and frees

static BOOL PokeListProc_Init(GameProc *proc, u32 *state, void *param, void *work);
static void *PokeListProc_DeleteHeap(void *heapId, void *result);
static BOOL PokeListProc_Exit(GameProc *proc, u32 *state, void *param, void *work);
static BOOL PokeListProc_Main(GameProc *proc, u32 *state, void *param, void *work);

// Frames since the time left was last counted down
static u8 sTimerFrames;

GameProcFunctions POKELIST_PROC_FUNCTIONS = {
    PokeListProc_Init,
    PokeListProc_Main,
    PokeListProc_Exit,
};

static BOOL PokeListProc_Init(GameProc *proc, u32 *state, void *param, void *work) {
    PokeListWork *wk = work;

    switch (*state) {
    case 0:
        GFL_HeapCreateChild(HEAPID_USER, HEAPID_POKELIST, 0x30000);
        wk = GFL_ProcInitSubsystem(proc, sizeof(PokeListWork), HEAPID_POKELIST);
        wk->heapId = HEAPID_POKELIST;
        wk->param = param;
#ifdef HEX_STATUS
        // The player always has TM95, Hex Cannon, which any Pokémon learns
        if (wk->param->bag != NULL && BagSave_GetItemCountByID(wk->param->bag, ITEM_TM95, wk->heapId) == 0) {
            BagSave_AddItem(wk->param->bag, ITEM_TM95, 1, wk->heapId);
        }
#endif
        *state = 1;
    case 1:
        if (PokeList_Init(wk) == TRUE) {
            return TRUE;
        }
        break;
    }
    return FALSE;
}

// Called through DS Protect once the proc's work is freed
static void *PokeListProc_DeleteHeap(void *heapId, void *result) {
    GFL_HeapDelete(*(u32 *)heapId);
    return result;
}

static BOOL PokeListProc_Exit(GameProc *proc, u32 *state, void *param, void *work) {
    PokeListWork *wk = work;
    u32 heapId;
    BOOL result;
    BOOL *ret;
    u8 i;

    if (PokeList_Exit(wk) == FALSE) {
        return FALSE;
    }
    if (param == NULL) {
        for (i = 0; i < 3; i++) {
            if (wk->param->partners[i].party != NULL) {
                GFL_HeapFree(wk->param->partners[i].party);
            }
            if (wk->param->partners[i].name != NULL) {
                GFL_HeapFree(wk->param->partners[i].name);
            }
        }
        if (wk->param->regulation != NULL) {
            GFL_HeapFree(wk->param->regulation);
        }
        GFL_HeapFree(wk->param->party);
        GFL_HeapFree(wk->param);
    }
    GFL_ProcReleaseSubsystem(proc);
    heapId = HEAPID_POKELIST;
    result = TRUE;
    DSPROT_CHECKED_RUN(ret, DSProt_CallRunChecks, DSProt_CallCrash, PokeListProc_DeleteHeap, &heapId, &result);
    return *ret;
}

static BOOL PokeListProc_Main(GameProc *proc, u32 *state, void *param, void *work) {
    PokeListWork *wk = work;

    if (param == NULL && wk->param->timerEnabled == TRUE && wk->param->timeLeft != 0) {
        sTimerFrames++;
        if (sTimerFrames > 60) {
            sTimerFrames = 0;
            wk->param->timeLeft--;
        }
    }
    if (PokeList_Main(wk) == TRUE) {
        return TRUE;
    }
    return FALSE;
}
