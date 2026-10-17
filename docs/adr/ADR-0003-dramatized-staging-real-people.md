# ADR-0003 — Dramatized staging of real people (policy P-01)

- **Status:** Accepted
- **Date:** 2026-10-17
- **Decider:** Mahmoud El-Sayed (owner)
- **Related:** MTower series bible §4.1 (history and real people); [02-agent-catalog.md](../02-agent-catalog.md) Research agent; `fleet/mtower_fleet/grounding.py` (`STUDIO_POLICIES`)

## Context

The series bible says real people "appear only through actions stated in our sources" (§4.1.2), and allows reconstructed dialogue marked *(dramatized)* (§4.1.4). It says nothing about the *physical staging* of a sourced action.

On beat 2.4 ("The intercepted signal"), the sources (SRC-01 / H-07) state that Captain Hamdi Shalabi ordered radio silence and changed route after the interception warning. The locked screenplay shows how: he taps the dead set, draws a finger across his lips, raises his compass and sets a new bearing. The grounded Research agent correctly verified the orders, but flagged the gestures as unsourced — blocking all 9 shots of the beat on staging alone.

## Decision

**P-01 — Dramatized staging is allowed.** On-screen gestures, blocking and physical business that *show* a real person carrying out an action or order that **is** stated in the sources are allowed as dramatized staging, the visual equivalent of *(dramatized)* dialogue.

- Research marks them with a new verdict, **`dramatized`**, citing the sourced event (`H-xx`). They never block spend.
- They stay **visible** in every shot contract (not folded into `verified`), so an editor or fact-checker can audit them before release.
- **Limit:** staging may not add a fact the sources don't state — no new decision, event, outcome, number, private life, motive or credit. Staging that implies something unsourced is still `flagged` and blocks spend.

## Enforcement

| Layer | Rule |
|---|---|
| Research agent | rules 4 and 8: sourced action = `verified`; its on-screen gesture = `dramatized`; unsourced added fact = `flagged` |
| Studio Critic | definition of done accepts `dramatized` for sourced actions and rejects staging that adds facts |
| Tier-1 gate | a `dramatized` claim without an `H-xx` citation fails automatically |
| Grounding | the policy text is given to Research and the Critic alongside the series bible |

## Consequences

- Beats that dramatize documented actions are no longer blocked on choreography.
- The release checklist should review all `dramatized` claims alongside the end-card source note.
- **Follow-up for the owner:** add one line to the MTower series bible §4.1 so the legacy engine and human writers follow the same rule (this repo does not edit MTower).
