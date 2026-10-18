"""Wave 2 — the creative crew: Casting (4), Wardrobe (5), Makeup & Hair (5b), Set (6), Camera/DoP (7),
Stunt/Action (7b).

Each department receives the shot's LOCKED design (resolved from the MTower library by library.resolve)
and adds only craft judgment. `apply` writes a department's craft fields and nothing else, so locked
choices (who plays whom, costume, wear state, location, lens, look) cannot be changed by a model.
A department that disagrees with a locked choice files a concern for the human instead.
"""
from __future__ import annotations

import re
from typing import Any

from .base import Agent, _cost
from ..contract import CrowdEntry, MakeupEntry, WardrobeEntry

_COMMON_RULES = (
    "You are a head of department on a photorealistic historical war drama made with AI image models. "
    "The shot's design is LOCKED by the director (casting, costume, wear state, location, lens, look): do not "
    "change it. Add your department's craft on top. If you believe a locked choice is wrong, say so in "
    "`concerns` (one sentence each) — never silently change it. PRECEDENCE: the locked design and the location's "
    "own rules outrank the Director's notes and the scene intent; when they conflict, follow the lock and report the "
    "conflict in `concerns`. Props carried as a character addition (e.g. a compass on a lanyard) are locked "
    "costume props. "
    "IN FRAME: only the shot's locked cast and crowd groups appear in the frame. Anyone else the design mentions "
    "(e.g. 'the radio operator off to the side') is off-screen, or at most an unrecognizable partial shape — never "
    "give them costume, makeup or action entries; report a design that seems to need them in `concerns`. "
    "LOCK vs LOCK: if two locked items seem to conflict, choose the reading that satisfies both (e.g. shin-deep "
    "water, but splashes soak the trousers higher) and report the conflict in `concerns`. "
    "Be concrete and visual: your output becomes "
    "instructions for an image generator and checks for the image reviewer. No modern items. Restrained violence: "
    "no graphic wounds or gore (series bible §4.4). Keep each field short."
)


def common_context(shot, cat, resolved, prev_design: str, include_rules: bool = True) -> str:
    from .. import library

    s = resolved
    cast = "; ".join(f"{c.character_id} {c.character} (actor {c.actor_id}, {c.prominence})" for c in s.cast) or "none"
    ward = "; ".join(f"{w.target}: {w.wardrobe_id} / {w.wear_state}" for w in s.wardrobe) or "none"
    st = s.set
    carried = sorted({m for w in s.wardrobe for m in re.findall(r"\bPRP-\d{4}\b", w.additions)})
    others = sorted(set(s.beat_props) - set(st.props) - set(carried))
    sett = (f"location {st.location_id or '—'}" + (f", inside {st.vehicle_interior}" if st.vehicle_interior else "")
            + f", vehicles {st.vehicles or '—'}, props {st.props or '—'}"
            + (f", carried by characters (costume props, locked): {carried}" if carried else "")
            + (f", other props of this beat (may appear if the frame shows them): {others}" if others else ""))
    loc_rules = (cat.locations.get(st.location_id, {}) or {}).get("qa_rules") or []
    cam = (f"{s.camera.shot_size} / {s.camera.lens} / {s.camera.movement} / looks {s.camera.look_key} / "
           f"{s.camera.format}; lip-sync {s.policy.lip_sync}; face visible {s.policy.face_pass}")
    adv = [f"- {f.detail}" for f in shot.flags if not f.blocks_spend]
    i, d = shot.intent, shot.direction
    parts = []
    if include_rules and cat.production_rules():
        parts.append(cat.production_rules())
    parts += [
        "SHOT DESIGN (locked):\n" + library.design_text(cat, s.design),
        f"LOCKED WAVE-2 DESIGN:\n- cast: {cast}\n- wardrobe: {ward}\n- set: {sett}\n- camera: {cam}"
        + (f"\n- extras: {s.extras_text}" if s.extras_text else ""),
        "LOCATION RULES (locked — they outrank the Director's notes):\n"
        + ("\n".join(f"- {r}" for r in loc_rules) if loc_rules else "- none"),
        f"SCENE INTENT (Script): {i.subject} | {i.action} | {i.setting} | {i.time_of_day} | {i.mood}",
        f"DIRECTION (Director): coverage {d.coverage} | blocking {d.blocking} | performance {d.performance_note} | "
        f"pacing {d.pacing} | tone {d.tone_ref}",
        "RESEARCH ADVISORIES (unsourced period texture — keep plausible, don't over-specify):\n"
        + ("\n".join(adv) if adv else "- none"),
        f"PREVIOUS SHOT IN THE BEAT (for continuity):\n{prev_design or 'none — first shot of the beat'}",
    ]
    return "\n\n".join(parts)


class DeptAgent(Agent):
    BRIEF = ""            # key into Resolved.briefs
    TASK = ""             # the department's question + JSON schema
    RULES_IN_CONTEXT = True

    def build_user(self, shot, **ctx) -> str:
        r = ctx["resolved"]
        return (common_context(shot, ctx["cat"], r, ctx.get("prev_design", ""), self.RULES_IN_CONTEXT)
                + f"\n\nYOUR DEPARTMENT'S LIBRARY:\n{r.briefs.get(self.BRIEF, '—')}\n\nTASK:\n{self.TASK}")

    def act(self, shot, **ctx: Any) -> dict:
        user = self.build_user(shot, **ctx)
        if ctx.get("revision"):
            if ctx.get("crew"):
                user += f"\n\nTHE REST OF THE CREW'S CURRENT PREP (stay consistent with it):\n{ctx['crew']}"
            user += f"\n\nREVISE per the Studio Critic: {ctx['revision']}\nReturn the corrected JSON."
        data, usage = self.run_json(user)
        self.apply(shot, data, **ctx)
        shot.set_notes(self.NAME, [str(c) for c in (data.get("concerns") or [])])
        shot.log(self.NAME, f"wrote {self.NAME} design", cost_usd=_cost(usage, False), tokens=usage.get("total", 0))
        return usage

    def apply(self, shot, data: dict, **ctx) -> None:  # noqa: D401
        raise NotImplementedError


def _targets(shot) -> list[str]:
    return [c.character_id for c in shot.cast if c.actor_id] + [c.archetype for c in shot.crowd]


class CastingAgent(DeptAgent):
    NAME = "casting"
    BRIEF = "casting"
    RULES_IN_CONTEXT = False
    SYSTEM = _COMMON_RULES + (
        "\nYou are the Casting director. Tracked characters are already cast (locked). Your job here is the "
        "EXTRAS: turn the shot's extras line into crowd groups using the production's extras archetypes. Crowds "
        "are archetypes, never individually tracked actors; never invent a new named character.")
    TASK = (
        "Return JSON: { crowd: [ { archetype (a key from the EXTRAS ARCHETYPES list, or 'other'), count (integer, or "
        "null if the design gives none), wardrobe_id (from that archetype), wear_state (the scene's wear state unless "
        "the extras line says otherwise), note (what they look like / do, from the design) } ], concerns: [string] }. "
        "One entry per distinct group in the extras line.")

    def apply(self, shot, data, **ctx) -> None:
        r = ctx["resolved"]
        shot.crowd = []
        for c in data.get("crowd") or []:
            try:
                shot.crowd.append(CrowdEntry(
                    archetype=str(c.get("archetype") or "other"), count=c.get("count"),
                    wardrobe_id=str(c.get("wardrobe_id") or ""), wear_state=str(c.get("wear_state") or r.wear),
                    note=str(c.get("note") or "")))
            except Exception:  # noqa: BLE001 — a malformed entry is caught by Tier 1 (missing group)
                continue


class WardrobeAgent(DeptAgent):
    NAME = "wardrobe"
    BRIEF = "wardrobe"
    SYSTEM = _COMMON_RULES + (
        "\nYou are the Costume designer and Wardrobe supervisor. Costumes and wear states are locked. Decide what "
        "must READ on screen at this shot size and angle for each character and crowd group — rank insignia, "
        "character additions (glasses, kit, tools), how the wear state shows on the fabric — and flag continuity "
        "with the previous shot. A close-up shows small details; a wide shot only silhouettes and colour.")
    TASK = (
        "Return JSON: { wardrobe: [ { target (a character id like C-01, or a crowd archetype name), visible_details: "
        "[short concrete items that must be visible and correct in this frame], notes (continuity or how the wear "
        "state reads) } ], concerns: [string] }. One entry per character and crowd group in the shot (targets: "
        "{targets}).")

    def build_user(self, shot, **ctx) -> str:
        return super().build_user(shot, **ctx).replace("{targets}", ", ".join(_targets(shot)) or "none")

    def apply(self, shot, data, **ctx) -> None:
        r = ctx["resolved"]
        base = [w.model_copy() for w in r.wardrobe] + [
            WardrobeEntry(target=c.archetype, wardrobe_id=c.wardrobe_id, wear_state=c.wear_state) for c in shot.crowd]
        llm = {str(w.get("target")): w for w in (data.get("wardrobe") or []) if isinstance(w, dict)}
        for w in base:
            got = llm.get(w.target) or {}
            w.visible_details = [str(x) for x in (got.get("visible_details") or [])]
            w.notes = str(got.get("notes") or "")
        shot.wardrobe = base


class MakeupAgent(DeptAgent):
    NAME = "makeup"
    BRIEF = "makeup"
    SYSTEM = _COMMON_RULES + (
        "\nYou are the department-head Makeup artist and Hair/prosthetics designer. Everything on skin and head: "
        "grime, salt, mud, sweat, fatigue, sun, hair state. Never change an actor's signature features (face "
        "shape, moustache style, glasses). Injuries are implied, never graphic. Match the wear state: a salt-crusted "
        "uniform means salt on skin and eyebrows too.")
    TASK = (
        "Return JSON: { makeup: [ { target (character id or crowd archetype), skin_state, hair_state, injuries "
        "[usually empty; implied only], notes } ], concerns: [string] }. One entry per target: {targets}. "
        "If there are no people in the frame, return an empty list.")

    def build_user(self, shot, **ctx) -> str:
        return super().build_user(shot, **ctx).replace("{targets}", ", ".join(_targets(shot)) or "none")

    def apply(self, shot, data, **ctx) -> None:
        shot.makeup = []
        for m in data.get("makeup") or []:
            if not isinstance(m, dict) or not m.get("target"):
                continue
            shot.makeup.append(MakeupEntry(
                target=str(m["target"]), skin_state=str(m.get("skin_state") or ""),
                hair_state=str(m.get("hair_state") or ""), injuries=[str(x) for x in (m.get("injuries") or [])],
                notes=str(m.get("notes") or "")))


class SetAgent(DeptAgent):
    NAME = "set"
    BRIEF = "set"
    SYSTEM = _COMMON_RULES + (
        "\nYou are the Production designer, Set decorator and Props master. Location, vehicles and shot props are "
        "locked. Dress the world: what fills the frame (terrain, debris, vegetation, period clutter), the set's "
        "state at this moment, and which locked props are environmental vs actively handled by an actor. Static "
        "atmosphere is yours; explosions/moving smoke belong to VFX. Library-first: refer to props only by library "
        "ids; describe anything else as generic period dressing.")
    TASK = (
        "Return JSON: { props: [library ids placed in the environment], hand_props: [library ids an actor actively "
        "uses in this shot], hand_items: [items an actor actively uses that have NO library id, e.g. 'small "
        "red-filtered flashlight', 'scrap of paper' — these are library gaps], dressing: [short concrete items], "
        "set_state (one sentence), notes, concerns: [string] }. Every locked shot prop must appear in props or "
        "hand_props. You may also place props listed as 'other props of this beat' when the frame shows them. "
        "Props carried as character additions stay with Wardrobe — list them here only if an actor actively "
        "handles them in this shot.")

    def apply(self, shot, data, **ctx) -> None:
        r = ctx["resolved"]
        s = r.set.model_copy()
        ids = lambda xs: [m for x in (xs or []) for m in re.findall(r"\bPRP-\d{4}\b", str(x))]  # noqa: E731
        s.props, s.hand_props = ids(data.get("props")), ids(data.get("hand_props"))
        s.hand_items = [str(x) for x in (data.get("hand_items") or []) if str(x).strip()]
        s.dressing = [str(x) for x in (data.get("dressing") or [])]
        s.set_state = str(data.get("set_state") or "")
        s.notes = str(data.get("notes") or "")
        shot.set = s
        if s.hand_items:
            shot.set_notes("library", [f"no prop library entry yet for: {', '.join(s.hand_items)}"])


class CameraAgent(DeptAgent):
    NAME = "camera"
    BRIEF = "camera"
    SYSTEM = _COMMON_RULES + (
        "\nYou are the Director of Photography and Gaffer. Size, lens, move and look keys are locked. Design the "
        "light so it matches the locked looks and the location's light variant, and protect the frame for "
        "delivery (generate 16:9, crop to 2.39:1 — faces, eyes, hands and key action stay in the middle band). "
        "Night and low-key shots need an explicit exposure note so the image is dark but readable.")
    TASK = (
        "Return JSON: { light (key/fill/direction/colour in one or two sentences), exposure_note (required for night "
        "or low-key looks; else empty), framing_note (crop band, eyeline, what must stay readable — e.g. the mouth "
        "on lip-sync shots), concerns: [string] }.")

    def apply(self, shot, data, **ctx) -> None:
        c = ctx["resolved"].camera.model_copy()
        c.light = str(data.get("light") or "")
        c.exposure_note = str(data.get("exposure_note") or "")
        c.framing_note = str(data.get("framing_note") or "")
        shot.camera = c


class StuntAgent(DeptAgent):
    NAME = "action"
    BRIEF = "action"
    RULES_IN_CONTEXT = False
    SYSTEM = _COMMON_RULES + (
        "\nYou are the Stunt coordinator and military-action/armorer advisor. Only shots with real physical action "
        "(movement under load, weapon handling, firing, wading, crawling, fighting) need choreography; a "
        "dialogue close-up or a still insert does not. Weapon handling must be period-correct and plain; do not "
        "invent combat facts beyond the beat. Restraint cap applies.")
    TASK = (
        "Return JSON: { applies (bool), choreography (one or two sentences), weapon_handling (or empty), movement, "
        "beats: [3-5 short physical beats of the clip], safety_note (where weapons/backblast/water risk matter, else "
        "empty), concerns: [string] }. If applies is false, leave the other fields empty.")

    def apply(self, shot, data, **ctx) -> None:
        a = shot.action.model_copy()
        a.applies = bool(data.get("applies"))
        if a.applies:
            a.choreography = str(data.get("choreography") or "")
            a.weapon_handling = str(data.get("weapon_handling") or "")
            a.movement = str(data.get("movement") or "")
            a.beats = [str(x) for x in (data.get("beats") or [])]
            a.safety_note = str(data.get("safety_note") or "")
        else:
            a.choreography = a.weapon_handling = a.movement = a.safety_note = ""
            a.beats = []
        shot.action = a


DEPARTMENTS = {
    "casting": CastingAgent,
    "wardrobe": WardrobeAgent,
    "makeup": MakeupAgent,
    "set": SetAgent,
    "camera": CameraAgent,
    "action": StuntAgent,
}
