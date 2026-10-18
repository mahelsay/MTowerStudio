"""Roster distinctness checks: keep every virtual actor a clearly different person.

Each actor card in library/actors/actors.json carries structured `traits`
(face shape, nose, eyes, eye colour, eyebrows, jaw, hair, facial hair, skin tone, build)
chosen from `trait_vocabulary`. Two actors of the same gender and age group that share
too many traits would look like siblings on screen, so the engine warns about them and
refuses to generate new anchors for them until one card is changed.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .library import Library
from .settings import LIBRARY_DIR, load_json

TRAIT_FIELDS = ["face_shape", "nose", "eyes", "eye_color", "eyebrows", "jaw_chin", "hair", "facial_hair",
                "skin_tone", "build"]
DEFAULT_LIMITS = {"block_at_shared_traits": 5, "warn_at_shared_traits": 4, "compare_age_gap_years": 12,
                  "child_age_below": 16}


@dataclass
class Pair:
    a: str
    b: str
    shared: list[str]
    level: str  # "block" or "warn"


@dataclass
class Report:
    card_problems: list[str] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)

    def blocking_for(self, actor_ids: list[str]) -> list[str]:
        ids = set(actor_ids)
        msgs = [p for p in self.card_problems if p.split(":", 1)[0] in ids]
        msgs += [f"{p.a} and {p.b} share {len(p.shared)} traits ({', '.join(p.shared)})"
                 for p in self.pairs if p.level == "block" and (p.a in ids or p.b in ids)]
        return msgs


def _roster_meta() -> dict:
    return load_json(LIBRARY_DIR / "actors" / "actors.json")


def limits() -> dict:
    return {**DEFAULT_LIMITS, **_roster_meta().get("distinctness_limits", {})}


def _age_group(actor: dict, lim: dict) -> str:
    return "child" if actor.get("apparent_age", 99) < lim["child_age_below"] else "adult"


def comparable(a: dict, b: dict, lim: dict) -> bool:
    return (a.get("gender") == b.get("gender") and _age_group(a, lim) == _age_group(b, lim)
            and abs(a.get("apparent_age", 0) - b.get("apparent_age", 0)) <= lim["compare_age_gap_years"])


def related(a: dict, b: dict) -> bool:
    return b["id"] in (a.get("family_resemblance") or "") or a["id"] in (b.get("family_resemblance") or "")


def shared_traits(a: dict, b: dict) -> list[str]:
    ta, tb = a.get("traits") or {}, b.get("traits") or {}
    return [f for f in TRAIT_FIELDS if ta.get(f) and ta.get(f) == tb.get(f) and ta.get(f) != "none"]


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower().replace("-", " ")))


def card_problems(actor: dict, vocab: dict) -> list[str]:
    """Missing or unknown traits, and traits the prompt text never mentions."""
    traits = actor.get("traits") or {}
    out = []
    missing = [f for f in TRAIT_FIELDS if not traits.get(f)]
    if missing:
        out.append(f"{actor['id']}: missing traits {', '.join(missing)}")
    for f, value in traits.items():
        if vocab.get(f) and value not in vocab[f]:
            out.append(f"{actor['id']}: trait {f}='{value}' is not in trait_vocabulary (add it there first)")
    text = _words(actor.get("face_and_body", ""))
    for f, value in traits.items():
        if value == "none":
            continue
        absent = [w for w in _words(value) if w not in text]
        if absent:
            out.append(f"{actor['id']}: trait {f}='{value}' is not described in face_and_body (missing: {', '.join(absent)})"
                       " — the image model only sees face_and_body")
    return out


def check(lib: Library) -> Report:
    meta, lim = _roster_meta(), limits()
    vocab = meta.get("trait_vocabulary", {})
    report = Report()
    actors = list(lib.actors.values())
    for actor in actors:
        report.card_problems += card_problems(actor, vocab)
    for i, a in enumerate(actors):
        for b in actors[i + 1:]:
            if not comparable(a, b, lim) or related(a, b):
                continue
            shared = shared_traits(a, b)
            if len(shared) >= lim["block_at_shared_traits"]:
                report.pairs.append(Pair(a["id"], b["id"], shared, "block"))
            elif len(shared) >= lim["warn_at_shared_traits"]:
                report.pairs.append(Pair(a["id"], b["id"], shared, "warn"))
    return report


def nearest(lib: Library, actor_id: str) -> tuple[str, list[str]] | None:
    """The most similar comparable actor and the traits they share."""
    lim, me = limits(), lib.actors[actor_id]
    best = None
    for other in lib.actors.values():
        if other["id"] == actor_id or not comparable(me, other, lim) or related(me, other):
            continue
        shared = shared_traits(me, other)
        if best is None or len(shared) > len(best[1]):
            best = (other["id"], shared)
    return best


def coverage(lib: Library) -> dict[str, Counter]:
    """How often each trait value is used, so new actors can pick under-used looks."""
    counts = {f: Counter() for f in TRAIT_FIELDS}
    for actor in lib.actors.values():
        for f in TRAIT_FIELDS:
            value = (actor.get("traits") or {}).get(f)
            if value and value != "none":
                counts[f][value] += 1
    return counts


def unused(lib: Library) -> dict[str, list[str]]:
    vocab = _roster_meta().get("trait_vocabulary", {})
    used = coverage(lib)
    return {f: [v for v in vocab.get(f, []) if v not in used[f] and v != "none"] for f in TRAIT_FIELDS}
