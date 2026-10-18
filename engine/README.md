# Production Engine

The engine turns a production's shot lists into images, video, and voice by calling AI tools through their APIs. It is shared by every production and uses only Python's standard library (nothing extra to install).

## How it keeps you safe

| Guard | What it does |
|---|---|
| **Dry run by default** | Every `generate` command first prints the plan and the estimated cost, and stops. |
| **Explicit confirmation** | A paid run happens only with `--confirm-cost <USD>` at least as high as the estimate. |
| **Unverified prices block runs** | A model whose `price_usd` is `null` in `engine_config.json` cannot run. Prices are verified on the provider's site first. |
| **Spending limits** | A per-batch limit (`MTOWER_BATCH_LIMIT_USD`) and two monthly limits: fal/ElevenLabs (`MTOWER_MONTHLY_LIMIT_USD`) and Azure (`MTOWER_AZURE_MONTHLY_LIMIT_USD`, default $300, matching the Azure budget). Also set a cap on each provider's website. |
| **Cost ledger** | Every paid call is logged to `ledger.jsonl` (in git). |
| **Secrets stay local** | API keys are read from the repo-root `.env` (git-ignored) and never printed. |

## Setup (once)

1. Copy `.env.example` (repo root) to `.env` and fill in the keys. **Never paste keys into chat.**
2. Optional: set `MTOWER_MEDIA_ROOT` to a Google Drive folder so generated media sync to the cloud.
3. Run `./mtower.ps1 doctor` from this folder.

## Commands

Run from `engine/` with `./mtower.ps1 <command>` (the launcher finds the real Python).

| Command | What it does | Costs money? |
|---|---|---|
| `doctor` | Checks Python, `.env` keys (set / not set), media folder, library, model prices, limits | No |
| `check` | Validates every shot against the library, casting, and the locked screenplay | No |
| `prompt --shot 2.5-01` | Shows the full image prompt, motion prompt, and review list for a shot. `--chatgpt`: a paste-ready ChatGPT prompt + reference photos to attach | No |
| `import [shot IDs]` | Imports images saved in `media/inbox/` (named by shot ID, e.g. `T.2-01.png`) as 1280×720 keyframes | No |
| `generate composition 1.6-03 3.13-01` | **Hard shots on Azure** (gpt-image-2): the body-only prompt (with the natural-look blocks) + the props' reference photos → 1280×720 keyframes, then the face pass (Azure face swap; fal for children). `--quality low/medium/high`, `--variants N`, `--no-face-pass`, `--actor-refs` (attach the lead's anchor portrait instead of a face pass) | Only with `--confirm-cost` |
| `generate face-pass T.2-01` | Puts the cast's faces on the leads of the shot's latest keyframe batch (e.g. an imported ChatGPT image): Azure face swap by default | Only with `--confirm-cost` |
| `generate edit 4.8-03 --instruction "..."` | **Fixes one detail** of a keyframe with FLUX.1 Kontext on Azure (e.g. "Replace the cross on the wall with a paper calendar. Keep everything else exactly the same."). Edits the approved keyframe, else the newest (`--source FILE` to choose); faces are kept, so no face pass. $0.04 | Only with `--confirm-cost` |
| `prompt --actor ACT-0003` | Shows an actor's reference-portrait prompt | No |
| `script --part 01_act_one --beat 1.4` | Shows a beat's Arabic narration and dialogue from the screenplay | No |
| `generate anchors ACT-0003` | Plans candidate portraits for an actor (task 2.4). Refuses if `cast-check` finds a look-alike | Only with `--confirm-cost` |
| `generate training-set ACT-0003` | Plans 20 edits of the approved anchor (angles, light, expressions, outfits) for the actor's face model. `--only KEY…` re-rolls single variations. With `PRP-` IDs: edits of the prop's reference photos for a prop model | Only with `--confirm-cost` |
| `generate lora ACT-0003` | Trains the actor's face model (LoRA) from the kept training images (+ anchor); records it on the actor card (`lora_trained`). With `PRP-` IDs: trains a prop model | Only with `--confirm-cost` |
| `generate lora-tests ACT-0003` | Tests the trained face model on 3 real solo shots from the production (they double as draft keyframes); falls back to 4 studio portraits if the actor has no solo shot | Only with `--confirm-cost` |
| `cast-check [ids] [--coverage]` | Checks every actor is clearly a different person (shared face traits per pair, nearest look-alike, unused traits for new actors) | No |
| `generate plates LOC-0003` | Plans reference plates for a location/vehicle/prop in each light variant | Only with `--confirm-cost` |
| `generate keyframes --part 02_act_two 2.5-01` | Plans keyframes for shots (all shots of a part if no IDs are given) | Only with `--confirm-cost` |
| `generate clips --part 02_act_two 2.5-01` | Animates **approved** keyframes (shots or a whole part). Default `video_default` = Kling O3 Pro (chosen after the 2.5-05 bake-off); `video_kling_v3` = Kling v3 Pro; shots marked `premium` use `video_premium` = Veo 3.1 Fast. Each model gets the shot's length, rounded up to a duration it offers (Veo: 4/6/8 s; Kling: 3–15 s). `--models video_default video_kling_v3 video_premium` runs a side-by-side bake-off, one folder per model. No sound (we make our own). Veo 3.1 refuses Karim's face (ACT-0003, boyish 19) and every child, so Kling is the default | Only with `--confirm-cost` |
| `review [folder]` | Opens the review app at http://localhost:8765 (start it on `../../media` to see everything). Tabs per kind (Keyframes, Clips, Narration, Animatics, Cuts, Posters, Casting, Training sets, Face-model tests), filters (Needs decision · Approved below gate · Newer candidates · Not approved · Approved ✓ · All), a sidebar of shots with status dots and best QA score, and **one shot at a time**: the approved take next to the selected candidate with both QA verdicts, a filmstrip of every take (newest first), a note box, and a click-to-zoom. Keys: ↑↓ shot, ←→ take, A approve, C compare, N note, Z zoom. A **To do** box on every shot says what is expected (e.g. "approved below the gate: approve a better take, or press *Keep approved take* and give a reason"). **Approval gate** (`engine_config.json` → `qa_gate`, agreed 2026-10-13): keyframes and clips need QA 8/10, casting portraits and posters 7/10; below the gate, or without a review, Approve asks for a written reason, saved as `override` in `approved.json`. Training sets keep the Kept/Rejected toggles and the training gate | No |
| `ledger` | Shows recorded spending | No |
| `qa [shot IDs] [--part P] [--scope current\|all] [--anchors] [--force]` | **Vision QA** (Azure gpt-5.6-sol): reviews each image against its design and saves `<image>.qa.json` (shown on the gallery card) plus `03_production/qa/qa_report.md`. `--report` only rebuilds the report (free). $0.05–0.09 per image | Only with `--confirm-cost` |
| `script-qa 01_act_one [--beats 1.4] [--force] [--report]` | **Script board** (Azure gpt-5.6-sol, high reasoning) for a screenplay file under `01_development/screenplay/` (drafts too: `drafts/02_act_two_v2`). Every dialogue line is scored 0–10 on Egyptian street dialect (1973, the character's home), army register, intensity vs situation, character, drama, diacritics/spelling for the voices, and lip-sync length; the beat is checked as a scene, for history (real people only around documented actions) and the series rules (no Quran). Gate: every beat and every line ≥ 8/10. Each line also gets a suggested performance (intensity, volume, pace, emotion, delivery) for the shot list, and a rewrite when it is below the gate — the writer decides. Verdicts are saved per beat in `screenplay/qa/<file>/<beat>.json` with the beat's text hash, so a re-run only reviews beats that changed; report `screenplay/qa/<file>.qa.md`. About $0.08–0.20 per beat | Only with `--confirm-cost` |
| `autofix [shot IDs] [--part P] [--rounds 2]` | **Generate → review → fix loop**: follows the reviewer's fix route on Azure (edit / face swap / recompose with the reviewer's corrections), reviews again, up to N rounds; reports the best candidate. Never approves | Only with `--confirm-cost` (total budget) |
| `voice --part 02_act_two --beat 2.2` | Narration of a beat. With `narration.cast` set (Thunderbolt: N-01, old Hamdi) it records the beat from `narration_hamdi.md` in the cast narrator's voice and performance, re-recording until speech-to-text hears it (`--tries 3`); beats marked `—` are silent. `--voices <Azure voices>` or `--script egyptian\|formal` use Azure Speech on the older scripts, one WAV per voice (`--rate -6%`) | Only with `--confirm-cost` |
| `dialogue --beat T.3 [--lines 2 4]` | Records a beat's dialogue: each line in its character's cast voice, performed to the line's intensity / volume / pace / emotion / delivery and the situation from the screenplay; speech-to-text retakes (`--tries 3`); loudness matched to the volume, children pitched, radio lines filtered → `media/.../audio/dialogue/<beat>/L<n>-<speaker>/`. `dialogue --reel` (free) joins the whole episode's narration and dialogue in story order with a cue sheet → `audio/reel/` | Only with `--confirm-cost` |
| `audition [C-02 …\|uncast]` | Voice casting: each candidate voice in `voice_cast` reads the character's calmest and most intense line (the narrator: two narration beats) into one WAV per voice; approve one in the review app (Voice casting). Without speakers: the cast table and voice clashes | Only with `--confirm-cost` |
| `lipsync --beat T.3 [--model kling-avatar-v2-pro] [--shots …]` | Talking shots (`lip_sync: "required"`): keyframe (approved, else best) + the approved takes of the lines in the shot, with a 0.4 s breath, padded to the shot length → a lip-synced clip in `clips/<part>/<shot>/<batch>-lipsync-<model>/`. Kling AI Avatar v2 Pro $0.115/s (default); `omnihuman-1.5` $0.16/s; `minimax-h3-max` $0.05/s (≥5 s audio). A beat's shots render in parallel. `lipsync --reel 01_act_one` (free) joins a part's lip-synced shots in story order with their sound → `cut/talking_<part>/`. `lipsync --recover SHOT REQUEST_ID` fetches a paid job fal finished after a time-out. `lipsync --crop SHOT… [--keep 0.76]` (free) removes the fake subtitles Kling sometimes burns into the bottom of dark shots: keeps the top of the frame, scales it back to 1920×1080 as a new `…-cropped` batch and marks the old clip rejected. Do not add "no text/subtitles" to the lip-sync prompt — it makes them more likely | Only with `--confirm-cost` |
| `animatic --part 02_act_two --beats 2.5 --voice <wav>` | Moving storyboard: each shot's keyframe (approved, else the best QA candidate) held for the shot's length with a slow push-in, cut together, narration underneath → `media/.../animatic/`. `--clips` makes a **rough cut** from each shot's video clip instead (approved, else newest; a short clip is slowed up to 1.3× then holds its last frame, a long one is trimmed; lip-synced clips are never slowed; all at 1920×1080, 24 fps) → `media/.../cut/`. `--dialogue` lays each line's take at its shot with the lip-sync timing. `--narration` lays each beat's narrator take (approved, else newest) from the beat's first shot + `--vo-start`. `--ambience` adds a soft temporary wind bed | No (ffmpeg, local) |

Options for `generate`: `--tier draft|final`, `--variants N`, `--model image_ultra` (or `ultra`, anchors only), `--allow-similar` (anchors only), `--only KEY…` (training-set), `--steps N` (lora; price scales with steps), `--confirm-cost USD`, `--production <series/episode>`.

## Actor face models (LoRA) — how it works

1. **Anchor** — one approved portrait defines the face (`generate anchors`, then approve in `review`).
2. **Training set** — `generate training-set` asks FLUX.1 Kontext [pro] to redraw the same person 20 ways, following the studio recipe in `library/actors/training_set.json`. Each image gets a caption file (`photo of <trigger>, <what changed>`). Captions describe only what changes, so the face binds to the trigger word. Recipe v1.2 rule: at least 3 of 4 photos change the outfit, and at least 4 are action poses. Otherwise the anchor clothes and portrait framing get learned as part of the face. The Karim pilot (v1.1) showed exactly that: his anchor scarf appeared in every shot.
3. **Curate** — in `review`, training images show **Kept / Rejected** buttons. Reject any image where the face drifted. At least 10 must be kept. Rejections are saved in `rejected.json`.
4. **Train** — `generate lora` zips the kept images (+ the anchor unless `anchor.use_in_training` is false), uploads them to fal.ai storage (expires after 7 days; local copies stay), and runs `fal-ai/flux-lora-fast-training`. The weights are downloaded to `…/lora/<batch>/<trigger>.safetensors`, and the actor card gets `status: lora_trained` plus `lora.url`, `lora.media_path`, `lora.version`.
5. **Test** — `generate lora-tests` renders 3 real solo shots from the episode. Approve one to sign off, then the card moves to `locked`. A locked actor can't get new anchors, training images or a new face model (the engine refuses); to change one, set the status back to `lora_trained` and note why.
6. **Use** — keyframes with trained characters switch to `image_lora` (`fal-ai/flux-lora`) and send each character's face model. If a stored model URL has expired, the engine re-uploads the local copy. `--lora-scale 0.8` loosens the face model's hold on pose and clothing for one batch.

Known limits (from the 10-actor run):
- **Face bleed in group shots — solved by the face pass.** Shots with `extras` (or `"group": true`) are rendered in two steps: (1) the picture *without* face models — the lead is described only by age, skin, build, hair, beard, rank and gear, so extras keep their own faces; (2) a **face pass** (`mtower/faces.py`, `tools/Face-Patch.ps1`):
  - **Find:** Moondream finds every face (`face_detect`, $0.02; it found all 6 in a sunlit group where Florence-2 found none). If it finds too few, Florence-2's "find: human face" mode (`face_detect_fallback`, ≈$0.005) adds its single best guess.
  - **Close-up:** a square about 2.6× the lead's face is cut out and enlarged to 960×960. At full-frame size a 40–100 px face is too small, and the model invents blobs or re-poses the head.
  - **Repaint:** `fal-ai/flux-lora/inpainting` repaints only the face ellipse with the actor's face model ($0.035). The prompt covers the face, expression and light only, with no clothes or kit.
  - **Blend:** the close-up is shrunk back and blended in with a soft edge.

  The untouched picture is kept in `base/` with a `.faces.json` (all faces + the chosen one) and the repainted close-up (`*.patch.png`). Which face: `vision` by default (since 2026-10-15) — when there are more faces than characters, or several characters, `qa.identify_faces()` draws numbered boxes on the picture and the Azure reviewer (≈$0.008) matches each character to a box from the shot design and each character's role, rank and action; a character it cannot see gets no face and is skipped (falls back to `largest` if the call fails). Or set `"lead_face": "vision|largest|center|smallest|left|right"` on the shot. Optional shot fields: `"face"` (the expression to keep, e.g. a strained grimace — face models trained on calm portraits drift toward neutral) and `"face_strength"` (default 0.88; ~0.75 keeps more of the original expression and head angle). If no face is found, the base picture is kept and flagged — review it. If a pass fails partway, what was already spent is still recorded in the ledger.
- **Headscarf.** Kontext tends to drop a woman's headscarf when it changes her outfit. For actors whose `traits.hair` starts with `covered`, training edits and captions now ask to keep the headscarf.
- **Network.** The fal client retries status checks and downloads on network errors. It never retries a submit, so you are never billed twice.
- **Safety filter.** Kontext sometimes returns a black frame (e.g. grenades at night). The engine auto-rejects any image flagged by the provider (`has_nsfw_concepts`) so it never reaches a training set.

## Prop models (LoRA) — weapons that look right

Text alone gets rare weapons wrong (the Malyutka came out as an artillery shell). Props get their own small model, trained the same way as faces:

1. **References** — put real photos in `media/library/props/<PRP-ID>_<slug>/references/` (crop away borders and rounded corners). Optional on the card: `training_note` (e.g. the right paint colour, appended to every edit), `train_references` (which photos also go into training — leave out one with the wrong paint), `training_actions` (prop-specific poses, e.g. RPG held between the knees).
2. **Training set** — `generate training-set PRP-0003` makes ~12–15 Kontext edits from the recipe in `library/props/training_set.json` (plain views, sand/salt/night/dusk, dug-in, a soldier for scale). Review and reject; at least 10 must be kept.
3. **Train** — `generate lora PRP-0003` (~$2). The card gets `status: lora_trained` and `lora.*`. `create_masks` is off for props (it is a face feature).
4. **Use** — any shot listing the prop in `assets` sends its model with `lora.scale` from the card (RPG-7 0.8, Malyutka 0.9, RKG-3 0.7 — small props at full strength take over the frame) and puts the trigger in front of the prop's text.

Open issues: FLUX still often drops props mentioned only in the prompt in crowded group shots, and an actor model plus a prop model at full strength in one solo shot can lose the scene. Both T.2-01 and 2.6-02 were solved via ChatGPT + face pass (below), which is now the recommended route for complex compositions.

## Hard shots via Azure (automatic) — the default route

Since 2026-10-12 the studio's Azure Foundry resource (`studio/infra/`) runs the OpenAI image model the ChatGPT route used by hand. `generate composition <shots>` does the whole route in one batch:

1. **Composition** (`image_compose` → deployment `me-eus2-gpt-image-2`): the same body-only prompt as `prompt --chatgpt` (no trigger words), plus the props' reference photos (e.g. the Malyutka) through the edits endpoint, at exactly 1280×720. The SPN signs in with Entra ID (no keys).
2. **Face pass** on the new batch, chained automatically. Since 2026-10-13 (decision D-15) adults get the **Azure face swap** (`face_swap`): Moondream finds the lead's face (cached in `base/<image>.faces.json`, so a re-run is free), a tight ellipse mask (1.25 × 1.35 of the face box) is drawn, and gpt-image-2 repaints only that area with the actor's approved anchor portrait as image 2 and the `FACE_SWAP` rules (same head size, angle, gaze and scene light; don't copy the portrait's light or pose). It fixed what the fal inpaint did on 2.5-07 (head enlarged, turned to the camera, lit warm), for about $0.045 per face. Children keep the fal LoRA inpaint (gpt-image refuses minors); a shot can force it with `"face_method": "fal"`, or engine-wide with `face_pass.method` in `engine_config.json`. Use the shot field `face` (expression/pose to keep). Set `"face_pass": false` on shots where no face is visible (e.g. a back view); the prompt then asks for no visible face. The swap keeps the head exactly as composed (no helmet, cap or headset is added) and, for bare-headed wardrobe, says the short black hair stays visible. **INSERT** shots may list characters: they are drawn as hands and forearms only (face outside the frame), get no face pass, and the reviewer does not ask for a face. Shots with a child among the cast, extras or prompt go to FLUX Kontext on Azure (`image_compose_flux`), since gpt-image refuses minors. **Written text:** gpt-image writes legible Arabic religious phrases on letters; the production's `qa.rules` reject any Quran verse or Basmala in frame (global no-Quran rule), so describe handwriting as soft, unreadable texture (see PRP-0010 and shot 1.3-05).

**Natural-look controls** (`library/looks/looks.json` → `realism`, `realism_triggers`): the composer adds them by itself — `NATURAL_HUMAN` (head life-size for the body, ~7.5 heads tall, shoulders ~3 heads wide, head centred on the neck, face lit by the scene's light, nobody looks into the lens unless asked, five fingers) to every shot with people; `NATURAL_CHILD`, `NATURAL_GROUP` (perspective, feet on the ground, no merged or repeated people), `NATURAL_ANIMAL` / `NATURAL_BIRD` when the shot names one (word lists in `realism_triggers`; "kite" is excluded on purpose), `NATURAL_HANDS` to hand inserts, `SCALE_RULES` to every non-insert shot, and `MOTION_NATURAL` to every motion prompt. Video models that take a negative prompt also get the `AVOID_ANATOMY` list. Locations can carry `qa_rules` (e.g. LOC-0003: the marsh is mostly shin-deep, never above the knee), which the QA reviewer enforces.

Shot field `"kit": {"C-06": "..."}` replaces a character's `character_additions` (props and signatures from `casting.json`) for that one shot — e.g. Adel holding a grenade instead of his Malyutka control box. A wardrobe's `field_kit` (webbing, magazines, canteen) is left out in the off-duty wear states listed in `wardrobe.json` (`WEAR_POSTWAR`).

Cost: estimates use per-image ceilings ($0.02 / $0.08 / $0.30 for low / medium / high, +$0.03 per reference photo); the ledger records the **actual** cost from the token usage Azure returns (about $0.03 per medium 1280×720 image in the first runs). Azure spending has its own monthly limit.

`--actor-refs` attaches the lead's approved anchor portrait so gpt-image draws his face directly, with no face pass. It gave the most natural likeness in the first test (3.13-01), but Azure's safety system rejected it when the shot also carried a weapon reference photo (1.6-03); rejected requests aren't billed. Use it for shots without prop reference photos, and fall back to the face pass otherwise.

**Children:** Azure gpt-image-2 and gpt-image-2.5-flare (output moderation) and FLUX.2-pro (`stop_reason: refusal`) refuse every photorealistic child (even "a boy flying a kite on a beach"; tested 2026-10-12). **FLUX.1 Kontext pro** on the same Foundry (`image_compose_flux` → `me-eus2-flux-kontext-pro`, `safety_tolerance` 5, $0.04) doesn't, so `generate composition` sends shots whose cast includes a child (actor `apparent_age` under 16) there automatically:

- **Short prompt** (`PromptComposer.flux_prompt`): look + shot prompt + body + extras + lens. The long ChatGPT-style prompt made Kontext age the children up, mix in the location's other places, and drop costume details — so the shot prompt itself must say where we are.
- **Casting photo as input image**: when the shot has one lead with an approved anchor, Kontext gets that portrait and keeps the child's face, so no face pass follows (better likeness than the face pass, and right age and skin tone). Otherwise it composes from text and the face pass adds the face.
- No prop reference photos on this route. Kontext occasionally refuses a child shot at random; re-run it (refusals aren't recorded as spend).
- Say "not looking at the camera" in the shot prompt when the child must look elsewhere: with a casting photo, Kontext tends to face the lens.

The ChatGPT route below remains the manual fallback.

## Image QA — a second path that checks every picture

Generation and review are separate paths. `qa` sends each image to a reviewer model on Azure (`qa_review` → `me-eus2-gpt-5-6-sol`, decision D-16) together with:

- the shot's **design** in plain words: shot size, lens, move, the action and what happens next, each character (role, face, wardrobe, kit), extras, props and vehicles, the location and its `qa_rules`, the look and wear state, the director's design notes, and any note left on the image in the gallery;
- the production's **period and culture rules** (`production_config.json` → `qa`);
- **reference images**: each visible lead's casting portrait (identity check) and up to two real reference photos per prop.

The rubric (in `mtower/qa.py`) makes it first *measure* every visible person (head widths across the shoulders, neck, head on neck, face light vs. the scene, gaze), then check 11 categories: design match, anatomy & proportions, face integration, identity, period accuracy, props & weapons, physics & scale, location rules, lighting, technical artifacts, culture & safety. It answers in strict JSON: verdict (pass / minor / fail), score 0–10, a note per category, issues with severity and a concrete fix, and the cheapest **fix route** — `keep`, `edit` (with a ready edit instruction), `face_swap`, `recompose`, or `new_prompt`.

`autofix` closes the loop: it follows the route on Azure (Kontext edit, a new face swap from the untouched base, or a new composition with the reviewer's fixes added as "corrections from the last review"), reviews the new image, and stops at score 8+ or after `--rounds`. It never approves — the best candidate waits for the director in the gallery, with its QA verdict on the card. First full run (2026-10-13): the reviewer failed 28 of the 32 approved keyframes, mostly for design mismatches, warm or camera-facing faces from the old fal face pass, lighting, and props; 2.5-07 went from 3/10 to 9/10 in one round ($0.20). Across the episode, two rounds lifted most shots by 1–2 points; simple shots reach 8–9, crowded compositions (T.2-01, 3.2-02, 4.5-03) plateau at 5–6 and need a director's rewrite of the shot design. Azure's safety system rejects a few face swaps on battle shots (3.4-05, 5.4-05); those keep the base face and are flagged by the review.

`qa --report` also writes `media/productions/<prod>/qa_compare.html`: per shot, the approved keyframe next to the best-scoring candidate with both verdicts — the sign-off sheet after an autofix run.

## Narration takes (Azure Speech)

`voice --part 02_act_two --beat 2.5` renders one 48 kHz WAV per voice at a slightly slower documentary pace, with pauses at sentence ends and ellipses. The text comes from the production's narration script when `production_config.json` → `narration.script` is set (Thunderbolt: `egyptian` → `03_production/voice/narration_egyptian.md`, everyday Egyptian Arabic, voices `ar-EG-ShakirNeural` / `ar-EG-SalmaNeural`); `--script formal` reads the screenplay's diacritized formal VO instead (engine default voices `ar-AE-Rashid:DragonHDLatestNeural`, `ar-EG-ShakirNeural`, `ar-SA-HamedNeural`). Billed per character (about $0.005 per beat per voice). `check` fails if a beat with screenplay VO has no section in the narration script. ElevenLabs remains the planned final narrator.

**Listen-back check:** `voice --check` (optionally `--part` / `--beat`) sends each beat's newest takes to Azure speech-to-text (ar-EG) and compares what was heard with the text the take was made from; it prints a match score and any script phrase that was not heard, and saves `<take>.check.json`. About $0.0003 per second (≈ $0.25 for the whole episode). The recognizer's own spelling (e.g. «تالات», digits for numbers) lowers the score without being an error, so treat ✗ as "listen to this one". Pronunciation rule found this way: write numbers and «صاعقة» without diacritics in the Egyptian script — fully diacritized numbers were sometimes swallowed.

## Acted dialogue and voice casting (D-20, D-21)

The series is drama first: characters carry the scenes, and **every voice must match the situation**. Three pieces make that repeatable:

1. **Cast** — `production_config.json` → `voice_cast`: one entry per speaker (persona, language `egyptian`/`msa`/`hebrew`, and either a fixed `engine` + `voice` or `candidates` to audition; `pitch` > 1 for children; `engine: group` for a murmur of several voices). `audition` records candidates; the approved audition in the review app becomes the voice.
2. **Performance** — each `dialogue_refs` line in the shot lists: `intensity` 1–10, `volume` (whisper · low · normal · raised · shout), `pace` (slow · measured · normal · quick · rushed), `emotion`, `delivery`, optional `fx: "radio"` and `situation`. `check` validates them and warns when two characters who speak in the same beat share a voice.
3. **Direction** — `dialogue` builds the instructions for gpt-audio-1.5 (`mtower/dialogue.py` → `direction`): dialect rule → persona → the screenplay's scene heading, environment and the action before the line → delivery, emotion, intensity (with words: at 6+ "never relaxed or casual"), volume and pace. The text is read without vowel marks (they push the models toward formal Arabic) but with shadda. Every take goes through Azure speech-to-text (ar-EG or he-IL) and is re-recorded until it hears the line (match ≥ 0.7, nothing missing; best of `--tries`), then loudness-matched to its volume (whisper −27 … shout −16 LUFS), pitched and filtered.

Cost: gpt-audio-1.5 is token-billed; the engine computes each take's actual cost from the response usage (about $0.01–0.03 per line with retakes). Narration with `narration.cast` uses the same path (`voice --part --beat`): the beat's performance is a `<!-- intensity: 7; volume: low; ... -->` comment in `narration_hamdi.md`. The full guide for directors: `productions/thunderbolt/ep01_romani/03_production/voice/performance_guide.md`.

## Hard shots via ChatGPT (manual fallback, covered by a ChatGPT subscription)

ChatGPT's image generator follows complex compositions and attached reference photos better than FLUX, but it has no API on the subscription and can't use our face models. So it makes the picture, and the engine adds the actors' faces:

1. `prompt --shot T.2-01 --chatgpt` prints a paste-ready prompt (no trigger words; leads described by body only) and the prop reference photos to attach.
2. Save ChatGPT's image to `media/inbox/T.2-01.png` (several takes: `T.2-01 b.png`, …).
3. `import` (free) crops/resizes to 1280×720 into a new keyframe batch, keeps the original in `original/`, and empties the inbox.
4. `generate face-pass T.2-01` (≈$0.04 per image, dry run first; `--lead-face` to choose the face) repaints only the cast's faces with their face models. Re-runs start from the untouched picture in `base/`.

## Keeping virtual actors distinct

Image models drift toward one "default" face, so a roster can end up looking like siblings. Three controls prevent that:

1. **Trait cards.** Every actor in `library/actors/actors.json` has structured `traits` (face shape, nose, eyes, eye colour, eyebrows, jaw, hair, facial hair, skin tone, build) chosen from `trait_vocabulary`. Each trait must also appear in `face_and_body`, because that text is all the image model sees.
2. **`cast-check` gate.** Actors of the same gender and age group (adult/child, within 12 years) are compared. 4 shared traits = warning; 5+ = `generate anchors` refuses until a card is changed. Family members (`family_resemblance` naming each other) are exempt. Use `cast-check --coverage` when adding an actor to pick unused traits.
3. **Side-by-side review.** The gallery pins the approved roster above new candidates. The anchor prompt also asks for an ordinary unretouched face, no makeup/face paint, no insignia, and no text.

## Where things go

- **Generated media:** `MTOWER_MEDIA_ROOT` (default `./media`, git-ignored), mirroring the library and productions:
  `library/actors/ACT-0003_karim-nour/anchor/<batch>/…` · `productions/thunderbolt/ep01_romani/keyframes/<part>/<shot>/<batch>/…`
- Each batch folder has a `manifest.json` (prompt, model, seed, request ID, cost) and, once you approve, `approved.json`.

## Files

| File | Purpose |
|---|---|
| `mtower.ps1` | Launcher |
| `engine_config.json` | Providers, model IDs, payload defaults, **prices (verify before use)**, default limits |
| `mtower/settings.py` | Paths, `.env` loading, media root |
| `mtower/library.py` | Loads the studio library catalogs and look blocks |
| `mtower/production.py` | Loads a production; reads narration and dialogue from the screenplay |
| `mtower/prompts.py` | Composes image/motion prompts from looks + actor + wardrobe + wear state + shot |
| `mtower/costs.py` | Estimates, limits, confirmation, ledger |
| `mtower/jobs.py` | Plans and runs batches (anchors, training sets, LoRAs, plates, keyframes with face pass, clips) |
| `mtower/faces.py` | Face pass helpers: pick the lead's face, close-up square, inpainting and alpha edit masks (stdlib PNG), the face size/place check |
| `tools/Face-Patch.ps1` | Face pass: crop/enlarge the face square and blend the repainted close-up back (System.Drawing) |
| `mtower/qa.py` | Vision QA: design brief + references → strict JSON verdict per image; Markdown report |
| `mtower/autofix.py` | The generate → review → fix loop |
| `mtower/voice.py` | Narration takes with Azure Speech; narration scripts; speech-to-text listen-back check |
| `mtower/dialogue.py` | Voice cast, line performances, acting direction, gpt-audio / mini-tts / Azure Speech takes with speech-to-text retakes, auditions, cast narrator, lip-sync, dialogue track for the cut |
| `mtower/casting.py` | Roster distinctness checks (traits, look-alike pairs, coverage) |
| `mtower/gallery.py` | Local review gallery |
| `mtower/providers/` | fal.ai queue client and storage upload; Azure Foundry client (Entra ID sign-in, gpt-image generate/edit, actual cost from token usage); ElevenLabs text-to-speech client |
| `tools/Test-ShotList.ps1` | Shot-list validator (PowerShell) |
| `tools/Fit-Image.ps1` | Center-crop + resize an image to 1280×720 (used by `import`) |
| `tests/` | Unit tests: `python -m unittest discover -s tests` with `PYTHONPATH` set to this folder |

## Roadmap

- **v1 (done):** prompts, cost control, image batches, clip batches, review gallery, ledger, roster distinctness checks.
- **v1.1 (built, task 2.4):** LoRA training sets (Kontext reference editing), curation, LoRA training, LoRA tests, face models in keyframes.
- **v1.2 (built 2026-10-13):** Azure face swap, natural-look controls, vision QA + autofix loop, Azure Speech narration takes.
- **v1.3 (task 2.6):** animatic assembly (keyframes + narration + temp sound).
- **v1.4 (Phase 3):** timeline export for DaVinci Resolve; subtitles.
