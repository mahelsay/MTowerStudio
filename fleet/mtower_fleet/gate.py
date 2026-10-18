"""The studio-wide validation gate — Tier 1 (deterministic rules).

Tier 2 (Studio Critic) and Tier 3 (Image QA) live in their agents; the orchestrator
composes all three. Here are the free, deterministic Tier-1 rules per contract field.
"""
from __future__ import annotations

import re

from .contract import Shot


def tier1(shot: Shot, field: str) -> list[str]:
    """Return a list of rule violations for a field (empty = pass)."""
    problems: list[str] = []
    if field == "intent":
        i = shot.intent
        for k in ("subject", "action", "setting", "time_of_day", "mood"):
            if not getattr(i, k):
                problems.append(f"intent.{k} is empty")
    elif field == "research":
        if not shot.research:
            problems.append("no research claims produced")
        for c in shot.research:
            if c.verdict == "verified" and not c.source:
                problems.append(f"verified claim without a source: {c.claim!r}")
            if c.verdict == "dramatized" and not re.search(r"\bH-\d+", c.source or ""):
                problems.append(f"dramatized staging must cite the sourced event (H-xx): {c.claim!r}")
    elif field == "direction":
        d = shot.direction
        for k in ("coverage", "blocking", "pacing"):
            if not getattr(d, k):
                problems.append(f"direction.{k} is empty")
    return problems


def spend_blocked(shot: Shot) -> list[str]:
    """Open research flags block any paid generation."""
    return [f"open flag: {f.kind} — {f.detail}" for f in shot.open_flags]


NIGHT_HINT = re.compile(r"NIGHT|RED_CABIN|KEROSENE|LAMP|BARE_BULB|COCKPIT|BLUE_GLASS")


def tier1_wave2(shot: Shot, field: str, resolved, cat) -> list[str]:
    """Deterministic checks for a Wave-2 department (resolved = library.Resolved, cat = library.Catalog)."""
    p: list[str] = []
    people = [c.character_id for c in shot.cast if c.actor_id] + [c.archetype for c in shot.crowd]
    if field == "casting":
        if [c.model_dump() for c in shot.cast] != [c.model_dump() for c in resolved.cast]:
            p.append("casting: the locked cast was altered")
        if resolved.extras_text and not shot.crowd:
            p.append("casting: the shot has extras but no crowd group was defined")
        for c in shot.crowd:
            if c.wardrobe_id and c.wardrobe_id not in cat.wardrobe:
                p.append(f"casting: crowd '{c.archetype}' uses unknown wardrobe {c.wardrobe_id}")
            if c.wear_state and c.wear_state not in cat.wear_states:
                p.append(f"casting: crowd '{c.archetype}' uses unknown wear state {c.wear_state}")
    elif field == "wardrobe":
        locked = {w.target: (w.wardrobe_id, w.wear_state) for w in resolved.wardrobe}
        got = {w.target: (w.wardrobe_id, w.wear_state) for w in shot.wardrobe}
        for t, v in locked.items():
            if got.get(t) != v:
                p.append(f"wardrobe: locked costume/wear for {t} was altered or dropped")
        for t in people:
            if t not in got:
                p.append(f"wardrobe: no entry for {t}")
        for w in shot.wardrobe:
            if w.target.startswith("C-") and not w.visible_details:
                p.append(f"wardrobe: {w.target} has no visible details for this frame")
    elif field == "makeup":
        have = {m.target for m in shot.makeup}
        for t in people:
            if t not in have:
                p.append(f"makeup: no entry for {t}")
    elif field == "set":
        s, r = shot.set, resolved.set
        if (s.location_id, s.vehicle_interior, s.vehicles) != (r.location_id, r.vehicle_interior, r.vehicles):
            p.append("set: the locked location/vehicles were altered")
        placed = set(s.props) | set(s.hand_props)
        for pid in r.props:
            if pid not in placed:
                p.append(f"set: locked prop {pid} is not placed (props or hand_props)")
        for pid in placed:
            if pid not in cat.props:
                p.append(f"set: {pid} is not in the prop library")
            elif pid not in resolved.allowed_props:
                p.append(f"set: {pid} is not a prop of this shot, its characters, or this beat")
        if not s.set_state:
            p.append("set: set_state is empty")
    elif field == "camera":
        c, r = shot.camera, resolved.camera
        if (c.shot_size, c.lens, c.movement, c.look_key) != (r.shot_size, r.lens, r.movement, r.look_key):
            p.append("camera: the locked size/lens/move/looks were altered")
        if not c.light:
            p.append("camera: light is empty")
        if any(NIGHT_HINT.search(k) for k in c.look_key) and not c.exposure_note:
            p.append("camera: a night/low-key look needs an exposure note")
        if shot.generation_policy.lip_sync == "required" and not c.framing_note:
            p.append("camera: a lip-sync shot needs a framing note (mouth readable)")
    elif field == "action":
        a = shot.action
        if a.applies and not (a.choreography and a.beats):
            p.append("action: applies but choreography/beats are empty")
    return p
