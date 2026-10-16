"""The Orchestrator — runs a shot through the Wave-1 lifecycle with the validation gate.

Flow:  Script -> gate(intent) -> Research -> gate(research) [flags block spend]
       -> Director -> gate(direction).
Each gate = Tier 1 rules + Tier 2 Studio Critic; on a 'revise', the owning agent re-runs with the
critic's feedback (bounded rounds), then escalates to a human note if still failing.
"""
from __future__ import annotations

from . import gate, grounding
from .agents.critic import StudioCritic
from .agents.director import DirectorAgent
from .agents.research import ResearchAgent
from .agents.script import ScriptAgent
from .contract import Shot

MAX_REVISE_ROUNDS = 2


class Orchestrator:
    def __init__(self, *, verbose: bool = True) -> None:
        self.verbose = verbose
        self.script = ScriptAgent()
        self.research = ResearchAgent()
        self.director = DirectorAgent()
        self.critic = StudioCritic()

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
            shot.research = [c.model_copy() for c in beat_research.research]
            shot.flags = [f.model_copy() for f in beat_research.flags]
            shot.escalations += [f"beat {beat_ref} {e}" for e in beat_research.escalations]
            shot.log("research", f"inherited beat {beat_ref} fact check ({len(shot.research)} claims)")
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
        self._gated(shot, self.director, "direction")
        if shot.escalations:
            shot.status = "needs_review"  # a human gate: the critic could not be satisfied
        else:
            shot.status = "prepped" if not shot.open_flags else "researching"
        self._log(f"● done — status={shot.status}, cost≈${shot.cost_usd_total:.4f}, "
                  f"blocking flags={len(shot.open_flags)}, advisory={len(advisories)}, "
                  f"escalations={len(shot.escalations)}")
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
