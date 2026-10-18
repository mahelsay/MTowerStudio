# Episode 1 — Teaser trailer and poster plan

**Status:** draft by the director, 2026-10-13 · **Needs:** your sign-off on the concept and the poster pick · **Depends on:** the Look Test (task 2.5) for real video quality and cost

## When

| Item | When | Why then |
|---|---|---|
| **Poster key art** | **Now** (drafts made, see below) | Needs only images, which run on Azure. A poster also locks the series' visual promise early. |
| **Teaser trailer (60–75 s)** | **Right after the Look Test**, before the full episode's video | It reuses keyframes we already have, needs only ~14 video clips (~$15 on Kling O3), and tells us how audiences react before we spend ~$300+ on the whole episode. |
| Full trailer (2 min) | After the episode is cut | Built from the finished episode's best moments. |

## Poster

Three key-art concepts were drafted on Azure (gpt-image-2, high quality, 1024×1536, no text) and each was checked by the QA reviewer; a second round (v2) added the reviewer's corrections. Images: `media/productions/thunderbolt/ep01_romani/marketing/poster/` — v1 `20261013-085051`, v2 `20261013-085957` (open with `./mtower.ps1 review ../../media/productions/thunderbolt/ep01_romani/marketing`; each card shows its QA verdict). Cost: $1.50 for both rounds.

| Concept | Idea | Lead | QA v1 → v2 | Director's note |
|---|---|---|---|---|
| **A · The March** | The captain wading through the moonlit salt marsh, looking back at a file of men stretching to the horizon | Captain Shalabi (ACT-0001) | 6 → 6 | **Recommended.** v2 fixed the rifle in the water and shows the loads; still wants visible mine sacks and slightly shallower water. Strongest likeness and the series' signature image. |
| **B · The Ambush** | A commando from behind, firing a Malyutka from a sand pit at dawn; the lead Centurion burns | (no face) | 5 → 4 | Most "action" but the missile geometry and launcher keep coming out wrong; needs the Malyutka prop model or a manual fix. |
| **C · Home and Front** | The mother holding the letter at dusk; below her gaze, the men crossing the marsh at night | Umm Mostafa (ACT-0007) | 6 → 5 | Most emotional. v2 got the tiny silhouettes right, but her head is too large and enters the title area. |

**Round 3 (2026-10-13, batch `20261013-124617`, after your note on C: "keep only the lower half — soldiers, sky, moon"):**

| Concept | Idea | QA | Director's note |
|---|---|---|---|
| **D · Night Crossing** | C's lower half as its own poster: the file of men wading under a huge moon, wide sky for the title | **9/10** | **Recommended.** Clean, iconic, lots of room for the title. |
| **B3 · The Ambush (RPG)** | B rebuilt around an RPG-7 instead of the Malyutka | 6/10 | Best action version so far; the launcher still needs a fix pass. |
| C2 · Home and Front (edit) | Kontext edit of C v2 to remove the mother | 5/10 | Failed: a ghost of her face stays in the sky. Dropped in favour of D. |
| B4 · loaded RPG (edit) | Edit of B3 to show a loaded warhead | 4/10 | Worse than B3. Dropped. |

**Proposed set of three (one per role, as films usually release):** **A** (character poster — the captain), **D** (world poster — the night crossing), **B3** (action poster — the ambush, after one more fix). Waiting for your pick.

**Title layout (after you pick):** the AI never draws the lettering. The title «الصَّاعِقَةُ», the episode name «كَمِينُ رُمَّانَةَ», the tagline and the credits block are laid out on the chosen art afterwards (System.Drawing with an Arabic display font such as *Aldhabi* or *Sakkal Majalla*, or in a design tool), so the Arabic is always correct.

Tagline options (pick one):

1. «اِثْنَانِ وَأَرْبَعُونَ كِيلُومِتْرًا… لِيَصِلُوا فِي الْمَوْعِدِ.» — *Forty-two kilometres… to arrive on time.*
2. «قِلَّةٌ فِي مُوَاجَهَةِ لِوَاءٍ.» — *A few against a brigade.*
3. «قِصَّةٌ حَقِيقِيَّةٌ مِنْ حَرْبِ أُكْتُوبَر ١٩٧٣.» — *A true story from the October War, 1973.*

## Teaser trailer — 60–75 s outline

Built from shots that already have keyframes (after `autofix`), plus three title cards. Narration from the episode's VO (Azure Speech for the draft, ElevenLabs for the final).

| # | Beat | Shots | s | Sound / VO |
|---|---|---|---|---|
| 1 | Black. A radio voice | card | 3 | «هُنَا الْقَاهِرَةُ…» (1.10) |
| 2 | The red cabin | T.2-01, T.2-02, T.2-05 | 8 | rotor drone, one heartbeat |
| 3 | Six Mi-8s at dusk | 1.11-03, 1.11-06 | 6 | rotors rise |
| 4 | Jump into the marsh | 2.1-02 | 4 | splash |
| 5 | The march | 2.5-01, 2.5-03, 2.5-07 | 10 | VO 2.5 first line «عشرين كِيلُو فِي المَيَّة المَالْحَة وِالطِّين» (Egyptian narration, D-19) |
| 6 | Home | 1.3-02, 1.5-01, 2.7-04 | 8 | music enters; a letter line |
| 7 | Card | «١٢١ مُقَاتِلًا» / «لِوَاءٌ مُدَرَّعٌ» | 4 | low hit |
| 8 | The column | 3.4-05, 3.12-01 | 6 | tank tracks |
| 9 | The order | 3.7-01 | 5 | the captain's single word |
| 10 | The ambush | 1.6-03 (Malutka), 3.8-04, 4.5-03 | 8 | missile launch, impact, silence |
| 11 | The mother's face | 5.5-01 | 3 | breath |
| 12 | Title | «الصَّاعِقَةُ» · «كَمِينُ رُمَّانَةَ» | 5 | final hit |
| 13 | Date card | «قَرِيبًا» | 3 | — |

**Cost estimate:** ~14 clips × 5 s × $0.14 = **~$10–15** on Kling O3 via fal (needs the fal top-up), + narration cents, + music/SFX (library or licensed).

## Next steps

1. You pick a poster concept (or ask for variations); the director lays out the title.
2. After the Look Test: lock the trailer shot list above, render the clips, cut a draft with the Azure narrator.
