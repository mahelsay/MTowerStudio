"""The shot contract (schema v1) — the shared state every agent reads and writes.

Aligned with docs/03-orchestration.md and docs/09-shot-contract-proof.md. This is the
Wave-1 working subset (intent, research, direction) plus the full structural scaffold
so later waves can fill cast/wardrobe/set/camera/vfx/audio without a schema change.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Intent(BaseModel):
    subject: str = ""
    action: str = ""
    setting: str = ""
    time_of_day: str = ""
    mood: str = ""
    refs: dict[str, Any] = Field(default_factory=dict)


class ResearchClaim(BaseModel):
    claim: str
    verdict: Literal["verified", "corrected", "flagged"]
    tier: Literal["primary", "secondary", "weak", "none"] = "none"
    source: str = ""
    note: str = ""


class Flag(BaseModel):
    kind: Literal["anachronism", "inaccuracy", "unverifiable", "sensitivity"]
    detail: str
    blocks_spend: bool = True


class Direction(BaseModel):
    coverage: str = ""
    blocking: str = ""
    performance_note: str = ""
    pacing: str = ""
    tone_ref: str = ""


class CriticNote(BaseModel):
    target_field: str
    verdict: Literal["pass", "revise"]
    reasons: list[str] = Field(default_factory=list)
    revise_instructions: list[str] = Field(default_factory=list)


class HistoryEntry(BaseModel):
    ts: str = Field(default_factory=_now)
    agent: str
    action: str
    cost_usd: float = 0.0
    tokens: int = 0


class Shot(BaseModel):
    schema_version: int = SCHEMA_VERSION
    shot_id: str
    production: str = ""
    episode: str = ""
    beat_ref: str = ""
    status: str = "drafting"

    intent: Intent = Field(default_factory=Intent)
    research: list[ResearchClaim] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)
    direction: Direction = Field(default_factory=Direction)
    critic: list[CriticNote] = Field(default_factory=list)

    cost_usd_total: float = 0.0
    history: list[HistoryEntry] = Field(default_factory=list)

    def log(self, agent: str, action: str, cost_usd: float = 0.0, tokens: int = 0) -> None:
        self.history.append(HistoryEntry(agent=agent, action=action, cost_usd=cost_usd, tokens=tokens))
        self.cost_usd_total = round(self.cost_usd_total + cost_usd, 6)

    @property
    def open_flags(self) -> list[Flag]:
        return [f for f in self.flags if f.blocks_spend]
