"""The studio-wide validation gate — Tier 1 (deterministic rules).

Tier 2 (Studio Critic) and Tier 3 (Image QA) live in their agents; the orchestrator
composes all three. Here are the free, deterministic Tier-1 rules per contract field.
"""
from __future__ import annotations

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
    elif field == "direction":
        d = shot.direction
        for k in ("coverage", "blocking", "pacing"):
            if not getattr(d, k):
                problems.append(f"direction.{k} is empty")
    return problems


def spend_blocked(shot: Shot) -> list[str]:
    """Open research flags block any paid generation."""
    return [f"open flag: {f.kind} — {f.detail}" for f in shot.open_flags]
