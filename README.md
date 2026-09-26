# Hotel AgentOps Simulation

A working, auditable simulation of the governed multi-agent operating system from my case study
**Agentic AI for Sustainable Hospitality**. Developed in the MIT executive program
*Implementing Agentic AI: Building Your Organizational Playbook*.

> **This is a modeled simulation.**
> - No hotel system is connected.
> - Scenario data is labeled **MODELED SIMULATION DATA**.
> - No result here is realized hotel performance.

The case study designed the system and modeled the business case. This project runs it. You can follow one AI decision through the whole loop:

```
HOTEL DATA → CONTEXT → SPECIALIST AGENTS → ORCHESTRATOR → RECOMMENDATION → GOVERNANCE CHECK
→ HUMAN APPROVAL (if required) → ACTION → ACTUAL OUTCOME → AGENTOPS → READINESS GATE
```

## Run it (Python 3.9+, standard library only; tested on 3.11)

```bash
python -m hotel_agentops_sim demo            # full day + 3 failure tests + failure-mode matrix
python -m hotel_agentops_sim run             # interactive: you are the F&B manager (Approve / Modify / Reject / More context)
python -m hotel_agentops_sim trace D-0418    # follow one decision: input → agent → governance → human → action → outcome → KPI
python -m hotel_agentops_sim test tool-reliability   # or missing-context, guest-score
python -m hotel_agentops_sim failure-matrix  # all 10 failure modes from the case study, executed
python -m unittest -v                        # 20 tests of the governance guarantees
```

Every run writes the following to `runs/<name>/`:
- `decision_log.csv`: one row per material decision, with the 24 required columns
- `outcomes.csv`: prediction vs actual for each service
- `override_learning.csv`
- `agentops_summary.json`
- `traces/<Decision ID>.json`

A sample run is in [`sample_output/`](sample_output).

## What the first decision shows (D-0418, Saturday breakfast)

The Demand Agent derives **420 expected covers** from 231 of 250 occupied rooms and the last four Saturdays. That is **+12%** on last week.

- **Waste Agent:** finds chronic pastry overproduction (leftover above 20% in 4 of the last 4 Saturdays) and repeated hot-line stockouts.
- **Production Agent:** drafts **−12.2%** overall. It raises the hot line **+14%** and cuts pastry **−34%**.
- **Orchestrator:** detects that demand and production point in opposite directions. It resolves the conflict with the waste evidence.
- **Governance:** the change exceeds the ±10% delegated range, so risk is **MEDIUM** and the decision goes to the manager. Confidence is 92.7%, but high confidence does not grant authority.
- **Outcome:** **409 actual covers against 420 predicted, a 2.7% error.** This matches the decision trace in the case study. Waste is 23.3 kg against 47.3 kg on the kitchen's standing plan, with no stockouts.

The case study's illustration shows −14%. The simulation computes −12.2% from its inputs, and I kept the computed number rather than tuning inputs to match.

## Where each rule lives (inspect it)

| Case-study rule | Code |
|---|---|
| Four specialists, each with only the access its role needs | `agents/*.py`: `READS` / `WRITES`. `context.AgentView` raises on any other read. |
| Production Agent reads the approved plan only and writes within threshold | `agents/production.py`: `draft()` reads no raw data. `execute()` raises without an authorization. |
| Orchestrator coordinates, with no unrestricted purchasing | `orchestrator.py`, and `governance.WRITE_PERMISSIONS` (no agent may write purchasing) |
| Risk + reversibility + confidence + policy + permissions + context → authority | `governance.evaluate()`. Every rule that fires is written to `rule_trace`. |
| Confidence ≠ authority | `governance.evaluate()` step 5: confidence can only lower authority |
| Abstain when context is below 95% | `governance.evaluate()` step 1; `engine.run_service()` abstention branch |
| The 10 failure modes (p.8) | `governance.evaluate()` step 6 · `python -m hotel_agentops_sim failure-matrix` |
| Readiness gate: all 8 must pass, no averaging, first blocker | `agentops.evaluate_gate()`. It is tested against the workbook for all 8 pilot weeks. |
| Authority ladder: Bounded → Supervised → Delegated | `agentops.autonomy_level()` |
| Overrides become learning data, with no automatic retraining | `learning.py`: each case opens as *OPEN · evaluate* |

## Python and Excel: one job each

- **Python** answers *"What decision should the system make, and is it allowed?"*: agents, orchestration, governance, approval, the decision log.
- **Excel** (`Hotel_Food_Waste_Model.xlsx`) answers *"What happened, and is the system creating measurable value?"*: the modeled data, KPIs, AgentOps, the readiness gate and economics.

The thresholds are not typed into the code. `tools/extract_parameters.py` reads them from the workbook into `data/project_parameters.json`, recording the **source cell** of every value. A test checks the JSON still matches the workbook.

Examples:
- Tool reliability ≥ 99% comes from `Readiness Gate!C5`.
- Waste cost per kg is `Waste Cost!G3 / (Weekly Waste!F2 × 52)` = $15.12.

## New modeled assumptions

The case study didn't specify everything a running system needs. Each missing piece is a labeled assumption (**NA-01** to **NA-15** in `data/scenario_d0418.json`) and is referenced by ID in the code. Examples:
- How covers are forecast
- How confidence is computed
- The 80% low-confidence cutoff
- The MEDIUM/HIGH risk boundary (25%)
- The 12-hour stale-data limit
- The minimum sample of 20 decisions before day-level rates can move the gate

## Honest limits

- **One service is one observation.** MAPE, acceptance, override rate and escalation recall/precision are rates over many decisions. The control view shows them with their sample size (n) and flags them as below the minimum sample. Today's autonomy comes from the latest evaluated pilot week in the workbook (A8).
- **Waste scope is narrower than the pilot's.** The simulation models buffet overproduction and plate waste for four item groups. It does not model spoilage or prep waste, so its waste per cover is not comparable to the pilot's total.
- **Some outcomes are pending.** Purchasing and banquet decisions are marked PENDING because their effect happens after the simulated day.
- **The escalation labels are analyst-set.** Escalation recall and precision are scored against modeled ground-truth labels, which are listed in the scenario file.

## Layout

```
hotel_agentops_sim/
  context.py          8 required sources, completeness, stale/fallback detection, least-privilege views
  agents/             demand · inventory · waste · production
  orchestrator.py     structured recommendations + conflict detection
  governance.py       decision rights, policy, permissions, failure modes → authority
  approval.py         manager card + Approve / Modify / Reject / Request more context
  outcome.py          simulated actual outcome vs prediction (and vs the standing plan)
  agentops.py         day metrics with sample sizes, readiness gate, drift, autonomy level
  learning.py         override → outcome → root cause → proposed improvement
  decision_log.py     CSV log, outcomes, traces
  control_view.py     operational control view
  engine.py           runs one service end to end
data/                 project_parameters.json (from the workbook) · scenario_d0418.json (modeled)
tools/                extract_parameters.py
tests/                test_simulation.py
```
