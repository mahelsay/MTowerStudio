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
        "Night on the canal embankment. Corporal Mahmoud, the radio operator, crouches in deep shadow decoding a "
        "scrap of paper by the dim red glow of a red-filtered flashlight that glints on his taped wire-rimmed "
        "glasses. He whispers the decoded message. Tense, hushed."
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
