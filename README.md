# MTower Studio — HQ

An **independent multi-agent AI film studio**: a crew of specialist agents (script, director, research, casting, wardrobe, makeup, set, camera, stunt, QA, critic, learning keeper …) coordinated by an **orchestrator**, driving its own production engine (image, face-model, video, lip-sync, voice, sound, edit) on its own Azure landing zone. First production: *Thunderbolt* («الصَّاعِقَةُ»), Episode 1 *The Romani Ambush*.

Since 2026-10-18 the studio runs **on its own**: the MTower engine, library and production data were imported once (MTower is retired after cutover; no runtime dependency — audited).

## Layout

| Path | What |
|---|---|
| [`fleet/`](fleet/README.md) | The agent crew + orchestrator (Azure Foundry gpt-5.6, Entra-only) |
| [`engine/`](engine/README.md) | Production toolchain: generation, face models (LoRA), clips, lip-sync, voice, sound, animatic, review gallery, spend ledger |
| `library/` | Actors (cards, trait vocabulary, training recipe), wardrobe, props, locations, looks, vehicles, fonts |
| `productions/thunderbolt/` | Series bible, Ep 1 development (screenplay, research ledger), pre-production (casting, shot lists), contracts |
| `knowledge/` | Studio memory (Learning Keeper): `incidents.jsonl`, `lessons.json` — reviewable, editable |
| `media/` | Local media (git-ignored): actor anchors/training sets/face models, keyframes, clips, audio |
| `infra/` | Bicep landing zone: main Foundry (East US 2), media Foundry (Sweden Central), storage, NSP, budget |
| `web/` | Studio website (HQ) |
| `docs/` | Vision, architecture, agent catalog, orchestration, landing zone, migration, ADRs, handbook |

## Navigate

| Doc | What's inside |
|---|---|
| [`docs/00-vision.md`](docs/00-vision.md) | Goals, non-goals, the design-full/deploy-phased philosophy |
| [`docs/01-architecture.md`](docs/01-architecture.md) | Target architecture + diagrams |
| [`docs/02-agent-catalog.md`](docs/02-agent-catalog.md) | Every crew agent: role, I/O, tools, model, definition of done, deployment wave |
| [`docs/03-orchestration.md`](docs/03-orchestration.md) | Orchestrator model + the **shot contract** |
| [`docs/04-azure-landing-zone.md`](docs/04-azure-landing-zone.md) | Subscription, regions, Foundry, budget, guardrails |
| [`docs/05-migration-plan.md`](docs/05-migration-plan.md) | MTower → MTower Studio |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`plan.md`](plan.md) | Working plan + phase tracker |

## Status

See [`plan.md`](plan.md). Waves 1–2 live (beat 2.4 fully designed), Learning Keeper live (60 lessons), cast audited and re-designed (Phase D).
