"""Agent 3b — Studio Critic. Tier-2 reviewer of every non-image decision (reviewer != author)."""
from __future__ import annotations

from .. import client
from ..agents.base import _cost, _parse_json
from ..contract import CriticNote

# Definition-of-done per field the Critic checks against (from the agent catalog).
DOD = {
    "intent": (
        "Scene intent names subject, action, setting, time_of_day and mood; references library IDs for any "
        "location/vehicle/prop/character that has a library entry (story elements such as a message, a signal, an "
        "order or a sound are NOT props and need no ID — do not ask for one); keeps the key dramatic action of the "
        "shot; contains no invented historical fact (those are the Research agent's job)."
    ),
    "research": (
        "Every factual element in the intent (real events, places, units, equipment, numbers, real people) is "
        "verified, corrected or flagged, citing the episode fact-check ledger's IDs (SRC-xx / H-xx / D-x / A-flag). "
        "Production decisions (D-x) on disputed points count as handled. Composite characters, their personal moments "
        "and (dramatized) dialogue that paraphrases a sourced event are correctly marked 'creative', not flagged. "
        "Real people appear only through sourced actions — a real person's sourced action is 'verified', never "
        "'creative'. Nothing is asserted from memory without a citation. Source tiers follow the studio definition: "
        "primary = a participant/eyewitness account or the operation's documents (SRC-01, the Sa'iqa officer's "
        "account); secondary = press, encyclopedia articles, published histories; weak = unattributed/popular; a "
        "claim's tier = its strongest cited source. Production decisions (D-x) are handling notes, not evidence. "
        "Every flagged item has a flags entry. Judge substance: do not request a revision only for wording."
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

    def review(self, shot, field: str, grounding=None) -> CriticNote:
        content_obj = getattr(shot, field)
        dod = DOD.get(field, "Meets its stated purpose and is consistent with the scene intent.")
        if isinstance(content_obj, list):
            body = [x.model_dump() for x in content_obj]
            if field == "research":
                body = {"research": body, "flags": [f.model_dump() for f in shot.flags]}
        else:
            body = content_obj.model_dump() if hasattr(content_obj, "model_dump") else content_obj
        ground = ""
        if grounding is not None and not grounding.empty:
            if field == "research":
                ground = f"PRODUCTION GROUNDING (check citations and character types against this):\n{grounding.for_critic()}\n\n"
            elif field == "intent":
                ground = f"PRODUCTION GROUNDING (the beat this intent must stay true to):\n{grounding.for_intent_critic()}\n\n"
        user = (
            f"{ground}"
            f"Field under review: {field}\n"
            f"Definition of done: {dod}\n\n"
            f"Scene intent: {shot.intent.model_dump()}\n\n"
            f"The {field} to review: {body}"
        )
        messages = [
            {"role": "system", "content": self.SYSTEM + "\nRespond ONLY with a single valid JSON object."},
            {"role": "user", "content": user},
        ]
        text, usage = client.complete(messages, response_format={"type": "json_object"}, max_completion_tokens=8000)
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
