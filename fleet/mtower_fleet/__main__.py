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

    b = sub.add_parser("batch-qa", help="Image QA over approved MTower keyframes (compares human / MTower / studio)")
    b.add_argument("--production", default="thunderbolt")
    b.add_argument("--episode", default="ep01_romani")
    b.add_argument("--sample", type=int, default=6, help="frames to review, spread across acts (default 6)")
    b.add_argument("--all", action="store_true", help="review every approved frame")
    b.add_argument("--shots", help="comma-separated shot ids to review instead of a sample")
    b.add_argument("--confirm-cost", type=float, default=None,
                   help="spend gate: must be >= the printed estimate (USD) or nothing runs")

    bt = sub.add_parser("beat", help="run every shot of a beat through Wave 1 and save the shot contracts")
    bt.add_argument("--beat-ref", required=True)
    bt.add_argument("--production", default="thunderbolt")
    bt.add_argument("--episode", default="ep01_romani")
    bt.add_argument("--shots", help="comma-separated subset of the beat's shot ids")
    bt.add_argument("--resume", action="store_true",
                    help="reuse the saved beat fact check and skip shots whose contract is already current")
    bt.add_argument("--refresh-research", action="store_true",
                    help="re-run only the beat fact check and apply it to the saved shot contracts "
                         "(use after a policy or ledger change; Script/Director are not re-run)")
    bt.add_argument("--confirm-cost", type=float, default=None,
                    help="spend gate: must be >= the printed estimate (USD) or nothing runs")

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
        from . import store
        saved_to = store.save(shot)
        js = json.dumps(shot.model_dump(), indent=2, ensure_ascii=False)
        print("\n===== SHOT CONTRACT =====")
        print(js)
        print(f"\nsaved: {saved_to}")
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

    elif args.cmd == "batch-qa":
        from pathlib import Path

        from . import batch_qa

        frames = batch_qa.approved_frames(args.production, args.episode)
        if args.shots:
            wanted = {s.strip() for s in args.shots.split(",")}
            frames = [f for f in frames if f["shot_id"] in wanted]
        elif not args.all:
            frames = batch_qa.sample(frames, args.sample)
        estimate = round(len(frames) * batch_qa.EST_PER_REVIEW_USD, 2)
        print(f"Batch Image QA — {len(frames)} approved frame(s): {', '.join(f['shot_id'] for f in frames)}")
        print(f"Estimate: ${estimate:.2f} (≈${batch_qa.EST_PER_REVIEW_USD} per review with references)")
        if args.confirm_cost is None or args.confirm_cost < estimate:
            print(f"Not run. Re-run with --confirm-cost {estimate} to approve this spend.")
            return 0
        results = batch_qa.run(args.production, args.episode, frames)
        out_dir = Path(__file__).resolve().parents[1] / "reports"
        jpath, mpath = batch_qa.write_report(results, out_dir)
        print(f"\nreport: {mpath}\ndata:   {jpath}")

    elif args.cmd == "beat":
        from . import grounding, store

        if args.refresh_research:
            saved = [s for s in store.list_contracts(args.production, args.episode) if s.beat_ref == args.beat_ref]
            if not saved:
                print(f"No saved contracts for beat {args.beat_ref} — run the beat first.")
                return 1
            print(f"Refresh beat {args.beat_ref} fact check → apply to {len(saved)} saved contract(s): "
                  f"{', '.join(s.shot_id for s in saved)}")
            print(f"Estimate: ${BEAT_RESEARCH_EST:.2f} (beat fact check only; Script/Director not re-run)")
            if args.confirm_cost is None or args.confirm_cost < BEAT_RESEARCH_EST:
                print(f"Not run. Re-run with --confirm-cost {BEAT_RESEARCH_EST} to approve this spend.")
                return 0
            orch = Orchestrator()
            g = grounding.load(args.production, args.episode, args.beat_ref)
            beat = orch.research_beat(production=args.production, episode=args.episode, beat_ref=args.beat_ref, g=g)
            bpath = store.save_beat_research(beat, args.beat_ref)
            print("\n===== REFRESHED =====")
            print(f"beat fact check: {len(beat.research)} claims, {len(beat.open_flags)} blocking flag(s), "
                  f"{len(beat.escalations)} escalation(s) · ${beat.cost_usd_total:.3f}  → {bpath}")
            for s in saved:
                before = s.status
                store.save(orch.refresh(s, beat))
                print(f"  {s.shot_id:8} {before:11} → {s.status}")
            return 0

        ids = grounding.beat_shot_ids(args.production, args.episode, args.beat_ref)
        if args.shots:
            wanted = [s.strip() for s in args.shots.split(",")]
            ids = [i for i in ids if i in wanted]
        prior = store.load_beat_research(args.production, args.episode, args.beat_ref) if args.resume else None
        if prior is not None:
            ids = [i for i in ids if not store.is_current(args.production, args.episode, i, args.beat_ref)]
        if not ids:
            print(f"No shots to run for beat {args.beat_ref}" + (" (all contracts current)." if prior else "."))
            return 0
        estimate = round((0 if prior else BEAT_RESEARCH_EST) + len(ids) * SHOT_EST, 2)
        print(f"Beat {args.beat_ref}: {len(ids)} shot(s): {', '.join(ids)}")
        print(f"Estimate: ${estimate:.2f} (" + ("reusing saved beat fact check" if prior
              else f"beat fact check ≈${BEAT_RESEARCH_EST}") + f" + ≈${SHOT_EST} per shot)")
        if args.confirm_cost is None or args.confirm_cost < estimate:
            print(f"Not run. Re-run with --confirm-cost {estimate} to approve this spend.")
            return 0
        orch = Orchestrator()
        saved = []

        def _save(s):
            saved.append(store.save(s))

        def _save_beat(b):
            print(f"  beat fact check saved → {store.save_beat_research(b, args.beat_ref)}", flush=True)

        beat, shots = orch.run_beat(production=args.production, episode=args.episode, beat_ref=args.beat_ref,
                                    shot_ids=ids, on_shot=_save, on_beat=_save_beat, beat_research=prior)
        bpath = store._beat_path(args.production, args.episode, args.beat_ref)
        total = (0 if prior else beat.cost_usd_total) + sum(s.cost_usd_total for s in shots)
        print("\n===== BEAT SUMMARY =====")
        print(f"beat fact check: {len(beat.research)} claims, {len(beat.open_flags)} blocking flag(s) · "
              f"${beat.cost_usd_total:.3f}  → {bpath}")
        for s in shots:
            print(f"  {s.shot_id:8} {s.status:11} critic rounds={sum(1 for c in s.critic):2}  ${s.cost_usd_total:.3f}")
        print(f"total ≈ ${total:.3f} · {len(saved)} contract(s) saved under {saved[0].parent if saved else '-'}")
    return 0


BEAT_RESEARCH_EST = 0.20
SHOT_EST = 0.10


if __name__ == "__main__":
    raise SystemExit(main())
