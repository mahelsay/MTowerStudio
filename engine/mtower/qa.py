"""Vision QA: an Azure reviewer model checks every image against what it was designed to show.

Generation and review are two separate paths. The reviewer (engine_config 'qa_review', gpt-5.6-sol on the studio's
Foundry) gets the picture, the shot's design (screenplay context, characters, props, location rules, look, the
production's period rules), the leads' casting portraits and the real props' reference photos, and answers with a
strict JSON verdict: pass / minor / fail, a 0-10 score, a check per category, the issues with concrete fixes, and the
cheapest route to fix it (keep, edit, face swap, recompose, new prompt).

Verdicts are saved next to each image as <image>.qa.json (the review gallery shows them) and summarised in a Markdown
report under the production's 03_production/qa/ folder. Standard library only.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import costs
from .library import Library
from .production import Production
from .prompts import ANNOTATION, PromptComposer
from .settings import PRODUCTIONS_DIR, load_json, media_root, write_json

CATEGORIES = ["design_match", "anatomy_proportions", "face_integration", "identity", "period_accuracy", "props_weapons",
              "physics_scale", "location_rules", "lighting", "technical", "culture_safety"]
ROUTES = ["keep", "edit", "face_swap", "recompose", "new_prompt"]

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["people", "verdict", "score", "summary", "checks", "issues", "fix_route", "edit_instruction"],
    "properties": {
        "people": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["who", "where", "head_widths_across_shoulders", "head_size", "head_on_neck", "face_light", "gaze"],
            "properties": {
                "who": {"type": "string"}, "where": {"type": "string"},
                "head_widths_across_shoulders": {"type": "number"},
                "head_size": {"type": "string", "enum": ["natural", "too large", "too small", "not visible"]},
                "head_on_neck": {"type": "string", "enum": ["natural", "neck too long", "neck too short", "off-centre or tilted unnaturally", "not visible"]},
                "face_light": {"type": "string", "enum": ["matches the scene", "brighter or warmer than the scene", "darker than the scene", "not visible"]},
                "gaze": {"type": "string", "enum": ["as designed", "into the camera", "wrong direction", "not visible"]}}}},
        "verdict": {"type": "string", "enum": ["pass", "minor", "fail"]},
        "score": {"type": "integer"},
        "summary": {"type": "string"},
        "checks": {"type": "object", "additionalProperties": False, "required": CATEGORIES, "properties": {
            c: {"type": "object", "additionalProperties": False, "required": ["status", "notes"], "properties": {
                "status": {"type": "string", "enum": ["ok", "minor", "fail", "n/a"]}, "notes": {"type": "string"}}}
            for c in CATEGORIES}},
        "issues": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["severity", "category", "description", "fix"],
            "properties": {"severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                           "category": {"type": "string", "enum": CATEGORIES},
                           "description": {"type": "string"}, "fix": {"type": "string"}}}},
        "fix_route": {"type": "string", "enum": ROUTES},
        "edit_instruction": {"type": "string"},
    },
}

SYSTEM = """You are the image QA board of a film studio that makes photorealistic historical war drama with AI. You combine
four jobs: script supervisor (does the frame show what the shot was designed to show?), historical military advisor
(is every uniform, weapon, vehicle and object right for the period?), VFX compositing lead (does anything look generated,
pasted or physically wrong?) and casting director (is each lead clearly the cast actor?).

The frame you review becomes the first frame of an image-to-video clip, so every flaw spreads through the shot. Be strict
and specific, but never invent problems: judge only what is visible, and if you are unsure, say so and rate it minor.

Before judging, MEASURE the people: list in 'people' every clearly visible person in the foreground and middle ground
(up to six, the leads first). For each, look at the head against the body as a life-drawing teacher would: how many head
widths fit across the shoulders (a natural adult man: about 2.5-3; below 2.2 means the head is too large), whether the
neck is natural or stretched/shortened, whether the head sits centred on the neck and turns with the body, whether the
face has the same light colour and brightness as the neck, hands and uniform beside it, and where the eyes look.
Generated faces are often slightly too large, too frontal, too clean or lit warmer than the scene: look for exactly that.
Any 'too large', 'too small', 'neck too long', 'off-centre', 'brighter or warmer than the scene' or unwanted 'into the
camera' is at least a major issue in anatomy_proportions or face_integration.

Check, in this order:
1. design_match — the action, the number and placement of people, who is in front, the shot size and lens, the camera
   angle, the time of day and the setting all match the design. The frame fills 16:9 edge to edge.
2. anatomy_proportions — every head is life-size for its body (an adult is about 7.5 heads tall, shoulders about 3 heads
   wide), sits centred on its own neck between the shoulders and turns with the body; neck length and thickness are
   natural; two arms and two legs per person; hands have five fingers and grip things naturally; no merged, floating,
   cut-off or duplicated bodies; children have child proportions; nobody stares into the lens unless the design asks for it.
3. face_integration — faces look photographed in this scene, not pasted: the same light direction, colour temperature,
   contrast, grain, focus and dirt/wetness as the neck and body; no seam, halo, or face that is sharper, warmer or
   cleaner than its surroundings.
4. identity — only when casting portraits are attached: each lead is clearly the same person as his or her portrait
   (face shape, eyes, nose, mouth, facial hair, age, skin tone). Dirt, sweat, wet hair, expression and lighting may differ.
   The portrait is the truth for the face: where the written face description disagrees with the portrait, follow the
   portrait and do not report the difference.
   'n/a' when no portrait is attached or the face is not visible by design.
5. period_accuracy — uniforms, insignia, hairstyles, kit, vehicles, aircraft, furniture and everyday objects fit the
   production's period rules; nothing modern.
6. props_weapons — the named weapons and props are present, correct in shape, size and detail (compare with the
   attached reference photos when given), held and carried the way soldiers would.
7. physics_scale — real-world scale between people, weapons, vehicles and buildings; one perspective and horizon; water,
   mud, sand, smoke, splashes and reflections behave physically; shadows agree with the light.
8. location_rules — the location's own rules (given below) hold. Even in close-ups and inserts, whatever background is
   visible (ground, water, plants, sky, light) must belong to this location and time of day.
9. lighting — the look is the designed one (night stays night, fire is the only warm light at night, and so on).
10. technical — no AI artifacts (melted details, garbled patterns, extra objects, warped faces in the background),
   no text, captions, logos, watermarks, borders or letterbox bars, no heavy blur where focus is designed.
11. culture_safety — the culture and religion of the people shown are respected and consistent (see the rules); no gore.

Verdict: 'pass' = ready to animate as is; 'minor' = small flaws most viewers would miss, or one detail an edit can fix;
'fail' = a viewer would notice, or it breaks history, identity, anatomy or the design. Score 0-10: 9-10 flawless,
7-8 small flaws only, 5-6 noticeable but fixable flaws, 4 or less broken. Framing that is a little wider or tighter
than the designed lens, or a slightly different camera height, is minor unless it hides the story point. Each issue
names what is wrong and where, and a concrete fix.

fix_route — the cheapest route that fixes every major and critical issue:
- keep: nothing to fix.
- edit: one or two local details (an object, a symbol, a hand, a strap); write edit_instruction as one or two plain
  sentences for an image-edit model, ending with 'Keep everything else exactly the same.'
- face_swap: the composition is right but a lead's face is wrong (identity, size, placement or light): redo only the face.
- recompose: the design is fine but this render failed (anatomy, layout, scale): render it again from the same design.
- new_prompt: the design text itself causes the problem; say in the fix what to change in the shot design.
Leave edit_instruction empty unless fix_route is 'edit'."""


@dataclass
class Item:
    kind: str                    # keyframe | anchor
    target: str                  # shot ID or actor ID
    image: Path
    brief: str
    refs: list[tuple[str, Path]] = field(default_factory=list)
    status: str = ""             # approved / candidate / rejected / anchor

    @property
    def qa_path(self) -> Path:
        return self.image.with_suffix(".qa.json")


def _batch_state(path: Path) -> str:
    folder = path.parent
    approved = folder / "approved.json"
    if approved.exists() and load_json(approved).get("file") == path.name:
        return "approved"
    rejected = folder / "rejected.json"
    if rejected.exists() and path.name in load_json(rejected).get("files", []):
        return "rejected"
    return "candidate"


def _notes(path: Path) -> str:
    notes = path.parent / "notes.json"
    return load_json(notes).get(path.name, "") if notes.exists() else ""


def shot_brief(lib: Library, prod: Production, composer: PromptComposer, beat: dict, shot: dict) -> tuple[str, list[tuple[str, Path]]]:
    """The shot's design in plain words, plus the reference images to compare against (casting portraits, prop photos)."""
    from .jobs import rank_references, shot_references

    cast = prod.casting["cast"]
    wear = shot.get("wear", beat.get("wear"))
    looks = shot.get("look") or beat.get("look") or []
    chars = [c if isinstance(c, str) else c.get("id") for c in shot.get("characters") or []]
    face_visible = shot.get("face_pass", True) is not False and not composer.is_insert(shot)
    lines = [f"Shot {shot['shot_id']} — beat {beat.get('beat')} '{beat.get('title', '')}'.",
             f"Shot size {shot.get('size') or shot.get('shot_size')}, lens {composer.lens(shot.get('lens')) or shot.get('lens')}, "
             f"camera move {shot.get('move') or shot.get('camera_move') or 'static'}.",
             f"What the frame shows: {shot.get('prompt') or shot.get('image_prompt_core') or ''}",
             f"What happens next in the clip (for context): {shot.get('motion') or shot.get('motion_prompt') or ''}"]
    if shot.get("face"):
        lines.append(f"Face direction: {shot['face']}")
    if not face_visible:
        lines.append("By design the lead's face is NOT visible (seen from behind, in shadow or in profile darkness).")
    for c in chars:
        info = cast.get(c, {})
        lines.append(f"Character {c} {info.get('role', '')}: {composer.character(c, wear, use_lora=False)}")
    if shot.get("extras"):
        lines.append(f"Extras: {composer.extras_text(shot.get('extras'), wear)}")
    for a in shot.get("assets") or []:
        text = composer.asset_text(a, triggers=False)
        if text:
            lines.append(f"Asset {re.sub(ANNOTATION, '', a)}: {text}")
    loc_id = shot.get("location") or beat.get("location")
    loc = lib.locations.get(loc_id or "", {})
    if loc:
        lines.append(f"Location {loc_id} {loc.get('name', '')}: {loc.get('prompt', '')}")
        for rule in loc.get("qa_rules") or []:
            lines.append(f"Location rule: {rule}")
    look = "; ".join(x for x in (composer.look(k) for k in looks) if x)
    if look:
        lines.append(f"Look and light: {look}")
    if wear:
        lines.append(f"Wear state: {composer.wear_text(wear)}")
    if shot.get("notes"):
        lines.append(f"Director's design notes: {shot['notes']}")

    refs: list[tuple[str, Path]] = []
    if face_visible:
        for c in chars:
            actor = lib.actors.get(cast.get(c, {}).get("actor", ""), {})
            media = (actor.get("anchor") or {}).get("media_path")
            if media and (media_root() / media).exists():
                refs.append((f"casting portrait of {c} {cast[c].get('role', '')} (actor {actor.get('id')})", media_root() / media))
    per_prop: dict[str, int] = {}
    for p in shot_references(lib, shot):
        pid = re.search(r"PRP-\d{4}", str(p))
        key = pid.group(0) if pid else p.parent.name
        if per_prop.get(key, 0) < 2 and len(refs) < 5:
            per_prop[key] = per_prop.get(key, 0) + 1
            refs.append((f"real reference photo of prop {key} {lib.props.get(key, {}).get('name', '')}", p))
    for role, p in (rank_references(prod, chars) if not composer.is_insert(shot) else []):
        refs.append((f"official drawing of the shoulder-strap rank insignia the {role} must wear (judge count and shape; "
                     f"on film it is small gold metal on a khaki strap, so tiny details may be soft)", p))
    return "\n".join(lines), refs


def keyframe_items(lib: Library, prod: Production, shot_ids: list[str] | None = None, part: str | None = None,
                   scope: str = "current") -> list[Item]:
    """scope 'current': each shot's approved keyframe, else every image of its newest batch; 'all': every keyframe ever made."""
    composer = PromptComposer(lib, prod)
    items = []
    for sl, beat, shot in prod.all_shots(part):
        sid = shot["shot_id"]
        if shot_ids and sid not in shot_ids:
            continue
        root = media_root() / "productions" / prod.key / "keyframes" / sl["part"] / sid
        batches = sorted(d for d in root.glob("*") if d.is_dir() and re.match(r"^\d{8}-\d{6}", d.name)) if root.exists() else []
        files = [f for b in batches for f in sorted(b.glob("*.png"))]
        if not files:
            continue
        if scope == "current":
            approved = [f for f in files if _batch_state(f) == "approved"]
            if approved:  # the approved image plus every candidate made after it (re-draws of an approved shot)
                files = approved[-1:] + [f for f in files if f.parent.name > approved[-1].parent.name]
            else:
                files = sorted(batches[-1].glob("*.png"))
        brief, refs = shot_brief(lib, prod, composer, beat, shot)
        for f in files:
            items.append(Item("keyframe", sid, f, brief, refs, _batch_state(f)))
    return items


def anchor_items(lib: Library, actor_ids: list[str] | None = None) -> list[Item]:
    items = []
    for aid, actor in lib.actors.items():
        if actor_ids and aid not in actor_ids:
            continue
        media = (actor.get("anchor") or {}).get("media_path")
        if not media or not (media_root() / media).exists():
            continue
        brief = (f"Casting anchor portrait of virtual actor {aid} {actor.get('name_en', '')} "
                 f"({actor.get('gender', '')}, apparent age {actor.get('apparent_age', '?')}). This one portrait defines the "
                 f"actor's face for the whole series and trains the face model, so it must be a clean, natural, photoreal "
                 f"head-and-shoulders portrait, facing the camera, soft even light, plain background, no text. Anchors are "
                 f"vertical 3:4 portraits by design: the 16:9 frame rule does NOT apply to them.\n"
                 f"Designed face and body: {actor.get('face_and_body', '')}\n"
                 "For this portrait the shot-related checks (props, location, period kit) are 'n/a' unless something visible "
                 "breaks them; identity means: does the face match the designed description (age, build, every listed feature)?")
        items.append(Item("anchor", aid, media_root() / media, brief, [], "anchor"))
    return items


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _messages(item: Item, rules: dict) -> list[dict]:
    context = [f"PRODUCTION: {rules.get('story', '')}", "PRODUCTION RULES:"] + [f"- {r}" for r in rules.get("rules", [])]
    context += ["", "DESIGN OF THIS IMAGE:", item.brief]
    try:
        from .faces import image_size
        w, h = image_size(item.image)
        context += ["", f"FRAME SIZE (measured by the engine): {w}x{h} pixels. Do not estimate or report the aspect ratio "
                        "yourself (black bars painted inside the frame still count as a technical issue)."]
    except (OSError, ValueError):
        pass
    notes = _notes(item.image)
    if notes:
        context += ["", f"THE DIRECTOR ALREADY FLAGGED THIS IMAGE: \"{notes}\" — check this point first."]
    content: list[dict] = [{"type": "text", "text": "\n".join(context)},
                           {"type": "text", "text": "IMAGE 1 — the image to review:"},
                           {"type": "image_url", "image_url": {"url": _data_url(item.image), "detail": "high"}}]
    for n, (label, path) in enumerate(item.refs, 2):
        content += [{"type": "text", "text": f"IMAGE {n} — {label} (a reference, not to be reviewed):"},
                    {"type": "image_url", "image_url": {"url": _data_url(path), "detail": "high"}}]
    content.append({"type": "text", "text": "Review IMAGE 1 now and answer with the JSON verdict."})
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]


def usage_cost(usage: dict, m: dict) -> float:
    p = m["pricing_per_m_tokens"]
    return round((usage.get("prompt_tokens", 0) * p["input_per_m"] + usage.get("completion_tokens", 0) * p["output_per_m"])
                 / 1_000_000, 5)


def review(client, m: dict, item: Item, rules: dict) -> dict:
    body = {"messages": _messages(item, rules), "max_completion_tokens": m.get("max_completion_tokens", 6000),
            "reasoning_effort": m.get("reasoning_effort", "medium"),
            "response_format": {"type": "json_schema", "json_schema": {"name": "qa_verdict", "strict": True, "schema": SCHEMA}}}
    url = (f"{client.endpoint}/openai/deployments/{m['model_id']}/chat/completions?api-version={client.api_version}")
    started = time.time()
    for attempt in range(2):  # a review is cheap: retry once after a dropped connection or a read timeout
        try:
            data = client._post(url, json.dumps(body).encode("utf-8"), "application/json")
            break
        except Exception as err:  # noqa: BLE001
            if attempt or "network error" not in str(err):
                raise
            time.sleep(10)
    verdict = json.loads(data["choices"][0]["message"]["content"])
    usage = data.get("usage") or {}
    return {**verdict, "kind": item.kind, "target": item.target, "file": item.image.name, "state": item.status,
            "references": [label for label, _ in item.refs], "director_note": _notes(item.image),
            "model": m["model_id"], "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seconds": round(time.time() - started, 1), "usage": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens")},
            "cost_usd": usage_cost(usage, m), "request_id": data.get("_request_id")}


def estimates(items: list[Item]) -> list[costs.Estimate]:
    return [costs.estimate("qa_review", len(items))] if items else []


IDENTIFY_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["picks"], "properties": {
    "picks": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["char", "face", "why"],
                                         "properties": {"char": {"type": "string"}, "face": {"type": "integer"},
                                                        "why": {"type": "string"}}}}}}


def identify_faces(image: Path, boxes: list[dict], who: dict) -> tuple[list[int | None], float]:
    """Which detected face belongs to which character, decided by the vision reviewer from the shot design (role, rank,
    clothes, position, action) — 'the largest face' put the captain's face on the front man of a file he walks behind.
    who = {"shot": design text, "chars": [{"char", "role"}]}. Returns (1-based box number or None per character, cost)."""
    import subprocess
    import tempfile

    from .animatic import ffmpeg
    from .providers.azure import AzureClient

    m = costs.model("qa_review")
    with tempfile.TemporaryDirectory() as tmp:
        marked = Path(tmp) / "faces.png"
        draw = [f"drawbox=x={int(b['x'])}:y={int(b['y'])}:w={max(2, int(b['w']))}:h={max(2, int(b['h']))}:color=yellow:t=3,"
                f"drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{i}':x={int(b['x'])}:y={max(0, int(b['y']) - 34)}:"
                "fontsize=32:fontcolor=yellow:borderw=3:bordercolor=black" for i, b in enumerate(boxes, 1)]
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(image), "-vf", ",".join(draw), str(marked)],
                       check=True, stdin=subprocess.DEVNULL)
        url = _data_url(marked)
    lines = [f"- {c['char']}: {c['role']}" for c in who["chars"]]
    text = ("A still from a historical war film. The numbered yellow boxes mark the faces a detector found.\n"
            f"SHOT DESIGN: {who['shot']}\n\nCHARACTERS:\n" + "\n".join(lines) + "\n\n"
            "For each character, give the number of the face that belongs to him or her, judged from the role, rank, "
            "clothes, position in the frame and what the shot design says that person is doing (the faces are not yet "
            "the actors' faces, so do not judge by the face itself). Answer 0 when the character is not in the picture. "
            "Never give one face to two characters.")
    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": text},
                                                      {"type": "image_url", "image_url": {"url": url, "detail": "high"}}]}],
            "max_completion_tokens": 3000, "reasoning_effort": "low",
            "response_format": {"type": "json_schema", "json_schema": {"name": "face_ids", "strict": True, "schema": IDENTIFY_SCHEMA}}}
    client = AzureClient()
    data = client._post(f"{client.endpoint}/openai/deployments/{m['model_id']}/chat/completions?api-version={client.api_version}",
                        json.dumps(body).encode("utf-8"), "application/json")
    picks = {p["char"]: p["face"] for p in json.loads(data["choices"][0]["message"]["content"])["picks"]}
    cost = usage_cost(data.get("usage") or {}, m)
    costs.record({"provider": "azure", "kind": "face_identify", "target": image.name, "model_id": m["model_id"],
                  "units": 1, "unit": "request", "cost_usd": cost})
    out, used = [], set()
    for c in who["chars"]:
        n = picks.get(c["char"], 0)
        ok = isinstance(n, int) and 1 <= n <= len(boxes) and n not in used
        out.append(n if ok else None)
        used |= {n} if ok else set()
    return out, cost


LOOKALIKE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["confusable", "summary"], "properties": {
    "summary": {"type": "string"},
    "confusable": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                              "required": ["a", "b", "risk", "why", "fix"], "properties": {
        "a": {"type": "string"}, "b": {"type": "string"}, "risk": {"type": "integer"},
        "why": {"type": "string"}, "fix": {"type": "string"}}}}}}


def lookalike_review(lib: Library, roles: dict[str, str], min_risk: int = 5) -> dict:
    """The visual half of cast-check: the vision reviewer sees every approved casting portrait at once and lists pairs an
    ordinary viewer could confuse at night, in uniform, in dim light (the trait check only compares written traits).
    One request, about $0.05–0.10."""
    from .providers.azure import AzureClient

    m = costs.model("qa_review")
    content: list[dict] = [{"type": "text", "text": (
        "Casting portraits of a TV drama cast. Compare every pair of the same gender and similar age group (ignore children). "
        "Decide whether an ordinary viewer could confuse the two on screen at night, in the same uniform, in dim light. "
        f"List every pair with risk >= {min_risk} (1-10), highest first. For 'fix', say what to change in ONE of the two — "
        "prefer the actor marked 'not locked'.")}]
    for aid, actor in sorted(lib.actors.items()):
        path = media_root() / ((actor.get("anchor") or {}).get("media_path") or "")
        if not path.is_file():
            continue
        state = "locked" if actor.get("status") == "locked" else "not locked"
        content += [{"type": "text", "text": f"{aid} — {actor.get('name_en', '')} — {actor.get('gender', '')}, about "
                                             f"{actor.get('apparent_age', '?')} — plays {roles.get(aid, '(no role yet)')} — {state}"},
                    {"type": "image_url", "image_url": {"url": _data_url(path), "detail": "low"}}]
    body = {"messages": [{"role": "user", "content": content}], "max_completion_tokens": m.get("max_completion_tokens", 6000),
            "reasoning_effort": "medium",
            "response_format": {"type": "json_schema", "json_schema": {"name": "lookalikes", "strict": True, "schema": LOOKALIKE_SCHEMA}}}
    client = AzureClient()
    data = client._post(f"{client.endpoint}/openai/deployments/{m['model_id']}/chat/completions?api-version={client.api_version}",
                        json.dumps(body).encode("utf-8"), "application/json")
    result = json.loads(data["choices"][0]["message"]["content"])
    cost = usage_cost(data.get("usage") or {}, m)
    costs.record({"provider": "azure", "kind": "cast_check_visual", "target": f"{len(content) // 2} portraits",
                  "model_id": m["model_id"], "units": 1, "unit": "request", "cost_usd": cost})
    result["confusable"] = sorted((p for p in result["confusable"] if p["risk"] >= min_risk), key=lambda p: -p["risk"])
    return {**result, "cost_usd": cost}


def run(items: list[Item], confirm_cost: float | None, prod: Production, workers: int = 4) -> list[dict]:
    """Review every item (skips images that already have a .qa.json — pass them through force by deleting it)."""
    from .providers.azure import AzureClient, AzureError

    costs.authorize(estimates(items), confirm_cost)
    m = costs.model("qa_review")
    rules = prod.config.get("qa", {})
    client = AzureClient()
    client.token()  # sign in once before the threads start

    def one(item: Item) -> dict | None:
        for attempt in range(2):
            try:
                result = review(client, m, item, rules)
                write_json(item.qa_path, result)
                mark = {"pass": "✓", "minor": "~", "fail": "✗"}[result["verdict"]]
                print(f"  {mark} {item.target:8} {item.image.parent.name}/{item.image.name} {result['verdict']:5} "
                      f"{result['score']}/10 {result['fix_route']:10} ${result['cost_usd']:.3f}", flush=True)
                return result
            except (AzureError, KeyError, ValueError) as err:
                if attempt:
                    print(f"  ! {item.target} {item.image.name}: {str(err)[:200]}", flush=True)
        return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = [r for r in pool.map(one, items) if r]
    spent = round(sum(r["cost_usd"] for r in results), 4)
    if results:
        costs.record({"production": prod.key, "provider": "azure", "kind": "qa_review", "target": f"{len(results)} image(s)",
                      "model_id": m["model_id"], "units": len(results), "unit": "image", "cost_usd": spent,
                      "request_ids": [r.get("request_id") for r in results]})
    print(f"\nReviewed {len(results)} of {len(items)} image(s) · actual cost ${spent:.3f}")
    return results


def collect(prod: Production, lib: Library) -> list[dict]:
    """Every saved verdict for this production's keyframes and the library's anchors."""
    found = []
    roots = [media_root() / "productions" / prod.key / "keyframes", media_root() / "library" / "actors"]
    for root in roots:
        for path in sorted(root.rglob("*.qa.json")) if root.exists() else []:
            data = load_json(path)
            data["_path"] = path
            image = path.with_name(path.name[: -len(".qa.json")] + ".png")
            if data.get("kind") == "keyframe" and image.exists():
                data["state"] = _batch_state(image)  # approvals may have changed since the review
                data["batch"] = path.parent.name
            found.append(data)
    return found


def write_compare(prod: Production) -> Path:
    """media/.../qa_compare.html: per shot, the approved keyframe next to the best-scoring candidate made since, with both
    QA verdicts — the director's sign-off sheet after an autofix run. Open it straight from disk."""
    import html as h

    root = media_root() / "productions" / prod.key
    rows = []
    for sl, _, shot in prod.all_shots():
        sid = shot["shot_id"]
        folder = root / "keyframes" / sl["part"] / sid
        if not folder.exists():
            continue
        scored = []
        for f in folder.glob("*/*.qa.json"):
            image = f.with_name(f.name[: -len(".qa.json")] + ".png")
            if image.exists():
                scored.append((load_json(f), image))
        if not scored:
            continue
        approved = [(v, i) for v, i in scored if _batch_state(i) == "approved"]
        best = max(scored, key=lambda s: (s[0].get("score", 0), s[1].parent.name))
        current = approved[0] if approved else None

        def cell(entry, label):
            if not entry:
                return "<td><p>(nothing approved yet)</p></td>"
            v, img = entry
            rel = img.relative_to(root).as_posix()
            issues = "".join(f"<li><b>{h.escape(i['severity'])}</b> {h.escape(i['description'])}</li>"
                             for i in v.get("issues") or [] if i["severity"] != "minor")
            colour = {"pass": "#3c9", "minor": "#e90", "fail": "#e44"}.get(v.get("verdict"), "#888")
            return (f'<td><p><b>{label}</b> · <span style="color:{colour}">{h.escape(v.get("verdict", ""))} '
                    f'{v.get("score")}/10</span> · {h.escape(img.parent.name)}</p><a href="{rel}" target="_blank">'
                    f'<img src="{rel}"></a><p class="s">{h.escape(v.get("summary", ""))}</p><ul>{issues}</ul></td>')

        same = current and current[1] == best[1]
        rows.append(f"<tr><th>{sid}</th>{cell(current, 'approved')}"
                    + ("<td><p>The approved keyframe is still the best.</p></td>" if same else cell(best, "best candidate"))
                    + "</tr>")
    out = root / "qa_compare.html"
    style = ("body{font-family:Segoe UI,Arial;background:#111;color:#ddd;margin:20px}td,th{vertical-align:top;padding:8px;"
             "border-bottom:1px solid #333}th{font-size:18px}img{width:560px;display:block}p.s{max-width:560px;font-size:12px;"
             "color:#aaa}ul{max-width:560px;font-size:12px;padding-left:16px}")
    out.write_text(f"<!doctype html><meta charset=utf-8><title>QA compare</title><style>{style}</style>"
                   f"<h1>Approved vs best QA candidate — {h.escape(prod.key)}</h1><p>Approve a candidate in the review "
                   f"gallery (it appears under 'Older versions' of the shot until approved).</p><table>{''.join(rows)}</table>",
                   encoding="utf-8")
    return out


def write_report(prod: Production, lib: Library) -> Path:
    results = collect(prod, lib)
    order = {"fail": 0, "minor": 1, "pass": 2}
    out = PRODUCTIONS_DIR / prod.key / "03_production" / "qa" / "qa_report.md"
    counts = {v: sum(1 for r in results if r["verdict"] == v) for v in ("pass", "minor", "fail")}
    spent = sum(float(r.get("cost_usd") or 0) for r in results)
    lines = ["# Image QA report", "",
             f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by `mtower qa` (reviewer: Azure `{costs.model('qa_review')['model_id']}`). "
             "Each image's full verdict is saved next to it as `<image>.qa.json`; the review gallery shows it on the card.", "",
             f"**{len(results)} images reviewed** · ✓ pass {counts['pass']} · ~ minor {counts['minor']} · ✗ fail {counts['fail']} "
             f"· review cost ${spent:.2f}", "",
             "Routes: **keep** · **edit** (one detail, Kontext/gpt-image edit) · **face_swap** (redo a lead's face) · "
             "**recompose** (same design, new render) · **new_prompt** (change the shot design).", ""]
    for kind, title in (("keyframe", "Keyframes"), ("anchor", "Casting anchors")):
        rows = [r for r in results if r.get("kind") == kind]
        if not rows:
            continue
        lines += [f"## {title}", "", "| Target | Image | State | Verdict | Score | Route | Main issues |", "|---|---|---|---|---|---|---|"]
        rows.sort(key=lambda r: (r["target"], r.get("batch", ""), r["file"]))
        for r in rows:
            issues = sorted(r.get("issues") or [], key=lambda i: ["critical", "major", "minor"].index(i["severity"]))
            text = "; ".join(f"**{i['severity']}** {i['description']}" for i in issues[:3]) or r.get("summary", "")
            mark = {"pass": "✓ pass", "minor": "~ minor", "fail": "✗ fail"}[r["verdict"]]
            where = f"{r.get('batch', '')}/{r['file']}" if r.get("batch") else r["file"]
            lines.append(f"| {r['target']} | {where} | {r.get('state', '')} | {mark} | {r['score']} | {r['fix_route']} | "
                         f"{text.replace('|', '/')} |")
        lines.append("")
    approved_fail = [r for r in results if r.get("state") == "approved" and r["verdict"] == "fail"]
    if approved_fail:
        lines += ["## Approved keyframes that failed QA", ""]
        for r in sorted(approved_fail, key=lambda r: r["target"]):
            lines.append(f"- **{r['target']}** ({r['fix_route']}): {r.get('summary', '')}")
        lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    summary = [{k: v for k, v in r.items() if not k.startswith("_") and k not in ("checks", "usage", "request_id")} for r in
               sorted(results, key=lambda r: (order[r["verdict"]], r["target"]))]
    write_json(out.with_name("qa_summary.json"), {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                   "counts": counts, "items": summary})
    write_compare(prod)
    return out
