"""Library resolver — the deterministic half of every Wave-2 department.

MTower's production already LOCKS who plays whom (casting.json), each character's costume and allowed
wear states, and per shot the size, lens, move, look, location, assets and wear state (shot lists).
Re-deciding those with a model would spend money and risk drifting from the approved design, so the
studio resolves them here from the library and validates them with free Tier-1 rules. The Wave-2 agents
then add only craft judgment on top (continuity, makeup, dressing, light, choreography).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import grounding
from .contract import CameraSpec, CastEntry, GenerationPolicy, SetDressing, WardrobeEntry

_TOKEN = re.compile(r"\{([A-Z0-9_]+)\}")
_ID = re.compile(r"\b(?:VEH|PRP|LOC|WRD|ACT)-\d{4}\b")
NIGHT_LOOKS = {"LOOK_NIGHT_MOON", "LOOK_NIGHT_FIRE", "LOOK_RED_CABIN", "LOOK_KEROSENE", "LOOK_LAMP_TENT",
               "LOOK_BARE_BULB", "LOOK_COCKPIT_GREEN", "LOOK_CAIRO_BLUE_GLASS"}


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@dataclass
class Catalog:
    production: str
    episode: str
    actors: dict = field(default_factory=dict)
    wardrobe: dict = field(default_factory=dict)
    wear_states: dict = field(default_factory=dict)
    off_duty: set = field(default_factory=set)   # wear states where the field kit is left off
    locations: dict = field(default_factory=dict)
    vehicles: dict = field(default_factory=dict)
    props: dict = field(default_factory=dict)
    looks: dict = field(default_factory=dict)
    lenses: dict = field(default_factory=dict)
    format_defaults: dict = field(default_factory=dict)
    review_lists: dict = field(default_factory=dict)
    look_aliases: dict = field(default_factory=dict)
    tokens: dict = field(default_factory=dict)
    cast: dict = field(default_factory=dict)
    uncast: dict = field(default_factory=dict)
    extras: dict = field(default_factory=dict)
    qa: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ text helpers
    def expand(self, text: str) -> str:
        def sub(m):
            k = m.group(1)
            return self.tokens.get(k) or self.looks.get(k) or m.group(0)
        return _TOKEN.sub(sub, text or "")

    def look_text(self, key: str) -> str:
        if key in self.look_aliases:
            return self.expand(self.look_aliases[key])
        return self.looks.get(key, "")

    def known_look(self, key: str) -> bool:
        return key in self.looks or key in self.look_aliases

    def production_rules(self) -> str:
        if not self.qa:
            return ""
        return f"PRODUCTION: {self.qa.get('story', '')}\nPRODUCTION RULES:\n" + "\n".join(
            f"- {r}" for r in self.qa.get("rules", []))


@lru_cache(maxsize=8)
def catalog(production: str, episode: str) -> Catalog:
    lib = grounding.LIBRARY_DIR
    pre = grounding.PRODUCTIONS_DIR / production / episode / "02_preproduction"
    actors = _load(lib / "actors" / "actors.json")
    wardrobe = _load(lib / "wardrobe" / "wardrobe.json")
    looks = _load(lib / "looks" / "looks.json")
    cfg = _load(pre / "production_config.json")
    casting = _load(pre / "casting.json")
    return Catalog(
        production=production,
        episode=episode,
        actors={a["id"]: a for a in actors.get("actors", [])},
        wardrobe={w["id"]: w for w in wardrobe.get("wardrobe", [])},
        wear_states=wardrobe.get("wear_states", {}),
        off_duty=set(wardrobe.get("off_duty_wear_states", [])),
        locations={l["id"]: l for l in _load(lib / "locations" / "locations.json").get("locations", [])},
        vehicles={v["id"]: v for v in _load(lib / "vehicles" / "vehicles.json").get("vehicles", [])},
        props={p["id"]: p for p in _load(lib / "props" / "props.json").get("props", [])},
        looks=looks.get("look", {}),
        lenses=looks.get("camera", {}),
        format_defaults=looks.get("format_defaults", {}),
        review_lists=looks.get("review_lists", {}),
        look_aliases=cfg.get("look_aliases", {}),
        tokens=cfg.get("token_overrides", {}),
        cast=casting.get("cast", {}),
        uncast=casting.get("uncast_roles", {}),
        extras=casting.get("extras", {}),
        qa=cfg.get("qa", {}),
    )


# ---------------------------------------------------------------------- resolution

@dataclass
class Resolved:
    """The locked, library-resolved half of a shot's Wave-2 design + the library text the agents read."""
    design: dict
    cast: list[CastEntry]
    wardrobe: list[WardrobeEntry]
    set: SetDressing
    camera: CameraSpec
    policy: GenerationPolicy
    wear: str
    extras_text: str
    problems: list[str]                  # Tier-1 library-integrity problems
    briefs: dict[str, str]               # department -> library text for the agent
    carried_props: list[str] = field(default_factory=list)   # PRP ids carried by this shot's characters
    beat_props: list[str] = field(default_factory=list)      # PRP ids used or carried anywhere in the beat

    @property
    def allowed_props(self) -> set[str]:
        """Props that may appear in this shot: its own, its characters' costume props, and the beat's props."""
        return set(self.set.props) | set(self.carried_props) | set(self.beat_props)


@lru_cache(maxsize=64)
def beat_props(production: str, episode: str, beat_ref: str) -> tuple[str, ...]:
    """Every PRP id listed as an asset, or carried as a character addition, in any shot of the beat."""
    cat = catalog(production, episode)
    found: set[str] = set()
    for sid in grounding.beat_shot_ids(production, episode, beat_ref):
        d = grounding.find_shot(production, episode, sid) or {}
        for raw in d.get("assets") or []:
            found |= set(re.findall(r"\bPRP-\d{4}\b", str(raw)))
        for ch in _char_entries(d):
            info = cat.cast.get(ch.get("id"), {})
            found |= set(re.findall(r"\bPRP-\d{4}\b", info.get("character_additions") or ""))
    return tuple(sorted(found))


def _char_entries(design: dict) -> list[dict]:
    out = []
    for c in design.get("characters") or []:
        out.append(c if isinstance(c, dict) else {"id": c})
    return out


def resolve(cat: Catalog, design: dict) -> Resolved:
    problems: list[str] = []
    beat_wear = design.get("wear") or ""
    face_pass = design.get("face_pass", True) is not False
    insert = (design.get("size") or "").upper() in ("INSERT", "CARD")

    # ---- Casting: characters -> actors (casting.json is the locked source of truth)
    cast: list[CastEntry] = []
    wardrobe: list[WardrobeEntry] = []
    for ch in _char_entries(design):
        cid = ch.get("id")
        info = cat.cast.get(cid)
        if info is None:
            if cid in cat.uncast:
                cast.append(CastEntry(character_id=cid, character=cat.uncast[cid].get("character", ""),
                                      prominence="uncast — " + cat.uncast[cid].get("treatment", "")))
                continue
            problems.append(f"casting: {cid} is not in casting.json")
            continue
        actor = cat.actors.get(info.get("actor", ""), {})
        if not actor:
            problems.append(f"casting: {cid} → actor {info.get('actor')} not found in the actor library")
        prominence = ch.get("prominence") or ("not_visible" if not face_pass else "lead")
        cast.append(CastEntry(
            character_id=cid, character=info.get("character", ""), actor_id=info.get("actor", ""),
            face_model=(actor.get("lora") or {}).get("trigger", ""), actor_status=actor.get("status", ""),
            prominence=prominence))
        if info.get("lora_needed") and not (actor.get("lora") or {}).get("trigger"):
            problems.append(f"casting: {cid} needs a trained face model but actor {actor.get('id')} has none")
        # ---- Wardrobe base
        wear = ch.get("wear") or beat_wear
        allowed = info.get("wear_states") or []
        if wear and wear not in cat.wear_states:
            problems.append(f"wardrobe: wear state {wear} is not in the wardrobe library")
        elif wear and allowed and wear not in allowed:
            problems.append(f"wardrobe: {cid} is not allowed wear state {wear} (casting allows {', '.join(allowed)})")
        wid = info.get("wardrobe", "")
        if wid and wid not in cat.wardrobe:
            problems.append(f"wardrobe: {cid} → {wid} not found in the wardrobe library")
        additions = "; ".join(x for x in (info.get("character_additions"), info.get("face_additions")) if x)
        wardrobe.append(WardrobeEntry(target=cid, wardrobe_id=wid, wear_state=wear, additions=additions))

    # ---- Set: location, vehicles (incl. interiors), props — all library ids
    loc = design.get("location") or ""
    if loc and loc not in cat.locations:
        problems.append(f"set: location {loc} not found in the location library")
    vehicles, props, interior = [], [], ""
    for raw in design.get("assets") or []:
        for aid in _ID.findall(str(raw)):
            if aid.startswith("VEH"):
                if aid not in cat.vehicles:
                    problems.append(f"set: vehicle {aid} not in the vehicle library")
                if "interior" in str(raw).lower():
                    interior = f"{aid} cabin"
                else:
                    vehicles.append(aid)
            elif aid.startswith("PRP"):
                if aid not in cat.props:
                    problems.append(f"set: prop {aid} not in the prop library")
                props.append(aid)
    set_ = SetDressing(location_id=loc, vehicle_interior=interior, vehicles=vehicles, props=props)

    # ---- Camera: locked size / lens / move / looks + studio format
    looks = list(design.get("look") or [])
    for k in looks:
        if not cat.known_look(k):
            problems.append(f"camera: look key {k} is not defined in looks.json or the production's look aliases")
    lens = design.get("lens") or ""
    if lens and lens not in cat.lenses:
        problems.append(f"camera: lens {lens} is not defined in looks.json")
    if loc in cat.locations and not insert:
        variants = cat.locations[loc].get("light_variants") or []
        scene_looks = [k for k in looks if k not in ("LOOK_BASE",) and k in cat.looks]
        for k in scene_looks:
            if variants and k not in variants:
                problems.append(f"camera: look {k} is not one of {loc}'s light variants ({', '.join(variants)})")
    fd = cat.format_defaults
    camera = CameraSpec(shot_size=design.get("size") or "", lens=lens, movement=design.get("move") or "static",
                        look_key=looks, format=f"generate {fd.get('generate_aspect_ratio', '16:9')}, "
                                                f"deliver {fd.get('deliver_aspect_ratio', '2.39:1')}")
    policy = GenerationPolicy(lip_sync=design.get("lip_sync") or "avoid",
                              video_model=design.get("model") or "default", face_pass=face_pass)

    return Resolved(design=design, cast=cast, wardrobe=wardrobe, set=set_, camera=camera, policy=policy,
                    wear=beat_wear, extras_text=design.get("extras") or "", problems=problems,
                    briefs=_briefs(cat, design, cast, wardrobe, set_, looks, lens, loc, beat_wear),
                    carried_props=sorted({m for w in wardrobe for m in re.findall(r"\bPRP-\d{4}\b", w.additions)}),
                    beat_props=list(beat_props(cat.production, cat.episode, str(design.get("beat") or ""))))


def _briefs(cat, design, cast, wardrobe, set_, looks, lens, loc, wear) -> dict[str, str]:
    """Library text per department, so agents reason over the catalogs, not memory."""
    actors = "\n".join(
        f"- {c.character_id} {c.character} → {c.actor_id}: {cat.actors.get(c.actor_id, {}).get('face_and_body', '')} "
        f"Signature: {cat.actors.get(c.actor_id, {}).get('signature_features', '')}"
        for c in cast if c.actor_id)
    costumes = "\n".join(
        f"- {w.target} wears {w.wardrobe_id} '{cat.wardrobe.get(w.wardrobe_id, {}).get('name', '')}': "
        f"{cat.expand(cat.wardrobe.get(w.wardrobe_id, {}).get('prompt', ''))} "
        + ("(OFF DUTY in this wear state: no field kit) " if w.wear_state in cat.off_duty else
           f"Field kit: {cat.expand(cat.wardrobe.get(w.wardrobe_id, {}).get('field_kit', ''))} ")
        + f"Additions: {w.additions or '—'}"
        for w in wardrobe)
    extras_map = "\n".join(f"- {k}: wardrobe {v.get('wardrobe')} — {v.get('note', '')}" for k, v in cat.extras.items())
    wear_text = "\n".join(f"- {k}: {v}" for k, v in cat.wear_states.items())
    location = cat.locations.get(loc, {})
    loc_text = (f"{loc} {location.get('name', '')}: {location.get('prompt', '')} "
                f"(light variants: {', '.join(location.get('light_variants') or [])})") if location else "—"
    veh_text = "\n".join(
        f"- {v}: {cat.vehicles.get(v.split()[0], {}).get('name', '')} — "
        f"{cat.vehicles.get(v.split()[0], {}).get('prompt', '')}"
        for v in ([set_.vehicle_interior] if set_.vehicle_interior else []) + set_.vehicles)
    if set_.vehicle_interior:
        veh_text += f"\n  interior: {cat.vehicles.get(set_.vehicle_interior.split()[0], {}).get('interiors', {})}"
    prop_text = "\n".join(
        f"- {p}: {cat.props.get(p, {}).get('name', '')} — {cat.props.get(p, {}).get('prompt', '')} "
        f"(verify: {cat.props.get(p, {}).get('verify', '—')})" for p in set_.props)
    all_props = "\n".join(f"- {p['id']}: {p.get('name', '')}" for p in cat.props.values())
    look_text = "\n".join(f"- {k}: {cat.look_text(k)}" for k in looks)
    lens_text = f"{lens}: {cat.lenses.get(lens, '')}" if lens else "—"
    avoid = "\n".join(f"- {k}: {v}" for k, v in cat.review_lists.items() if k.startswith("AVOID"))
    fmt = json.dumps(cat.format_defaults, ensure_ascii=False)
    return {
        "casting": f"CAST (locked):\n{actors or '—'}\n\nEXTRAS ARCHETYPES (casting.json):\n{extras_map}",
        "wardrobe": f"COSTUMES (locked):\n{costumes or '—'}\n\nWEAR STATES:\n{wear_text}\n\nAVOID:\n{avoid}",
        "makeup": f"CAST:\n{actors or '—'}\n\nBEAT WEAR STATE: {wear} — {cat.wear_states.get(wear, '')}\n\nWEAR STATES:\n{wear_text}",
        "set": f"LOCATION: {loc_text}\n\nVEHICLES:\n{veh_text or '—'}\n\nSHOT PROPS (locked):\n{prop_text or '—'}\n\n"
               f"PROP LIBRARY (ids you may cite):\n{all_props}\n\nAVOID:\n{avoid}",
        "camera": f"LOOKS (locked):\n{look_text or '—'}\n\nLENS: {lens_text}\n\nLOCATION: {loc_text}\n\nFORMAT: {fmt}",
        "action": f"SHOT PROPS:\n{prop_text or '—'}\n\nCOSTUMES:\n{costumes or '—'}",
    }


def design_text(cat: Catalog, design: dict) -> str:
    """The shot's locked design in plain words (shared by all departments)."""
    lines = [
        f"Shot {design.get('shot_id')} — beat {design.get('beat')} '{design.get('beat_title', '')}'.",
        f"Size {design.get('size')}, lens {design.get('lens')}, move {design.get('move') or 'static'}, "
        f"duration {design.get('duration_s', '?')}s.",
        f"What the frame shows: {design.get('prompt', '')}",
        f"What happens in the clip: {design.get('motion') or ''}",
    ]
    for k, label in (("face", "Face direction"), ("extras", "Extras"), ("notes", "Director's design notes")):
        if design.get(k):
            lines.append(f"{label}: {design[k]}")
    if design.get("face_pass") is False:
        lines.append("By design the lead's face is NOT clearly visible (profile darkness, back, or shadow).")
    return "\n".join(lines)
