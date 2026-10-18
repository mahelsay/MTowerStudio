"""A production: its config, casting, shot lists, and screenplay text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .settings import PRODUCTIONS_DIR, load_json

BEAT_HEADING = re.compile(r"^### Beat ([T0-9]+\.[0-9]+)\b")
SPEAKER_LINE = re.compile(r"^\*\*([A-Z][A-Z0-9 .'\-]*[A-Z0-9])\*\*(.*)$")
VO_LINE = re.compile(r"^\*\*VO\*\*")
STAGE_DIRECTION = re.compile(r"^\*\(.*\)\*$")


@dataclass
class DialogueLine:
    speaker: str
    text: str
    note: str = ""
    subtitle: str = ""


@dataclass
class BeatText:
    beat: str
    vo: str = ""
    dialogue: list[DialogueLine] = field(default_factory=list)
    title: str = ""
    heading: str = ""
    environment: str = ""
    action: list[tuple[int, str]] = field(default_factory=list)  # (dialogue lines before it, paragraph)

    def situation(self, line: int) -> str:
        """What is happening when dialogue line <line> (1-based) is spoken: scene heading, environment, and the action
        written before that line — the context a voice actor needs."""
        parts = [p for p in (self.heading, self.environment) if p]
        parts += [text for before, text in self.action if before < line]
        return " ".join(parts)


ACTION_SKIP = re.compile(r"^(\*\*(SFX|MUSIC|SUPER|Assets|MAIN TITLE|Subtitle)|\||#|---|>|\*\(|No dialogue|END OF|SMASH|CUT TO|FADE)")


def _plain(text: str) -> str:
    return re.sub(r"\*\*?([^*]+)\*\*?", r"\1", text).strip()


def parse_screenplay(path: Path) -> dict[str, BeatText]:
    """Extract narration (VO) and dialogue lines per beat from a screenplay Markdown file.

    Dialogue lines are numbered in order within a beat; a stage direction such as
    '*(beat)*' inside one speaker's block starts a new line. '**Subtitle:**' lines
    attach to the preceding line.
    """
    beats: dict[str, BeatText] = {}
    current: BeatText | None = None
    lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        heading = BEAT_HEADING.match(line)
        if heading:
            current = BeatText(heading.group(1), title=line.split("—", 1)[1].strip() if "—" in line else "")
            beats[current.beat] = current
            i += 1
            continue
        if line.startswith("## ") and not line.startswith("### "):
            current = None
        if current is None:
            i += 1
            continue

        if VO_LINE.match(line):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            paragraphs, para = [], []
            while j < len(lines) and lines[j].startswith(">"):
                content = lines[j][1:].strip()
                if content:
                    para.append(content)
                elif para:
                    paragraphs.append(" ".join(para))
                    para = []
                j += 1
            if para:
                paragraphs.append(" ".join(para))
            current.vo = "\n\n".join(paragraphs)
            i = j
            continue

        speaker = SPEAKER_LINE.match(line)
        if speaker and i + 1 < len(lines) and lines[i + 1].startswith(">"):
            name, note = speaker.group(1).strip(), speaker.group(2).strip()
            j = i + 1
            pending: list[str] = []
            subtitle = ""

            def flush() -> None:
                nonlocal pending, subtitle
                if pending:
                    current.dialogue.append(DialogueLine(name, " ".join(pending), note, subtitle))
                pending, subtitle = [], ""

            while j < len(lines) and lines[j].startswith(">"):
                content = lines[j][1:].strip()
                if content.startswith("**Subtitle:**"):
                    subtitle = content.replace("**Subtitle:**", "").strip()
                    if not pending and current.dialogue:
                        current.dialogue[-1].subtitle = subtitle
                        subtitle = ""
                elif STAGE_DIRECTION.match(content):
                    flush()
                elif content:
                    pending.append(content)
                j += 1
            flush()
            i = j
            continue
        stripped = line.strip()
        if stripped.startswith(("**INT.", "**EXT.", "**INT/EXT")):
            current.heading = _plain(stripped)
        elif stripped.startswith("**Environment:**"):
            current.environment = _plain(stripped)
        elif stripped and not ACTION_SKIP.match(stripped) and not stripped.startswith("**VO"):
            current.action.append((len(current.dialogue), _plain(stripped)))
        i += 1
    return beats


@dataclass
class Production:
    key: str
    root: Path
    config: dict
    casting: dict

    @classmethod
    def load(cls, key: str) -> "Production":
        root = PRODUCTIONS_DIR / key
        pre = root / "02_preproduction"
        if not pre.exists():
            raise FileNotFoundError(f"No production at {root}")
        return cls(key, root, load_json(pre / "production_config.json"), load_json(pre / "casting.json"))

    @property
    def preproduction(self) -> Path:
        return self.root / "02_preproduction"

    def shot_list_paths(self) -> list[Path]:
        return sorted(self.preproduction.glob("shot_list_*.json"))

    def shot_list(self, part: str) -> dict:
        matches = [p for p in self.shot_list_paths() if part in p.stem]
        if len(matches) != 1:
            raise ValueError(f"Part '{part}' matched {len(matches)} shot lists")
        return load_json(matches[0])

    def all_shots(self, part: str | None = None):
        """Yield (shot_list, beat, shot) for one part or all parts."""
        paths = self.shot_list_paths()
        if part:
            paths = [p for p in paths if part in p.stem]
        for path in paths:
            sl = load_json(path)
            for beat in sl["beats"]:
                for shot in beat["shots"]:
                    yield sl, beat, shot

    def find_shot(self, shot_id: str):
        for sl, beat, shot in self.all_shots():
            if shot["shot_id"] == shot_id:
                return sl, beat, shot
        raise KeyError(f"Shot {shot_id} not found")

    def screenplay(self, shot_list: dict) -> dict[str, BeatText]:
        return parse_screenplay((self.preproduction / shot_list["screenplay"]).resolve())

    def token_overrides(self) -> dict:
        return {k: v for k, v in self.config.get("token_overrides", {}).items() if not k.endswith("_status")}
