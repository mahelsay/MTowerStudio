# MTower Studio — Agent Fleet (`fleet/`)

The runnable agent fleet. **Wave 1** is live: the orchestrator runs a beat through Script → Research → Director with the studio-wide validation gate (Tier 1 rules + Tier 2 Studio Critic), producing a validated **shot contract** on the real Azure Foundry `gpt-5.6` deployments (Entra-only auth).

## Layout

| Path | What |
|---|---|
| `mtower_fleet/config.py` | settings + SPN auth from repo-root `.env` |
| `mtower_fleet/client.py` | Azure OpenAI client (Entra token), reasoning + vision calls, usage/cost |
| `mtower_fleet/contract.py` | the shot contract (schema v1, Pydantic) |
| `mtower_fleet/agents/` | Script (1), Director (1b), Research (2), Image QA (3), Studio Critic (3b), Wave 2 crew (4–7b), Learning Keeper (15) |
| `mtower_fleet/lessons.py`, `harvest.py` | studio memory store (incidents, lessons, advise, promote) + free harvest of engine history |
| `mtower_fleet/audit_cast.py` | cast audit + studio QA pick of portrait-edit candidates |
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
| `beat --beat-ref 2.4 --refresh-research` | re-run only the beat fact check and apply it to the saved contracts (after a policy or ledger change) | `--confirm-cost` |
| `qa --image …` | Image QA on one frame | — |
| `batch-qa [--sample N \| --all \| --shots …]` | Image QA over approved keyframes; compares human / MTower QA / studio; report in `reports/` | `--confirm-cost` |
| `design --beat-ref 2.4 [--shots …] [--redo]` | Wave 2: the crew designs prepped shots (casting → wardrobe/makeup/set/camera/action in parallel → production meeting); `--redo` also re-designs designed shots and shots escalated only by design | `--confirm-cost` |
| `lessons status\|harvest\|distill\|show\|approve\|retire\|advise` | Learning Keeper: studio memory. `harvest` (free) turns engine history into incidents; `distill` turns incidents into lessons; `advise <shot>` shows what the crew will be told | `--confirm-cost` (distill) |
| `cast-audit [ACT-…]` | Phase D: vision audit of every library actor — fit to role + production rules, anchor quality, training-set drift/defects, face-model failure rate on real shots | `--confirm-cost` |

## Learning Keeper (agent 15) — studio memory (2026-10-18)

- **Capture:** every gate failure becomes an incident in `knowledge/incidents.jsonl` — Critic revisions and escalations (Wave 1 + 2), studio Image QA fails, cast-audit findings — with what fixed it (or that it is unresolved). Engine history is harvested free.
- **Distill:** the Keeper (gpt-5.6-terra) turns incidents into lessons in `knowledge/lessons.json`: problem, cause, **prevention** (applied before generating), **check** (for QA), departments, tags. Repeats are merged.
- **Advise:** before departments work, the orchestrator gives each its matching lessons (tag match on location, props, cast, looks, lens, size); the Critic enforces RULES; Image QA verifies each lesson's check.
- **Promote:** candidate → **rule** when it recurs on ≥3 shots with a proven fix, or held up twice when applied, or the human approves (`lessons approve L-…`). Retired when it keeps failing.
- Seeded 2026-10-18 from MTower's history: 344 incidents → 60 lessons (14 rules), $0.63.

## How it behaves (2026-10-16)

- **Grounded Research.** Research and the Critic read the production's own research (series-bible rules, the episode fact-check ledger, the locked beat, character profiles, act flags). Composite characters and *(dramatized)* lines are `creative`; real people's actions must cite the ledger. Gestures that show a real person's sourced action are `dramatized` (policy P-01, ADR-0003) — allowed, logged, non-blocking.
- **Research runs once per beat.** Every shot inherits the beat's fact check (a crew fact-checks the scene, not each camera angle).
- **Escalations block.** If the Critic still wants a revision after 2 rounds, the shot is `needs_review` (a human gate), never `prepped`.
- **Image QA uses references** (casting portraits, prop photos, rank-insignia drawings), the full shot brief, and the production QA rules. Faces too small or hidden are `not_visible`, not an identity fail.
- **Costs** use real Azure meters (sol $4/$20 per 1M tokens in/out; terra ≈ half). Requests time out after 3 min and retry.

## Wave 2 — the creative crew (2026-10-18)

- **Lock first, craft second.** Cast, costumes, wear states, location (+ rules), lens and looks come deterministically from the MTower library; departments only add craft (crowd groups, visible details, makeup, dressing, light/exposure, choreography). Departments with no work (no people, no extras, inserts) are filled without a model call.
- **Precedence:** the lock outranks the Director and the scene intent. A department that follows the lock is correct; conflicts become **concerns for the human** (`department_notes`), never failures. Lock-vs-lock conflicts are reported, not punished.
- **Production meeting.** The Critic reviews all departments together (incl. cross-department fit). A pass sticks; later rounds re-judge only revised departments, and a revising department sees the rest of the crew's prep. 2 rounds, then escalate.
- **Props:** a shot's own props are required; other props of the beat are optional; a prop carried by an off-screen character never appears unattended; items with no library id go to `hand_items` (logged as a library gap).
- **Beat 2.4 result:** 9/9 `ready_to_compose`; Wave 2 spend ≈ $1.85 incl. the fix iterations (final passes ≈ $0.07–0.10 per shot).
