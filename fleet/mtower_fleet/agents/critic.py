"""Agent 3b — Studio Critic. Tier-2 reviewer of every non-image decision (reviewer != author)."""
from __future__ import annotations

from .. import client
from ..agents.base import _cost, _parse_json
from ..contract import CriticNote

# Definition-of-done per field the Critic checks against (from the agent catalog).
DOD = {
    "intent": (
        "Scene intent names subject, action, setting, time_of_day and mood; references library IDs for any "
        "location/vehicle/prop/character that has a library entry (story elements such as a message, a signal, an "
        "order or a sound are NOT props and need no ID — do not ask for one); keeps the key dramatic action of the "
        "shot; contains no invented historical fact (those are the Research agent's job)."
    ),
    "research": (
        "Every factual element in the intent (real events, places, units, equipment, numbers, real people) is "
        "verified, corrected or flagged, citing the episode fact-check ledger's IDs (SRC-xx / H-xx / D-x / A-flag). "
        "Production decisions (D-x) on disputed points count as handled. Composite characters, their personal moments "
        "and (dramatized) dialogue that paraphrases a sourced event are correctly marked 'creative', not flagged. "
        "Real people appear only through sourced actions — a real person's sourced action is 'verified', never "
        "'creative'. Per studio policy P-01, a gesture or staging that SHOWS a real person's sourced action is "
        "correctly 'dramatized' (cites the sourced event, does not block); only staging that adds an unsourced fact "
        "must be flagged. Nothing is asserted from memory without a citation. Source tiers follow the studio definition: "
        "primary = a participant/eyewitness account or the operation's documents (SRC-01, the Sa'iqa officer's "
        "account); secondary = press, encyclopedia articles, published histories; weak = unattributed/popular; a "
        "claim's tier = its strongest cited source. Production decisions (D-x) are handling notes, not evidence. "
        "Every flagged item has a flags entry. Judge substance: do not request a revision only for wording."
    ),
    "direction": (
        "Coverage, blocking, a performance note, pacing and a tone reference are present and consistent with a "
        "restrained grounded historical war drama and with the scene intent."
    ),
}


class StudioCritic:
    NAME = "critic"
    SYSTEM = (
        "You are the Studio Critic of an AI film studio — a meticulous QC lead / script supervisor. You review ONE "
        "agent's decision against that agent's definition-of-done and the scene intent. You did not write it "
        "(reviewer is never the author). Be strict but fair; judge the decision, not pixels. "
        "Output JSON: { verdict: 'pass'|'revise', reasons: [string], revise_instructions: [string] }. "
        "Pass only if the decision genuinely meets the definition-of-done."
    )

    def review(self, shot, field: str, grounding=None) -> CriticNote:
        content_obj = getattr(shot, field)
        dod = DOD.get(field, "Meets its stated purpose and is consistent with the scene intent.")
        if isinstance(content_obj, list):
            body = [x.model_dump() for x in content_obj]
            if field == "research":
                body = {"research": body, "flags": [f.model_dump() for f in shot.flags]}
        else:
            body = content_obj.model_dump() if hasattr(content_obj, "model_dump") else content_obj
        ground = ""
        if grounding is not None and not grounding.empty:
            if field == "research":
                ground = f"PRODUCTION GROUNDING (check citations and character types against this):\n{grounding.for_critic()}\n\n"
            elif field == "intent":
                ground = f"PRODUCTION GROUNDING (the beat this intent must stay true to):\n{grounding.for_intent_critic()}\n\n"
        user = (
            f"{ground}"
            f"Field under review: {field}\n"
            f"Definition of done: {dod}\n\n"
            f"Scene intent: {shot.intent.model_dump()}\n\n"
            f"The {field} to review: {body}"
        )
        messages = [
            {"role": "system", "content": self.SYSTEM + "\nRespond ONLY with a single valid JSON object."},
            {"role": "user", "content": user},
        ]
        text, usage = client.complete(messages, response_format={"type": "json_object"}, max_completion_tokens=8000)
        data = _parse_json(text)
        note = CriticNote(
            target_field=field,
            verdict=data.get("verdict", "revise"),
            reasons=data.get("reasons", []) or [],
            revise_instructions=data.get("revise_instructions", []) or [],
        )
        shot.critic.append(note)
        shot.log(self.NAME, f"reviewed {field}: {note.verdict}", cost_usd=_cost(usage, False), tokens=usage.get("total", 0))
        return note

    # ------------------------------------------------------------------ Wave 2: the production meeting
    def review_departments(self, shot, context: str, departments: list[str],
                           context_only: list[str] | tuple = ()) -> dict[str, CriticNote]:
        """One review of the Wave-2 departments: each against its definition of done, plus how they fit.
        `context_only` departments already passed: shown so conflicts can be seen, but not re-judged."""
        dods = "\n".join(f"- {d}: {WAVE2_DOD[d]}" for d in departments)
        outputs = {d: _department_output(shot, d) for d in departments}
        passed = {d: _department_output(shot, d) for d in context_only}
        user = (
            f"{context}\n\nDEFINITIONS OF DONE:\n{dods}\n- cross-department: the departments agree with each other "
            f"(a prop that motivates the light is placed by Set; a handled prop is a hand prop and matches the action; "
            f"makeup matches the wear state; nothing contradicts the scene intent or the Director).\n\n"
            f"DEPARTMENT OUTPUTS TO REVIEW:\n{outputs}\n\n"
            + (f"ALREADY APPROVED (context only — do not return verdicts for these):\n{passed}\n\n" if passed else "")
            + "Return JSON: { departments: { <name>: { verdict: 'pass'|'revise', reasons: [string], "
            "revise_instructions: [string] } }, cross_department: [string] }. Include every department listed. "
            "cross_department lists only PROBLEMS or conflicts (e.g. Director-vs-lock, department-vs-department) — "
            "leave it empty when there are none; never put confirmations or praise in it. "
            "Ask for a revision only for a real problem (missing, wrong, inconsistent, implausible, modern, graphic), "
            "never for wording.\nPRECEDENCE: the LOCKED design — casting (incl. character additions and the props "
            "they carry, e.g. a compass on a lanyard), costumes and wear states, the location and its rules, lens and "
            "looks — outranks the Director's notes and the scene intent. A department that follows the lock against "
            "the Director is CORRECT: never ask it to follow the Director. Report any Director-vs-lock conflict in "
            "cross_department instead. Props carried as character additions are locked costume props, not "
            "unauthorized props. Disagreement with the LOCKED design is not a reason to revise a department.\n"
            "IN FRAME: only the locked cast and crowd groups are in frame; never require entries for a person who is "
            "not in the locked cast (they are off-screen). LOCK vs LOCK: when two locked items conflict (e.g. a wear "
            "state's wording vs a location rule), a department that picks a reading satisfying both is CORRECT — "
            "report the conflict in cross_department for the human, never fail a department for it. Items an actor "
            "uses that have no library id belong in Set's hand_items (a library gap), not hand_props."
        )
        messages = [
            {"role": "system", "content": self.SYSTEM + "\nThis is a production meeting: you review the whole crew's "
             "prep for one shot.\nRespond ONLY with a single valid JSON object."},
            {"role": "user", "content": user},
        ]
        text, usage = client.complete(messages, response_format={"type": "json_object"}, max_completion_tokens=8000)
        data = _parse_json(text)
        got = _meeting_verdicts(data, departments)
        missing = [d for d in departments if d not in got]
        if missing:  # a format slip, not a design failure: ask once more for the missing verdicts
            retry = messages + [{"role": "assistant", "content": text}, {"role": "user", "content": (
                f"Your answer has no verdict for: {', '.join(missing)}. Return the full JSON again, with "
                f"departments as an object keyed exactly by: {', '.join(departments)}.")}]
            text2, u2 = client.complete(retry, response_format={"type": "json_object"}, max_completion_tokens=8000)
            usage = {k: usage.get(k, 0) + u2.get(k, 0) if isinstance(usage.get(k), int) else usage.get(k) for k in usage}
            data2 = _parse_json(text2)
            got = {**got, **_meeting_verdicts(data2, departments)}
            data = data2 if data2.get("cross_department") else data
        cross = [str(x) for x in (data.get("cross_department") or [])]
        notes: dict[str, CriticNote] = {}
        for d in departments:
            v = got.get(d)
            if v is None:
                note = CriticNote(target_field=d, verdict="revise",
                                  reasons=[f"critic returned no verdict for {d} (keys seen: {list(data)[:6]})"])
            else:
                verdict = str(v.get("verdict", "")).strip().lower()
                verdict = "pass" if verdict in ("pass", "approved", "approve", "ok", "accept") else "revise"
                note = CriticNote(target_field=d, verdict=verdict,
                                  reasons=[str(x) for x in (v.get("reasons") or [])],
                                  revise_instructions=[str(x) for x in (v.get("revise_instructions") or [])])
            notes[d] = note
            shot.critic.append(note)
        shot.set_notes("critic", cross)
        verdicts = ", ".join(f"{d} {n.verdict}" for d, n in notes.items())
        shot.log(self.NAME, f"production meeting: {verdicts}" + (f"; cross: {len(cross)}" if cross else ""),
                 cost_usd=_cost(usage, False), tokens=usage.get("total", 0))
        return notes


def _meeting_verdicts(data: dict, departments: list[str]) -> dict[str, dict]:
    """Normalize the meeting answer: object keyed by department, a list of {name, verdict…}, or top-level keys."""
    raw = data.get("departments", data)
    found: dict[str, object] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                found[str(item.get("name") or item.get("department") or item.get("target") or "")] = item
    elif isinstance(raw, dict):
        found = dict(raw)
    alias = {"stunt": "action", "stunt/action": "action", "stunt_action": "action", "dop": "camera",
             "camera/dop": "camera", "set decoration": "set", "set_decoration": "set", "makeup & hair": "makeup",
             "makeup_and_hair": "makeup", "makeup and hair": "makeup"}
    out: dict[str, dict] = {}
    for key, v in found.items():
        k = alias.get(str(key).strip().lower(), str(key).strip().lower())
        if isinstance(v, str):
            v = {"verdict": v}
        if not isinstance(v, dict):
            continue
        for d in departments:
            if k == d or k.startswith(d):
                out[d] = v
    return out


def _department_output(shot, d: str):
    if d == "casting":
        return {"cast (locked)": [c.model_dump() for c in shot.cast], "crowd": [c.model_dump() for c in shot.crowd]}
    if d == "wardrobe":
        return [w.model_dump() for w in shot.wardrobe]
    if d == "makeup":
        return [m.model_dump() for m in shot.makeup]
    if d == "set":
        return shot.set.model_dump()
    if d == "camera":
        return shot.camera.model_dump()
    if d == "action":
        return shot.action.model_dump()
    return None


WAVE2_DOD = {
    "casting": (
        "Every group in the extras line is a crowd entry using a production extras archetype, with the count and look "
        "the design gives; no new named characters; the locked cast is untouched."
    ),
    "wardrobe": (
        "Every character and crowd group has an entry; visible details are right for the shot size (a close-up names "
        "small items such as insignia or glasses; a wide shot does not promise detail no one can see); rank insignia "
        "and character additions from casting are kept; the wear state reads consistently with the previous shot; "
        "period-correct, nothing modern."
    ),
    "makeup": (
        "Every person in frame has an entry; skin and hair match the wear state (salt on the uniform means salt on "
        "skin); the actor's signature features are preserved; injuries are implied only, never graphic; continuity "
        "with the previous shot."
    ),
    "set": (
        "Every locked prop is placed; a library prop an actor uses in this shot is a hand prop, and an item an actor "
        "uses that has no library id is listed in hand_items; props from elsewhere in the beat may appear when the "
        "frame shows them; dressing is period-correct "
        "and plausible for the location; static atmosphere only (no explosions or moving smoke); set state fits the "
        "beat and the previous shot."
    ),
    "camera": (
        "Light matches the locked looks and the location's light; night or low-key shots have an exposure note that "
        "keeps the image dark but readable; framing keeps faces, hands and the key action in the middle band for "
        "the 2.39:1 crop; a lip-sync shot keeps the mouth readable; consistent with the Director's coverage."
    ),
    "action": (
        "'applies' is true only for real physical action; when true, choreography and beats are concrete, weapon "
        "handling is period-correct and plain, nothing invents combat facts beyond the beat, restraint is kept."
    ),
}
