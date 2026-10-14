# MTower Studio — HQ

The **architecture, agent fleet design, Azure landing zone, and migration plan** for turning the MTower AI film studio from a single-pipeline production engine into a **multi-agent virtual studio** with an orchestrator and a full specialist crew.

This repo is **planning and design only** — no production code and no generated media. The live production code and the current Episode 1 work stay in the existing [`MTower`](https://github.com/mahelsay/MTower) repo until we deliberately migrate.

## What this is

MTower today is one local Python engine driving cloud models (gpt-image, FLUX, Sora, Speech on Azure Foundry; LoRA/video on fal.ai) through a strict `estimate → dry-run → confirm → ledger` pipeline. It works: Episode 1 of *Thunderbolt* («الصَّاعِقَةُ») has a locked script, 306 shots, a trained cast, and a vision-QA step.

**MTower Studio** is the next shape: the same capabilities re-expressed as a **crew of specialist agents** (research, Egyptian-Arabic, wardrobe, set decoration, casting, camera, director, script, VFX, continuity, sound) coordinated by an **orchestrator**, each agent owning one job with its own context, tools, model, and "definition of done."

## Guiding principle: design full, deploy phased

We document the **complete** studio org now (all ~12 crew roles, the full contract). We **stand them up in waves** — orchestrator + a few agents + QA first — because the inter-agent "shot contract" is far easier to get right with 4 agents than 12.

## Navigate

| Doc | What's inside |
|---|---|
| [`docs/00-vision.md`](docs/00-vision.md) | Goals, non-goals, the design-full/deploy-phased philosophy |
| [`docs/01-architecture.md`](docs/01-architecture.md) | Target architecture + diagrams |
| [`docs/02-agent-catalog.md`](docs/02-agent-catalog.md) | Every crew agent: role, I/O, tools, model, definition of done, deployment wave |
| [`docs/03-orchestration.md`](docs/03-orchestration.md) | Orchestrator model + the **shot contract** (the keystone data schema) |
| [`docs/04-azure-landing-zone.md`](docs/04-azure-landing-zone.md) | Subscription/tenant home, region, Foundry project, budget, guardrails |
| [`docs/05-migration-plan.md`](docs/05-migration-plan.md) | MTower → MTower Studio, phased, tied to the tenant move |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`plan.md`](plan.md) | Working plan + phase tracker |

## Status

Foundation / design. Nothing deployed from this repo yet. See [`plan.md`](plan.md) for the live phase tracker.