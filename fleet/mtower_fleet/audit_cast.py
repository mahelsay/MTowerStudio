"""Cast audit — the studio re-checks every library actor before trusting it (Phase D, independence).

One vision review per actor (gpt-5.6-sol): the approved anchor portrait at full detail + the actor's whole LoRA training
set as low-detail thumbnails (cheap), the captions, the characters the actor plays, the production rules, and the
measured identity failure rate of the actor's face model on real keyframes (free, from QA history). Verdict per actor:

  keep      — fit for the role(s), training set clean
  reroll    — the look is right, but some training images are defective/off-identity → re-roll those keys, retrain
  redesign  — the look itself does not fit the role / production rules → new anchor + training set + face model

Every non-keep finding is captured as a Learning Keeper incident (kind 'anchor' / 'training_set').
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from . import client, grounding, lessons
from .agents.base import _cost, _parse_json
from .agents.image_qa import _image_part

EST_PER_ACTOR_USD = 0.12

SYSTEM = (
    "You are the Casting QA lead of an AI film studio making a photorealistic 1973 Egyptian war drama. Each virtual "
    "actor has an approved ANCHOR portrait (image 1) and a TRAINING SET of reference edits used to train the actor's "
    "face model (LoRA). A bad anchor or a bad training set costs every later shot: faces drift and the reviewer fails "
    "keyframes. Judge, strictly and concretely:\n"
    "1. FIT: does the anchor's look fit every character the actor plays AND the production rules (period, region, age, "
    "rank, military grooming rules such as hair)? A signature feature that contradicts a production rule is a "
    "REDESIGN finding: say exactly which feature must change and to what, keeping everything else.\n"
    "2. ANCHOR QUALITY: photoreal ordinary person (not a model), natural skin, correct anatomy, no text/artifacts, "
    "1970s-plausible grooming.\n"
    "3. TRAINING SET: the same person in every image (flag image keys whose face drifts: different nose/eyes/age/"
    "hair colour, or facial hair the anchor does not have); defects (warped hands, extra fingers, plastic skin, text, "
    "modern items, duplicates); variety (outfits, angles, light, action poses) so clothes and framing do not bake into "
    "the face; captions describe only what changes, never the face. The recipe DELIBERATELY includes civilian outfits, "
    "a 'headwear' key and village settings: they teach the face model to separate face from clothing — never flag "
    "them as role conflicts.\n"
    "Verdict: 'keep' (fit and clean), 'reroll' (look fits; list training keys to re-roll), or 'redesign' (the look must "
    "change). Output JSON: { verdict, fit: { ok: bool, conflicts: [string] }, anchor: { score: 0-10, issues: [string] }, "
    "training: { score: 0-10, drift_keys: [string], defect_keys: [string], issues: [string] }, "
    "redesign_change: string (only for redesign: the exact new look, one sentence), summary: string }."
)


def _media() -> Path:
    return grounding.media_root()


def _identity_rates(production: str, episode: str) -> dict[str, dict]:
    """Free: how often the reviewer failed identity per character on real keyframes (MTower/studio QA history)."""
    stats: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for q in (_media() / "productions" / production / episode / "keyframes").rglob("*.qa.json"):
        try:
            d = json.loads(q.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        idc = (d.get("checks") or {}).get("identity") or {}
        st = idc.get("status")
        if st not in ("ok", "fail", "minor"):
            continue
        for cid in set(re.findall(r"\bC-\d{2}\b", idc.get("notes") or "")):
            stats[cid][st] += 1
    return {c: {"reviews": sum(v.values()), "fail": v["fail"], "rate": round(v["fail"] / max(sum(v.values()), 1), 2)}
            for c, v in stats.items()}


def _latest(folder: Path) -> Path | None:
    batches = sorted(p for p in folder.glob("*") if p.is_dir()) if folder.exists() else []
    return batches[-1] if batches else None


def actor_material(actor: dict) -> dict:
    """Anchor + every KEPT training image across all batches (the engine's rule: minus each batch's rejected.json)."""
    slug_dir = _media() / "library" / "actors" / f"{actor['id']}_{actor['slug']}"
    anchor = actor.get("anchor") or {}
    anchor_path = _media() / anchor["media_path"] if anchor.get("media_path") else None
    root = slug_dir / "training_set"
    images, batches = [], []
    for ts in sorted(p for p in root.glob("*") if p.is_dir()) if root.exists() else []:
        rejected = set()
        if (ts / "rejected.json").exists():
            try:
                rejected = set(json.loads((ts / "rejected.json").read_text(encoding="utf-8")).get("files", []))
            except Exception:  # noqa: BLE001
                pass
        batches.append(ts.name)
        for p in sorted(ts.glob("*.png")):
            if p.name in rejected:
                continue
            cap = p.with_suffix(".txt")
            key = re.sub(r"^act-\d{4}-", "", p.stem).rsplit("_", 1)[0]
            images.append({"key": f"{key}@{ts.name[-6:]}", "path": p,
                           "caption": cap.read_text(encoding="utf-8").strip() if cap.exists() else ""})
    return {"anchor": anchor_path if anchor_path and anchor_path.exists() else None, "training": images,
            "training_batch": ",".join(batches) or None}


def audit_actor(actor: dict, roles: list[dict], rules: str, identity: dict) -> dict:
    m = actor_material(actor)
    role_txt = "\n".join(f"- {r['cid']} {r['character']}: {r.get('additions', '')}" for r in roles) or "- (no role yet)"
    id_txt = "\n".join(f"- {r['cid']}: identity failed in {identity[r['cid']]['fail']} of "
                       f"{identity[r['cid']]['reviews']} keyframe reviews" for r in roles if r["cid"] in identity) or "- n/a"
    text = (f"{rules}\n\nACTOR {actor['id']} ({actor.get('name_en')}), {actor.get('gender')}, apparent age "
            f"{actor.get('apparent_age')}.\nWritten look: {actor.get('face_and_body')}\nSignature features: "
            f"{actor.get('signature_features')}\n\nPLAYS:\n{role_txt}\n\nFACE MODEL ON REAL SHOTS (history):\n{id_txt}\n\n"
            f"TRAINING SET ({len(m['training'])} images, batch {m['training_batch']}): thumbnails follow the anchor, each "
            f"labelled with its key and caption.")
    content: list[dict] = [{"type": "text", "text": text}]
    if m["anchor"]:
        content += [{"type": "text", "text": "IMAGE 1 — APPROVED ANCHOR PORTRAIT:"}, _image_part(str(m["anchor"]))]
    for n, t in enumerate(m["training"], start=2):
        part = _image_part(str(t["path"]))
        part["image_url"]["detail"] = "low"
        content += [{"type": "text", "text": f"IMAGE {n} — training key '{t['key']}' · caption: {t['caption'][:400]}"},
                    part]
    messages = [{"role": "system", "content": SYSTEM + "\nRespond ONLY with a single valid JSON object."},
                {"role": "user", "content": content}]
    raw, usage = client.complete(messages, vision=True, response_format={"type": "json_object"},
                                 max_completion_tokens=6000)
    data = _parse_json(raw)
    data.update(actor=actor["id"], name=actor.get("name_en"), roles=[r["cid"] for r in roles],
                training_images=len(m["training"]), training_batch=m["training_batch"],
                identity_history={r["cid"]: identity.get(r["cid"]) for r in roles},
                _cost_usd=_cost(usage, True))
    return data


def run(production: str, episode: str, actor_ids: list[str] | None = None, on_actor=None) -> list[dict]:
    lib = json.loads((grounding.LIBRARY_DIR / "actors" / "actors.json").read_text(encoding="utf-8"))["actors"]
    pre = grounding.PRODUCTIONS_DIR / production / episode / "02_preproduction"
    cast = json.loads((pre / "casting.json").read_text(encoding="utf-8"))["cast"]
    qa = json.loads((pre / "production_config.json").read_text(encoding="utf-8")).get("qa", {})
    rules = f"PRODUCTION: {qa.get('story', '')}\nPRODUCTION RULES:\n" + "\n".join(f"- {r}" for r in qa.get("rules", []))
    identity = _identity_rates(production, episode)
    out = []
    for a in lib:
        if actor_ids and a["id"] not in actor_ids:
            continue
        roles = [{"cid": cid, "character": c.get("character", ""),
                  "additions": "; ".join(x for x in (c.get("character_additions"), c.get("face_additions")) if x)}
                 for cid, c in cast.items() if c.get("actor") == a["id"]]
        try:
            res = audit_actor(a, roles, rules, identity)
        except Exception as e:  # noqa: BLE001
            res = {"actor": a["id"], "error": str(e)}
        out.append(res)
        if "error" not in res and res.get("verdict") != "keep":
            kind = "anchor" if res.get("verdict") == "redesign" else "training_set"
            problem = " || ".join((res.get("fit") or {}).get("conflicts", []) + (res.get("anchor") or {}).get("issues", [])
                                  + (res.get("training") or {}).get("issues", []))
            lessons.capture(kind=kind, target=a["id"], production=production, episode=episode, department="casting",
                            source="studio-cast-audit", problem=problem or res.get("summary", ""), resolved=False,
                            fix=res.get("redesign_change", ""), tags=[r["cid"] for r in roles] + [f"KIND:{kind}"])
        if on_actor:
            on_actor(res)
    return out


def estimate(actor_ids: list[str] | None = None) -> tuple[int, float]:
    lib = json.loads((grounding.LIBRARY_DIR / "actors" / "actors.json").read_text(encoding="utf-8"))["actors"]
    n = sum(1 for a in lib if not actor_ids or a["id"] in actor_ids)
    return n, round(n * EST_PER_ACTOR_USD, 2)


PICK_SYSTEM = (
    "You are the Casting QA lead. A virtual actor's approved portrait (image 1, BEFORE) was edited to fix one thing. "
    "Judge each CANDIDATE: (a) identity — is it unmistakably the SAME person (bone structure, nose, eyes, skin marks); "
    "(b) the requested change is fully and naturally applied; (c) photoreal, no artifacts, plausible 1973 Egypt; "
    "(d) fits the role. Score 0-10 each candidate; pass needs score >= 8 and identity same. Output JSON: "
    "{ candidates: [ { file, identity: 'same'|'drifted', change_applied: bool, score, issues: [string] } ], "
    "best: file or '', verdict: 'pass'|'fail', note }."
)


def pick_anchor(actor: dict, roles: list[dict], instruction: str, batch: Path) -> dict:
    """Studio QA of anchor-edit candidates (before vs after), choosing the best one."""
    m = actor_material(actor)
    rejected = set()
    if (batch / "rejected.json").exists():
        rejected = set(json.loads((batch / "rejected.json").read_text(encoding="utf-8")).get("files", []))
    cands = [p for p in sorted(batch.glob("*.png")) if p.name not in rejected]
    role_txt = "; ".join(f"{r['cid']} {r['character']}" for r in roles) or "no role"
    content: list[dict] = [{"type": "text", "text": f"ACTOR {actor['id']} plays {role_txt}. Written look: "
                            f"{actor.get('face_and_body')}\nREQUESTED CHANGE: {instruction}"},
                           {"type": "text", "text": "IMAGE 1 — BEFORE (approved portrait):"}, _image_part(str(m["anchor"]))]
    for n, c in enumerate(cands, start=2):
        content += [{"type": "text", "text": f"IMAGE {n} — CANDIDATE file '{c.name}':"}, _image_part(str(c))]
    messages = [{"role": "system", "content": PICK_SYSTEM + "\nRespond ONLY with a single valid JSON object."},
                {"role": "user", "content": content}]
    raw, usage = client.complete(messages, vision=True, response_format={"type": "json_object"},
                                 max_completion_tokens=4000)
    data = _parse_json(raw)
    data.update(actor=actor["id"], batch=str(batch), _cost_usd=_cost(usage, True))
    (batch / "studio_pick.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data
