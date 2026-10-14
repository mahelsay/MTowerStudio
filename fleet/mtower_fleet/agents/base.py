"""Agent base — persona + JSON output + cost tracking.

Every Wave-1 agent is a thin subclass: it supplies a persona (L1), builds a task prompt
from the shot contract, and writes its parsed result back. The base handles the model call,
strict-JSON parsing (with one repair retry), usage/cost, and the history log.
"""
from __future__ import annotations

import json
from typing import Any

from .. import client, contract

# Rough $/1K-token estimates (placeholders — refine against real pricing). Tracking matters more than precision.
_RATES = {
    "reasoning": {"prompt": 0.0005, "completion": 0.0015},
    "vision": {"prompt": 0.002, "completion": 0.008},
}


def _cost(usage: dict, vision: bool) -> float:
    r = _RATES["vision" if vision else "reasoning"]
    return round((usage["prompt"] / 1000) * r["prompt"] + (usage["completion"] / 1000) * r["completion"], 6)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        raise


class Agent:
    NAME: str = "agent"
    VISION: bool = False
    SYSTEM: str = ""

    def build_user(self, shot: "contract.Shot", **ctx: Any) -> str:  # noqa: D401
        raise NotImplementedError

    def apply(self, shot: "contract.Shot", data: dict) -> None:
        raise NotImplementedError

    def run_json(self, user: str) -> tuple[dict, dict]:
        messages = [
            {"role": "system", "content": self.SYSTEM + "\n\nRespond ONLY with a single valid JSON object, no prose."},
            {"role": "user", "content": user},
        ]
        content, usage = client.complete(messages, vision=self.VISION, response_format={"type": "json_object"})
        try:
            data = _parse_json(content)
        except Exception:
            # one repair attempt
            fix = [
                {"role": "system", "content": "Return the previous answer as a single valid JSON object only."},
                {"role": "user", "content": content},
            ]
            content, u2 = client.complete(fix, vision=self.VISION, response_format={"type": "json_object"})
            usage = {k: usage.get(k, 0) + u2.get(k, 0) if isinstance(usage.get(k), int) else usage.get(k) for k in usage}
            data = _parse_json(content)
        return data, usage

    def act(self, shot: "contract.Shot", **ctx: Any) -> dict:
        user = self.build_user(shot, **ctx)
        revision = ctx.get("revision")
        if revision:
            user += f"\n\nREVISE per the Studio Critic: {revision}\nFix these and return the corrected JSON."
        data, usage = self.run_json(user)
        self.apply(shot, data)
        cost = _cost(usage, self.VISION)
        shot.log(self.NAME, f"wrote {self.NAME} output", cost_usd=cost, tokens=usage.get("total", 0))
        return usage
