"""Agent 1b — Director. Creative lead: coverage, blocking, performance, pacing, tone."""
from __future__ import annotations

from .base import Agent


class DirectorAgent(Agent):
    NAME = "director"
    SYSTEM = (
        "You are the Director agent of an AI film studio — the creative lead (distinct from the logistics "
        "Orchestrator). A veteran, film-school trained, master of visual storytelling and genre tone. You turn a "
        "scene intent into visual direction: coverage (how the moment is covered — shot sizes/angles at a high "
        "level), blocking (who is where, how they move), a performance note, pacing, and a tone reference. You work "
        "within the locked script (coverage, not story changes). You hand exact framing/lens/light to the Camera/DoP.\n"
        "Output JSON with keys: coverage, blocking, performance_note, pacing, tone_ref. One concise phrase each."
    )

    def build_user(self, shot, **ctx) -> str:
        i = shot.intent
        design = ctx.get("shot_design") or {}
        locked = ""
        if design:
            from .. import library
            cat = library.catalog(shot.production, shot.episode)
            loc = cat.locations.get(design.get("location") or "", {})
            rules = "\n".join(f"- {r}" for r in (loc.get("qa_rules") or []))
            ids = design.get("character_ids") or design.get("characters") or []
            in_frame = ", ".join(f"{cid} {(cat.cast.get(cid) or {}).get('character', '')}".strip() for cid in ids)
            locked = (
                f"\n\nLOCKED SHOT DESIGN (from the shot list — your direction must fit it):\n"
                f"- size/lens/move: {design.get('size')} / {design.get('lens')} / {design.get('move')}\n"
                f"- frame: {design.get('prompt', '')}\n"
                f"- IN FRAME (locked cast — nobody else is visible; anyone else named is off-screen): "
                f"{in_frame or 'no tracked characters'}\n"
                + (f"- location {loc.get('id')}: {loc.get('prompt', '')}\n" if loc else "")
                + (f"LOCATION RULES (never contradict them):\n{rules}\n" if rules else "")
            )
        return (
            f"Scene intent to direct:\n- subject: {i.subject}\n- action: {i.action}\n- setting: {i.setting}\n"
            f"- time_of_day: {i.time_of_day}\n- mood: {i.mood}{locked}\n\n"
            "Give visual direction consistent with a restrained, grounded historical war drama."
        )

    def apply(self, shot, data) -> None:
        d = shot.direction
        d.coverage = data.get("coverage", d.coverage)
        d.blocking = data.get("blocking", d.blocking)
        d.performance_note = data.get("performance_note", d.performance_note)
        d.pacing = data.get("pacing", d.pacing)
        d.tone_ref = data.get("tone_ref", d.tone_ref)
