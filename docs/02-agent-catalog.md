# 02 — Agent Catalog

**Status:** draft, 2026-10-14. The full crew, designed up front; deployed in waves (see the Wave column). Each entry is written so the agent can be implemented from it without re-reading the vision. Every agent reads and writes the **shot contract** ([03-orchestration.md](03-orchestration.md)); none call each other directly.

## Conventions

- Every agent obeys the **standing studio rules** and is built from the **four competence layers** (L1 Persona · L2 Knowledge · L3 Tools · L4 Collaborators) defined in [06-agent-competence-model.md](06-agent-competence-model.md). In particular, **every output of every agent passes the validation gate** (reviewer ≠ author).
- **Reads / Writes** are fields of the shot contract (or library catalogs).
- **Model** is a starting recommendation — cheap text model unless the role needs vision or generation.
- **DoD** = definition of done: the condition the orchestrator checks before the shot advances.
- **Wave**: 1 = prove the loop, 2 = creative crew, 3 = finishing crew.

---

## The crew at a glance

| # | Agent | One-line craft | Model class | Wave |
|---|---|---|---|---|
| 0 | **Orchestrator** | Runs the board; assigns work, enforces gates | text (reasoning) | 1 |
| 1 | **Script / Scenario** | Beat → shot intent; dialogue & VO text | text (reasoning) | 1 |
| 2 | **Research / Fact-check** | Historical & technical truth, 1967–1973 | text + web | 1 |
| 3 | **Quality (QA)** | Validates every image vs its intent | **vision** | 1 |
| 4 | **Casting** | Characters → library actors, distinctness | text | 2 |
| 5 | **Wardrobe** | Costume + wear state per character/shot | text (+vision check) | 2 |
| 6 | **Set decoration** | Location dressing, interior/exterior, period props placement | text (+vision check) | 2 |
| 7 | **Camera / DoP** | Framing, lens, movement, light, format | text | 2 |
| 8 | **Egyptian-Arabic specialist** | Dialect, slang, diacritics, delivery notes | text + Speech | 3 |
| 9 | **VFX / Effects** | Explosions, smoke, tracers, weather, damage | text (+vision check) | 3 |
| 10 | **Continuity** | Cross-shot consistency (time, blood, props, light) | **vision** | 3 |
| 11 | **Sound / Voice** | Narration, dialogue, SFX, music briefs | text + Speech/tts | 3 |

> The orchestrator (0) is the coordinator, not a craft specialist; it is listed here for completeness and detailed in [03-orchestration.md](03-orchestration.md).

---

## Wave 1 — prove the loop

### 1. Script / Scenario agent
- **Craft:** turn a locked screenplay beat into a precise, filmable **shot intent** — subject, action, blocking, emotional note — and own the dialogue/VO text (Egyptian Arabic draft, formal VO as meaning source).
- **Reads:** `beat_ref`, screenplay, series bible, episode plan.
- **Writes:** `shot.intent` (structured), `shot.dialogue[]`, `shot.vo`.
- **Tools:** screenplay reader (engine), library ID lookup (to reference, not duplicate).
- **Model:** text reasoning.
- **DoD:** shot intent names subject, action, setting, time-of-day, mood, and references library IDs for any location/vehicle/prop/character; no invented facts (hands off to Research for anything historical).
- **Guardrails:** never generates media; never alters a locked script — proposes change-log entries only.

### 2. Research / Fact-check agent
- **Craft:** guarantee historical and technical truth for 1967–1973 Egyptian/Israeli operations — uniforms, gear, weapons, vehicles, locations, timeline, cultural detail.
- **Reads:** `shot.intent`, episode research notes, `beat_ref`.
- **Writes:** `shot.research[]` (claims with sources + verdict), `shot.flags[]` (anachronism/risk).
- **Tools:** web search, episode fact-check docs, library catalogs (to confirm period-correct assets exist).
- **Model:** text reasoning + web.
- **DoD:** every period-sensitive element in the shot intent is marked verified / corrected / flagged, with a source; no unresolved anachronism flags remain open when the shot reaches generation.
- **Guardrails:** real people only through sourced actions (series rule); cites sources, never asserts from memory alone.

### 3. Quality (QA) agent
- **Craft:** the role that started this whole idea — check every generated image against its shot intent for anatomy, identity, period accuracy, props, physics, and light; return pass/fail with actionable fixes.
- **Reads:** candidate image, `shot.intent`, `shot.wardrobe`, `shot.cast`, library review lists.
- **Writes:** `shot.qa` = `{score, verdict, issues[], fix_instructions[]}`.
- **Tools:** vision model, the existing `qa` / `autofix` logic, face-detection boxes.
- **Model:** **vision** (gpt-5.6-sol, MTower D-16).
- **DoD:** image scored against the rubric; verdict ≥ gate → pass; else fail with specific, regenerable fix instructions (bounded to N autofix rounds before escalating to a human).
- **Guardrails:** "measure the people first" structured pass before judgement (MTower lesson); never approves — only scores; human still signs off at the gallery gate.

---

## Wave 2 — the creative crew

### 4. Casting agent
- **Craft:** map each character in a shot to a **library actor**, honoring one-role-per-actor-per-series, locked stand-ins for real people, and roster distinctness.
- **Reads:** `shot.intent.characters[]`, `casting.json`, `actors.json`.
- **Writes:** `shot.cast[]` = `{character_id, actor_id, face_model}`.
- **Tools:** library resolver, `cast-check` distinctness, casting.json.
- **Model:** text.
- **DoD:** every character resolves to a locked actor with a trained face model (or an explicit "anchor-only / free" note); no distinctness collision; real-person stand-ins never recast.
- **Guardrails:** library-first; refuses to invent an actor when a suitable one exists; flags when a new actor/anchor is genuinely needed (human approves).

### 5. Wardrobe agent
- **Craft:** choose the costume and **wear state** (clean/muddy/bloodied/wet) per character per shot, period-correct and continuity-aware.
- **Reads:** `shot.intent`, `shot.cast`, `wardrobe.json`, `shot.continuity` (prior wear state).
- **Writes:** `shot.wardrobe[]` = `{character_id, wardrobe_id, wear_state}`.
- **Tools:** library resolver, optional vision check on the candidate.
- **Model:** text; optional vision for the post-gen check.
- **DoD:** each cast character has a resolved wardrobe ID + wear state consistent with the scene and with continuity; covered-hair actors keep their headscarf (MTower training rule).
- **Guardrails:** period accuracy (1967–1973 uniforms/gear); escalates missing wardrobe assets rather than improvising anachronisms.

### 6. Set decoration agent
- **Craft:** dress the location — interiors (rooms, furniture, props placement) and exteriors (streets, buildings, signage, vehicles), period-correct and plausible.
- **Reads:** `shot.intent`, `locations.json`, `vehicles.json`, `props.json`, `shot.research`.
- **Writes:** `shot.set` = `{location_id, dressing[], vehicles[], props[]}`.
- **Tools:** library resolver, vision check.
- **Model:** text; optional vision.
- **DoD:** location resolves to a library LOC; all placed vehicles/props are library IDs, period-correct, and physically plausible for the blocking; no anachronistic signage/objects.
- **Guardrails:** library-first; flags crowded-group-shot prop risks (MTower open issue) for the camera/VFX agents.

### 7. Camera / DoP agent
- **Craft:** decide framing, lens, camera movement, lighting, and output format per shot, consistent with the production's look.
- **Reads:** `shot.intent`, `looks.json`, `visual_guide.md`, `shot.set`.
- **Writes:** `shot.camera` = `{shot_size, lens, movement, light, look_key, format}`.
- **Tools:** looks catalog, visual guide.
- **Model:** text.
- **DoD:** shot has a resolved look key + camera spec that matches the series visual guide and the beat's emotional note; night/dark shots carry an explicit exposure note (MTower open issue).
- **Guardrails:** references `looks.json` keys, never duplicates look wording into the shot.

---

## Wave 3 — the finishing crew

### 8. Egyptian-Arabic specialist agent
- **Craft:** master of Egyptian everyday Arabic and slang — adapt VO/dialogue into natural dialect with **full diacritics (التشكيل الكامل)** and delivery/acting notes; verify pronunciation.
- **Reads:** `shot.vo`, `shot.dialogue[]`, `narration_egyptian.md`, D-19/D-20 direction.
- **Writes:** `shot.dialogue[].egyptian`, `shot.vo.egyptian`, `shot.voice_notes`.
- **Tools:** Azure Speech (render + `voice --check` speech-to-text verification), tts/audio models.
- **Model:** text + Speech.
- **DoD:** every spoken line has an Egyptian-dialect version with full diacritics and an acting note; a speech-to-text check round-trips to the intended meaning.
- **Guardrails:** formal screenplay VO remains the meaning source of truth; dialect changes wording, not meaning.

### 9. VFX / Effects agent
- **Craft:** specify effects — explosions, muzzle flash, tracers, smoke, dust, water, weather, vehicle/structure damage — restrained and period-plausible.
- **Reads:** `shot.intent`, `shot.set`, `shot.research`.
- **Writes:** `shot.vfx[]` = `{effect, intensity, placement, timing}`.
- **Tools:** vision check on candidates; references props/vehicles for consistent damage.
- **Model:** text; optional vision.
- **DoD:** effects are specified with intensity + placement, consistent with physics and the restrained-violence series rule; no effect contradicts the research flags.
- **Guardrails:** restrained violence (series bible); flags shots where effects + actor/prop models together risk losing the scene (MTower open issue).

### 10. Continuity agent
- **Craft:** enforce consistency **across** shots within a scene/sequence — time of day, light direction, wear state, injuries, prop positions, who-holds-what.
- **Reads:** this shot + neighboring shots' contracts in the same beat/scene.
- **Writes:** `shot.continuity` = `{prior_state_ref, deltas[], violations[]}`.
- **Tools:** vision (compare frames), contract store queries.
- **Model:** **vision**.
- **DoD:** no unexplained continuity violation vs adjacent approved shots; any intentional change (e.g. a wound appearing) is recorded as a delta, not a violation.
- **Guardrails:** read-only on other agents' fields; raises violations for the orchestrator to route, never edits another craft's decision.

### 11. Sound / Voice agent
- **Craft:** own the audio brief per shot/beat — narration takes, dialogue delivery, SFX list, and music cues; coordinate renders.
- **Reads:** `shot.vo`, `shot.dialogue[]`, `shot.voice_notes`, beat timing.
- **Writes:** `shot.audio` = `{narration_take, dialogue_takes[], sfx[], music_cue}`.
- **Tools:** Azure Speech / tts / gpt-audio, engine `voice`/`animatic`, ledger.
- **Model:** text + Speech/audio.
- **DoD:** each narrated/spoken beat has a rendered take that passes the listen-back check; SFX and music cues are listed for the edit; costs logged.
- **Guardrails:** drafts on Azure Speech; ElevenLabs remains the planned final narrator (D-19); no premium render without a cost gate.

---

## Notes on crew size

Start from these 12 and adjust after review:
- **Mergeable** if we want a leaner Wave 2: Wardrobe + Set + VFX could begin as one **"Art Department"** agent and split later.
- **Possibly split** if load grows: Script could split into **Scenario (structure)** vs **Dialogue (lines)**.
- **Editor / Timeline** and **Marketing/Poster** agents exist implicitly in MTower (`animatic`, marketing drafts) — add as a Wave 3+ role if the orchestrator needs them as first-class crew.

The orchestrator does not need the full crew to be useful — Wave 1 (Orchestrator + Script + Research + QA) already closes the generate → validate → regenerate loop end to end.
