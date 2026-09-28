"""Thin adapter between the Streamlit app and the hotel_agentops_sim package.
The app never re-implements a decision rule: every result comes from the package's own engine,
governance, AgentOps and gate code (the same code the 20 unit tests cover)."""
from __future__ import annotations

import copy
import csv
import io
import json
from dataclasses import dataclass, field

from hotel_agentops_sim import governance
from hotel_agentops_sim.agentops import autonomy_level, drift, evaluate_gate
from hotel_agentops_sim.approval import MODIFIABLE, ApprovalQueue
from hotel_agentops_sim.engine import run_service
from hotel_agentops_sim.models import HumanDecision
from hotel_agentops_sim.orchestrator import GROUP_LABEL
from hotel_agentops_sim.parameters import load_parameters, load_scenario, modified, thresholds

PARAMS = load_parameters()
SCENARIO = load_scenario()
SOURCES = PARAMS["required_context_sources"]["value"]
SOURCE_LABEL = {"pms_occupancy": "PMS · occupancy", "reservations": "Reservations", "pos_history": "POS · covers history",
                "inventory": "Inventory", "shelf_life": "Shelf life", "waste_history": "Waste tracking",
                "event_schedule": "Events calendar", "guest_experience_signal": "Guest-experience signal"}
TYPE_LABEL = {"production_adjustment": "Breakfast production plan", "flag_overproduction": "Overproduction flag",
              "inventory_transfer": "Inventory transfer", "purchasing_adjustment": "Purchase-order change",
              "banquet_production_change": "Banquet production change", "abstain_missing_context": "Abstention",
              "guardrail_escalation": "Guardrail escalation", "override_drift_investigation": "Drift investigation"}
CATEGORIES = [c["reason"] for c in PARAMS["override_categories"]]


@dataclass
class Pending:
    decision_id: str
    decision_type: str
    recommendation: str
    reason: str
    confidence: float
    risk: str
    reversibility: str
    authority: str
    rule_trace: list
    expected_impact: str
    lines: list = field(default_factory=list)
    modifiable: bool = False


class WebApproval(ApprovalQueue):
    """Approval step driven by choices made in the browser instead of the terminal."""

    def __init__(self, choices: dict, approver: str = "F&B Manager (you)"):
        super().__init__("scripted", {}, CATEGORIES, approver=approver, output_fn=lambda *a, **k: None)
        self.web_choices, self.seen = choices, []

    def route(self, rec, gov, at):
        self.seen.append(Pending(rec.decision_id, rec.decision_type, rec.recommendation, rec.reason, rec.confidence,
                                 rec.risk_level, rec.reversibility, gov.required_authority, list(gov.rule_trace),
                                 rec.expected_impact, rec.details.get("lines", []), rec.decision_type in MODIFIABLE))
        c = self.web_choices.get(rec.decision_type, {"choice": "approve"})
        choice = c["choice"]
        if choice == "modify" and rec.decision_type not in MODIFIABLE:
            choice = "reject"                                   # same rule as the command line
        return HumanDecision(choice=choice, approver=self.approver, timestamp=at,
                             final_change_pct=c.get("new_change_pct") if choice == "modify" else None,
                             override=choice in ("modify", "reject"), override_reason=c.get("reason", "") if choice in ("modify", "reject") else "",
                             note=c.get("note", ""))


def evidence_for(source_week: str | None = None, **overrides) -> dict:
    src = PARAMS["gate_evidence_by_week"][source_week] if source_week else PARAMS["latest_gate_evidence"]
    ev = {k: v["value"] for k, v in src.items()}
    ev["week"] = source_week or ev.get("week")
    ev.update(overrides)
    return ev


def params_with(context_threshold: float | None = None, delegated_range: float | None = None, gate_thresholds: dict | None = None) -> dict:
    p = copy.deepcopy(PARAMS)
    if context_threshold is not None: p["context_completeness_threshold"]["value"] = context_threshold
    if delegated_range is not None: p["delegated_prep_range"]["value"] = delegated_range
    for k, v in (gate_thresholds or {}).items(): p["readiness_thresholds"][k]["value"] = v
    return p


def run(scenario: dict | None = None, *, choices: dict | None = None, params: dict | None = None, evidence: dict | None = None,
        failures: dict | None = None, override_history: list | None = None):
    """Run one service end to end. Returns (RunResult, narrative log lines, approval cards seen)."""
    log: list[str] = []
    approval = WebApproval(choices or {})
    res = run_service(copy.deepcopy(scenario or SCENARIO), params or PARAMS, evidence=evidence, override_history=override_history,
                      failures=failures, mode="scripted", approval=approval, say=lambda *a, **k: log.append(" ".join(str(x) for x in a)))
    return res, log, approval.seen


def public_records(res) -> list[dict]:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in res.records]


def log_csv(res) -> bytes:
    rows = public_records(res)
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return buf.getvalue().encode()


def traces_json(res) -> bytes:
    return json.dumps(res.traces, indent=2, default=str).encode()


def sections(log: list[str]) -> dict:
    """Split the engine's narrative into its numbered stages (① … ⑦)."""
    marks = "①②③④⑤⑥⑦"
    out, cur = {m: [] for m in marks}, None
    for line in log:
        for chunk in line.split("\n"):
            s = chunk.strip()
            if s[:1] in marks: cur = s[:1]
            if cur: out[cur].append(chunk.rstrip())
    return out


def gate(evidence: dict, th: dict | None = None):
    th = th or thresholds(PARAMS)
    g = evaluate_gate(evidence, th)
    history = [w["value"] for w in PARAMS["override_rate_history"]]
    d = drift(history, PARAMS["drift_rule"]["multiplier"], PARAMS["drift_rule"]["trailing_weeks"])
    level, why = autonomy_level(g, evidence, th, d)
    return g, level, why


__all__ = ["GROUP_LABEL", "PARAMS", "SCENARIO", "SOURCES", "SOURCE_LABEL", "TYPE_LABEL", "CATEGORIES", "run", "gate", "evidence_for", "params_with",
           "modified", "thresholds", "public_records", "log_csv", "traces_json", "sections", "governance", "drift", "evaluate_gate", "autonomy_level"]
