"""Episode 1 poster key-art drafts on Azure gpt-image-2 (no text; titles are laid out afterwards), then a QA review each.

Run from studio/engine:  python ../../productions/thunderbolt/ep01_romani/03_production/marketing/poster_drafts.py
"""
import sys
from datetime import datetime
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[5] / "studio" / "engine"
sys.path.insert(0, str(ENGINE))

from mtower import costs, qa  # noqa: E402
from mtower.library import Library  # noqa: E402
from mtower.production import Production  # noqa: E402
from mtower.providers.azure import AzureClient, usage_cost  # noqa: E402
from mtower.settings import load_env, media_root, write_json  # noqa: E402

load_env()
lib, prod = Library.load(), Production.load("thunderbolt/ep01_romani")
anchor = lambda aid: media_root() / lib.actors[aid]["anchor"]["media_path"]  # noqa: E731
props = media_root() / "library" / "props"

COMMON = ("Photorealistic vertical theatrical movie poster key art for a historical war drama set in October 1973, "
          "shot on 35mm film with anamorphic lenses, natural grain, restrained period colour. Absolutely no text, letters, "
          "titles, logos or watermarks anywhere: the title is added later, so keep the top quarter of the picture calm "
          "(sky or darkness) for it. Egyptian Sa'iqa commandos of 1973: sand-khaki field uniforms, bare-headed with short black "
          "hair, Soviet-pattern canvas chest rigs, AKM rifles with wooden stocks; nothing modern. Natural human anatomy: heads "
          "life-size for their bodies and centred on the neck, faces lit by the scene's own light, nobody looks into the "
          "camera. Everything at true real-world scale; one consistent perspective.")

CONCEPTS = {
    "A_the_march": {
        "refs": [anchor("ACT-0001")],
        "prompt": COMMON + " Night, lit only by moonlight and starlight, deep blue-black palette. In the lower foreground, "
                  "the captain — the man in the attached casting portrait, exactly the same face and mustache — wades "
                  "through a vast flat salt marsh: white salt crust over black mud, the brine only at mid-shin, never above the "
                  "knee. He looks back over his shoulder along a long single file of commandos that stretches behind him to the "
                  "horizon, the men carrying RPG-7 launchers, Malyutka missile suitcases and sacks of mines held clear of the "
                  "water. Salt dried white on their uniforms. A vast starry sky above; on the far horizon a faint orange glow of "
                  "war. Epic, quiet, determined.",
        "brief": "Poster concept A 'The March': the captain (ACT-0001) in the lower foreground wading through the shin-deep "
                 "Tina Plain salt marsh at night, looking back over his shoulder at a long file of commandos to the horizon, "
                 "carrying RPG-7s, Malyutka cases and mines above the water; starry sky; empty top quarter for the title; no text.",
    },
    "B_the_ambush": {
        "refs": [props / "PRP-0003_malyutka-at3-sagger" / "references" / "ref_02_launcher_on_case.png",
                 props / "PRP-0003_malyutka-at3-sagger" / "references" / "ref_01_soldier_scale.png"],
        "prompt": COMMON + " Early morning, low sun through drifting dust and black smoke, amber haze. Foreground: an "
                  "Egyptian commando seen from behind and slightly to the side, his face not visible, lying in a shallow sand "
                  "pit behind a deployed 9M14 Malyutka (AT-3 Sagger) suitcase launcher exactly like the attached reference "
                  "photos (use them only for the weapon's shape and size), his hand on the small control box, a missile "
                  "streaking away with a thin bright trail. In the middle distance, on a desert road, a column of Israeli "
                  "Centurion tanks; the lead tank hit and burning, black smoke rising into the sky. Low dunes all around. "
                  "Tension: the moment before everything changes.",
        "brief": "Poster concept B 'The Ambush': a commando from behind (face not visible) firing a Malyutka (AT-3 Sagger) "
                 "suitcase missile from a sand pit at dawn; a column of Israeli Centurion tanks on the road, the lead tank burning; "
                 "smoke rising; empty top quarter for the title; no text.",
    },
    "C_home_and_front": {
        "refs": [anchor("ACT-0007")],
        "prompt": COMMON + " A double image that blends at the horizon. Upper half: an Egyptian village mother in 1973 — the "
                  "woman in the attached casting portrait, exactly the same face, her hair covered by a dark headscarf, a "
                  "modest long dark village dress — stands in the warm dusk light of a Nile Delta mud-brick courtyard, holding a "
                  "folded letter to her chest and looking toward the distant horizon, not at the camera. Lower half: far away "
                  "beneath her gaze, small silhouettes of a single file of commandos crossing a moonlit salt marsh at night. "
                  "Warm dusk gold above fading into night blue below. Intimate and epic at once.",
        "brief": "Poster concept C 'Home and Front': the mother (ACT-0007, headscarf, modest dress) at dusk in a Delta courtyard "
                 "holding a letter, looking to the horizon; below, small silhouettes of commandos marching across a moonlit "
                 "salt marsh; the two halves blend at the horizon; empty top quarter for the title; no text.",
    },
    "D_night_crossing": {
        "refs": [],
        "prompt": COMMON + " Night. A huge calm sky fills the upper two thirds of the picture: deep blue-black, thick with stars, "
                  "a bright full moon low over the horizon. Below, a vast flat salt marsh, white salt crust and sheets of shallow "
                  "water that mirror the moon and the stars. Far away, small dark silhouettes of a long single file of "
                  "bare-headed commandos cross the marsh from left to right, the water only at their shins, rifles, RPG "
                  "launchers and missile cases raised against the moonlight; their reflections trail beneath them. Silence, "
                  "distance, endurance. Moonlight only, cold blue, fine film grain.",
        "brief": "Poster concept D 'The Night Crossing' (from the user's note on C: keep only the lower half): a huge starry "
                 "sky with a low full moon; far below, small silhouettes of a single file of commandos crossing a shin-deep "
                 "moonlit salt marsh, weapons raised, reflections in the water; empty top quarter for the title; no text.",
    },
    "B3_the_ambush": {
        "refs": [],
        "prompt": COMMON + " Late afternoon, low sun through drifting dust and black smoke. Over the shoulder of an Egyptian "
                  "commando seen from behind (his face not visible), kneeling in a shallow sand pit at the edge of low dunes, "
                  "an RPG-7 launcher on his right shoulder, aimed straight at a desert road below. On the road, a column of "
                  "Israeli Centurion tanks; the lead tank is hit and burning, thick black smoke rising into the sky above the "
                  "column. The commando, the launcher and the burning tank line up clearly. Grit, heat, courage.",
        "brief": "Poster concept B3 'The Ambush' (RPG version): over the shoulder of a kneeling commando (face not visible) "
                 "aiming an RPG-7 at a column of Israeli Centurion tanks on a desert road, the lead tank burning; smoke "
                 "rising; empty top quarter for the title; no text.",
    },
}

client = AzureClient()
m = costs.model("image_compose")
review = costs.model("qa_review")
# v2 corrections from the QA review of the first drafts (2026-10-13)
FIXES = {
    "A_the_march": " Corrections: the brine reaches only halfway up the shins, the men's knees and thighs are clearly above the "
                   "water; the captain's AKM is slung on his shoulder with the muzzle pointing up, nothing touches the water; "
                   "the men behind him clearly carry Malyutka suitcases and RPG-7 tubes on their shoulders.",
    "C_home_and_front": " Corrections: the commandos below are tiny distant silhouettes, no bigger than a fingernail in the frame, "
                        "and both scenes share one horizon line where dusk gold fades into night.",
    "B_the_ambush": " Corrections: the Malyutka launcher is small, knee-high, sitting on its opened suitcase lid; only one "
                    "missile, already in flight; no second missile left on the rail.",
}
wanted = [a for a in sys.argv[1:] if not a.startswith("--")]
v2 = "--v2" in sys.argv
CONCEPTS = {k: ({**v, "prompt": v["prompt"] + FIXES.get(k, "")} if v2 else v) for k, v in CONCEPTS.items() if not wanted or k in wanted}
out = media_root() / "productions" / prod.key / "marketing" / "poster" / datetime.now().strftime("%Y%m%d-%H%M%S")
out.mkdir(parents=True, exist_ok=True)
files, spent, items = [], 0.0, []
for name, c in CONCEPTS.items():
    try:
        res = client.images(m["model_id"], c["prompt"], [Path(r) for r in c["refs"]], 1, "1024x1536", "high", "png")
    except Exception as err:  # noqa: BLE001
        print(f"  ! {name}: {str(err)[:300]}")
        continue
    cost = usage_cost(res.usage, m["pricing_per_m_tokens"])
    spent += cost
    path = out / f"poster_{name}.png"
    path.write_bytes(res.images[0])
    files.append(path.name)
    items.append({"target": name, "prompt": c["prompt"], "files": [path.name], "seeds": [], "request_ids": [res.request_id],
                  "cost_usd_estimate": cost, "references": [Path(r).name for r in c["refs"]]})
    print(f"  ✓ {name}: ${cost:.3f}")
    item = qa.Item("poster", name, path, c["brief"] + "\nThis is a vertical 2:3 poster: the 16:9 frame rule does NOT apply.",
                   [(f"reference {Path(r).name}", Path(r)) for r in c["refs"]], "candidate")
    verdict = qa.review(client, review, item, prod.config.get("qa", {}))
    write_json(item.qa_path, verdict)
    spent += verdict["cost_usd"]
    print(f"    QA {verdict['verdict']} {verdict['score']}/10: {verdict['summary'][:300]}")
write_json(out / "manifest.json", {"kind": "poster", "target": "ep01 poster drafts", "model_id": f"azure/{m['model_id']}",
                                   "prompt": "three key-art concepts (see items)", "files": files, "items": items})
costs.record({"production": prod.key, "provider": "azure", "kind": "poster", "target": "ep01 poster drafts",
              "model_id": m["model_id"], "units": len(files), "unit": "image", "cost_usd": round(spent, 4), "out_dir": str(out)})
print(f"Saved in {out} · spent ${spent:.2f}")
