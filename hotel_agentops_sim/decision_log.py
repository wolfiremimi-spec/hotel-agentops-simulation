"""Structured, traceable outputs. Every material decision becomes one row; every row has a full JSON trace:
INPUT → AGENT → GOVERNANCE → HUMAN → ACTION → OUTCOME → KPI."""
from __future__ import annotations

import csv
import json
from pathlib import Path

LOG_COLUMNS = [
    "Decision ID", "Timestamp", "Service", "Agent(s)", "Recommendation", "Confidence", "Risk", "Reversibility",
    "Context Completeness", "Policy Status", "Required Authority", "Human Approval Required", "AI Recommendation",
    "Human Decision", "Final Action", "Override", "Override Reason", "Execution Status", "Actual Outcome",
    "Waste Impact", "Guest Impact", "Financial Impact", "Escalation", "AgentOps Status",
    # traceability extras
    "Decision Type", "Approver", "Decision Timestamp", "Scenario", "Run",
]
OUTCOME_COLUMNS = ["Decision ID", "Run", "Predicted Covers", "Actual Covers", "Forecast APE", "Actual Production kg",
                   "Actual Consumption kg", "Actual Waste kg", "Overproduction kg", "Plate Waste kg", "Waste Source",
                   "Waste per Cover", "Guest F&B Score", "Stockouts", "Operational Exception", "Plan Used",
                   "Counterfactual Waste kg (standing plan)"]


def write_run(result, run_name: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [{**{k: r.get(k, "") for k in LOG_COLUMNS if k != "Run"}, "Run": run_name} for r in result.records]
    with open(out_dir / "decision_log.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    outcomes = []
    for did, t in result.traces.items():
        o = (t.get("outcome") or {}).get("actual") or {}
        if "actual_covers" not in o:
            continue
        outcomes.append({
            "Decision ID": did, "Run": run_name, "Predicted Covers": o.get("predicted_covers"),
            "Actual Covers": o["actual_covers"], "Forecast APE": o.get("forecast_ape"),
            "Actual Production kg": o["production_kg"], "Actual Consumption kg": o["consumption_kg"],
            "Actual Waste kg": o["waste_kg"], "Overproduction kg": o["overproduction_kg"],
            "Plate Waste kg": o["plate_waste_kg"],
            "Waste Source": "; ".join(f"{g} {l['leftover_kg']} kg" for g, l in o["lines"].items() if l["leftover_kg"] > 0),
            "Waste per Cover": o["waste_per_cover"], "Guest F&B Score": o["guest_fb_score"],
            "Stockouts": ", ".join(o["stockouts"]) or "None", "Operational Exception": o["operational_exception"],
            "Plan Used": o["plan_used"], "Counterfactual Waste kg (standing plan)": o["counterfactual_waste_kg"]})
    with open(out_dir / "outcomes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUTCOME_COLUMNS)
        w.writeheader()
        w.writerows(outcomes)

    if result.learning:
        with open(out_dir / "override_learning.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(result.learning[0].keys()))
            w.writeheader()
            w.writerows(result.learning)

    (out_dir / "traces").mkdir(exist_ok=True)
    for did, t in result.traces.items():
        (out_dir / "traces" / f"{did}.json").write_text(json.dumps(t, indent=2, default=str))
    summary = {"run": run_name, "scenario": result.scenario_id, "gate": result.gate, "autonomy_level": result.autonomy,
               "autonomy_reasons": result.autonomy_why, "context_completeness": result.context.completeness,
               "day_metrics": result.metrics, "guardrail_events": result.guardrail_events,
               "label": "MODELED SIMULATION · not realized hotel performance"}
    (out_dir / "agentops_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary
