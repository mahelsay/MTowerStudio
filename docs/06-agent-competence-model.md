# 06 — Agent Competence Model & Standing Rules

**Status:** Accepted, 2026-10-14. This is the **template every agent in the studio is built from** and the set of rules every agent obeys without exception. When we design any new agent, we fill in its four competence layers and it automatically inherits the standing rules.

## Standing studio rules (every agent, no exceptions)

1. **Validation gate on every output.** Nothing an agent writes enters the shot contract until it passes the gate — Tier 1 (rules) → Tier 2 (critic) → Tier 3 (vision QA for images). The **reviewer is never the author**. QA is not a stage at the end; it is a property of *every* step. (ADR-0002.)
2. **Library-first.** Reuse existing library assets (actors, wardrobe, locations, vehicles, props, looks) before proposing new ones.
3. **Reference, never duplicate.** Point at library IDs and look keys; never re-describe a library asset inline.
4. **Human gates are absolute.** No spending, publishing/sharing, or phase transition happens without explicit human approval.
5. **Ground facts, don't imagine them.** Any historical/technical/cultural claim must come from grounding or the Research agent, with a source — never from model memory alone.
6. **Append to history.** Every action and its cost is logged to the shot contract for audit.

## The four competence layers

Every agent gets its ability from the same four layers. Designing an agent = specifying these four.

| Layer | Real-world analogy | What it is | Where it lives |
|---|---|---|---|
| **L1 — Persona** | university degree + career | System/role prompt encoding credentials, craft, taste, genre mastery, standards, and voice. Sets the model's reasoning priors. | the agent's system prompt |
| **L2 — Knowledge / grounding** | homework, references, research dossier | Curated domain facts the agent must not hallucinate: series bible, episode research, period/country/environment grounding packs. Retrievable (RAG/knowledge tool), versioned, cited. | attached knowledge base / grounding files |
| **L3 — Tools** | equipment | Callable functions the agent can invoke: library lookup, web search, screenplay reader, Speech/tts render, vision, cost/ledger. | Foundry tool/function connections |
| **L4 — Collaborators** | the crew around them | Other agents it defers to for expertise outside its craft. Competence is **distributed** — an agent asks a peer rather than faking expertise. Hand-offs are brokered by the orchestrator via the shot contract. | the shot contract + orchestrator routing |

## Rule of thumb: which layer supplies which knowledge

- **Craft, genre, taste, structure** (how to write drama/thriller/history; how to light a night exterior) → **L1 persona.**
- **Hard facts: country specifics, period detail, environment, equipment, culture** → **L2 grounding + L4 Research agent.** Never persona memory alone.
- **Doing things** (generate, render, look up, cost) → **L3 tools.**
- **Judgment outside my craft** (dialect, continuity, coverage) → **L4 collaborators.**

## Collaboration vs QA — they are different and both always on

- **Collaboration (L4)** = *getting it right.* Peers supply knowledge or craft the agent lacks, before/while it works.
- **QA / validation (standing rule 1)** = *proving it's right.* An independent reviewer checks the finished output.

QA never substitutes for collaboration, and collaboration never skips QA. An agent that leaned on the right peers still has its output validated.

## Worked example — the Script / Scenario agent

- **L1 Persona:** veteran screenwriter, MFA in screenwriting, 20 years in historical war drama; master of drama, action, thriller, and historical structure; disciplined about a locked script, creative within it.
- **L2 Knowledge:** series bible, episode plan, fact-check docs, and a **1967–1973 Egypt grounding pack** (Sinai geography/environment, Sa'iqa doctrine, period civilian life, cultural detail).
- **L3 Tools:** screenplay reader, library ID lookup, change-log writer.
- **L4 Collaborators:** Research (facts), Egyptian-Arabic specialist (dialect), Director (coverage/shot breakdown), Continuity (cross-shot consistency).

> This same four-layer card is produced for every agent in [02-agent-catalog.md](02-agent-catalog.md).
