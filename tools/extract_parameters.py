"""Extract the governance thresholds and KPIs this simulation depends on from the
case-study workbook, with the source cell of every value.

    python tools/extract_parameters.py path/to/Hotel_Food_Waste_Model.xlsx

Writes data/project_parameters.json. The simulation itself only reads that JSON
(standard library only), so it runs without Excel or openpyxl installed.
Needs openpyxl for this one extraction step: pip install openpyxl
"""
import json
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]


def cell(wb, sheet, ref):
    return {"value": wb[sheet][ref].value, "source": f"{sheet}!{ref}"}


def main(xlsx):
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    if wb["Readiness Gate"]["C2"].value is None:
        sys.exit("Workbook has no calculated values. Open it in Excel, save, and re-run.")
    gate_rows = {
        "recommendation_acceptance": ("C2", ">="),
        "escalation_recall": ("C3", ">="),
        "escalation_precision": ("C4", ">="),
        "tool_reliability": ("C5", ">="),
        "human_override_rate": ("C6", "<="),
        "forecast_mape": ("C7", "<="),
        "guest_fb_score": ("C8", ">="),
        "policy_violations": ("C9", "=="),
    }
    thresholds = {k: {**cell(wb, "Readiness Gate", ref), "test": op} for k, (ref, op) in gate_rows.items()}
    # Latest evaluated pilot week (A8, row 19) = the evidence base the gate currently stands on.
    latest = {
        "week": cell(wb, "Readiness Gate", "A19"),
        "recommendation_acceptance": cell(wb, "Readiness Gate", "B19"),
        "escalation_recall": cell(wb, "Readiness Gate", "C19"),
        "escalation_precision": cell(wb, "Readiness Gate", "D19"),
        "tool_reliability": cell(wb, "Readiness Gate", "E19"),
        "human_override_rate": cell(wb, "Readiness Gate", "F19"),
        "forecast_mape": cell(wb, "Readiness Gate", "G19"),
        "guest_fb_score": cell(wb, "Readiness Gate", "H19"),
        "policy_violations": cell(wb, "Readiness Gate", "I19"),
        "gate": cell(wb, "Readiness Gate", "K19"),
    }
    cols = {"recommendation_acceptance": "B", "escalation_recall": "C", "escalation_precision": "D",
            "tool_reliability": "E", "human_override_rate": "F", "forecast_mape": "G", "guest_fb_score": "H",
            "policy_violations": "I", "gate": "K", "first_blocker": "L"}
    by_week = {wb["Readiness Gate"][f"A{r}"].value: {k: cell(wb, "Readiness Gate", f"{c}{r}") for k, c in cols.items()}
               for r in range(12, 20)}
    ov = wb["Overrides"]
    categories = [{"reason": ov[f"A{r}"].value, "pilot_count": ov[f"B{r}"].value,
                   "system_improvement": ov[f"D{r}"].value, "source": f"Overrides!A{r}:D{r}"} for r in range(2, 9)]
    annual_waste_cost = wb["Waste Cost"]["G3"].value
    baseline_weekly_kg = wb["Weekly Waste"]["F2"].value
    params = {
        "_about": "Extracted from the case-study workbook. Every value carries its source cell. "
                  "Values marked source 'Case study' come from the 17-page case study, not a cell.",
        "workbook": Path(xlsx).name,
        "readiness_thresholds": thresholds,
        "latest_gate_evidence": latest,
        "gate_evidence_by_week": by_week,
        "override_categories": categories,
        "drift_rule": {"multiplier": 1.5, "trailing_weeks": 3, "source": "Overrides!A18 (rule text)"},
        "override_rate_history": [{"week": wb["AgentOps"][f"A{r}"].value, "value": wb["AgentOps"][f"K{r}"].value,
                                   "source": f"AgentOps!K{r}"} for r in range(2, 10)],
        "guest_score_floor": cell(wb, "Readiness Gate", "C8"),
        "waste_cost_per_kg": {
            "value": round(annual_waste_cost / (baseline_weekly_kg * 52), 2),
            "source": "Waste Cost!G3 / (Weekly Waste!F2 x 52)",
        },
        "manager_loaded_hourly_cost": cell(wb, "Economics", "B19"),
        "hotel_rooms": {"value": 250, "source": "Case study p.9 (250 rooms)"},
        "context_completeness_threshold": {"value": 0.95, "source": "Case study p.8 (>= 95% for delegated execution)"},
        "delegated_prep_range": {"value": 0.10, "source": "Case study p.7 (small prep adjustment <= +/-10%)"},
        "required_context_sources": {
            "value": ["pms_occupancy", "reservations", "pos_history", "inventory", "shelf_life",
                      "waste_history", "event_schedule", "guest_experience_signal"],
            "source": "Case study p.8 (8 required sources)",
        },
    }
    out = ROOT / "data" / "project_parameters.json"
    out.write_text(json.dumps(params, indent=2, default=str))
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Hotel_Food_Waste_Model.xlsx")
