# MTower Studio — Agent Fleet (`fleet/`)

The runnable agent fleet. **Wave 1** is live: the orchestrator runs a beat through Script → Research → Director with the studio-wide validation gate (Tier 1 rules + Tier 2 Studio Critic), producing a validated **shot contract** on the real Azure Foundry `gpt-5.6` deployments (Entra-only auth).

## Layout

| Path | What |
|---|---|
| `mtower_fleet/config.py` | settings + SPN auth from repo-root `.env` |
| `mtower_fleet/client.py` | Azure OpenAI client (Entra token), reasoning + vision calls, usage/cost |
| `mtower_fleet/contract.py` | the shot contract (schema v1, Pydantic) |
| `mtower_fleet/agents/` | Script (1), Director (1b), Research (2), Image QA (3), Studio Critic (3b) |
| `mtower_fleet/gate.py` | Tier-1 deterministic rules + spend-block on open flags |
| `mtower_fleet/orchestrator.py` | the lifecycle runner + bounded critic-revise loop |
| `mtower_fleet/probe.py` | connectivity probe (both models) |
| `mtower_fleet/__main__.py` | CLI |

## Setup

```powershell
cd fleet
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`.env` (repo root) must hold the SPN values (`AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET/SUBSCRIPTION_ID`).
Data-plane roles must be granted (done 2026-10-14). Models: `me-eus2-gpt-5-6-terra` (reasoning), `me-eus2-gpt-5-6-sol` (vision).

## Run

```powershell
# connectivity check
.\.venv\Scripts\python.exe -m mtower_fleet.probe

# run a beat through Wave 1 (built-in Episode-1 demo)
.\.venv\Scripts\python.exe -m mtower_fleet run --demo --out sample.json

# or a custom beat
.\.venv\Scripts\python.exe -m mtower_fleet run --shot 1.4-03 --beat-ref 1.4 --beat "..."
```

## What Wave 1 proves

- The full stack works: SPN → Entra token → Azure Foundry `gpt-5.6` → agents → shot contract.
- **QA on every step** is real: the Studio Critic reviews every decision and sends it back on a fail (bounded to 2 rounds, then escalates).
- **Flags block spend**: open Research flags stop the shot before any paid generation.
- Cost and history are tracked per step.

## Commands

| Command | What it does | Spend gate |
|---|---|---|
| `probe` | both models respond (free-ish) | — |
| `run --demo` / `run --shot … --beat-ref …` | one shot through Wave 1; contract saved | — |
| `beat --beat-ref 2.4 [--resume]` | fact-check the beat once, then every shot; contracts saved to `productions/<prod>/<ep>/contracts/` | `--confirm-cost` |
| `qa --image …` | Image QA on one frame | — |
| `batch-qa [--sample N \| --all \| --shots …]` | Image QA over approved keyframes; compares human / MTower QA / studio; report in `reports/` | `--confirm-cost` |

## How it behaves (2026-10-16)

- **Grounded Research.** Research and the Critic read the production's own research (series-bible rules, the episode fact-check ledger, the locked beat, character profiles, act flags). Composite characters and *(dramatized)* lines are `creative`; real people's actions must cite the ledger.
- **Research runs once per beat.** Every shot inherits the beat's fact check (a crew fact-checks the scene, not each camera angle).
- **Escalations block.** If the Critic still wants a revision after 2 rounds, the shot is `needs_review` (a human gate), never `prepped`.
- **Image QA uses references** (casting portraits, prop photos, rank-insignia drawings), the full shot brief, and the production QA rules. Faces too small or hidden are `not_visible`, not an identity fail.
- **Costs** use real Azure meters (sol $4/$20 per 1M tokens in/out; terra ≈ half). Requests time out after 3 min and retry.
