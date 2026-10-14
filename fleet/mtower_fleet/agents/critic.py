"""Agent 3b — Studio Critic. Tier-2 reviewer of every non-image decision (reviewer != author)."""
from __future__ import annotations

from .. import client
from ..agents.base import _cost, _parse_json
from ..contract import CriticNote

# Definition-of-done per field the Critic checks against (from the agent catalog).
DOD = {
    "intent": (
        "Scene intent names subject, action, setting, time_of_day and mood; references library IDs for any "
        "location/vehicle/prop/character the beat names; contains no invented historical fact (those are the "
        "Research agent's job)."
    ),
    "research": (
        "Every period-sensitive/factual element present in the intent is verified, corrected or flagged with a "
        "sourced tier; nothing is asserted from memory without a citation (uncited => flagged)."
    ),
    "direction": (
        "Coverage, blocking, a performance note, pacing and a tone reference are present and consistent with a "
        "restrained grounded historical war drama and with the scene intent."
    ),
}


class StudioCritic:
    NAME = "critic"
    SYSTEM = (
        "You are the Studio Critic of an AI film studio — a meticulous QC lead / script supervisor. You review ONE "
        "agent's decision against that agent's definition-of-done and the scene intent. You did not write it "
        "(reviewer is never the author). Be strict but fair; judge the decision, not pixels. "
        "Output JSON: { verdict: 'pass'|'revise', reasons: [string], revise_instructions: [string] }. "
        "Pass only if the decision genuinely meets the definition-of-done."
    )

    def review(self, shot, field: str) -> CriticNote:
        content_obj = getattr(shot, field)
        dod = DOD.get(field, "Meets its stated purpose and is consistent with the scene intent.")
        user = (
            f"Field under review: {field}\n"
            f"Definition of done: {dod}\n\n"
            f"Scene intent: {shot.intent.model_dump()}\n\n"
            f"The {field} to review: {content_obj.model_dump() if hasattr(content_obj, 'model_dump') else content_obj}"
        )
        messages = [
            {"role": "system", "content": self.SYSTEM + "\nRespond ONLY with a single valid JSON object."},
            {"role": "user", "content": user},
        ]
        text, usage = client.complete(messages, response_format={"type": "json_object"})
        data = _parse_json(text)
        note = CriticNote(
            target_field=field,
            verdict=data.get("verdict", "revise"),
            reasons=data.get("reasons", []) or [],
            revise_instructions=data.get("revise_instructions", []) or [],
        )
        shot.critic.append(note)
        shot.log(self.NAME, f"reviewed {field}: {note.verdict}", cost_usd=_cost(usage, False), tokens=usage.get("total", 0))
        return note
