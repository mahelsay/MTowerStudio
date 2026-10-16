"""CLI: run a beat through the Wave-1 fleet and print the resulting shot contract.

Examples:
  python -m mtower_fleet run --shot 2.4-02 --beat-ref 2.4 \
      --beat "Night: the radio operator decodes a scrap of paper by a red-filtered flashlight, whispering."
  python -m mtower_fleet run --demo
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from .orchestrator import Orchestrator

DEMO = {
    "shot_id": "2.4-02",
    "beat_ref": "2.4",
    "production": "thunderbolt",
    "episode": "ep01_romani",
    "beat": (
        "Night, the Tina Plain salt marsh. Corporal Mahmoud, the radio operator, wades beside Captain Shalabi, the "
        "set strapped high on his back. He decodes a coded reply by red light: the enemy has intercepted their "
        "signal. Shalabi orders radio silence and sets a new compass bearing. (Fallback text only — the orchestrator "
        "uses the locked screenplay beat when the MTower repo is available.)"
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser(prog="mtower_fleet")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a beat through the Wave-1 fleet")
    r.add_argument("--demo", action="store_true", help="use the built-in Episode-1 demo beat")
    r.add_argument("--shot")
    r.add_argument("--beat-ref", default="")
    r.add_argument("--production", default="thunderbolt")
    r.add_argument("--episode", default="ep01_romani")
    r.add_argument("--beat")
    r.add_argument("--notes", default="")
    r.add_argument("--out", help="write the shot contract JSON to this path")

    q = sub.add_parser("qa", help="run Image QA (vision) on an image against a shot intent")
    q.add_argument("--image", required=True, help="local path or https URL of the frame")
    q.add_argument("--shot", default="adhoc")
    q.add_argument("--subject", default="")
    q.add_argument("--action", default="")
    q.add_argument("--setting", default="")
    q.add_argument("--time", default="")
    q.add_argument("--mood", default="")
    q.add_argument("--gate", type=float, default=8.0)

    args = ap.parse_args()

    if args.cmd == "run":
        if args.demo:
            p = DEMO
            shot_id, beat_ref, production, episode, beat = p["shot_id"], p["beat_ref"], p["production"], p["episode"], p["beat"]
        else:
            if not (args.shot and args.beat):
                ap.error("--shot and --beat are required (or use --demo)")
            shot_id, beat_ref, production, episode, beat = args.shot, args.beat_ref, args.production, args.episode, args.beat

        orch = Orchestrator()
        shot = orch.run_shot(shot_id=shot_id, beat=beat, production=production, episode=episode, beat_ref=beat_ref, notes=args.notes)
        js = json.dumps(shot.model_dump(), indent=2, ensure_ascii=False)
        print("\n===== SHOT CONTRACT =====")
        print(js)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(js)
            print(f"\nwritten: {args.out}")

    elif args.cmd == "qa":
        from .agents.image_qa import ImageQAAgent
        from .contract import Shot

        shot = Shot(shot_id=args.shot)
        shot.intent.subject = args.subject
        shot.intent.action = args.action
        shot.intent.setting = args.setting
        shot.intent.time_of_day = args.time
        shot.intent.mood = args.mood
        print(f"Image QA on {args.image}\n  intent: {shot.intent.subject} | {shot.intent.action}")
        result = ImageQAAgent().review(shot, args.image, gate=args.gate)
        print("\n===== IMAGE QA =====")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\ncost≈${shot.cost_usd_total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
