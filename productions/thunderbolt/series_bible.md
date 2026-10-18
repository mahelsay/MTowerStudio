# الصَّاعِقَةُ — *Thunderbolt*
## Series Bible

| Field | Value |
|---|---|
| Working title | **الصَّاعِقَةُ** — *Thunderbolt* (Sa'iqa is Arabic for "thunderbolt") · *working title, to be confirmed* |
| Format | AI-generated historical drama series · **one episode = one real Egyptian Sa'iqa special operation** · ~45 minutes per episode |
| Period | 1967–1973: from the June War, through the War of Attrition, to the October War |
| Language | Arabic narration and dialogue; Hebrew radio voices with Arabic subtitles |
| Status | Locked v1.0 (2026-10-10) · **v1.1 (2026-10-15): drama-first** — §4.2, §5 and §6 rewritten so the story is carried by the characters' dialogue, not by narration (user direction: "a normal series with normal drama dialogue and action scenes, as if with real actors") · Season 1 slate remains open |

> **What is a series bible?** It is the rulebook for the whole show. Every episode must follow it so the series feels like one show, even when the stories, places, and characters change.

---

## 1. Series logline

### العربية

> فِي كُلِّ حَلْقَةٍ، عَمَلِيَّةٌ حَقِيقِيَّةٌ لِرِجَالِ الصَّاعِقَةِ الْمِصْرِيَّةِ بَيْنَ عَامَيْ ١٩٦٧ وَ١٩٧٣: رِجَالٌ قَلِيلُونَ، خَلْفَ خُطُوطِ الْعَدُوِّ، بِأَسْلِحَةٍ خَفِيفَةٍ… وَعَائِلَاتٌ تَنْتَظِرُ فِي الْبُيُوتِ خَبَرًا لَا يَأْتِي.

### English

> Each episode follows one real operation by Egyptian Sa'iqa commandos between 1967 and 1973: a few lightly armed men behind enemy lines — and, at home, the families waiting for news that does not come.

---

## 2. Why this show works (the "engine")

- **The A-plot (≈ 75% of each episode):** the mission itself, told with tactical accuracy — the orders, the insertion, the approach, the action, the cost, and the way home.
- **The B-plot (≈ 20%):** the home front — the families of a few (fictional) commandos in villages and cities, living through the same days without knowing what is happening to their men.
- **The epilogue (≈ 5%):** what really happened, in a few on-screen cards, and a dedication.

The two plots answer each other: the men are silent behind enemy lines; the families are silent at home. The episode ends where they meet again — or don't.

---

## 3. Format: one episode

**Target length:** 42–46 minutes including titles and credits — the length of a standard one-hour TV drama episode without commercials.

| Part | Length | Purpose |
|---|---|---|
| **Teaser** (cold open) | 2–3 min | A tense moment from inside the mission, then the main title. Hooks the viewer. |
| **Act One** | 9–11 min | Who these men are, the mission orders, and the families at home. |
| **Act Two** | 9–11 min | The insertion and approach: getting behind enemy lines. |
| **Act Three** | 8–10 min | The operation reaches its peak. |
| **Act Four** | 6–8 min | The cost. |
| **Act Five** | 5–7 min | The way home, the families, the epilogue cards, and credits. |

**Act-outs:** each act ends on a strong image or turn (a cliffhanger), so the next act starts with momentum.

**Screenplay files:** one file per part — `00_teaser.md`, `01_act_one.md` … `05_act_five.md` — in `productions/thunderbolt/epNN_name/01_development/screenplay/`.

**Beat numbering:** beats are numbered by act — `T.1` for the teaser, `1.1`, `1.2` for Act One, and so on — so each beat maps directly to a group of shots in the Phase 2 shot list.

---

## 4. Rules for every episode

### 4.1 History and real people

1. **Every episode is based on a real, documented operation.** Each one needs a source file in its `research/` folder.
2. **Real people** (commanders, named soldiers, enemy officers) appear only through actions stated in our sources. **No invented private lives, families, or backstories for real people**, unless they come from verified sources such as published interviews.
3. **Composite characters** are fictional people who represent the real men of the unit. They carry the personal moments of the episode and the home-front stories. They are labeled as fictional in the episode's `characters.md`.
4. **Dialogue reconstructed from a source's paraphrase** is marked *(dramatized)* in the screenplay.
5. **Contested facts** (unit numbers, casualty figures, equipment) stay neutral in the narration until verified. **Where Egyptian and Israeli accounts disagree on numbers, present them as each side's claim** ("according to Egyptian sources…"), never as established fact.
6. **Every episode ends with an on-screen source note** if any facts remain unverified at release.

### 4.2 The home front (B-plot)

1. Only **composite characters** have families on screen.
2. The B-plot is told through **short, real scenes between family members** — a mother and daughter, a wife and son — plus letters, radio and silent moments. Children ask the questions the adults avoid; the adults answer sideways.
3. Historical texture of the period is welcome and should be accurate: wartime radio announcements, blackout-painted windows, families displaced from the canal cities since 1967, and Ramadan in October 1973.
4. The home front never knows more than a real family would have known at that time.

### 4.3 The enemy

The Israeli side is a professional, dangerous enemy — never mocked or caricatured. It is shown through machines, distant figures, and **radio voices in Hebrew with Arabic subtitles**. Hebrew lines must be checked by a native speaker before recording.

### 4.4 Violence

**Restrained.** Death and injury are implied through smoke, distance, sound, and absence — an empty position, a dropped object, a rifle with no owner. No graphic wounds or bodies in close-up. This keeps the tone dignified and keeps shots usable in AI image and video tools, which often block graphic violence.

### 4.5 No Quran

**No Quran anywhere in the series** (user rule, 2026-10-14): no verse quoted in dialogue, narration, on-screen text or titles, and no Quran recitation in the sound design (a radio plays songs or news instead). Characters may use everyday expressions such as «إن شاء الله» or «الحمد لله». `./mtower.ps1 check` flags Quran words and known verses in the screenplay, narration scripts and shot lists (`production_config.json` → `script_rules`).

---

## 5. Tone, sound, and look (series-wide)

These decisions were made while developing Episode 1 and now apply to every episode.

| Area | Series rule |
|---|---|
| **Narrator** | Old Hamdi Shalabi remembering, in his own everyday Egyptian Arabic (first person). **One or two short lines in a few beats only**, for time, place and documented context no character could naturally say (dates, unit numbers, what the mission was). Never explains what the audience can see or what a character can say. **Speaks only about documented events — never about the fictional home-front characters.** |
| **Dialogue** | **Drama-first:** the story is carried by the characters talking on camera — orders, arguments, jokes, fear, tenderness — like a real Egyptian TV drama. Everyday Egyptian street Arabic of 1973 for each character's home (Cairo, rural Delta, Suez, Upper Egypt), and the real register of an Egyptian army unit («يا فندم», «تمام يا فندم», «إشارة», «خزنة»). Short lines (one close shot each, about 14 words at most), subtext over statement, facts said the way people would really say them. Every line carries its performance (intensity, volume, pace, emotion). Fully vocalized for reading; real people's lines are marked *(dramatized)*. |
| **Music** | **Silence-first.** No score under tension, waiting, or battle — only real sound. Each episode has one **main theme** that appears at a few key moments and returns for the ending. The series main title has its own theme. |
| **Visual focus** | **Intimacy and endurance** at the soldiers' eye level: hands, boots, faces, equipment. Enemy aircraft and tanks are seen from the ground — distant, large, and impersonal. |
| **Light** | Each episode keeps a strict lighting timeline that follows the real hours of the operation. |
| **Period accuracy** | 1967–1973 Egyptian uniforms, web gear, weapons, vehicles, and civilian life must be consistent and checked against references. |

---

## 6. Making it with AI: production rules for writers

AI video is strong at landscapes, action, atmosphere, and faces in silence. Dialogue works shot by shot: each line is recorded in the character's cast voice and lip-synced on a close shot of the speaker (Kling Avatar). Write to that:

1. **Scenes carry the words.** Every beat that has people in it should have them talking to each other — at least one real exchange — unless the silence is the point. Letters in voiceover, radio and narration are seasoning, not the meal. Aim for dialogue in about **a third to half of each act's screen time** (less in battle, more in camps and homes).
2. **One speaker per talking shot, one or two short sentences per line.** Conversations are cut shot / reverse shot, like any TV drama; reactions are separate silent shots. Long speeches are broken by an action or a reply.
3. **Give every main character one strong visual signature** (a scar, glasses, a piece of equipment) so viewers can follow them in dark or dusty shots — and **one verbal signature** (Sayed's dry jokes, Mahmoud's precision, Hassan's few slow words, Adel's teasing).
4. **Plan about 8 clips per minute** — about 350–380 generated clips per 45-minute episode. Each clip is one shot of about 3–10 seconds; talking shots are short.
5. **Reuse locations and lighting setups** within an episode where the story allows it; it makes consistency much easier.
6. **Every screenplay passes the script board before recording:** `./mtower.ps1 script-qa <file>` scores each line for Egyptian dialect, army register, intensity vs situation, character, drama, history/rules and lip-sync length; every beat and every line must reach **8/10** (the same gate as the pictures).

### 6.1 Production engine and tool stack (decided 2026-10-11)

The series is made with an **automated production engine**: Python scripts in `studio/engine/` call the AI tools through their APIs (programmable connections), driven by each episode's JSON shot lists. The user approves at a few checkpoints, mostly by picking the best take. The same engine is reused for every episode.

| Job | Tool (via API) | Role |
|---|---|---|
| Still images: reference sheets and keyframes | **Flux** (Black Forest Labs), plus a **custom character model (LoRA)** trained for each main face | Photoreal period look; the LoRA locks each face across hundreds of shots. Alternative for multi-angle reference generation: Google's image model. |
| Image-to-video clips | **Kling** for most shots; **Google Veo** for a small number of key shots | Image-to-video from approved keyframes, 5–10 seconds per clip |
| Arabic narration, dialogue, letters | **ElevenLabs** | Reads fully vocalized Arabic accurately |
| Model access | **fal.ai or Replicate** (pay per use) | One account and API key for many models; no stack of monthly subscriptions |
| Upscaling and finishing | AI upscaler (e.g., Topaz Video AI) | Sharp final delivery |
| Edit, sound, color, subtitles | **DaVinci Resolve** (free version) | The engine generates a timeline file from the shot list; the editor polishes it |

**Note:** Midjourney was considered but has historically offered no official API, so it cannot be part of an automated engine. Tool availability, model versions, and prices change quickly — they are verified when the engine is built (Phase 2, task 2.3).

### 6.2 Quality and cost rules

1. **Images first, motion second.** Every clip starts from an approved still keyframe.
2. **Animatic before video.** The whole episode is assembled from keyframes, narration, and temporary sound, and watched end to end before any video is paid for.
3. **Drafts cheap, finals premium.** Test with fast, low-cost models; run premium models only on approved shots.
4. **Look test first.** A handful of shots are produced end to end to measure real quality and cost per shot before a full run.
5. **Spending control.** Every platform has a monthly spending cap. The engine estimates the cost before each batch, logs every API call, and asks for approval before spending.
6. **Secrets stay local.** API keys live only in a local `.env` file (ignored by git) and are never pasted into chat or committed.

---

## 7. Recurring series elements

| Element | Description |
|---|---|
| Main title | Black screen, the sound of wind over sand, then «الصَّاعِقَةُ» in white. ~30 seconds, at the end of every teaser. |
| Episode title card | Episode name in Arabic and English over the first image of Act One. |
| Narrator | The same voice in every episode (see §5). |
| Epilogue cards | White text on black: what happened to the men, honors, and the source note. |
| Dedication | Every episode ends with a one-line dedication read by the narrator. |

**Recurring characters:** none for now. The series is an **anthology** — each episode has its own unit and characters, as different real units carried out different operations. A recurring framing character (for example, an instructor teaching these operations to young officers) is an option for later seasons.

---

## 8. Season 1 slate

| # | Episode | Operation | Period | Status |
|---|---|---|---|---|
| 1 | **كَمِينُ رُمَّانَةَ** — *The Romani Ambush* | Captain Hamdi Shalabi's company ambushes an Israeli armored brigade on the Romani road | Oct 6–8, 1973 | **In pre-production** (`ep01_romani/`) |
| 2+ | *To be selected* | See candidate list below | 1967–1973 | Research |

**Candidate operations for later episodes** (first-pass research; each must be researched in depth before development — see `ep01_romani/01_development/research/sources.md` for the source list):

| Candidate | Date | Place | Unit / commander (per sources) | Why it could be an episode | Source confidence |
|---|---|---|---|---|---|
| **Battle of Ras al-Ush** (رَأْسُ الْعُشِّ) | Jul 1–4, 1967 | East-bank road to Port Fuad, ~14 km south of Port Said | Sa'iqa group; 1st Lt. Gaber al-Gazzar (killed), Lt. Abd al-Wahhab al-Zuhairi | The first stand after the June War — a natural **season opener or prequel** | Medium (Egyptian sources only) |
| **The Tabba al-Mashura raid** (إِغَارَةُ التَّبَّةِ الْمَسْحُورَةِ) | Night of Apr 21, 1969 | Israeli strongpoint south of the Little Bitter Lake | Raid party under 1st Lt. Abdu Ahmed Arafa | A tight cross-canal raid to capture a prisoner — a classic commando mission | Medium-low (one source) |
| **Shadwan Island** (مَعْرَكَةُ شَدْوَانَ) | Jan 22, 1970 | Shadwan Island, mouth of the Gulf of Suez | Sa'iqa company, 1st Lt. Muhammad Sharif al-Nu'mani | A defensive battle against an Israeli raid; Egyptian and Israeli accounts strongly conflict — would need careful handling | High that it happened; outcome disputed |
| **The Sudr pass landings** (مَعْرَكَةُ سُدْرٍ) | Oct 6–21, 1973 | Sudr defile, southern Sinai | Sa'iqa battalion, Maj. Mahmoud Abbas; Capt. Rif'at Abd al-Wahhab Amer (killed) | Heliborne landings without fighter cover on the first night of the war — the southern twin of Romani | Medium |
| **The siege of Port Tewfik** (لِسَانُ بُورِ تَوْفِيق) | Oct 6–13, 1973 | Israeli strongpoint at the southern canal entrance | Sa'iqa force, Maj. Zaghloul Muhammad Fathi | A week-long siege ending in surrender before the Red Cross | Medium |
| **The defense of Ismailia** (مَعْرَكَةُ الْإِسْمَاعِيلِيَّةِ) | Oct 18–22, 1973 | Abu Sultan, Serabaeum, Nefisha | 73rd Battalion, 129th Sa'iqa Group, with the 182nd Paratrooper Brigade | Holding the last line against Sharon's division until the ceasefire — a natural **season finale** | High (well documented, including in English) |

**Production focus (decided 2026-10-10):** Episode 1 is made **completely** — through Pre-production and Execution — before Episode 2 is chosen. Episode 1 is also the learning project for the whole pipeline.

**Suggested Season 1 shape (for later discussion):** open with Romani (Episode 1, in development), include Sudr as its southern counterpart, and end with Ismailia. Ras al-Ush could serve as a prequel episode.

---

## 9. Episode development checklist

Every episode goes through the same Phase 1 steps before Pre-production:

1. Research file with sources (`research/`)
2. Episode plan: logline, act structure, runtime budget, fact lock, asset registry (`episode_plan.md`)
3. Character profiles, real vs. composite (`characters.md`)
4. Screenplay: teaser + five acts (`screenplay/`)
5. Executive review and sign-off (`episode_plan.md` §5)
