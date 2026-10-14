"""The Orchestrator — runs a shot through the Wave-1 lifecycle with the validation gate.

Flow:  Script -> gate(intent) -> Research -> gate(research) [flags block spend]
       -> Director -> gate(direction).
Each gate = Tier 1 rules + Tier 2 Studio Critic; on a 'revise', the owning agent re-runs with the
critic's feedback (bounded rounds), then escalates to a human note if still failing.
"""
from __future__ import annotations

from . import gate
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
        for round_no in range(1, MAX_REVISE_ROUNDS + 1):
            problems = gate.tier1(shot, field)
            note = self.critic.review(shot, field)
            if not problems and note.verdict == "pass":
                self._log(f"  ✓ {field}: tier-1 clean, critic pass")
                return
            feedback = "; ".join(problems + note.reasons + note.revise_instructions) or "tighten and complete the field"
            self._log(f"  ↻ {field} revise (round {round_no}): {feedback}")
            if field == "intent" or field == "direction":
                agent.act(shot, revision=feedback, **ctx)
            elif field == "research":
                # research appends; reset then re-run with feedback
                shot.research.clear()
                shot.flags.clear()
                agent.act(shot, revision=feedback, **ctx)
        self._log(f"  ⚠ {field}: still failing after {MAX_REVISE_ROUNDS} rounds — escalate to human")

    def run_shot(self, *, shot_id: str, beat: str, production: str, episode: str, beat_ref: str, notes: str = "") -> Shot:
        shot = Shot(shot_id=shot_id, production=production, episode=episode, beat_ref=beat_ref)
        self._log(f"● Script → intent")
        self._gated(shot, self.script, "intent", beat=beat, notes=notes)
        self._log(f"● Research → facts")
        self._gated(shot, self.research, "research")
        blocks = gate.spend_blocked(shot)
        if blocks:
            self._log("  ⛔ spend blocked by open flags:")
            for b in blocks:
                self._log(f"     - {b}")
        self._log(f"● Director → coverage")
        self._gated(shot, self.director, "direction")
        shot.status = "prepped" if not shot.open_flags else "researching"
        self._log(f"● done — status={shot.status}, cost≈${shot.cost_usd_total:.4f}, "
                  f"flags={len(shot.open_flags)}")
        return shot
