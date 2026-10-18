# Performance guide — voices and intensity

**Why:** the user's standing rule (2026-10-13): *the voices and their intensity must always match the situation* — a man under fire must sound under fire, a mother at a doorway must sound like it. This guide is how every line of Episode 1 is cast and directed. Decisions: D-20 (drama first) and D-21 (performance system) in `studio/infra/docs/decisions.md`.

## How it works

1. **One fixed voice per character** — `02_preproduction/production_config.json` → `voice_cast`. A character is *cast* when the entry has a `voice`, or when one of its auditions is approved in the review app (**Voice casting**). `./mtower.ps1 audition` lists the cast; `./mtower.ps1 audition C-02` records new auditions (each candidate reads the character's calmest and most intense line).
2. **Every line carries its performance** — in the shot lists, each `dialogue_refs` entry has:

   | Field | Values | Meaning |
   |---|---|---|
   | `intensity` | 1–10 | how much is at stake *inside* the character (scale below) |
   | `volume` | whisper · low · normal · raised · shout | how loud he/she actually speaks |
   | `pace` | slow · measured · normal · quick · rushed | speed and pauses |
   | `emotion` | short phrase | the feeling under the words |
   | `delivery` | one or two sentences | the actor's note: what the character is doing, to whom, and why |
   | `fx` | radio (optional) | the line is heard through a radio / handset |
   | `situation` | (optional) | overrides the automatic situation |

3. **The situation is automatic** — the engine reads the screenplay beat: scene heading, environment, and all action written *before* the line. The voice actor (gpt-audio-1.5) gets: language rule → character persona → situation → this line's delivery, emotion, intensity, volume and pace.
4. **Retakes until the words are right** — every take is checked by speech-to-text and re-recorded (up to 3 tries) until it hears the line as written. The *acting* is judged by you, by ear, in the review app (**Dialogue**).
5. **Finished takes** — loudness is matched to the volume (whisper −27 LUFS · low −23 · normal −20 · raised −18 · shout −16), so a whisper stays a whisper in the mix but is never inaudible; children's voices are pitched up; radio lines get a radio filter.
6. **Lip-sync and the cut** — `lipsync --beat <beat>` animates the talking shots (`lip_sync: "required"`) with the approved takes (Kling Avatar v2 Pro); `animatic --part <part> --beats <beat> --clips --dialogue` lays every line at its shot with the same timing.

Commands (from `studio/engine`): `./mtower.ps1 dialogue --beat T.3` (dry run) → `--confirm-cost <USD>`; `./mtower.ps1 lipsync --beat T.3` → `--confirm-cost`; `./mtower.ps1 voice --part 02_act_two --beat 2.2` for Hamdi's narration.

## The intensity scale

Intensity is **what is at stake inside the character**, not loudness. A whisper can be a 9 (Shalabi into the handset as a tank battalion passes); a shout can be a 4 (calling across a courtyard).

| Level | Feels like | Body and voice | Example in Episode 1 |
|---|---|---|---|
| 1–2 | relaxed, at ease | loose, warm, unhurried | — (nobody in this episode is truly at ease) |
| 3–4 | everyday, engaged | present, normal breath; small feelings | Sayed teaching the straps (1.2) · Ali asking about Suez (1.5) |
| 5–6 | tense: something real is at stake | held breath, tighter consonants, fewer words | the sealed envelope (1.4) · «السلاح فوق راسكو» (2.3) |
| 7–8 | high stakes: urgent pressure | voice tight in the throat, clipped, no wasted words | the pilot's warning and «نزّلنا» (T.3) · the intercepted signal (2.4) · Umm Mostafa «مصطفى…» (5.5) |
| 9–10 | life or death: the peak of the scene | everything in the voice — even when whispering | «سيبوهم يعدّوا» (3.4) · «عدّوا يا أمّه!» (3.2) · «اضرب!» (3.6, the episode's single 10) |

**Rules:** at 6 and above, a take must never sound relaxed, casual or sleepy (the first Shalabi take was rejected for exactly this). At every level, never theatrical or over the top — film acting, not stage acting. Only one 10 per episode.

## Volume and pace

| Volume | How it sounds | Mixed at |
|---|---|---|
| whisper | breathy, almost no voiced tone, close to one person | −27 LUFS |
| low | quiet, held back, for one or two people | −23 LUFS |
| normal | ordinary speaking level | −20 LUFS |
| raised | projecting over noise or across a room | −18 LUFS |
| shout | full force | −16 LUFS |

Pace: **slow** (real pauses) · **measured** (deliberate) · **normal** · **quick** (clipped) · **rushed** (words tumbling out).

## The cast

| ID | Character | Voice | Persona (short) |
|---|---|---|---|
| N-01 | Hamdi Shalabi, old (narrator) | audition | late seventies, remembering for his grandchildren; low, slightly worn, moved |
| C-01 | Captain Hamdi Shalabi | gpt-audio-1.5 · echo ✔ | ~30, few words, controlled; tightens under pressure, never panics |
| C-08 | Mi-8 squadron leader | gpt-audio-1.5 · ash ✔ | mid-40s, calm professional authority, protective |
| C-02 | Sergeant Sayed | audition | mid-30s, Suez, gravelly and dry, protective |
| C-03 | Private Mostafa | audition | 19, village boy, earnest, braver than he feels |
| C-04 | Corporal Mahmoud | audition | mid-20s radio operator, precise, whispers |
| C-07 | Commander of Sa'iqa Forces | audition | early 50s, formal, fatherly warmth underneath |
| C-11 | Umm Mostafa | audition | mid-40s, rural Delta, very few words, strong and low |
| C-12 | Zeinab (12) | audition (pitched) | bright, quick, proud she can read |
| C-13 | Fatma | audition | ~30, Suez in Cairo, composed, soft, tired |
| C-14 | Ali (8) | audition (pitched) | small, curious, a little shy |
| — | Cairo radio announcer | audition | 1973 state radio, formal Arabic, radio filter |
| — | Commandos (murmur) | group of 4 voices | exhausted men murmuring «إن شاء الله» |
| — | Israeli radio voices (3) | audition | Hebrew, radio filter; professional, never caricatured |

Two characters who speak in the same beat must not share a voice — `check` and `audition` warn about clashes. The narrator (old Hamdi) is auditioned with the young Shalabi's own voice (echo, pitched slightly down) against two others, so you can choose between continuity and contrast.

## The episode's emotional arc (dialogue)

Intensity of each line in order, and the peak of each beat.

| Beat | Title | Who speaks | Lines | Peak | The peak feeling |
|---|---|---|---|---|---|
| T.3 | Phantoms on the radar | squadron leader, Shalabi | 7 → 8 → 7 → 8 | 8 | the weight of a decision that risks all his men |
| 1.2 | "Afraid?" | Sayed, Mostafa | 3 → 4 → 5 → 3 | 5 | a boy hiding fear |
| 1.3 | The letter from the front | Zeinab, Mostafa (letter), Umm Mostafa | 3 → 3 → 4 | 4 | quiet pride mixed with worry |
| 1.4 | The orders | Commander, Shalabi | 5 → 5 → 5 → 6 → 6 | 6 | the weight registers |
| 1.5 | The blue windows | Ali, Fatma | 3 → 4 | 4 | tired hope, holding back sadness |
| 1.7 | Letters | Mostafa (letter), Sayed | 3 → 6 → 6 → 5 | 6 | matter-of-fact masking deep feeling |
| 1.10 | "Here is Cairo" | radio announcer | 7 | 7 | triumph |
| 2.3 | Compass and map | Shalabi | 6 → 6 | 6 | decisive; moving out |
| 2.4 | The intercepted signal | Mahmoud, Shalabi | 8 → 8 | 8 | cold, urgent command; no panic |
| 2.6 | Mostafa goes under | Sayed | 5 | 5 | relief and pride |
| 2.13 | Few against many | Shalabi, commandos, Sayed | 6 → 5 → 7 | 7 | a quiet vow |
| 2.14 | Three platoons, three kilometers | Shalabi | 5 | 5 | focused planning |
| 2.16 | Barrel pits | Sayed | 4 | 4 | practical instruction |
| 3.2 | "They crossed!" | Zeinab, Umm Mostafa | 9 → 6 | 9 | breathless joy, then a mother's fear |
| 3.4 | The battalion passes | Shalabi, Sayed | 9 → 9 | 9 | iron control, whispered |
| 3.5 | The road looks clear | Israeli radio | 4 | 4 | routine confidence |
| 3.6 | The order | Shalabi | 10 | 10 | the release of all held tension |
| 3.10 | War games | Fatma | 6 | 6 | sharp worry |
| 3.12 | Stuck in the sand | Israeli tank and brigade commanders | 9 → 8 | 9 | confused panic under fire |
| 4.8 | Blackout | Ali, Fatma | 3 → 5 | 5 | suppressed grief |
| 5.3 | The letter arrives | Zeinab, Mostafa (letter) | 4 → 4 | 4 | tender; the plea rises |
| 5.5 | The son returns | Umm Mostafa | 8 | 8 | overwhelming relief |
| 5.6 | Sayed's letter | Mostafa, Sayed (letter) | 7 → 6 | 7 | grief-stricken duty; calm acceptance |

**Shape:** Act One stays at 3–6 (people, waiting, small fears) with the teaser's 8 as a promise; Act Two climbs to 8 in the marsh; Act Three holds 9 in whispers and breaks once at 10 («اضرب!»); Acts Four and Five come down to grief and relief (5–8), mostly quiet.

## Narration (old Hamdi)

`03_production/voice/narration_hamdi.md` — 22 short first-person beats, about a third of the old documentary narration. Each beat's performance is a comment at the top of its section (default intensity 5, low, measured). The deepest moments are 4.5 and 4.9 (8): his men running at the tanks, and burying them in the dark. He never narrates the families at home.

## Your review (in the app)

- **Voice casting:** listen to each candidate (calm sample, then intense sample) and approve one per character. Write a note if none fits — e.g. "older", "rougher", "less polished".
- **Dialogue:** every line shows its target under the text — `[8/10 · raised · quick] sharp objection…`. Approve the take that hits it; note "too calm", "too theatrical", "wrong word" etc.; the note goes into the line's `delivery` and the line is re-recorded.
