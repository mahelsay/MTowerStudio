"""Studio memory — the Learning Keeper's store: incidents (what went wrong and what fixed it) and lessons.

Pipeline
  capture  → an INCIDENT is recorded whenever a step fails a gate (QA score below the bar, a Critic 'revise',
             an escalation) together with what eventually fixed it (or that it is still unresolved). Free.
  distill  → the Learning Keeper agent turns incidents into LESSONS: problem, cause, prevention (an instruction
             to apply BEFORE generating), a check for QA, and tags. Paid (cheap reasoning model), spend-gated.
  advise   → before a department works or a paid generation runs, the orchestrator asks for the lessons whose
             tags match the shot (location, props, cast, look, lens, shot size, kind, model). Deterministic, free.
  feedback → when a lesson was applied, the outcome (pass first time / failed again) is recorded.
  promote  → candidate → rule when it recurs on >= RULE_MIN_TARGETS different targets AND at least one incident
             proves the fix works, or it held up when applied >= RULE_MIN_PASSES times, or the human approves it.
             Retired when it keeps failing or the human says so.

Files (text, in git so the human can review and edit them): knowledge/incidents.jsonl, knowledge/lessons.json
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import grounding

KNOWLEDGE_DIR = grounding.STUDIO_ROOT / "knowledge"
INCIDENTS = KNOWLEDGE_DIR / "incidents.jsonl"
LESSONS = KNOWLEDGE_DIR / "lessons.json"

RULE_MIN_TARGETS = 3        # recurring on 3+ different shots → a rule
RULE_MIN_PASSES = 2         # applied and held up twice → a rule
RETIRE_MIN_FAILS = 3        # applied and failed 3+ times (more fails than passes) → retired
QA_PASS_SCORE = 8           # the studio's image gate (MTower's 8/10)

_ENTITY = re.compile(r"\b(?:LOC|PRP|VEH|WRD|ACT|C|LOOK|LENS|WEAR)[-_][A-Z0-9_]+\b")
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------------------------- tags

def design_text(design: dict | None) -> str:
    """The words of a shot design that situational lessons match against (prompt, motion, notes, assets, extras)."""
    d = design or {}
    return " ".join(str(d.get(k, "")) for k in ("prompt", "motion", "notes", "extras", "assets", "beat_title", "face"))


def tags_for_design(design: dict | None, kind: str = "", model: str = "") -> list[str]:
    """Tags of a shot design (shot-list entry): location, look, wear, lens, size, cast, props, kind, model."""
    d = design or {}
    tags: set[str] = set()
    for key in ("location", "wear", "lens"):
        if d.get(key):
            tags.add(str(d[key]))
    if d.get("size"):
        tags.add(f"SIZE:{str(d['size']).upper()}")
    for look in d.get("look") or []:
        tags.add(str(look))
    for cid in d.get("character_ids") or d.get("characters") or []:
        tags.add(str(cid))
    for a in d.get("assets") or []:
        tags.update(_ENTITY.findall(str(a)))
    tags.update(_ENTITY.findall(str(d.get("prompt", ""))))
    if d.get("lip_sync") == "required":
        tags.add("LIPSYNC")
    if not (d.get("character_ids") or d.get("characters")):
        tags.add("NO_CAST")
    if kind:
        tags.add(f"KIND:{kind}")
    if model:
        tags.add(f"MODEL:{model}")
    return sorted(tags)


# --------------------------------------------------------------------------------------------- incidents

def incident_id(source: str, kind: str, target: str, problem: str) -> str:
    h = hashlib.sha1(f"{source}|{kind}|{target}|{problem}".encode("utf-8")).hexdigest()[:10]
    return f"I-{h}"


def load_incidents() -> list[dict]:
    if not INCIDENTS.exists():
        return []
    out = []
    for line in INCIDENTS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def capture(*, kind: str, target: str, problem: str, production: str = "", episode: str = "",
            department: str = "", categories: list[str] | None = None, fix: str = "", resolved: bool | None = None,
            score_before: float | None = None, score_after: float | None = None, attempts: int = 1,
            cost_usd: float = 0.0, tags: list[str] | None = None, source: str = "studio",
            human_approved: bool | None = None, extra: dict | None = None) -> dict | None:
    """Record one incident (idempotent by content). Returns it, or None if already known."""
    rec = {
        "id": incident_id(source, kind, target, problem), "at": _now(), "source": source,
        "production": production, "episode": episode, "kind": kind, "target": target, "department": department,
        "categories": sorted(set(categories or [])), "problem": problem.strip()[:1200], "fix": fix.strip()[:1200],
        "resolved": resolved, "score_before": score_before, "score_after": score_after, "attempts": attempts,
        "cost_usd": round(cost_usd, 4), "tags": sorted(set(tags or [])), "human_approved": human_approved,
        "distilled": False, **(extra or {}),
    }
    with _lock:
        known = {i["id"] for i in load_incidents()}
        if rec["id"] in known:
            return None
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        with INCIDENTS.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def mark_distilled(ids: set[str]) -> None:
    with _lock:
        rows = load_incidents()
        for r in rows:
            if r["id"] in ids:
                r["distilled"] = True
        INCIDENTS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


# --------------------------------------------------------------------------------------------- lessons

def load_lessons() -> list[dict]:
    if not LESSONS.exists():
        return []
    return json.loads(LESSONS.read_text(encoding="utf-8")).get("lessons", [])


def save_lessons(lessons: list[dict]) -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    doc = {"$note": "Studio memory, kept by the Learning Keeper. status: candidate (advisory) | rule (must follow) | "
                    "retired. Edit freely: set status 'rule' to approve (approved_by: human) or 'retired' to drop.",
           "updated_at": _now(), "lessons": sorted(lessons, key=lambda l: l["id"])}
    LESSONS.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_lesson_id(lessons: list[dict]) -> str:
    n = max((int(l["id"].split("-")[1]) for l in lessons if re.fullmatch(r"L-\d+", l.get("id", ""))), default=0)
    return f"L-{n + 1:04d}"


def promote(lesson: dict) -> dict:
    """Deterministic lifecycle: candidate → rule (recurrence, held up when applied, or human) → retired."""
    if lesson.get("approved_by") == "human" or lesson.get("status") == "retired" and lesson.get("retired_by") == "human":
        return lesson
    ap = lesson.setdefault("applied", {"passes": 0, "fails": 0})
    if ap.get("fails", 0) >= RETIRE_MIN_FAILS and ap["fails"] > ap.get("passes", 0):
        lesson["status"] = "retired"
        lesson["retired_reason"] = f"applied {ap['fails']}× and still failed (passed {ap.get('passes', 0)}×)"
    elif lesson.get("status") == "candidate" and (
            (len(set(lesson.get("targets", []))) >= RULE_MIN_TARGETS and lesson.get("proven_fixes", 0) >= 1)
            or ap.get("passes", 0) >= RULE_MIN_PASSES):
        lesson["status"] = "rule"
        lesson["promoted_at"] = _now()
        lesson["promoted_by"] = "auto"
    return lesson


def record_outcome(lesson_ids: list[str], passed: bool) -> None:
    """Feedback: lessons applied to a step that then passed (or failed again)."""
    if not lesson_ids:
        return
    with _lock:
        lessons = load_lessons()
        for l in lessons:
            if l["id"] in lesson_ids:
                ap = l.setdefault("applied", {"passes": 0, "fails": 0})
                ap["passes" if passed else "fails"] = ap.get("passes" if passed else "fails", 0) + 1
                l["updated_at"] = _now()
                promote(l)
        save_lessons(lessons)


@dataclass
class Advice:
    lessons: list[dict]

    @property
    def ids(self) -> list[str]:
        return [l["id"] for l in self.lessons]

    def text(self, header: bool = True) -> str:
        if not self.lessons:
            return ""
        rules = [l for l in self.lessons if l["status"] == "rule"]
        cands = [l for l in self.lessons if l["status"] == "candidate"]
        lines = ["STUDIO MEMORY (Learning Keeper — lessons from past failures on similar shots):"] if header else []
        if rules:
            lines.append("RULES (must follow):")
            lines += [f"- [{l['id']}] {l['prevention']}" for l in rules]
        if cands:
            lines.append("ADVISORIES (seen before; apply unless they conflict with the lock):")
            lines += [f"- [{l['id']}] {l['prevention']}" for l in cands]
        return "\n".join(lines)

    def checks(self) -> str:
        return "\n".join(f"- [{l['id']}] {l['check']}" for l in self.lessons if l.get("check"))


def advise(tags: list[str], *, kind: str = "", department: str = "", limit: int = 8, text: str = "") -> Advice:
    """Lessons relevant to a step: entity-tag overlap first, then general lessons for the same kind/department.
    A lesson with `keywords` applies only when the shot's design text mentions one of them (situational lessons)."""
    tagset = set(tags)
    low = (text or "").lower()
    scored = []
    for l in load_lessons():
        if l.get("status") == "retired":
            continue
        ap = l.get("applies_to", {})
        kinds, depts, ltags = set(ap.get("kinds", [])), set(ap.get("departments", [])), set(ap.get("tags", []))
        if kind and kinds and kind not in kinds and "any" not in kinds:
            continue
        if department and depts and department not in depts and "any" not in depts:
            continue
        kws = ap.get("keywords") or []
        if kws and not any(k.lower() in low for k in kws):
            continue
        entity_hits = len({t for t in ltags & tagset if not t.startswith(("KIND:", "MODEL:"))})
        general = not {t for t in ltags if not t.startswith(("KIND:", "MODEL:", "SIZE:"))}
        if ltags and not entity_hits and not general:
            continue
        score = entity_hits * 3 + (2 if l.get("status") == "rule" else 0) + min(len(set(l.get("targets", []))), 5) * 0.2
        score += 1 if department and department in depts else 0
        scored.append((score, l))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return Advice([l for _, l in scored[:limit]])


def summary() -> dict:
    lessons, incidents = load_lessons(), load_incidents()
    by = {s: sum(1 for l in lessons if l.get("status") == s) for s in ("rule", "candidate", "retired")}
    return {"lessons": len(lessons), **by, "incidents": len(incidents),
            "undistilled": sum(1 for i in incidents if not i.get("distilled")),
            "unresolved": sum(1 for i in incidents if i.get("resolved") is False)}
