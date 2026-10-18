"""Dialogue and character voices (D-20, D-21): every character has one fixed voice, and every line is performed with
its intensity, volume, pace, emotion and the situation it is spoken in.

- The cast lives in production_config.json → voice_cast (approved voice, or the approved audition in the review app).
- The performance of each line lives in the shot lists' dialogue_refs; the situation is built from the screenplay
  (scene heading, environment, and the action written before the line).
- Every take is checked by speech-to-text and re-recorded (up to N tries) until the words come out as written.
- Takes are loudness-matched to their volume (a whisper stays quieter than a shout), pitched (children) and filtered
  (radio) here, so lip-sync and the rough cut get the finished line.

Media: audio/dialogue/<beat>/L<n>-<speaker>/<batch>/ · audio/auditions/<speaker>/<batch>/ · audio/vo/<beat>/<batch>/.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import costs
from .production import Production
from .settings import PRODUCTIONS_DIR, load_json, media_root, write_json

VOLUMES = {  # how it sounds, and the loudness (LUFS) the finished take is matched to
    "whisper": ("whispered: breathy, almost no voiced tone, said close to one person's ear", -27),
    "low": ("low and quiet, held back, meant for one or two people nearby", -23),
    "normal": ("normal speaking level", -20),
    "raised": ("raised voice, projecting over noise or across a room", -18),
    "shout": ("shouting with full force", -16),
}
PACES = {"slow": "unhurried — the slowness lives in the pauses between phrases; every word itself at natural speed, never drawn out",
         "measured": "deliberate, but each word at natural Egyptian speed", "normal": "natural, brisk Egyptian conversational pace",
         "quick": "quick and clipped", "rushed": "rushed, the words tumbling out"}
TEMPO_RULE = ("Egyptians talk fast and clipped in everyday speech: say every word at natural Egyptian speed. Never stretch, "
              "drag or sing a vowel or a syllable, never slow the words down to sound emotional — feeling lives in the "
              "voice and the breath, and a pause (…) is a short silence between phrases, not a slower word.")
INTENSITY = [(2, "relaxed, at ease"), (4, "everyday, engaged"), (6, "tense: something real is at stake"),
             (8, "high stakes: urgent pressure in the body and the voice"), (10, "life or death: the peak of the scene")]
LANGUAGES = {
    "egyptian": ("Speak natural Egyptian Arabic (the Cairo dialect as spoken in the 1970s), never formal Arabic (fusha).", "ar-EG"),
    "msa": ("Speak formal Modern Standard Arabic (fusha) with the diction of a 1970s Egyptian state radio announcer.", "ar-EG"),
    "hebrew": ("Speak Hebrew with a native Israeli accent.", "he-IL"),
}
EXACT = "Read the text exactly as written, word for word; do not add, translate, explain or repeat anything."
FX = {"radio": "highpass=f=320,lowpass=f=3200,acompressor=threshold=-20dB:ratio=6:attack=5:release=60,"
               "acrusher=bits=10:mix=0.12,volume=1.4"}
ENGINE_MODEL = {"gpt-audio-1.5": "voice_gpt_audio", "gpt-4o-mini-tts": "voice_gpt_mini_tts", "azure-speech": "voice_azure"}
_HARAKAT = re.compile(r"[\u064B-\u0650\u0652\u0670\u0640]")  # every Arabic diacritic except shadda (U+0651)
ACCEPT_MATCH = 0.7


@dataclass
class Line:
    part: str
    beat: str
    n: int
    speaker: str
    text: str
    shot_id: str
    title: str
    situation: str
    perf: dict

    @property
    def key(self) -> str:
        return f"L{self.n}-{re.sub(r'[^A-Za-z0-9]+', '-', self.speaker).strip('-')}"


# ---- reading the script ---------------------------------------------------------------------------------------------
def lines(prod: Production, beat: str | None = None, part: str | None = None) -> list[Line]:
    """Every dialogue line of the production (or one beat / part) with its performance and situation."""
    out = []
    for path in prod.shot_list_paths():
        if part and part not in path.stem:
            continue
        sl = load_json(path)
        text = prod.screenplay(sl)
        for b in sl["beats"]:
            if beat and b["beat"] != beat:
                continue
            bt = text.get(b["beat"])
            for ref in b.get("dialogue_refs") or []:
                dl = bt.dialogue[ref["line"] - 1]
                perf = {k: ref[k] for k in ("intensity", "volume", "pace", "emotion", "delivery", "fx", "situation") if k in ref}
                situation = ref.get("situation") or bt.situation(ref["line"])
                out.append(Line(sl["part"], b["beat"], ref["line"], ref["speaker"], dl.text, ref.get("shot_id", ""),
                                bt.title or b.get("title", ""), situation, perf))
    return out


def check_performance(prod: Production) -> list[str]:
    """Problems with the performance fields and the voice cast (for 'check')."""
    problems, cast = [], prod.config.get("voice_cast", {})
    for ln in lines(prod):
        p, where = ln.perf, f"beat {ln.beat} line {ln.n} ({ln.speaker})"
        if not isinstance(p.get("intensity"), int) or not 1 <= p["intensity"] <= 10:
            problems.append(f"{where}: intensity must be 1–10")
        if p.get("volume") not in VOLUMES:
            problems.append(f"{where}: volume must be one of {', '.join(VOLUMES)}")
        if p.get("pace") not in PACES:
            problems.append(f"{where}: pace must be one of {', '.join(PACES)}")
        if not p.get("emotion") or not p.get("delivery"):
            problems.append(f"{where}: emotion and delivery are required")
        if p.get("fx") and p["fx"] not in FX:
            problems.append(f"{where}: unknown fx '{p['fx']}'")
        if ln.speaker not in cast:
            problems.append(f"{where}: speaker has no entry in production_config voice_cast")
    peaks = [f"{ln.beat} L{ln.n}" for ln in lines(prod) if ln.perf.get("intensity") == 10]
    if len(peaks) > 1:
        problems.append(f"intensity 10 is used {len(peaks)} times ({', '.join(peaks)}) — the episode has a single 10 "
                        "(performance guide); make the others 9")
    return problems


def speakable(text: str, language: str = "egyptian") -> str:
    """The text a voice model reads: Arabic without vowel marks (they push the models toward formal Arabic) but with the
    shadda, no quote marks or markup."""
    text = re.sub(r"[«»\"*]", "", text).strip()
    return _HARAKAT.sub("", text) if language != "hebrew" else text


# ---- the cast -----------------------------------------------------------------------------------------------------
def file_tag(entry: dict) -> str:
    tag = f"{entry['engine']}__{entry['voice']}"
    return tag + (f"__p{float(entry['pitch']):.2f}" if entry.get("pitch") and abs(float(entry["pitch"]) - 1) > 1e-6 else "")


def parse_tag(stem: str) -> dict:
    parts = stem.split("__")
    entry = {"engine": parts[0], "voice": parts[1]}
    if len(parts) > 2 and parts[2].startswith("p"):
        entry["pitch"] = float(parts[2][1:])
    return entry


def approved_audition(prod: Production, speaker: str) -> dict | None:
    root = media_root() / "productions" / prod.key / "audio" / "auditions" / slug(speaker)
    for approval in sorted(root.glob("*/approved.json"), reverse=True) if root.exists() else []:
        name = load_json(approval).get("file", "")
        if name:
            return {**parse_tag(Path(name).stem), "status": f"audition approved ({approval.parent.name})"}
    return None


def slug(speaker: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", speaker).strip("-")


def resolve(prod: Production, speaker: str) -> dict | None:
    """The speaker's voice: the cast entry's fixed voice, else its approved audition (None: not cast yet)."""
    entry = dict(prod.config.get("voice_cast", {}).get(speaker) or {})
    if not entry:
        return None
    if entry.get("engine") == "group" or entry.get("voice"):
        return entry
    picked = approved_audition(prod, speaker)
    return {**entry, **picked} if picked else None


def cast_status(prod: Production) -> list[dict]:
    rows, used = [], {}
    for line in lines(prod):
        used.setdefault(line.speaker, set()).add(line.beat)
    narr = prod.config.get("narration", {}).get("cast")
    for speaker, entry in prod.config.get("voice_cast", {}).items():
        if speaker.startswith("_"):
            continue
        r = resolve(prod, speaker)
        rows.append({"speaker": speaker, "name": entry.get("name", ""), "voice": file_tag(r) if r and r.get("voice") else
                     ("group" if r else None), "status": (r or {}).get("status", "cast" if r else "needs audition"),
                     "beats": sorted(used.get(speaker, [])) + (["narration"] if speaker == narr else []),
                     "candidates": len(entry.get("candidates", []))})
    return rows


def voice_clashes(prod: Production) -> list[str]:
    """Two characters with the same base voice (engine + voice, whatever the pitch) who speak in the same beat; the
    narrator counts as speaking in every beat it narrates."""
    rows = [r for r in cast_status(prod) if r["voice"] and r["voice"] != "group"]
    narr = prod.config.get("narration", {}).get("cast")
    for r in rows:
        if r["speaker"] == narr:
            r["beats"] = [b for b in r["beats"] if b != "narration"] + _narrated_beats(prod)
    base = lambda r: "__".join(r["voice"].split("__")[:2])  # noqa: E731
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            shared = set(a["beats"]) & set(b["beats"])
            if base(a) == base(b) and shared:
                out.append(f"{a['speaker']} and {b['speaker']} share {base(a)} in beat(s) {', '.join(sorted(shared))}")
    return out


def _narrated_beats(prod: Production) -> list[str]:
    from . import voice
    script, beats = prod.config.get("narration", {}).get("script"), []
    if not script:
        return beats
    for path in prod.shot_list_paths():
        for b in load_json(path)["beats"]:
            try:
                if voice.narration_text(prod, "", b["beat"], script):
                    beats.append(b["beat"])
            except KeyError:
                pass
    return beats


# ---- the acting direction -----------------------------------------------------------------------------------------
def intensity_words(n: int) -> str:
    return next(words for top, words in INTENSITY if n <= top)


def direction(entry: dict, perf: dict, title: str = "", situation: str = "") -> str:
    """The instructions a voice model performs from: language, character, situation, and this line's performance."""
    lang = LANGUAGES[entry.get("language", "egyptian")][0]
    n = int(perf.get("intensity", 5))
    vol = VOLUMES.get(perf.get("volume", "normal"))[0]
    parts = [lang, EXACT, f"Character: {entry.get('persona', '')}"]
    if title or situation:
        parts.append(f"Scene{(' — ' + title) if title else ''}: {situation}".strip())
    parts.append(f"This line: {perf.get('delivery', '')}")
    parts.append(f"Emotion: {perf.get('emotion', '')}. Intensity {n}/10 — {intensity_words(n)}. Volume: {vol}. "
                 f"Pace: {PACES.get(perf.get('pace', 'normal'))}.")
    if entry.get("language", "egyptian") == "egyptian":
        parts.append(TEMPO_RULE)
    parts.append("Play it like a film actor in this exact moment: real breath and tension, the emotion carried in the voice; "
                 + ("never relaxed or casual, never sleepy; " if n >= 6 else "") + "never theatrical or over the top.")
    return " ".join(p for p in parts if p)


# ---- engines -------------------------------------------------------------------------------------------------------
def _post(client, url: str, body: dict) -> bytes:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": "Bearer " + client.token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=max(client.timeout, 180)) as resp:
            return resp.read()
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"HTTP {err.code} {err.read().decode('utf-8', 'replace')[:300]}") from None
    except OSError as err:  # connection reset / timeout: the caller may retry
        raise RuntimeError(f"network error: {err}") from None


def _token_cost(usage: dict) -> float:
    p = costs.model("voice_gpt_audio")["pricing_per_m_tokens"]
    pin, pout = usage.get("prompt_tokens_details") or {}, usage.get("completion_tokens_details") or {}
    audio_in, audio_out = pin.get("audio_tokens", 0) or 0, pout.get("audio_tokens", 0) or 0
    text_in = (usage.get("prompt_tokens", 0) or 0) - audio_in
    text_out = (usage.get("completion_tokens", 0) or 0) - audio_out
    return round((text_in * p["text_input_per_m"] + audio_in * p["audio_input_per_m"] + text_out * p["text_output_per_m"]
                  + audio_out * p["audio_output_per_m"]) / 1e6, 5)


def _ssml(text: str, voice: str, lang: str, perf: dict) -> str:
    import html
    rate = {"slow": "-12%", "measured": "-6%", "normal": "0%", "quick": "+8%", "rushed": "+15%"}[perf.get("pace", "normal")]
    volume = {"whisper": "x-soft", "low": "soft", "normal": "medium", "raised": "loud", "shout": "x-loud"}[perf.get("volume", "normal")]
    body = html.escape(text, quote=False).replace("…", '<break time="500ms"/>')
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{lang}"><voice name="{voice}">'
            f'<prosody rate="{rate}" volume="{volume}">{body}</prosody></voice></speak>')


def render_raw(client, entry: dict, text: str, instructions: str, perf: dict, out: Path) -> float:
    """One raw take from the entry's engine into out (WAV); returns the cost in USD."""
    engine = entry["engine"]
    if engine == "gpt-audio-1.5":
        m = costs.model("voice_gpt_audio")
        data = json.loads(_post(client, f"{client.endpoint}/openai/deployments/{m['model_id']}/chat/completions?api-version={m['api_version']}",
                                {"modalities": ["text", "audio"], "audio": {"voice": entry["voice"], "format": "wav"},
                                 "messages": [{"role": "system", "content": "You are a voice actor. " + instructions},
                                              {"role": "user", "content": "Perform this line exactly:\n" + text}]}))
        out.write_bytes(base64.b64decode(data["choices"][0]["message"]["audio"]["data"]))
        return _token_cost(data.get("usage") or {})
    if engine == "gpt-4o-mini-tts":
        m = costs.model("voice_gpt_mini_tts")
        out.write_bytes(_post(client, f"{client.endpoint}/openai/deployments/{m['model_id']}/audio/speech?api-version={m['api_version']}",
                              {"model": "gpt-4o-mini-tts", "input": text, "voice": entry["voice"], "response_format": "wav",
                               "instructions": instructions}))
        return round(m["per_call_usd"] + _seconds(out) * m["price_usd"], 5)
    if engine == "azure-speech":
        lang = LANGUAGES[entry.get("language", "egyptian")][1]
        req = urllib.request.Request(f"{client.endpoint}/tts/cognitiveservices/v1",
                                     data=_ssml(text, entry["voice"], lang, perf).encode("utf-8"), method="POST",
                                     headers={"Authorization": "Bearer " + client.token(), "Content-Type": "application/ssml+xml",
                                              "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm", "User-Agent": "mtower"})
        try:
            with urllib.request.urlopen(req, timeout=client.timeout) as resp:
                out.write_bytes(resp.read())
        except urllib.error.HTTPError as err:
            raise RuntimeError(f"Azure Speech HTTP {err.code} {err.read().decode('utf-8', 'replace')[:300]}") from None
        return round(len(text) / 1000 * costs.model("voice_azure")["price_usd"], 5)
    raise ValueError(f"Unknown voice engine '{engine}'")


def _ffmpeg() -> str:
    from .animatic import ffmpeg
    return ffmpeg()


def _seconds(wav: Path) -> float:
    from .animatic import probe_seconds
    return probe_seconds(_ffmpeg(), wav)


def finish(raw: Path, out: Path, perf: dict, pitch: float | None = None, tempo: float = 1.0) -> None:
    """48 kHz mono, pitch (children), tempo (pitch-preserving speed-up), fx (radio), loudness matched to the volume."""
    chain = ["aresample=48000",
             # trim leading/trailing silence (the models often add a second of air): lip-sync and cut timing need the words
             "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08",
             "areverse", "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15", "areverse"]
    if pitch and abs(pitch - 1) > 1e-6:
        chain += [f"asetrate={int(48000 * pitch)}", "aresample=48000", f"atempo={1 / pitch:.4f}"]
    if tempo and abs(tempo - 1) > 1e-6:
        chain.append(f"atempo={tempo:.4f}")
    if perf.get("fx") in FX:
        chain.append(FX[perf["fx"]])
    chain.append(f"loudnorm=I={VOLUMES.get(perf.get('volume', 'normal'))[1]}:TP=-2:LRA=11")
    chain.append("aresample=48000")
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(raw), "-af", ",".join(chain), "-ac", "1",
                    "-c:a", "pcm_s16le", str(out)], check=True, stdin=subprocess.DEVNULL)


def _group(client, entry: dict, text: str, instructions: str, perf: dict, out: Path) -> float:
    """A murmur: each member says the line, offset a little, mixed together."""
    tmp, cost = [], 0.0
    for i, member in enumerate(entry.get("members", [])):
        raw = out.with_name(f"{out.stem}.m{i}.wav")
        cost += render_raw(client, member, text, instructions, perf, raw)
        tmp.append(raw)
    args = [_ffmpeg(), "-y", "-loglevel", "error"]
    for raw in tmp:
        args += ["-i", str(raw)]
    graph = ";".join(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={i * 230 + (i % 2) * 90},volume={1 - i * 0.12:.2f}[m{i}]"
                     for i in range(len(tmp)))
    graph += ";" + "".join(f"[m{i}]" for i in range(len(tmp))) + f"amix=inputs={len(tmp)}:duration=longest:normalize=0[a]"
    subprocess.run(args + ["-filter_complex", graph, "-map", "[a]", str(out)], check=True, stdin=subprocess.DEVNULL)
    for raw in tmp:
        raw.unlink(missing_ok=True)
    return cost


def take(client, entry: dict, text: str, instructions: str, perf: dict, out: Path, tries: int = 3,
         tempo: float = 1.0) -> dict:
    """A finished take, re-recorded until speech-to-text hears the line as written (best of <tries>)."""
    from . import voice
    language = entry.get("language", "egyptian")
    spoken = speakable(text, language)
    best, cost, attempts = None, 0.0, []
    raw = out.with_name(out.stem + ".raw.wav")
    words = len(spoken.split())
    short = words <= 2  # speech-to-text cannot judge one or two (often whispered) words; the ear decides
    limit = max_seconds(spoken)
    errors, fallback = [], None
    for attempt in range(1, tries + 2):
        if attempt > tries and best is not None:
            break
        try:
            if entry.get("engine") == "group":
                cost += _group(client, entry, spoken, instructions, perf, raw)
            else:
                cost += render_raw(client, entry, spoken, instructions, perf, raw)
        except RuntimeError as err:  # e.g. HTTP 500 "the model produced invalid content": one more try
            errors.append(str(err)[:200])
            if attempt > tries:
                break
            continue
        if entry.get("engine") == "group":
            best = (1.0, raw.read_bytes(), "", [])
            break
        secs = _seconds(raw)
        if secs > limit:  # the model rambled or added words: never keep it if anything better comes
            attempts.append({"try": attempt, "too_long_s": round(secs, 1), "limit_s": round(limit, 1)})
            if fallback is None or secs < fallback[0]:
                fallback = (secs, raw.read_bytes())
            continue
        probe = out.with_name(out.stem + ".16k.wav")
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(raw), "-ar", "16000", "-ac", "1", str(probe)],
                       check=True, stdin=subprocess.DEVNULL)
        heard, seconds = voice.transcribe(client, probe, LANGUAGES[language][1])
        probe.unlink(missing_ok=True)
        cost += seconds * voice.STT_USD_PER_SECOND
        r = voice.compare(text, heard)
        attempts.append({"try": attempt, "match": r["match"], "missing": r["missing"], "heard": heard})
        if best is None or r["match"] > best[0]:
            best = (r["match"], raw.read_bytes(), heard, r["missing"])
        if r["match"] >= ACCEPT_MATCH and not r["missing"]:
            break
        if short:
            break
    if best is None and fallback is not None:
        best = (0.0, fallback[1], "(every try ran too long — kept the shortest)", ["too long"])
    if best is None:
        raise RuntimeError("no take: " + " | ".join(errors))
    raw.write_bytes(best[1])
    finish(raw, out, perf, entry.get("pitch"), tempo if entry.get("language", "egyptian") == "egyptian" else 1.0)
    raw.unlink(missing_ok=True)
    return {"match": best[0], "heard": best[2], "missing": best[3], "ok": best[0] >= ACCEPT_MATCH and not best[3],
            "tries": len(attempts) or 1, "attempts": attempts, "seconds": round(_seconds(out), 2), "cost_usd": round(cost, 5)}


# ---- planning ------------------------------------------------------------------------------------------------------
def max_seconds(text: str) -> float:
    """Longest believable take for a line: longer means the voice model added or repeated words."""
    return 2.0 + 1.2 * len(speakable(text).split())


def est_seconds(text: str) -> float:
    return max(2.0, len(speakable(text).split()) / 2.0 + 1.0)


def take_estimate(entry: dict, text: str, tries: int) -> list[costs.Estimate]:
    members = entry.get("members") if entry.get("engine") == "group" else [entry]
    out = []
    for m in members:
        key = ENGINE_MODEL[m["engine"]]
        model = costs.model(key)
        if key == "voice_azure":
            out.append(costs.estimate(key, len(text) / 1000 * tries))
        else:
            out.append(costs.estimate(key, est_seconds(text) * tries, [("usd", model.get("per_call_usd", 0) * tries)]))
    return out


def _record(prod: Production, kind: str, target: str, entry: dict, cost: float, out: Path) -> None:
    engine = entry.get("engine")
    costs.record({"production": prod.key, "provider": "azure", "kind": kind, "target": target,
                  "model_id": f"{engine} {entry.get('voice', '')}".strip(), "units": 1, "unit": "take",
                  "cost_usd": round(cost, 5), "out_dir": str(out)})


def _client():
    from .providers.azure import AzureClient
    return AzureClient()


# ---- commands ------------------------------------------------------------------------------------------------------
def plan_dialogue(prod: Production, beat: str, only: list[int] | None = None, tries: int = 3):
    todo, missing = [], []
    for ln in lines(prod, beat):
        if only and ln.n not in only:
            continue
        entry = resolve(prod, ln.speaker)
        (todo.append((ln, entry)) if entry else missing.append(ln.speaker))
    estimates = [e for ln, entry in todo for e in take_estimate(entry, ln.text, tries)]
    return todo, sorted(set(missing)), estimates


def dialogue_tempo(prod: Production) -> float:
    """Global pitch-preserving speed-up of finished Egyptian takes (production_config dialogue.tempo; user note 2026-10-16:
    the voices drag their words)."""
    return float((prod.config.get("dialogue") or {}).get("tempo", 1.0))


def run_dialogue(prod: Production, beat: str, only: list[int] | None, confirm_cost: float | None, tries: int = 3) -> list[dict]:
    todo, missing, estimates = plan_dialogue(prod, beat, only, tries)
    if missing:
        raise KeyError(f"Not cast yet: {', '.join(missing)} — run 'audition' and approve a voice in the review app (Voice casting)")
    if not todo:
        raise KeyError(f"No dialogue lines in beat {beat}")
    costs.authorize(estimates, confirm_cost)
    client, stamp, rows = _client(), datetime.now().strftime("%Y%m%d-%H%M%S"), []
    for ln, entry in todo:
        out_dir = media_root() / "productions" / prod.key / "audio" / "dialogue" / beat / ln.key / stamp
        out_dir.mkdir(parents=True, exist_ok=True)
        instructions = direction(entry, ln.perf, ln.title, ln.situation)
        name = f"{(ln.shot_id or beat).lower().replace('.', '-')}_{slug(ln.speaker).lower()}.wav"
        result = take(client, entry, ln.text, instructions, ln.perf, out_dir / name, tries, dialogue_tempo(prod))
        p = ln.perf
        write_json(out_dir / "take.json", {"beat": beat, "line": ln.n, "speaker": ln.speaker, "shot_id": ln.shot_id,
                                           "text": ln.text, "voice": file_tag(entry) if entry.get("voice") else "group",
                                           "performance": p, "direction": instructions, "tempo": dialogue_tempo(prod),
                                           **result, "file": name})
        write_json(out_dir / "manifest.json", {
            "kind": "dialogue", "target": f"{beat} line {ln.n} · {entry.get('name', ln.speaker)}",
            "model_id": file_tag(entry) if entry.get("voice") else "group",
            "prompt": f"{ln.text}\n\n[{p.get('intensity')}/10 · {p.get('volume')} · {p.get('pace')}] {p.get('emotion')} — "
                      f"{p.get('delivery')}" + (f" · fx {p['fx']}" if p.get("fx") else ""),
            "items": [{"files": [name], "match": result["match"], "tries": result["tries"], "cost_usd_estimate": result["cost_usd"]}]})
        _record(prod, "dialogue", f"{beat} L{ln.n} {ln.speaker}", entry, result["cost_usd"], out_dir)
        rows.append({"line": ln, "dir": out_dir, **result})
    return rows


def _take_matches(folder: Path, text: str) -> bool:
    """A take belongs to a line only while the line's words are unchanged (lines are renumbered when a beat is rewritten)."""
    meta = folder / "take.json"
    if not meta.is_file():
        return True
    return load_json(meta).get("text", text) == text


def best_take(prod: Production, beat: str, ln: Line) -> Path | None:
    """The approved take of a line, else its newest — only takes recorded with the line's current words."""
    root = media_root() / "productions" / prod.key / "audio" / "dialogue" / beat / ln.key
    if not root.exists():
        return None
    for approval in sorted(root.glob("*/approved.json"), reverse=True):
        f = approval.parent / load_json(approval).get("file", "")
        if f.is_file() and _take_matches(approval.parent, ln.text):
            return f
    takes = sorted((p for p in root.glob("*/*.wav") if not p.name.endswith((".raw.wav", ".16k.wav"))
                    and _take_matches(p.parent, ln.text)), key=lambda p: (p.parent.name, p.name))
    passed = [p for p in takes if (p.parent / "take.json").is_file() and load_json(p.parent / "take.json").get("ok")]
    if len(speakable(ln.text).split()) <= 2:  # speech-to-text cannot judge one or two words: the newest take
        passed = []
    return (passed or takes)[-1] if takes else None  # the newest take speech-to-text accepted, else the newest


def audition_samples(prod: Production, speaker: str) -> list[tuple[str, dict, str, str]]:
    """(text, performance, title, situation) samples for an audition: the speaker's calmest and most intense lines,
    or for the narrator the configured narration beats."""
    entry = prod.config.get("voice_cast", {}).get(speaker, {})
    if entry.get("audition_narration"):
        out = []
        for beat in entry["audition_narration"]:
            text, perf = narration(prod, beat)
            out.append((text, perf, f"narration {beat}", NARRATOR_SITUATION))
        return out
    own = [ln for ln in lines(prod) if ln.speaker == speaker]
    if not own:
        return []
    low = min(own, key=lambda ln: (ln.perf.get("intensity", 5), -len(ln.text)))
    high = max(own, key=lambda ln: (ln.perf.get("intensity", 5), len(ln.text)))
    picks = [low] if low is high else [low, high]
    return [(ln.text, ln.perf, ln.title, ln.situation) for ln in picks]


def plan_audition(prod: Production, speaker: str, tries: int = 3):
    entry = prod.config.get("voice_cast", {}).get(speaker)
    if not entry:
        raise KeyError(f"{speaker} has no entry in production_config voice_cast")
    candidates = [{**entry, **c} for c in entry.get("candidates", [])] or ([entry] if entry.get("voice") or entry.get("engine") == "group" else [])
    samples = audition_samples(prod, speaker)
    estimates = [e for c in candidates for text, *_ in samples for e in take_estimate(c, text, tries)]
    return entry, candidates, samples, estimates


def run_audition(prod: Production, speaker: str, confirm_cost: float | None, tries: int = 3) -> Path:
    entry, candidates, samples, estimates = plan_audition(prod, speaker, tries)
    if not candidates or not samples:
        raise KeyError(f"{speaker}: nothing to audition (no candidates or no lines)")
    costs.authorize(estimates, confirm_cost)
    client = _client()
    out_dir = media_root() / "productions" / prod.key / "audio" / "auditions" / slug(speaker) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    items, total = [], 0.0
    for cand in candidates:
        parts, results = [], []
        try:
            for i, (text, perf, title, situation) in enumerate(samples):
                part = out_dir / f"{file_tag(cand)}.s{i}.wav"
                r = take(client, cand, text, direction(cand, perf, title, situation), perf, part, tries)
                parts.append(part)
                results.append({"text": text, "intensity": perf.get("intensity"), "volume": perf.get("volume"),
                                "match": r["match"], "tries": r["tries"], "heard": r["heard"]})
                total += r["cost_usd"]
        except RuntimeError as err:
            for p in parts:
                p.unlink(missing_ok=True)
            print(f"  ✗ {file_tag(cand):34} {str(err)[:160]}", flush=True)
            continue
        final = out_dir / f"{file_tag(cand)}.wav"
        args = [_ffmpeg(), "-y", "-loglevel", "error"]
        for p in parts:
            args += ["-i", str(p)]
        graph = "".join(f"[{i}:a]apad=pad_dur=0.8[p{i}];" for i in range(len(parts))) + \
                "".join(f"[p{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[a]"
        subprocess.run(args + ["-filter_complex", graph, "-map", "[a]", "-c:a", "pcm_s16le", str(final)], check=True,
                       stdin=subprocess.DEVNULL)
        for p in parts:
            p.unlink(missing_ok=True)
        items.append({"files": [final.name], "voice": file_tag(cand), "samples": results})
        print(f"  ✓ {file_tag(cand):34} " + "  ".join(f"[{s['intensity']}/10 match {s['match']:.2f}]" for s in results), flush=True)
    if not items:
        raise RuntimeError(f"{speaker}: every candidate failed")
    write_json(out_dir / "manifest.json", {
        "kind": "audition", "target": f"voice {speaker} · {entry.get('name', speaker)}",
        "model_id": ", ".join(i["voice"] for i in items),
        "prompt": f"{entry.get('persona', '')}\n\nSamples (calm, then intense): " + " || ".join(
            f"[{p.get('intensity')}/10 {p.get('volume')}] {t}" for t, p, *_ in samples), "items": items})
    _record(prod, "audition", speaker, {"engine": "mixed", "voice": f"{len(candidates)} candidates"}, total, out_dir)
    return out_dir


# ---- narration by the cast narrator ---------------------------------------------------------------------------------
NARRATOR_SITUATION = ("He sits at home, fifty years after the war, and tells the story of the Romani ambush to his "
                      "grandchildren in his own words; the pictures on screen are his memory.")
_PERF_COMMENT = re.compile(r"<!--\s*(.*?)\s*-->", re.S)


def narration(prod: Production, beat: str, script: str | None = None) -> tuple[str, dict]:
    """(text, performance) of a beat in the narration script; performance from a '<!-- intensity: 6; volume: low;
    pace: slow; emotion: ... -->' comment in the beat's section. Text '' = the beat is deliberately silent."""
    from . import voice
    script = script or prod.config.get("narration", {}).get("script")
    raw = voice.narration_section(prod, beat, script)
    perf = {"intensity": 5, "volume": "low", "pace": "measured", "emotion": "remembering",
            "delivery": "Telling it to his grandchildren, intimate and plain; the memory moves him."}
    m = _PERF_COMMENT.search(raw)
    if m:
        for item in m.group(1).split(";"):
            if ":" in item:
                k, v = (s.strip() for s in item.split(":", 1))
                perf[k] = int(v) if k == "intensity" else v
    text = _PERF_COMMENT.sub("", raw).strip()
    return ("" if text in ("—", "-") else text), perf


def run_narration(prod: Production, part: str, beat: str, confirm_cost: float | None, tries: int = 3) -> Path:
    speaker = prod.config.get("narration", {}).get("cast", "N-01")
    entry = resolve(prod, speaker)
    if not entry:
        raise KeyError(f"The narrator {speaker} is not cast yet — run 'audition {speaker}' and approve a voice")
    text, perf = narration(prod, beat)
    if not text:
        raise KeyError(f"Beat {beat} is silent in the narration script (no narration)")
    costs.authorize(take_estimate(entry, text, tries), confirm_cost)
    sl = prod.shot_list(part)
    bt = prod.screenplay(sl).get(beat)
    memory = (bt.situation(10 ** 6) if bt else "")
    instructions = direction(entry, perf, f"narration over beat {beat}", NARRATOR_SITUATION + " What he sees: " + memory)
    out = media_root() / "productions" / prod.key / "audio" / "vo" / beat / datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{slug(speaker).lower()}-{file_tag(entry).replace('__', '-')}.wav"
    client = _client()
    out.mkdir(parents=True, exist_ok=True)
    result = take(client, entry, text, instructions, perf, out / name, tries)
    write_json(out / "take.json", {"beat": beat, "speaker": speaker, "text": text, "performance": perf,
                                   "direction": instructions, **result, "file": name})
    write_json(out / "manifest.json", {"kind": "narration", "target": f"{part} beat {beat} ({prod.config.get('narration', {}).get('script')})",
                                       "model_id": file_tag(entry), "prompt": text,
                                       "items": [{"files": [name], "match": result["match"], "cost_usd_estimate": result["cost_usd"]}]})
    _record(prod, "narration", f"{beat} {speaker}", entry, result["cost_usd"], out)
    return out


# ---- lip-sync ------------------------------------------------------------------------------------------------------
LIPSYNC = {"kling-avatar-v2-pro": "lipsync_kling_avatar", "omnihuman-1.5": "lipsync_omnihuman", "minimax-h3-max": "lipsync_minimax"}
LEAD_IN = 0.4  # seconds of breath before the first line of a talking shot


def lipsync_plan(prod: Production, beat: str, shots: list[str] | None = None) -> list[dict]:
    """Talking shots of a beat (lip_sync 'required'): keyframe, the takes in the shot, and the audio length."""
    from .animatic import best_keyframe
    plan = []
    by_shot: dict[str, list[Line]] = {}
    for ln in lines(prod, beat):
        by_shot.setdefault(ln.shot_id, []).append(ln)
    for sl, b, shot in prod.all_shots():
        if b["beat"] != beat or shot.get("lip_sync") != "required" or (shots and shot["shot_id"] not in shots):
            continue
        sid = shot["shot_id"]
        takes = [(ln, best_take(prod, beat, ln)) for ln in by_shot.get(sid, [])]
        image, why = best_keyframe(prod, sl["part"], sid)
        plan.append({"shot": shot, "part": sl["part"], "keyframe": image, "keyframe_pick": why, "lines": takes,
                     "speakers": sorted({ln.speaker for ln, _ in takes})})
    return plan


def fit_talking_shots(prod: Production, part: str, apply: bool = False) -> list[tuple[str, float, int]]:
    """Talking shots sized to their current takes: lead-in + lines + gaps + a short tail (min 2 s). Shots were planned
    from estimates; when takes get faster (dialogue.tempo) a long shot just holds a silent face. Edits the shot list in
    place (only each shot's duration_s) when apply is True. Returns (shot, seconds of audio, new duration)."""
    import math
    import re as _re
    path = next(p for p in prod.shot_list_paths() if part in p.stem)
    sl = load_json(path)
    changes = []
    for b in sl["beats"]:
        for item in lipsync_plan(prod, b["beat"]):
            if item["part"] != sl["part"]:
                continue
            files = [f for _, f in item["lines"] if f]
            if not files or len(files) != len(item["lines"]):
                continue
            audio = LEAD_IN + sum(_seconds(f) for f in files) + 0.35 * (len(files) - 1)
            new = max(2, math.ceil(audio + 0.6))
            if new != item["shot"].get("duration_s"):
                changes.append((item["shot"]["shot_id"], round(audio, 2), new))
    if apply and changes:
        text = path.read_text(encoding="utf-8")
        for sid, _, new in changes:
            text, n = _re.subn(r'("shot_id": "' + _re.escape(sid) + r'",\s*"duration_s": )[0-9.]+', r"\g<1>" + str(new), text)
            if not n:
                raise ValueError(f"{sid}: could not find its duration_s right after shot_id in {path.name}")
        path.write_text(text, encoding="utf-8")
    return changes


def lipsync_audio(item: dict, out: Path) -> float:
    """The shot's soundtrack for lip-sync: a short breath, then each line in order, padded to the shot length."""
    shot_s = float(item["shot"].get("duration_s") or 5)
    files = [f for _, f in item["lines"]]
    args = [_ffmpeg(), "-y", "-loglevel", "error"]
    for f in files:
        args += ["-i", str(f)]
    lead = int(LEAD_IN * 1000)
    graph = "".join(f"[{i}:a]aresample=44100,aformat=channel_layouts=mono" + (f",adelay={lead}" if i == 0 else "")
                    + f",apad=pad_dur={0.35 if i < len(files) - 1 else 0}[a{i}];" for i in range(len(files)))
    graph += "".join(f"[a{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=0:a=1,apad=whole_dur={shot_s}[a]"
    subprocess.run(args + ["-filter_complex", graph, "-map", "[a]", "-ac", "1", str(out)], check=True, stdin=subprocess.DEVNULL)
    return _seconds(out)


def run_lipsync(prod: Production, beat: str, model: str, confirm_cost: float | None, shots: list[str] | None = None) -> list[dict]:
    from .providers.fal import FalClient, download
    plan = lipsync_plan(prod, beat, shots)
    problems = [f"{p['shot']['shot_id']}: no keyframe" for p in plan if not p["keyframe"]]
    problems += [f"{p['shot']['shot_id']}: line {ln.n} ({ln.speaker}) has no take — run 'dialogue --beat {beat}'"
                 for p in plan for ln, f in p["lines"] if not f]
    problems += [f"{p['shot']['shot_id']}: no dialogue line in this shot" for p in plan if not p["lines"]]
    if problems:
        raise KeyError("; ".join(problems))
    if not plan:
        raise KeyError(f"Beat {beat} has no talking shots (lip_sync 'required')")
    key = LIPSYNC[model]
    m = costs.model(key)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    work = media_root() / "productions" / prod.key / "audio" / "lipsync" / beat / stamp
    work.mkdir(parents=True, exist_ok=True)
    for p in plan:
        p["audio"] = work / f"{p['shot']['shot_id'].lower().replace('.', '-')}.wav"
        p["seconds"] = lipsync_audio(p, p["audio"])
    try:
        costs.authorize([costs.estimate(key, max(p["seconds"], 5.0 if model == "minimax-h3-max" else 0)) for p in plan],
                        confirm_cost)
    except costs.SpendingError:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
        raise
    fal, rows = FalClient(), []

    def one(p: dict) -> dict:
        shot = p["shot"]
        sid = shot["shot_id"]
        payload = {"image_url": fal.upload_file(p["keyframe"]), "audio_url": fal.upload_file(p["audio"]), **m.get("payload", {})}
        if model != "minimax-h3-max":
            payload["prompt"] = (f"{shot.get('motion', '')} The person speaks the line naturally with the right emotion; "
                                 "the mouth moves with the words. Natural blinking. He never looks into the camera.").strip()
            # never name subtitles/captions here: on 2026-10-17 "no subtitles" made Kling Avatar burn some in (T.3-08)
        out = media_root() / "productions" / prod.key / "clips" / p["part"] / sid / f"{stamp}-lipsync-{model}"
        out.mkdir(parents=True, exist_ok=True)
        result = fal.run(m["model_id"], payload, timeout=1800)  # Kling Avatar can sit in fal's queue for many minutes
        dest = download((result.get("video") or {}).get("url"), out / f"{sid.lower().replace('.', '-')}.mp4")
        seconds = _seconds(dest)
        cost = round(seconds * m["price_usd"], 3)
        write_json(out / "manifest.json", {
            "kind": "clip", "target": sid, "model_id": m["model_id"], "lipsync": True,
            "prompt": "lip-sync: " + " / ".join(f"{ln.speaker}: {ln.text}" for ln, _ in p["lines"]) + f" — {payload.get('prompt', '')}",
            "keyframe": str(p["keyframe"]), "audio": [str(f) for _, f in p["lines"]],
            "items": [{"files": [dest.name], "request_ids": [result.get("_request_id")], "cost_usd_estimate": cost}]})
        costs.record({"production": prod.key, "provider": "fal", "kind": "lipsync", "target": sid, "model_id": m["model_id"],
                      "units": round(seconds, 2), "unit": "second", "cost_usd": cost,
                      "request_ids": [result.get("_request_id")], "out_dir": str(out)})
        print(f"  ✓ {sid:8} {seconds:4.1f}s ${cost:.2f}  {dest}", flush=True)
        if p["seconds"] > float(shot.get("duration_s") or 5) + 0.05:
            print(f"    ! the lines last {p['seconds']:.1f}s, longer than the shot ({shot.get('duration_s')}s) — lengthen the shot "
                  "in the shot list so the cut does not clip them", flush=True)
        return {"shot": sid, "seconds": seconds, "cost": cost, "out": dest, "speakers": p["speakers"]}

    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=4) as pool:  # fal queues the jobs; one at a time took ~7 min each
        for future in cf.as_completed([pool.submit(one, p) for p in plan]):
            try:
                rows.append(future.result())
            except Exception as err:  # noqa: BLE001 — one failed shot must not lose the others (they are paid)
                print(f"  ✗ {str(err)[:300]}", flush=True)
    return rows


def narration_take(prod: Production, beat: str) -> Path | None:
    """The narrator's take for a beat in the production's narration script: approved, else the newest."""
    vo_root = media_root() / "productions" / prod.key / "audio" / "vo" / beat
    script = prod.config.get("narration", {}).get("script")
    if not script or beat not in set(_narrated_beats(prod)) or not vo_root.exists():
        return None
    takes = []
    for m in sorted(vo_root.glob("*/manifest.json")):
        if f"({script})" in load_json(m).get("target", ""):
            approved = m.parent / "approved.json"
            f = m.parent / (load_json(approved)["file"] if approved.exists() else load_json(m)["items"][0]["files"][0])
            if f.is_file():
                takes.append((approved.exists(), m.parent.name, f))
    return max(takes)[2] if takes else None


def voice_reel(prod: Production) -> Path:
    """The whole episode's voices in story order — each beat's narration (approved, else newest) then its dialogue
    lines — with a cue sheet, for listening through the performances in one go."""
    narrated = set(_narrated_beats(prod))
    pieces, cues, clock = [], [], 0.0
    for path in prod.shot_list_paths():
        for b in load_json(path)["beats"]:
            beat = b["beat"]
            if beat in narrated:
                f = narration_take(prod, beat)
                if f:
                    pieces.append(f)
                    cues.append(f"{clock:7.1f}s  {beat:5} VO   {narration(prod, beat)[0][:70]}")
                    clock += _seconds(f) + 0.8
            for ln in lines(prod, beat):
                f = best_take(prod, beat, ln)
                if f:
                    pieces.append(f)
                    cues.append(f"{clock:7.1f}s  {beat:5} L{ln.n} {ln.speaker:10} [{ln.perf.get('intensity')}/10 {ln.perf.get('volume')}] {ln.text[:60]}")
                    clock += _seconds(f) + 0.8
    if not pieces:
        raise KeyError("No takes yet")
    out = media_root() / "productions" / prod.key / "audio" / "reel" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    listing = out / "list.txt"
    padded = []
    for i, f in enumerate(pieces):
        p = out / f"p{i:03d}.wav"
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(f), "-af", "aresample=48000,apad=pad_dur=0.8", "-ac", "1",
                        "-c:a", "pcm_s16le", str(p)], check=True, stdin=subprocess.DEVNULL)
        padded.append(p)
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in padded), encoding="utf-8")
    final = out / "episode_voices.wav"
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(final)],
                   check=True, stdin=subprocess.DEVNULL)
    for p in padded:
        p.unlink(missing_ok=True)
    listing.unlink(missing_ok=True)
    (out / "cues.txt").write_text("\n".join(cues) + "\n", encoding="utf-8")
    write_json(out / "manifest.json", {"kind": "dialogue", "target": "Episode 1 — all voices in story order (reel)",
                                       "model_id": "ffmpeg (local)", "prompt": "\n".join(cues)})
    return final


def recover_lipsync(prod: Production, shot_id: str, request_id: str, model: str = "kling-avatar-v2-pro") -> Path:
    """Fetch a lip-sync that fal finished after the engine stopped waiting (it is paid for) and file it like a normal run."""
    from .providers.fal import FalClient, download
    m = costs.model(LIPSYNC[model])
    fal = FalClient()
    app = "/".join(m["model_id"].split("/")[:2])
    status = fal._request("GET", f"{fal.base}/{app}/requests/{request_id}/status")
    if status.get("status") != "COMPLETED":
        raise RuntimeError(f"request {request_id} is {status.get('status')}")
    result = fal._request("GET", f"{fal.base}/{app}/requests/{request_id}")
    sl, _, _ = prod.find_shot(shot_id)
    out = media_root() / "productions" / prod.key / "clips" / sl["part"] / shot_id / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-lipsync-{model}"
    out.mkdir(parents=True, exist_ok=True)
    dest = download((result.get("video") or {}).get("url"), out / f"{shot_id.lower().replace('.', '-')}.mp4")
    seconds = _seconds(dest)
    cost = round(seconds * m["price_usd"], 3)
    write_json(out / "manifest.json", {"kind": "clip", "target": shot_id, "model_id": m["model_id"], "lipsync": True,
                                       "prompt": f"lip-sync (recovered fal request {request_id})",
                                       "items": [{"files": [dest.name], "request_ids": [request_id], "cost_usd_estimate": cost}]})
    costs.record({"production": prod.key, "provider": "fal", "kind": "lipsync", "target": shot_id, "model_id": m["model_id"],
                  "units": round(seconds, 2), "unit": "second", "cost_usd": cost, "request_ids": [request_id], "out_dir": str(out)})
    return dest


def crop_subtitles(prod: Production, shot_id: str, keep: float = 0.76) -> Path:
    """Kling Avatar sometimes burns fake subtitle text into the bottom of a clip (mostly in dark scenes; asking it not
    to made it worse). Free fix: keep the top `keep` of the frame (centred left-right, same 16:9 shape), scale it back to
    full size and file it as a new clip batch, then mark the source clip rejected so the cut uses the clean one."""
    from .animatic import best_clip
    if not 0.6 <= keep < 1:
        raise ValueError("keep must be between 0.6 and 1 (the share of the frame height to keep)")
    sl, _, _ = prod.find_shot(shot_id)
    src, _ = best_clip(prod, sl["part"], shot_id)
    if not src or "lipsync" not in src.parent.name:
        raise KeyError(f"{shot_id} has no lip-sync clip")
    if src.parent.name.endswith("-cropped"):
        raise KeyError(f"{shot_id}'s clip is already cropped ({src.parent.name})")
    out = src.parent.parent / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{src.parent.name.split('-', 2)[2]}-cropped"
    out.mkdir(parents=True, exist_ok=True)
    dest = out / src.name
    vf = (f"crop=trunc(iw*{keep}/2)*2:trunc(ih*{keep}/2)*2:(iw-iw*{keep})/2:0,"
          "scale=1920:1080:flags=lanczos,setsar=1")
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(src), "-vf", vf, "-c:v", "libx264", "-crf", "16",
                    "-preset", "slow", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.0", "-c:a", "copy", str(dest)],
                   check=True, stdin=subprocess.DEVNULL)
    manifest = load_json(src.parent / "manifest.json") if (src.parent / "manifest.json").exists() else {}
    write_json(out / "manifest.json", {**manifest, "kind": "clip", "target": shot_id, "lipsync": True,
                                       "cropped_from": str(src), "crop_keep": keep,
                                       "prompt": f"cropped (top {keep:.0%} kept, fake subtitles removed) — " + manifest.get("prompt", ""),
                                       "items": [{"files": [dest.name], "cost_usd_estimate": 0}]})
    marks = src.parent / "rejected.json"
    files = set(load_json(marks).get("files", [])) if marks.exists() else set()
    write_json(marks, {"files": sorted(files | {src.name})})
    return dest


def talking_reel(prod: Production, part: str) -> Path:
    """The lip-synced talking shots of one part in story order, with their own sound — a quick way to judge the acting
    on picture before the rest of the scene exists."""
    from .animatic import best_clip
    clips = []
    for sl, b, shot in prod.all_shots(part):
        if shot.get("lip_sync") == "required":
            clip, _ = best_clip(prod, sl["part"], shot["shot_id"])
            if clip and any(k in clip.parent.name for k in ("lipsync", "avatar")):
                clips.append((b["beat"], shot["shot_id"], clip))
    if not clips:
        raise KeyError(f"No lip-synced clips in {part} yet")
    out = media_root() / "productions" / prod.key / "cut" / f"talking_{part}" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    args, chains = [_ffmpeg(), "-y", "-loglevel", "error"], []
    for i, (_, _, clip) in enumerate(clips):
        args += ["-i", str(clip)]
        chains.append(f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,"
                      f"fps=24,format=yuv420p[v{i}];[{i}:a]aresample=48000,aformat=channel_layouts=mono[a{i}]")
    graph = ";".join(chains) + ";" + "".join(f"[v{i}][a{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=1[v][a]"
    final = out / f"talking_{part}.mp4"
    subprocess.run(args + ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
                           "-preset", "medium", "-c:a", "aac", "-b:a", "192k", str(final)], check=True, stdin=subprocess.DEVNULL)
    write_json(out / "manifest.json", {"kind": "cut", "target": f"talking shots · {part}", "model_id": "ffmpeg (local)",
                                       "prompt": " · ".join(f"{b} {s}" for b, s, _ in clips)})
    return final


def placed_lines(prod: Production, beat: str, shot_starts: dict[str, float]) -> list[tuple["Line", Path, float]]:
    """(line, take, start second) for every line of a beat in a cut whose shots start at shot_starts: the first line of
    a shot starts after the lead-in breath, the next ones follow it (the same timing lip-sync used)."""
    placed, cursor = [], {}
    for ln in lines(prod, beat):
        f = best_take(prod, beat, ln)
        if not f or ln.shot_id not in shot_starts:
            continue
        start = cursor.get(ln.shot_id, shot_starts[ln.shot_id] + LEAD_IN)
        placed.append((ln, f, start))
        cursor[ln.shot_id] = start + _seconds(f) + 0.35
    return placed


def dialogue_track(prod: Production, beat: str, shot_starts: dict[str, float]) -> list[tuple[Path, float]]:
    """(take, start second) for every line of a beat in a cut (see placed_lines)."""
    return [(f, start) for _, f, start in placed_lines(prod, beat, shot_starts)]


def subtitle_events(placed: list[tuple["Line", Path, float]], english: dict[str, list]) -> list[tuple[float, float, str]]:
    """English subtitle events (start, end, text) for placed lines. english: shot id -> the shot's "dialogue_en", one
    entry per line of the shot in order; an entry that is a list is shown part by part, timed by length."""
    events, seen = [], {}
    for ln, f, start in placed:
        k = seen.get(ln.shot_id, 0)
        seen[ln.shot_id] = k + 1
        entries = english.get(ln.shot_id) or []
        if k >= len(entries) or not entries[k]:
            continue
        parts = entries[k] if isinstance(entries[k], list) else [entries[k]]
        length = _seconds(f)
        total = sum(len(p) for p in parts)
        t = start
        for p in parts:
            share = length * len(p) / total
            events.append((t, t + share, p))
            t += share
    events.sort()
    out = []
    for i, (s, e, text) in enumerate(events):  # hold each a little longer (at least 1.4 s) without touching the next
        nxt = events[i + 1][0] - 0.08 if i + 1 < len(events) else e + 10
        out.append((max(0.0, s - 0.08), min(max(e + 0.35, s + 1.4), nxt), text))
    return out
