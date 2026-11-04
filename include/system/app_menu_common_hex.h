#ifndef POKEBW2_SYSTEM_APP_MENU_COMMON_HEX_H
#define POKEBW2_SYSTEM_APP_MENU_COMMON_HEX_H

#include "types.h"
#include "constants/battle.h"
#include "constants/pokemon.h"
#include "pml/poke_party.h"
#include "system/app_menu_common.h"

// The status icon of a party Pokémon in the overlays that show it. Main's AppMenuCommon_GetStatusIcon doesn't know Hex,
// and a build with Hex can't change main, so the overlays ask this, which gives the poison icon for Hex
#ifdef HEX_STATUS
static inline u32 AppMenuCommon_GetStatusIconWithHex(PartyPkm *pkm) {
    if (PokeParty_GetParam(pkm, PKM_PARAM_HP, NULL) != 0 &&
        PokeParty_GetParam(pkm, PKM_PARAM_STATUS, NULL) == CONDITION_HEX) {
        return APP_STATUS_ICON_POISON;
    }
    return AppMenuCommon_GetStatusIcon(pkm);
}
#define APP_MENU_STATUS_ICON(pkm) AppMenuCommon_GetStatusIconWithHex(pkm)
#else
#define APP_MENU_STATUS_ICON(pkm) AppMenuCommon_GetStatusIcon(pkm)
#endif

#endif // POKEBW2_SYSTEM_APP_MENU_COMMON_HEX_H
