#!/bin/zsh
# Usage: melon-run.sh ROM.nds [SAVE.sav | -]
# melonDS loads the .sav that sits next to the ROM with the same base name. Unless a SAVE is given, the one in Downloads
# is copied there first, so each run starts from it; "-" keeps the ROM's own .sav. What was there is kept as .sav.bak
set -e
rom="$1"
save="${2-$HOME/Downloads/Pokemon Black 2 S&#9.sav}"
[ -f "$rom" ] || { echo "no ROM: $rom" >&2; exit 1; }
# A running melonDS would write its own save over the copy below when it closes, so it goes first
if pkill -x melonDS 2>/dev/null; then
    # melonDS may not quit on the polite signal: it is forced after 3 seconds
    for i in {1..15}; do pgrep -x melonDS >/dev/null || break; sleep 0.2; done
    pkill -9 -x melonDS 2>/dev/null || true
    while pgrep -x melonDS >/dev/null; do sleep 0.2; done
fi
if [ "$save" != "-" ]; then
    [ -f "$save" ] || { echo "no save: $save" >&2; exit 1; }
    target="${rom%.nds}.sav"
    [ -f "$target" ] && cp "$target" "$target.bak"
    cp "$save" "$target"
fi
exec "$HOME/Downloads/melonDS.app/Contents/MacOS/melonDS" "$rom"
