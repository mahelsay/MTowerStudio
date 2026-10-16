"""Agent 1 — Script / Scenario. Beat → filmable scene intent (+ dialogue meaning)."""
from __future__ import annotations

from .base import Agent


class ScriptAgent(Agent):
    NAME = "script"
    SYSTEM = (
        "You are the Script/Scenario agent of an AI film studio: a veteran screenwriter, MFA, 20 years in historical "
        "war drama, master of drama/action/thriller/historical structure. You work WITHIN a locked story — you never "
        "rewrite it, you translate a story beat into a precise, filmable scene intent. You do NOT invent historical "
        "facts (the Research agent owns truth) and you do NOT choose coverage/shots (the Director owns that).\n"
        "Given a beat, output the scene intent as JSON with keys: "
        "subject, action, setting, time_of_day, mood, refs. "
        "`refs` is an object that may contain location/vehicle/props/characters referencing library IDs if the beat "
        "names them (else leave empty). Keep each field one concise sentence or phrase."
    )

    def build_user(self, shot, **ctx) -> str:
        beat = ctx.get("beat", "")
        extra = ctx.get("notes", "")
        design = ctx.get("shot_design") or {}
        shot_part = ""
        if design:
            shot_part = (
                f"\n\nTHIS SHOT ({shot.shot_id}) from the locked shot list — describe THIS shot, not the whole beat:\n"
                f"- size/lens/move: {design.get('size') or design.get('shot_size')} / {design.get('lens')} / "
                f"{design.get('move') or design.get('camera_move')}\n"
                f"- characters: {design.get('character_ids')}\n"
                f"- library assets: {design.get('assets') or []}\n"
                f"- design prompt: {design.get('prompt')}\n"
                f"- motion: {design.get('motion') or design.get('motion_prompt')}\n"
                f"- location/look: {design.get('location')} / {design.get('look')}"
            )
        return (
            f"Production: {shot.production} / {shot.episode}\n"
            f"LOCKED SCREENPLAY — beat {shot.beat_ref}:\n{beat}{shot_part}\n\nNotes: {extra}"
        )

    def apply(self, shot, data) -> None:
        i = shot.intent
        i.subject = data.get("subject", i.subject)
        i.action = data.get("action", i.action)
        i.setting = data.get("setting", i.setting)
        i.time_of_day = data.get("time_of_day", i.time_of_day)
        i.mood = data.get("mood", i.mood)
        if isinstance(data.get("refs"), dict):
            i.refs = data["refs"]
        shot.status = "researching"
