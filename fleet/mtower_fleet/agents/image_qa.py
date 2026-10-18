"""Agent 3 — Image QA (vision reviewer). Scores a generated frame against its intent.

Wave 1 has no image generation yet (image models arrive in Wave 2), so this agent is built and
callable but exercised later. It accepts a local image path or an https URL.
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from .. import client
from ..agents.base import _cost, _parse_json

RUBRIC = (
    "anatomy; identity (face-match to the cast actor — a face mismatch is an automatic fail); period accuracy; "
    "props & continuity; physics/plausibility; light; intent & tone"
)


def _image_part(image: str) -> dict:
    if image.startswith("http://") or image.startswith("https://"):
        return {"type": "image_url", "image_url": {"url": image}}
    p = Path(image)
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


class ImageQAAgent:
    NAME = "image_qa"
    SYSTEM = (
        "You are the Image QA agent of an AI film studio — an exacting dailies reviewer / DIT with a "
        "cinematographer's eye. Assume the generator is lying until proven right. Measure the PEOPLE first "
        "(count, face size/angle, identity), then judge the frame against its intent on this rubric: " + RUBRIC + ".\n"
        "Identity status per lead: 'pass' (visibly the same person as the casting portrait), 'fail' (a clearly "
        "readable face that is NOT the same person — an automatic fail of the frame), or 'not_visible' (the face is "
        "hidden by design — veil, deep shadow, back to camera — OR too small or soft to judge features reliably, e.g. "
        "a distant figure in a wide shot). Only use 'fail' when you can actually read the features; never fail "
        "identity on a face a few pixels tall. 'not_visible' is not a fail by itself — note it.\n"
        "Check the shot design literally: counts (people, extras), wear state, and any production or location rules "
        "given. Rank insignia must match the attached insignia drawing (device count and shape).\n"
        "Gate: pass needs score >= the gate (8; hero shots 9) AND no identity 'fail'. Output JSON: "
        "{ score: number 0-10, verdict: 'pass'|'fail', identity: [{ who, status: 'pass'|'fail'|'not_visible', "
        "note }], identity_pass: bool, issues: [string], fix_instructions: [string] }."
    )

    def review(self, shot, image: str, *, gate: float = 8.0, references: list[tuple[str, str]] | None = None,
               design: str = "", rules: str = "", lesson_checks: str = "") -> dict:
        i = shot.intent
        user_text = (
            f"Shot intent — subject: {i.subject}; action: {i.action}; setting: {i.setting}; "
            f"time_of_day: {i.time_of_day}; mood: {i.mood}. Gate = {gate}."
        )
        if rules:
            user_text = f"{rules}\n\n{user_text}"
        if design:
            user_text += f"\n\nShot design from the locked shot list:\n{design}"
        if lesson_checks:
            user_text += ("\n\nKNOWN FAILURE MODES on similar shots (Learning Keeper) — verify each explicitly; when "
                          "one recurs, start that issue with its id, e.g. '[L-0004] ...':\n" + lesson_checks)
        refs = references or []
        if refs:
            user_text += (
                "\n\nReference images follow the frame. Use casting portraits to judge identity "
                "(same person, allowing for lighting, angle and wear) and prop photos to judge weapons/equipment. "
                "References are NOT to be reviewed."
            )
        else:
            user_text += "\n\nNo casting portraits are attached: judge identity only for internal consistency."
        content: list[dict] = [{"type": "text", "text": user_text},
                               {"type": "text", "text": "IMAGE 1 — THE FRAME TO REVIEW:"}, _image_part(image)]
        for n, (label, path) in enumerate(refs, start=2):
            content += [{"type": "text", "text": f"IMAGE {n} — {label} (reference):"}, _image_part(path)]
        messages = [
            {"role": "system", "content": self.SYSTEM + "\nRespond ONLY with a single valid JSON object."},
            {"role": "user", "content": content},
        ]
        text, usage = client.complete(messages, vision=True, response_format={"type": "json_object"},
                                      max_completion_tokens=8000)
        data = _parse_json(text)
        cost = _cost(usage, True)
        data["_cost_usd"] = cost
        data["_tokens"] = usage.get("total", 0)
        shot.log(self.NAME, f"QA {data.get('verdict','?')} score={data.get('score','?')}",
                 cost_usd=cost, tokens=usage.get("total", 0))
        return data
