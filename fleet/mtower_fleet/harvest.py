"""Harvest incidents from the production engine's history (free, deterministic).

Every engine attempt left a batch folder: manifest.json (model + exact prompt), <image>.qa.json (score, verdict,
issues with category/severity/fix, fix_route, edit_instruction) and, if signed off, approved.json. For each target
(shot, poster, actor anchor) the attempts are ordered in time; a target that fell below the QA bar becomes one
incident: the distinct major problems, what was done next (fix route / edit instruction), what changed in the prompt
of the attempt that finally passed, and whether it was ever resolved or approved by the human anyway.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import grounding, lessons


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _sentences(prompt: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+", prompt or "") if len(s.strip()) > 12]


def _prompt_delta(before: str, after: str, limit: int = 4) -> str:
    old = set(_sentences(before))
    added = [s for s in _sentences(after) if s not in old]
    return " | ".join(added[:limit])[:700]


def _attempts(root: Path) -> dict[tuple[str, str], list[dict]]:
    by: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for q in root.rglob("*.qa.json"):
        d = _load(q)
        if not d or d.get("score") is None:
            continue
        man = _load(q.parent / "manifest.json")
        img = q.name[: -len(".qa.json")]
        appr = _load(q.parent / "approved.json")
        by[(d.get("kind") or man.get("kind") or "image", d.get("target") or man.get("target") or q.parent.parent.name)].append({
            "at": d.get("reviewed_at") or q.parent.name, "score": d.get("score"), "verdict": d.get("verdict"),
            "issues": d.get("issues") or [], "fix_route": d.get("fix_route", ""), "edit": d.get("edit_instruction", ""),
            "prompt": man.get("prompt", ""), "model": man.get("model_id") or man.get("model_key", ""),
            "approved": bool(appr) and str(appr.get("file", "")).startswith(img.split(".")[0]), "batch": q.parent.name,
            "cost": d.get("cost_usd", 0) or 0,
        })
    for v in by.values():
        v.sort(key=lambda a: a["at"])
    return by


def harvest_engine(production: str = "thunderbolt", episode: str = "ep01_romani") -> dict:
    media = grounding.media_root()
    roots = [media / "productions" / production / episode, media / "library"]
    made = skipped = 0
    for root in roots:
        if not root.exists():
            continue
        for (kind, target), atts in _attempts(root).items():
            fails = [a for a in atts if (a["score"] or 0) < lessons.QA_PASS_SCORE]
            if not fails:
                continue
            first_fail = fails[0]
            later_pass = next((a for a in atts if a["at"] > first_fail["at"] and (a["score"] or 0) >= lessons.QA_PASS_SCORE), None)
            seen, problems, cats = set(), [], []
            for a in fails:
                for i in a["issues"]:
                    if not isinstance(i, dict) or i.get("severity") not in ("major", "critical"):
                        continue
                    key = (i.get("category"), (i.get("description") or "")[:60])
                    if key in seen:
                        continue
                    seen.add(key)
                    cats.append(i.get("category") or "other")
                    problems.append(f"[{i.get('category')}/{i.get('severity')}] {i.get('description', '')}"
                                    + (f" → suggested: {i['fix']}" if i.get("fix") else ""))
            if not problems:
                continue
            last_fail = [a for a in fails if not later_pass or a["at"] < later_pass["at"]][-1]
            fix = ""
            if later_pass:
                delta = _prompt_delta(first_fail["prompt"], later_pass["prompt"])
                fix = (f"route {last_fail['fix_route'] or '?'}"
                       + (f"; edit: {last_fail['edit']}" if last_fail["edit"] else "")
                       + (f"; prompt added: {delta}" if delta else "")
                       + (f"; passing model {later_pass['model']}" if later_pass["model"] != first_fail["model"] else ""))
            design = grounding.find_shot(production, episode, target) if kind in ("keyframe", "clip") else None
            human_ok = any(a["approved"] for a in atts)
            rec = lessons.capture(
                kind=kind, target=target, production=production, episode=episode, source="engine-history",
                problem=" || ".join(problems[:6]), categories=cats, fix=fix, resolved=bool(later_pass),
                score_before=first_fail["score"], score_after=(later_pass or atts[-1])["score"],
                attempts=len(atts), cost_usd=sum(a["cost"] for a in atts),
                tags=lessons.tags_for_design(design, kind=kind, model=first_fail["model"]),
                human_approved=human_ok,
                extra={"note": "human approved a frame QA failed" if human_ok and not later_pass else ""},
            )
            made += 1 if rec else 0
            skipped += 0 if rec else 1
    return {"new_incidents": made, "already_known": skipped, **lessons.summary()}
