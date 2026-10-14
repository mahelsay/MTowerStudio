"""Agent 2 — Research / Fact-check. The universal fact desk; flags block spend."""
from __future__ import annotations

from .base import Agent
from ..contract import Flag, ResearchClaim


class ResearchAgent(Agent):
    NAME = "research"
    SYSTEM = (
        "You are the Research/Fact-check agent of an AI film studio — the universal fact desk. You verify EVERYTHING "
        "real: history, geography (countries, cities, terrain, climate), places, culture, and technical/military "
        "detail. For this production the setting is Egyptian Sa'iqa special operations, 1967-1973. You are rigorous "
        "and skeptical: you NEVER assert from memory alone — a claim without a credible source is a flag, not a fact.\n"
        "Sourcing tiers: primary/archival > secondary (reputable) > weak. Weak-only sources must be flagged.\n"
        "Strictness = block: anything unverifiable is flagged and blocks paid generation.\n"
        "Given a scene intent, output JSON with keys:\n"
        "  research: array of { claim, verdict (verified|corrected|flagged), tier (primary|secondary|weak|none), "
        "source, note }\n"
        "  flags: array of { kind (anachronism|inaccuracy|unverifiable|sensitivity), detail, blocks_spend (bool) }\n"
        "Only list period-sensitive or factual elements actually present in the intent. If a source URL is not known, "
        "set tier 'none' and verdict 'flagged' (you cannot cite from memory)."
    )

    def build_user(self, shot, **ctx) -> str:
        i = shot.intent
        return (
            f"Scene intent to fact-check (period: 1967-1973 Sinai/Egypt):\n"
            f"- subject: {i.subject}\n- action: {i.action}\n- setting: {i.setting}\n"
            f"- time_of_day: {i.time_of_day}\n- refs: {i.refs}"
        )

    def apply(self, shot, data) -> None:
        for c in data.get("research", []) or []:
            try:
                shot.research.append(ResearchClaim(**{
                    "claim": c.get("claim", ""),
                    "verdict": c.get("verdict", "flagged"),
                    "tier": c.get("tier", "none"),
                    "source": c.get("source", ""),
                    "note": c.get("note", ""),
                }))
            except Exception:
                continue
        for f in data.get("flags", []) or []:
            try:
                shot.flags.append(Flag(**{
                    "kind": f.get("kind", "unverifiable"),
                    "detail": f.get("detail", ""),
                    "blocks_spend": bool(f.get("blocks_spend", True)),
                }))
            except Exception:
                continue
        shot.status = "prepping" if not shot.open_flags else "researching"
