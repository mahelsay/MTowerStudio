"""Narration with Azure Speech (the studio's Foundry resource): the screenplay's diacritized Arabic VO, one take per voice.

ElevenLabs stays the planned final narrator; Azure Speech gives a temporary or comparison voice at a tiny cost (billed per
character). Takes are saved as 48 kHz WAV under media/productions/<prod>/audio/vo/<beat>/<batch>/ with a manifest.
Standard library only.
"""

from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from . import costs
from .production import Production
from .settings import media_root, write_json

FORMAT = "riff-48khz-16bit-mono-pcm"


def narration_section(prod: Production, beat: str, script: str) -> str:
    """The raw '## <beat>' section of 03_production/voice/narration_<script>.md (including performance comments)."""
    from .settings import PRODUCTIONS_DIR
    path = PRODUCTIONS_DIR / prod.key / "03_production" / "voice" / f"narration_{script}.md"
    if not path.exists():
        raise KeyError(f"No narration script {path}")
    m = re.search(rf"^## {re.escape(beat)}\s*$(.*?)(?=^## |\Z)", path.read_text(encoding="utf-8"), re.M | re.S)
    if not m or not m.group(1).strip():
        raise KeyError(f"Beat {beat} has no section in {path.name}")
    return m.group(1).strip()


def narration_text(prod: Production, part: str, beat: str, script: str | None = None) -> str:
    """The beat's VO: from the screenplay (formal Arabic), or from 03_production/voice/narration_<script>.md
    (e.g. 'egyptian': everyday Egyptian Arabic), one '## <beat>' section per beat. '' = the script keeps this beat silent
    (section '—'); '<!-- ... -->' performance comments are left out."""
    if script:
        text = re.sub(r"<!--.*?-->", "", narration_section(prod, beat, script), flags=re.S).strip()
        return "" if text in ("—", "-") else text
    for path in prod.shot_list_paths():
        if part in path.stem:
            from .settings import load_json
            sl = load_json(path)
            text = prod.screenplay(sl).get(beat)
            if text and text.vo:
                return text.vo.strip()
            raise KeyError(f"Beat {beat} in {part} has no narration (VO) in the screenplay.")
    raise KeyError(f"No shot list part '{part}'.")


def ssml(text: str, voice: str, rate: str = "-6%", pause_ms: int = 450) -> str:
    """Narration SSML: a slower documentary pace, a pause at each ellipsis and between sentences."""
    body = html.escape(text, quote=False)
    body = body.replace("…", f'<break time="{pause_ms + 250}ms"/>')
    body = re.sub(r"\.\s+", f'.<break time="{pause_ms}ms"/> ', body)
    lang = "ar-EG"
    # multilingual voices need the language named; Arabic voices speak it natively
    inner = f'<lang xml:lang="{lang}">{body}</lang>' if not voice.startswith("ar-") else body
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" '
            f'xml:lang="{lang}"><voice name="{voice}"><prosody rate="{rate}">{inner}</prosody></voice></speak>')


def synthesize(client, voice: str, text: str, out: Path, rate: str = "-6%") -> int:
    """One take to a WAV file; returns the characters billed (the spoken text, not the SSML tags)."""
    body = ssml(text, voice, rate).encode("utf-8")
    req = urllib.request.Request(f"{client.endpoint}/tts/cognitiveservices/v1", data=body, method="POST", headers={
        "Authorization": f"Bearer {client.token()}", "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": FORMAT, "User-Agent": "mtower"})
    try:
        with urllib.request.urlopen(req, timeout=client.timeout) as resp:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(resp.read())
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"Azure Speech {voice} failed: HTTP {err.code} {err.read().decode('utf-8', 'replace')[:300]}") from None
    return len(text)


def plan_cost(text: str, voices: list[str]) -> list[costs.Estimate]:
    return [costs.estimate("voice_azure", len(text) / 1000 * len(voices))]


def run(prod: Production, part: str, beat: str, voices: list[str], rate: str, confirm_cost: float | None,
        script: str | None = None) -> Path:
    from .providers.azure import AzureClient

    text = narration_text(prod, part, beat, script)
    costs.authorize(plan_cost(text, voices), confirm_cost)
    client = AzureClient()
    out = media_root() / "productions" / prod.key / "audio" / "vo" / beat / datetime.now().strftime("%Y%m%d-%H%M%S")
    files, chars = [], 0
    m = costs.model("voice_azure")
    for voice in voices:
        name = re.sub(r"[^A-Za-z0-9]+", "-", voice).strip("-").lower() + ".wav"
        chars += synthesize(client, voice, text, out / name, rate)
        files.append(name)
        print(f"  ✓ {voice} -> {out / name}", flush=True)
    cost = round(chars / 1000 * m["price_usd"], 4)
    write_json(out / "manifest.json", {"kind": "narration", "target": f"{part} beat {beat}" + (f" ({script})" if script else ""),
                                       "model_id": "azure speech",
                                       "prompt": text, "items": [{"files": files, "voices": voices, "rate": rate,
                                                                  "characters": chars, "cost_usd_estimate": cost}]})
    costs.record({"production": prod.key, "provider": "azure", "kind": "narration", "target": f"{beat} ({len(voices)} voice(s))",
                  "model_id": "azure-speech", "units": round(chars / 1000, 3), "unit": m["unit"], "cost_usd": cost,
                  "out_dir": str(out)})
    return out


# ---- listen-back check: Azure speech-to-text on a take, compared with its script ---------------------------------
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640\u0591-\u05C7]")  # Arabic harakat, Hebrew niqqud and cantillation
_PUNCT = re.compile(r"[«»…،.:;؛,?!؟–—\-\"'()]")
STT_USD_PER_SECOND = 1.0 / 3600


def normalize(text: str) -> list[str]:
    """Words without diacritics, punctuation or hamza/ta-marbuta spelling differences."""
    text = _PUNCT.sub(" ", _DIACRITICS.sub("", text))
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي")):
        text = text.replace(a, b)
    return text.split()


def compare(expected: str, heard: str) -> dict:
    """How much of the script the recognizer heard: a 0–1 match and the script phrases it did not hear (numbers the
    recognizer wrote as digits count as heard)."""
    import difflib
    a, b = normalize(expected), normalize(heard)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    missing = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        said = b[j1:j2]
        if op == "delete" and i2 - i1 >= 2:
            missing.append(" ".join(a[i1:i2]))
        elif op == "replace" and i2 - i1 >= 3 and len(said) * 3 <= i2 - i1 and not all(w.isdigit() for w in said):
            missing.append(" ".join(a[i1:i2]))
    return {"match": round(sm.ratio(), 2), "missing": missing}


def transcribe(client, wav: Path, language: str = "ar-EG") -> tuple[str, float]:
    """(recognized text, seconds of speech) from Azure speech-to-text (short-audio REST, up to 60 s)."""
    import json
    req = urllib.request.Request(
        f"{client.endpoint}/stt/speech/recognition/conversation/cognitiveservices/v1?language={language}&format=detailed",
        data=wav.read_bytes(), method="POST",
        headers={"Authorization": f"Bearer {client.token()}", "Content-Type": "audio/wav", "User-Agent": "mtower"})
    try:
        with urllib.request.urlopen(req, timeout=client.timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"Azure speech-to-text failed: HTTP {err.code} {err.read().decode('utf-8', 'replace')[:300]}") from None
    best = (data.get("NBest") or [{}])[0]
    return best.get("Lexical", ""), data.get("Duration", 0) / 1e7


def check_beats(prod: Production, beats: list[str], min_match: float = 0.6) -> list[dict]:
    """Listen-back check of each beat's newest narration batch: every take is transcribed and compared with the text
    it was made from (the batch manifest's prompt). Saves <take>.check.json next to each WAV."""
    import json
    from .providers.azure import AzureClient

    client, rows, seconds = AzureClient(), [], 0.0
    root = media_root() / "productions" / prod.key / "audio" / "vo"
    for beat in beats:
        batches = sorted(p.parent for p in (root / beat).glob("*/manifest.json")) if (root / beat).exists() else []
        if not batches:
            rows.append({"beat": beat, "take": None, "match": 0.0, "missing": ["(no narration take)"], "ok": False})
            continue
        batch = batches[-1]
        expected = json.loads((batch / "manifest.json").read_text(encoding="utf-8")).get("prompt", "")
        for wav in sorted(batch.glob("*.wav")):
            heard, dur = transcribe(client, wav)
            seconds += dur
            result = {"beat": beat, "take": f"{batch.name}/{wav.name}", "heard": heard, **compare(expected, heard)}
            result["ok"] = result["match"] >= min_match and not result["missing"]
            write_json(wav.with_suffix(".check.json"), result)
            rows.append(result)
    if seconds:
        costs.record({"production": prod.key, "provider": "azure", "kind": "narration_check", "target": f"{len(beats)} beat(s)",
                      "model_id": "azure-speech-stt", "units": round(seconds, 1), "unit": "second",
                      "cost_usd": round(seconds * STT_USD_PER_SECOND, 4)})
    return rows
