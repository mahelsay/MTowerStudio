"""Batch Image QA over approved MTower keyframes — compares three judgments per frame:

  1. the human approval (approved.json, the gallery sign-off)
  2. MTower's own QA engine verdict (<frame>.qa.json, if present)
  3. the studio Image QA agent (this fleet), given the same kind of references
     (casting portraits of the shot's characters + real prop photos)

Spend discipline: prints an estimate and refuses to run unless --confirm-cost >= the estimate.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from . import grounding
from .agents.image_qa import ImageQAAgent
from .contract import Shot

EST_PER_REVIEW_USD = 0.09  # MTower measured $0.05-0.085 per sol review with references; $0.10 ceiling
MAX_REFS = 5


def _media_root() -> Path:
    env = os.getenv("MTOWER_MEDIA_ROOT")
    return Path(env) if env else grounding.MTOWER_REPO / "media"


def _keyframes_dir(production: str, episode: str) -> Path:
    return _media_root() / "productions" / production / episode / "keyframes"


def approved_frames(production: str, episode: str) -> list[dict]:
    """Every approved frame: {shot_id, part, image, approved_at, folder}."""
    out = []
    for ap in sorted(_keyframes_dir(production, episode).rglob("approved.json")):
        try:
            data = json.loads(ap.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        img = ap.parent / data.get("file", "")
        if not img.exists():
            continue
        out.append({
            "shot_id": ap.parent.parent.name,
            "part": ap.parent.parent.parent.name,
            "image": str(img),
            "approved_at": data.get("approved_at", ""),
            "folder": str(ap.parent),
        })
    return out


def sample(frames: list[dict], n: int) -> list[dict]:
    """Round-robin across parts so a small sample still covers the whole episode."""
    by_part: dict[str, list[dict]] = {}
    for f in frames:
        by_part.setdefault(f["part"], []).append(f)
    picked: list[dict] = []
    while len(picked) < n and any(by_part.values()):
        for part in sorted(by_part):
            if by_part[part] and len(picked) < n:
                picked.append(by_part[part].pop(0))
    return picked


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def references_for(production: str, episode: str, design: dict) -> list[tuple[str, str]]:
    repo = grounding.MTOWER_REPO
    casting = _load_json(repo / "productions" / production / episode / "02_preproduction" / "casting.json").get("cast", {})
    actors = {a["id"]: a for a in _load_json(repo / "studio" / "library" / "actors" / "actors.json").get("actors", [])}
    refs: list[tuple[str, str]] = []
    face_visible = design.get("face_pass", True) is not False
    for cid in design.get("character_ids", []) if face_visible else []:
        aid = casting.get(cid, {}).get("actor")
        media = ((actors.get(aid) or {}).get("anchor") or {}).get("media_path")
        if media and (_media_root() / media).exists():
            role = casting.get(cid, {}).get("character", "")
            refs.append((f"casting portrait of {cid} {role} (actor {aid})", str(_media_root() / media)))
    props_root = _media_root() / "library" / "props"
    for asset in design.get("assets") or []:
        m = re.search(r"PRP-\d{4}", str(asset))
        if not m:
            continue
        for folder in props_root.glob(f"{m.group(0)}_*"):
            for p in sorted((folder / "references").glob("*"))[:2]:
                if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                    refs.append((f"real reference photo of prop {m.group(0)}", str(p)))
    insignia = repo / "studio" / "library" / "wardrobe" / "insignia"
    seen: set[str] = set()
    for cid in design.get("character_ids", []):
        name = casting.get(cid, {}).get("rank_reference")
        if name and name not in seen and (insignia / name).exists():
            seen.add(name)
            refs.append((f"official drawing of the shoulder-strap rank insignia {cid} "
                         f"{casting[cid].get('character', '')} must wear (judge the count and shape of the devices; "
                         f"on film it is small gold metal on a khaki strap, so fine detail may be soft)",
                         str(insignia / name)))
    return refs[:MAX_REFS]


def production_rules(production: str, episode: str) -> str:
    qa = _load_json(grounding.MTOWER_REPO / "productions" / production / episode / "02_preproduction"
                    / "production_config.json").get("qa", {})
    if not qa:
        return ""
    return f"PRODUCTION: {qa.get('story', '')}\nPRODUCTION RULES:\n" + "\n".join(f"- {r}" for r in qa.get("rules", []))


def mtower_verdict(frame: dict) -> dict:
    img = Path(frame["image"])
    qa = img.with_name(img.stem + ".qa.json")
    d = _load_json(qa)
    if not d:
        return {}
    return {"score": d.get("score"), "verdict": d.get("verdict"), "summary": d.get("summary", ""),
            "reviewed_at": d.get("reviewed_at", "")}


def design_text(production: str, episode: str, design: dict) -> str:
    repo = grounding.MTOWER_REPO
    casting = _load_json(repo / "productions" / production / episode / "02_preproduction" / "casting.json").get("cast", {})
    locations = {l["id"]: l for l in _load_json(repo / "studio" / "library" / "locations" / "locations.json")
                 .get("locations", [])}
    lines = [
        f"Shot {design.get('shot_id')} — beat {design.get('beat')} '{design.get('beat_title', '')}'.",
        f"Shot size {design.get('size') or design.get('shot_size')}, lens {design.get('lens')}, "
        f"camera move {design.get('move') or design.get('camera_move') or 'static'}.",
        f"What the frame shows: {design.get('prompt', '')}",
        f"What happens next in the clip (context only): {design.get('motion') or design.get('motion_prompt') or ''}",
    ]
    if design.get("face"):
        lines.append(f"Face direction: {design['face']}")
    if design.get("face_pass") is False:
        lines.append("By design the lead's face is NOT visible (seen from behind, in shadow or in profile darkness).")
    for cid in design.get("character_ids", []):
        c = casting.get(cid, {})
        extra = "; ".join(x for x in (c.get("character_additions"), c.get("face_additions")) if x)
        lines.append(f"Character {cid} {c.get('character', '')} (wardrobe {c.get('wardrobe', '?')})"
                     + (f": {extra}" if extra else ""))
    if design.get("extras"):
        lines.append(f"Extras (count matters): {design['extras']}")
    if design.get("assets"):
        lines.append(f"Assets: {design['assets']}")
    loc = locations.get(design.get("location") or "", {})
    if loc:
        lines.append(f"Location {loc['id']} {loc.get('name', '')}: {loc.get('prompt', '')}")
        for rule in loc.get("qa_rules") or []:
            lines.append(f"Location rule: {rule}")
    if design.get("look"):
        lines.append(f"Look keys: {design['look']}")
    if design.get("wear"):
        lines.append(f"Wear state: {design['wear']}")
    if design.get("notes"):
        lines.append(f"Director's design notes: {design['notes']}")
    return "\n".join(lines)


def run(production: str, episode: str, frames: list[dict], *, verbose: bool = True) -> list[dict]:
    agent = ImageQAAgent()
    rules = production_rules(production, episode)
    results = []
    for n, f in enumerate(frames, 1):
        design = grounding.find_shot(production, episode, f["shot_id"]) or {}
        shot = Shot(shot_id=f["shot_id"], production=production, episode=episode, beat_ref=str(design.get("beat", "")))
        shot.intent.subject = design.get("prompt", "")
        shot.intent.action = design.get("motion", "")
        refs = references_for(production, episode, design)
        if verbose:
            print(f"[{n}/{len(frames)}] {f['shot_id']} — {len(refs)} reference image(s) …", flush=True)
        try:
            qa = agent.review(shot, f["image"], references=refs, design=design_text(production, episode, design),
                              rules=rules)
        except Exception as e:  # noqa: BLE001 — record and continue the batch
            qa = {"error": str(e)}
        results.append({
            **f,
            "design_prompt": design.get("prompt", ""),
            "references": [label for label, _ in refs],
            "human": "approved",
            "mtower": mtower_verdict(f),
            "studio": qa,
        })
        if verbose and "error" not in qa:
            print(f"      studio: {qa.get('verdict')} {qa.get('score')}  ·  mtower: "
                  f"{results[-1]['mtower'].get('verdict', '—')} {results[-1]['mtower'].get('score', '')}  ·  "
                  f"${qa.get('_cost_usd', 0):.3f}", flush=True)
    return results


def write_report(results: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    jpath = out_dir / f"batch_qa_{stamp}.json"
    jpath.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    ok = [r for r in results if "error" not in r["studio"]]
    total = sum(r["studio"].get("_cost_usd", 0) for r in ok)
    agree = sum(1 for r in ok if r["mtower"] and r["mtower"].get("verdict") == r["studio"].get("verdict"))
    with_mt = sum(1 for r in ok if r["mtower"])
    lines = [
        f"# Batch Image QA — {stamp}",
        "",
        f"Frames: {len(results)} approved keyframes · reviewed: {len(ok)} · cost: ${total:.3f}",
        f"Studio passes: {sum(1 for r in ok if r['studio'].get('verdict') == 'pass')} / {len(ok)} · "
        f"agreement with MTower QA: {agree} / {with_mt}",
        "",
        "| Shot | Human | MTower QA | Studio QA | Identity | Top issue |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        s = r["studio"]
        if "error" in s:
            lines.append(f"| {r['shot_id']} | approved | — | error | — | {s['error'][:80]} |")
            continue
        mt = r["mtower"]
        mt_cell = f"{mt.get('verdict')} {mt.get('score')}" if mt else "—"
        ident = ", ".join(f"{i.get('who','?')}: {i.get('status','?')}" for i in (s.get("identity") or [])) or "—"
        issue = (s.get("issues") or ["—"])[0].replace("|", "/")[:140]
        lines.append(f"| {r['shot_id']} | approved | {mt_cell} | {s.get('verdict')} {s.get('score')} | {ident[:90]} | {issue} |")
    mpath = out_dir / f"batch_qa_{stamp}.md"
    mpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jpath, mpath
