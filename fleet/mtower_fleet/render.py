"""Render bridge — a designed shot contract becomes a QA-checked keyframe.

  contract (ready_to_compose)
    → Learning Keeper: lessons for the prompt writer (prevention) and for the reviewer (checks)
    → crew brief: the Wave-2 craft (wardrobe, makeup, set, camera, action) as production design for the prompt
    → engine: composition (gpt-image on the media Foundry, or FLUX for child shots) + face pass
    → engine Image QA (gpt-5.6-sol, references, strict verdict with a fix route), told the lesson checks + crew brief
    → pass (score >= gate) → status 'composed' (the director still approves in the gallery)
      fail → incident captured → follow the reviewer's fix route (edit / face swap / recompose with fixes) → re-review
    → after the loop: lessons credited (held up) or debited (failed again); a fixed failure becomes a resolved incident.

Spend: every round's ceiling is checked against the budget before it runs (--confirm-cost).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from . import grounding, lessons, store
from .contract import RenderAttempt, Shot

ENGINE_DIR = grounding.STUDIO_ROOT / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from mtower import autofix, costs, jobs, qa  # noqa: E402
from mtower.library import Library  # noqa: E402
from mtower.production import Production  # noqa: E402
from mtower.settings import load_env, media_root  # noqa: E402

load_env()

GATE = 8
CREW_LIMIT = 1400       # characters of crew brief added to the image prompt
EST_ROUND = 0.32        # ceiling per round: composition (~$0.11 with refs) + face pass (~$0.10) + QA (~$0.10)


def crew_brief(s: Shot) -> str:
    """The crew's craft for the image prompt: what must be visible, in plain visual sentences."""
    parts: list[str] = []
    for w in s.wardrobe:
        if w.visible_details:
            parts.append(f"{w.target} wardrobe: " + "; ".join(w.visible_details[:4]))
    for m in s.makeup:
        bits = [x for x in (m.skin_state, m.hair_state) if x] + list(m.injuries[:2])
        if bits:
            parts.append(f"{m.target} skin/hair: " + "; ".join(bits))
    st = s.set
    set_bits = list(st.dressing[:4]) + ([st.set_state] if st.set_state else []) + [f"hand item: {h}" for h in st.hand_items[:2]]
    if set_bits:
        parts.append("Set: " + "; ".join(set_bits))
    cam = [x for x in (s.camera.light, s.camera.exposure_note, s.camera.framing_note) if x]
    if cam:
        parts.append("Camera/light: " + " ".join(cam))
    if s.action.applies:
        act = [x for x in (s.action.choreography, s.action.weapon_handling, s.action.movement) if x]
        if act:
            parts.append("Action: " + " ".join(act))
    text = " | ".join(parts)
    return text[:CREW_LIMIT]


def _memory(design: dict) -> tuple[lessons.Advice, lessons.Advice]:
    tags = lessons.tags_for_design(design, kind="keyframe")
    txt = lessons.design_text(design)
    return (lessons.advise(tags, department="prompting", kind="keyframe", limit=6, text=txt),
            lessons.advise(tags, department="image_qa", kind="keyframe", limit=8, text=txt))


def _prevention(adv: lessons.Advice) -> str:
    rules = [l for l in adv.lessons if l["status"] == "rule"]
    cands = [l for l in adv.lessons if l["status"] == "candidate"][:3]
    return " ".join(l["prevention"].rstrip(".") + "." for l in rules + cands)


def _rel(p: Path) -> str:
    try:
        return p.relative_to(media_root()).as_posix()
    except ValueError:
        return str(p)


def _review(lib, prod, sid: str, image: Path, crew: str, checks: str, client, m, rules) -> dict:
    item = autofix.item_for(lib, prod, sid, image)
    extra = []
    if crew:
        extra.append(f"PRODUCTION DESIGN FROM THE CREW (the image should show this): {crew}")
    if checks:
        extra.append("KNOWN FAILURE MODES ON SIMILAR SHOTS (Learning Keeper) — verify each explicitly; when one recurs, "
                     "start that issue's description with its id, e.g. '[L-0004] ...':\n" + checks)
    if extra:
        item.brief = item.brief + "\n\n" + "\n\n".join(extra)
    v = qa.review(client, m, item, rules)
    qa.write_json(image.with_suffix(".qa.json"), v)
    costs.record({"production": prod.key, "provider": "azure", "kind": "qa_review", "target": sid,
                  "model_id": m["model_id"], "units": 1, "unit": "image", "cost_usd": v["cost_usd"]})
    return v


def _issues(v: dict) -> list[str]:
    return [f"[{i.get('category')}/{i.get('severity')}] {i.get('description', '')}" for i in v.get("issues") or []
            if i.get("severity") in ("critical", "major")]


def render_shot(s: Shot, *, rounds: int = 2, budget: float = 1.0, log=print, resume: bool = False) -> Shot:
    from mtower.providers.azure import AzureClient

    lib, prod = Library.load(), Production.load(f"{s.production}/{s.episode}")
    sid = s.shot_id
    design = grounding.find_shot(s.production, s.episode, sid) or {}
    write_adv, check_adv = _memory(design)
    crew = crew_brief(s)
    prevention = _prevention(write_adv)
    crew_text = " ".join(x for x in (crew, prevention) if x)
    used = sorted(set(write_adv.ids) | set(check_adv.ids))
    log(f"● {sid}: crew brief {len(crew)} chars · lessons {used or 'none'}")
    m, rules, client = costs.model("qa_review"), prod.config.get("qa", {}), AzureClient()
    spent, image, verdict, first_fail, route = 0.0, None, None, None, "compose"
    if resume and s.renders:  # continue the fix loop from the best render so far and its verdict
        best = max(s.renders, key=lambda r: (r.score or 0, r.round))  # newest among the best (carries the latest route)
        image = media_root() / best.image
        verdict = qa.load_json(image.with_suffix(".qa.json")) if image.with_suffix(".qa.json").exists() else None
        if verdict:
            route = verdict.get("fix_route") or "recompose"
            first_fail = verdict if (verdict.get("score") or 0) < GATE else None
            log(f"  resume from {best.image} ({best.score}/10) → {route}")
    start_round = len(s.renders)
    for n in range(start_round, start_round + rounds + 1):
        if route == "compose" or route in ("recompose", "new_prompt"):
            notes = {sid: autofix.fix_notes(verdict)} if verdict else None
            plan = jobs.plan_compositions(lib, prod, [sid], crew={sid: crew_text}, notes=notes)
        elif route == "edit":
            plan = jobs.plan_edit(prod, sid, verdict.get("edit_instruction", ""), image)
        elif route == "face_swap":
            plan = autofix.plan_reface(lib, prod, sid, image)
        else:
            break
        ceiling = sum(e.total for e in jobs.estimates(plan)) + m["price_usd"]
        if spent + ceiling > budget:
            log(f"  budget reached (${spent:.2f} + ${ceiling:.2f} > ${budget:.2f}) — stopping")
            break
        log(f"  round {n}: {route} (ceiling ${ceiling:.2f})")
        before = jobs.latest_keyframe(prod, prod.find_shot(sid)[0]["part"], sid)
        round_cost = jobs.run(plan, round(sum(e.total for e in jobs.estimates(plan)), 4) + 0.001, prod.key)
        new = jobs.latest_keyframe(prod, prod.find_shot(sid)[0]["part"], sid)
        if not new or new == before:
            spent += round_cost
            s.log("render", f"{route}: no new image", cost_usd=round(round_cost, 4))
            log("  ! no new image came back")
            break
        image = new
        verdict = _review(lib, prod, sid, image, crew, check_adv.checks(), client, m, rules)
        round_cost += verdict["cost_usd"]
        spent += round_cost
        cited = sorted({x for i in verdict.get("issues") or [] for x in re.findall(r"\[(L-\d{4})\]", i.get("description", ""))})
        s.renders.append(RenderAttempt(round=n, route=route, image=_rel(image), score=verdict.get("score"),
                                       verdict=verdict.get("verdict", ""), fix_route=verdict.get("fix_route", ""),
                                       issues=_issues(verdict), cost_usd=round(round_cost, 4), lessons=used))
        s.log("render", f"{route} → QA {verdict.get('verdict')} {verdict.get('score')}/10 ({image.parent.name})",
              cost_usd=round(round_cost, 4))
        log(f"  → {image.parent.name}/{image.name}: {verdict.get('verdict')} {verdict.get('score')}/10 · "
            f"route {verdict.get('fix_route')}" + (f" · recurring lessons {cited}" if cited else ""))
        passed = verdict.get("verdict") == "pass" or (verdict.get("score") or 0) >= GATE
        if passed:
            break
        if first_fail is None:
            first_fail = verdict
            lessons.record_outcome(cited, False)  # the lesson was applied and the failure recurred anyway
        route = verdict.get("fix_route") or "recompose"
        if route == "keep":
            break
    best = max(s.renders, key=lambda r: r.score or 0) if s.renders else None
    ok = bool(best and ((best.score or 0) >= GATE or best.verdict == "pass"))
    design_tags = lessons.tags_for_design(design, kind="keyframe")
    if first_fail is not None:
        lessons.capture(kind="keyframe", target=sid, production=s.production, episode=s.episode, department="render",
                        source="studio-render", problem=" || ".join(_issues(first_fail))[:1200],
                        fix=(f"route {first_fail.get('fix_route')}: {autofix.fix_notes(first_fail)}" if ok else ""),
                        resolved=ok, score_before=first_fail.get("score"), score_after=best.score if best else None,
                        attempts=len(s.renders), cost_usd=spent, tags=design_tags)
    if ok and first_fail is None:
        lessons.record_outcome(used, True)  # first render passed with these lessons applied
    s.status = "composed" if ok else "render_review"
    log(f"● {sid}: {s.status} · best {best.score if best else '-'}/10 · spent ${spent:.2f}")
    return s


def estimate(n_shots: int, rounds: int) -> float:
    return round(n_shots * (rounds + 1) * EST_ROUND, 2)


def render_many(shots: list[Shot], *, rounds: int, budget: float, log=print, resume: bool = False) -> list[Shot]:
    left = budget
    for s in shots:
        if left < EST_ROUND:
            log(f"budget exhausted before {s.shot_id}")
            break
        start_cost = s.cost_usd_total
        render_shot(s, rounds=rounds, budget=min(left, (rounds + 1) * EST_ROUND + 0.2), log=log, resume=resume)
        store.save(s)
        left -= s.cost_usd_total - start_cost
    return shots
