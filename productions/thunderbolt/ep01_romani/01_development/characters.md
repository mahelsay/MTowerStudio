# كَمِينُ رُمَّانَةَ — Character Profiles

**Episode:** 1 — «كَمِينُ رُمَّانَةَ» · **Roadmap task:** 1.5 · **Status:** Locked v1.0 (2026-10-10) · **Feeds:** Phase 2 task 2.1 (reference sheets)

## How to read this file

A **character profile** fixes who each person is, what they do in the story, how they look, and how they sound, so that every scene and every AI-generated image stays consistent.

Each character has a **type**:

| Type | Meaning | Rule |
|---|---|---|
| **REAL — named** | A real historical person named in our source | Show only actions stated in the transcript. No invented private life, family, or backstory. Reconstructed dialogue is marked *(dramatized)*. |
| **REAL — unnamed role** | A real role (e.g., the helicopter pilot) whose identity we don't know | Never give them a name. Show only the role's documented actions. |
| **COMPOSITE** | A fictional character built to represent the real men of the company | Clearly fictional. Names are common Egyptian first names, not real individuals. Their personal moments may be invented, but they never take credit for a specific documented act attributed to a real person. |

The **canonical visual descriptor** is the exact English wording that Phase 2 prompts must reuse word for word. All descriptors are provisional until the character reference sheets are approved.

> **Studio library (2026-10-11):** each character is now played by a reusable virtual actor from `studio/library/actors/actors.json`. The actor defines the face; this file defines the character. The *canonical visual descriptors* below are kept for reference; the engine now builds prompts from the actor card + wardrobe + the character additions in `../02_preproduction/casting.json`. 🔒 = actor locked to this role (real person or real role).

---

## 1. Egyptian Sa'iqa company (قُوَّاتُ الصَّاعِقَةِ)

### C-01 — النَّقِيبُ حَمْدِي شَلَبِي · Captain Hamdi Shalabi
**Type:** REAL — named · **Asset ID:** CMD-01 · **Appears:** Teaser, Acts 1–5 · **Played by:** ACT-0001 Tarek Selim 🔒 (studio library)

| Field | Detail |
|---|---|
| Role | Commander, 1st Company, 183rd Sa'iqa Battalion; leads the whole 122-man force |
| Rank on screen | Captain (نَقِيب) in every mission scene. Promotion to major and the Star of Military Honor appear only in the epilogue. |
| Age | Late 20s to early 30s *(provisional — verify)* |
| What the transcript tells us | His company won every pre-war unit competition. He takes the sealed envelope, waits, and opens it on order. He accepts the squadron leader's early drop, navigates 42 km by compass, imposes radio silence, deploys his three platoons across 3 km, orders barrel pits, lets the advance guard and a full battalion pass, orders the attack, holds until ammunition runs out, buries the martyrs, and leads the survivors home on foot over five days. |
| Character in one line | A quiet decision-maker who carries every choice alone and spends his words carefully. |
| Behavior on screen | Few words, low voice, hand signals more than speech. Checks the map twice. Counts his men by touch. Never shows panic. Before the battle he steadies his men in a few plain words: «إِحْنَا قُلَيِّلِينْ، وِهُمَّ كْتِيرْ… بَسّْ هُمَّ مَا يِعْرَفُوشْ إِحْنَا فِينْ». (No Quran is quoted anywhere in the series — user rule, 2026-10-14.) |
| Arc | **Waiting** (sealed envelope) → **deciding** (landing, silence, letting the battalion pass, the order to fire) → **paying the price** (burying his men) → **bringing them home**. |
| Voice | Egyptian colloquial Arabic, calm and low. Lines are short. |
| Canonical visual descriptor (provisional) | *Egyptian commando captain, about 30 years old, lean wiry build, short black hair, trimmed black mustache, sun-darkened olive skin, calm deep-set dark eyes, 1973 Egyptian sand-khaki field uniform, captain's three-star rank insignia on the shoulder straps, Soviet-pattern chest rig, compass on a lanyard* |
| Open items | Find reference photos of Hamdi Shalabi before Phase 2. If photos exist, the descriptor must be rewritten to match them. Confirm the captain's insignia. |

### C-02 — الرَّقِيبُ سَيِّد · Sergeant Sayed
**Type:** COMPOSITE · **Asset ID:** CMD-09 · **Appears:** Teaser, Acts 1–5 · **Played by:** ACT-0002 Hazem Abdallah (studio library)

| Field | Detail |
|---|---|
| Role | Veteran platoon sergeant in Mostafa's platoon |
| Age | Mid-30s |
| Character in one line | The company's backbone: steady, dry, protective of the young men. |
| Behavior on screen | Watches faces, not the horizon. Stops trouble with a hand on a shoulder rather than a word. |
| Arc | Act 1: teaches Mostafa to strap his rocket bag ("Afraid? … So am I."); before dawn on Oct 6 he writes a letter to his wife Fatma and gives it to Mostafa to deliver if he does not return. Act 2: pulls Mostafa out of the brine. Act 3: stops Mostafa from firing too early as the enemy battalion passes. Act 4: when the rockets run out, he is among the men who run at the tanks with anti-tank grenades, and he is martyred. Act 5: his letter reaches Fatma by Mostafa's hand. |
| Home | Originally from Suez. His family has been displaced since 1967 and lives in one room in Shubra, Cairo (see C-13, C-14). |
| Voice | Egyptian colloquial, gravelly, sparing. |
| Canonical visual descriptor (provisional) | *Egyptian commando sergeant, mid-30s, broad shoulders, square jaw, close-cropped black hair greying at the temples, thick black mustache, weathered sun-lined face, 1973 Egyptian sand-khaki field uniform, sergeant's chevrons, AK-47 with fixed wooden stock* |

### C-03 — الْجُنْدِيُّ مُصْطَفَى · Private Mostafa
**Type:** COMPOSITE · **Asset ID:** CMD-09 · **Appears:** Teaser, Acts 1–5 · **Played by:** ACT-0003 Karim Nour (studio library)

| Field | Detail |
|---|---|
| Role | RPG-7 assistant gunner; the youngest man the audience follows |
| Age | 19–20 |
| Character in one line | The audience's eyes: afraid, determined, and changed by what he survives. |
| Behavior on screen | Silent prayer in the cabin. Salt in his eyebrows on the march. Finger tightening on the trigger as the battalion rolls past. |
| Arc | **Fear** (Acts 1–2: "Afraid? — No."; falls in the brine but keeps the launcher dry) → **discipline** (Act 3: learns to wait) → **endurance** (Acts 4–5: survives, carries Sayed's rifle and Sayed's letter on the five-day walk home) → **duty** (Act 5: delivers the letter to Fatma). |
| Home | A village in Menoufia, in the Nile Delta. Lives with his widowed mother (C-11) and younger sister (C-12). Writes letters home that his sister reads aloud. |
| Voice | Egyptian colloquial (rural Menoufia); short, earnest lines, braver than he feels. Drama rewrite (2026-10-15): he talks with Sayed, Adel and the others on camera. |
| Canonical visual descriptor (provisional) | *Young Egyptian commando private, about 19, slim, boyish clean-shaven face, short black hair, large dark eyes, 1973 Egyptian sand-khaki field uniform slightly too big for him, RPG-7 rocket carrier bag on his back* |

### C-04 — الْعَرِيفُ مَحْمُود · Corporal Mahmoud
**Type:** COMPOSITE · **Asset ID:** CMD-09 · **Appears:** Acts 1–5 · **Played by:** ACT-0004 Sherif Mansour (studio library)

| Field | Detail |
|---|---|
| Role | Company radio operator; always within arm's reach of Shalabi |
| Age | Mid-20s |
| Character in one line | The man who carries the company's only voice — and the order to keep it silent. |
| Arc | Act 2: decodes the warning that the company's signal was intercepted (Beat 2.4). Act 3: relays "do not engage" and then the order to fire; runs with Shalabi between the platoons. Act 4: the radio carries no news; he walks home with the dead set on his back. |
| Voice | Egyptian colloquial, whispered on the radio. |
| Canonical visual descriptor (provisional) | *Egyptian commando corporal, mid-20s, medium build, narrow face, thin black mustache, wire-rimmed glasses taped at the hinge, 1973 Egyptian sand-khaki field uniform, Soviet-pattern manpack radio on his back with a whip antenna, handset clipped to the chest rig* |

### C-05 — رَقِيبُ الْمُهَنْدِسِينَ حَسَن · Engineer Sergeant Hassan
**Type:** COMPOSITE · **Asset ID:** CMD-09 / CMD-12 · **Appears:** Acts 1–4 · **Played by:** ACT-0013 Mahmoud Abdel-Rahim (studio library; recast from ACT-0005 on 2026-10-12 for a clearer Sa'idi look)

| Field | Detail |
|---|---|
| Role | Leader of the attached engineer section; breaches the minefield; then leads one of the small rear-security groups |
| Age | Early 30s |
| Character in one line | Patient hands: the slowest, most careful man in the company — on purpose. |
| Arc | Act 2: crawls ahead with probe and tape so the company can cross the minefield (Beat 2.10); supervises the hiding of the excavated soil so the barrel pits are invisible from the air, then takes a rear-security group. Act 3: he is the first to hear the Israeli half-tracks coming in behind the ambush (Beat 3.13). Act 4: his group fights the landed Israeli company and destroys it; Hassan is martyred holding the rear — only his tape reel is left in the sand (Beat 4.1). |
| Voice | Very few words, Upper-Egyptian (Sa'idi) colour: the slowest, calmest voice in the company; mostly hand signals. Drama rewrite (2026-10-15): his first line is the deadpan answer to Adel about the Malutka wire (1.6). |
| Canonical visual descriptor (provisional) | *Egyptian army engineer sergeant, early 30s, compact build, shaved head under a cloth cap, short black beard, calm focused expression, 1973 Egyptian sand-khaki field uniform, steel mine probe in hand, reel of white marking tape strapped to his back* |

### C-06 — الْجُنْدِيُّ عَادِل · Private Adel
**Type:** COMPOSITE · **Asset ID:** CMD-09 / CMD-10 · **Appears:** Acts 1–4 · **Played by:** ACT-0006 Amr Fahmy (studio library)

| Field | Detail |
|---|---|
| Role | Malutka (AT-3 Sagger) missile operator in the attached anti-tank platoon |
| Age | Early 20s |
| Character in one line | The marksman: calm at the control box when everyone else is shouting. |
| Arc | Act 2: carries a missile case through the salt with a partner, never lowering it. Act 3: guides the missile that stops the lead tank, and keeps firing through the long hours of the battle. Act 4: fires his last missile, then picks up an anti-tank grenade. |
| Voice | Egyptian colloquial (Delta). The unit's dry joker — teases Mostafa, jokes when he is scared — and dead calm at the control box. Drama rewrite (2026-10-15): speaks in 1.1, 1.6, 1.7, 1.9, 1.11 and onward. |
| Canonical visual descriptor (provisional) | *Egyptian anti-tank missile operator, early 20s, tall and thin, long face, neat short black hair, small scar through the left eyebrow, 1973 Egyptian sand-khaki field uniform, kneeling over a Malutka suitcase launcher with its control box and periscope sight* |

---

## 2. Other Egyptian roles

### C-07 — Commander of Sa'iqa Forces
**Type:** REAL — named in the transcript (Maj. Gen. Nabil Shukri), **unnamed on screen** until verified · **Appears:** Beat 1.4 · **Played by:** ACT-0011 Farouk El-Desouky 🔒 (studio library)

| Field | Detail |
|---|---|
| Role | Hands Shalabi the sealed envelope on Oct 5 |
| On screen | One short exchange («جَاهِزْ يَا حَمْدِي؟»). Seen mostly in lamp-light; respectful, formal. |
| Canonical visual descriptor (provisional) | *Senior Egyptian army officer, about 50, solid build, greying hair, clipped grey mustache, 1973 Egyptian khaki service uniform with general officer's insignia and red collar tabs *(verify)*, standing in a lamp-lit command tent* |

### C-08 — Mi-8 Squadron Leader
**Type:** REAL — unnamed role · **Appears:** Beats T.3, 2.1–2.2 · **Played by:** ACT-0012 Magdy Riad 🔒 (studio library)

| Field | Detail |
|---|---|
| Role | Lead pilot of the six-helicopter formation |
| On screen | Sees the Phantoms on radar and insists on dropping the company early: «مُهِمِّتِي أَوَصَّلَكْ… وَأَحَافِظْ عَلَى حَيَاتَكْ». Never named. |
| Canonical visual descriptor (provisional) | *Egyptian Air Force helicopter pilot, late 30s, flight helmet with boom microphone, olive flight suit, face lit green by Mi-8 cockpit instruments* |

### N-01 — The Narrator · الرَّاوِي (old Hamdi Shalabi)

| Field | Detail |
|---|---|
| Type | Off-screen voice: **Hamdi Shalabi himself, in his late seventies, remembering** (drama-first direction, D-20/D-21, 2026-10-13). Speaks in the first person, only about what he lived and what is documented; never over the fictional home front. |
| Language | Everyday Egyptian Arabic — `../03_production/voice/narration_hamdi.md` (22 short beats, about a third of the earlier documentary narration). The screenplay VO (formal Arabic) stays the source of truth for facts. |
| Delivery | Intimate, plain, an old man telling his grandchildren; the memories still move him (performance per beat in the script). Not a documentary reader. |
| Voice | Cast `N-01` in `../02_preproduction/production_config.json` → `voice_cast` (gpt-audio-1.5, chosen by audition). See `../03_production/voice/performance_guide.md`. |

---

## 3. The home front (B-plot)

All four are **COMPOSITE / fictional**. They exist so the audience feels what the operation meant to the families of the real men. Per the series bible (§4.2), only composite characters have families on screen, and they never know more than a real family would have known at the time. They are told mostly through images, letters read in voiceover, radio, and short lines.

### C-11 — أُمُّ مُصْطَفَى · Umm Mostafa
**Type:** COMPOSITE · **Appears:** Beats 1.3, 1.8, 1.12, 3.2, 5.3, 5.5 · **Played by:** ACT-0007 Souad Roshdy (studio library)

| Field | Detail |
|---|---|
| Who | Mostafa's widowed mother in a village in Menoufia (Nile Delta). Bakes bread in a clay oven; cannot read. |
| Age | Mid-40s, looks older |
| Character in one line | Strength that never speaks about itself. |
| Arc | Hears her son's letter read aloud (1.3) → sets an empty plate for him at the Ramadan iftar on Oct 6 (1.12) → asks "And Mostafa?" when the village celebrates the crossing (3.2) → holds his last letter not knowing if he is alive (5.3) → touches his face when he comes home (5.5). |
| Voice | Rural Egyptian colloquial; very few words. |
| Canonical visual descriptor (provisional) | *Egyptian village woman in her mid-40s, strong weathered face, deep-set dark eyes, black galabeya and long black headscarf (tarha), flour on her hands, standing in a mud-brick courtyard beside a clay bread oven, Nile Delta village, 1973* |

### C-12 — زَيْنَب · Zeinab
**Type:** COMPOSITE · **Appears:** Beats 1.3, 1.8, 1.12, 3.2, 5.3, 5.5 · **Played by:** ACT-0008 Malak Samy (studio library)

| Field | Detail |
|---|---|
| Who | Mostafa's sister, 12. Goes to school; reads his letters aloud to their mother. |
| Character in one line | The family's voice and its hope. |
| Arc | Reads the letter (1.3) → runs home with the news "They crossed!" (3.2) → reads the last letter (5.3) → sees Mostafa first and runs to him (5.5). |
| Visual signature | Two long braids; always carrying something (a letter, a bread tray, a water jar). |
| Canonical visual descriptor (provisional) | *Egyptian village girl, 12 years old, thin, bright eyes, two long black braids, faded blue cotton dress, barefoot, Nile Delta village, 1973* |

### C-13 — فَاطِمَة · Fatma
**Type:** COMPOSITE · **Appears:** Beats 1.5, 1.10, 2.7, 3.10, 4.8, 5.6 · **Played by:** ACT-0009 Nadia Fouad (studio library)

| Field | Detail |
|---|---|
| Who | Sayed's wife, about 30. Displaced from Suez since 1967, living in one room in Shubra, Cairo; earns a living as a seamstress. |
| Character in one line | She has been waiting to go home for six years; now she waits for her husband. |
| Arc | "When your father brings it back" (1.5) → stops sewing at the radio announcement but does not go to the window (1.10) → a sleepless first night (2.7) → pulls Ali in from playing war (3.10) → doesn't answer "When is Baba coming?" (4.8) → reads Sayed's letter and does not cry in front of Ali, as he asked (5.6). |
| Voice | Cairene-Suez Egyptian colloquial; few words. |
| Visual signature | Foot-pedal sewing machine; a thimble on her finger. |
| Canonical visual descriptor (provisional) | *Egyptian woman about 30, slim, composed, tired dark eyes, hair under a simple patterned headscarf, modest 1970s knee-length dress with long sleeves, thimble on her finger, sitting at a black Singer-style foot-pedal sewing machine in a small room with blue-painted blackout windows, Cairo, 1973* |

### C-14 — عَلِيّ · Ali
**Type:** COMPOSITE · **Appears:** Beats 1.5, 1.10, 2.7, 3.10, 4.8, 5.6 · **Played by:** ACT-0010 Youssef Mamdouh (studio library)

| Field | Detail |
|---|---|
| Who | Sayed and Fatma's son, 8. Too young to remember Suez. |
| Character in one line | The future the men are fighting for — and the question nobody can answer. |
| Arc | Asks when they will go back to Suez (1.5) → scratches a hole in the blue window paint to see the celebrations (1.10) → plays commandos and tanks in the alley (3.10) → asks "When is Baba coming?" (4.8) → looks up at Mostafa, who salutes him (5.6). |
| Visual signature | A small tin toy airplane he is never without. |
| Canonical visual descriptor (provisional) | *Egyptian boy, 8 years old, short black hair, big curious eyes, striped cotton shirt and shorts, holding a small tin toy airplane, Cairo, 1973* |

---

## 4. Israeli forces

The Israeli side is shown through machines, radio voices, and distant figures. Nobody on the Israeli side is mocked or caricatured; they are a professional, dangerous enemy.

### C-09 — Assaf Yagouri · עסף יגורי
**Type:** REAL — named · **Appears:** Beat 3.4

| Field | Detail |
|---|---|
| Role | Commander of the Israeli tank battalion that passes through the ambush zone before the main column |
| On screen | Seen only at a distance, in a tank commander's hatch, as his battalion passes the ambush unengaged (both the podcast and Israeli-sourced accounts agree on this). **No dialogue.** The podcast's claim that he refused a recall is contradicted by Israeli-sourced accounts (he wanted to turn back and attack), so it is not shown. |
| Open items | ⚠️ His unit and role are flagged for verification (H-13). If unverified, he can remain unnamed on screen. |

### C-10 — Israeli brigade commander
**Type:** REAL — unnamed role (per Israeli-sourced accounts: Col. Natan "Natke" Nir, 217th Brigade — not named on screen) · **Appears:** Beat 3.12 · Radio voice only.

### Israeli ensemble (non-individual)

| Group | Notes |
|---|---|
| Tank crews | 1973 IDF olive-drab coveralls, CVC tanker helmets; seen in hatches and turrets |
| Reconnaissance aircraft crew | Never seen; only the aircraft (AIR-04) |
| Infantry on half-tracks (Shaked unit, per Israeli sources) | 1973 IDF olive uniforms, helmets with netting, FN FAL / Uzi weapons *(verify)*; Beats 3.13, 4.1 |
| Infantry on the bus | Seen only as the bus passes and is hit (ARM-06) |

---

## 5. Ensemble consistency rules

1. **Faces never drift.** C-01 to C-06 and C-11 to C-14 each get a locked reference sheet (front, ¾, profile; day and night) in Phase 2, reused for every shot.
2. **Wear states follow the story** (see CMD-02): clean (Act 1) → mud-soaked (Tina) → salt-crusted (march) → sand-caked (dunes and Act 3) → battle-worn (Acts 3–4) → gaunt and sunburned (five-day walk) → clean post-war uniform (Mostafa, November 1973).
3. **Each composite has one visual signature** so viewers can tell them apart in dark or dusty shots: Sayed — grey temples and thick mustache; Mostafa — oversized uniform and boyish face; Mahmoud — taped glasses and radio antenna; Hassan — shaved head and tape reel; Adel — eyebrow scar and the Malutka; Umm Mostafa — black tarha and flour on her hands; Zeinab — two braids; Fatma — sewing machine and thimble; Ali — tin toy airplane.
4. **Two worlds, two palettes.** The desert is sand, salt, and night blue; the village is green and gold; the Cairo flat is filtered through blue-painted glass. Keep these palettes strict so viewers always know where they are.
5. **Recurring props carry the story:** Mostafa's letter, Sayed's letter (clean → salt- and sand-stained), Sayed's photo, Hassan's tape reel, Ali's tin airplane.
6. **Background commandos** (the rest of the 122) share the same uniform and gear rules but have no locked faces.
