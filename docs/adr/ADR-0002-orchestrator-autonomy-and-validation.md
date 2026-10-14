# ADR-0002 — Orchestrator autonomy, hosting, and the studio-wide validation layer

- **Status:** Accepted
- **Date:** 2026-10-14
- **Deciders:** Mahmoud El-Sayed (owner)
- **Related:** [01-architecture.md](../01-architecture.md), [03-orchestration.md](../03-orchestration.md), [02-agent-catalog.md](../02-agent-catalog.md)

## Context

Reviewing Agent 0 (the Orchestrator) one-on-one, four decisions were made about how it runs and how quality is enforced across the whole fleet.

## Decisions

1. **Supervised autonomy, earned over time.** The orchestrator starts in a checkpoint-heavy mode: it stops for the owner at every milestone, taste call, or green-light moment — not only at spend/publish/phase gates. Checkpoints are dialed down per-agent as trust is established.

2. **Hosted on Azure Foundry from day one** (not engine-local first). Professional target shape: managed threads, run traces, parallelism, unattended scheduling. **Dependency:** the MTower engine's cost-control and library functions must be exposed to the hosted orchestrator as callable tools (Foundry tool/function connections) before it goes live.

3. **Budget alert at 70% of the subscription budget** (~$490 on the $700 tenant), in addition to forecast alerts. Applied at deploy time (no resources in the new project/tenant yet). Supersedes MTower's 50/80/100 pattern for the studio.

4. **Studio-wide validation layer ("QA on every step").** No agent output is accepted into the shot contract until it passes a gate. Three tiers:
   - **Tier 1 — Rules (deterministic, free, every write):** schema valid, library IDs resolve, required fields present, no open research flags, cost within cap.
   - **Tier 2 — Critic (cheap LLM, every judgment call):** an independent reviewer persona checks the decision against the agent's definition-of-done and the shot intent; returns pass / revise-with-reasons.
   - **Tier 3 — Vision QA (the QA agent, every image):** anatomy, identity, period, props, physics, light.
   - **Invariant:** the reviewer is never the agent that produced the output. Bounded revise rounds, then human escalation.

## Consequences

- **Positive:** quality is enforced uniformly, not just on final frames; errors are caught at the step that produced them; fully auditable.
- **Negative / cost:** Tier 2 adds latency and cheap token spend per decision; mitigated by tiering (Tier 1 does most of the work for free). The tier-2 scope (every decision vs only consequential ones) is a tunable dial.
- **Dependency:** engine functions wrapped as Foundry tools before the orchestrator is hosted.
