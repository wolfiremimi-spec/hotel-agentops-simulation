"""AgentOps (case study layer 7) and the production-readiness gate.

Two different evidence bases are kept apart on purpose:
  * gate evidence   - the latest evaluated week in the workbook (A8). This is what sets today's autonomy.
  * day metrics     - counts from this simulation's decisions. Rates from a handful of decisions are
                      reported with their sample size (n) and cannot move the gate until n >= 20 (NA-14).
"""
from __future__ import annotations

GATE_ORDER = [  # same order as the workbook's first-blocker formula
    ("recommendation_acceptance", "Acceptance"), ("escalation_recall", "Recall"),
    ("escalation_precision", "Precision"), ("tool_reliability", "Tool reliability"),
    ("human_override_rate", "Override rate"), ("forecast_mape", "Forecast MAPE"),
    ("guest_fb_score", "Guest score"), ("policy_violations", "Policy violations"),
]
MIN_SAMPLE = 20      # NA-14


def _passes(value, op, threshold) -> bool:
    return {">=": value >= threshold, "<=": value <= threshold, "==": value == threshold}[op]


def evaluate_gate(evidence: dict, thresholds: dict) -> dict:
    """All eight must pass. No averaging: a strong metric cannot offset a failed one."""
    checks, first = [], None
    for key, label in GATE_ORDER:
        threshold, op = thresholds[key]
        ok = _passes(evidence[key], op, threshold)
        checks.append({"metric": label, "key": key, "value": evidence[key], "test": op, "threshold": threshold, "pass": ok})
        if not ok and first is None:
            first = label
    return {"result": "PASS" if first is None else "HOLD", "first_blocker": first or "—", "checks": checks,
            "failed": sum(not c["pass"] for c in checks)}


def drift(history: list[float], multiplier: float = 1.5, trailing: int = 3) -> dict:
    """Case-study drift rule: this week's override rate > 1.5x its trailing 3-week average."""
    current, prior = history[-1], history[-1 - trailing:-1]
    avg = sum(prior) / len(prior)
    return {"current": current, "trailing_avg": avg, "limit": multiplier * avg, "drift": current > multiplier * avg}


def autonomy_level(gate: dict, evidence: dict, thresholds: dict, drift_state: dict) -> tuple[str, list[str]]:
    """NA-13. Guest-guardrail breach, policy violation or override drift REDUCE autonomy;
    any other HOLD keeps autonomy at SUPERVISED; PASS allows DELEGATED."""
    why = []
    if evidence["guest_fb_score"] < thresholds["guest_fb_score"][0]:
        why.append(f"Guest F&B {evidence['guest_fb_score']:.2f} < {thresholds['guest_fb_score'][0]:.2f} → REDUCE AUTONOMY")
    if evidence["policy_violations"] > 0:
        why.append("Policy violations > 0 → REDUCE AUTONOMY")
    if drift_state["drift"]:
        why.append(f"Override rate {drift_state['current']:.0%} > 1.5 × trailing {drift_state['trailing_avg']:.0%}"
                   " → REDUCE AUTONOMY + INVESTIGATE")
    if why:
        return "BOUNDED", why
    if gate["result"] == "PASS":
        return "DELEGATED", ["Gate PASS → low-risk reversible actions may be delegated"]
    return "SUPERVISED", [f"Gate HOLD (first blocker: {gate['first_blocker']}) → HOLD AUTONOMY: no delegated execution"]


def day_metrics(records: list[dict], tool_calls: list, executions: list) -> dict:
    """Metrics that can legitimately be computed from this run's observations."""
    decided = [r for r in records if r["_decided"]]
    accepted = [r for r in decided if r["_accepted"]]
    overridden = [r for r in decided if r["Override"] == "YES"]
    required = [r for r in records if r["_escalation_required"]]
    escalated = [r for r in records if r["Escalation"] == "YES"]
    correct = [r for r in escalated if r["_escalation_required"]]
    ok_calls = sum(c.ok for c in tool_calls)
    apes = [r["_forecast_ape"] for r in records if r.get("_forecast_ape") is not None]
    fails = sum(not e.ok for e in executions)

    def rate(num, den):
        return {"value": (num / den) if den else None, "num": num, "den": den,
                "sufficient": den >= MIN_SAMPLE}
    return {
        "recommendation_acceptance": rate(len(accepted), len(decided)),
        "human_override_rate": rate(len(overridden), len(decided)),
        "escalation_recall": rate(len(correct), len(required)),
        "escalation_precision": rate(len(correct), len(escalated)),
        "tool_reliability": rate(ok_calls, len(tool_calls)),
        "execution_failure_rate": rate(fails, len(executions)),
        "forecast_mape": {"value": sum(apes) / len(apes) if apes else None, "num": len(apes), "den": len(apes),
                          "sufficient": False, "note": "MAPE is a mean over services; one service gives one APE."},
        "policy_violations": {"value": sum(1 for r in records if r["_policy_violation_executed"]), "sufficient": True},
        "policy_blocks": sum(1 for r in records if r["Execution Status"].startswith("BLOCKED")),
    }
