# MTower Studio — Azure landing zone (`infra/`)

The new studio's own Azure home: a self-contained Foundry resource + agent-fleet project + Wave-1 model deployments + storage + budget + NSP, all as Bicep. Independent of the legacy MTower resource group, so it migrates on its own.

Design & decisions: [`../docs/04-azure-landing-zone.md`](../docs/04-azure-landing-zone.md) · [`../docs/adr/ADR-0001-subscription-tenant-home.md`](../docs/adr/ADR-0001-subscription-tenant-home.md).

## What it builds (East US 2, RG `me-eus2-mtowerstudio-rg`)

| Resource | Name | Notes |
|---|---|---|
| Foundry (AIServices S0) | `me-eus2-mtowerstudio-fdy` | keys disabled, IP firewall, system identity, project management on |
| Project | `me-eus2-mtowerstudio` | the agent fleet workspace |
| Deployment — reasoning | `me-eus2-gpt-5-6-terra` | agents (Orchestrator, Script, Director, Research, Critic, Stunt) |
| Deployment — vision | `me-eus2-gpt-5-6-sol` | Image QA + Continuity |
| Storage (StorageV2 LRS) | `meeus2mtowerstudiost01` | keys disabled, `media` container, 14-day soft delete |
| NSP (+ profile, allow-pc, 2 assoc.) | `me-eus2-mtowerstudio-nsp` | satisfies tenant SFI storage policy |
| Budget | `me-eus2-mtowerstudio-budget` | $700 ceiling, **70% alert** + forecast |
| Diagnostics | `-fdy-diag`, `-nsp-diag`, `-st-diag`, `-blob-diag` | → Log Analytics |

Image / video / speech models are added in Waves 2–3 (idle deployments cost nothing).

## Prerequisites

- **Bicep CLI** (`winget install Microsoft.Bicep`, or the standalone download the scripts assume on PATH).
- `.env` (repo root) Azure section filled in: `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`.
- The SPN has **Contributor** on the subscription (verified 2026-10-14).

## Run (PowerShell 7, from `infra/scripts/`)

| Step | Command | Who |
|---|---|---|
| 1 | `./Deploy-Studio.ps1` | Assistant — dry run (What-If); changes nothing |
| 2 | `./Deploy-Studio.ps1 -Apply` | Assistant, after you OK the What-If |
| 3 | `./Grant-StudioAccess.ps1 -Apply` | **You** (Owner — Contributor can't grant roles) |
| 4 | `./Test-Studio.ps1` | Assistant — free health check |

## Notes

- **Dry run first, always.** `-Apply` only after you review the What-If.
- Home IP changed? The firewall will lock out this PC — update `allowedIps` in `bicep/main.bicepparam` and re-deploy. (`Deploy-Studio.ps1` warns on drift.)
- Portal changes are overwritten by the next deploy — change `bicep/`, not the portal.
- A new subscription may need up to 48 h before budgets can be created; if the budget step fails, re-run later.
