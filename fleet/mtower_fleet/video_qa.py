"""Video QA (agent 3c) — reviews a generated clip, not a still: what only motion can break.

Frames are sampled with ffmpeg (default 8, evenly spread, plus first/last) and sent to the vision reviewer with the
clip's approved keyframe (the start frame), the casting portraits, the shot design, the motion prompt and the Learning
Keeper's checks. It judges:
  identity_drift  — do the leads stay the same person across frames (vs the keyframe and casting portrait)?
  morphing        — faces, hands, limbs, weapons, vehicles melting/warping/duplicating between frames
  motion          — does the scripted action happen (the motion prompt), plausibly, with weight and physics?
  continuity      — wardrobe, props, light and location stay consistent with the keyframe through the clip
  lip_sync        — talking shots only: mouth visible and moving with speech-like shapes (true sync needs audio)
  technical       — flicker, frozen frames, black/letterbox bars, text, compression mush
Gate: pass needs score >= 8 and no 'fail' in identity_drift or morphing. Failures become Learning Keeper incidents.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import client, grounding, lessons
from .agents.base import _cost, _parse_json
from .agents.image_qa import _image_part

ENGINE_DIR = grounding.STUDIO_ROOT / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

GATE = 8
FRAMES = 8
EST_PER_CLIP_USD = 0.12

SYSTEM = (
    "You are the Video QA reviewer (dailies) of an AI film studio making a photorealistic 1973 Egyptian war drama with "
    "image-to-video models. You review a CLIP through evenly spaced frames in time order, against its start keyframe, "
    "casting portraits, the shot design and the motion prompt. Judge what only motion can break:\n"
    "- identity_drift: the leads must stay the same person in every frame (face shape, features, age, facial hair).\n"
    "- morphing: faces, hands, fingers, limbs, weapons, vehicles must not melt, warp, merge, duplicate or pop between "
    "frames.\n- motion: the scripted action from the motion prompt happens, with natural weight, physics and timing; "
    "no frozen subject, no moonwalking, no impossible camera move.\n- continuity: wardrobe, rank insignia, props, light "
    "and location stay consistent with the keyframe through the clip.\n- lip_sync: only for talking shots — the mouth is "
    "visible and moving in speech-like shapes; otherwise 'n/a'.\n- technical: flicker, frozen or duplicated frames, "
    "letterbox bars, text, heavy compression.\nEach check: status 'ok' | 'minor' | 'fail' | 'n/a' with a note naming the "
    "frame numbers. Score 0-10. Gate: pass needs score >= 8 and no 'fail' in identity_drift or morphing. Output JSON: "
    "{ score, verdict: 'pass'|'fail', checks: { identity_drift, morphing, motion, continuity, lip_sync, technical: "
    "{ status, note } }, issues: [ { severity: 'critical'|'major'|'minor', category, description, frames: [int] } ], "
    "fix_route: 'keep'|'regenerate'|'regenerate_other_model'|'new_keyframe'|'trim', fix_note, summary }."
)


def _ffmpeg() -> str:
    from mtower.animatic import ffmpeg
    return ffmpeg()


def _ffprobe_duration(clip: Path) -> float:
    exe = _ffmpeg()
    out = subprocess.run([exe, "-i", str(clip)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 5.0


def sample_frames(clip: Path, n: int = FRAMES, out_dir: Path | None = None) -> list[Path]:
    """n frames evenly spread across the clip (first and last included), as JPEGs (720p max)."""
    dur = _ffprobe_duration(clip)
    out_dir = out_dir or Path(tempfile.mkdtemp(prefix="vqa_"))
    times = [min(dur - 0.05, max(0.0, dur * i / (n - 1))) for i in range(n)]
    frames = []
    for i, t in enumerate(times, 1):
        f = out_dir / f"f{i:02d}.jpg"
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1",
                        "-vf", "scale='min(1280,iw)':-2", "-q:v", "3", str(f)], check=True)
        if f.exists():
            frames.append(f)
    return frames


def _keyframe_for(clip: Path) -> Path | None:
    """The start frame the clip was made from (manifest), else the shot's approved keyframe."""
    man = clip.parent / "manifest.json"
    if man.exists():
        try:
            d = json.loads(man.read_text(encoding="utf-8"))
            for it in d.get("items") or []:
                for k in ("image_path", "keyframe", "source_image"):
                    if it.get(k) and Path(it[k]).exists():
                        return Path(it[k])
        except Exception:  # noqa: BLE001
            pass
    from mtower import jobs
    from mtower.production import Production
    prod = Production.load("thunderbolt/ep01_romani")
    try:
        sl, _, _ = prod.find_shot(clip.parent.parent.name)
        return jobs.approved_keyframe(prod, sl["part"], clip.parent.parent.name)
    except Exception:  # noqa: BLE001
        return None


def review_clip(clip: Path, production: str = "thunderbolt", episode: str = "ep01_romani", frames: int = FRAMES) -> dict:
    from .batch_qa import design_text, references_for, production_rules
    sid = clip.parent.parent.name
    design = grounding.find_shot(production, episode, sid) or {}
    man = clip.parent / "manifest.json"
    motion = ""
    if man.exists():
        try:
            motion = json.loads(man.read_text(encoding="utf-8")).get("prompt", "")
        except Exception:  # noqa: BLE001
            pass
    adv = lessons.advise(lessons.tags_for_design(design, kind="clip"), department="video", limit=6,
                         text=lessons.design_text(design))
    talking = design.get("lip_sync") == "required" or "lipsync" in clip.parent.name
    shots = sample_frames(clip, frames)
    keyframe = _keyframe_for(clip)
    refs = [r for r in references_for(production, episode, design) if r[0].startswith("casting portrait")][:2]
    text = (f"{production_rules(production, episode)}\n\nSHOT DESIGN:\n{design_text(production, episode, design)}\n\n"
            f"MOTION PROMPT (what the clip must do): {motion or design.get('motion', '')}\n"
            f"Talking shot (judge lip_sync): {talking}\n"
            + (f"\nKNOWN FAILURE MODES (Learning Keeper) — check each:\n{adv.checks()}\n" if adv.lessons else "")
            + f"\nFrames follow in time order ({len(shots)} frames).")
    content: list[dict] = [{"type": "text", "text": text}]
    if keyframe:
        content += [{"type": "text", "text": "START KEYFRAME (reference, approved):"}, _image_part(str(keyframe))]
    for label, path in refs:
        p = _image_part(path)
        p["image_url"]["detail"] = "low"
        content += [{"type": "text", "text": f"{label} (reference):"}, p]
    for i, f in enumerate(shots, 1):
        content += [{"type": "text", "text": f"FRAME {i}:"}, _image_part(str(f))]
    raw, usage = client.complete([{"role": "system", "content": SYSTEM + "\nRespond ONLY with a single valid JSON object."},
                                  {"role": "user", "content": content}], vision=True,
                                 response_format={"type": "json_object"}, max_completion_tokens=5000)
    v = _parse_json(raw)
    v.update(clip=str(clip), shot=sid, frames=len(shots), keyframe=str(keyframe or ""), lessons=adv.ids,
             _cost_usd=_cost(usage, True))
    clip.with_suffix(".vqa.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    if v.get("verdict") != "pass":
        lessons.capture(kind="clip", target=sid, production=production, episode=episode, department="video",
                        source="studio-video-qa", resolved=False,
                        problem=" || ".join(f"[{i.get('category')}/{i.get('severity')}] {i.get('description', '')}"
                                            for i in v.get("issues") or [] if i.get("severity") in ("critical", "major"))[:1200],
                        fix=f"{v.get('fix_route', '')}: {v.get('fix_note', '')}",
                        score_before=v.get("score"), tags=lessons.tags_for_design(design, kind="clip",
                                                                                   model=_model_of(clip)))
    return v


def _model_of(clip: Path) -> str:
    man = clip.parent / "manifest.json"
    try:
        return json.loads(man.read_text(encoding="utf-8")).get("model_id", "") if man.exists() else ""
    except Exception:  # noqa: BLE001
        return ""


def find_clips(production: str, episode: str, shot_ids: list[str] | None = None, approved_only: bool = False) -> list[Path]:
    root = grounding.media_root() / "productions" / production / episode / "clips"
    out = []
    for c in sorted(root.rglob("*.mp4")):
        sid = c.parent.parent.name
        if shot_ids and sid not in shot_ids:
            continue
        if approved_only and not (c.parent / "approved.json").exists():
            continue
        out.append(c)
    return out
