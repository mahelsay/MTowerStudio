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

    def run_shot(self, *, shot_id: str, beat: str, production: str, episode: str, beat_ref: str, notes: str = "") -> Shot:
        shot = Shot(shot_id=shot_id, production=production, episode=episode, beat_ref=beat_ref)
        g = grounding.load(production, episode, beat_ref)
        design = grounding.find_shot(production, episode, shot_id)
        if g.empty:
            self._log("  (no production grounding found — Research cannot verify anything)")
        else:
            self._log(f"  grounding: beat {beat_ref} text, {len(g.character_ids)} character profiles, fact-check ledger")
        self._log(f"● Script → intent")
        self._gated(shot, self.script, "intent", beat=g.beat_text or beat, shot_design=design, notes=notes, grounding=g)
        self._log(f"● Research → facts")
        self._gated(shot, self.research, "research", grounding=g)
        blocks = gate.spend_blocked(shot)
        if blocks:
            self._log("  ⛔ spend blocked by open flags:")
            for b in blocks:
                self._log(f"     - {b}")
        advisories = [f for f in shot.flags if not f.blocks_spend]
        if advisories:
            self._log(f"  ⓘ {len(advisories)} advisory flag(s) (don't block spend; for Wardrobe/Image QA to watch)")
        self._log(f"● Director → coverage")
        self._gated(shot, self.director, "direction")
        shot.status = "prepped" if not shot.open_flags else "researching"
        self._log(f"● done — status={shot.status}, cost≈${shot.cost_usd_total:.4f}, "
                  f"blocking flags={len(shot.open_flags)}, advisory={len(advisories)}")
        return shot
