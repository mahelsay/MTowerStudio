"""Compose image and motion prompts for shots and reference sheets."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .library import ID_PATTERN, Library
from .production import Production

ANNOTATION = re.compile(r"\s*\(.*?\)")
FRAMING = {  # shot size in words: the lens alone let the image model drift to wide two-shots (QA, 2026-10-14)
    "ECU": "extreme close-up: the face fills the frame",
    "CU": "close-up: one person's head and the top of the shoulders fill most of the frame",
    "MCU": "medium close-up: one person framed from mid-chest up, the head in the upper part of the frame",
    "MS": "medium shot: framed from the waist up",
}


@dataclass
class ComposedShot:
    shot_id: str
    image_prompt: str
    motion_prompt: str
    negative_prompt: str
    model_tier: str
    duration_s: float
    characters: list[str]


def _clean(parts: list[str]) -> str:
    text = ". ".join(p.strip().rstrip(".") for p in parts if p and p.strip())
    return re.sub(r"\s+", " ", text).strip() + "."


HAIR = re.compile(r"\b(hair|haircut|braids?|shaved|bald)\b", re.IGNORECASE)
WARDROBE_HAIR = re.compile(r"\s+with\s+[^,.;()]*\bhair\b", re.IGNORECASE)


def resolve_hair(face: str, wardrobe: str, additions: str) -> tuple[str, str]:
    """One hair description per character, so the image model never gets two that disagree.

    Priority: the role's character_additions (e.g. 'short military haircut') > the actor's own
    hair in face_and_body > the wardrobe's generic default (e.g. 'bare-headed with short black hair').
    Clauses about covered hair (headscarf) or facial hair are kept.
    """
    def is_hair_clause(clause: str) -> bool:
        low = clause.lower()
        return bool(HAIR.search(clause)) and "covered" not in low and "facial" not in low

    if HAIR.search(additions):
        face = ", ".join(c for c in face.split(", ") if not is_hair_clause(c))
        wardrobe = WARDROBE_HAIR.sub("", wardrobe)
    elif any(is_hair_clause(c) for c in face.split(", ")):
        wardrobe = WARDROBE_HAIR.sub("", wardrobe)
    return face, wardrobe


class PromptComposer:
    def __init__(self, library: Library, production: Production):
        self.lib = library
        self.prod = production
        self.tokens = production.token_overrides()
        self.aliases = production.config.get("look_aliases", {})

    # ---- blocks -------------------------------------------------------------
    def look(self, key: str) -> str:
        if key in self.aliases:
            return self.lib.expand(self.aliases[key], self.tokens)
        value = self.lib.block(key)
        return self.lib.expand(value, self.tokens) if value else ""

    def lens(self, key: str | None) -> str:
        if not key:
            return ""
        return self.lib.block(key) or key

    def wardrobe_text(self, wardrobe_id: str | None, wear_key: str | None = None) -> str:
        """The costume; its field_kit (webbing, magazines) is left off in off-duty wear states."""
        if not wardrobe_id:
            return ""
        item = self.lib.wardrobe.get(wardrobe_id)
        if not item:
            return ""
        text = self.lib.expand(item["prompt"], self.tokens)
        if item.get("field_kit") and wear_key not in self.lib.off_duty_wear:
            text += ", " + item["field_kit"]
        return text

    def wear_text(self, wear_key: str | None) -> str:
        return self.lib.wear_states.get(wear_key or "", "")

    def body_hint(self, actor: dict, skip_hair: bool = False) -> str:
        """Everything the base pass needs so the body matches the face added later: age, skin, build, hair, beard."""
        t = actor.get("traits") or {}
        man = actor.get("gender") != "female"
        age = actor.get("apparent_age")
        who = ("boy" if man else "girl") if age and age < 16 else ("man" if man else "woman")
        parts = [f"an Egyptian {who}" + (f" about {age}" if age else "")]
        skin = next((c for c in actor.get("face_and_body", "").split(", ") if "skin" in c), "")
        if skin:
            parts.append(skin)
        elif t.get("skin_tone"):
            parts.append(f"{t['skin_tone'].replace('-', ' ')} skin")
        if t.get("build"):
            parts.append(f"{t['build'].replace('-', ' ')} build")
        if t.get("hair") and not skip_hair:
            parts.append(f"{t['hair'].replace('-', ' ')} hair" if "hair" not in t["hair"] else t["hair"].replace("-", " "))
        if t.get("facial_hair") and t["facial_hair"] not in ("none", "clean-shaven"):
            parts.append(t["facial_hair"].replace("-", " "))
        return ", ".join(parts)

    def character(self, char_id: str, wear_key: str | None, use_lora: bool = True, include_wardrobe: bool = True,
                  include_face: bool = True, include_additions: bool = True, kit: str | None = None) -> str:
        """kit (a shot's per-character override) replaces the role's character_additions for that one shot."""
        cast = self.prod.casting["cast"].get(char_id)
        if not cast:
            return ""
        actor = self.lib.actors[cast["actor"]]
        trigger = actor.get("lora", {}).get("trigger") if use_lora and actor.get("status") in ("lora_trained", "locked") else None
        additions = ANNOTATION.sub("", (cast.get("character_additions") or "") if kit is None else kit)
        wardrobe = self.wardrobe_text(cast.get("wardrobe"), wear_key) if include_wardrobe else ""
        face, wardrobe = resolve_hair(actor["face_and_body"], wardrobe, additions)
        parts = [trigger, face] if include_face else [self.body_hint(actor, skip_hair=bool(HAIR.search(additions)))]
        # face_additions (e.g. glasses) belong to the face, so the face pass keeps them too
        parts.append(cast.get("face_additions", ""))
        if wardrobe:
            parts.append(f"wearing {wardrobe}")
        if additions and include_additions:
            parts.append(additions)
        wear = self.wear_text(wear_key)
        if include_wardrobe and wear and wear_key != "WEAR_CLEAN":
            parts.append(wear)
        return ", ".join(p for p in parts if p)

    def characters(self, char_ids: list[str], wear_key: str | None, use_lora: bool = True,
                   faces: bool = True, shared_wardrobe: str | None = None, kit: dict | None = None) -> list[str]:
        """One character: full description. Several: each face once, then each shared wardrobe once.
        faces=False (group-shot base pass): role only — rank, gear, clothes; the face pass adds the face later."""
        kit = kit or {}
        if not faces:
            out = []
            for c in char_ids:
                wid = self.prod.casting["cast"].get(c, {}).get("wardrobe")
                text = self.character(c, wear_key, False, include_wardrobe=wid != shared_wardrobe, include_face=False, kit=kit.get(c))
                if text:
                    out.append(f"{self.prod.casting['cast'][c].get('role') or 'the lead'}: {text}" if len(char_ids) > 1 else text)
            return out
        if len(char_ids) <= 1:
            return [self.character(c, wear_key, use_lora, kit=kit.get(c)) for c in char_ids]
        ordinals = ["first", "second", "third", "fourth", "fifth"]
        parts, wardrobes = [], []
        for n, c in enumerate(char_ids):
            text = self.character(c, wear_key, use_lora, include_wardrobe=False, kit=kit.get(c))
            if text:
                parts.append(f"the {ordinals[min(n, 4)]} person: {text}")
            wid = self.prod.casting["cast"].get(c, {}).get("wardrobe")
            if wid and wid not in wardrobes:
                wardrobes.append(wid)
        wear = self.wear_text(wear_key)
        for wid in wardrobes:
            # each person's hair is already described with their face; drop the wardrobe's generic hair default
            text = f"{'all' if len(wardrobes) == 1 else 'some'} wearing {WARDROBE_HAIR.sub('', self.wardrobe_text(wid, wear_key))}"
            if wear and wear_key != "WEAR_CLEAN":
                text += f", {wear}"
            parts.append(text)
        return parts

    def actor_ref(self, actor_id: str) -> str:
        """An actor's LoRA trigger once trained, otherwise their face description."""
        actor = self.lib.actors.get(actor_id, {})
        trigger = actor.get("lora", {}).get("trigger")
        if trigger and actor.get("status") in ("lora_trained", "locked"):
            return trigger
        return actor.get("face_and_body", actor_id)

    def asset_text(self, raw: str, triggers: bool = True) -> str:
        match = ID_PATTERN.search(raw)
        if not match:
            return ""
        item = self.lib.asset(match.group(0))
        if not item or match.group(1) in ("ACT", "WRD"):
            return ""
        note = ANNOTATION.search(raw)
        interior = ""
        if note and "interior" in note.group(0) and item.get("interiors"):
            interior = item["interiors"].get("cabin", "")
        binding = self.prod.config.get("prop_bindings", {}).get(match.group(0), {})
        values = {k: self.actor_ref(v) for k, v in binding.items() if k.isupper()}
        text = self.lib.expand(interior or item.get("prompt", ""), {**self.tokens, **values})
        trigger = (item.get("lora") or {}).get("trigger")
        if triggers and trigger and item.get("status") in ("lora_trained", "locked") and not interior:
            text = f"{trigger}, {text}"
        return text

    def extras_text(self, extras: str | None, wear_key: str | None) -> str:
        if not extras:
            return ""
        text = ANNOTATION.sub("", extras)
        wrd = re.search(r"WRD-\d{4}", extras)
        if wrd:
            text += f", wearing {self.wardrobe_text(wrd.group(0), wear_key)}"
            wear = self.wear_text(wear_key)
            if wear and wear_key != "WEAR_CLEAN":
                text += f", {wear}"
        return text

    # ---- shots --------------------------------------------------------------
    def shot(self, beat: dict, shot: dict, use_lora: bool = True, faces: bool = True, triggers: bool = True) -> ComposedShot:
        looks = shot.get("look") or beat.get("look") or []
        wear = shot.get("wear", beat.get("wear"))
        location_id = shot.get("location") or beat.get("location")
        chars = [c if isinstance(c, str) else c.get("id") for c in shot.get("characters") or []]
        extras_wrd = re.search(r"WRD-\d{4}", shot.get("extras") or "")

        parts = [self.look(k) for k in looks]
        parts.append(shot.get("prompt") or shot.get("image_prompt_core") or "")
        people_text = self.characters(chars, wear, use_lora, faces, extras_wrd.group(0) if extras_wrd else None, shot.get("kit"))
        if self.is_insert(shot):
            people_text = [f"only the hands and forearms of {t}; the face stays outside the frame" for t in people_text if t]
        parts.extend(people_text)
        parts.append(self.extras_text(shot.get("extras"), wear))
        for a in shot.get("assets") or []:
            parts.append(self.asset_text(a, triggers))
        if location_id and location_id in self.lib.locations:
            parts.append("setting: " + self.lib.locations[location_id]["prompt"])
        parts.append(self.lens(shot.get("lens")))
        size = (shot.get("size") or shot.get("shot_size") or "").upper()
        if self.is_insert(shot):
            parts.append("tight insert shot: the detail fills the whole frame")
        elif size in FRAMING:
            parts.append(FRAMING[size] + (", only this one person's face in the frame" if shot.get("lip_sync") == "required"
                                          and size in ("ECU", "CU", "MCU") else ""))
        else:
            parts.append("wide cinematic composition with the subject in the central band of the frame")
        people = " ".join(parts)
        if not self.is_insert(shot) and "commando" in people and "bare-headed" in people:
            # said positively: naming helmets or headsets made the image model add them (QA, 2026-10-14)
            parts.append("every Egyptian commando's head is uncovered, his short black hair visible")
        parts.extend(self.realism(shot))

        motion_parts = [shot.get("motion") or shot.get("motion_prompt") or "", shot.get("move") or shot.get("camera_move") or "",
                        "realistic natural motion, cinematic 35mm film look, 24 fps", self.lib.block("MOTION_NATURAL") or ""]
        review = self.prod.config.get("review_lists", [])
        negative = ", ".join(self.lib.looks.get("review_lists", {}).get(k, "") for k in review)
        tier = shot.get("model") or shot.get("video_model") or "default"
        return ComposedShot(shot["shot_id"], _clean(parts), _clean(motion_parts), negative, tier, float(shot.get("duration_s", 0)), chars)

    def chatgpt_prompt(self, beat: dict, shot: dict) -> str:
        """Paste-ready prompt for ChatGPT image generation (manual, covered by the subscription).
        No face models or trigger words: leads are described by body only; the engine's face pass adds the actor's face."""
        base = self.shot(beat, shot, use_lora=False, faces=False, triggers=False).image_prompt
        if self.is_insert(shot):
            # the face line made the model put whole soldiers into hand and fabric inserts
            faces = " Only the detail is in frame: no faces and no other people."
        elif shot.get("face_pass", True):
            faces = " Every person has a different, ordinary, unretouched face. Keep faces natural and clearly lit enough to see."
        else:
            faces = " The person is seen from behind; no face is visible."
        return ("Create one photorealistic widescreen 16:9 landscape image: a still frame from a historical war film. "
                + base + faces + " The picture fills the whole frame edge to edge, with no black letterbox bars."
                " No text, captions, logos, borders, or watermarks.")

    def flux_prompt(self, beat: dict, shot: dict) -> str:
        """Short prompt for FLUX.1 Kontext (child shots): it follows a few plain sentences far better than the long
        ChatGPT prompt, which made it age the children up, mix in the location's other places, and drop costume details.
        The shot prompt itself must say where we are; the location's generic setting is left out."""
        looks = shot.get("look") or beat.get("look") or []
        wear = shot.get("wear", beat.get("wear"))
        chars = [c if isinstance(c, str) else c.get("id") for c in shot.get("characters") or []]
        return _clean([*[self.look(k) for k in looks], shot.get("prompt") or "",
                       *self.characters(chars, wear, use_lora=False, faces=False, kit=shot.get("kit")),
                       self.extras_text(shot.get("extras"), wear), self.lens(shot.get("lens")),
                       "the child's face clearly visible" if shot.get("face_pass", True) else "",
                       self.lib.block("NATURAL_CHILD") or ""])

    def triggered(self, key: str, text: str) -> bool:
        """Whether the text names one of the words that call for a realism block (looks.json realism_triggers)."""
        words = self.lib.looks.get("realism_triggers", {}).get(key) or []
        low = text.lower()
        return any(re.search(rf"\b{re.escape(w)}(s|es)?\b", low) for w in words if isinstance(w, str))

    def realism(self, shot: dict) -> list[str]:
        """The natural-look blocks a shot needs (looks.json 'realism'): anatomy and head-to-body proportions for people,
        children, groups, animals and birds; hands in inserts; real-world scale for everything else."""
        block = lambda k: self.lib.block(k) or ""  # noqa: E731
        text = " ".join([shot.get("prompt") or shot.get("image_prompt_core") or "", ANNOTATION.sub("", shot.get("extras") or "")])
        chars = shot.get("characters") or []
        if self.is_insert(shot):
            return [block("NATURAL_HANDS")] if self.triggered("NATURAL_HANDS", text) else []
        out = []
        if chars or shot.get("extras") or self.triggered("PEOPLE", text):
            out.append(block("NATURAL_HUMAN"))
            if self.has_child(shot):
                out.append(block("NATURAL_CHILD"))
            if len(chars) > 1 or shot.get("extras") or self.triggered("GROUP", text):
                out.append(block("NATURAL_GROUP"))
        out += [block(k) for k in ("NATURAL_ANIMAL", "NATURAL_BIRD") if self.triggered(k, text)]
        out.append(block("SCALE_RULES"))
        return [x for x in out if x]

    @staticmethod
    def is_insert(shot: dict) -> bool:
        """A detail shot with nobody's face in it (a hand, a boot, a fabric). A cast character in an INSERT is there for
        his hands and sleeve only: describing his face made the model paint a face close-up instead (QA, 2026-10-15)."""
        return (shot.get("size") or shot.get("shot_size")) == "INSERT" and not shot.get("extras")

    CHILD_WORDS = re.compile(r"\b(boy|boys|girl|girls|child|children|kid|kids|toddler|baby|infant|schoolboy|schoolgirl)\b", re.I)

    def has_child(self, shot: dict) -> bool:
        """A cast child (apparent age under 16) or a child among the extras / in the prompt — Azure gpt-image refuses both."""
        cast = self.prod.casting["cast"]
        for c in shot.get("characters") or []:
            actor = self.lib.actors.get(cast.get(c if isinstance(c, str) else c.get("id"), {}).get("actor", ""), {})
            if (actor.get("apparent_age") or 99) < 16:
                return True
        return bool(self.CHILD_WORDS.search(f"{shot.get('extras') or ''} {shot.get('prompt') or ''}"))

    def face_pass_prompt(self, beat: dict, shot: dict, char_id: str) -> str:
        """Prompt for repainting one character's face on a close-up crop: the face model trigger, the face, the light.
        No clothes or kit: the crop shows a head, and a full-body prompt makes the model re-pose it or invent objects."""
        looks = shot.get("look") or beat.get("look") or []
        person = self.character(char_id, None, use_lora=True, include_wardrobe=False, include_additions=False)
        return _clean(["close-up photo of the face of " + person, shot.get("face", ""), *[self.look(k) for k in looks],
                       "same head angle, expression and lighting as the surrounding picture, natural skin texture"])

    def role_brief(self, char_id: str) -> str:
        """Who a character is and what he wears (no face): enough to find him among the people in a frame."""
        cast = self.prod.casting["cast"].get(char_id, {})
        looks = self.character(char_id, None, use_lora=False, include_face=False)
        return "; ".join(x for x in (cast.get("role"), looks) if x)

    def shot_design_text(self, beat: dict, shot: dict) -> str:
        return " ".join(x for x in (beat.get("title"), shot.get("prompt") or shot.get("image_prompt_core"),
                                    f"Also in frame: {ANNOTATION.sub('', shot['extras'])}." if shot.get("extras") else "",
                                    f"Camera: {shot.get('size', '')} {shot.get('move', '')}".strip()) if x)

    def face_swap_prompt(self, beat: dict, shot: dict, char_id: str) -> str:
        """Prompt for the Azure face swap (gpt-image masked edit): image 1 is the frame, image 2 the actor's anchor portrait,
        the mask covers the lead's face. The frame keeps its head size, angle and light; only the identity changes."""
        looks = shot.get("look") or beat.get("look") or []
        cast = self.prod.casting["cast"].get(char_id, {})
        role = cast.get("role") or "the lead"
        light = "; ".join(x for x in (self.look(k) for k in looks if k != "LOOK_BASE") if x)
        extras = ", ".join(x for x in (cast.get("face_additions"), shot.get("face")) if x)
        bare = "bare-headed" in self.character(char_id, None, use_lora=False, kit=(shot.get("kit") or {}).get(char_id))
        return " ".join(p for p in [
            "Image 1 is a still frame from a historical war film. Image 2 is the casting portrait of the actor who plays "
            f"{role}: the person whose face is inside the masked area of image 1.",
            "Give that person the face of the person in image 2: the same facial structure, eyes, eyebrows, nose, mouth, "
            "skin tone and facial hair.",
            "His head stays uncovered, his short black hair visible." if bare else "",
            f"In this shot: {extras}." if extras else "",
            f"The scene's light: {light}." if light else "",
            (lambda b: b[:1].upper() + b[1:])(self.lib.block("FACE_SWAP") or "") + "."] if p)

    # ---- reference sheets -------------------------------------------------------
    def actor_reference(self, actor_id: str, variation: str = "REF_ANCHOR") -> str:
        actor = self.lib.actors[actor_id]
        base = self.look("LOOK_BASE")
        ref = self.lib.expand(self.lib.looks["reference_variations"][variation], self.tokens)
        return _clean([base, actor["face_and_body"],
                       "an ordinary real person photographed for a casting file, not a model, unretouched skin with natural "
                       "imperfections, slightly asymmetrical features",
                       "bare face without makeup or face paint, no marks on the skin except those described",
                       "plain simple civilian clothing with no badges or insignia", ref,
                       "clean photograph with no text or lettering anywhere in the frame"])

    def asset_reference(self, asset_id: str, look_key: str | None = None) -> str:
        item = self.lib.asset(asset_id)
        if not item:
            raise KeyError(asset_id)
        look = self.look(look_key) if look_key else ""
        return _clean([self.look("LOOK_BASE"), look, item.get("prompt", ""), "reference plate, no people, clear view"])
