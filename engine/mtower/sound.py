"""Sound for the cut: beds, spot effects and music, all on fal, plus the plan of where each one plays.

A shot list part can carry a "sound" block:
    "sound": {
      "beds":  [{"id": "rotor", "from": "T.1-01", "offset": 3, "to": "T.3-10", "prompt": "...", "level": 0.5,
                 "fade_in": 9, "fade_out": 0}],
      "music": [{"id": "main_title", "from": "T.4-01", "offset": 2, "seconds": 28, "prompt": "...", "level": 0.8,
                 "fade_out": 3}]
    }
- beds: a seamless text-to-sound loop (ElevenLabs sound effects) laid continuously from one shot to another — the room
  tone of a scene (rotors, wind), so the sound does not jump at every cut.
- spots: each moving shot's own effects, generated from its clip by a video-to-audio model (MMAudio), so they land on
  the action. The prompt is the shot's "sfx", else its beat's "sfx". Lip-sync shots and cards get none ("spot": false
  turns a shot off).
- music: candidates for a cue (ElevenLabs music, instrumental); the user approves one in the review app (Sound).

Media: audio/sound/<part>/<kind>/<id>/<batch>/ with a manifest (kind "bed" / "sfx" / "music") the review app lists.
Picks: the approved file, else the newest.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import costs
from .production import Production
from .settings import load_json, media_root, write_json


@dataclass
class Cue:
    kind: str  # bed | sfx | music
    id: str  # bed/music id, or the shot id for spot effects
    prompt: str
    seconds: float
    spec: dict
    clip: Path | None = None  # spot effects: the clip they are generated from


def sound_root(prod: Production, part: str) -> Path:
    return media_root() / "productions" / prod.key / "audio" / "sound" / part


def spec(prod: Production, part: str) -> dict:
    return prod.shot_list(part).get("sound") or {}


def _shots(prod: Production, part: str) -> list[tuple[dict, dict]]:
    return [(b, s) for b in prod.shot_list(part)["beats"] for s in b["shots"]]


def is_card(shot: dict) -> bool:
    return "CARD" in (shot.get("size"), shot.get("shot_size"))


def is_talking(shot: dict) -> bool:
    return shot.get("lip_sync") == "required"


def span(prod: Production, part: str, first: str, last: str | None = None) -> tuple[float, float]:
    """(start, end) in seconds within the part, from the start of shot `first` to the end of shot `last`."""
    clock, start, end = 0.0, None, None
    for _, s in _shots(prod, part):
        dur = float(s.get("duration_s") or 5)
        if s["shot_id"] == first:
            start = clock
        if s["shot_id"] == (last or first):
            end = clock + dur
        clock += dur
    if start is None or end is None:
        raise KeyError(f"{part}: unknown shot in sound span {first}..{last}")
    return start, end


def plan(prod: Production, part: str, kinds: set[str], shots: list[str] | None = None, variants: int = 3,
         cues_only: list[str] | None = None) -> list[Cue]:
    """cues_only: bed / music cue ids to make (default all)."""
    from .animatic import best_clip, probe_seconds, ffmpeg

    cues: list[Cue] = []
    sp = spec(prod, part)
    sfx_max = costs.model("sfx_text").get("max_seconds", 22)
    if "bed" in kinds:
        for bed in sp.get("beds", []):
            if cues_only and bed["id"] not in cues_only:
                continue
            start, end = span(prod, part, bed["from"], bed.get("to"))
            cues.append(Cue("bed", bed["id"], bed["prompt"], min(sfx_max, max(1.0, end - start - bed.get("offset", 0))), bed))
    if "music" in kinds:
        for m in sp.get("music", []):
            if cues_only and m["id"] not in cues_only:
                continue
            for _ in range(variants):
                cues.append(Cue("music", m["id"], m["prompt"], float(m["seconds"]), m))
    if "sfx" in kinds:
        exe = ffmpeg()
        for beat, s in _shots(prod, part):
            sid = s["shot_id"]
            if (shots and sid not in shots) or is_card(s) or is_talking(s) or s.get("spot") is False:
                continue
            prompt = s.get("sfx") or beat.get("sfx")
            clip, _ = best_clip(prod, part, sid)
            if not prompt or not clip:
                continue
            seconds = min(probe_seconds(exe, clip), float(s.get("duration_s") or 5), costs.model("sfx_video")["max_seconds"])
            cues.append(Cue("sfx", sid, prompt, seconds, s, clip))
    return cues


def estimates(cues: list[Cue]) -> list[costs.Estimate]:
    key = {"bed": "sfx_text", "sfx": "sfx_video", "music": "music"}
    return [costs.estimate(key[c.kind], c.seconds / 60 if c.kind == "music" else c.seconds) for c in cues]


def _extract_audio(video: Path, dest: Path) -> Path:
    from .animatic import ffmpeg
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "2", "-ar", "48000", str(dest)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    return dest


def run(prod: Production, part: str, cues: list[Cue], confirm_cost: float | None) -> list[Path]:
    from .providers.fal import FalClient, download

    costs.authorize(estimates(cues), confirm_cost)
    fal, stamp, made = FalClient(), datetime.now().strftime("%Y%m%d-%H%M%S"), []
    counter: dict[tuple, int] = {}
    for cue in cues:
        folder = {"bed": "beds", "sfx": "spots", "music": "music"}[cue.kind]
        out = sound_root(prod, part) / folder / cue.id / stamp
        out.mkdir(parents=True, exist_ok=True)
        n = counter[(cue.kind, cue.id)] = counter.get((cue.kind, cue.id), 0) + 1
        try:
            if cue.kind == "sfx":
                m = costs.model("sfx_video")
                payload = {**m.get("payload", {}), "video_url": fal.upload_file(cue.clip), "prompt": cue.prompt,
                           "negative_prompt": m.get("negative_prompt", ""), "duration": round(cue.seconds, 2)}
                result = fal.run(m["model_id"], payload, timeout=900)
                video = download((result.get("video") or {}).get("url"), out / "with_sound.mp4")
                dest = _extract_audio(video, out / f"{cue.id.lower().replace('.', '-')}.wav")
                video.unlink(missing_ok=True)
                units, unit = cue.seconds, "second"
            elif cue.kind == "bed":
                m = costs.model("sfx_text")
                payload = {**m.get("payload", {}), "text": cue.prompt, "duration_seconds": round(cue.seconds, 1)}
                result = fal.run(m["model_id"], payload, timeout=600)
                dest = download((result.get("audio") or {}).get("url"), out / f"{cue.id}.mp3")
                units, unit = cue.seconds, "second"
            else:
                m = costs.model("music")
                payload = {**m.get("payload", {}), "prompt": cue.prompt, "music_length_ms": int(cue.seconds * 1000)}
                result = fal.run(m["model_id"], payload, timeout=900)
                dest = download((result.get("audio") or {}).get("url"), out / f"{cue.id}_v{n}.mp3")
                units, unit = cue.seconds / 60, "minute"
        except Exception as err:  # noqa: BLE001 — one failed cue must not lose the others (they are paid)
            print(f"  ✗ {cue.kind} {cue.id}: {str(err)[:300]}", flush=True)
            continue
        cost = round(units * m["price_usd"], 4)
        manifest = out / "manifest.json"
        items = load_json(manifest).get("items", []) if manifest.exists() else []
        items.append({"files": [dest.name], "request_ids": [result.get("_request_id")], "cost_usd_estimate": cost})
        write_json(manifest, {"kind": {"bed": "bed", "sfx": "sfx", "music": "music"}[cue.kind],
                              "target": f"{part} {cue.kind} {cue.id}", "model_id": m["model_id"],
                              "prompt": cue.prompt, "seconds": round(cue.seconds, 2),
                              "clip": str(cue.clip) if cue.clip else None, "items": items})
        costs.record({"production": prod.key, "provider": "fal", "kind": cue.kind, "target": cue.id,
                      "model_id": m["model_id"], "units": round(units, 3), "unit": unit, "cost_usd": cost,
                      "request_ids": [result.get("_request_id")], "out_dir": str(out)})
        print(f"  ✓ {cue.kind:5} {cue.id:12} {cue.seconds:5.1f}s ${cost:.3f}  {dest}", flush=True)
        made.append(dest)
    return made


def pick(prod: Production, part: str, kind: str, cue_id: str) -> Path | None:
    """The approved file of a bed / spot / music cue, else the newest."""
    folder = sound_root(prod, part) / {"bed": "beds", "sfx": "spots", "music": "music"}[kind] / cue_id
    if not folder.exists():
        return None
    for approval in sorted(folder.glob("*/approved.json"), reverse=True):
        f = approval.parent / load_json(approval).get("file", "")
        if f.is_file():
            return f
    files = sorted((p for p in folder.glob("*/*") if p.suffix.lower() in (".wav", ".mp3")), key=lambda p: (p.parent.name, p.name))
    return files[-1] if files else None


def layers(prod: Production, part: str, shot_starts: dict[str, float], shot_ids: set[str]) -> list[dict]:
    """Every sound layer of the cut: {file, start, seconds, level, fade_in, fade_out, loop, bus}. Spans are clipped to
    the shots in the cut."""
    out = []
    sp = spec(prod, part)
    for kind, key in (("bed", "beds"), ("music", "music")):
        for cue in sp.get(key, []):
            if cue["from"] not in shot_ids:
                continue
            f = pick(prod, part, kind, cue["id"])
            if not f:
                continue
            start, end = span(prod, part, cue["from"], cue.get("to"))
            begin = shot_starts[cue["from"]] + cue.get("offset", 0)
            length = cue.get("play_seconds", cue["seconds"]) if kind == "music" else (end - start - cue.get("offset", 0))
            out.append({"file": f, "start": begin, "seconds": length, "level": cue.get("level", 0.5),
                        "fade_in": cue.get("fade_in", 0), "fade_out": cue.get("fade_out", 0),
                        "loop": kind == "bed", "bus": kind, "id": cue["id"], "tempo": cue.get("tempo")})
    for beat, s in _shots(prod, part):
        sid = s["shot_id"]
        if sid not in shot_ids:
            continue
        f = pick(prod, part, "sfx", sid)
        if f:
            out.append({"file": f, "start": shot_starts[sid], "seconds": float(s.get("duration_s") or 5),
                        "level": s.get("sfx_level", sp.get("spot_level", 0.6)), "fade_in": 0.05, "fade_out": 0.25,
                        "loop": False, "bus": "sfx", "id": sid})
    return out


def describe(cues: list[Cue]) -> str:
    return "\n".join(f"  {c.kind:5} {c.id:12} {c.seconds:5.1f}s  {c.prompt[:90]}" for c in cues)
