"""Agent 2 — Research / Fact-check. The universal fact desk; flags block spend.

Grounded (L2) in the production's own research: series-bible rules, the episode fact-check
ledger (SRC-xx / H-xx / D-x), the locked beat, character profiles and the act's historical flags.
"""
from __future__ import annotations

from .base import Agent
from ..contract import Flag, ResearchClaim

_RULES = (
    "You are the Research/Fact-check agent of an AI film studio — the universal fact desk. You verify EVERYTHING "
    "real: history, geography, places, culture, technical/military detail. You never assert from memory alone.\n\n"
    "HOW TO JUDGE A SCENE (apply the production's own rules, provided as grounding):\n"
    "1. Factual claims about real events, places, units, equipment, numbers and real people must be matched to the "
    "   episode fact-check ledger. Cite the ledger's IDs in `source` (e.g. 'SRC-01; H-07; A2-03'). If the ledger "
    "   records a production decision on a disputed point (D-x), the scene following that decision is VERIFIED with "
    "   a note naming the decision — the dispute is already handled by the end-card source note.\n"
    "2. Source tiers: 'primary' = the operation's own documentation or an eyewitness account from a participant "
    "   (SRC-01, the Sa'iqa officer's account based on unit documents); 'secondary' = reputable press, encyclopedia "
    "   articles, published histories; 'weak' = unattributed or popular-only accounts.\n"
    "3. COMPOSITE characters are fictional by design (series bible §4.1.3). Their existence, names, personal "
    "   moments and look are verdict 'creative' — NOT flagged. Only flag a composite if they take credit for a "
    "   specific documented act of a real person.\n"
    "4. REAL people may appear only through actions stated in the sources. A real person shown doing something the "
    "   sources don't state = flag.\n"
    "5. Dialogue marked *(dramatized)* that paraphrases a sourced event = 'creative' (cite the event's H-xx).\n"
    "6. Period equipment and texture (e.g. a Soviet-pattern manpack radio, red-light discipline at night, uniform "
    "   cut) — if the ledger doesn't cover it, verdict 'flagged' with tier 'none' unless you can name a real, "
    "   specific source. Mark it blocks_spend=false when it is general period texture with no claim about a real "
    "   person or event (a low-risk visual detail for the Image QA and Wardrobe agents to watch), and "
    "   blocks_spend=true when getting it wrong would misrepresent a documented event.\n"
    "7. Anything that contradicts the ledger or the series bible = flag with blocks_spend=true.\n"
    "8. When checking a WHOLE BEAT: write one claim for EACH distinct on-screen action of a REAL person (each must "
    "   be verified against a ledger ID, or flagged). A real person's action that paraphrases a sourced event is "
    "   'verified' (cite the event), never 'creative'. Group each COMPOSITE character's actions and dialogue into a "
    "   'creative' claim that names the composite. Cover every action in the beat.\n"
    "9. Tier = the tier of the strongest source you cite; list every source ID in `source`. A production decision "
    "   (D-x) is a handling decision, not evidence — mention it in `note`, never as the source or tier.\n\n"
    "Output JSON with keys:\n"
    "  research: array of { claim, verdict (verified|corrected|flagged|creative), tier (primary|secondary|weak|none), "
    "source, note }\n"
    "  flags: array of { kind (anachronism|inaccuracy|unverifiable|sensitivity), detail, blocks_spend (bool) }\n"
    "Every flagged research item must have a matching entry in flags. Keep claims specific to what is in the scene."
)


class ResearchAgent(Agent):
    NAME = "research"
    SYSTEM = _RULES

    def build_user(self, shot, **ctx) -> str:
        i = shot.intent
        grounding = ctx.get("grounding")
        scene = (
            f"SCENE INTENT TO FACT-CHECK (beat {shot.beat_ref}):\n"
            f"- subject: {i.subject}\n- action: {i.action}\n- setting: {i.setting}\n"
            f"- time_of_day: {i.time_of_day}\n- mood: {i.mood}\n- refs: {i.refs}"
        )
        if grounding is not None and not grounding.empty:
            return f"{grounding.for_research()}\n\n{scene}"
        return scene + "\n\n(No production grounding available — you may not verify anything from memory.)"

    def apply(self, shot, data) -> None:
        for c in data.get("research", []) or []:
            try:
                shot.research.append(ResearchClaim(**{
                    "claim": c.get("claim", ""),
                    "verdict": c.get("verdict", "flagged"),
                    "tier": c.get("tier", "none"),
                    "source": c.get("source", ""),
                    "note": c.get("note", ""),
                }))
            except Exception:
                continue
        for f in data.get("flags", []) or []:
            try:
                shot.flags.append(Flag(**{
                    "kind": f.get("kind", "unverifiable"),
                    "detail": f.get("detail", ""),
                    "blocks_spend": bool(f.get("blocks_spend", True)),
                }))
            except Exception:
                continue
        shot.status = "prepping" if not shot.open_flags else "researching"
