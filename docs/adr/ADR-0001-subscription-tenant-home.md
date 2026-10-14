# ADR-0001 — Subscription & tenant home for MTower Studio

- **Status:** Proposed (pending external-tenant live verification)
- **Date:** 2026-10-14
- **Deciders:** Mahmoud El-Sayed (owner), with assistant feasibility probe
- **Related:** MTower decision D-02; [04-azure-landing-zone.md](../04-azure-landing-zone.md)

## Context

MTower Studio needs a permanent Azure home. Candidates visible from the studio PC:

- **MCAPS-Hybrid-REQ-37883** (`ce60eb14`) — Microsoft tenant `f2c3093b`, ~"$3k/mo". No direct role at sub scope (inherited only).
- **ME-MngEnvMCAP225775** (`ac25e0cf`) — Microsoft tenant `f2c3093b`. Current MTower home; owner holds **Owner + User Access Administrator (root)**.
- **External personal tenant** (`973659a7` / `cbade9a5`), ~"$700/mo". MFA-blocked during the probe (not yet verified live).

Live findings (2026-10-14):
- **East US 2** is required (only US region with all needed models) — identical across all subs, so region does not discriminate.
- Both Microsoft-tenant subs carry **MCAPSGov Deny/Audit/Deploy** guardrails (the family that forced MTower's NSP workaround via policy SFI-NS2.2.1).
- **SPN creation is an Entra/tenant permission.** The Microsoft tenant does not allow self-service app registration ("a new SPN will be provided"); the owner's **own external tenant does**.
- Cost: the agent fleet adds mostly **cheap text tokens**; the full crew fits **$700**.

## Decision

**Make the external personal $700/mo tenant the permanent home** (confirming MTower D-02). Use the current `ME-MngEnvMCAP225775` sub as the **build-and-prove** environment until the planned **tenant move** relocates the subscription to the external tenant.

## Options considered

1. **MCAPS $3k Microsoft sub** — rejected: wrong governance home for a personal creative project; carries MCAPSGov guardrails; no self-service SPN; budget headroom not needed.
2. **Stay on `ME-MngEnv` indefinitely** — rejected as *permanent*: still Microsoft-tenant (guardrails, no SPN self-service), though it is the right *interim* build environment.
3. **External $700 tenant** — **chosen**: personal project on personal GitHub; ample pay-per-use budget; no gov guardrails; self-service SPN creation removes a concrete future blocker.

## Consequences

- **Positive:** correct governance separation; fewer policy blockers; self-managed identity; migrates via the existing `studio/infra` Bicep in one re-deploy (MTower runbook §4).
- **Negative / risk:** external-tenant **model availability + quota in East US 2 is unverified** (MFA-blocked) — must be confirmed before the tenant move / Phase C.
- **Follow-up:** re-auth to the external tenant and verify; then extend Bicep with the new `studio` Foundry project and migrate.

## Open verification (blocking the move, not the design)

- [ ] Re-auth past MFA to the external tenant.
- [ ] Confirm East US 2 hosts the required model deployments there.
- [ ] Confirm quota is sufficient (gpt-image ≥ current).
- [ ] Confirm app-registration (SPN) self-service.
