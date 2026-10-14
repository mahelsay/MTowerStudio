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
| 1 | **Script / Scenario** | Scenario, scene detail & dialogue meaning (within the locked story) | text (reasoning) | 1 |
| 1b | **Director** | Creative lead: coverage/shot breakdown, blocking, performance, tone | text (reasoning) | 1 |
| 2 | **Research / Fact-check** | Universal fact desk: history, geography, places, culture, technical | text + web | 1 |
| 3 | **Image QA** | Vision review of every generated image vs intent | **vision** | 1 |
| 3b | **Studio Critic** | Tier-2 review of every non-image decision (studio-wide) | text (reasoning) | 1 |
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
- **Craft:** write the **scenario** within the locked story — scene detail (subject, action, blocking, emotional note) and the **dialogue/VO meaning** (formal VO as meaning source; Egyptian dialect pass belongs to Agent 8). Does **not** decide shot count/coverage — that's the Director.
- **Reads:** `beat_ref`, screenplay, series bible, episode plan, grounding/tone bible.
- **Writes:** `shot.intent` (scene detail), `shot.dialogue[]`, `shot.vo`.
- **Tools:** screenplay reader (engine), library ID lookup (to reference, not duplicate), change-log writer.
- **Model:** text reasoning.
- **DoD:** scene intent names subject, action, setting, time-of-day, mood, and references library IDs for any location/vehicle/prop/character; no invented facts (hands off to Research); consistent with the tone bible.
- **Guardrails:** never generates media; never alters a locked script — proposes change-log entries only.
- **Competence (L1–L4):** L1 master screenwriter + genre mastery (drama/action/thriller/historical); L2 series bible + episode research + 1967–73 Egypt grounding pack; L3 screenplay reader, library lookup, change-log; L4 Research (facts), Egyptian-Arabic (dialect), Director (coverage), Continuity.

### 1b. Director agent
- **Craft:** the creative lead. Turns the scenario into **visual storytelling**: decides **coverage** (how many shots a beat becomes and from where), **blocking**, **performance intent**, **pacing**, and the **tone** each scene must hit. Sets the creative north star; distinct from the Orchestrator (logistics) and the Camera/DoP (executes framing/lens/light per shot).
- **Reads:** `shot.intent`, screenplay, series bible, `visual_guide.md`, `looks.json`, the **grounding/tone bible** (reference pull).
- **Writes:** the **shot breakdown** for a beat (the set of shots), and per shot `shot.direction` = `{coverage, blocking, performance_note, pacing, tone_ref}`.
- **Tools:** screenplay reader, library + looks lookup, grounding/tone-bible retrieval.
- **Model:** text reasoning (strong).
- **DoD:** every beat is decomposed into shots, each with coverage + blocking + a performance note + a tone reference, consistent with the visual guide and the tone bible; no shot lacks a stated intent.
- **Guardrails:** works within the locked script (coverage, not story changes); references look keys and tone-bible entries rather than re-describing them; hands per-shot framing/lens/light to Camera/DoP.
- **Competence (L1–L4):** L1 veteran director, film-school trained, master of visual storytelling and genre tone; L2 series bible + visual guide + **tone bible** (the user's reference pull: films, series, footage, stills); L3 screenplay reader, library/looks lookup, tone-bible retrieval; L4 Script (scenario), Camera/DoP (execution), Research (facts), Continuity, all craft agents.

### 2. Research / Fact-check agent
- **Craft:** the studio's **universal fact desk** — guarantees the truth of *everything real*, not just history: historical events & timeline; **geography** (countries, cities, neighborhoods, terrain, climate, distances); period & present-day **places**; **culture, society, religion, customs**; language context; **technical/military** detail (weapons, vehicles, gear, radios, tactics); logistics and plausibility. Catches errors before they cost money at generation.
- **Reads:** `shot.intent`, `shot.direction`, episode research notes, `beat_ref`, Tone Bible factual corpus.
- **Writes:** `shot.research[]` (claims with **source + tier + verdict**), `shot.flags[]` (anachronism / inaccuracy / unverifiable / sensitivity).
- **Tools:** web search, fact-check documents, Tone Bible retrieval, library catalogs (confirm a correct asset already exists).
- **Model:** text reasoning + web.
- **Decisions (locked 2026-10-14):**
  - **Strictness = block.** Anything unverifiable is flagged and **no paid generation runs while a flag is open** (orchestrator-enforced).
  - **Tiered sourcing:** primary/archival > reputable secondary > weak. Weak-only sources are auto-flagged for the user's review.
  - **Human expert gate:** sensitive real-people and combat facts escalate to the user as final authority before being treated as settled.
- **DoD:** every real-world element in the shot (historical, geographic, cultural, technical) is marked verified/corrected/flagged **with a sourced tier**; no unresolved flag remains open at generation.
- **Guardrails:** real people only through sourced actions (series rule); **never asserts from memory alone** — a claim without a citation is a flag, not a fact.
- **Competence (L1–L4):** L1 lead researcher backed by specialist advisor hats (historian · geographer · military/technical advisor · cultural consultant), rigorous and source-citing; L2 Tone Bible factual corpus + episode fact-check docs + series bible, with live web for anything ungrounded; L3 web search, fact-check docs, Tone Bible + library lookup; L4 Script & Director (what to check), Set/Wardrobe/VFX (consume verdicts), Egyptian-Arabic (language/slang authenticity).

### 3. Image QA agent (vision reviewer)
- **Craft:** the role that started this whole idea — the independent **vision** check on every generated image against its shot intent: anatomy, identity, period accuracy, props, physics, light, and tone; returns a score + actionable fixes. Catches what the generator rationalizes, before the human sees it and before money is spent animating it.
- **Rubric:** anatomy · **identity (face match to the cast actor's model/anchor)** · period accuracy · props & continuity · physics/plausibility · light · intent & tone (vs the Director's `tone_ref`/look key).
- **Reads:** candidate image, `shot.intent`, `shot.direction`, `shot.wardrobe`, `shot.cast` (+ actor anchor), `shot.set`, library review lists, period grounding.
- **Writes:** `shot.qa` = `{score, verdict, issues[], fix_instructions[], rounds}`.
- **Tools:** vision model, the existing `qa` / `autofix` logic, face-detection boxes, the cast actor's anchor portrait for identity match.
- **Model:** **vision** (gpt-5.6-sol, MTower D-16).
- **Decisions (locked 2026-10-14):**
  - **Gate score = 8/10** default; **hero/key shots may demand a higher bar (e.g. 9)**.
  - **Autofix bounded to 2 rounds**, then escalate to the user.
  - **Identity is non-negotiable:** a **face-match failure is an automatic fail** regardless of overall score.
- **DoD:** image scored on the full rubric; verdict ≥ gate **and** identity passes → **pass** (to human approval); else **fail** with specific, regenerable fixes; after 2 rounds without a pass → escalate.
- **Guardrails:** "measure the people first" structured pass before judgement (MTower lesson); **never approves** — only scores; the human gallery sign-off is still the final gate.
- **Competence (L1–L4):** L1 exacting dailies reviewer / DIT with a cinematographer's eye, assumes the generator is lying until proven right; L2 the shot's intent/direction/cast/wardrobe/set + library review lists + period grounding; L3 vision model, qa/autofix, face detection, actor anchors; L4 Orchestrator (routing), Research (period truth), Continuity (cross-shot), generation step (receives fixes).

### 3b. Studio Critic agent (Tier-2 decision reviewer)
- **Craft:** the **studio-wide** reviewer behind the validation gate — reviews **every non-image decision of every agent** (script intent, research verdicts, casting, wardrobe, set, camera, VFX, audio) against that agent's definition-of-done and the shot intent, before the orchestrator accepts it. The text-side counterpart to Image QA. (Standing rule 1, ADR-0002 Tier 2.)
- **Reads:** the producing agent's proposed output + the shot contract context (intent, direction, relevant prior fields) + the agent's DoD.
- **Writes:** `shot.critic[]` = `{target_field, verdict, reasons[], revise_instructions[]}`.
- **Tools:** the shot contract, the agent catalog (to know each DoD), library/grounding lookup for spot-checks.
- **Model:** cheap text reasoning (the Tier-2 "critic").
- **DoD:** every reviewed decision is marked pass / revise with reasons; revise routes back to the **owning** agent (never edited by the Critic); bounded revise rounds, then human escalation.
- **Guardrails:** **reviewer ≠ author** (never reviews its own work); judges decisions, not pixels (images go to Image QA); cheap-by-default, scope tunable (every decision vs only consequential ones).
- **Competence (L1–L4):** L1 meticulous script supervisor / QC lead who knows every craft's standard; L2 the agent catalog's definitions-of-done + standing rules + shot context; L3 contract + catalog + grounding lookup; L4 all agents (reviews them), Orchestrator (routes revisions), escalates to the human.

---

## Wave 2 — the creative crew

### 4. Casting agent
- **Craft:** map each character in a scene to a **library actor** from the **Talent Pool**, honoring the casting laws and roster distinctness; also **owns the Talent Pool and actor evolution** (see [08-talent-pool-and-actor-evolution.md](08-talent-pool-and-actor-evolution.md)).
- **Reads:** `shot.intent.characters[]`, `shot.direction`, `casting.json`, the Talent Pool dossiers.
- **Writes:** `shot.cast[]` = `{character_id, actor_id, face_model}`; and Talent Pool updates (stats/ratings) after each production.
- **Tools:** library/Talent-Pool resolver, `cast-check` distinctness, casting.json, QA-data reader (to update ratings).
- **Model:** text.
- **Decisions (locked 2026-10-14):**
  - **Crowds = archetypes** (not individually tracked); trained actors only for recurring or framed roles.
  - **On a gap, propose a candidate** (describe the needed look + suggest generating an anchor) for the user's approval.
  - **Stricter ensemble distinctness:** no two speaking/main characters within the similarity threshold `N` (tighter than the default crowd bar).
  - **Talent Pool:** design full now; **seed a modest diverse core, grow on demand**; evolution runs automatically from QA data (cost-aware — don't pre-train unused talent).
- **DoD:** every character resolves to a **locked actor with a trained face model** (or explicit "anchor-only / free"); no distinctness collision (ensemble rule enforced); real-person stand-ins never recast; missing-actor gaps are flags, not silent inventions.
- **Guardrails:** library-first; never recasts a locked role; never creates/trains a new actor without the user's sign-off (training cost + library change).
- **Competence (L1–L4):** L1 seasoned casting director + talent-agency manager with an ensemble-builder's eye; L2 Talent Pool dossiers + casting.json + character breakdowns + series casting laws; L3 Talent-Pool/library resolver, cast-check, QA-data reader; L4 Script/Director (who's in the scene), Wardrobe (receives cast), Continuity (same face across shots), Image QA (supplies evolution data), user (approves new actors).

### 5. Wardrobe agent
- **Craft:** choose the costume and **wear state** (clean/dusty/muddy/wet/bloodied/torn) per character per shot, period-correct and continuity-aware.
- **Reads:** `shot.intent`, `shot.direction`, `shot.cast`, `wardrobe.json`, `shot.continuity` (prior wear state).
- **Writes:** `shot.wardrobe[]` = `{character_id, wardrobe_id, wear_state}`.
- **Tools:** library resolver, optional vision check on the candidate.
- **Model:** text; optional vision for the post-gen check.
- **Decisions (locked 2026-10-14):**
  - **Blood split:** Wardrobe owns persistent **garment state** (a bloodstained shirt that stays bloodied across shots); **VFX** owns the *moment* of injury (spray/impact).
  - **Auto-escalating wear:** across a continuous action sequence, Wardrobe **progressively advances** dirt/damage automatically; the **Director may override** a specific shot and **Continuity validates** the progression.
  - **Continuity veto:** on a wear-state disagreement, **Continuity has veto on consistency**; Wardrobe owns the creative choice.
- **DoD:** each cast character has a resolved wardrobe ID + wear state consistent with the scene and prior continuity; covered-hair characters keep their headscarf (MTower rule); missing garments are flags, not anachronisms.
- **Guardrails:** period accuracy (1967–1973 uniforms/gear/insignia); escalates missing wardrobe assets rather than improvising.
- **Competence (L1–L4):** L1 period costume designer + continuity-obsessed wardrobe supervisor, expert in 1967–73 Egyptian/Israeli uniforms & period civilian dress; L2 wardrobe.json + prior continuity state + Research verdicts + series bible; L3 library resolver, vision check; L4 Casting (who's in shot), Research (period), Continuity (veto on consistency), VFX (garment damage vs effect), Image QA (verifies).

### 6. Set decoration agent
- **Craft:** dress the **world** — interiors (rooms, furniture, prop placement) and exteriors (streets, buildings, signage, parked vehicles), period-correct, lived-in, and plausible.
- **Reads:** `shot.intent`, `shot.direction`, `locations.json`, `vehicles.json`, `props.json`, `shot.research`, `shot.continuity`, Tone Bible visual refs.
- **Writes:** `shot.set` = `{location_id, dressing[], vehicles[], props[], set_state}`.
- **Tools:** library resolver, vision check.
- **Model:** text; optional vision.
- **Decisions (locked 2026-10-14):**
  - **Set/VFX boundary:** Set owns **static atmosphere** (ambient dust, a smoldering wreck that's part of the scene, hanging haze); **VFX** owns **dynamic events** (the explosion that creates the wreck, moving smoke, tracers).
  - **Set continuity:** a location's dressed/damaged **state persists and evolves** across a sequence (a room shot up stays damaged), tracked automatically with **Continuity validating** — same model as wardrobe wear.
  - **Props split:** **Set owns environmental props** (crates, furniture, parked vehicles); **hand-props actively used** by an actor (the radio a soldier speaks into) are handled by the shot's action/Camera.
- **DoD:** location resolves to a library LOC; all placed vehicles/environmental props are library IDs, period-correct, physically plausible for the blocking; set_state consistent with prior continuity; no anachronistic dressing/signage; gaps are flags.
- **Guardrails:** library-first; flags crowded-group-shot prop risks (MTower open issue) for Camera/VFX.
- **Competence (L1–L4):** L1 production designer + set decorator + props master, expert in 1967–73 Egyptian/Sinai environments, architecture, street life, military installations, period objects; L2 locations/vehicles/props.json + Research verdicts + Tone Bible refs + series bible; L3 library resolver, vision check; L4 Research (place/period), Director/Camera (frame needs, blocking), VFX (dynamic effects), Continuity (same set across shots), Image QA (verifies).

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
