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
        "Gate: pass needs score >= 8 (hero shots 9) AND identity must pass. Output JSON: "
        "{ score: number 0-10, verdict: 'pass'|'fail', identity_pass: bool, issues: [string], "
        "fix_instructions: [string] }."
    )

    def review(self, shot, image: str, *, gate: float = 8.0) -> dict:
        i = shot.intent
        user_text = (
            f"Shot intent — subject: {i.subject}; action: {i.action}; setting: {i.setting}; "
            f"time_of_day: {i.time_of_day}; mood: {i.mood}. Gate = {gate}. Review the attached frame."
        )
        messages = [
            {"role": "system", "content": self.SYSTEM + "\nRespond ONLY with a single valid JSON object."},
            {"role": "user", "content": [{"type": "text", "text": user_text}, _image_part(image)]},
        ]
        text, usage = client.complete(messages, vision=True, response_format={"type": "json_object"})
        data = _parse_json(text)
        shot.log(self.NAME, f"QA {data.get('verdict','?')} score={data.get('score','?')}",
                 cost_usd=_cost(usage, True), tokens=usage.get("total", 0))
        return data
