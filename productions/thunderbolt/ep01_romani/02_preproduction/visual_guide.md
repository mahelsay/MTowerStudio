# Episode 1 — Visual Guide

**Roadmap task:** 2.1 · **Status:** Draft v2.0 (studio library edition) · **Machine-readable files:** [`production_config.json`](production_config.json) · [`casting.json`](casting.json)

> **What this file is for:** it says how *this episode* uses the studio library: which film looks, which actors play which characters, which locations, vehicles, and props appear, and which details still need checking. The reusable pieces themselves live in the studio library ([`../../../../studio/library/`](../../../../studio/library/)), so the next production can reuse them.

---

## 1. Format and film look

This episode uses the studio defaults (`studio/library/looks/looks.json` → `format_defaults`):

| Setting | Value |
|---|---|
| Delivery | **2.39:1** cinemascope, generated at 16:9 and cropped in the edit |
| Framing rule | Faces, eyes, hands, and key action stay in the middle ~75% of the frame height |
| Frame rate / resolution | 24 fps · 1080p drafts and animatic → upscaled 4K finals |
| Base look | `LOOK_BASE_FILM_70S` + ", 1973" — 35mm film, anamorphic lenses, natural grain, restrained period color, documentary realism |
| Lens set | 24mm · 35mm · 50mm · 85mm · 135mm · 100mm macro (`camera` blocks) |

## 2. Three worlds, three palettes

The viewer must always know where they are from color alone.

| World | Palette | Looks used |
|---|---|---|
| **Desert** (Sinai) | Sand, salt-white, night blue, smoke grey, firelight orange | `LOOK_DAY_DESERT`, `LOOK_NIGHT_MOON`, `LOOK_DAWN_HAZE`, `LOOK_BATTLE_SMOKE`, `LOOK_NIGHT_FIRE`, `LOOK_DUSK_RED` |
| **Village** (Menoufia) | Green and gold, warm mud-brick, orange sunset | `LOOK_VILLAGE_DELTA`, `LOOK_DUSK_RED` |
| **Cairo flat** (Shubra) | Muted blue, warm bulb, amber lamp | `LOOK_CAIRO_BLUE_GLASS`, `LOOK_KEROSENE` |
| Interiors | — | `LOOK_RED_CABIN`, `LOOK_COCKPIT_GREEN`, `LOOK_LAMP_TENT`, `LOOK_BARE_BULB` |

## 3. Cast

Characters are cast from the studio's virtual actors. A character's prompt is built from **actor face + wardrobe + character additions + wear state** (see `casting.json`).

| Character | Played by (actor) | Trigger | Wardrobe | Character additions | Face model |
|---|---|---|---|---|---|
| C-01 Captain Hamdi Shalabi | ACT-0001 Tarek Selim 🔒 | `act0001tarek` | WRD-0001 | Captain's insignia, compass | LoRA |
| C-02 Sergeant Sayed | ACT-0002 Hazem Abdallah | `act0002hazem` | WRD-0001 | Sergeant's chevrons | LoRA |
| C-03 Private Mostafa | ACT-0003 Karim Nour | `act0003karim` | WRD-0001 | Oversized uniform, rocket bag | LoRA |
| C-04 Corporal Mahmoud | ACT-0004 Sherif Mansour | `act0004sherif` | WRD-0001 | Taped glasses, backpack radio | LoRA |
| C-05 Engineer Sgt. Hassan | ACT-0005 Yasser Hamdan | `act0005yasser` | WRD-0001 | Tape reel, mine probe | LoRA |
| C-06 Private Adel | ACT-0006 Amr Fahmy | `act0006amr` | WRD-0001 | Malutka control box | LoRA |
| C-07 Commander of Sa'iqa Forces | ACT-0011 Farouk El-Desouky 🔒 | — | WRD-0003 | — | Reference image only |
| C-08 Mi-8 Squadron Leader | ACT-0012 Magdy Riad 🔒 | — | WRD-0002 | — | Reference image only |
| C-11 Umm Mostafa | ACT-0007 Souad Roshdy | `act0007souad` | WRD-0006 | Flour on her hands | LoRA |
| C-12 Zeinab | ACT-0008 Malak Samy | `act0008malak` | WRD-0008 | Two long braids | LoRA |
| C-13 Fatma | ACT-0009 Nadia Fouad | `act0009nadia` | WRD-0007 | Thimble | LoRA |
| C-14 Ali | ACT-0010 Youssef Mamdouh | `act0010youssef` | WRD-0009 | Tin toy airplane | LoRA |

🔒 = **locked to role**: these actors portray real people or real roles and are never recast. ACT-0001 is a respectful stand-in for Captain Shalabi; if verified photographs are found, the actor is rebuilt to match them.

**Not cast** (no locked faces): Israeli tank crews and the battalion commander (C-09, distant only, WRD-0004), the Israeli brigade commander (C-10, radio only), Israeli infantry (WRD-0005), the remaining Egyptian commandos (WRD-0001), villagers, neighbors, the postman.

## 4. Library assets used in this episode

| Type | IDs | Light / state variants needed |
|---|---|---|
| Locations | LOC-0001 dunes · LOC-0002 road · LOC-0003 Tina Plain · LOC-0004 flat desert · LOC-0005 airfield & groves · LOC-0006 village · LOC-0007 Cairo flat · LOC-0008 training salt flats · LOC-0009 barracks · LOC-0010 Suez Canal at night · LOC-0011 command tent | Listed per location in `locations.json` |
| Vehicles | VEH-0001 Mi-8 (with cabin and cockpit) · VEH-0002 F-4E · VEH-0003 Egyptian jets · VEH-0004 Israeli recon jet · VEH-0005 Sho't Kal Centurion · VEH-0006 jeep · VEH-0007 tracked APC · VEH-0008 bus · VEH-0009 M3 half-track · VEH-0010 rowing boat | Listed per vehicle in `vehicles.json` |
| Wardrobe | WRD-0001 to WRD-0009 + wear states `WEAR_CLEAN` → `WEAR_POSTWAR` | See casting |
| Props | PRP-0001 to PRP-0016 | Listed per prop in `props.json` |

The episode plan's older IDs (ENV-, AIR-, ARM-, CMD-, PRP-0x) map to library IDs in `production_config.json` → `legacy_id_map`.

## 5. Period accuracy checklist

Every keyframe is reviewed against the studio lists `AVOID_GENERAL` and `AVOID_MODERN_MILITARY` (no modern gear, no text or logos, no gore).

**Open details to verify against 1973 reference photos:**

| Item | Current placeholder | Where to fix |
|---|---|---|
| Commando headgear | Bare-headed, short hair | `production_config.json` → `HEADGEAR` |
| Rifle stock | AKM, fixed wooden stock | PRP-0001 |
| Anti-tank hand grenade | RKG-3 | PRP-0004 |
| Mi-8 camouflage and roundel | Sand-and-brown, Egyptian roundel | VEH-0001 |
| Centurion markings (217th Brigade) | Generic chevrons | VEH-0005 |
| Half-track model | M3-type | VEH-0009 |
| Egyptian jets on Oct 6 / Israeli recon jet | Unspecified | VEH-0003, VEH-0004 |
| Advance-guard tracked vehicles | Unspecified | VEH-0007 |

## 6. Example: how a prompt is assembled

**Mostafa (C-03), close-up at night, salt-crusted** — the engine combines:

1. `LOOK_BASE` → `LOOK_BASE_FILM_70S`, 1973
2. `LOOK_NIGHT_MOON`
3. Actor ACT-0003: trigger `act0003karim` + *young Egyptian man, about 19, slim, boyish clean-shaven face, short black hair, large dark eyes*
4. Wardrobe WRD-0001 (with `HEADGEAR`) + additions: *uniform slightly too big for him, RPG-7 rocket carrier bag*
5. Wear state `WEAR_SALT`
6. Shot text: *close-up, looking off camera*
7. Lens `LENS_85_PORTRAIT`

Until the actor's LoRA is trained, the trigger word is left out and the face description does the work.

## 7. Episode approval tracker

Status is recorded on each library card (`status` field); this table is the episode's checklist.

| Group | Items | Status |
|---|---|---|
| Actors with LoRA | ACT-0001 … ACT-0010 | ☐ concept → anchor approved → LoRA trained → locked |
| Actors with reference image | ACT-0011, ACT-0012 | ☐ |
| Locations | LOC-0001 … LOC-0011 | ☐ |
| Vehicles | VEH-0001 … VEH-0010 | ☐ |
| Props | PRP-0001 … PRP-0016 | ☐ |

## 8. Shot lists (task 2.2)

| Part | File | Shots | Length | Premium (Veo) | Lip-sync needed |
|---|---|---|---|---|---|
| Teaser | [`shot_list_00_teaser.json`](shot_list_00_teaser.json) | 19 (2 title cards) | 2:10 | 2 | 0 |
| Act One | [`shot_list_01_act_one.json`](shot_list_01_act_one.json) | 73 | 10:20 | 3 | 0 |
| Act Two | [`shot_list_02_act_two.json`](shot_list_02_act_two.json) | 73 | 9:35 | 5 | 0 |
| Act Three | [`shot_list_03_act_three.json`](shot_list_03_act_three.json) | 62 | 8:35 | 9 | 0 |
| Act Four | [`shot_list_04_act_four.json`](shot_list_04_act_four.json) | 42 | 5:55 | 8 | 0 |
| Act Five | [`shot_list_05_act_five.json`](shot_list_05_act_five.json) | 37 (5 cards) | 6:45 | 7 | 0 |
| **Total** | | **306 shots · 299 generated** | **43:20** | **34** | **0** |

**Validation:** every file passes `studio/engine/tools/Test-ShotList.ps1` — all characters cast, all library IDs and look/lens keys exist, beat durations match the screenplay targets.

**Shot sizes:** EWS extreme wide · WS wide · MS medium · MCU medium close-up · CU close-up · ECU extreme close-up · OTS over-the-shoulder · INSERT detail · CARD title/text card.

**Production notes for the engine (task 2.3) and the look test (task 2.5):**

1. **No shot needs lip-sync.** Every spoken line is placed over hands, the back of a head, a profile in shadow, a helmet microphone, or a letter — by design.
2. **Long shots:** AI video clips are usually 5–10 seconds. Shots longer than 10 seconds (e.g., 1.1-10, 2.15-01, 5.7-01) are produced either as a held keyframe with subtle motion or as 2+ chained clips. The engine marks them automatically.
3. **Premium shots (34, about 11%)** are the emotional and spectacle peaks. The look test will measure the premium/default cost difference; if it's large, the list can be trimmed to about 20.
4. **Narration and dialogue are referenced, not copied.** The engine reads the Arabic text from the locked screenplay, so a fully vocalized line exists in one place only.
5. **Order of work:** keyframes for all 299 generated shots → animatic → only then video.