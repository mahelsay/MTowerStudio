"""L2 grounding — loads a production's own research and rules for the agents.

For a beat this assembles, from the studio's own production data (productions/, library/):
  * series-bible rules (§4: history & real people, home front, enemy, violence)
  * the episode fact-check ledger (research/sources.md: SRC-xx sources, H-xx claims, D-x decisions)
  * the beat text from the locked screenplay
  * profiles of the characters in the beat (REAL vs COMPOSITE matters for Research)
  * the act's Historical Flags table

It also looks up a shot's design in the shot lists (used by batch Image QA).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parents[2]          # the MTowerStudio repository
PRODUCTIONS_DIR = STUDIO_ROOT / "productions"
LIBRARY_DIR = STUDIO_ROOT / "library"


def media_root() -> Path:
    env = os.getenv("MTOWER_MEDIA_ROOT", "").strip()
    return Path(env) if env else STUDIO_ROOT / "media"

# Studio policies that refine the series bible. Decided by the owner; recorded in docs/adr/.
STUDIO_POLICIES = (
    "P-01 Dramatized staging of real people (ADR-0003, decided 2026-10-17). On-screen gestures, blocking and "
    "physical business that SHOW a REAL person carrying out an action or order that IS stated in the sources are "
    "allowed as dramatized staging — the visual equivalent of *(dramatized)* dialogue (series bible §4.1.4). "
    "Examples: a finger across the lips to show a sourced radio-silence order; raising a compass to show a sourced "
    "change of route. Verdict 'dramatized', citing the sourced event (H-xx) in `source`; never blocks spend. "
    "LIMITS: staging may not add a fact the sources don't state — no new decision, event, outcome, number, "
    "private life, motive or credit. Staging that implies something unsourced is still 'flagged' and blocks spend."
)


def _production_dir(production: str) -> Path:
    return PRODUCTIONS_DIR / production


def _episode_dir(production: str, episode: str) -> Path:
    return _production_dir(production) / episode


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _section(text: str, start_pattern: str, stop_pattern: str) -> str:
    """Lines from the first match of start_pattern up to (not incl.) the next stop_pattern match."""
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        if not inside and re.match(start_pattern, line):
            inside = True
            out.append(line)
            continue
        if inside:
            if re.match(stop_pattern, line):
                break
            out.append(line)
    return "\n".join(out).strip()


def _act_file(production: str, episode: str, beat_ref: str) -> Path | None:
    prefix = "00_" if beat_ref.upper().startswith("T") else f"0{beat_ref.split('.')[0]}_"
    folder = _episode_dir(production, episode) / "01_development" / "screenplay"
    hits = sorted(folder.glob(f"{prefix}*.md"))
    return hits[0] if hits else None


@dataclass
class Grounding:
    beat_ref: str
    bible_rules: str = ""
    sources: str = ""
    beat_text: str = ""
    characters: str = ""
    historical_flags: str = ""
    character_ids: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.sources or self.beat_text)

    def for_research(self) -> str:
        parts = [
            ("SERIES BIBLE — RULES FOR HISTORY AND REAL PEOPLE", self.bible_rules),
            ("STUDIO POLICIES (refine the series bible; apply them)", STUDIO_POLICIES),
            ("CHARACTER PROFILES (type REAL vs COMPOSITE)", self.characters),
            (f"LOCKED SCREENPLAY — BEAT {self.beat_ref}", self.beat_text),
            ("ACT HISTORICAL FLAGS (already decided treatments)", self.historical_flags),
            ("EPISODE FACT-CHECK LEDGER (sources SRC-xx, claims H-xx, decisions D-x)", self.sources),
        ]
        return "\n\n".join(f"=== {title} ===\n{body}" for title, body in parts if body)

    def for_critic(self) -> str:
        # Reviewing research: the rules, who is real vs composite, the beat being checked, and the ledger to cite.
        parts = [
            ("SERIES BIBLE — RULES", self.bible_rules),
            ("STUDIO POLICIES (refine the series bible; apply them)", STUDIO_POLICIES),
            ("CHARACTER PROFILES", self.characters),
            (f"LOCKED SCREENPLAY — BEAT {self.beat_ref}", self.beat_text),
            ("ACT HISTORICAL FLAGS", self.historical_flags),
            ("EPISODE FACT-CHECK LEDGER", self.sources),
        ]
        return "\n\n".join(f"=== {title} ===\n{body}" for title, body in parts if body)

    def for_intent_critic(self) -> str:
        # Reviewing a scene intent needs the beat it came from and who the characters are — not the whole ledger.
        parts = [
            (f"LOCKED SCREENPLAY — BEAT {self.beat_ref}", self.beat_text),
            ("CHARACTER PROFILES", self.characters),
        ]
        return "\n\n".join(f"=== {title} ===\n{body}" for title, body in parts if body)


def load(production: str, episode: str, beat_ref: str, extra_character_ids: list[str] | None = None) -> Grounding:
    g = Grounding(beat_ref=beat_ref)

    bible = _read(_production_dir(production) / "series_bible.md")
    g.bible_rules = _section(bible, r"^## 4\. ", r"^## 5\. ")

    ep = _episode_dir(production, episode) / "01_development"
    g.sources = _read(ep / "research" / "sources.md")

    act = _act_file(production, episode, beat_ref)
    if act:
        text = _read(act)
        g.beat_text = _section(text, rf"^### Beat {re.escape(beat_ref)}\b", r"^(### Beat |## )")
        g.historical_flags = _section(text, r"^## Historical Flags", r"^## ")

    ids = sorted(set(re.findall(r"\bC-\d{2}\b", g.beat_text)) | set(extra_character_ids or []))
    g.character_ids = ids
    chars = _read(ep / "characters.md")
    if chars:
        how_to = _section(chars, r"^## How to read this file", r"^(---|## )")
        profiles = [_section(chars, rf"^### {cid} ", r"^(### |## )") for cid in ids]
        g.characters = "\n\n".join([how_to] + [p for p in profiles if p])
    return g


def beat_shot_ids(production: str, episode: str, beat_ref: str) -> list[str]:
    """All shot ids of a beat, in shot-list order."""
    folder = _episode_dir(production, episode) / "02_preproduction"
    for f in sorted(folder.glob("shot_list_*.json")):
        try:
            data = json.loads(_read(f))
        except json.JSONDecodeError:
            continue
        for beat in data.get("beats", []):
            if str(beat.get("beat")) == beat_ref:
                return [s["shot_id"] for s in beat.get("shots", []) if s.get("shot_id")]
    return []


def find_shot(production: str, episode: str, shot_id: str) -> dict | None:
    """Return {shot_id, beat, location, look, wear, prompt, characters, ...} from the shot lists."""
    folder = _episode_dir(production, episode) / "02_preproduction"
    for f in sorted(folder.glob("shot_list_*.json")):
        try:
            data = json.loads(_read(f))
        except json.JSONDecodeError:
            continue
        for beat in data.get("beats", []):
            for shot in beat.get("shots", []):
                if shot.get("shot_id") == shot_id:
                    out = dict(shot)
                    out["beat"] = beat.get("beat")
                    out["beat_title"] = beat.get("title")
                    out.setdefault("location", beat.get("location"))
                    out.setdefault("look", beat.get("look"))
                    out.setdefault("wear", beat.get("wear"))
                    out["prompt"] = shot.get("prompt") or shot.get("image_prompt_core") or shot.get("description") or ""
                    chars = shot.get("characters") or []
                    out["character_ids"] = [c["id"] if isinstance(c, dict) else c for c in chars]
                    return out
    return None
