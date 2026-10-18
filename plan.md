# MTower Studio — Working Plan

**Started:** 2026-10-14 · **Owner:** Mahmoud El-Sayed · **Mode:** design-first, no deployment from this repo yet.

## Problem

MTower is a single-pipeline production engine. It works, but every job (QA, wardrobe, set, research, casting…) runs as engine code with the human as the orchestrator. The idea: re-express the studio as a **crew of specialist agents** under an **orchestrator**, so each role has isolated context, its own tools and model, independent iteration, and a clear definition of done — mirroring a real film unit.

## Principle

**Design the full crew now; deploy in waves.** The shared **shot contract** is the keystone — prove it with a small fleet before scaling to the full crew.

## Target home (decided 2026-10-14)

- **Subscription home:** external personal $700/mo tenant (confirms MTower decision D-02) — no MCAPSGov guardrails, self-service SPN creation. Build-and-prove on the current `ME-MngEnvMCAP225775` sub until the tenant move completes.
- **Foundry:** **new dedicated project** for the agent fleet inside the **existing Foundry resource** (reuse model deployments, no redeploy/quota duplication).
- **Region:** East US 2 (only US region with all required models — provider-level, not negotiable).

## Phases

| Phase | What | Status |
|---|---|---|
| 0 | **Foundation docs** (this repo): vision, architecture, agent catalog, orchestration/shot contract, landing zone, migration plan, ADRs | DONE |
| 1 | **Reference intake → Tone Bible** (per production/episode) + **shot contract v1** locked, reviewed on one real Episode-1 shot | DONE (schema v1 locked 2026-10-14; see doc 09) |
| 1.5 | **Azure landing zone DEPLOYED** — Foundry `me-eus2-mtowerstudio-fdy` + project + gpt-5.6-terra/sol + storage + NSP + budget(70%); data roles granted; healthy | DONE (2026-10-14; infra/) |
| 2 | **Wave 1 fleet** in the new Foundry project: Orchestrator + Script + Director + Research + Image QA + Studio Critic | IN PROGRESS — grounded Research (Ep1 ledger), beat-level fact check, contract store, full beat 2.4 run (9 contracts); batch Image QA agrees with MTower QA 6/6. Beat 2.4: all 9 shots prepped after policy P-01 (ADR-0003, dramatized staging) |
| 3 | **Wave 2**: casting (extras), wardrobe, makeup & hair, set decoration, camera/DoP, stunt/action + production meeting | DONE for beat 2.4 (2026-10-18) — 9/9 shots `ready_to_compose`; open: library conflicts for the human (C-04 hair, WEAR_MUD vs LOC-0003, 2.4-03b prompt, missing flashlight/paper-scrap props, red flashlight vs LOOK_NIGHT_MOON) |
| 4 | **Wave 3**: VFX, Continuity, Sound, Dialect/Language, Editor/Post (+ Marketing when needed) | pending |
| 5 | **Migrate** live production from MTower engine → Studio fleet, episode by episode | pending |

## Phase 0 checklist

- [x] Repo skeleton + README + plan.md
- [x] 00-vision.md
- [x] 01-architecture.md
- [x] 02-agent-catalog.md
- [x] 03-orchestration.md (shot contract)
- [x] 04-azure-landing-zone.md
- [x] 05-migration-plan.md
- [x] ADR-0001 (subscription/tenant home)

**Phase 0 complete 2026-10-14.** Next: review the agent catalog + shot contract, then Phase 1 (contract proof on real Episode-1 shots).

## Open questions (for the user)

1. External $700 tenant live model/quota availability in East US 2 — **unverified** (MFA-blocked during probe). Confirm via re-auth before Phase 2.
2. Final crew size: start from the ~12 proposed roles; trim or merge after the catalog review.
3. Does the orchestrator run **hosted in Foundry** (autonomous) or **locally in the engine** (human-in-loop) for Wave 1? (Recommendation in 03-orchestration.md.)


