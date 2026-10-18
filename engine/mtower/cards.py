"""Title cards and on-screen captions, drawn locally with ffmpeg (free). Arabic is shaped by HarfBuzz/FriBiDi.

A CARD shot carries "card":
    {"style": "lines", "font": "Amiri-Regular.ttf", "size": 64, "lines": ["...", "..."],
     "first": 2.0, "gap": 2.5, "fade": 1.0, "hold_until": 12.5, "fade_out": 1.2}
  lines fade in one after another (first, first+gap, ...), hold together, then fade out at hold_until.
    {"style": "title", "font": "NotoKufiArabic-Black.ttf", "size": 220, "lines": ["..."], "first": 3.0, "fade": 2.5,
     "hold_until": 27.0, "fade_out": 2.0, "zoom": 0.04}
  one centred title with a slow push-in (zoom = how much it grows over the shot).
Any shot can carry "super" (a caption over the picture):
    {"text": "...", "start": 1.0, "duration": 4.0, "font": "Amiri-Regular.ttf", "size": 52}
English subtitles (cut built with english=True): card "lines_en" (one per Arabic line), super "text_en", and the shot's
"dialogue_en" (one entry per spoken line; an entry may be a list of parts shown one after another), burned in.
Fonts live in library/fonts (SIL Open Font License).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .settings import LIBRARY_DIR

FONTS = LIBRARY_DIR / "fonts"
W, H, FPS = 1920, 1080, 24
# Every shot part is encoded alike so the cut can be joined by stream copy and plays everywhere: grade filters work in
# RGB and would otherwise make libx264 pick 4:4:4 (High 4:4:4 profile), which browsers and Windows players refuse.
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.0"]


RLI, PDI = "\u2067", "\u2069"


def is_arabic(text: str) -> bool:
    return any("\u0600" <= c <= "\u06ff" or "\u0750" <= c <= "\u077f" or "\ufb50" <= c <= "\ufefc" for c in text)


def visual(line: str) -> str:
    """The text in logical order for ffmpeg's drawtext (HarfBuzz + FriBiDi), which lays Arabic words out right-to-left
    by itself — never reverse them (an earlier word-reversal printed every card backwards). drawtext runs FriBiDi with a
    left-to-right paragraph, though, so punctuation at the ends of an Arabic line (": … .") landed on the wrong side;
    a right-to-left isolate around the line fixes that. Measured 2026-10-18 (ffmpeg 9.0.2)."""
    line = line.strip()
    return f"{RLI}{line}{PDI}" if is_arabic(line) else line


def _alpha(start: float, fade: float, hold_until: float, fade_out: float) -> str:
    end = hold_until + fade_out
    return (f"if(lt(t,{start:.3f}),0,if(lt(t,{start + fade:.3f}),(t-{start:.3f})/{fade:.3f},"
            f"if(lt(t,{hold_until:.3f}),1,if(lt(t,{end:.3f}),1-(t-{hold_until:.3f})/{fade_out:.3f},0))))")


def _workdir(font: str, texts: list[str], en_font: str | None = None) -> Path:
    """ffmpeg filter arguments cannot hold Windows drive paths or raw Arabic safely: copy the font(s) and write each text
    to a file in a scratch folder (t0.txt, t1.txt, ...), and run ffmpeg there with relative names."""
    work = Path(tempfile.mkdtemp(prefix="mtower-card-"))
    for name, dest in ((font, "font.ttf"), (en_font, "font_en.ttf")):
        if not name:
            continue
        src = FONTS / name
        if not src.exists():
            raise FileNotFoundError(f"Font {name} not in {FONTS}")
        shutil.copy(src, work / dest)
    for i, t in enumerate(texts):
        (work / f"t{i}.txt").write_text(visual(t), encoding="utf-8")
    return work


def wrap(text: str, limit: int = 46) -> list[str]:
    """One subtitle line, or two balanced lines split at a space near the middle — preferably after a comma or
    before a dash."""
    text = " ".join(text.split())
    if len(text) <= limit or " " not in text:
        return [text]
    mid = len(text) / 2

    def cost(i: int) -> float:
        natural = text[i - 1] in ",;:.…?!" or text[i + 1:i + 2] in ("—", "–")
        return abs(i - mid) - (len(text) * 0.15 if natural else 0)
    cut = min((i for i, c in enumerate(text) if c == " "), key=cost)
    return [text[:cut], text[cut + 1:]]


def card_filter(card: dict, seconds: float, english: bool = False) -> tuple[str, Path]:
    """english: draw card["lines_en"] (a smaller English line under each Arabic line, fading in with it)."""
    lines = card["lines"]
    lines_en = (card.get("lines_en") or []) if english else []
    size = int(card.get("size", 64))
    size_en = int(card.get("size_en", round(size * 0.5)))
    work = _workdir(card.get("font", "Amiri-Regular.ttf"), lines + [t or "" for t in lines_en],
                    card.get("font_en", "NotoSans-Regular.ttf") if lines_en else None)
    fade, out = float(card.get("fade", 1.0)), float(card.get("fade_out", 1.2))
    hold = float(card.get("hold_until", seconds - out - 0.5))
    step = size * float(card.get("line_height_en" if lines_en else "line_height", 2.6 if lines_en else 1.7))
    en_drop = size * 0.62 + size_en if lines_en else 0.0  # Arabic baseline -> English baseline
    top = (H - step * (len(lines) - 1) - en_drop) / 2 + size * 0.35  # baseline of the first line
    color = card.get("color", "0xF2EDE4")
    chain = []
    for i in range(len(lines)):
        start = float(card.get("first", 1.5)) + i * float(card.get("gap", 2.5))
        alpha = _alpha(start, fade, hold, out)
        base = top + i * step
        chain.append(f"drawtext=fontfile=font.ttf:textfile=t{i}.txt:fontsize={size}:fontcolor={color}:"
                     f"x=(w-tw)/2:y={base:.0f}-ascent:alpha='{alpha}'")
        if i < len(lines_en) and lines_en[i]:
            chain.append(f"drawtext=fontfile=font_en.ttf:textfile=t{len(lines) + i}.txt:fontsize={size_en}:"
                         f"fontcolor={card.get('color_en', '0xB8B1A6')}:x=(w-tw)/2:y={base + en_drop:.0f}-ascent:"
                         f"alpha='{alpha}'")
    vf = ",".join(chain)
    if card.get("style") == "title" and card.get("zoom"):
        z = float(card["zoom"])
        vf += (f",scale=w='trunc({W}*(1+{z}*t/{seconds:.3f})/2)*2':h='trunc({H}*(1+{z}*t/{seconds:.3f})/2)*2':eval=frame,"
               f"crop={W}:{H}")
    vf += ",format=yuv420p"
    return vf, work


def render_card(exe: str, card: dict, seconds: float, dest: Path, english: bool = False) -> Path:
    vf, work = card_filter(card, seconds, english)
    try:
        subprocess.run([exe, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={seconds:.3f}",
                        "-vf", vf, "-frames:v", str(int(round(seconds * FPS))), *X264, str(dest.resolve())],
                       check=True, capture_output=True, stdin=subprocess.DEVNULL, cwd=work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return dest


def super_filter(sup: dict, english: bool = False) -> tuple[str, Path]:
    """english: draw sup["text_en"] smaller under the Arabic caption."""
    text_en = sup.get("text_en") if english else None
    size = int(sup.get("size", 52))
    size_en = int(sup.get("size_en", 32))
    work = _workdir(sup.get("font", "Amiri-Regular.ttf"), [sup["text"]] + ([text_en] if text_en else []),
                    sup.get("font_en", "NotoSans-Regular.ttf") if text_en else None)
    start, dur = float(sup.get("start", 1.0)), float(sup.get("duration", 4.0))
    fade = float(sup.get("fade", 0.6))
    alpha = _alpha(start, fade, start + dur - fade, fade)
    shadow = "shadowcolor=black@0.6:shadowx=2:shadowy=2"
    y = sup.get("y", f"h-{int(size * 2.6 + (size_en * 1.75 if text_en else 0))}")
    vf = (f"drawtext=fontfile=font.ttf:textfile=t0.txt:fontsize={size}:fontcolor={sup.get('color', '0xF2EDE4')}:"
          f"{shadow}:x=(w-tw)/2:y={y}:alpha='{alpha}'")
    if text_en:
        vf += (f",drawtext=fontfile=font_en.ttf:textfile=t1.txt:fontsize={size_en}:"
               f"fontcolor={sup.get('color_en', '0xE0DACF')}:{shadow}:x=(w-tw)/2:y=h-{int(size_en * 3.1)}:alpha='{alpha}'")
    return vf, work


def overlay_super(exe: str, clip: Path, sup: dict, english: bool = False) -> Path:
    """Burn a caption into a finished shot clip (in place)."""
    vf, work = super_filter(sup, english)
    tmp = clip.with_name(clip.stem + "_super.mp4")
    try:
        subprocess.run([exe, "-y", "-loglevel", "error", "-i", str(clip.resolve()), "-vf", vf, *X264, str(tmp.resolve())],
                       check=True, capture_output=True, stdin=subprocess.DEVNULL, cwd=work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    tmp.replace(clip)
    return clip


SUB_FONT, SUB_SIZE, SUB_BOTTOM = "NotoSans-Medium.ttf", 40, 64


def subtitle_filter(events: list[tuple[float, float, str]], size: int = SUB_SIZE) -> tuple[str, Path]:
    """Burned-in subtitles: events are (start s, end s, text) in cut time; each is one or two centred lines at the
    bottom, white with a dark outline, with a quick fade."""
    texts, chain = [], []
    for start, end, text in events:
        rows = wrap(text)
        for k, row in enumerate(rows):
            n = len(texts)
            texts.append(row)
            baseline = f"h-{SUB_BOTTOM + int((len(rows) - 1 - k) * size * 1.32)}"
            fade = min(0.12, (end - start) / 4)
            chain.append(f"drawtext=fontfile=font.ttf:textfile=t{n}.txt:fontsize={size}:fontcolor=0xF4F1EA:"
                         f"borderw=2:bordercolor=black@0.85:shadowcolor=black@0.5:shadowx=2:shadowy=2:"
                         f"x=(w-tw)/2:y={baseline}-ascent:enable='between(t,{start:.3f},{end:.3f})':"
                         f"alpha='{_alpha(start, fade, end - fade, fade)}'")
    return ",".join(chain), _workdir(SUB_FONT, texts)


def burn_subtitles(exe: str, video: Path, events: list[tuple[float, float, str]]) -> Path:
    """Burn subtitle events into a video (in place); any audio is copied."""
    if not events:
        return video
    vf, work = subtitle_filter(events)
    tmp = video.with_name(video.stem + "_subs.mp4")
    try:
        subprocess.run([exe, "-y", "-loglevel", "error", "-i", str(video.resolve()), "-vf", vf + ",format=yuv420p", *X264,
                        "-c:a", "copy", "-movflags", "+faststart", str(tmp.resolve())],
                       check=True, capture_output=True, stdin=subprocess.DEVNULL, cwd=work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    tmp.replace(video)
    return video
