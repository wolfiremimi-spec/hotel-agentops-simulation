# Hotel AgentOps Simulation

[![tests](https://github.com/wolfiremimi-spec/hotel-agentops-simulation/actions/workflows/tests.yml/badge.svg)](https://github.com/wolfiremimi-spec/hotel-agentops-simulation/actions/workflows/tests.yml)
&nbsp;**[Pilot app](https://hotel-agentops.streamlit.app)** · **[Control Room](https://hotel-agentops-control-room.streamlit.app)**

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
python -m hotel_agentops_sim run             # interactive: you are the F&B manager (Approve / Modify / Reject / Request more context)
python -m hotel_agentops_sim trace D-0418    # follow one decision: input → agent → governance → human → action → outcome → KPI
python -m hotel_agentops_sim test tool-reliability   # or missing-context, guest-score
python -m hotel_agentops_sim failure-matrix  # all 10 failure modes from the case study, executed
python -m unittest -v                        # 20 tests of the governance guarantees
python tests/app/run_all.py                  # 132 end-to-end checks of the pilot app and the Control Room
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

- **Waste Agent:** finds chronic pastry overproduction (leftover above 20% on all of the last 4 Saturdays) and repeated hot-line stockouts.
- **Production Agent:** drafts **−12.2%** overall. It raises the hot line **+14%** and cuts pastry **−34%**.
- **Orchestrator:** detects that demand and production point in opposite directions. It resolves the conflict with the waste evidence.
- **Governance:** the change exceeds the ±10% delegated range, so risk is **MEDIUM** and the decision goes to the manager. Confidence is 92.7%, but high confidence does not grant authority.
- **Outcome:** **409 actual covers against 420 predicted, a 2.7% error.** This matches the decision trace in the case study. Waste is 23.3 kg against 47.3 kg on the kitchen's standing plan, with no stockouts.

The case study's illustration shows −14%. The simulation computes −12.2% from its inputs, and I kept the computed number rather than tuning inputs to match.

## Interactive Control Room (Streamlit)

**Live app:** [hotel-agentops-control-room.streamlit.app](https://hotel-agentops-control-room.streamlit.app) · start from the Suggested path on Mission Control

A browser front end on the same simulation code, built for people who will never open a terminal:

| Page | What you can do |
|---|---|
| Mission Control | Modeled pilot results and the live readiness status |
| Live Service: You Decide | Play the F&B manager: approve, modify, reject or ask for more context on each decision, then see the outcome, the AgentOps metrics, the learning cases and the full audit trail (downloadable) |
| Scenario Lab | Change occupancy, forecast error, waste history, event demand, any of the 8 data feeds, the governance policy and the evidence week, and compare with the case-study scenario |
| Failure Lab | The three failure tests and all ten failure modes, executed live |
| Procurement: Next Week's Order | The Procurement Agent's supplier order per item group from the recorded services (less where food is left over, more where guests ran short), policy what-ifs on the safety buffers, and your Approve / Modify / Reject decision with its governance trace |
| Readiness Gate & Autonomy | The 8-metric gate for every pilot week, a what-if gate you control, the autonomy ladder and the drift rule |
| AgentOps & Learning | Weekly quality, safety and reliability metrics; every override reason mapped to a system improvement |
| Business Value | The workbook's economics, recalculated live with its own formulas |
| Architecture & Decision Rights | Seven layers, least-privilege agents (read from the code), decision rights and the governance order |
| Methodology & Limits | Disclosures, assumptions NA-01 to NA-15 and every parameter's source cell |

The app never re-implements a decision rule: `control_room/sim.py` calls the package's own engine, governance, AgentOps and gate functions.
Workbook values shown in the app are copied by `tools/extract_app_data.py` into `data/control_room_workbook.json`.

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Hotel AgentOps pilot application (built for a hotel's own data)

**Live app:** [hotel-agentops-control-room.streamlit.app](https://hotel-agentops-control-room.streamlit.app) · start from the Suggested path on Mission Control

The Control Room demonstrates the operating model on the case study's modeled hotel. The pilot application runs the
same engine on **figures a hotel enters itself**, one service at a time:

| Screen | What the hotel does |
|---|---|
| Hotel setup | Rooms, consumption per cover, standing par, waste cost, governance policy, and four weeks of baseline history (typed in or imported from a CSV template) |
| Today's plan | Enters this morning's occupancy, reservations, inventory, events and guest signal; the agents recommend; governance routes each decision; the manager approves, modifies, rejects or asks for more context; the kitchen gets a production sheet (printable, or CSV) |
| Close out service | Records actual covers, leftovers and stockouts after breakfast; the day is scored (recorded waste, forecast error, estimated waste vs standing par) |
| Next week's order | Suggests next week's supplier order per item group from the hotel's own close-outs (less where food is usually left over, more where guests ran short); an optional AI Procurement Agent explains it and may only raise orders for guest safety; a manager approves every order, and it is logged with a downloadable purchase order; once the week is closed out, order accuracy is measured against what was actually used and the next suggestion learns from any shortfall |
| Decision log & audit | Every decision with its rule trace, human decision and outcome; learning cases from overrides; an append-only audit trail; CSV/JSON export |
| Performance & autonomy | The eight-check readiness gate computed from the hotel's own last 28 days; autonomy starts SUPERVISED and is earned |
| Ops copilot (optional) | A Gemini model that answers from the workspace's records and re-runs a morning as a what-if; it never decides who may act |

**AI specialist agents (case study layers 3–4).** With a `GEMINI_API_KEY`, the Demand, Inventory, Waste and Production
agents are language-model agents, and the Orchestrator reviews how their signals combine:
- Each agent answers its case-study question with tools. It can only read the sources its role grants; reads go through
  the engine's least-privilege view, so a request for anything else is denied in code, not by prompt.
- Demand, Inventory and Waste run in parallel (the case study's `asyncio.gather`), then Production sizes the plan from
  their signals only.
- They read what rules can't: the front-desk and kitchen notes a manager types each morning.
- **Output verification:** every proposal is checked before use, and AI can make the system more cautious, never less.
  Forecasts may move at most ±15% from the statistical forecast; confidence may only go down; a group is "chronic
  overproduction" only with ≥15% average leftover; stockout-prone flags can't be dropped; buffers stay within 2–15%; the
  Orchestrator may escalate a plan but never resolve a conflict the rules left open.
- If a model fails or its output fails verification, the rule-based agent is used and the fallback is logged.
- Decision rights, the policy check, approvals and the readiness gate are deterministic rules, never AI.
Every agent's rationale, changes and verification result are saved with the day's decisions.

How it stays honest:
- **Data comes in by form or CSV.** There are no PMS/POS/inventory integrations; those would come in a funded pilot.
- **Autonomy is earned from the hotel's own record.** A new hotel stays SUPERVISED until it has 20 manager decisions and 4 closed-out services; then all eight gate checks must pass.
- **Escalations caused only by the current autonomy level don't count against escalation precision.** Otherwise a supervised hotel could never demonstrate precision. This is visible in each decision's rule trace.
- **Estimates are labeled.** "Waste vs standing par" serves the kitchen's usual par against that day's measured consumption; it is a lower bound on days an item ran out.
- **Access is pilot-grade.** Each hotel has a private workspace code; only its SHA-256 hash is stored. Database tables have row-level security on with no policies, so only the server (holding the secret key) can read them.

Deploy it as its own Streamlit app with main file `hotel_app.py`. One-time setup:
1. Create a free Supabase project and run `product/schema.sql` in its SQL editor.
2. In the Streamlit app's **Secrets**, add `SUPABASE_URL`, `SUPABASE_SECRET_KEY` and a random `APP_SALT` (and optionally `GEMINI_API_KEY`).

Without a database it still runs, with only the demo workspace available.

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
- **The pilot application is decision support, not a live integration.** It runs on figures the hotel enters; it has not been validated in a real hotel.
- **AI agent outputs vary between runs.** Verification bounds what they can change, and the proposals a manager reviews are the ones that are saved, but two mornings with identical data may get slightly different AI reasoning.
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
hotel_app.py          pilot application entry point
product/
  core.py             hotel profile → scenario, morning run, close-out, earned autonomy from the hotel's record
  store.py            Supabase (REST) and in-memory storage with the same interface
  schema.sql          database tables, row-level security, append-only audit log
  agent.py            Gemini tool-calling loop (copilot and agents)
  ai_agents.py        AI specialist agents with scoped tools, output verification and rule-based fallback
  views/              welcome · today · closeout · orders · decision_log · performance · setup · copilot · videos
```
