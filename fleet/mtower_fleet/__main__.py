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

    dz = sub.add_parser("design", help="Wave 2: design prepped shots (casting, wardrobe, makeup, set, camera, stunt)")
    dz.add_argument("--beat-ref", required=True)
    dz.add_argument("--production", default="thunderbolt")
    dz.add_argument("--episode", default="ep01_romani")
    dz.add_argument("--shots", help="comma-separated subset of the beat's shot ids")
    dz.add_argument("--redo", action="store_true", help="also re-design shots that are already designed")
    dz.add_argument("--confirm-cost", type=float, default=None,
                    help="spend gate: must be >= the printed estimate (USD) or nothing runs")

    ls = sub.add_parser("lessons", help="Learning Keeper: studio memory (harvest / distill / show / approve / retire)")
    ls.add_argument("action", choices=("status", "harvest", "distill", "show", "approve", "retire", "advise"))
    ls.add_argument("ids", nargs="*", help="lesson ids for approve/retire; shot id for advise")
    ls.add_argument("--status", choices=("rule", "candidate", "retired"), help="show: filter by status")
    ls.add_argument("--batches", type=int, help="distill: at most N batches")
    ls.add_argument("--reason", default="", help="retire: why")
    ls.add_argument("--production", default="thunderbolt")
    ls.add_argument("--episode", default="ep01_romani")
    ls.add_argument("--confirm-cost", type=float, default=None,
                    help="spend gate for distill: must be >= the printed estimate (USD) or nothing runs")

    ca = sub.add_parser("cast-audit", help="Phase D: vision audit of every library actor (anchor + training set + fit)")
    ca.add_argument("ids", nargs="*", help="actor ids (default: all)")
    ca.add_argument("--production", default="thunderbolt")
    ca.add_argument("--episode", default="ep01_romani")
    ca.add_argument("--confirm-cost", type=float, default=None,
                    help="spend gate: must be >= the printed estimate (USD) or nothing runs")

    rd = sub.add_parser("render", help="Render bridge: designed shots → keyframe → Image QA (+ lessons) → fix loop")
    rd.add_argument("--beat-ref", required=True)
    rd.add_argument("--production", default="thunderbolt")
    rd.add_argument("--episode", default="ep01_romani")
    rd.add_argument("--shots", help="comma-separated subset of the beat's shot ids")
    rd.add_argument("--rounds", type=int, default=2, help="fix rounds after the first render (default 2)")
    rd.add_argument("--redo", action="store_true", help="also re-render shots already composed")
    rd.add_argument("--continue", dest="resume", action="store_true",
                    help="continue the fix loop of render_review shots from their best render and its verdict")
    rd.add_argument("--brief", action="store_true", help="free: print each shot's crew brief + lessons, render nothing")
    rd.add_argument("--confirm-cost", type=float, default=None,
                    help="spend gate: must be >= the printed estimate (USD) or nothing runs")

    vq = sub.add_parser("video-qa", help="Video QA: review generated clips frame-by-frame (identity drift, morphing, motion)")
    vq.add_argument("--production", default="thunderbolt")
    vq.add_argument("--episode", default="ep01_romani")
    vq.add_argument("--shots", help="comma-separated shot ids (default: every clip)")
    vq.add_argument("--approved", action="store_true", help="only clips approved in the gallery")
    vq.add_argument("--frames", type=int, default=8)
    vq.add_argument("--confirm-cost", type=float, default=None,
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

    elif args.cmd == "design":
        from . import grounding, store
        from .orchestrator import design_summary

        order = grounding.beat_shot_ids(args.production, args.episode, args.beat_ref)
        by_id = {s.shot_id: s for s in store.list_contracts(args.production, args.episode)
                 if s.beat_ref == args.beat_ref}
        wanted = [s.strip() for s in args.shots.split(",")] if args.shots else order
        todo, skipped = [], []
        for sid in [i for i in order if i in wanted]:
            s = by_id.get(sid)
            design_only = s is not None and s.status == "needs_review" and s.escalations and all(
                e.startswith("design ") for e in s.escalations)
            if s is None:
                skipped.append(f"{sid} (no contract — run the beat first)")
            elif s.status == "ready_to_compose" and not args.redo:
                skipped.append(f"{sid} (already designed — use --redo)")
            elif design_only and not args.redo:
                skipped.append(f"{sid} (design escalated — use --redo to re-design)")
            elif s.status not in ("prepped", "ready_to_compose") and not design_only:
                skipped.append(f"{sid} (status {s.status})")
            else:
                todo.append(s)
        for x in skipped:
            print(f"  skip {x}")
        if not todo:
            print(f"Nothing to design for beat {args.beat_ref}.")
            return 0
        estimate = round(len(todo) * DESIGN_EST, 2)
        print(f"Design beat {args.beat_ref}: {len(todo)} shot(s): {', '.join(s.shot_id for s in todo)}")
        print(f"Estimate: ${estimate:.2f} (≈${DESIGN_EST} per shot: up to 6 departments + production meeting)")
        if args.confirm_cost is None or args.confirm_cost < estimate:
            print(f"Not run. Re-run with --confirm-cost {estimate} to approve this spend.")
            return 0
        # continuity: the shot just before the first one, if it is already designed
        first = order.index(todo[0].shot_id)
        prev = by_id.get(order[first - 1]) if first > 0 else None
        start_cost = {s.shot_id: s.cost_usd_total for s in todo}
        orch = Orchestrator()
        orch.design_beat(todo, on_shot=store.save, prev=prev if prev and design_summary(prev) else None)
        print("\n===== DESIGN SUMMARY =====")
        spent = 0.0
        for s in todo:
            delta = s.cost_usd_total - start_cost[s.shot_id]
            spent += delta
            print(f"  {s.shot_id:8} {s.status:17} concerns={len(s.department_notes):2}  "
                  f"escalations={len(s.escalations)}  ${delta:.3f}")
        print(f"design spend ≈ ${spent:.3f} · contracts saved")

    elif args.cmd == "lessons":
        return _lessons_cmd(args)
    elif args.cmd == "render":
        return _render_cmd(args)
    elif args.cmd == "video-qa":
        from . import video_qa
        clips = video_qa.find_clips(args.production, args.episode,
                                    [x.strip() for x in args.shots.split(",")] if args.shots else None, args.approved)
        est = round(len(clips) * video_qa.EST_PER_CLIP_USD, 2)
        print(f"Video QA: {len(clips)} clip(s), {args.frames} frames each — estimate ${est:.2f} (gpt-5.6-sol)")
        if not clips:
            return 0
        if args.confirm_cost is None or args.confirm_cost < est:
            print(f"Not run. Re-run with --confirm-cost {est} to approve this spend.")
            return 0
        spent = 0.0
        for c in clips:
            try:
                v = video_qa.review_clip(c, args.production, args.episode, args.frames)
            except Exception as e:  # noqa: BLE001
                print(f"  {c.parent.parent.name:8} ERROR {str(e)[:120]}")
                continue
            spent += v["_cost_usd"]
            ch = v.get("checks") or {}
            print(f"  {v['shot']:8} {v.get('verdict', '?'):4} {v.get('score')}/10 · drift {ch.get('identity_drift', {}).get('status')}"
                  f" · morph {ch.get('morphing', {}).get('status')} · motion {ch.get('motion', {}).get('status')} · "
                  f"{v.get('fix_route')} · {c.parent.name} · {(v.get('summary') or '')[:90]}", flush=True)
        print(f"spend ≈ ${spent:.2f} · verdicts saved next to each clip (*.vqa.json)")
    elif args.cmd == "cast-audit":
        from . import audit_cast
        from datetime import datetime
        from pathlib import Path
        n, est = audit_cast.estimate(args.ids or None)
        print(f"Cast audit: {n} actor(s) — estimate ${est:.2f} (gpt-5.6-sol, anchor + low-detail training set)")
        if args.confirm_cost is None or args.confirm_cost < est:
            print(f"Not run. Re-run with --confirm-cost {est} to approve this spend.")
            return 0
        res = audit_cast.run(args.production, args.episode, args.ids or None, on_actor=lambda r: print(
            f"  {r['actor']:9} {r.get('verdict', 'ERROR'):9} anchor {(r.get('anchor') or {}).get('score', '-')} · "
            f"training {(r.get('training') or {}).get('score', '-')} · {r.get('training_images', '?')} imgs · "
            f"${r.get('_cost_usd', 0):.3f} · {(r.get('summary') or r.get('error', ''))[:110]}", flush=True))
        out = Path(__file__).resolve().parents[1] / "reports" / f"cast_audit_{datetime.now():%Y%m%d-%H%M%S}.json"
        out.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"spend ≈ ${sum(r.get('_cost_usd', 0) for r in res):.3f} · report {out}")
    return 0


def _render_cmd(args) -> int:
    from . import grounding, render, store

    order = grounding.beat_shot_ids(args.production, args.episode, args.beat_ref)
    by_id = {s.shot_id: s for s in store.list_contracts(args.production, args.episode) if s.beat_ref == args.beat_ref}
    wanted = [x.strip() for x in args.shots.split(",")] if args.shots else order
    todo = []
    for sid in [i for i in order if i in wanted]:
        s = by_id.get(sid)
        if s is None or s.status not in ("ready_to_compose", "composed", "render_review"):
            print(f"  skip {sid} ({'no contract' if s is None else s.status} — design it first)")
        elif s.status in ("composed", "render_review") and not (args.redo or (args.resume and s.status == "render_review")):
            print(f"  skip {sid} (already {s.status} — use --redo, or --continue for render_review)")
        else:
            todo.append(s)
    if args.brief:
        for s in todo:
            design = grounding.find_shot(s.production, s.episode, s.shot_id) or {}
            w, c = render._memory(design)
            print(f"\n── {s.shot_id} ──\nCREW: {render.crew_brief(s)}\nPREVENTION ({', '.join(w.ids)}): "
                  f"{render._prevention(w)}\nQA CHECKS ({', '.join(c.ids)}):\n{c.checks()}")
        return 0
    if not todo:
        print("Nothing to render.")
        return 0
    est = render.estimate(len(todo), args.rounds)
    print(f"Render beat {args.beat_ref}: {len(todo)} shot(s): {', '.join(s.shot_id for s in todo)}")
    print(f"Estimate (ceiling): ${est:.2f} (≈${render.EST_ROUND} per round × {args.rounds + 1} rounds per shot; "
          f"most shots stop after a pass)")
    if args.confirm_cost is None or args.confirm_cost < est:
        print(f"Not run. Re-run with --confirm-cost {est} to approve this spend.")
        return 0
    start = {s.shot_id: s.cost_usd_total for s in todo}
    render.render_many(todo, rounds=args.rounds, budget=args.confirm_cost, resume=args.resume)
    print("\n===== RENDER SUMMARY =====")
    for s in todo:
        best = max(s.renders, key=lambda r: r.score or 0) if s.renders else None
        print(f"  {s.shot_id:8} {s.status:14} best {best.score if best else '-'}/10 · {len(s.renders)} render(s) · "
              f"${s.cost_usd_total - start[s.shot_id]:.2f} · {best.image if best else ''}")
    print("Approve the keepers in the review gallery (engine: mtower review).")
    return 0


def _lessons_cmd(args) -> int:
    from . import grounding, harvest, lessons
    from .agents import keeper

    if args.action == "status":
        print(json.dumps(lessons.summary(), indent=1))
    elif args.action == "harvest":
        print("Harvesting incidents from the engine's history (free) …")
        print(json.dumps(harvest.harvest_engine(args.production, args.episode), indent=1))
    elif args.action == "distill":
        pending, est = keeper.estimate()
        if args.batches:
            est = round(min(est, args.batches * keeper.EST_PER_BATCH_USD), 2)
        print(f"Distill {pending} incident(s) into lessons — estimate ${est:.2f} (gpt-5.6-terra, "
              f"{keeper.BATCH} incidents per call)")
        if not pending:
            return 0
        if args.confirm_cost is None or args.confirm_cost < est:
            print(f"Not run. Re-run with --confirm-cost {est} to approve this spend.")
            return 0
        res = keeper.distill_pending(limit_batches=args.batches, on_batch=lambda t: print(
            f"  batch {t['batches']}: +{t['added']} new, {t['updated']} merged, ${t['cost_usd']:.3f}", flush=True))
        print(json.dumps(res, indent=1))
    elif args.action == "show":
        for l in lessons.load_lessons():
            if args.status and l["status"] != args.status:
                continue
            print(f"{l['id']} [{l['status']}] {l['title']}  ({len(set(l.get('targets', [])))} targets, "
                  f"{l.get('proven_fixes', 0)} proven fixes, applied {l.get('applied', {})})\n"
                  f"   prevent: {l['prevention']}\n   check:   {l.get('check', '')}\n"
                  f"   who: {l['applies_to'].get('departments')} · tags: {l['applies_to'].get('tags') or 'general'}")
    elif args.action in ("approve", "retire"):
        all_l = lessons.load_lessons()
        for l in all_l:
            if l["id"] in args.ids:
                if args.action == "approve":
                    l.update(status="rule", approved_by="human", promoted_at=lessons._now())
                else:
                    l.update(status="retired", retired_by="human", retired_reason=args.reason or "human decision")
                print(f"{l['id']} → {l['status']}")
        lessons.save_lessons(all_l)
    elif args.action == "advise":
        for sid in args.ids:
            design = grounding.find_shot(args.production, args.episode, sid)
            adv = lessons.advise(lessons.tags_for_design(design, kind="keyframe"), limit=12, text=lessons.design_text(design))
            print(f"── {sid} ──\n{adv.text() or '(no lessons)'}\n")
    return 0


BEAT_RESEARCH_EST = 0.20
SHOT_EST = 0.10
DESIGN_EST = 0.15


if __name__ == "__main__":
    raise SystemExit(main())
