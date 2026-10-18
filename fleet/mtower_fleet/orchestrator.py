"""The Orchestrator — runs shots through the studio lifecycle with the validation gate.

Wave 1:  Script -> gate(intent) -> Research (once per beat) -> gate(research) [flags block spend]
         -> Director -> gate(direction).                                     => status 'prepped'
Wave 2:  library resolve (locked design) -> Casting (crowds) -> Wardrobe | Makeup | Set | Camera | Stunt
         (in parallel) -> Tier-1 rules -> Studio Critic production meeting.    => status 'ready_to_compose'
Each gate = Tier 1 rules + Tier 2 Studio Critic; on a 'revise', the owning agent re-runs with the
critic's feedback (bounded rounds), then escalates to a human note if still failing.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from . import client, gate, grounding, library
from .agents.critic import StudioCritic
from .agents.director import DirectorAgent
from .agents.research import ResearchAgent
from .agents.script import ScriptAgent
from .agents.wave2 import DEPARTMENTS, common_context
from .contract import Shot

MAX_REVISE_ROUNDS = 2
PARALLEL_DEPARTMENTS = ("wardrobe", "makeup", "set", "camera", "action")


class Orchestrator:
    def __init__(self, *, verbose: bool = True) -> None:
        self.verbose = verbose
        self.script = ScriptAgent()
        self.research = ResearchAgent()
        self.director = DirectorAgent()
        self.critic = StudioCritic()
        self.departments = {name: cls() for name, cls in DEPARTMENTS.items()}

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def _gated(self, shot: Shot, agent, field: str, **ctx) -> None:
        """Run an agent, then enforce Tier-1 rules + Tier-2 critic with bounded revise rounds."""
        agent.act(shot, **ctx)
        grounding = ctx.get("grounding")
        for round_no in range(0, MAX_REVISE_ROUNDS + 1):
            problems = gate.tier1(shot, field)
            note = self.critic.review(shot, field, grounding=grounding)
            if not problems and note.verdict == "pass":
                suffix = f" (after {round_no} revision{'s' if round_no != 1 else ''})" if round_no else ""
                self._log(f"  ✓ {field}: tier-1 clean, critic pass{suffix}")
                return
            feedback = "; ".join(problems + note.reasons + note.revise_instructions) or "tighten and complete the field"
            if round_no == MAX_REVISE_ROUNDS:
                break
            self._log(f"  ↻ {field} revise (round {round_no + 1}): {feedback[:400]}{'…' if len(feedback) > 400 else ''}")
            if field == "research":
                # research appends; reset then re-run with feedback
                shot.research.clear()
                shot.flags.clear()
            agent.act(shot, revision=feedback, **ctx)
        self._log(f"  ⚠ {field}: still failing after {MAX_REVISE_ROUNDS} revisions — escalate to human")
        shot.escalations.append(f"{field}: critic still requests revision after {MAX_REVISE_ROUNDS} rounds — "
                                f"{feedback[:300]}")

    def run_shot(self, *, shot_id: str, beat: str, production: str, episode: str, beat_ref: str, notes: str = "",
                 g: "grounding.Grounding | None" = None, beat_research: Shot | None = None) -> Shot:
        shot = Shot(shot_id=shot_id, production=production, episode=episode, beat_ref=beat_ref)
        g = g or grounding.load(production, episode, beat_ref)
        design = grounding.find_shot(production, episode, shot_id)
        if g.empty:
            self._log("  (no production grounding found — Research cannot verify anything)")
        elif beat_research is None:
            self._log(f"  grounding: beat {beat_ref} text, {len(g.character_ids)} character profiles, fact-check ledger")
        self._log(f"● Script → intent")
        self._gated(shot, self.script, "intent", beat=g.beat_text or beat, shot_design=design, notes=notes, grounding=g)
        if beat_research is not None:
            self._inherit(shot, beat_research)
            self._log(f"● Research → inherited from beat {beat_ref} ({len(shot.research)} claims)")
        else:
            self._log(f"● Research → facts")
            self._gated(shot, self.research, "research", grounding=g)
        blocks = gate.spend_blocked(shot)
        if blocks:
            self._log("  ⛔ spend blocked by open flags:")
            for b in blocks:
                self._log(f"     - {b}")
        advisories = [f for f in shot.flags if not f.blocks_spend]
        if advisories and beat_research is None:
            self._log(f"  ⓘ {len(advisories)} advisory flag(s) (don't block spend; for Wardrobe/Image QA to watch)")
        self._log(f"● Director → coverage")
        self._gated(shot, self.director, "direction", shot_design=design)
        shot.wave_ready = max(shot.wave_ready, 1)
        self._settle(shot)
        self._log(f"● done — status={shot.status}, cost≈${shot.cost_usd_total:.4f}, "
                  f"blocking flags={len(shot.open_flags)}, advisory={len(advisories)}, "
                  f"escalations={len(shot.escalations)}")
        return shot

    @staticmethod
    def _settle(shot: Shot) -> None:
        if shot.escalations:
            shot.status = "needs_review"  # a human gate: the critic could not be satisfied
        elif shot.open_flags:
            shot.status = "researching"
        else:
            shot.status = "ready_to_compose" if shot.wave_ready >= 2 else "prepped"

    @staticmethod
    def _inherit(shot: Shot, beat: Shot) -> None:
        """Replace a shot's research with its beat's fact check (drops any earlier beat-level escalations)."""
        prefix = f"beat {beat.beat_ref} "
        shot.research = [c.model_copy() for c in beat.research]
        shot.flags = [f.model_copy() for f in beat.flags]
        shot.escalations = [e for e in shot.escalations if not e.startswith(prefix)]
        shot.escalations += [f"{prefix}{e}" for e in beat.escalations]
        shot.log("research", f"inherited beat {beat.beat_ref} fact check ({len(shot.research)} claims)")

    def refresh(self, shot: Shot, beat: Shot) -> Shot:
        """Apply a new beat fact check to an existing shot contract (Script/Director don't read research)."""
        self._inherit(shot, beat)
        self._settle(shot)
        return shot

    def research_beat(self, *, production: str, episode: str, beat_ref: str, g: "grounding.Grounding") -> Shot:
        """Fact-check the whole locked beat once; every shot in the beat inherits the result."""
        beat = Shot(shot_id=f"beat-{beat_ref}", production=production, episode=episode, beat_ref=beat_ref)
        title = g.beat_text.splitlines()[0].lstrip("# ").strip() if g.beat_text else beat_ref
        beat.intent.subject = title
        beat.intent.action = "Everything that happens in this beat, exactly as written in the locked screenplay (provided)."
        beat.intent.setting = "As written in the beat's scene heading."
        beat.intent.time_of_day = "As written in the beat's scene heading."
        beat.intent.mood = "As written."
        self._log(f"● Research → whole beat {beat_ref} (once, shared by every shot)")
        self._gated(beat, self.research, "research", grounding=g)
        return beat

    def run_beat(self, *, production: str, episode: str, beat_ref: str, shot_ids: list[str] | None = None,
                 on_shot=None, on_beat=None, beat_research: Shot | None = None) -> tuple[Shot, list[Shot]]:
        g = grounding.load(production, episode, beat_ref)
        ids = shot_ids or grounding.beat_shot_ids(production, episode, beat_ref)
        self._log(f"Beat {beat_ref}: {len(ids)} shot(s) · grounding: {len(g.character_ids)} character profiles, "
                  f"fact-check ledger")
        if beat_research is not None:
            beat = beat_research
            self._log(f"● Research → reusing saved beat {beat_ref} fact check ({len(beat.research)} claims)")
        else:
            beat = self.research_beat(production=production, episode=episode, beat_ref=beat_ref, g=g)
            if on_beat:
                on_beat(beat)  # persist immediately so a crash mid-beat doesn't lose the fact check
        shots = []
        for n, sid in enumerate(ids, 1):
            self._log(f"\n── Shot {sid} ({n}/{len(ids)}) ──")
            s = self.run_shot(shot_id=sid, beat="", production=production, episode=episode, beat_ref=beat_ref,
                              g=g, beat_research=beat)
            shots.append(s)
            if on_shot:
                on_shot(s)
        return beat, shots

    # ================================================================== Wave 2 — the creative crew

    def design_shot(self, shot: Shot, prev: Shot | None = None) -> Shot:
        """Turn a prepped shot into a fully designed one: locked design from the library + department craft."""
        cat = library.catalog(shot.production, shot.episode)
        design = grounding.find_shot(shot.production, shot.episode, shot.shot_id)
        if design is None:
            shot.escalations.append(f"design: shot {shot.shot_id} not found in the shot lists")
            self._settle(shot)
            return shot
        resolved = library.resolve(cat, design)
        shot.cast = [c.model_copy() for c in resolved.cast]
        shot.generation_policy = resolved.policy.model_copy()
        shot.escalations = [e for e in shot.escalations if not e.startswith("design")]
        if resolved.problems:
            for p in resolved.problems:
                self._log(f"  ⛔ library: {p}")
            shot.escalations.append("design: library integrity — " + "; ".join(resolved.problems))

        people = bool([c for c in resolved.cast if c.actor_id]) or bool(resolved.extras_text)
        insert = (resolved.camera.shot_size or "").upper() in ("INSERT", "CARD")
        prev_text = design_summary(prev) if prev is not None else ""
        ctx = {"resolved": resolved, "cat": cat, "prev_design": prev_text}

        def deterministic(name: str) -> bool:
            if name == "casting":
                return not resolved.extras_text
            if name in ("makeup", "wardrobe"):
                return not people
            if name == "action":
                return insert or not people
            return False

        def fill_deterministic(name: str) -> None:
            if name == "casting":
                shot.crowd = []
            elif name == "makeup":
                shot.makeup = []
            elif name == "wardrobe":
                shot.wardrobe = []
            elif name == "action":
                shot.action.applies = False

        def run(name: str, revision: str = "") -> None:
            if deterministic(name):
                fill_deterministic(name)
                shot.log(name, f"no {name} work in this shot (resolved without a model)")
                return
            extra = {"revision": revision, "crew": crew_minutes(shot, exclude=name)} if revision else {}
            self.departments[name].act(shot, **ctx, **extra)

        def run_parallel(names: list[str], revisions: dict[str, str] | None = None) -> None:
            revisions = revisions or {}
            with ThreadPoolExecutor(max_workers=len(names) or 1) as pool:
                list(pool.map(lambda n: run(n, revisions.get(n, "")), names))

        def tier1_fix(names: list[str]) -> None:
            """Free rules first; one targeted re-run for a department that breaks them."""
            failing = {n: gate.tier1_wave2(shot, n, resolved, cat) for n in names}
            failing = {n: p for n, p in failing.items() if p and not deterministic(n)}
            if failing:
                for n, p in failing.items():
                    self._log(f"  ↻ {n} tier-1: {'; '.join(p)[:200]}")
                fix = [n for n in failing if n != "casting"]
                if "casting" in failing:
                    run("casting", "; ".join(failing["casting"]))
                run_parallel(fix, {n: "; ".join(failing[n]) for n in fix})

        client.get_client()  # resolve the endpoint once before the parallel calls
        self._log("● Casting → crowds" + ("" if resolved.extras_text else " (no extras — no model call)"))
        run("casting")
        tier1_fix(["casting"])
        self._log(f"● Departments → {', '.join(PARALLEL_DEPARTMENTS)} (in parallel)")
        run_parallel(list(PARALLEL_DEPARTMENTS))
        tier1_fix(list(PARALLEL_DEPARTMENTS))

        reviewed = [n for n in ("casting",) + PARALLEL_DEPARTMENTS if not deterministic(n)]
        context = common_context(shot, cat, resolved, prev_text)
        to_review = list(reviewed)          # passes stick: a department is re-judged only after it is revised
        for round_no in range(0, MAX_REVISE_ROUNDS + 1):
            hard = {n: gate.tier1_wave2(shot, n, resolved, cat) for n in to_review}
            hard = {n: p for n, p in hard.items() if p}
            approved = [n for n in reviewed if n not in to_review]
            notes = self.critic.review_departments(shot, context, to_review, context_only=approved)
            revise = {n: "; ".join(hard.get(n, []) + nt.reasons + nt.revise_instructions)
                      for n, nt in notes.items() if nt.verdict != "pass" or n in hard}
            if not revise:
                suffix = f" (after {round_no} revision{'s' if round_no != 1 else ''})" if round_no else ""
                self._log(f"  ✓ production meeting: all departments pass{suffix}")
                break
            if round_no == MAX_REVISE_ROUNDS:
                for n, fb in revise.items():
                    self._log(f"  ⚠ {n}: still failing after {MAX_REVISE_ROUNDS} revisions — escalate to human")
                    shot.escalations.append(f"design {n}: critic still requests revision — {fb[:300]}")
                break
            self._log(f"  ↻ meeting round {round_no + 1}: revise {', '.join(revise)}")
            revised = set(revise)
            if "casting" in revise:
                run("casting", revise.pop("casting"))
                for dep in ("wardrobe", "makeup"):  # their targets follow the crowd
                    if dep in reviewed:
                        revise.setdefault(dep, "the crowd groups changed; update your entries to match")
                        revised.add(dep)
            run_parallel(list(revise), revise)
            to_review = [n for n in reviewed if n in revised]

        shot.wave_ready = max(shot.wave_ready, 2)
        self._settle(shot)
        if shot.department_notes:
            self._log(f"  ⓘ {len(shot.department_notes)} department concern(s) about the locked design (for you)")
        self._log(f"● designed — status={shot.status}, cost≈${shot.cost_usd_total:.4f}, "
                  f"escalations={len(shot.escalations)}")
        return shot

    def design_beat(self, shots: list[Shot], on_shot=None, prev: Shot | None = None) -> list[Shot]:
        """Design a beat's shots in shot-list order; each shot sees the previous one for continuity."""
        out = []
        for n, s in enumerate(shots, 1):
            self._log(f"\n── Design {s.shot_id} ({n}/{len(shots)}) ──")
            self.design_shot(s, prev=prev)
            out.append(s)
            prev = s
            if on_shot:
                on_shot(s)
        return out


def crew_minutes(s: Shot, exclude: str = "") -> str:
    """The other departments' current prep for this shot (given to a department while it revises)."""
    parts = {
        "casting": f"crowd: {[c.model_dump() for c in s.crowd]}",
        "wardrobe": f"wardrobe: {[{'target': w.target, 'visible': w.visible_details} for w in s.wardrobe]}",
        "makeup": f"makeup: {[{'target': m.target, 'skin': m.skin_state, 'hair': m.hair_state} for m in s.makeup]}",
        "set": f"set: props {s.set.props}, hand props {s.set.hand_props}, hand items {s.set.hand_items}, "
               f"dressing {s.set.dressing}, state {s.set.set_state}",
        "camera": f"camera: light {s.camera.light}; exposure {s.camera.exposure_note}; framing {s.camera.framing_note}",
        "action": f"action: {s.action.model_dump()}",
    }
    return "\n".join(f"- {v}" for k, v in parts.items() if k != exclude)


def design_summary(s: Shot | None) -> str:
    """What the next shot's departments need to stay continuous with this one."""
    if s is None or s.wave_ready < 2:
        return ""
    ward = "; ".join(f"{w.target} {w.wardrobe_id}/{w.wear_state}: {', '.join(w.visible_details[:4])}"
                     for w in s.wardrobe)
    mk = "; ".join(f"{m.target}: skin {m.skin_state}; hair {m.hair_state}" for m in s.makeup)
    return (f"{s.shot_id} ({s.camera.shot_size}, {s.camera.lens})\n- wardrobe: {ward or '—'}\n- makeup: {mk or '—'}"
            f"\n- set state: {s.set.set_state or '—'}; hand props: {s.set.hand_props or '—'}\n"
            f"- light: {s.camera.light or '—'}")
