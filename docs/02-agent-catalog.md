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
| 5b | **Makeup & Hair / Prosthetics** | Skin: wounds, grime, sweat, blood on faces, aging, hair | text (+vision check) | 2 |
| 6 | **Set decoration** | Location dressing, interior/exterior, period props placement | text (+vision check) | 2 |
| 7 | **Camera / DoP** | Framing, lens, movement, light, format | text | 2 |
| 7b | **Stunt / Action Choreographer** | Combat blocking, weapon handling, movement, safety-plausible action | text (reasoning) | 2 |
| 8 | **Dialect / Language specialist** | Egyptian-Arabic dialect, slang, diacritics, per-character register | text + Speech | 3 |
| 9 | **VFX / Effects** | Explosions, smoke, tracers, weather, damage | text (+vision check) | 3 |
| 10 | **Continuity** | Cross-shot consistency (time, blood, props, light) | **vision** | 3 |
| 11 | **Sound / Voice** | Narration, dialogue, SFX, music briefs | text + Speech/tts | 3 |
| 12 | **Editor / Post** | Assemble approved shots → animatic → cut + subtitles | text + assembly | 3 |
| 13 | **Marketing** *(support)* | Poster/key art, teaser plan, synopsis (on-brand) | text + image | 3+ |
| 14 | **Graphic & Title Design** | In-world graphics, titles/credits, subtitles, studio brand & web | text + image | 3 |

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
  - **Dramatized staging (P-01, ADR-0003, 2026-10-17):** gestures/staging that *show* a real person's sourced action are verdict `dramatized` (cite the `H-xx` event; never block). Staging that adds an unsourced fact is still flagged.
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
- **Competence (L1–L4):** L1 period costume designer + continuity-obsessed wardrobe supervisor, expert in 1967–73 Egyptian/Israeli uniforms & period civilian dress; L2 wardrobe.json + prior continuity state + Research verdicts + series bible; L3 library resolver, vision check; L4 Casting (who's in shot), Research (period), Continuity (veto on consistency), VFX (garment damage vs effect), Image QA (verifies), **Makeup & Hair (skin counterpart)**.

### 5b. Makeup & Hair / Prosthetics agent
- **Craft:** everything on the **skin and head** (vs Wardrobe's cloth): wounds, scars, bruises, grime, sweat, blood on faces/hands, sunburn, aging, beard/hair state, and prosthetics. Makes faces read as real and battle-worn.
- **Reads:** `shot.intent`, `shot.direction`, `shot.cast`, `shot.continuity` (prior skin/injury state), `shot.vfx` (injury events), Research notes.
- **Writes:** `shot.makeup[]` = `{character_id, skin_state, injuries[], hair_state, prosthetics[]}`.
- **Tools:** library resolver (makeup presets), vision check on the candidate.
- **Model:** text; optional vision.
- **Decisions (locked 2026-10-14, per studio defaults):**
  - **Skin vs cloth split:** Makeup owns on-body appearance (blood on a face, grime on skin); Wardrobe owns the garment; VFX owns the injury *event*; clean three-way boundary.
  - **Injury continuity:** a wound, once inflicted (a VFX/Director delta), **persists and ages** across later shots — tracked with **Continuity validating**.
  - **Restraint cap:** gore on skin obeys the same **hard restrained-violence cap** as VFX.
- **DoD:** each framed character has a resolved skin/hair state consistent with the scene, prior continuity, and any injury deltas; within the restraint cap; gaps flagged.
- **Guardrails:** period-accurate grooming (1967–73); never exceeds the gore cap; defers injury-*event* timing to VFX/Director.
- **Competence (L1–L4):** L1 department-head makeup artist + prosthetics/SFX-makeup specialist, expert in battle-wound realism and period grooming; L2 makeup presets + prior continuity state + VFX injury events + Research period notes; L3 library resolver, vision check; L4 Wardrobe (cloth counterpart), VFX (injury event), Casting (who's framed), Continuity (injury persistence), Image QA (verifies).

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
- **Craft:** translate the Director's intent into **concrete photographic specs** — shot size, lens, movement, lighting, and format — consistent with the series look and buildable by the image models.
- **Reads:** `shot.intent`, `shot.direction` (coverage/intent), `looks.json`, `visual_guide.md`, `shot.set`, Tone Bible visual refs, `shot.continuity`.
- **Writes:** `shot.camera` = `{shot_size, lens, movement, light, look_key, format, exposure_note}`.
- **Tools:** looks catalog, visual guide, optional vision check on framing/light.
- **Model:** text.
- **Decisions (locked 2026-10-14):**
  - **Lighting continuity veto:** **Continuity vetoes** lighting consistency (light direction/color across a scene); Camera owns the creative lighting choice.
  - **Look discipline:** Camera is **strictly bound to existing `looks.json` keys**; a *new* look is proposed only via a flag for the user's approval (protects series-wide coherence).
  - **Size/lens source of truth:** the **Director paints broad coverage**; **Camera refines and finalizes** the exact shot size + lens.
- **DoD:** resolved **look key + full camera spec** matching the visual guide and the beat's emotional note; **night/dark shots carry an explicit exposure note** (MTower open issue); consistent with the Director's intent and prior lighting continuity.
- **Guardrails:** references `looks.json` keys, never duplicates look wording into the shot; new looks are flagged, not improvised.
- **Competence (L1–L4):** L1 award-calibre cinematographer + gaffer, master of lenses/lighting/composition, fluent in how image models read camera/light language; L2 looks.json + visual guide + Tone Bible refs + Director intent + set contents; L3 looks catalog, visual guide, vision check; L4 Director (intent), Set (frame contents), VFX (light-affecting effects), Continuity (veto on light), Image QA (verifies), **Stunt/Action (combat blocking)**.

### 7b. Stunt / Action Choreographer agent
- **Craft:** design the **physical action** — combat blocking, weapon handling, movement, hand-to-hand, fire-and-movement, falls, and vehicle action — believable, period-correct, and tactically sound for a Sa'iqa special-ops series.
- **Reads:** `shot.intent`, `shot.direction`, `shot.set`, `shot.research` (tactics/weapons), `shot.cast`, `shot.vfx`.
- **Writes:** `shot.action` = `{choreography, weapon_handling, movement, beats[], safety_note}`.
- **Tools:** Research tactics/weapons lookup, library (weapons/vehicles), optional vision check.
- **Model:** text (reasoning).
- **Decisions (locked 2026-10-14, per studio defaults):**
  - **Tactical realism via Research:** weapon handling and tactics are **verified by Research** (correct firing stance, period doctrine) — anachronistic/wrong handling is flagged like any fact error.
  - **Feeds Director + Camera + VFX:** choreography sets what the Director covers, what Camera frames, and which effects VFX triggers (muzzle flash timed to a trigger pull).
  - **Restraint cap:** action obeys the hard restrained-violence cap.
- **DoD:** each action shot has choreography + correct weapon handling + movement beats, tactically verified, within the restraint cap; consistent with the blocking.
- **Guardrails:** period-correct tactics/weapon handling (no modern techniques); defers effect rendering to VFX and framing to Camera; restraint cap enforced.
- **Competence (L1–L4):** L1 stunt coordinator + military-action/armorer advisor, expert in period small-unit tactics and weapon handling; L2 Research tactics/weapons verdicts + library weapons/vehicles + Tone Bible action refs; L3 Research lookup, library, vision check; L4 Director (coverage), Camera (framing), VFX (effect timing), Research (tactics), Continuity (action across shots).

---

## Wave 3 — the finishing crew

### 8. Dialect / Language specialist agent (Egyptian-Arabic first)
- **Craft:** turn the Script agent's dialogue/VO **meaning** into natural, living **Egyptian Arabic** (slang, register, rhythm, era-appropriate expression) with **full diacritics (التشكيل الكامل)** and delivery/acting notes; verify pronunciation. Built Egyptian-first, structured to add languages (e.g. Hebrew radio with Arabic subtitles) later.
- **Reads:** `shot.vo`, `shot.dialogue[]`, `shot.cast` (voice profiles), `narration_egyptian.md`, D-19/D-20 direction, Research language notes.
- **Writes:** `shot.dialogue[].egyptian` (+ diacritized, acting_note), `shot.vo.egyptian`, `shot.voice_notes`, per-character voice profiles.
- **Tools:** Azure Speech (render + `voice --check` speech-to-text verification), tts/audio models, diacritization.
- **Model:** text + Speech.
- **Decisions (locked 2026-10-14):**
  - **Per-character register:** adapts dialect by character (officer vs village conscript, Cairene vs Sa'idi), tracked as a per-character voice profile.
  - **Era-authenticity via Research:** too-modern/anachronistic expressions are flagged through Research, like any other anachronism.
  - **Extensible scope:** Egyptian-Arabic first, with structure to add Hebrew/other languages later.
- **DoD:** every spoken line has an Egyptian-dialect version with **full diacritics** + an acting note; a **speech-to-text check round-trips** to the intended meaning; register matches the character's voice profile.
- **Guardrails:** formal screenplay VO remains the meaning source of truth; dialect changes wording, not meaning; no ungrounded period slang (checked with Research).
- **Competence (L1–L4):** L1 native Egyptian dialect coach + screen-dialogue writer, master of Cairene/regional slang and registers, obsessive about TTS diacritics; L2 narration_egyptian.md + language direction (D-19/D-20) + character voice profiles + Research period-language notes; L3 Azure Speech, voice --check, tts/audio, diacritization; L4 Script (meaning), Research (period language), Sound/Voice (final production), Casting (voice profiles).

### 9. VFX / Effects agent
- **Craft:** specify the **dynamic effects** (the *events*) — explosions, muzzle flash, tracers, smoke, dust, water, weather, vehicle/structure damage — restrained and period-plausible.
- **Reads:** `shot.intent`, `shot.direction`, `shot.set`, `shot.research`, `shot.continuity`.
- **Writes:** `shot.vfx[]` = `{effect, intensity, placement, timing}`; effect-light proposal; evolving effect state.
- **Tools:** vision check on candidates; references props/vehicles for consistent damage.
- **Model:** text; optional vision.
- **Decisions (locked 2026-10-14):**
  - **Hard gore cap:** the restrained-violence rule is an **enforced cap** — VFX flags/clamps anything past the defined line (treated like a gate), not a soft guideline.
  - **Effect-light coordination:** **VFX proposes** the effect light (muzzle flash, explosion, fire); **Camera integrates** it into the frame's lighting.
  - **Effect continuity:** persistent smoke/fire/damage across a sequence is tracked as **evolving state with Continuity validating** (same model as set/wardrobe).
- **DoD:** effects specified with **type, intensity, placement, timing**; physically coherent and consistent with Research's verdicts; within the restrained-violence cap; risk shots flagged.
- **Guardrails:** restrained violence (hard cap); owns the *event* only (Set = static aftermath, Wardrobe = garment result); flags shots where effects + actor/prop models together risk losing the scene (MTower open issue).
- **Competence (L1–L4):** L1 VFX supervisor + pyrotechnics/SFX coordinator, expert in period ordnance behavior, ballistics feel, restrained believable war effects; L2 Research ordnance verdicts + props/vehicles.json + restrained-violence rule + Tone Bible action refs; L3 vision check, props/vehicle references; L4 Research (ordnance), Set (aftermath), Wardrobe (garment result), Camera (effect light), Continuity (persistence), Sound (effect audio), Image QA (verifies).

### 10. Continuity agent
- **Craft:** enforce consistency **across** shots — time of day, light direction, wear state, injuries, prop positions, who-holds-what, set damage, weather, appearance — the studio's guardian against drift.
- **Reads:** this shot + neighboring shots' contracts in the same beat/scene, the running world-state, the Director/Script **delta list** (intended changes).
- **Writes:** `shot.continuity` = `{prior_state_ref, deltas[], violations[]}`; updates the running world-state.
- **Tools:** vision (compare frames), contract store queries across the sequence.
- **Model:** **vision**.
- **Decisions (locked 2026-10-14):**
  - **Scope = both:** within-**scene** as the strict gate; **cross-scene/whole-episode** tracked as persistent world-state (a scar from Act 1 persists to Act 5).
  - **Delta source of truth:** the **Director/Script own the intended-change (delta) list**; Continuity validates against it (never guesses intent).
  - **Blocking power:** an **open continuity violation blocks the shot from human approval** until resolved (strongest guarantee against drift reaching the cut).
- **DoD:** no unexplained violation vs adjacent approved shots; every intentional change recorded as a **delta**; running world-state updated for downstream shots.
- **Guardrails:** read-only on other agents' fields (reviewer ≠ author); raises violations for the orchestrator to route; judges relationships between frames (Image QA judges single frames).
- **Competence (L1–L4):** L1 veteran script/continuity supervisor with a photographic memory and obsessive frame-to-frame eye; L2 neighboring shot contracts + running world-state + intended delta list; L3 vision compare, contract-store queries; L4 Wardrobe/Set/Camera/VFX (consistency veto), Image QA (complementary), Director/Script (delta list), Orchestrator (routes fixes).

### 11. Sound / Voice agent
- **Craft:** own the **audio brief** per shot/beat — narration takes, dialogue delivery, SFX list, and music cues; coordinate renders and the listen-back check.
- **Reads:** `shot.vo`, `shot.dialogue[]` (+ egyptian), `shot.voice_notes`, `shot.vfx` (effect audio), beat timing.
- **Writes:** `shot.audio` = `{narration_take, dialogue_takes[], sfx[], music_cue}`.
- **Tools:** Azure Speech / tts / gpt-audio, engine `voice`/`animatic`, ledger.
- **Model:** text + Speech/audio.
- **Decisions (locked 2026-10-14):**
  - **Draft vs final tiering:** Azure Speech for drafts/animatic; **ElevenLabs remains the planned final narrator** (D-19) — premium renders are cost-gated.
  - **SFX sourced from VFX events:** the effect list drives the SFX brief (a muzzle flash implies its report), keeping picture and sound coherent.
  - **Music = cue briefs, not final score** in-studio; final scoring is a human/ElevenLabs/licensed step, cost-gated.
- **DoD:** each narrated/spoken beat has a rendered take that **passes the listen-back (speech-to-text) check**; SFX + music cues listed for the edit; costs logged.
- **Guardrails:** no premium render without a cost gate; respects session sensitivity; SFX/music coherent with VFX and tone.
- **Competence (L1–L4):** L1 supervising sound editor + re-recording mixer + music supervisor, ear for period ambience and restrained scoring; L2 voice notes + dialect takes + VFX event list + Tone Bible music/sound refs + D-19/D-20 direction; L3 Azure Speech/tts/gpt-audio, voice/animatic, ledger; L4 Dialect specialist (lines), VFX (effect audio), Editor (timeline), Director (tone), user (final scoring approval).

### 12. Editor / Post agent
- **Craft:** assemble approved shots into a **cut** — ordering, timing/pacing, transitions, and subtitles — building the animatic first, then the edited sequence; the studio's cutting room.
- **Reads:** approved `shot.generation.selected` + `shot.audio` across a beat/scene, beat timing, the Director's pacing notes, `shot.dialogue` (for subtitles).
- **Writes:** `scene.cut` = `{shot_order[], durations[], transitions[], subtitle_track}`; animatic/edit artifacts (paths).
- **Tools:** engine `animatic`/timeline export, subtitle generation, ledger.
- **Model:** text (reasoning) + the engine's assembly tools.
- **Decisions (locked 2026-10-14):**
  - **Animatic-before-video:** lock timing on keyframes + narration + temp sound **before** paying for motion video (MTower discipline).
  - **Only approved shots enter the cut:** the Editor never pulls un-approved or QA-failed frames.
  - **Subtitles from the canonical dialogue** (Arabic subtitles for Hebrew radio, per series rule), timed to the audio.
- **DoD:** a scene cut exists with ordered approved shots, locked durations/transitions, and a timed subtitle track; animatic reviewed before any video spend.
- **Guardrails:** assembles only approved material; no premium video render until the animatic timing is locked and cost-gated; final polish/grade/upscale remains a human step in the NLE (e.g. DaVinci Resolve).
- **Competence (L1–L4):** L1 film editor with a sense of rhythm and story; L2 approved shots + audio + pacing notes + beat timing; L3 engine animatic/timeline, subtitles, ledger; L4 Director (pacing), Sound (audio bed), Continuity (order sanity), user (final cut approval).

### 13. Marketing agent *(supporting; optional)*
- **Craft:** produce promotional assets from the finished material — **poster concepts, key art, teaser/trailer plans, episode synopses** — on the studio's look and tone.
- **Reads:** the series bible, Tone Bible, approved hero shots, the episode cut, the visual guide.
- **Writes:** marketing artifacts (poster drafts, trailer plan, synopsis) under the production's `marketing/`.
- **Tools:** image generation (via the engine, cost-gated), the library, looks.
- **Model:** text + image (via engine).
- **Decisions (locked 2026-10-14):**
  - **Reuses hero frames/look** — marketing is derived from approved material and the established look, not a divergent aesthetic.
  - **Cost-gated and human-approved** like any generation; nothing published without the user (privacy/publish gate).
- **DoD:** requested marketing assets drafted on-brand, cost-logged, staged for the user's review; nothing published automatically.
- **Guardrails:** never publishes/shares (human gate); respects session sensitivity and copyright (original key art, not cloned).
- **Competence (L1–L4):** L1 key-art designer + trailer editor + copywriter; L2 series/Tone bible + approved hero shots + the cut; L3 engine image gen, library, looks; L4 Director (tone), Editor (trailer source), Image QA (verifies key art), user (publish approval).

### 14. Graphic & Title Design agent
- **Craft:** all **designed graphics** — (a) **in-world period graphics** (Arabic signage, telegrams, letters, maps, newspapers, documents, unit insignia); (b) **title & credits design** (main/end titles, episode title cards, lower-thirds, subtitle styling); (c) the **studio brand & UX** (logo system, identity, the studio website). The art department's graphic artist + title designer + brand designer.
- **Reads:** `shot.intent`/`shot.set` (what graphics a scene needs), series/Tone bible, Research verdicts (period-correct text/typography), `shot.dialogue` (titles/subtitles), the episode cut.
- **Writes:** `shot.graphics[]` = `{type, content, placement}`; title/credit specs; brand/web artifacts under the studio's `brand/`.
- **Tools:** image generation (via the engine, cost-gated), typography/layout, library, looks.
- **Model:** text + image (via engine).
- **Decisions (locked 2026-10-14):**
  - **Period-correct typography via Research:** in-world text (Arabic script style, fonts, document formats) is verified by Research — no anachronistic lettering.
  - **In-world graphics vs physical dressing:** Graphic Design owns *designed artifacts* (a printed telegram, a map); **Set** owns their physical placement in the frame.
  - **Brand consistency:** titles, episode cards, and promo share one designed identity; cost-gated and human-approved like any generation.
- **DoD:** required graphics/titles designed, period-correct, legible, on-brand, cost-logged; nothing published without the user.
- **Guardrails:** period-accurate lettering (checked with Research); original design, not cloned IP; never publishes/shares (human gate).
- **Competence (L1–L4):** L1 art-department graphic artist + main-title designer + brand/UX designer, expert in period Arabic typography and document design; L2 series/Tone bible + Research typography verdicts + the cut + brand system; L3 engine image gen, typography/layout, library; L4 Set (physical placement), Research (period type), Marketing (campaign), Editor (titles/subtitles in the cut), Director (tone), user (publish approval).

---

## Notes on crew size

The full crew is now **18 roles**: Orchestrator (0), Script (1), Director (1b), Research (2), Image QA (3), Studio Critic (3b), Casting (4), Wardrobe (5), Makeup & Hair (5b), Set (6), Camera/DoP (7), Stunt/Action (7b), Dialect/Language (8), VFX (9), Continuity (10), Sound/Voice (11), Editor/Post (12), Marketing (13, optional support), Graphic & Title Design (14). Adjust as reality dictates:
- **Mergeable** for a leaner start: Wardrobe + Set + VFX could begin as one **"Art Department"** agent and split later.
- **Possibly split** if load grows: Script could split into **Scenario (structure)** vs **Dialogue (lines)**; Casting could spin off a dedicated **Talent Manager** for Talent-Pool upkeep.
- **Marketing (13)** is optional supporting crew — stand it up only when promotion is needed.

The orchestrator does not need the full crew to be useful — **Wave 1** (Orchestrator + Script + Director + Research + Image QA + Studio Critic) already closes the generate → validate → regenerate loop end to end. Waves 2–3 add the creative and finishing crew.
