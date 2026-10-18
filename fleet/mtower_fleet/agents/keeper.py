"""Agent 15 — Learning Keeper. The studio's memory: turns incidents (failures and their fixes) into lessons.

It never generates or judges media. It reads what went wrong, why, and what finally worked, and writes a short,
reusable lesson: a PREVENTION (an instruction the crew applies before generating), a CHECK (what QA should look
for), and TAGS (where it applies). It merges repeats into existing lessons instead of creating duplicates.
"""
from __future__ import annotations

import re

from .. import lessons as store
from .base import Agent, _cost

DEPARTMENTS = ("script", "director", "research", "casting", "wardrobe", "makeup", "set", "camera", "action",
               "prompting", "image_qa", "face_pass", "video", "voice", "sound", "editor")
KINDS = ("design", "keyframe", "clip", "lipsync", "anchor", "training_set", "poster", "voice", "any")
BATCH = 20
EST_PER_BATCH_USD = 0.07


class LearningKeeper(Agent):
    NAME = "keeper"
    SYSTEM = (
        "You are the Learning Keeper of an AI film studio making a photorealistic 1973 Egyptian war drama with "
        "image/video generation models and a crew of agents. You keep the studio's memory so the same mistake is "
        "not paid for twice. You receive INCIDENTS (a step that failed review: the problems, what was tried, whether "
        "it was finally fixed, and the prompt text that was added when it passed) and the EXISTING LESSONS.\n"
        "For each incident either attach it to an existing lesson that describes the same root cause, or create a "
        "new lesson, or skip it (one-off noise, or a QA false alarm with no general lesson). Rules:\n"
        "- A lesson is about a ROOT CAUSE that recurs, phrased generally enough to apply to future shots "
        "(e.g. 'weapons dip into water in marsh scenes'), not a single shot's description.\n"
        "- prevention: ONE imperative instruction the crew applies BEFORE generating (prompt wording, staging, "
        "lens/framing, model choice, reference images, wardrobe detail). Concrete and visual, max 40 words. Prefer "
        "what actually fixed it (the 'fix' text); if never fixed, propose the most plausible prevention and say so "
        "in `cause`.\n"
        "- check: what the image reviewer must verify (max 25 words).\n"
        "- departments: who must apply it, from: " + ", ".join(DEPARTMENTS) + ". 'prompting' = the image prompt "
        "writer; 'image_qa' = the reviewer (use it for QA calibration lessons, e.g. a human approved frames QA "
        "failed for the same reason).\n"
        "- kinds: from " + ", ".join(KINDS) + ".\n"
        "- tags: ONLY copy tags that appear on the cited incidents and that the lesson truly depends on (a location, "
        "prop, look, character, lens, size, model). Leave tags EMPTY for a general lesson that applies everywhere.\n"
        "- Merge aggressively: never create a lesson that duplicates an existing one; attach instead.\n"
        "- Never invent historical facts; lessons are about craft and process."
    )

    def distill(self, incidents: list[dict], existing: list[dict]) -> tuple[dict, dict]:
        def brief(i: dict) -> str:
            ent = [t for t in i.get("tags", []) if not t.startswith("MODEL:")]
            return (f"- {i['id']} | {i['kind']} {i['target']} | {'FIXED' if i.get('resolved') else 'UNRESOLVED'}"
                    f"{' (human approved anyway)' if i.get('human_approved') and not i.get('resolved') else ''} | "
                    f"score {i.get('score_before')}→{i.get('score_after')} in {i.get('attempts')} attempts | "
                    f"tags {ent}\n  problem: {i['problem'][:650]}\n  fix: {(i.get('fix') or 'none')[:450]}")
        lessons_txt = "\n".join(
            f"- {l['id']} ({l['status']}, {len(set(l.get('targets', [])))} targets): {l['title']} — {l['prevention']}"
            f" | tags {l.get('applies_to', {}).get('tags', [])}" for l in existing) or "none yet"
        user = (f"EXISTING LESSONS:\n{lessons_txt}\n\nINCIDENTS:\n" + "\n".join(brief(i) for i in incidents)
                + "\n\nReturn JSON: { updates: [ { lesson_id, incident_ids: [..] } ], new: [ { title, problem, cause, "
                  "prevention, check, kinds: [..], departments: [..], tags: [..], incident_ids: [..] } ], "
                  "skip: [ { incident_id, reason } ] }. Every incident id must appear exactly once.")
        return self.run_json(user)


def _apply(data: dict, batch: list[dict], lessons: list[dict]) -> tuple[int, int]:
    by_inc = {i["id"]: i for i in batch}
    by_id = {l["id"]: l for l in lessons}
    added = updated = 0

    def attach(lesson: dict, ids: list[str]) -> None:
        for iid in ids:
            inc = by_inc.get(iid)
            if not inc or any(e["incident"] == iid for e in lesson["evidence"]):
                continue
            lesson["evidence"].append({"incident": iid, "target": inc["target"], "kind": inc["kind"],
                                       "resolved": inc.get("resolved"), "source": inc.get("source")})
            lesson.setdefault("targets", [])
            if inc["target"] not in lesson["targets"]:
                lesson["targets"].append(inc["target"])
            if inc.get("resolved"):
                lesson["proven_fixes"] = lesson.get("proven_fixes", 0) + 1
        lesson["updated_at"] = store._now()

    for u in data.get("updates") or []:
        l = by_id.get(str(u.get("lesson_id")))
        if l:
            attach(l, [str(x) for x in u.get("incident_ids") or []])
            store.promote(l)
            updated += 1
    for n in data.get("new") or []:
        ids = [str(x) for x in n.get("incident_ids") or [] if str(x) in by_inc]
        if not ids or not n.get("prevention"):
            continue
        allowed = {t for iid in ids for t in by_inc[iid].get("tags", [])}
        tags = sorted({str(t) for t in n.get("tags") or [] if str(t) in allowed and not str(t).startswith("MODEL:")})
        l = {"id": store.next_lesson_id(lessons), "status": "candidate", "title": str(n.get("title", ""))[:120],
             "problem": str(n.get("problem", ""))[:400], "cause": str(n.get("cause", ""))[:400],
             "prevention": str(n["prevention"])[:400], "check": str(n.get("check", ""))[:250],
             "applies_to": {"kinds": [k for k in n.get("kinds") or [] if k in KINDS] or ["any"],
                            "departments": [d for d in n.get("departments") or [] if d in DEPARTMENTS],
                            "tags": tags},
             "evidence": [], "targets": [], "proven_fixes": 0, "applied": {"passes": 0, "fails": 0},
             "created_at": store._now(), "source": "keeper"}
        attach(l, ids)
        store.promote(l)
        lessons.append(l)
        by_id[l["id"]] = l
        added += 1
    return added, updated


def distill_pending(*, limit_batches: int | None = None, on_batch=None) -> dict:
    """Distill every undistilled incident, BATCH at a time (resolved incidents first: they carry the fixes)."""
    keeper = LearningKeeper()
    pending = [i for i in store.load_incidents() if not i.get("distilled")]
    pending.sort(key=lambda i: (not i.get("resolved"), i["kind"], i["target"]))
    batches = [pending[k:k + BATCH] for k in range(0, len(pending), BATCH)][: limit_batches or None]
    total = {"batches": 0, "added": 0, "updated": 0, "cost_usd": 0.0}
    for b in batches:
        lessons = store.load_lessons()
        data, usage = keeper.distill(b, [l for l in lessons if l["status"] != "retired"])
        added, updated = _apply(data, b, lessons)
        store.save_lessons(lessons)
        store.mark_distilled({i["id"] for i in b})
        total["batches"] += 1
        total["added"] += added
        total["updated"] += updated
        total["cost_usd"] += _cost(usage, False)
        if on_batch:
            on_batch(total)
    return {**total, **store.summary()}


def estimate() -> tuple[int, float]:
    pending = sum(1 for i in store.load_incidents() if not i.get("distilled"))
    batches = -(-pending // BATCH)
    return pending, round(batches * EST_PER_BATCH_USD, 2)


_ID = re.compile(r"\[(L-\d{4})\]")


def cited(text: str) -> list[str]:
    return sorted(set(_ID.findall(text or "")))
