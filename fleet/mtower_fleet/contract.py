"""The shot contract (schema v1) — the shared state every agent reads and writes.

Aligned with docs/03-orchestration.md and docs/09-shot-contract-proof.md. This is the
Wave-1 working subset (intent, research, direction) plus the full structural scaffold
so later waves can fill cast/wardrobe/set/camera/vfx/audio without a schema change.
"""
from __future__ import annotations

import threading
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
    # verified/corrected = factual claim checked against a source; flagged = cannot be confirmed (blocks spend);
    # creative = allowed invention per the series bible (composite character, dramatized dialogue, family moment);
    # dramatized = staging that shows a REAL person's sourced action (policy P-01 / ADR-0003); never blocks.
    verdict: Literal["verified", "corrected", "flagged", "creative", "dramatized"]
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


# ---------------------------------------------------------------- Wave 2 — the creative crew (schema v1, doc 09)

class CastEntry(BaseModel):              # Casting (4) — resolved from casting.json + the actor library
    character_id: str
    character: str = ""
    actor_id: str = ""
    face_model: str = ""                 # LoRA trigger of the trained face model ("" = anchor only)
    actor_status: str = ""               # library status, e.g. 'locked'
    prominence: str = ""                 # lead / background / not_visible (face hidden by design)


class CrowdEntry(BaseModel):             # Casting (4) — archetype extras, not individually tracked
    archetype: str
    count: Optional[int] = None
    wardrobe_id: str = ""
    wear_state: str = ""
    note: str = ""


class WardrobeEntry(BaseModel):          # Wardrobe (5)
    target: str                          # character id (C-xx) or crowd archetype
    wardrobe_id: str = ""
    wear_state: str = ""
    additions: str = ""                  # character_additions / face_additions that must read on screen
    visible_details: list[str] = Field(default_factory=list)
    notes: str = ""


class MakeupEntry(BaseModel):            # Makeup & Hair (5b)
    target: str
    skin_state: str = ""
    hair_state: str = ""
    injuries: list[str] = Field(default_factory=list)   # restrained — implied, never graphic (bible §4.4)
    notes: str = ""


class SetDressing(BaseModel):            # Set decoration (6)
    location_id: str = ""
    vehicle_interior: str = ""           # e.g. 'VEH-0001 cabin' when the shot lives inside a vehicle
    vehicles: list[str] = Field(default_factory=list)
    props: list[str] = Field(default_factory=list)          # environmental props (library ids)
    hand_props: list[str] = Field(default_factory=list)     # props an actor actively uses (library ids)
    hand_items: list[str] = Field(default_factory=list)     # items an actor uses that have NO library entry yet
    dressing: list[str] = Field(default_factory=list)
    set_state: str = ""
    notes: str = ""


class CameraSpec(BaseModel):             # Camera / DoP (7)
    shot_size: str = ""
    lens: str = ""
    movement: str = ""
    look_key: list[str] = Field(default_factory=list)
    format: str = ""
    light: str = ""
    exposure_note: str = ""
    framing_note: str = ""


class ActionSpec(BaseModel):             # Stunt / Action (7b) — only shots with physical action
    applies: bool = False
    choreography: str = ""
    weapon_handling: str = ""
    movement: str = ""
    beats: list[str] = Field(default_factory=list)
    safety_note: str = ""


class GenerationPolicy(BaseModel):       # Engine / Orchestrator — not a craft field
    lip_sync: str = "avoid"
    video_model: str = "default"
    face_pass: bool = True


class RenderAttempt(BaseModel):          # Render bridge — one engine render + its Image QA verdict
    round: int = 0
    route: str = ""                      # compose | recompose | edit | face_swap
    image: str = ""                      # path relative to media/
    score: float | None = None
    verdict: str = ""
    fix_route: str = ""
    issues: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    lessons: list[str] = Field(default_factory=list)
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


_LOG_LOCK = threading.Lock()  # Wave 2 departments run in parallel and share one shot


class Shot(BaseModel):
    schema_version: int = SCHEMA_VERSION
    shot_id: str
    production: str = ""
    episode: str = ""
    beat_ref: str = ""
    status: str = "drafting"
    wave_ready: int = 0                  # highest wave whose agents have run

    intent: Intent = Field(default_factory=Intent)
    research: list[ResearchClaim] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)
    direction: Direction = Field(default_factory=Direction)

    cast: list[CastEntry] = Field(default_factory=list)
    crowd: list[CrowdEntry] = Field(default_factory=list)
    wardrobe: list[WardrobeEntry] = Field(default_factory=list)
    makeup: list[MakeupEntry] = Field(default_factory=list)
    set: SetDressing = Field(default_factory=SetDressing)
    camera: CameraSpec = Field(default_factory=CameraSpec)
    action: ActionSpec = Field(default_factory=ActionSpec)
    generation_policy: GenerationPolicy = Field(default_factory=GenerationPolicy)

    critic: list[CriticNote] = Field(default_factory=list)

    cost_usd_total: float = 0.0
    escalations: list[str] = Field(default_factory=list)  # gate failures awaiting a human decision
    department_notes: list[str] = Field(default_factory=list)  # concerns about the LOCKED design; non-blocking
    lessons_applied: list[str] = Field(default_factory=list)   # Learning Keeper lesson ids given to the crew
    renders: list[RenderAttempt] = Field(default_factory=list)  # render bridge: keyframe attempts + QA
    history: list[HistoryEntry] = Field(default_factory=list)

    def log(self, agent: str, action: str, cost_usd: float = 0.0, tokens: int = 0) -> None:
        with _LOG_LOCK:
            self.history.append(HistoryEntry(agent=agent, action=action, cost_usd=cost_usd, tokens=tokens))
            self.cost_usd_total = round(self.cost_usd_total + cost_usd, 6)

    def set_notes(self, department: str, notes: list[str]) -> None:
        """Replace one department's concerns (thread-safe; re-runs don't duplicate)."""
        prefix = f"{department}: "
        with _LOG_LOCK:
            self.department_notes = [n for n in self.department_notes if not n.startswith(prefix)] + [
                f"{prefix}{n}" for n in notes if n]

    @property
    def open_flags(self) -> list[Flag]:
        return [f for f in self.flags if f.blocks_spend]
