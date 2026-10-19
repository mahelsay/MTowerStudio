"""Plan and run generation batches: actor anchors, asset plates, shot keyframes, clips."""

from __future__ import annotations
import base64
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import costs
from .library import Library, update_actor, update_prop
from .production import Production
from .prompts import PromptComposer
from .settings import LIBRARY_DIR, engine_config, load_json, media_root, write_json


@dataclass
class Job:
    kind: str
    target: str
    prompt: str
    model_key: str
    units: float
    out_dir: Path
    payload: dict = field(default_factory=dict)
    negative: str = ""
    extra: list = field(default_factory=list)  # [(model_key, units)] helper calls billed with this job
    price_usd: float | None = None  # overrides the model's unit price (e.g. a quality level)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def batch_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _image_model(tier: str, use_lora: bool) -> str:
    if use_lora:
        return "image_lora"
    return {"draft": "image_draft", "final": "image_final"}[tier]


# ---- planners -------------------------------------------------------------------
def refuse_locked(lib: Library, actor_ids: list[str], action: str) -> None:
    """A locked actor's look is final: new anchors, training images or face models would silently change it."""
    locked = [a for a in actor_ids if lib.actors.get(a, {}).get("status") == "locked"]
    if locked:
        raise ValueError(f"{', '.join(locked)} {'is' if len(locked) == 1 else 'are'} locked (approved for production), "
                         f"so no new {action}. To change a locked actor, the director sets the card's status back to "
                         "'lora_trained' in library/actors/actors.json and notes why.")


def plan_anchors(lib: Library, prod: Production, actor_ids: list[str], candidates: int, tier: str,
                 model_key: str | None = None) -> list[Job]:
    refuse_locked(lib, actor_ids, "anchor portraits")
    composer = PromptComposer(lib, prod)
    size = engine_config()["reference_image_size"]
    key = model_key or _image_model(tier, False)
    if key not in engine_config()["models"] and f"image_{key}" in engine_config()["models"]:
        key = f"image_{key}"
    uses_aspect = "aspect_ratio" in costs.model(key).get("payload", {})
    jobs, stamp = [], batch_id()
    azure = costs.model(key).get("provider") == "azure"
    # Azure portraits are made at high quality, 1024x1536 (actual ≈ $0.17 each; the configured high price is the ceiling)
    portrait_price = costs.model(key).get("quality_prices_usd", {}).get("high") if azure else None
    for aid in actor_ids:
        actor = lib.actors[aid]
        out = media_root() / "library" / "actors" / f"{aid}_{actor['slug']}" / "anchor" / stamp
        payload = {"num_images": candidates} if uses_aspect else {"num_images": candidates, "image_size": size}
        jobs.append(Job("anchor", aid, composer.actor_reference(aid, "REF_ANCHOR"), key, candidates, out, payload,
                        price_usd=portrait_price))
    return jobs


def plan_anchor_edit(lib: Library, actor_id: str, instruction: str, candidates: int = 3,
                     model_key: str = "image_edit_identity", source_path: str | None = None) -> list[Job]:
    """Re-design one feature of an actor (hair, grooming, eyebrows …) on top of the approved anchor with FLUX Kontext:
    the face and everything else are kept. The candidates land in a new anchor batch for review/approval; after the
    new anchor is approved, regenerate the training set and the face model from it."""
    if not instruction.strip():
        raise ValueError("say what to change, e.g. --instruction \"Give him a short regulation black military haircut.\"")
    refuse_locked(lib, [actor_id], "anchor portraits")
    source = Path(source_path) if source_path else anchor_path(lib, actor_id)
    out = actor_dir(lib, actor_id) / "anchor" / batch_id()
    prompt = (f"{instruction.strip()}. Change only what this instruction names. Keep exactly the same person: the same "
              "face, face shape, bone structure, nose, eyes, skin tone and skin marks, age, build, expression, pose, "
              "framing, clothing and background. Photorealistic 35mm film photograph, natural unretouched skin texture, "
              "1970s Egypt, no text or lettering anywhere.")
    return [Job("anchor", actor_id, prompt, model_key, candidates, out,
                {"num_images": candidates, "image_path": str(source)})]


# ---- actor face models (LoRA) ---------------------------------------------------------
def actor_dir(lib: Library, actor_id: str) -> Path:
    return media_root() / "library" / "actors" / f"{actor_id}_{lib.actors[actor_id]['slug']}"


def anchor_path(lib: Library, actor_id: str) -> Path:
    anchor = lib.actors[actor_id].get("anchor") or {}
    if not anchor.get("media_path"):
        raise FileNotFoundError(f"{actor_id} has no approved anchor yet — generate and approve one first.")
    path = media_root() / anchor["media_path"]
    if not path.exists():
        raise FileNotFoundError(f"Approved anchor for {actor_id} not found at {path}")
    return path


def lora_weight(actor: dict) -> dict | None:
    """The fal 'loras' entry for an actor with a trained face model, or None."""
    lora = actor.get("lora") or {}
    if actor.get("status") not in ("lora_trained", "locked") or not lora.get("url"):
        return None
    weight = {"path": lora["url"], "scale": lora.get("scale", engine_config().get("training", {}).get("lora_scale", 1.0))}
    if lora.get("media_path"):
        weight["_local"] = lora["media_path"]
    return weight


def training_recipe() -> dict:
    return load_json(LIBRARY_DIR / "actors" / "training_set.json")


def lora_trigger(actor: dict) -> str:
    """The actor's face-model trigger word; refuses to train or caption without one (else captions read 'photo of None')."""
    trigger = (actor.get("lora") or {}).get("trigger")
    if not trigger:
        raise ValueError(f"{actor['id']} has no lora.trigger in actors.json — add one first "
                         f"(e.g. 'act{actor['id'][-4:]}{actor['slug'].split('-')[0]}').")
    return trigger


def training_text(actor: dict, variation: dict) -> tuple[str, str]:
    """(edit instruction, caption) for one recipe variation, adapted to the actor."""
    trigger = lora_trigger(actor)
    female = actor.get("gender") == "female"
    covered = str((actor.get("traits") or {}).get("hair", "")).startswith("covered")
    edit = variation.get("edit_female") if female and variation.get("edit_female") else variation["edit"]
    caption = variation.get("caption_female") if female and variation.get("caption_female") else variation["caption"]
    new_outfit = variation.get("outfit_female") if female and variation.get("outfit_female") else variation.get("outfit")
    # Kontext tends to drop a headscarf when told to change clothes; the face then drifts too
    keep_scarf = ", still wearing a headscarf that fully covers the hair" if covered and "headscarf" not in edit else ""
    if new_outfit:
        return f"{edit}, now wearing {new_outfit} instead of the original clothes{keep_scarf}", \
            f"photo of {trigger}, {caption}, wearing {new_outfit}" + (" and a headscarf" if keep_scarf else "")
    outfit = (actor.get("anchor") or {}).get("outfit")
    if outfit and not variation.get("changes_outfit"):
        caption = f"{caption}, wearing {outfit}"
    return edit + keep_scarf, f"photo of {trigger}, {caption}"


def plan_training_set(lib: Library, actor_ids: list[str], keys: list[str] | None = None,
                      model_key: str = "image_edit") -> list[Job]:
    """One reference edit of the approved anchor per recipe variation (new angle, light, expression, outfit).
    model_key: 'image_edit' (FLUX Kontext, cheap) or 'image_edit_identity' (Nano Banana Pro: re-roll drifted keys)."""
    refuse_locked(lib, actor_ids, "training images")
    recipe, stamp, jobs = training_recipe(), batch_id(), []
    child = recipe.get("child_safe") or {}
    for aid in actor_ids:
        anchor = anchor_path(lib, aid)
        out = actor_dir(lib, aid) / "training_set" / stamp
        is_child = (lib.actors[aid].get("apparent_age") or 99) < child.get("age_below", 0)
        for v in recipe["variations"]:
            if keys and v["key"] not in keys:
                continue
            if is_child and v["key"] in child.get("skip_keys", []):
                continue
            edit, caption = training_text(lib.actors[aid], v)
            jobs.append(Job("training_set", f"{aid}:{v['key']}", f"{edit}. {recipe['identity_lock']}", model_key, 1,
                            out, {"num_images": 1, "image_path": str(anchor), "_caption": caption}))
    return jobs


def training_images(lib: Library, actor_id: str) -> list[Path]:
    """Every kept training image (all batches, minus those marked rejected in the review gallery)."""
    root = actor_dir(lib, actor_id) / "training_set"
    kept = []
    for batch in sorted(p for p in root.glob("*") if p.is_dir()):
        rejected = set(load_json(batch / "rejected.json").get("files", [])) if (batch / "rejected.json").exists() else set()
        kept += [p for p in sorted(batch.glob("*.png")) if p.name not in rejected]
    return kept


def variation_key(path: Path) -> str:
    """'act-0003-soaking-wet_01.png' -> 'soaking-wet'."""
    return re.sub(r"^act-\d{4}-", "", path.stem).rsplit("_", 1)[0]


def check_training_set(lib: Library, actor_id: str) -> list[str]:
    """Problems that would make a face model learn the wrong things. Empty list = ready to train."""
    gate = training_recipe().get("gate", {})
    images = training_images(lib, actor_id)
    outfit = ((lib.actors[actor_id].get("anchor") or {}).get("outfit") or "").lower()
    problems = []
    if len(images) < gate.get("min_kept", 10):
        problems.append(f"only {len(images)} kept training images (need {gate.get('min_kept', 10)})")
    trigger = ((lib.actors[actor_id].get("lora") or {}).get("trigger") or "").lower()
    wrong = [p.name for p in images if p.with_suffix(".txt").exists()
             and not p.with_suffix(".txt").read_text(encoding="utf-8").lower().startswith(f"photo of {trigger},")]
    if trigger and wrong:
        problems.append(f"{len(wrong)} captions don't start with 'photo of {trigger},' (e.g. {wrong[0]}) — "
                        "the face model would learn the wrong trigger word")
    if images and outfit:
        captions = [p.with_suffix(".txt").read_text(encoding="utf-8").lower() if p.with_suffix(".txt").exists() else ""
                    for p in images]
        changed = sum(1 for c in captions if outfit not in c)
        share = changed / len(images)
        if share < gate.get("min_outfit_changed_share", 0):
            problems.append(f"only {changed} of {len(images)} kept images change the outfit ({share:.0%}; need "
                            f"{gate['min_outfit_changed_share']:.0%}) — the anchor clothes would become part of the face")
    actions = {variation_key(p) for p in images} & set(gate.get("action_keys", []))
    if len(actions) < gate.get("min_action_poses", 0):
        problems.append(f"only {len(actions)} action poses kept ({', '.join(sorted(actions)) or 'none'}; need "
                        f"{gate['min_action_poses']}) — shots would drift toward posed portraits")
    return problems


def plan_lora(lib: Library, actor_ids: list[str], steps: int, allow_weak_set: bool = False) -> list[Job]:
    refuse_locked(lib, actor_ids, "face model training")
    stamp, jobs = batch_id(), []
    for aid in actor_ids:
        actor = lib.actors[aid]
        images = training_images(lib, aid)
        problems = check_training_set(lib, aid)
        if problems and not allow_weak_set:
            raise ValueError(f"{aid} training set is not ready: " + "; ".join(problems) +
                             f". Fix it with 'generate training-set {aid} --only <keys>' and the review gallery"
                             " (or pass --allow-weak-set).")
        files = [str(p) for p in images]
        captions = {}
        trigger = lora_trigger(actor)
        if (actor.get("anchor") or {}).get("use_in_training", True):
            anchor = str(anchor_path(lib, aid))
            files.append(anchor)
            captions[anchor] = (f"photo of {trigger}, head-and-shoulders portrait, facing the camera, plain neutral background"
                                + (f", wearing {actor['anchor']['outfit']}" if actor["anchor"].get("outfit") else ""))
        out = actor_dir(lib, aid) / "lora" / stamp
        jobs.append(Job("lora", aid, f"face LoRA '{trigger}' from {len(files)} images, {steps} steps", "lora_training",
                        steps / 1000, out, {"trigger_word": trigger, "steps": steps, "_files": files, "_captions": captions}))
    return jobs


# ---- prop models (LoRA) -----------------------------------------------------------------
REFERENCE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def prop_dir(lib: Library, prop_id: str) -> Path:
    return media_root() / "library" / "props" / f"{prop_id}_{lib.props[prop_id]['slug']}"


def prop_references(lib: Library, prop_id: str) -> list[Path]:
    """Real photos of the prop (supplied by the team) in references/ — the ground truth for its shape and size."""
    folder = prop_dir(lib, prop_id) / "references"
    return sorted(p for p in folder.glob("*") if p.suffix.lower() in REFERENCE_SUFFIXES) if folder.exists() else []


def shot_references(lib: Library, shot: dict) -> list[Path]:
    """Reference photos of the shot's props (the real weapons), limited to each prop's train_references if set."""
    refs = []
    for asset in shot.get("assets") or []:
        m = re.search(r"PRP-\d{4}", asset)
        if not m or m.group(0) not in lib.props:
            continue
        keep = lib.props[m.group(0)].get("train_references")
        refs += [p for p in prop_references(lib, m.group(0)) if not keep or p.name in keep]
    return refs


INSIGNIA_DIR = LIBRARY_DIR / "wardrobe" / "insignia"


def rank_references(prod: Production, char_ids: list[str]) -> list[tuple[str, Path]]:
    """Official drawings of the rank insignia worn by the shot's cast (casting.json 'rank_reference'), as (role, path)."""
    cast, refs = prod.casting["cast"], []
    for c in char_ids:
        name = cast.get(c, {}).get("rank_reference")
        path = INSIGNIA_DIR / name if name else None
        if path and path.exists() and path not in [p for _, p in refs]:
            refs.append((re.sub(r"\s*\([^)]*\)", "", cast[c].get("role") or cast[c].get("character") or c), path))
    return refs


def prop_recipe() -> dict:
    return load_json(LIBRARY_DIR / "props" / "training_set.json")


def plan_prop_training_set(lib: Library, prop_ids: list[str], keys: list[str] | None = None) -> list[Job]:
    """Kontext edits of the prop's reference photos: new light, ground, angle, and a soldier for scale."""
    recipe, stamp, jobs = prop_recipe(), batch_id(), []
    for pid in prop_ids:
        prop = lib.props[pid]
        trigger = (prop.get("lora") or {}).get("trigger")
        if not trigger:
            raise ValueError(f"{pid} has no lora.trigger in props.json — add one (e.g. 'prp{pid[-4:]}{prop['slug'].split('-')[0]}').")
        refs = prop_references(lib, pid)
        if len(refs) < recipe["gate"].get("min_references", 1):
            raise FileNotFoundError(f"{pid} has no reference photos — put real photos in {prop_dir(lib, pid) / 'references'}")
        name = prop["name"]
        out = prop_dir(lib, pid) / "training_set" / stamp
        variations = recipe["variations"] + prop.get("training_actions", [])
        for n, v in enumerate(variations):
            if keys and v["key"] not in keys:
                continue
            ref = refs[n % len(refs)]
            edit = v["edit"].replace("{NAME}", name)
            lock = recipe["identity_lock"].replace("{NAME}", name)
            if prop.get("training_note"):
                lock += " " + prop["training_note"]
            jobs.append(Job("training_set", f"{pid}:{v['key']}", f"{edit}. {lock}", "image_edit", 1, out,
                            {"num_images": 1, "image_path": str(ref), "aspect_ratio": recipe.get("aspect_ratio", "4:3"),
                             "_caption": f"photo of {trigger}, {name}, {v['caption']}"}))
    return jobs


def prop_training_images(lib: Library, prop_id: str) -> list[Path]:
    root = prop_dir(lib, prop_id) / "training_set"
    kept = []
    for batch in sorted(p for p in root.glob("*") if p.is_dir()):
        rejected = set(load_json(batch / "rejected.json").get("files", [])) if (batch / "rejected.json").exists() else set()
        kept += [p for p in sorted(batch.glob("*.png")) if p.name not in rejected]
    return kept


def plan_prop_lora(lib: Library, prop_ids: list[str], steps: int, allow_weak_set: bool = False) -> list[Job]:
    """Train a prop model from the kept training images plus the reference photos themselves."""
    stamp, jobs = batch_id(), []
    min_kept = prop_recipe()["gate"].get("min_kept", 10)
    for pid in prop_ids:
        prop = lib.props[pid]
        trigger = prop["lora"]["trigger"]
        images = prop_training_images(lib, pid)
        if len(images) < min_kept and not allow_weak_set:
            raise ValueError(f"{pid} training set is not ready: only {len(images)} kept images (need {min_kept}).")
        files = [str(p) for p in images]
        captions = {}
        for ref in prop_references(lib, pid):
            if prop.get("train_references") and ref.name not in prop["train_references"]:
                continue  # e.g. a photo that shows the right size but the wrong paint scheme
            files.append(str(ref))
            captions[str(ref)] = f"photo of {trigger}, {prop['name']}, reference photograph"
        out = prop_dir(lib, pid) / "lora" / stamp
        jobs.append(Job("lora", pid, f"prop LoRA '{trigger}' from {len(files)} images, {steps} steps", "lora_training",
                        steps / 1000, out, {"trigger_word": trigger, "steps": steps, "create_masks": False,
                                            "_files": files, "_captions": captions}))
    return jobs


def actor_solo_shots(lib: Library, prod: Production, actor_id: str, count: int = 3) -> list[tuple[str, str]]:
    """(part, shot_id) of shots where only this actor's character appears, spread across the episode."""
    composer = PromptComposer(lib, prod)
    chars = {cid for cid, c in prod.casting["cast"].items() if c.get("actor") == actor_id}
    solo = []
    for sl, beat, shot in prod.all_shots():
        if (shot.get("model") or shot.get("video_model")) == "none" or "CARD" in (shot.get("size"), shot.get("shot_size")):
            continue
        if shot.get("size") == "INSERT":
            continue
        found = composer.shot(beat, shot).characters
        if len(found) == 1 and found[0] in chars:
            solo.append((sl["part"], shot["shot_id"]))
    if len(solo) <= count:
        return solo
    step = (len(solo) - 1) / (count - 1)
    return [solo[round(i * step)] for i in range(count)]


def plan_lora_tests(lib: Library, prod: Production, actor_ids: list[str]) -> list[Job]:
    """Test a trained face model on real shots from the production (they double as keyframes: no throwaway images).
    Falls back to 4 studio test portraits for actors with no solo shot in this production."""
    composer, stamp, jobs = PromptComposer(lib, prod), batch_id(), []
    size = engine_config().get("training", {}).get("test_image_size", "portrait_4_3")
    for aid in actor_ids:
        weight = lora_weight(lib.actors[aid])
        if not weight:
            raise ValueError(f"{aid} has no trained face model yet — run 'generate lora {aid}' first.")
        shots = actor_solo_shots(lib, prod, aid)
        if shots:
            for part, shot_id in shots:
                jobs += plan_keyframes(lib, prod, part, [shot_id], "draft", 1)
            continue
        trigger = lib.actors[aid]["lora"]["trigger"]
        out = actor_dir(lib, aid) / "lora_tests" / stamp
        for variation in ("REF_THREE_QUARTER_DAY", "REF_PROFILE", "REF_NIGHT", "REF_EXPRESSION"):
            prompt = f"photo of {trigger}, " + composer.actor_reference(aid, variation)
            jobs.append(Job("lora_test", f"{aid}:{variation.lower()}", prompt, "image_lora", 1, out,
                            {"num_images": 1, "image_size": size, "loras": [weight]}))
    return jobs


def _training_zip(files: list[str], extra_captions: dict | None = None) -> bytes:
    """Images plus captions (same-name .txt files, or extra_captions by path), as a zip archive for the trainer."""
    import io
    import zipfile

    extra_captions = extra_captions or {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for n, f in enumerate(files, 1):
            path = Path(f)
            stem = f"{n:03d}"
            zf.write(path, f"{stem}{path.suffix.lower()}")
            caption_file = path.with_suffix(".txt")
            caption = extra_captions.get(f) or (caption_file.read_text(encoding="utf-8").strip() if caption_file.exists() else "")
            if caption:
                zf.writestr(f"{stem}.txt", caption)
    return buf.getvalue()


def plan_plates(lib: Library, prod: Production, asset_ids: list[str], tier: str, variants: int) -> list[Job]:
    composer = PromptComposer(lib, prod)
    jobs, stamp = [], batch_id()
    for aid in asset_ids:
        item = lib.asset(aid)
        if not item:
            raise KeyError(f"Unknown asset {aid}")
        looks = item.get("light_variants") or [None]
        looks = [k for k in looks if k is None or k.startswith("LOOK_")] or [None]
        catalog = {"LOC": "locations", "VEH": "vehicles", "PRP": "props", "WRD": "wardrobe"}[aid[:3]]
        for look in looks:
            out = media_root() / "library" / catalog / f"{aid}_{item['slug']}" / "plates" / (look or "neutral") / stamp
            jobs.append(Job("plate", f"{aid}:{look or 'neutral'}", composer.asset_reference(aid, look), _image_model(tier, False),
                            variants, out, {"num_images": variants}))
    return jobs


def prop_weights(lib: Library, shot: dict) -> list[dict]:
    """Trained prop models (LoRAs) for the props listed in a shot's assets."""
    weights = []
    for raw in shot.get("assets") or []:
        match = re.search(r"PRP-\d{4}", raw)
        item = lib.props.get(match.group(0)) if match else None
        w = lora_weight(item) if item else None
        if w and w not in weights:
            weights.append(w)
    return weights


def is_group_shot(shot: dict) -> bool:
    """A shot with other people besides the cast: face models must not touch their faces."""
    return bool(shot.get("group", bool(shot.get("extras"))))


def face_strategy(shot: dict) -> str:
    """A shot's lead_face if set, else 'vision': the reviewer model matches each character to a detected face from the
    shot design (falls back to the largest faces when it can't)."""
    return shot.get("lead_face") or "vision"


def plan_keyframes(lib: Library, prod: Production, part: str | None, shot_ids: list[str] | None, tier: str, variants: int,
                   lora_scale: float | None = None) -> list[Job]:
    """One job per shot. Group shots with trained actors become two jobs: the picture without face models
    (so extras keep their own faces), then a face pass that repaints only the leads' faces."""
    composer = PromptComposer(lib, prod)
    jobs, stamp = [], batch_id()
    for sl, beat, shot in prod.all_shots(part):
        if shot_ids and shot["shot_id"] not in shot_ids:
            continue
        model_tier = shot.get("model") or shot.get("video_model") or "default"
        if model_tier == "none" or shot.get("size") == "CARD" or shot.get("shot_size") == "CARD":
            continue
        composed = composer.shot(beat, shot)
        cast = prod.casting["cast"]
        actors = [(c, w) for c in composed.characters if c in cast
                  for w in [lora_weight(lib.actors[cast[c]["actor"]])] if w]
        if lora_scale is not None:
            actors = [(c, {**w, "scale": lora_scale}) for c, w in actors]
        props = prop_weights(lib, shot)
        out = media_root() / "productions" / prod.key / "keyframes" / sl["part"] / shot["shot_id"] / stamp
        if actors and is_group_shot(shot):
            base = composer.shot(beat, shot, use_lora=False, faces=False)
            payload = {"num_images": variants, **({"loras": props} if props else {})}
            jobs.append(Job("keyframe", shot["shot_id"], base.image_prompt, _image_model(tier, bool(props)), variants, out,
                            payload, base.negative_prompt))
            jobs.append(_face_job(lib, prod, composer, beat, shot, out, variants, actors, None))
            continue
        weights = [w for _, w in actors] + props
        payload = {"num_images": variants, **({"loras": weights} if weights else {})}
        jobs.append(Job("keyframe", shot["shot_id"], composed.image_prompt, _image_model(tier, bool(weights)), variants, out,
                        payload, composed.negative_prompt))
    return jobs


# ---- images made outside the engine (e.g. ChatGPT) --------------------------------------
SHOT_FILE = re.compile(r"^(T\.\d+-\d+|\d+\.\d+-\d+)")


def inbox_dir() -> Path:
    return media_root() / "inbox"


def inbox_files(shot_ids: list[str] | None = None) -> dict[str, list[Path]]:
    """Inbox images grouped by the shot ID their file name starts with (e.g. 'T.2-01.png', '2.6-02 v2.png')."""
    found: dict[str, list[Path]] = {}
    folder = inbox_dir()
    for f in sorted(folder.glob("*")) if folder.exists() else []:
        m = SHOT_FILE.match(f.name)
        if f.is_file() and m and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp") and (not shot_ids or m.group(1) in shot_ids):
            found.setdefault(m.group(1), []).append(f)
    return found


def fit_image(src: Path, dest: Path, width: int = 1280, height: int = 720) -> str:
    """Center-crop and resize to the keyframe size (Windows: System.Drawing via tools/Fit-Image.ps1)."""
    import subprocess

    script = Path(__file__).resolve().parent.parent / "tools" / "Fit-Image.ps1"
    done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-In", str(src),
                           "-Out", str(dest), "-Width", str(width), "-Height", str(height)], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=120)
    if done.returncode != 0:
        raise RuntimeError(f"Could not convert {src.name}: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout.strip()


def import_keyframes(prod: Production, shot_id: str, files: list[Path], source: str = "chatgpt") -> Path:
    """Copy outside images into a new keyframe batch (1280x720), keep the originals, empty them from the inbox. Free."""
    import shutil

    sl, _, _ = prod.find_shot(shot_id)
    out = media_root() / "productions" / prod.key / "keyframes" / sl["part"] / shot_id / batch_id()
    (out / "original").mkdir(parents=True, exist_ok=True)
    names = []
    for n, f in enumerate(files, 1):
        name = f"{_slug(shot_id)}_{n:02d}.png"
        print(f"  {f.name} -> {name}: {fit_image(f, out / name)}")
        shutil.move(str(f), out / "original" / f.name)
        names.append(name)
    _merge_manifest(out, {"kind": "keyframe", "target": shot_id, "model_key": "imported", "model_id": f"{source} (manual)",
                          "prompt": "", "negative_prompt": ""},
                    {"target": shot_id, "prompt": f"imported from {source}", "files": names, "seeds": [], "request_ids": [],
                     "cost_usd_estimate": 0.0, "originals": [f.name for f in files]})
    return out


def face_pass_model(composer: PromptComposer, shot: dict) -> str:
    """Which face pass a shot gets: the Azure face swap (default) or the fal LoRA inpaint (children — gpt-image refuses
    minors — or a shot with face_method 'fal')."""
    method = shot.get("face_method") or engine_config().get("face_pass", {}).get("method", "azure")
    return "image_inpaint" if method == "fal" or composer.has_child(shot) else "face_swap"


def _face_job(lib: Library, prod: Production, composer: PromptComposer, beat: dict, shot: dict, out: Path, images: int,
              actors: list[tuple[str, dict]], strategy: str | None) -> Job:
    key = face_pass_model(composer, shot)
    cast = prod.casting["cast"]
    if key == "face_swap":
        chars = [{"char": c, "anchor": str(media_root() / (lib.actors[cast[c]["actor"]].get("anchor") or {}).get("media_path", "")),
                  "prompt": composer.face_swap_prompt(beat, shot, c)} for c, _ in actors]
        check = costs.model(key).get("check", {}).get("enabled")
        extra = [("face_detect", images * (2 if check else 1))]  # ceiling: detect before, check after
    else:
        chars = [{"char": c, "lora": w, "prompt": composer.face_pass_prompt(beat, shot, c)} for c, w in actors]
        extra = [("face_detect", images), ("face_detect_fallback", images)]  # ceiling: detector + fallback
    who = {"shot": composer.shot_design_text(beat, shot),
           "chars": [{"char": c, "role": composer.role_brief(c)} for c, _ in actors]}
    return Job("face_pass", f"{shot['shot_id']}:faces", " | ".join(x["prompt"] for x in chars), key,
               images * len(chars), out,
               {"_chars": chars, "_who": who, "_stem": _slug(shot["shot_id"]), "_strategy": strategy or face_strategy(shot),
                **({"_strength": shot["face_strength"]} if shot.get("face_strength") and key == "image_inpaint" else {})},
               extra=extra)


def _face_pass_job(lib: Library, prod: Production, composer: PromptComposer, beat: dict, shot: dict, out: Path,
                   images: int, strategy: str | None = None) -> Job | None:
    """Face pass over `images` pictures in `out` (they may not exist yet: a chained job finds them at run time).
    The fal LoRA inpaint needs the actor's face model; the Azure face swap only needs the approved casting portrait."""
    cast = prod.casting["cast"]
    swap = face_pass_model(composer, shot) == "face_swap"
    actors = []
    for c in composer.shot(beat, shot).characters:
        if c not in cast:
            continue
        actor = lib.actors[cast[c]["actor"]]
        w = lora_weight(actor)
        if w or (swap and (actor.get("anchor") or {}).get("media_path")):
            actors.append((c, w))
    if not actors or not images:
        return None
    return _face_job(lib, prod, composer, beat, shot, out, images, actors, strategy)


def plan_face_pass(lib: Library, prod: Production, shot_ids: list[str], strategy: str | None = None) -> list[Job]:
    """Repaint the cast's faces (with their face models) on the latest keyframe batch of each shot — e.g. an imported image."""
    composer, jobs = PromptComposer(lib, prod), []
    for shot_id in shot_ids:
        sl, beat, shot = prod.find_shot(shot_id)
        root = media_root() / "productions" / prod.key / "keyframes" / sl["part"] / shot_id
        batches = sorted(p for p in root.glob("*") if p.is_dir() and any(p.glob(f"{_slug(shot_id)}_*.png"))) if root.exists() else []
        if not batches:
            raise FileNotFoundError(f"No keyframes for {shot_id} yet — import or generate one first.")
        out = batches[-1]
        job = _face_pass_job(lib, prod, composer, beat, shot, out, len(sorted(out.glob(f"{_slug(shot_id)}_*.png"))), strategy)
        if job:
            jobs.append(job)
    return jobs


COMPOSE_REFERENCE_NOTE = ("Use the attached photos only as the exact reference for the weapons' and props' shape, size, "
                          "and colour; do not copy their backgrounds, framing, or any people in them.")
COMPOSE_ACTOR_NOTE = ("The first attached photo is a casting portrait of the lead ({who}): he must be clearly the same person, "
                      "with the same face and facial features, but with the hair, uniform, pose, expression and lighting "
                      "described here; ignore the portrait's clothing and background.")
COMPOSE_RANK_NOTE = ("Rank insignia: {who}. Those attached drawings are the official shoulder-strap insignia: reproduce "
                     "them exactly (same devices, same count, gold metal) but small, on the real khaki shoulder straps of "
                     "the uniform, at true scale for the framing; do not copy the drawing's flat colours or put it anywhere else.")


def _ordinal(n: int) -> str:
    return ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"][min(n, 8) - 1]


FLUX_ACTOR_NOTE = ("Show the child from this casting photo, with exactly the same face, as a still from a film; change the "
                   "clothes, hair, pose, expression, setting and light to those described here.")


def _child_anchor(lib: Library, prod: Production, composer: PromptComposer, beat: dict, shot: dict) -> Path | None:
    """The approved casting photo of a child shot's only lead, for FLUX Kontext to keep the face (else None: face pass)."""
    cast = prod.casting["cast"]
    leads = [c for c in composer.shot(beat, shot).characters if c in cast]
    if len(leads) != 1:
        return None
    try:
        path = anchor_path(lib, cast[leads[0]]["actor"])
    except (FileNotFoundError, KeyError, ValueError):
        return None
    return path if path.exists() else None


def plan_compositions(lib: Library, prod: Production, shot_ids: list[str], variants: int = 1, quality: str | None = None,
                      strategy: str | None = None, face_pass: bool = True, actor_refs: bool = False,
                      notes: dict[str, str] | None = None, crew: dict[str, str] | None = None) -> list[Job]:
    """Hard compositions on Azure (gpt-image): the same body-only prompt as the ChatGPT route plus the props' reference
    photos, saved as a new 1280x720 keyframe batch; then (by default) the face pass puts the cast's faces on the leads.

    actor_refs: also attach the lead's approved anchor portrait so gpt-image draws his face directly (no face pass).
    notes: per shot, corrections to add to the prompt (e.g. the QA reviewer's fixes for the last render).
    crew: per shot, the studio crew's production design (wardrobe, makeup, set, camera, action, lessons) for the prompt.
    Child shots go to FLUX.1 Kontext instead (gpt-image refuses children): short prompt, the child's casting photo as input."""
    m = costs.model("image_compose")
    quality = quality or m["payload"].get("quality", "medium")
    prices = m.get("quality_prices_usd", {})
    if quality not in prices:
        raise ValueError(f"Unknown quality '{quality}'. Use one of: {', '.join(prices)}")
    composer, jobs, stamp = PromptComposer(lib, prod), [], batch_id()
    for shot_id in shot_ids:
        sl, beat, shot = prod.find_shot(shot_id)
        child = composer.has_child(shot)
        # Azure gpt-image (and FLUX.2-pro) refuse every photorealistic child (tested 2026-10-12); FLUX.1 Kontext pro doesn't
        refs = [] if child else shot_references(lib, shot)
        note = COMPOSE_REFERENCE_NOTE if refs else ""
        prompt = composer.flux_prompt(beat, shot) if child else composer.chatgpt_prompt(beat, shot)
        child_anchor = _child_anchor(lib, prod, composer, beat, shot) if child else None
        shot_face_pass = face_pass  # per shot: one child shot must not switch the face pass off for the rest
        if child_anchor:  # Kontext keeps the casting photo's face: no face pass needed
            prompt = FLUX_ACTOR_NOTE + " " + prompt
            shot_face_pass = False
        if actor_refs and not child:
            cast = prod.casting["cast"]
            leads = [c for c in composer.shot(beat, shot).characters if c in cast]
            if len(leads) != 1:
                raise ValueError(f"{shot_id}: actor references support exactly one lead (found {len(leads)})")
            refs = [anchor_path(lib, cast[leads[0]]["actor"])] + refs
            prompt += " " + COMPOSE_ACTOR_NOTE.format(who=cast[leads[0]].get("role") or "the lead")
            note = note.replace("Use the attached photos", "Use the other attached photos")
            shot_face_pass = False
        prompt += (" " + note) if note else ""
        ranks = [] if child or composer.is_insert(shot) else rank_references(prod, composer.shot(beat, shot).characters)
        if ranks:
            refs = refs + [p for _, p in ranks]
            prompt += " " + COMPOSE_RANK_NOTE.format(who="; ".join(
                f"{r} wears the insignia in the {_ordinal(len(refs) - len(ranks) + i)} attached image" for i, (r, _) in enumerate(ranks, 1)))
        if crew and crew.get(shot_id):
            prompt += " Production design from the crew (follow it): " + crew[shot_id].strip()
        if notes and notes.get(shot_id):
            prompt += " Corrections from the last review (make sure of these): " + notes[shot_id].strip()
        out = media_root() / "productions" / prod.key / "keyframes" / sl["part"] / shot_id / stamp
        if child:
            internal = {"_references": [], "_quality": "flux", "_stem": _slug(shot_id)}
            if child_anchor:
                internal.update({"_quality": "flux + casting photo", "_input_image": str(child_anchor)})
            jobs.append(Job("composition", shot_id, prompt, "image_compose_flux", variants, out, internal))
        else:
            jobs.append(Job("composition", shot_id, prompt, "image_compose", variants, out,
                            {"_references": [str(r) for r in refs], "_quality": quality, "_stem": _slug(shot_id)},
                            extra=[("usd", round(len(refs) * m.get("reference_price_usd", 0) * variants, 4))] if refs else [],
                            price_usd=prices[quality]))
        if shot_face_pass and shot.get("face_pass", True) and not composer.is_insert(shot):
            job = _face_pass_job(lib, prod, composer, beat, shot, out, variants, strategy)
            if job:
                jobs.append(job)
    return jobs


def plan_edit(prod: Production, shot_id: str, instruction: str, source: Path | None = None) -> list[Job]:
    """Fix one detail of a keyframe with FLUX.1 Kontext ("replace the cross on the wall with a calendar"): it redraws
    the picture from the instruction and keeps the rest — faces included — so no face pass follows.
    source: the image to edit (default: the shot's approved keyframe, else its newest one)."""
    if not instruction.strip():
        raise ValueError("say what to change, e.g. --instruction \"Remove the cross from the wall. Keep everything else the same.\"")
    sl, _, _ = prod.find_shot(shot_id)
    source = source or approved_keyframe(prod, sl["part"], shot_id) or latest_keyframe(prod, sl["part"], shot_id)
    if not source or not Path(source).exists():
        raise FileNotFoundError(f"No keyframe to edit for {shot_id} — generate one first, or pass --source.")
    out = media_root() / "productions" / prod.key / "keyframes" / sl["part"] / shot_id / batch_id()
    return [Job("composition", shot_id, instruction.strip(), "image_compose_flux", 1, out,
                {"_references": [], "_quality": "flux edit", "_stem": _slug(shot_id), "_input_image": str(source), "_edit": True})]


def latest_keyframe(prod: Production, part: str, shot_id: str) -> Path | None:
    shot_dir = media_root() / "productions" / prod.key / "keyframes" / part / shot_id
    for batch in sorted((d for d in shot_dir.glob("*") if d.is_dir()), reverse=True):
        pngs = sorted(batch.glob("*.png"))
        if pngs:
            return pngs[0]
    return None


def approved_keyframe(prod: Production, part: str, shot_id: str) -> Path | None:
    shot_dir = media_root() / "productions" / prod.key / "keyframes" / part / shot_id
    for approval in sorted(shot_dir.glob("*/approved.json"), reverse=True):
        return approval.parent / load_json(approval)["file"]
    return None


def clip_duration(m: dict, wanted_s: float) -> int:
    """The shortest duration the model offers that covers the shot, else its longest (trim or extend in the edit)."""
    allowed = sorted(m.get("durations") or [5, 10])
    return next((d for d in allowed if d >= wanted_s), allowed[-1])


def plan_clips(lib: Library, prod: Production, part: str | None, shot_ids: list[str] | None,
               model_keys: list[str] | None = None) -> list[Job]:
    """Animate approved keyframes. model_keys (e.g. a bake-off of several video models) overrides the shot's tier;
    each model gets its own batch folder so takes sit side by side."""
    composer = PromptComposer(lib, prod)
    jobs, stamp = [], batch_id()
    for sl, beat, shot in prod.all_shots(part):
        if shot_ids and shot["shot_id"] not in shot_ids:
            continue
        composed = composer.shot(beat, shot)
        if composed.model_tier == "none":
            continue
        keyframe = approved_keyframe(prod, sl["part"], shot["shot_id"])
        if not keyframe:
            raise FileNotFoundError(f"No approved keyframe for {shot['shot_id']} — approve one with the review gallery first.")
        keys = model_keys or ["video_premium" if composed.model_tier == "premium" else "video_default"]
        scene = shot.get("prompt") or shot.get("image_prompt_core") or ""
        prompt = f"{scene}. {composed.motion_prompt}" if scene else composed.motion_prompt
        end_frame = None
        if shot.get("flow_to"):  # one unbroken camera move that lands on the next shot's first picture
            nxt = prod.find_shot(shot["flow_to"])[0]
            end_frame = approved_keyframe(prod, nxt["part"], shot["flow_to"])
            if not end_frame:
                raise FileNotFoundError(f"{shot['shot_id']} flows into {shot['flow_to']}, which has no approved keyframe yet.")
            move = shot.get("flow_motion") or composed.motion_prompt
            prompt = (f"{scene}. {move} One continuous unbroken take: the camera physically travels and the shot ends "
                      f"exactly on the final frame given.") if scene else move
        for key in keys:
            m = costs.model(key)
            if m.get("unit") != "second":
                raise ValueError(f"'{key}' is not a video model")
            if end_frame and not m.get("end_image_field"):
                raise ValueError(f"{shot['shot_id']} flows into {shot['flow_to']}, but '{key}' cannot take an end frame — "
                                 "use a model with end_image_field (video_default).")
            seconds = clip_duration(m, composed.duration_s)
            out = media_root() / "productions" / prod.key / "clips" / sl["part"] / shot["shot_id"] / (
                f"{stamp}-{key}" if len(keys) > 1 or model_keys else stamp + ("-flow" if end_frame else ""))
            payload = {"duration": m.get("duration_format", "{s}").format(s=seconds), "image_path": str(keyframe)}
            if end_frame:
                payload["end_image_path"] = str(end_frame)
            jobs.append(Job("clip", shot["shot_id"], prompt, key, seconds, out, payload,
                            composed.negative_prompt if m.get("negative_prompt", True) else ""))
    return jobs


# ---- estimate / run -----------------------------------------------------------------
def estimates(jobs: list[Job]) -> list[costs.Estimate]:
    return [costs.estimate(j.model_key, j.units, j.extra, j.price_usd) for j in jobs]


def _merge_manifest(out_dir: Path, entry: dict, item: dict) -> None:
    """One manifest per batch folder; several jobs (e.g. training-set variations) may share a folder."""
    path = out_dir / "manifest.json"
    manifest = load_json(path) if path.exists() else {**entry, "files": [], "items": [], "cost_usd_estimate": 0.0}
    manifest["files"] += item["files"]
    manifest["items"].append(item)
    manifest["seeds"] = manifest.get("seeds", []) + item["seeds"]
    manifest["request_ids"] = manifest.get("request_ids", []) + item["request_ids"]
    manifest["cost_usd_estimate"] = round(manifest["cost_usd_estimate"] + item["cost_usd_estimate"], 4)
    write_json(path, manifest)


def _resolve_loras(client, loras: list[dict]) -> list[dict]:
    """Use each face model's stored URL; if it has expired, re-upload the local copy."""
    from .providers.fal import reachable

    resolved = []
    for w in loras:
        local = w.get("_local")
        path = w["path"]
        if local and not reachable(path):
            path = client.upload_file(media_root() / local)
        resolved.append({"path": path, "scale": w.get("scale", 1.0)})
    return resolved


def _finish_lora(job: Job, result: dict, lib_actor_id: str) -> list[str]:
    from .providers.fal import download

    lora_url = result["diffusers_lora_file"]["url"]
    trigger = job.payload["trigger_word"]
    weights = download(lora_url, job.out_dir / f"{trigger}.safetensors")
    files = [weights.name]
    if result.get("config_file"):
        files.append(download(result["config_file"]["url"], job.out_dir / "training_config.json").name)
    update = update_prop if lib_actor_id.startswith("PRP-") else update_actor
    update(lib_actor_id, {
        "status": "lora_trained",
        "lora": {"base_model": "FLUX.1 [dev] (fal-ai/flux-lora)", "version": job.out_dir.name, "url": lora_url,
                 "media_path": weights.relative_to(media_root()).as_posix(), "steps": job.payload["steps"],
                 "training_images": len(job.payload["_files"]), "trained": datetime.now().strftime("%Y-%m-%d")}})
    return files


def _auto_reject(out_dir: Path, name: str) -> None:
    path = out_dir / "rejected.json"
    data = load_json(path) if path.exists() else {"files": []}
    if name not in data["files"]:
        data["files"].append(name)
    write_json(path, data)


def _detect_faces(client, job: Job, base: Path, internal: dict, expiry, tally: dict, fallback: bool = True) -> list[dict] | None:
    """The leads' face boxes in a base image (cached in base/<stem>.faces.json, so a re-run costs nothing), else None."""
    from . import faces

    chars = internal["_chars"]
    cache = base.with_suffix(".faces.json")
    strategy = internal.get("_strategy", "largest")
    if cache.exists():
        saved = load_json(cache)
        if saved.get("characters") == [c["char"] for c in chars] and saved.get("strategy") == strategy \
                and len(saved.get("chosen") or []) >= len(chars):
            return saved["chosen"]
    width, height = faces.image_size(base)
    detect = costs.model("face_detect")
    current = client.upload_file(base, expiry)
    found = client.run(detect["model_id"], {**detect.get("payload", {}), "image_url": current}, detect.get("timeout_seconds"))
    tally["detections"] += 1
    tally["request_ids"].append(found.get("_request_id"))
    boxes = faces.faces_from_detection(found, width, height)
    if fallback and len(boxes) < len(chars):
        fb = costs.model("face_detect_fallback")
        found = client.run(fb["model_id"], {**fb.get("payload", {}), "image_url": current}, fb.get("timeout_seconds"))
        tally["fallbacks"] += 1
        tally["request_ids"].append(found.get("_request_id"))
        boxes = faces.merge_boxes(boxes, faces.faces_from_detection(found, width, height))
    chosen = faces.pick_faces(boxes, width, len(chars), "largest" if strategy == "vision" else strategy)
    if strategy == "vision" and internal.get("_who") and boxes and (len(boxes) > len(chars) or len(chars) > 1):
        from . import qa
        try:
            picks, _ = qa.identify_faces(base, boxes, internal["_who"])  # recorded in the ledger by identify_faces
            chosen = [boxes[n - 1] if n else None for n in picks]
            missing = [c["char"] for c, b in zip(chars, chosen) if b is None]
            if missing:
                print(f"     ! {base.name}: {', '.join(missing)} not found in the picture — that face is left as it is", flush=True)
        except Exception as err:  # noqa: BLE001 — fall back to the largest faces rather than lose the pass
            print(f"     ! {base.name}: face identification failed ({str(err)[:120]}) — using the largest faces", flush=True)
    write_json(cache, {"strategy": strategy, "faces": boxes, "chosen": chosen, "characters": [c["char"] for c in chars]})
    if len(chosen) < len(chars) or all(b is None for b in chosen):
        print(f"     ! {base.name}: found {len(boxes)} face(s) for {len(chars)} character(s) — kept the picture "
              "without the face pass; review it", flush=True)
        return None
    return chosen


def _face_swap(fal, job: Job, model: dict, internal: dict, expiry, tally: dict) -> None:
    """Azure face swap: for each lead, a gpt-image masked edit of the frame with the actor's anchor portrait as image 2.
    The tight mask keeps the head's size and place; the check re-detects the face afterwards and flags any image whose
    face grew, shrank or moved (faces.json 'check'). Counts into tally as it goes."""
    import shutil

    from . import faces
    from .providers.azure import AzureClient, usage_cost

    az = AzureClient()
    payload = model.get("payload", {})
    pads = model.get("mask", {})
    check = model.get("check", {})
    for img in sorted(job.out_dir.glob(f"{internal['_stem']}_*.png")):
        base = job.out_dir / "base" / img.name
        base.parent.mkdir(parents=True, exist_ok=True)
        if not base.exists():
            shutil.copy2(img, base)
        chosen = _detect_faces(fal, job, base, internal, expiry, tally) if fal else None
        if chosen is None and not fal:
            cache = base.with_suffix(".faces.json")
            chosen = load_json(cache).get("chosen") if cache.exists() else None
            if not chosen:
                print(f"     ! {img.name}: no saved face boxes and no fal key for detection — skipped", flush=True)
                continue
        if chosen is None:
            continue
        width, height = faces.image_size(base)
        work = job.out_dir / "base" / f"{img.stem}.work.png"
        shutil.copy2(base, work)
        for char, box in zip(internal["_chars"], chosen):
            if box is None:
                continue
            if not Path(char["anchor"]).is_file():
                raise FileNotFoundError(f"{char['char']}: approved anchor portrait not found at {char['anchor']}")
            mask = job.out_dir / "base" / f"{img.stem}.{char['char']}.mask.png"
            mask.write_bytes(faces.alpha_mask_png(width, height, box, pads.get("pad_w", 1.25), pads.get("pad_h", 1.35)))
            result = az.edit(model["model_id"], char["prompt"], [work, Path(char["anchor"])], mask,
                             payload.get("size", "1280x720"), payload.get("quality", "medium"),
                             payload.get("output_format", "png"), payload.get("input_fidelity"), payload.get("moderation"))
            tally["inpaints"] += 1
            tally["request_ids"].append(result.request_id)
            tally["azure_usd"] += usage_cost(result.usage, model["pricing_per_m_tokens"]) if result.usage else model["price_usd"]
            work.write_bytes(result.images[0])
            if faces.image_size(work) != (width, height):
                raw = work.with_suffix(".raw.png")
                work.replace(raw)
                fit_image(raw, work, width, height)
                raw.unlink(missing_ok=True)
        verdicts = []
        if check.get("enabled") and fal:
            try:
                det = costs.model("face_detect")
                found = fal.run(det["model_id"], {**det.get("payload", {}), "image_url": fal.upload_file(work, expiry)},
                                det.get("timeout_seconds"))
                tally["detections"] += 1
                tally["request_ids"].append(found.get("_request_id"))
                after = faces.faces_from_detection(found, width, height)
                verdicts = [{"char": c["char"], **faces.check_face(b, after, check.get("min_area", 0.65), check.get(
                    "max_area", 1.45), check.get("max_shift", 0.5))} for c, b in zip(internal["_chars"], chosen) if b is not None]
            except Exception as err:  # the check must never lose a paid image
                verdicts = [{"ok": None, "reason": f"check skipped: {str(err)[:120]}"}]
        if verdicts:
            cache = base.with_suffix(".faces.json")
            write_json(cache, {**load_json(cache), "check": verdicts} if cache.exists() else {"check": verdicts})
            for v in verdicts:
                if v.get("ok") is False:
                    print(f"     ! {img.name}: face check failed for {v.get('char')}: {v['reason']} — review it", flush=True)
        shutil.move(work, img)
        tally["files"].append(img.name)


def _face_pass(client, job: Job, model: dict, internal: dict, expiry, tally: dict) -> None:
    """Repaint the leads' faces in each base image of a group shot. Counts into tally as it goes (files, request_ids,
    inpaints, detections), so the spend is still recorded if a later step fails.

    The untouched base image is kept in base/ next to a faces.json with every detected face and the ones chosen."""
    import shutil

    from . import faces
    from .providers.fal import download

    chars = internal["_chars"]
    for img in sorted(job.out_dir.glob(f"{internal['_stem']}_*.png")):
        base = job.out_dir / "base" / img.name
        base.parent.mkdir(parents=True, exist_ok=True)
        if not base.exists():  # a re-run (e.g. another strategy) starts again from the untouched picture
            shutil.copy2(img, base)
        width, height = faces.image_size(base)
        chosen = _detect_faces(client, job, base, internal, expiry, tally)
        if chosen is None:
            continue
        work = job.out_dir / "base" / f"{img.stem}.work.png"
        shutil.copy2(base, work)
        patch = model.get("patch", {})
        res = int(patch.get("resolution", 960))
        for char, box in zip(chars, chosen):
            if box is None:
                continue
            x, y, side = faces.patch_rect(box, width, height, patch.get("factor", 2.6))
            local = faces.scale_box(box, x, y, res / side)
            crop = job.out_dir / "base" / f"{img.stem}.crop.png"
            face_patch("crop", work, crop, x, y, side, res=res)
            crop_url = client.upload_file(crop, expiry)
            mask = client.upload(faces.ellipse_mask_png(res, res, local), "image/png", f"{img.stem}_mask.png", expiry)
            payload = {**model.get("payload", {}), "prompt": char["prompt"], "image_url": crop_url, "mask_url": mask,
                       "loras": _resolve_loras(client, [char["lora"]]), "image_size": {"width": res, "height": res},
                       "num_images": 1, **({"strength": internal["_strength"]} if internal.get("_strength") else {})}
            result = client.run(model["model_id"], payload, model.get("timeout_seconds"))
            tally["inpaints"] += 1
            tally["request_ids"].append(result.get("_request_id"))
            repainted = job.out_dir / "base" / f"{img.stem}.{char['char']}.patch.png"
            download(result["images"][0]["url"], repainted)
            cx, cy, rx, ry = faces.ellipse(faces.scale_box(box, x, y, 1.0))
            face_patch("paste", work, work, x, y, side, patch=repainted, ellipse=(cx, cy, rx, ry))
            crop.unlink(missing_ok=True)
        shutil.move(work, img)
        tally["files"].append(img.name)


def face_patch(mode: str, src: Path, dest: Path, x: int, y: int, side: int, res: int = 960, patch: Path | None = None,
               ellipse: tuple[float, float, float, float] | None = None) -> str:
    """Crop a face square to a close-up, or blend a repainted close-up back (tools/Face-Patch.ps1, System.Drawing)."""
    import subprocess

    script = Path(__file__).resolve().parent.parent / "tools" / "Face-Patch.ps1"
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Mode", mode, "-In", str(src),
            "-Out", str(dest), "-X", str(x), "-Y", str(y), "-Size", str(side), "-Res", str(res)]
    if patch:
        cx, cy, rx, ry = ellipse
        args += ["-Patch", str(patch), "-Cx", f"{cx:.2f}", "-Cy", f"{cy:.2f}", "-Rx", f"{rx:.2f}", "-Ry", f"{ry:.2f}"]
    done = subprocess.run(args, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    if done.returncode != 0:
        raise RuntimeError(f"Face patch ({mode}) failed for {src.name}: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout.strip()


def _composition(job: Job, m: dict, internal: dict, production_key: str) -> tuple[float, bool]:
    """One Azure gpt-image job: generate (or edit with reference photos), save 1280x720 PNGs, record the ACTUAL cost.
    Casting portraits (kind 'anchor') keep the portrait size. Returns (cost, ok)."""
    from . import faces
    from .providers.azure import AzureClient, AzureError, usage_cost

    portrait = job.kind == "anchor"
    refs = [Path(r) for r in internal.get("_references", [])]
    payload = m.get("payload", {})
    if portrait:
        payload = {**payload, "size": "1024x1536"}
        internal = {"_quality": "high", "_stem": job.target.lower(), **internal}
    source = Path(internal["_input_image"]) if internal.get("_input_image") else None
    if source:
        if internal.get("_edit"):  # an edit keeps the source picture's aspect ratio
            payload = {k: v for k, v in payload.items() if k != "aspect_ratio"}
        payload = {**payload, "input_image": base64.b64encode(source.read_bytes()).decode()}
    stem = internal["_stem"]
    print(f"  -> composition {job.target} via Azure {m['model_id']} ({internal['_quality']}, {len(refs)} reference photo(s)) ...",
          flush=True)
    job.out_dir.mkdir(parents=True, exist_ok=True)
    files, request_ids, cost = [], [], 0.0
    try:
        client = AzureClient()
        for _ in range(int(job.units)):  # one image per request: the per-minute quota counts requests, and a failure loses less
            if m.get("api") == "bfl":
                result = client.flux(m["model_id"], m["model_path"], job.prompt, payload)
            else:
                result = client.images(m["model_id"], job.prompt, refs, 1, payload.get("size", "1280x720"),
                                       internal["_quality"], payload.get("output_format", "png"), payload.get("moderation"))
            request_ids.append(result.request_id)
            cost += usage_cost(result.usage, m["pricing_per_m_tokens"]) if result.usage else costs.estimate(
                job.model_key, 1, price_usd=job.price_usd).total
            for data in result.images:
                name = f"{stem}_{len(files) + 1:02d}.png"
                (job.out_dir / name).write_bytes(data)
                if not portrait and faces.image_size(job.out_dir / name) != (1280, 720):  # keep the original, fit the keyframe
                    (job.out_dir / "original").mkdir(exist_ok=True)
                    original = job.out_dir / "original" / name
                    (job.out_dir / name).replace(original)
                    fit_image(original, job.out_dir / name)
                files.append(name)
    except AzureError as err:
        print(f"     ! {job.target}: {str(err)[:300]}", flush=True)
    cost = round(cost, 4)
    if not files and not request_ids and job.out_dir.exists() and not any(job.out_dir.iterdir()):
        job.out_dir.rmdir()  # nothing came back: leave no empty batch for later steps to pick up as "latest"
    if files or request_ids:
        item = {"target": job.target, "prompt": job.prompt, "files": files, "seeds": [], "request_ids": request_ids,
                "cost_usd_estimate": cost, "cost_basis": "token usage" if m.get("api") != "bfl" else "list price",
                "quality": internal["_quality"], "references": [r.name for r in refs]}
        if source:
            item["edited_from"] = str(source)
        _merge_manifest(job.out_dir, {"kind": "anchor" if portrait else "keyframe", "target": job.target, "model_key": job.model_key,
                                      "model_id": f"azure/{m['model_id']}", "prompt": job.prompt, "negative_prompt": ""}, item)
        costs.record({"production": production_key, "provider": "azure", "kind": job.kind, "target": job.target,
                      "model_id": m["model_id"], "units": len(files), "unit": m["unit"], "cost_usd": cost,
                      "request_ids": request_ids, "out_dir": str(job.out_dir)})
    return cost, bool(files)


def run(jobs: list[Job], confirm_cost: float | None, production_key: str) -> float:
    from .providers.fal import FalClient, FalError, download

    total = costs.authorize(estimates(jobs), confirm_cost)
    fal: list = []

    def fal_client() -> FalClient:  # created on first use: an Azure-only batch doesn't need FAL_KEY
        if not fal:
            fal.append(FalClient())
        return fal[0]

    failed: list[str] = []
    expiry = engine_config().get("training", {}).get("upload_expiry_seconds")
    uploads: dict[str, str] = {}
    spent = 0.0
    for job in jobs:
        m = costs.model(job.model_key)
        payload = {**m.get("payload", {}), **job.payload}
        if job.kind != "lora":
            payload["prompt"] = job.prompt
        internal = {k: payload.pop(k) for k in list(payload) if k.startswith("_")}
        if job.kind == "composition" or (job.kind == "anchor" and m.get("provider") == "azure"):
            cost, ok = _composition(job, m, internal, production_key)
            spent += cost
            if not ok:
                failed.append(job.target)
            continue
        client = fal_client()
        if job.kind == "face_pass" and m.get("provider") == "azure":
            print(f"  -> face swap {job.target} via Azure {m['model_id']} ...", flush=True)
            tally = {"files": [], "request_ids": [], "inpaints": 0, "detections": 0, "fallbacks": 0, "azure_usd": 0.0}
            try:
                _face_swap(client, job, m, internal, expiry, tally)
            except Exception as err:  # noqa: BLE001 — record what was spent before stopping
                if "balance" in str(err).lower():
                    print(f"     ! fal balance is empty: face detection needs it — {str(err)[:120]}", flush=True)
                failed.append(job.target)
                print(f"     ! stopped {job.target}: {str(err)[:200]}", flush=True)
            files, request_ids = tally["files"], tally["request_ids"]
            azure_cost = round(tally["azure_usd"], 4)
            fal_cost = costs.estimate("face_detect", tally["detections"], [("face_detect_fallback", tally["fallbacks"])]).total
            if not (tally["inpaints"] or tally["detections"]):
                continue
            spent += azure_cost + fal_cost
            _merge_manifest(job.out_dir, {"kind": "keyframe", "target": job.target.split(":")[0]},
                            {"target": job.target, "prompt": job.prompt, "files": [], "seeds": [], "request_ids": request_ids,
                             "cost_usd_estimate": round(azure_cost + fal_cost, 4),
                             "face_pass": {"method": "azure face swap", "repainted": files, "strategy": internal.get("_strategy"),
                                           "characters": [c["char"] for c in internal["_chars"]]}})
            if tally["inpaints"]:
                costs.record({"production": production_key, "provider": "azure", "kind": job.kind, "target": job.target,
                              "model_id": m["model_id"], "units": tally["inpaints"], "unit": m["unit"], "cost_usd": azure_cost,
                              "request_ids": request_ids, "out_dir": str(job.out_dir)})
            if tally["detections"] or tally["fallbacks"]:
                costs.record({"production": production_key, "kind": "face_detect", "target": job.target,
                              "model_id": costs.model("face_detect")["model_id"], "units": tally["detections"], "unit": "image",
                              "cost_usd": fal_cost, "request_ids": [], "out_dir": str(job.out_dir)})
            continue
        if job.kind == "face_pass":
            print(f"  -> face pass {job.target} via {m['model_id']} ...", flush=True)
            tally = {"files": [], "request_ids": [], "inpaints": 0, "detections": 0, "fallbacks": 0}
            try:
                _face_pass(client, job, m, internal, expiry, tally)
            except (FalError, RuntimeError) as err:
                if "balance" in str(err).lower():
                    raise
                failed.append(job.target)
                print(f"     ! stopped {job.target}: {str(err)[:160]}", flush=True)
            files, request_ids, inpaints, detections = (tally[k] for k in ("files", "request_ids", "inpaints", "detections"))
            if not (inpaints or detections):
                continue
            cost = costs.estimate(job.model_key, inpaints, [("face_detect", detections),
                                                            ("face_detect_fallback", tally["fallbacks"])]).total
            spent += cost
            _merge_manifest(job.out_dir, {"kind": "keyframe", "target": job.target.split(":")[0]},
                            {"target": job.target, "prompt": job.prompt, "files": [], "seeds": [], "request_ids": request_ids,
                             "cost_usd_estimate": cost, "face_pass": {"repainted": files, "strategy": internal.get("_strategy"),
                                                                      "characters": [c["char"] for c in internal["_chars"]]}})
            costs.record({"production": production_key, "kind": job.kind, "target": job.target, "model_id": m["model_id"],
                          "units": inpaints, "unit": m["unit"], "cost_usd": cost, "request_ids": request_ids,
                          "out_dir": str(job.out_dir)})
            continue
        if "image_path" in payload:
            image = payload.pop("image_path")
            uploads.setdefault(image, client.upload_file(Path(image), expiry))
            payload[m.get("image_field", "image_url")] = [uploads[image]] if m.get("image_list") else uploads[image]
            if "end_image_path" in payload:
                end = payload.pop("end_image_path")
                uploads.setdefault(end, client.upload_file(Path(end), expiry))
                payload[m["end_image_field"]] = uploads[end]
            if job.kind == "clip" and job.negative:
                payload["negative_prompt"] = job.negative
        if payload.get("loras"):
            payload["loras"] = _resolve_loras(client, payload["loras"])
        if job.kind == "lora":
            print(f"  -> uploading {len(internal['_files'])} training images for {job.target} ...", flush=True)
            payload["images_data_url"] = client.upload(_training_zip(internal["_files"], internal.get("_captions")),
                                                       "application/zip", f"{_slug(job.target)}_training.zip", expiry)
        print(f"  -> {job.kind} {job.target} via {m['model_id']} ...", flush=True)
        files, request_ids, seeds = [], [], []
        remaining = int(payload.get("num_images", 0))
        chunks = [payload] if not remaining else []
        while remaining > 0:
            n = min(4, remaining)
            chunks.append({**payload, "num_images": n})
            remaining -= n
        try:
            for chunk in chunks:
                result = client.run(m["model_id"], chunk, m.get("timeout_seconds"))
                request_ids.append(result.get("_request_id"))
                seeds.append(result.get("seed"))
                if job.kind == "lora":
                    files += _finish_lora(job, result, job.target)
                blanked = result.get("has_nsfw_concepts") or []
                for idx, img in enumerate(result.get("images") or []):
                    name = download(img["url"], job.out_dir / f"{_slug(job.target)}_{len(files) + 1:02d}.png").name
                    files.append(name)
                    if idx < len(blanked) and blanked[idx]:
                        # the provider's safety filter returns a black frame; never let it reach a training set or review
                        _auto_reject(job.out_dir, name)
                        print(f"     ! {name} came back blanked by the safety filter — auto-rejected", flush=True)
                    if internal.get("_caption"):
                        (job.out_dir / name).with_suffix(".txt").write_text(internal["_caption"], encoding="utf-8")
                if result.get("video"):
                    files.append(download(result["video"]["url"], job.out_dir / f"{_slug(job.target)}.mp4").name)
        except FalError as err:
            # a stuck or failed request must not cost the rest of the batch; report it for a targeted re-run
            if "balance" in str(err).lower():
                raise
            failed.append(job.target)
            print(f"     ! skipped {job.target}: {str(err)[:160]}", flush=True)
            continue
        cost = costs.estimate(job.model_key, job.units).total
        spent += cost
        entry = {"kind": job.kind, "target": job.target.split(":")[0], "model_key": job.model_key, "model_id": m["model_id"],
                 "prompt": job.prompt, "negative_prompt": job.negative}
        _merge_manifest(job.out_dir, entry, {"target": job.target, "prompt": job.prompt, "files": files, "seeds": seeds,
                                             "request_ids": request_ids, "cost_usd_estimate": cost,
                                             **({"loras": payload["loras"]} if payload.get("loras") else {})})
        costs.record({"production": production_key, "kind": job.kind, "target": job.target, "model_id": m["model_id"],
                      "units": job.units, "unit": m["unit"], "cost_usd": cost, "request_ids": request_ids,
                      "out_dir": str(job.out_dir)})
    if failed:
        print(f"{len(failed)} job(s) skipped and not charged in the ledger: {', '.join(failed)}")
        print("Re-run just those (e.g. 'generate training-set <ACT-ID> --only <keys>'). If fal finished them later, "
              "check https://fal.ai/dashboard/requests.")
    print(f"Done. Estimated spend for this batch: ${spent:.2f} (authorized ${total:.2f}).")
    return spent


def count_chained(duration_s: float) -> int:
    return max(1, math.ceil(duration_s / 10))
