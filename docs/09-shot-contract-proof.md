# 09 — Phase 1: Shot Contract Proof (real Episode-1 shot)

**Status:** in progress, 2026-10-14. Stress-testing the shot contract ([03-orchestration.md](03-orchestration.md)) against a **real** MTower Episode-1 shot, to confirm the schema and ownership map survive production data before we build anything.

## Method

Take an actual shot from MTower's locked shot list and casting, and express it as a `shot contract`. Note every field MTower already has (so migration is a mapping, not a redesign) and every field the contract *adds* (the agent-era structure).

## Source shot: `T.2-01` (Teaser, Beat T.2 "The red cabin")

From `productions/thunderbolt/ep01_romani/02_preproduction/shot_list_00_teaser.json` + `casting.json`:
- 6s WS, lens `LENS_WIDE_24`, slow push-in, looks `[LOOK_BASE, LOOK_RED_CABIN]`.
- Character `C-01` (Capt. Hamdi, `ACT-0001`, `WEAR_CLEAN`, background) + ~18 commando extras.
- Assets `VEH-0001` (Mi-8 cabin), `PRP-0002` (RPG-7), `PRP-0003` (Malyutka).
- Interior Mi-8 at night, commandos shoulder-to-shoulder, RPGs upright, officer at forward bulkhead.

## Mapped to the shot contract

```jsonc
{
  "schema_version": 1,
  "shot_id": "T.2-01",
  "production": "thunderbolt",
  "episode": "ep01_romani",
  "beat_ref": "T.2",
  "status": "approved",              // this shot already exists in MTower
  "wave_ready": 2,

  "intent": {                        // Script — from description + screenplay
    "subject": "Mi-8 cabin at night, ~18 commandos shoulder to shoulder",
    "action": "men sway with the airframe; officer at the forward bulkhead",
    "setting": "interior Mi-8 helicopter cabin, rear view",
    "time_of_day": "night",
    "mood": "tense, silent, pre-mission dread",
    "refs": { "vehicle": "VEH-0001", "props": ["PRP-0002", "PRP-0003"] }
  },
  "direction": {                     // Director — coverage/blocking/tone
    "coverage": "establishing WS of the cabin",
    "blocking": "commandos on fold-down side benches, RPGs upright between knees; officer forward",
    "performance_note": "stillness; faces darkened; restrained",
    "pacing": "slow", "tone_ref": "red-cabin dread"
  },
  "research": [                      // Research — verified
    { "claim": "Mi-8 used to insert Sa'iqa 1973", "verdict": "verified", "tier": "primary", "source": "..." },
    { "claim": "RPG-7 / Malyutka in service 1973", "verdict": "verified", "tier": "primary", "source": "..." }
  ],
  "flags": [],

  "cast": [                          // Casting — from casting.json
    { "character_id": "C-01", "actor_id": "ACT-0001", "face_model": "act0001", "prominence": "background" }
  ],
  "crowd": [                         // NEW: archetype extras (not individually tracked)
    { "archetype": "egyptian_commandos", "count": 18, "wardrobe_id": "WRD-0001",
      "wear_state": "WEAR_CLEAN", "note": "faces darkened" }
  ],
  "wardrobe": [
    { "character_id": "C-01", "wardrobe_id": "WRD-0001", "wear_state": "WEAR_CLEAN" }
  ],
  "set": {
    "location_id": null, "vehicle_interior": "VEH-0001",
    "dressing": ["Malyutka cases + mine sacks down the center aisle"],
    "props": ["PRP-0002", "PRP-0003"], "set_state": "intact"
  },
  "camera": {
    "shot_size": "WS", "lens": "LENS_WIDE_24", "movement": "slow push-in down the aisle",
    "light": "red cabin lamp, flickering; dark", "look_key": ["LOOK_BASE", "LOOK_RED_CABIN"],
    "format": "2.39:1", "exposure_note": "night interior — lift shadows, keep red key"
  },
  "vfx": [{ "effect": "airframe vibration + handheld shake", "intensity": "subtle",
            "placement": "whole frame", "timing": "continuous" }],
  "continuity": { "prior_state_ref": null, "deltas": [], "violations": [] },

  "dialogue": [], "vo": null,        // none this shot
  "voice_notes": null,
  "audio": { "narration_take": null, "dialogue_takes": [],
             "sfx": ["rotor beat", "airframe rattle", "buckles tapping", "breathing"],
             "music_cue": null },

  "generation": { "candidates": [/* engine fills */], "selected": "..." },
  "qa": { "score": null, "verdict": "approved-in-mtower", "gate": 8.0, "issues": [], "rounds": 0 },
  "approval": { "state": "approved", "by": "user", "at": "2026-10-12", "notes": null },

  "cost_usd_total": 0.0,
  "history": [ /* append-only */ ]
}
```

## Findings

**The mapping works — most fields already exist in MTower.** Direct correspondences:

| MTower shot-list field | Shot contract field | Owner |
|---|---|---|
| `shot_id`, `beat`, `duration_s` | `shot_id`, `beat_ref` | — |
| `description` / `image_prompt_core` | `intent` | Script |
| `camera_move`, `shot_size`, `lens`, `look` | `camera` | Camera/DoP |
| `characters[].id/wear/prominence` | `cast[]` + `wardrobe[]` | Casting / Wardrobe |
| `extras` | `crowd[]` (NEW archetype shape) | Casting |
| `assets` (VEH/PRP) | `set` | Set decoration |
| `motion_prompt` | `vfx[]` (motion) + `camera.movement` | VFX / Camera |
| `sfx`, `music`, `vo` | `audio`, `vo` | Sound / Dialect |
| `video_model`, `lip_sync` | `generation` policy | Engine/Orchestrator |

**Schema changes this proof surfaced (fold into v1):**
1. **`crowd[]`** — a first-class archetype-extras field, distinct from tracked `cast[]` (matches the Casting decision: crowds = archetypes). MTower's free-text `extras` becomes structured.
2. **`set.vehicle_interior`** — a shot can live *inside* a vehicle (Mi-8 cabin) rather than a `location_id`; the set field needs both.
3. **`camera.look_key` is an array** (MTower stacks `LOOK_BASE` + a scene look). Contract must allow multiple look keys.
4. **`direction` vs `intent`** split holds up — MTower crams blocking into `description`; the contract cleanly separates Script's *what* from Director's *how*.
5. **`generation` policy** (video_model/lip_sync) is an orchestrator/engine concern, not a craft field — confirmed.

**Ownership map held** — every field maps to exactly one owning agent; reviewers (QA, Continuity) stay read-only. No collisions found on a real shot.

## Next in Phase 1

- Model **2 more diverse shots** to exercise edges: a **dialogue/VO beat** (Sound + Dialect fields) and a **night action shot with effects + injury delta** (VFX + Continuity). T.2-01 was a crowd establishing shot; those two cover the rest of the schema.
- Then **lock `schema_version: 1`** and update [03-orchestration.md](03-orchestration.md) with `crowd[]`, `vehicle_interior`, and array look keys.
