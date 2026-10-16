"""Shot-contract store — git-tracked JSON, one file per shot (docs/03-orchestration.md §6).

Layout (in the MTowerStudio repo, never in the live MTower repo):
  productions/<production>/<episode>/contracts/<shot_id>.json
  productions/<production>/<episode>/contracts/beats/<beat>.research.json   (beat-level fact check)
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import REPO_ROOT
from .contract import Shot

STORE_ROOT = REPO_ROOT / "productions"


def _dir(production: str, episode: str) -> Path:
    return STORE_ROOT / production / episode / "contracts"


def _safe(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_")


def save(shot: Shot) -> Path:
    path = _dir(shot.production, shot.episode) / f"{_safe(shot.shot_id)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(shot.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load(production: str, episode: str, shot_id: str) -> Shot | None:
    path = _dir(production, episode) / f"{_safe(shot_id)}.json"
    return Shot.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def save_beat_research(beat: Shot, beat_ref: str) -> Path:
    path = _beat_path(beat.production, beat.episode, beat_ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(beat.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _beat_path(production: str, episode: str, beat_ref: str) -> Path:
    return _dir(production, episode) / "beats" / f"{_safe(beat_ref)}.research.json"


def load_beat_research(production: str, episode: str, beat_ref: str) -> Shot | None:
    path = _beat_path(production, episode, beat_ref)
    return Shot.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def is_current(production: str, episode: str, shot_id: str, beat_ref: str) -> bool:
    """A shot contract is current if it was written after the beat fact check it inherits."""
    shot = _dir(production, episode) / f"{_safe(shot_id)}.json"
    beat = _beat_path(production, episode, beat_ref)
    return shot.exists() and beat.exists() and shot.stat().st_mtime >= beat.stat().st_mtime


def list_contracts(production: str, episode: str) -> list[Shot]:
    folder = _dir(production, episode)
    return [Shot.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]
