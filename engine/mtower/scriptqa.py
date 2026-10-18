"""Script QA: an Azure reviewer checks a screenplay, beat by beat and line by line, before anything is recorded or shot.

The board (engine_config 'script_review', gpt-5.6-sol, high reasoning) reads each beat with its scene, the cast's
personas, the neighbouring beats and the series rules, and scores every dialogue line on:
  - dialect      — everyday Egyptian street Arabic of 1973 (Cairo / rural Delta / Suez as the character), no MSA leakage
  - military     — how a 1973 Egyptian army unit really talks (ranks, «يا فندم», orders, kit names, sergeant to private)
  - intensity    — volume, pace and feeling fit the situation (a whisper in the ranks, a shout over rotors)
  - character    — the line sounds like this person (age, home, rank, persona) and nobody else
  - drama        — subtext, conflict, humour, a turn; no exposition dumps, no clichés, no speeches
  - diacritics   — full, correct vowel marks for TTS in Egyptian pronunciation (numbers stay undiacritized)
  - lipsync      — short enough for one close shot (about 14 words, ~5 s)
It also checks the beat as a scene (arc, missed opportunities), history (real people only around documented actions,
facts unchanged) and the series rules (no Quran). Every line gets a suggested performance (intensity 1-10, volume,
pace, emotion, delivery) for the shot list, and a rewrite when it falls below the gate.

Verdicts are saved under 01_development/screenplay/qa/<file stem>/<beat>.json with the hash of the beat's text, so a
re-run only reviews beats that changed (or --force). A Markdown report sits next to them. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import costs
from .production import BEAT_HEADING, Production, parse_screenplay
from .settings import write_json

GATE = 8
VOLUMES = ["whisper", "low", "normal", "raised", "shout"]
PACES = ["slow", "measured", "normal", "quick", "rushed"]
AXES = ["dialect", "military", "intensity", "character", "drama", "diacritics", "lipsync"]

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["beat_score", "verdict", "summary", "scene_issues", "history_issues", "rule_issues", "lines"],
    "properties": {
        "beat_score": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "summary": {"type": "string"},
        "scene_issues": {"type": "array", "items": {"type": "string"}},
        "history_issues": {"type": "array", "items": {"type": "string"}},
        "rule_issues": {"type": "array", "items": {"type": "string"}},
        "lines": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["n", "speaker", "score", "scores", "issues", "rewrite", "performance"],
            "properties": {
                "n": {"type": "integer"},
                "speaker": {"type": "string"},
                "score": {"type": "integer"},
                "scores": {"type": "object", "additionalProperties": False, "required": AXES,
                           "properties": {a: {"type": "integer"} for a in AXES}},
                "issues": {"type": "array", "items": {"type": "string"}},
                "rewrite": {"type": "string"},
                "performance": {"type": "object", "additionalProperties": False,
                                "required": ["intensity", "volume", "pace", "emotion", "delivery"],
                                "properties": {"intensity": {"type": "integer"},
                                               "volume": {"type": "string", "enum": VOLUMES},
                                               "pace": {"type": "string", "enum": PACES},
                                               "emotion": {"type": "string"},
                                               "delivery": {"type": "string"}}}}}}}}

SYSTEM = f"""You are the script board of an Egyptian TV drama studio: a veteran Egyptian screenwriter and dialogue
editor, a retired Egyptian army officer who served in 1973 (Sa'iqa / commando units), and a voice director. You review
one beat (scene) of a screenplay for a drama series about Egyptian Sa'iqa commandos in October 1973 — a real
operation (the Romani ambush) with composite (fictional) soldiers and families around the real commander.

The series is DRAMA-FIRST: it must play like a real Egyptian TV drama with actors, not a documentary. People talk,
argue, joke, fear, give orders and react on camera. The narrator (old Hamdi Shalabi, remembering) gets at most one or
two short lines per beat, only for time, place and documented context no character could naturally say (unit
numbers, dates, what the mission was); the screenplay writes his VO in formal Arabic as the factual reference (it is
recorded from a separate Egyptian-Arabic narration file), so do not score the VO's diacritics or dialect.

Score every dialogue line 0-10 on each axis, strictly (8 = broadcast quality; 10 = a line a top Egyptian writer would
be proud of):
- dialect: everyday Egyptian street Arabic as really spoken in 1973 by THIS person (Cairene, rural Menoufia / Delta,
  Suezi; a child; a general). No Modern Standard Arabic words or grammar leaking in (only the radio announcer and
  narrator use MSA). No Levantine/Gulf words, no modern slang that did not exist in 1973, no stiff "translated" phrasing.
  Word choice, word order and rhythm must be what an Egyptian would actually say in that moment.
- military: how a 1973 Egyptian army unit really talks — «يا فندم», «تمام يا فندم», «أوامرك», «حاضر», «عُلِم»,
  orders as short imperatives, ranks addressed correctly (a private never calls a captain by name; a sergeant calls
  a private by name or «يا ابني» / «يا عسكري»), correct kit names («خزنة», «آر بي جي», «مالوتكا», «لغم», «جهاز»,
  «سماعة»), unit words («سرية», «فصيلة», «جماعة», «كتيبة»). Score 10 when the line has no military content and
  nothing military is missing.
- intensity: the line, its parenthetical and the performance fit the situation exactly — stakes, volume (you cannot
  whisper over rotors; a man in ranks on parade whispers), pace, and what the character feels underneath.
  Intensity scale (stakes inside the character, not loudness): 1-2 at ease; 3-4 everyday; 5-6 something real at
  stake; 7-8 urgent pressure; 9-10 life or death. Film acting, never theatrical. The episode has one single 10.
- character: sounds like this person (age, home, rank, persona below) and could not be swapped with another speaker.
- drama: does real dramatic work — subtext over statement, conflict or warmth, humour where people would joke,
  a turn; no exposition dumped for the audience, no clichés, no speeches, no slogans. Facts the narrator used to carry
  should come out naturally, as people would really say them.
- diacritics: the voice model gets the bare letters plus the shadda (vowel marks are stripped before recording,
  because they push the voices toward formal Arabic). So the SPELLING must lead an Egyptian voice to the right
  pronunciation («مِشْ», «دِلْوَقْتِي», «عَشَانْ», «اللِّي», «مَافِيشْ»), and the vowel marks must be correct for the
  human reader. House style (do not penalize): a sukun on word endings including a final «ةْ», and «الْ» written for
  the Egyptian «il-». Number words («تلات», «أربعة», «مية واتنين وعشرين») and «صاعقة» are deliberately left without
  marks — never penalize that. «مَيَّة» (water) keeps its marks. Flag any word that becomes ambiguous once the marks
  are gone (the voice once read the name «عَلِي» as the preposition «على», and «أَرَجَّعْ» "take back" as «أرجع»
  "go back"): rewrite so the bare letters can only be read one way (e.g. «عَلِي ابْنِي»).
- lipsync: one close shot per line — at most about 14 words / 5 seconds; two short sentences at most. Lines marked
  V.O. (a letter read in voice-over, a radio) are not lip-synced: score lipsync 10 for them, but they should still
  stay under about 25 seconds and build to one clear release.
"score" is the line's overall score: never higher than its lowest axis + 2, and below {GATE} whenever any axis is
below {GATE - 2}.

For EVERY line, give "performance": intensity (1-10), volume ({' | '.join(VOLUMES)}), pace ({' | '.join(PACES)}),
emotion (a short phrase), delivery (one or two sentences for the voice actor: what the character is doing, to whom,
and why). Give it even when the line is fine — it goes into the shot list.

If a line scores below {GATE}, "rewrite" is the improved line: complete, in the same speaker's Egyptian Arabic, FULLY
diacritized by the rules above, keeping the same story facts and the same dramatic job (do not add plot). Otherwise
"rewrite" is "". Do not rewrite letters being read aloud into something a 20-year-old village soldier would not
write. Keep a line that is already good — do not rewrite for taste.

"issues" (per line) and the beat-level lists are short, concrete and in English, quoting the Arabic words at fault.
scene_issues: the beat as a scene — does it have a shape and a turn, is the intensity curve right, is a reaction or
moment missing, is anything confusing for a viewer, is a line redundant. history_issues: real people (Captain Hamdi
Shalabi, the Commander of Sa'iqa Forces, the squadron leader) may only speak around their documented actions and must
be marked (dramatized); no invented private life for them; facts (numbers, places, times, weapons) must not change;
the families never know more than a real family would have known that day. rule_issues: the series rules — NO QURAN
anywhere (no verse, no recitation; everyday «إن شاء الله» / «الحمد لله» / «والله» are fine), restrained violence.

"beat_score" is the beat as a whole (0-10); "verdict" is "pass" only when beat_score >= {GATE} and every line
score >= {GATE}. Lines marked "close to the source's words" reconstruct what the historical source reports was said:
keep their wording and judge only whether it is natural spoken Egyptian (do not rewrite them for style). Lines are
numbered as given; return them in the same order with the same numbers."""


def beat_sections(path: Path) -> dict[str, str]:
    """The raw Markdown of each beat (from its '### Beat' heading to the next beat or section heading)."""
    out: dict[str, list[str]] = {}
    current = None
    for line in path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n"):
        m = BEAT_HEADING.match(line)
        if m:
            current = m.group(1)
            out[current] = [line]
            continue
        if line.startswith("## ") or line.startswith("# "):
            current = None
        if current:
            out[current].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def cast_brief(prod: Production, speakers: set[str]) -> str:
    ids = {k: v for k, v in prod.config.get("speakers", {}).items() if not k.startswith("_")}
    cast = prod.config.get("voice_cast", {})
    rows = []
    for s in sorted(speakers):
        cid = ids.get(s, s)
        entry = cast.get(cid) or {}
        name = (prod.casting.get("cast", {}).get(cid) or {}).get("character") or entry.get("name") or s
        persona = entry.get("persona") or "(no persona yet — judge from the screenplay)"
        rows.append(f"- {s} ({cid}, {name}): {persona}")
    return "\n".join(rows)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def qa_dir(prod: Production, path: Path) -> Path:
    return prod.root / "01_development" / "screenplay" / "qa" / path.stem


def plan(prod: Production, path: Path, beats: list[str] | None = None, force: bool = False) -> list[dict]:
    sections = beat_sections(path)
    parsed = parse_screenplay(path)
    order = list(sections)
    items = []
    for i, beat in enumerate(order):
        if beats and beat not in beats:
            continue
        lines = parsed[beat].dialogue if beat in parsed else []
        if not lines:
            continue
        digest = _digest(sections[beat])
        out = qa_dir(prod, path) / f"{beat}.json"
        if out.exists() and not force:
            try:
                if json.loads(out.read_text(encoding="utf-8")).get("hash") == digest:
                    continue
            except ValueError:
                pass
        neighbours = []
        for j in (i - 1, i + 1):
            if 0 <= j < len(order):
                b = parsed.get(order[j])
                neighbours.append(f"{'BEFORE' if j < i else 'AFTER'}: Beat {order[j]} — {b.title if b else ''}")
        items.append({"beat": beat, "text": sections[beat], "lines": lines, "hash": digest, "out": out,
                      "neighbours": neighbours})
    return items


def _user_text(prod: Production, path: Path, item: dict) -> str:
    numbered = "\n".join(f"{n}. {ln.speaker}{' ' + ln.note if ln.note else ''}: {ln.text}"
                         for n, ln in enumerate(item["lines"], 1))
    return (f"SCREENPLAY FILE: {path.name}\n{chr(10).join(item['neighbours'])}\n\n"
            f"CAST (speakers in this beat):\n{cast_brief(prod, {ln.speaker for ln in item['lines']})}\n\n"
            f"THE BEAT AS WRITTEN:\n{item['text']}\n\n"
            f"DIALOGUE LINES TO SCORE (numbered in order; the parenthetical note is the writer's performance hint):\n"
            f"{numbered}")


def review(client, m: dict, prod: Production, path: Path, item: dict) -> dict:
    body = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _user_text(prod, path, item)}],
            "max_completion_tokens": m.get("max_completion_tokens", 24000),
            "reasoning_effort": m.get("reasoning_effort", "high"),
            "response_format": {"type": "json_schema", "json_schema": {"name": "script_verdict", "strict": True, "schema": SCHEMA}}}
    url = f"{client.endpoint}/openai/deployments/{m['model_id']}/chat/completions?api-version={client.api_version}"
    started = time.time()
    for attempt in range(2):
        try:
            data = client._post(url, json.dumps(body).encode("utf-8"), "application/json")
            break
        except Exception as err:  # noqa: BLE001
            if attempt or "network error" not in str(err):
                raise
            time.sleep(10)
    verdict = json.loads(data["choices"][0]["message"]["content"])
    usage = data.get("usage") or {}
    p = m["pricing_per_m_tokens"]
    cost = round((usage.get("prompt_tokens", 0) * p["input_per_m"] + usage.get("completion_tokens", 0) * p["output_per_m"])
                 / 1_000_000, 5)
    lines = verdict["lines"]
    if len(lines) != len(item["lines"]):
        raise ValueError(f"reviewer returned {len(lines)} lines for {len(item['lines'])}")
    worst = min((ln["score"] for ln in lines), default=10)
    verdict["verdict"] = "pass" if verdict["beat_score"] >= GATE and worst >= GATE else "fail"
    for n, (ln, src) in enumerate(zip(lines, item["lines"]), 1):
        ln["text"] = src.text
        ln["n"] = n
    return {**verdict, "beat": item["beat"], "file": path.name, "hash": item["hash"], "model": m["model_id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seconds": round(time.time() - started, 1),
            "usage": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens")}, "cost_usd": cost}


def estimates(items: list[dict]) -> list[costs.Estimate]:
    return [costs.estimate("script_review", len(items))] if items else []


def run(prod: Production, path: Path, items: list[dict], confirm_cost: float | None, workers: int = 4) -> list[dict]:
    from .providers.azure import AzureClient, AzureError

    costs.authorize(estimates(items), confirm_cost)
    m = costs.model("script_review")
    client = AzureClient()
    client.token()

    def one(item: dict) -> dict | None:
        for attempt in range(2):
            try:
                result = review(client, m, prod, path, item)
                write_json(item["out"], result)
                return result
            except (AzureError, KeyError, ValueError) as err:
                if attempt:
                    print(f"  ! {item['beat']}: {str(err)[:200]}", flush=True)
        return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = [r for r in pool.map(one, items) if r]
    spent = round(sum(r["cost_usd"] for r in results), 4)
    if results:
        costs.record({"production": prod.key, "provider": "azure", "kind": "script_review",
                      "target": f"{path.stem}: {len(results)} beat(s)", "model_id": m["model_id"],
                      "units": len(results), "unit": "beat", "cost_usd": spent})
    print(f"Reviewed {len(results)} of {len(items)} beat(s) · actual cost ${spent:.3f}")
    return results


def _beat_key(beat: str) -> tuple:
    return tuple(int(x) if x.isdigit() else -1 for x in re.split(r"[.]", beat))


def saved(prod: Production, path: Path) -> list[dict]:
    d = qa_dir(prod, path)
    current = beat_sections(path)
    out = []
    for f in sorted(d.glob("*.json"), key=lambda f: _beat_key(f.stem)):
        v = json.loads(f.read_text(encoding="utf-8"))
        if v.get("beat") in current:
            v["stale"] = v.get("hash") != _digest(current[v["beat"]])
            out.append(v)
    return out


def summary_lines(verdicts: list[dict], verbose: bool = True) -> list[str]:
    rows = []
    for v in verdicts:
        worst = min((ln["score"] for ln in v["lines"]), default=10)
        mark = "✓" if v["verdict"] == "pass" else "✗"
        stale = " (text changed since review)" if v.get("stale") else ""
        rows.append(f"{mark} Beat {v['beat']:5} beat {v['beat_score']}/10 · lowest line {worst}/10 · "
                    f"{len(v['lines'])} lines{stale}")
        if not verbose:
            continue
        for issue in v["scene_issues"] + v["history_issues"] + v["rule_issues"]:
            rows.append(f"    scene: {issue}")
        for ln in v["lines"]:
            if ln["score"] >= GATE:
                continue
            low = ", ".join(f"{a} {ln['scores'][a]}" for a in AXES if ln["scores"][a] < GATE)
            rows.append(f"    {ln['n']:2}. {ln['speaker']} {ln['score']}/10 ({low}): {ln['text']}")
            for issue in ln["issues"]:
                rows.append(f"        - {issue}")
            if ln["rewrite"]:
                rows.append(f"        → {ln['rewrite']}")
    return rows


def write_report(prod: Production, path: Path) -> Path:
    verdicts = saved(prod, path)
    passed = sum(v["verdict"] == "pass" and not v.get("stale") for v in verdicts)
    md = [f"# Script QA — {path.name}", "",
          f"Gate: every line and the beat ≥ {GATE}/10. **{passed} of {len(verdicts)} beat(s) pass.** "
          f"Reviewer: {verdicts[0]['model'] if verdicts else '-'}.", "",
          "| Beat | Verdict | Beat score | Lowest line | Lines |", "|---|---|---|---|---|"]
    for v in verdicts:
        worst = min((ln["score"] for ln in v["lines"]), default=10)
        md.append(f"| {v['beat']} | {v['verdict']}{' (stale)' if v.get('stale') else ''} | {v['beat_score']} | {worst} | "
                  f"{len(v['lines'])} |")
    md += ["", "## Details", ""]
    for v in verdicts:
        md += [f"### Beat {v['beat']} — {v['verdict']} ({v['beat_score']}/10)", "", v["summary"], ""]
        for issue in v["scene_issues"] + v["history_issues"] + v["rule_issues"]:
            md.append(f"- {issue}")
        md += ["", "| # | Speaker | Score | Performance | Line | Issues / rewrite |", "|---|---|---|---|---|---|"]
        for ln in v["lines"]:
            p = ln["performance"]
            fix = "; ".join(ln["issues"]) + (f" → {ln['rewrite']}" if ln["rewrite"] else "")
            md.append(f"| {ln['n']} | {ln['speaker']} | {ln['score']} | {p['intensity']} · {p['volume']} · {p['pace']} — "
                      f"{p['emotion']} | {ln['text']} | {fix.replace('|', '/')} |")
        md.append("")
    out = qa_dir(prod, path).parent / f"{path.stem}.qa.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md), encoding="utf-8")
    return out
