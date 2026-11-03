# Seamless world streaming: work in progress

This is a handoff for the experimental `chunk` branch. It is not a finished seamless world and is not a matching-ROM
decompilation. The changes deliberately alter game code and assets; they should not be merged into `main` as-is.

## Goal and current state

Load and unload nearby world chunks around the player, keeping neighboring areas, their events and actors available
without replacing the whole field at every outdoor boundary. Preserve ordinary doors, interior warps and unrelated
boundaries. Both versions and old saves eventually need to work.

The runtime and several map placements are implemented, but **no in-game boundary crossing has been verified**. The
host-side tests described below check data and individual helpers, not the real DS renderer, movement, memory use,
event scheduler or full playthrough. Do not describe any of these areas as proven seamless.

## Runtime changes

- `src/ov036/field_g3d_mapper.c` and `include/field/field_g3d_mapper.h`: a bounded fifth mainland chunk slot, direction-
  based prefetch, retention and eviction of chunks, and a cache of textures and prop systems for multiple areas.
- `src/ov036/fieldmap.c` and `include/field/field_internal.h`: one neighboring event buffer, two-zone NPC prefetch
  and retention, a conservative actor-capacity fallback, zone-specific actor reuse, and exchange of event buffers on
  crossings. The design supports only one neighboring event/NPC zone at a time, not all zones that a multi-way
  junction might require.
- `src/ov012/field_actor.c`, `src/ov012/scrcmd_work.c` and related script commands: zone-qualified lookup for several
  actor operations, safer scripted actor addition, and NPC script selection by the actor's zone. Event, sign, trigger,
  quicksand and warp handling includes selected neighboring-zone paths in `src/ov036/fieldmap_event.c`.
- Trainer sight is deliberately restricted to the player's current zone. Other script/plugin paths, scheduled events,
  map-init behavior, mutable event state and resource lifetimes still need a complete cross-zone review.
- `Field_MigrateLegacyOutdoorPosition` translates old local-coordinate saves for the relocated outdoor zones and
  updates their existing actors. Host-side tests cover its idempotence, but real old saves have not been tested.

## Outdoor areas

| Connection | Current implementation | Important limits |
| --- | --- | --- |
| Route 16 / Lostlorn Forest | Forest placed at mainland cells `(15,10)` and `(15,11)`; a cloned approach at `(15,12)`; entrance warps disabled. | Collision-grid path passes. Visual geometry, the scripted scene and traversal are untested. |
| Route 4 / northern Castelia street | Street placed at `(13,19)` and `(13,20)`; version-specific Route 4 entrance warps disabled; crowd positions translated. | Collision-grid path passes. The rest of Castelia's separate rail-based maps remains disconnected. |
| Route 8 / Moor of Icirrus | Four Moor chunks placed at `(6,3)` through `(7,4)`; entrance warps disabled; events translated. | Collision-grid path passes, but the corridor only changes collision and may be visibly obstructed. Two unassigned background cells were replaced. |
| Route 14 / Abundant Shrine | Four shrine chunks placed at `(19,10)` through `(20,11)`; entrance warps disabled; event, actor-route and camera positions translated. | Collision-grid path passes, but its appearance, scripted scene and interior returns need in-game checks. Two unassigned background cells were replaced. |
| Striaton City / Dreamyard | Dreamyard placed at `(26,18)` through `(27,19)`; event and script coordinates translated. Experimental one-tile corridor changes both tree geometry and collision. | **Entrance warps remain enabled.** Packed geometry and terrain were checked statically, not walked in-game. Do not disable the warps until actual traversal and appearance are verified. Basement warps remain. |
| Outer / inner Virbank Complex | Inner section placed at `(6,22)` and `(6,23)`; event, scene and save coordinates translated. | **Entrance warps remain enabled.** A wall and gate obstruct the candidate seam; geometry and collision have not been connected. |

Other separate outdoor matrices, bridges, gates and rail-based maps still need investigation and integration. The
mainland matrix is `res/field/matrices/overworld.json`; zones, entities, scripts and model terrain live under
`res/field/`.

## Asset tools and tests

- `tools/data/map_model_data.py` can append a model based on an existing archive member and selectively re-encode
  changed shapes using `compact_position_edits`. The latter is an opt-in with constraints; it needs broader tests,
  especially for vertex colors, normals, UVs, transforms and models other than the two Dreamyard corridor chunks.
- `tools/data/open_dreamyard_corridor.py` prepares the experimental geometry and terrain. It moves tree vertices below
  ground, which can distort adjacent tree triangles. Review its visible results before using or extending it.
- `tools/data/chunk_geometry_corridor.py` checks ground and conservative triangle bounding boxes; it does not prove
  visual clearance or cover all possible props. Dreamyard tests also inspect the bounds of placed props in the two
  edited chunks and compare packed triangle positions and prop records.
- `tools/data/chunk_residency_report.py` reports area diversity in a matrix window.
- Run the current host tests from the repository root:

  ```sh
  python3 -m unittest tools.data.test_virbank_complex_placement tools.data.test_dreamyard_placement \
    tools.data.test_chunk_geometry_corridor tools.data.test_abundant_shrine_seam tools.data.test_moor_seam \
    tools.data.test_castelia_seam tools.data.test_lostlorn_seam tools.data.test_chunk_actor_residency \
    tools.data.test_chunk_event_boundaries -v
  ```

  The latest recorded run passed 23 tests. Some Dreamyard packed-archive tests require `extract/` and `build/` files;
  they skip when those files are unavailable.

## Build and testing status

- White 2's ROM target built during the last implementation pass; the current Black 2 source and changed assets
  compiled. `build/pokewhite2_us.nds` is a generated file and can become stale after switching branches or edits.
- The latest full `ninja` failed: the Black 2 original-archive comparison for `a/0/5/6` differs, and Black 2 ROM
  packing reported that the ARM9 secure area changed and requested an ARM7 BIOS. These changes intentionally alter
  original game data, so the matching-ROM checks cannot be claimed as passing.
- Earlier code-layout changes sometimes allowed both ROM targets to pack; do not assume that is stable. Preserve full
  build logs and inspect warnings and failures. A BIOS must come from an authorized source if needed.
- The two edited Dreamyard chunks packed to 55,988 and 62,076 bytes in both versions, below the mainland's `0x1b008`
  chunk buffer. This is not a runtime heap or VRAM measurement.
- melonDS was launched with the White 2 ROM from `build/`, but the session had no computer-control or screen access;
  neither successful game loading nor traversal was confirmed. Back up saves before manual testing.

## Recommended next steps

1. Set up an emulator or real-device testing workflow and back up saves. Verify loading, rendering, collision, NPCs,
   interactions, transitions, encounters, memory pressure, and travel in both directions for each existing seam.
2. Validate Dreamyard's experimental corridor in-game, including the nearby prop models and any distorted trees. Keep
   its entry warps until the path is verified; then test behavior with those warps disabled.
3. Design a visible, collision-matched route for inner Virbank Complex; preserve its entrance warp until verified.
4. Finish cross-zone event and script routing, NPC and trainer behavior, zone initialization, multi-neighbor residency,
   actor capacity and resource eviction. Test rapid reversals, saving/loading, map changes and three-zone junctions.
5. Integrate remaining outdoor and rail-based areas incrementally, translating all event, script, camera, Fly and save
   coordinates and preserving necessary interior connections. Validate geometry as well as collision.
6. Decide how this nonmatching experimental feature should coexist with the matching-ROM `main` branch before merging
   or publishing it. Resolve Black 2 packing and run both versions' full builds and warning checks when appropriate.
