"""Generate → review → fix, automatically: the QA loop for keyframes.

For each shot: take its current keyframe (approved, else newest) and its QA verdict (reviewing it first if needed), then
follow the reviewer's fix route on Azure and review the result again, up to N rounds:

  keep       → done
  edit       → FLUX.1 Kontext edit of the current image with the reviewer's edit instruction
  face_swap  → a new batch from the current image's untouched base, then the Azure face swap
  recompose / new_prompt → a new Azure composition (+ face swap) with the reviewer's fixes added as corrections

Nothing is approved automatically: the best-scoring candidate is reported, and the director signs off in the gallery.
Spending stops at the --confirm-cost budget. Standard library only.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import costs, jobs, qa
from .library import Library
from .production import Production
from .prompts import PromptComposer
from .settings import load_json, media_root


def current_keyframe(prod: Production, shot_id: str) -> Path | None:
    sl, _, _ = prod.find_shot(shot_id)
    return jobs.approved_keyframe(prod, sl["part"], shot_id) or jobs.latest_keyframe(prod, sl["part"], shot_id)


def item_for(lib: Library, prod: Production, shot_id: str, image: Path) -> qa.Item:
    composer = PromptComposer(lib, prod)
    _, beat, shot = prod.find_shot(shot_id)
    brief, refs = qa.shot_brief(lib, prod, composer, beat, shot)
    return qa.Item("keyframe", shot_id, image, brief, refs, qa._batch_state(image))


def fix_notes(verdict: dict) -> str:
    """The reviewer's fixes for the major and critical issues, as one short paragraph for the next render."""
    fixes = [i["fix"].strip().rstrip(".") for i in verdict.get("issues") or [] if i["severity"] in ("critical", "major")]
    return ". ".join(fixes[:5]) + "." if fixes else ""


def plan_reface(lib: Library, prod: Production, shot_id: str, image: Path) -> list[jobs.Job]:
    """A new batch holding the image's untouched base (before any face pass), then the face pass on it."""
    sl, beat, shot = prod.find_shot(shot_id)
    base = image.parent / "base" / image.name
    source = base if base.exists() else image
    out = media_root() / "productions" / prod.key / "keyframes" / sl["part"] / shot_id / jobs.batch_id()
    out.mkdir(parents=True, exist_ok=True)
    stem = jobs._slug(shot_id)
    shutil.copy2(source, out / f"{stem}_01.png")
    cached = source.with_suffix(".faces.json") if source == base else None
    if cached and cached.exists():  # reuse the face boxes: no detection call
        (out / "base").mkdir(exist_ok=True)
        shutil.copy2(source, out / "base" / f"{stem}_01.png")
        shutil.copy2(cached, out / "base" / f"{stem}_01.faces.json")
    jobs._merge_manifest(out, {"kind": "keyframe", "target": shot_id, "model_key": "reface", "model_id": "copy for face pass",
                               "prompt": f"base of {image.parent.name}/{image.name}", "negative_prompt": ""},
                         {"target": shot_id, "prompt": "copied for a new face pass", "files": [f"{stem}_01.png"], "seeds": [],
                          "request_ids": [], "cost_usd_estimate": 0.0, "copied_from": str(source)})
    job = jobs._face_pass_job(lib, prod, PromptComposer(lib, prod), beat, shot, out, 1)
    return [job] if job else []


def _run(plan: list[jobs.Job], prod: Production) -> float:
    total = round(sum(e.total for e in jobs.estimates(plan)), 4)
    return jobs.run(plan, total + 0.001, prod.key)


def autofix(lib: Library, prod: Production, shot_ids: list[str], rounds: int, budget: float, min_score: int = 8) -> list[dict]:
    from .providers.azure import AzureClient

    m = costs.model("qa_review")
    rules = prod.config.get("qa", {})
    client = AzureClient()
    spent, summary = 0.0, []
    for sid in shot_ids:
        image = current_keyframe(prod, sid)
        if not image:
            print(f"  {sid}: no keyframe yet — skipped")
            continue
        verdict_path = image.with_suffix(".qa.json")
        if verdict_path.exists():
            verdict = load_json(verdict_path)
        else:
            try:
                verdict = qa.review(client, m, item_for(lib, prod, sid, image), rules)
            except Exception as err:  # noqa: BLE001
                print(f"  ! {sid}: review failed ({str(err)[:120]}) — skipped")
                continue
            qa.write_json(verdict_path, verdict)
            spent += verdict["cost_usd"]
            costs.record({"production": prod.key, "provider": "azure", "kind": "qa_review", "target": sid,
                          "model_id": m["model_id"], "units": 1, "unit": "image", "cost_usd": verdict["cost_usd"]})
        history = [(image, verdict)]
        print(f"\n== {sid}: {image.parent.name}/{image.name} {verdict['verdict']} {verdict['score']}/10 → {verdict['fix_route']}")
        for n in range(rounds):
            if verdict["verdict"] == "pass" or verdict["score"] >= min_score or verdict["fix_route"] == "keep":
                break
            route = verdict["fix_route"]
            if route == "edit" and verdict.get("edit_instruction"):
                plan = jobs.plan_edit(prod, sid, verdict["edit_instruction"], image)
            elif route == "face_swap":
                plan = plan_reface(lib, prod, sid, image)
            else:
                plan = jobs.plan_compositions(lib, prod, [sid], notes={sid: fix_notes(verdict)})
            ceiling = sum(e.total for e in jobs.estimates(plan)) + m["price_usd"]
            if spent + ceiling > budget:
                print(f"  {sid}: budget reached (${spent:.2f} of ${budget:.2f}) — stopping")
                break
            print(f"  round {n + 1}: {route} (ceiling ${ceiling:.2f})")
            try:
                spent += _run(plan, prod)
            except Exception as err:  # noqa: BLE001 — one failed shot must not stop the others
                print(f"  ! {sid}: {str(err)[:200]}")
                break
            new = jobs.latest_keyframe(prod, prod.find_shot(sid)[0]["part"], sid)
            if not new or new == image:
                print(f"  ! {sid}: no new image came back")
                break
            image = new
            try:
                verdict = qa.review(client, m, item_for(lib, prod, sid, image), rules)
            except Exception as err:  # noqa: BLE001 — keep the new image; review it later with 'qa'
                print(f"  ! {sid}: review failed ({str(err)[:120]}) — run 'qa {sid}' later")
                break
            qa.write_json(image.with_suffix(".qa.json"), verdict)
            spent += verdict["cost_usd"]
            costs.record({"production": prod.key, "provider": "azure", "kind": "qa_review", "target": sid,
                          "model_id": m["model_id"], "units": 1, "unit": "image", "cost_usd": verdict["cost_usd"]})
            history.append((image, verdict))
            print(f"  → {image.parent.name}/{image.name} {verdict['verdict']} {verdict['score']}/10 → {verdict['fix_route']}")
        best_image, best = max(history, key=lambda h: h[1]["score"])
        summary.append({"shot": sid, "start_score": history[0][1]["score"], "best_score": best["score"],
                        "best": f"{best_image.parent.name}/{best_image.name}", "verdict": best["verdict"],
                        "rounds": len(history) - 1, "route": best["fix_route"], "summary": best.get("summary", "")})
        if spent >= budget:
            print(f"\nBudget ${budget:.2f} reached.")
            break
    print(f"\nAutofix spent about ${spent:.2f}")
    return summary
