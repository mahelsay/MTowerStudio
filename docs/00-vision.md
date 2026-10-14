# 00 — Vision

## What MTower Studio is

A **virtual film studio run by a crew of AI agents.** Where MTower today is one engine that a human drives step by step, MTower Studio is a **production house**: an orchestrator (the showrunner/1st AD) hands work to specialist agents — research, script, Egyptian-Arabic dialogue, casting, wardrobe, set decoration, camera, VFX, continuity, sound, and QA — each of which owns one craft, carries only its own context and references, uses its own tools and model, and signs off against a clear **definition of done**.

The output is unchanged: historically grounded episodes of *Thunderbolt* («الصَّاعِقَةُ»). What changes is **how the work is produced** — specialized, parallel, auditable, and independently improvable.

## Why agents (and not just a bigger script)

A monolithic prompt or a single engine run is cheaper and simpler, and for small coherent tasks it is the right tool. The studio is **not** a small coherent task — it is genuinely multi-disciplinary, and that is exactly where a multi-agent design earns its cost:

1. **Context isolation** — the historical-accuracy agent is not distracted by VFX rules; the wardrobe agent's window stays dense with 1967–1973 uniform references. Each agent reasons better because it carries less, more relevant context.
2. **Independent iteration & versioning** — tune the QA rubric without touching wardrobe; improve the Egyptian-Arabic voice without risking the camera logic.
3. **Right model per role** — a cheap reasoning model for research lookups, a premium vision model for QA, image models for generation. A monolith can't mix these in one call.
4. **Parallelism** — set decoration, wardrobe, and prop research for a scene run concurrently, then converge.
5. **Specialized tools & guardrails per role** — QA gets vision + a scoring rubric; research gets web/search; nobody carries a bloated toolbelt.
6. **Auditability** — "why does this frame look wrong?" traces to the agent that signed off.

The costs we accept in return: orchestration logic, an inter-agent contract, cross-boundary error handling, more tokens, and harder end-to-end debugging. The **shot contract** (see [03-orchestration.md](03-orchestration.md)) is how we keep those costs bounded.

## Goals

- Re-express the studio as an **orchestrator + specialist crew** without losing MTower's hard-won discipline (estimate → dry-run → confirm → ledger; library-first; locked script before media).
- **Preserve the library** (actors, wardrobe, locations, vehicles, props, looks) as the shared source of truth every agent reads.
- **Improve quality** on specialized subtasks through context isolation and per-role QA.
- Keep **cost control** and **approvals** at least as strong as today, enforced at the orchestrator boundary.
- Make the studio **reusable across productions**, not just Episode 1.

## Non-goals

- **Not** a rewrite of what works. The MTower engine, library schema, and provider integrations are assets to wrap, not discard.
- **Not** full autonomy. A human stays in the loop at spend, publish, and phase-gate boundaries (MTower's autonomy preference carries over).
- **Not** new resource *types* in Azure. The agent fleet runs on the existing Foundry footprint (new project, reused deployments).
- **Not** lip-sync/video innovation here — that stays on the proven fal.ai path; this repo is about orchestration, not new generation tech.
- **Not** a place for secrets, media, or production code. Design and decisions only.

## Design philosophy: design full, deploy phased

We write the **entire** crew catalog and the **full** shot contract up front, so the target is unambiguous. We **deploy in waves** so the contract is proven cheaply:

- **Wave 1** — Orchestrator + Script + Research + QA (+ one creative specialist). This is the smallest fleet that exercises the full generate → validate → regenerate loop, which is the pain point that started this whole idea.
- **Wave 2** — wardrobe, set decoration, casting, camera.
- **Wave 3** — VFX, continuity, sound, Egyptian-Arabic specialist.

Each wave only proceeds once the previous wave's contract and hand-offs are stable. Agents are cheap to add onto a good contract and expensive to retrofit onto a bad one.

## Definition of success for the foundation

- A crew catalog where any role can be implemented from its entry without re-reading this vision.
- A shot contract concrete enough that two agents written by different people compose without a meeting.
- A landing-zone and migration plan that survive the tenant move with one re-deploy.
