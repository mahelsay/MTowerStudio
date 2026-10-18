"""Animatic: a beat (or several) as a moving storyboard — each shot's keyframe held for the shot's length with a slow
push-in, cut together, with the narration take laid underneath. Free (ffmpeg, local).

Picks per shot: the approved keyframe, else the candidate with the best QA score, else the newest keyframe.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import jobs
from .cards import X264
from .production import Production
from .settings import load_json, media_root


def ffmpeg() -> str:
    """ffmpeg from MTOWER_FFMPEG, PATH, or the winget install location."""
    found = os.environ.get("MTOWER_FFMPEG") or shutil.which("ffmpeg")
    if found:
        return found
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    for exe in sorted(root.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"), reverse=True):
        return str(exe)
    raise FileNotFoundError("ffmpeg not found: install it (winget install Gyan.FFmpeg) or set MTOWER_FFMPEG")


def best_keyframe(prod: Production, part: str, shot_id: str, prefer_best: bool = False) -> tuple[Path | None, str]:
    approved = jobs.approved_keyframe(prod, part, shot_id)
    if approved and not prefer_best:
        return approved, "approved"
    root = media_root() / "productions" / prod.key / "keyframes" / part / shot_id
    scored = []
    for qa_file in root.glob("*/*.qa.json") if root.exists() else []:
        image = qa_file.with_name(qa_file.name[: -len(".qa.json")] + ".png")
        if image.exists():
            scored.append((load_json(qa_file).get("score", 0), qa_file.parent.name, image))
    if scored:
        score, _, image = max(scored)
        return image, f"best QA {score}/10"
    latest = jobs.latest_keyframe(prod, part, shot_id)
    return latest, "newest" if latest else "missing"


def best_clip(prod: Production, part: str, shot_id: str) -> tuple[Path | None, str]:
    """The approved video clip of a shot, else its newest one."""
    root = media_root() / "productions" / prod.key / "clips" / part / shot_id
    if not root.exists():
        return None, "missing"
    for approval in sorted(root.glob("*/approved.json"), reverse=True):
        clip = approval.parent / load_json(approval).get("file", "")
        if clip.is_file():
            return clip, "approved clip"
    def rejected(p: Path) -> bool:
        marks = p.parent / "rejected.json"
        return marks.exists() and p.name in load_json(marks).get("files", [])

    newest = sorted((p for p in root.glob("*/*.mp4") if not rejected(p)), key=lambda p: (p.parent.name, p.name))
    return (newest[-1], "newest clip") if newest else (None, "missing")


def probe_seconds(exe: str, video: Path) -> float:
    probe = str(Path(exe).with_name("ffprobe" + Path(exe).suffix))
    out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                         check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    return float(out.strip() or 0)


def fit_filter(clip_s: float, shot_s: float, max_stretch: float = 1.3) -> str:
    """Video filter that fits a rendered clip to the shot's designed length at 1920x1080/24 fps: a short clip is slowed
    down (up to max_stretch) and then holds its last frame; a long clip is trimmed."""
    stretch = min(max(shot_s / clip_s, 1.0), max_stretch) if clip_s > 0 else 1.0
    chain = [f"setpts={stretch:.4f}*PTS"] if stretch > 1.0001 else []
    chain += ["scale=1920:1080:force_original_aspect_ratio=decrease", "pad=1920:1080:(ow-iw)/2:(oh-ih)/2", "setsar=1",
              "fps=24", f"tpad=stop_mode=clone:stop_duration={shot_s:.3f}", f"trim=duration={shot_s:.3f}",
              "setpts=PTS-STARTPTS", "format=yuv420p"]
    return ",".join(chain)


AMBIENCE = ("anoisesrc=color=brown:amplitude=0.6:sample_rate=48000,lowpass=f=500,highpass=f=40,"
            "tremolo=f=0.12:d=0.55,volume=0.22")


def playback_problems(exe: str, video: Path) -> list[str]:
    """Every H.264 parameter set in the file must be 4:2:0 8-bit (High profile or lower): one 4:4:4 shot in a
    stream-copied cut makes browsers stall and Windows players refuse the file at that shot."""
    out = subprocess.run([exe, "-hide_banner", "-i", str(video), "-map", "0:v", "-c", "copy", "-bsf:v", "trace_headers",
                          "-f", "null", "-"], capture_output=True, text=True, errors="replace", stdin=subprocess.DEVNULL).stderr
    bad = set()
    for key, ok in (("profile_idc", {66, 77, 100}), ("chroma_format_idc", {1}), ("bit_depth_luma_minus8", {0})):
        for line in out.splitlines():
            if key in line and "=" in line:
                value = int(line.rsplit("=", 1)[1])
                if value not in ok:
                    bad.add(f"{key}={value}")
    return sorted(bad)


def grade(prod: Production, beat: dict, shot: dict) -> str:
    """The colour grade of a shot (production_config grades, by look), as ',filter' to append, or ''."""
    grades = prod.config.get("grades") or {}
    looks = shot.get("look") or beat.get("look") or []
    found = [grades[k] for k in looks if k in grades and not k.startswith("_")]
    return ("," + ",".join(found)) if found else ""


def build(prod: Production, part: str, beats: list[str], voice: Path | None = None, vo_start: float = 1.0,
          prefer_best: bool = False, use_clips: bool = False, ambience: bool = False, dialogue: bool = False,
          narration: bool = False, sound: bool = False, english: bool = False) -> Path:
    """english: burn English subtitles in (card lines_en, super text_en, shot dialogue_en; see cards)."""
    from . import cards
    exe = ffmpeg()
    shots = [(b, s) for sl, b, s in prod.all_shots(part) if b["beat"] in beats
             and ((s.get("size") or s.get("shot_size")) != "CARD" or s.get("card"))]
    if not shots:
        raise KeyError(f"No shots for beat(s) {', '.join(beats)} in {part}")
    folder = "cut" if use_clips else "animatic"
    out_dir = media_root() / "productions" / prod.key / folder / "_".join(beats) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    parts, picks, starts, clock = [], [], {}, 0.0
    for n, (beat, shot) in enumerate(shots, 1):
        dur = float(shot.get("duration_s") or 5)
        starts[shot["shot_id"]] = clock
        clock += dur
        clip = out_dir / f"{n:02d}_{shot['shot_id']}.mp4"
        frames = int(dur * 24)
        if shot.get("card"):
            cards.render_card(exe, shot["card"], dur, clip, english)
            parts.append(clip)
            picks.append({"shot": shot["shot_id"], "seconds": dur, "pick": "title card"})
            print(f"  {shot['shot_id']:8} {dur:>4.0f}s  title card")
            continue
        video, why_video = best_clip(prod, part, shot["shot_id"]) if use_clips else (None, "")
        if video:
            seconds = probe_seconds(exe, video)
            synced = any(k in video.parent.name for k in ("lipsync", "avatar", "omnihuman", "h3-max"))  # never stretched
            args = [exe, "-y", "-loglevel", "error", "-i", str(video), "-an",
                    "-vf", fit_filter(seconds, dur, 1.0 if synced else 1.3) + grade(prod, beat, shot),
                    "-frames:v", str(frames), *X264, str(clip)]
            subprocess.run(args, check=True, capture_output=True, stdin=subprocess.DEVNULL)
            if shot.get("super"):
                cards.overlay_super(exe, clip, shot["super"], english)
            parts.append(clip)
            picks.append({"shot": shot["shot_id"], "seconds": dur, "clip": str(video), "clip_seconds": round(seconds, 2),
                          "pick": why_video})
            print(f"  {shot['shot_id']:8} {dur:>4.0f}s  {why_video:16} {video.parent.name}/{video.name} ({seconds:.1f}s)")
            continue
        image, why = best_keyframe(prod, part, shot["shot_id"], prefer_best)
        if use_clips:
            why = f"no clip; {why} keyframe"
        if image:
            vf = (f"scale=2560:1440,zoompan=z='min(zoom+0.0006,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":d={frames}:s=1920x1080:fps=24{grade(prod, beat, shot)},format=yuv420p")
            args = [exe, "-y", "-loglevel", "error", "-loop", "1", "-i", str(image), "-vf", vf, "-frames:v", str(frames),
                    *X264, str(clip)]
        else:
            args = [exe, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r=24:d={dur}",
                    *X264, str(clip)]
        subprocess.run(args, check=True, capture_output=True, stdin=subprocess.DEVNULL)
        if image and shot.get("super"):
            cards.overlay_super(exe, clip, shot["super"], english)
        parts.append(clip)
        picks.append({"shot": shot["shot_id"], "seconds": dur, "image": str(image) if image else None, "pick": why})
        print(f"  {shot['shot_id']:8} {dur:>4.0f}s  {why:16} {image.parent.name + '/' + image.name if image else '(black)'}")
    listing = out_dir / "concat.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    silent = out_dir / "video.mp4"
    subprocess.run([exe, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
                    "-movflags", "+faststart", str(silent)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    final = out_dir / f"{folder}_{'_'.join(beats)}.mp4"
    total = sum(float(s.get("duration_s") or 5) for _, s in shots)
    layout = "stereo" if sound else "mono"
    inputs, mix = [], []  # one mix entry per input, in order: input n+1 is mix entry n
    voices, effects = [], []
    if voice:
        delay = int(vo_start * 1000)
        inputs += ["-i", str(voice)]
        mix.append(f"[{len(mix) + 1}:a]aresample=48000,aformat=channel_layouts={layout},adelay={delay}|{delay},apad[vo]")
        voices.append("[vo]")
    if ambience:
        fade = max(total - 2, 0)
        inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", AMBIENCE]
        mix.append(f"[{len(mix) + 1}:a]aformat=channel_layouts={layout},afade=t=in:d=1.5,afade=t=out:st={fade:.3f}:d=2[amb]")
        effects.append("[amb]")
    lines_placed, subs = [], []
    if narration:  # the narrator's take of each beat, from the beat's first shot (plus vo_start)
        from . import dialogue as dlg
        beat_start = {}
        for b, s in shots:
            beat_start.setdefault(b["beat"], starts[s["shot_id"]])
        for beat in beats:
            take = dlg.narration_take(prod, beat)
            if take and beat in beat_start:
                lines_placed.append((take, beat_start[beat] + vo_start))
    if dialogue:
        from . import dialogue as dlg
        for beat in beats:
            placed = dlg.placed_lines(prod, beat, starts)
            lines_placed += [(f, start) for _, f, start in placed]
            subs += dlg.subtitle_events(placed, {s["shot_id"]: s.get("dialogue_en") for _, s in shots})
    if english and subs:
        cards.burn_subtitles(exe, silent, subs)
    for i, (take, start) in enumerate(lines_placed):
        ms = int(start * 1000)
        inputs += ["-i", str(take)]
        mix.append(f"[{len(mix) + 1}:a]aresample=48000,aformat=channel_layouts={layout},volume=1.5,adelay={ms}|{ms},apad[d{i}]")
        voices.append(f"[d{i}]")
    sound_layers = []
    if sound:
        from . import sound as snd
        sound_layers = snd.layers(prod, part, starts, set(starts))
        for j, layer in enumerate(sound_layers):
            seconds, ms = max(0.1, min(layer["seconds"], total - layer["start"])), int(layer["start"] * 1000)
            inputs += (["-stream_loop", "-1"] if layer["loop"] else []) + ["-i", str(layer["file"])]
            chain = (f"[{len(mix) + 1}:a]aresample=48000,aformat=channel_layouts={layout},"
                     + (f"atempo={layer['tempo']}," if layer.get("tempo") else "")
                     + f"atrim=0:{seconds:.3f},asetpts=PTS-STARTPTS")
            if layer["fade_in"]:
                chain += f",afade=t=in:d={min(layer['fade_in'], seconds):.3f}"
            if layer["fade_out"]:
                fo = min(layer["fade_out"], seconds)
                chain += f",afade=t=out:st={seconds - fo:.3f}:d={fo:.3f}"
            mix.append(chain + f",volume={layer['level']},adelay={ms}|{ms},apad[fx{j}]")
            effects.append(f"[fx{j}]")
    if mix:
        def bus(labels: list[str], name: str) -> str:
            return (f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0[{name}]" if len(labels) > 1
                    else f"{labels[0]}anull[{name}]")
        graph = ";".join(mix)
        if sound and voices and effects:  # effects and music duck under the voices
            graph += (f";{bus(voices, 'vb')};{bus(effects, 'fb')};[vb]asplit=2[vb1][vb2]"
                      ";[fb][vb1]sidechaincompress=threshold=0.035:ratio=5:attack=15:release=450[fbd]"
                      ";[vb2][fbd]amix=inputs=2:duration=longest:normalize=0[m]")
        else:
            graph += ";" + bus(voices + effects, "m")
        if sound:
            graph += ";[m]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,alimiter=limit=0.891:level=0[a]"
        else:
            graph += ";[m]alimiter=limit=0.891:level=0[a]"  # takes are boosted 1.5x and summed: keep peaks under -1 dBFS
        subprocess.run([exe, "-y", "-loglevel", "error", "-i", str(silent), *inputs, "-filter_complex", graph,
                        "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)], check=True, capture_output=True, stdin=subprocess.DEVNULL)
    else:
        silent.replace(final)
    problems = playback_problems(exe, final)
    if problems:
        raise RuntimeError(f"{final.name} would not play in browsers / Windows players: {problems}")
    for p in parts:
        p.unlink(missing_ok=True)
    listing.unlink(missing_ok=True)
    silent.unlink(missing_ok=True)
    (out_dir / f"{folder}.json").write_text(json.dumps({"part": part, "beats": beats, "voice": str(voice) if voice else None,
                                                        "ambience": ambience, "shots": picks,
                                                        "dialogue": [{"take": str(t), "start": round(s, 2)} for t, s in lines_placed],
                                                        "sound": [{**l, "file": str(l["file"]), "start": round(l["start"], 2)}
                                                                  for l in sound_layers]},
                                                       ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    kind = "cut" if use_clips else "animatic"
    (out_dir / "manifest.json").write_text(json.dumps({"kind": kind, "target": f"beat {' '.join(beats)}",
                                                       "model_id": "ffmpeg (local)", "prompt": "; ".join(
                                                           f"{p['shot']} {p['seconds']:.0f}s {p['pick']}" for p in picks)
                                                       + (f"; voice {voice.parent.name}/{voice.name}" if voice else "")
                                                       + (f"; dialogue {len(lines_placed)} line(s)" if dialogue else "")
                                                       + (f"; sound {len(sound_layers)} layer(s)" if sound else "")},
                                                      ensure_ascii=False, indent=2), encoding="utf-8")
    return final
