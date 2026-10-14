# 09 — Phase 1: Shot Contract Proof (real Episode-1 shot)

**Status:** ✅ complete, schema v1 locked 2026-10-14. Stress-tested the shot contract ([03-orchestration.md](03-orchestration.md)) against **three real** MTower Episode-1 shots (crowd establishing · night dialogue · day action), confirming the schema and ownership map survive production data. Ten additions folded into `schema_version: 1` (see "Schema v1 — LOCKED" below).

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

## Shot 2 — `2.4-02` (Act Two, Beat 2.4 — a dialogue / night beat)

Real shot: CU of the radio operator (C-04, Corporal Mahmoud) decoding at night, face lit only by a red-filtered flashlight glinting on his taped wire-rimmed glasses, whispering; `lip_sync: required`; deep shadow. Exercises the **audio / dialect / wardrobe-detail / night-exposure** edges.

```jsonc
{
  "schema_version": 1, "shot_id": "2.4-02", "production": "thunderbolt", "episode": "ep01_romani",
  "beat_ref": "2.4", "status": "approved",
  "intent": { "subject": "radio operator decoding, night", "action": "whispers as he reads a scrap of paper",
    "setting": "canal embankment, night, deep shadow", "time_of_day": "night", "mood": "tense, hushed",
    "refs": { "props": ["PRP-0007"] } },
  "direction": { "coverage": "CU profile", "blocking": "face lit only by a red-filtered flashlight on the note",
    "performance_note": "lips parted in a whisper, face mostly in shadow", "pacing": "slow", "tone_ref": "red-light hush" },
  "cast": [ { "character_id": "C-04", "actor_id": "ACT-0004", "face_model": "act0004", "prominence": "lead" } ],
  "wardrobe": [ { "character_id": "C-04", "wardrobe_id": "WRD-0001", "wear_state": "WEAR_SALT",
    "additions": "taped wire-rimmed glasses (face addition)" } ],
  "makeup": [ { "character_id": "C-04", "skin_state": "field-tired", "injuries": [], "hair_state": "short military" } ],
  "set": { "location_id": "LOC-0003", "props": ["PRP-0007"], "set_state": "intact" },
  "camera": { "shot_size": "CU", "lens": "LENS_85_PORTRAIT", "movement": "static",
    "light": "red-filtered flashlight key, deep shadow", "look_key": ["LOOK_BASE", "LOOK_NIGHT_CANAL"],
    "format": "2.39:1", "exposure_note": "very low key — lift just the lit profile, keep red cast (MTower night-dark issue)" },
  "vfx": [],
  "dialogue": [ { "character_id": "C-04", "text_vo": "<decoded message, meaning>",
    "egyptian": "<Egyptian-dialect whisper, diacritized>", "diacritized": true,
    "acting_note": "whispering into the dark, steely, barely audible" } ],
  "vo": null, "voice_notes": "ar-EG, close-mic whisper, restrained",
  "audio": { "narration_take": null, "dialogue_takes": ["take_whisper_01"], "sfx": ["distant water", "paper"], "music_cue": null },
  "continuity": { "prior_state_ref": "2.4-01", "deltas": [], "violations": [] },
  "generation": { "policy": { "lip_sync": "required", "video_model": "default" }, "candidates": [], "selected": "..." },
  "qa": { "verdict": "approved-in-mtower", "gate": 8.0 },
  "approval": { "state": "approved", "by": "user" }
}
```

**New edges this surfaced:** `wardrobe[].additions` (MTower's `face_additions`, e.g. glasses) and the `makeup[]` block (Agent 5b) both attach to a character; **dialogue carries both meaning (`text_vo`) and dialect (`egyptian`)** owned by different agents on the same object; `generation.policy.lip_sync` confirmed as an engine/orchestrator field, not a craft field.

## Shot 3 — `3.8-01` (Act Three, Beat 3.8 "The battle" — an action / effects beat)

Real shot: an RPG team rising out of a pit and firing at the tank column, backblast kicking up sand. Exercises **crowd / VFX / stunt-action / environmental continuity** edges.

```jsonc
{
  "schema_version": 1, "shot_id": "3.8-01", "production": "thunderbolt", "episode": "ep01_romani",
  "beat_ref": "3.8", "status": "approved",
  "intent": { "subject": "RPG team fires on the column", "action": "rise from the pit, fire, drop back",
    "setting": "open desert, daylight, battle smoke", "time_of_day": "day", "mood": "controlled violence",
    "refs": { "props": ["PRP-0002"] } },
  "direction": { "coverage": "MS handheld", "blocking": "team rises, fires, drops as backblast blows sand",
    "performance_note": "drilled, fast, no panic", "pacing": "fast", "tone_ref": "restrained war" },
  "cast": [],
  "crowd": [ { "archetype": "egyptian_commandos", "count": 3, "wardrobe_id": "WRD-0001",
    "wear_state": "WEAR_BATTLE", "note": "RPG team" } ],
  "makeup": [ { "archetype": "egyptian_commandos", "skin_state": "sweat + dust", "injuries": [] } ],
  "set": { "location_id": "LOC-0004", "props": ["PRP-0002"], "set_state": "battle — smoke building" },
  "camera": { "shot_size": "MS", "lens": "LENS_35", "movement": "handheld",
    "light": "harsh midday + muzzle/backblast flash", "look_key": ["LOOK_BASE", "LOOK_BATTLE_SMOKE"],
    "format": "2.39:1", "exposure_note": "hard sun; protect highlights in the dust burst" },
  "action": { "choreography": "two-man RPG drill: gunner up, fires, both drop", "weapon_handling": "RPG-7 shoulder-fired, clear backblast cone",
    "movement": "rise-fire-drop", "beats": ["up","fire","down"], "safety_note": "backblast cone clear of friendlies" },
  "vfx": [ { "effect": "RPG backblast + sand cloud", "intensity": "medium", "placement": "behind the team", "timing": "on fire" },
    { "effect": "muzzle flash", "intensity": "low", "placement": "launcher", "timing": "on fire" } ],
  "vfx_light": "backblast flash — Camera integrates",
  "continuity": { "prior_state_ref": "3.7-06", "deltas": [ { "field": "set.set_state", "change": "smoke accumulates across beat 3.8" } ], "violations": [] },
  "dialogue": [], "vo": { "ref": "screenplay 3.8 VO", "placement": "over 3.8-04..08" },
  "audio": { "sfx": ["RPG launch", "backblast", "impact", "distant tank guns"], "music_cue": null },
  "generation": { "policy": { "lip_sync": "avoid", "video_model": "default" }, "candidates": [], "selected": "..." },
  "qa": { "verdict": "approved-in-mtower", "gate": 8.0 },
  "approval": { "state": "approved", "by": "user" }
}
```

**New edges this surfaced:** an `action` block (Agent 7b Stunt/Action) sits beside `vfx[]`; `crowd[]` carries its own `makeup[]` (archetype-level); `vfx_light` is proposed by VFX and consumed by Camera (the locked boundary); **continuity deltas are environmental here (smoke/wear), not human injury** — see the finding below.

## Key finding: restrained violence reshapes continuity

MTower's shot `3.8-05` is annotated **"No injuries shown"** — the series' restrained-violence rule. So **human-injury continuity deltas are rare**; the real cross-shot deltas are **environmental** (accumulating smoke, set damage, wear-state escalation `WEAR_SAND → WEAR_BATTLE`). The contract already models this: deltas target *any* field (`set.set_state`, `wardrobe[].wear_state`), not just injuries. Good — the Continuity + Wardrobe + Set "evolving state" decisions hold without a gore pipeline.

## Schema v1 — LOCKED (2026-10-14)

Three real shots (crowd establishing · night dialogue · day action) exercised every block. Folded into `schema_version: 1`:

1. **`crowd[]`** — archetype extras, distinct from `cast[]`; may carry archetype-level `makeup[]`.
2. **`set.vehicle_interior`** — a shot can live inside a vehicle, not only a `location_id`.
3. **`camera.look_key` is an array** — MTower stacks `LOOK_BASE` + a scene look.
4. **`wardrobe[].additions`** — MTower `face_additions` (e.g. glasses) attach to a character.
5. **`makeup[]`** — skin/hair/injury block (Agent 5b), per character or archetype.
6. **`action`** — Stunt/Action block (Agent 7b), beside `vfx[]`.
7. **`vfx_light`** — VFX proposes, Camera integrates (locked boundary).
8. **`dialogue[]` carries both** `text_vo` (Script, meaning) and `egyptian` (Dialect, wording) on one object.
9. **`generation.policy`** holds `lip_sync` + `video_model` — engine/orchestrator, not craft.
10. **`deltas` target any field** — continuity is general, not injury-specific (fits restrained violence).

**Ownership map held across all three shots** — every field maps to exactly one owning agent; reviewers (QA, Continuity) stay read-only. **Phase 1 complete.**

## Next

- Update [03-orchestration.md](03-orchestration.md) §2.4 schema to carry the v1 additions (crowd, makeup, action, vfx_light, wardrobe.additions, generation.policy, array look keys, vehicle_interior).
- Proceed to Phase 2 (Wave 1 fleet in the new Foundry project) or the Azure Bicep landing zone.
