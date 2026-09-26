"""Governance (case study layer 5). Decides WHO may act on a recommendation.

Authority = f(risk, reversibility, confidence, policy, permissions, context completeness, current autonomy level).
CONFIDENCE ≠ AUTHORITY: confidence can only lower authority, never raise it above what risk allows.
Every rule that fires is written to `rule_trace`, so each decision can be audited line by line.
"""
from __future__ import annotations

from .models import GovernanceResult, Recommendation

LOW_CONFIDENCE = 0.80          # NA-03

# Least-privilege write permissions (case study p.4). Purchasing is not writable by any agent.
WRITE_PERMISSIONS = {
    "Demand Agent": [],
    "Inventory Agent": ["inventory_recommendation"],
    "Waste Agent": ["waste_insight"],
    "Production Agent": ["production_plan"],
    "Orchestrator": [],
}

AUTHORITY_TEXT = {
    "EXECUTE": "Agent executes (delegated)",
    "MANAGER_APPROVAL": "Agent recommends · manager approves",
    "HUMAN_DECISION": "Human decision · mandatory escalation",
    "RECOMMEND_ONLY": "Recommend only · no execution",
    "ABSTAIN": "Abstain · escalate to manager",
    "BLOCK": "Blocked · escalate",
}

# NA-13: autonomy level set by the readiness gate
LEVELS = ["BOUNDED", "SUPERVISED", "DELEGATED"]


def policy_check(rec: Recommendation, plan_kg: dict | None = None) -> list[str]:
    """Hard constraints. Returns violations (empty list = pass)."""
    v = []
    if rec.decision_type == "production_adjustment":
        plan = plan_kg or rec.details["plan_kg"]
        for g, need in rec.details["expected_consumption_kg"].items():
            available = plan[g] + rec.details["usable_carry_over_kg"].get(g, 0.0)
            if available + 1e-9 < need:                                    # NA-11: no planned stockouts
                v.append(f"{g}: {available:.1f} kg available < {need:.1f} kg expected consumption (planned stockout)")
    executor, scope = rec.details.get("executor"), rec.details.get("write_scope")
    if executor and scope not in WRITE_PERMISSIONS.get(executor, []):
        v.append(f"{executor} has no write permission for '{scope}'")
    return v


def evaluate(rec: Recommendation, *, context, autonomy_level: str, context_threshold: float,
             delegated_range: float, conflict: dict | None = None) -> GovernanceResult:
    t: list[str] = []
    escalate = False

    # 1 · Context completeness (abstention)
    t.append(f"Context completeness {context.completeness:.1%} (threshold {context_threshold:.0%})")
    if context.completeness < context_threshold:
        t.append(f"→ BELOW THRESHOLD: missing {', '.join(context.missing)} → ABSTAIN + ESCALATE")
        return GovernanceResult("ABSTAIN", AUTHORITY_TEXT["ABSTAIN"], True, True, "NOT EVALUATED (abstained)", t)

    # 2 · Policy (hard constraints) → BLOCK
    violations = policy_check(rec)
    if violations:
        t += [f"Policy violation: {x}" for x in violations] + ["→ BLOCK + ESCALATE"]
        return GovernanceResult("BLOCK", AUTHORITY_TEXT["BLOCK"], True, True, "VIOLATION: " + "; ".join(violations), t)
    policy_status = "PASS"
    t.append("Policy: all hard constraints pass")

    # 3 · Base authority from risk and reversibility (case study p.7)
    t.append(f"Risk {rec.risk_level} · reversibility {rec.reversibility} · confidence {rec.confidence:.1%}")
    if rec.risk_level == "HIGH" or rec.reversibility in ("LOW", "IRREVERSIBLE") and rec.risk_level != "LOW":
        authority = "HUMAN_DECISION" if rec.risk_level == "HIGH" else "MANAGER_APPROVAL"
    elif rec.risk_level == "MEDIUM":
        authority = "MANAGER_APPROVAL"
    else:
        authority = "EXECUTE"
    t.append(f"Decision rights for {rec.risk_level} risk → {AUTHORITY_TEXT[authority]}")

    # 4 · Permissions: an action no agent may write always goes to a human
    executor = rec.details.get("executor")
    if executor is None and authority == "EXECUTE":
        authority = "MANAGER_APPROVAL"
    if executor is None:
        t.append(f"No agent holds write permission for '{rec.details.get('write_scope')}' → a human must act")

    # 5 · Confidence can only lower authority (CONFIDENCE ≠ AUTHORITY)
    if rec.confidence < LOW_CONFIDENCE:
        if authority == "HUMAN_DECISION":
            t.append(f"Low confidence ({rec.confidence:.0%} < {LOW_CONFIDENCE:.0%}) + high risk → ESCALATE")
            escalate = True
        else:
            authority = "RECOMMEND_ONLY"
            t.append(f"Low confidence ({rec.confidence:.0%} < {LOW_CONFIDENCE:.0%}) → RECOMMEND ONLY")
    elif authority != "EXECUTE":
        t.append(f"High confidence ({rec.confidence:.0%}) does not grant authority for {rec.risk_level} risk")

    # 6 · Failure-mode rules from the case study (p.8)
    if context.fallback:
        t.append(f"Fallback data in use ({', '.join(context.fallback)}) → FALLBACK + ESCALATE")
        escalate = True
        if authority == "EXECUTE":
            authority = "MANAGER_APPROVAL"
    if context.stale and rec.details.get("depends_on_inventory"):
        t.append(f"Stale feed ({', '.join(context.stale)}) → BLOCK EXECUTION")
        return GovernanceResult("BLOCK", AUTHORITY_TEXT["BLOCK"], True, True,
                                "PASS (execution blocked: stale data)", t)
    if rec.details.get("abnormal_event"):
        t.append("Abnormal event demand → HUMAN REVIEW")
        escalate = True
        if authority not in ("HUMAN_DECISION",):
            authority = "HUMAN_DECISION"
    if conflict and conflict.get("conflict") and rec.decision_type == "production_adjustment":
        t.append("Agent conflict: " + conflict["note"])
        if not conflict["resolved"]:
            t.append("→ Unresolved conflict → ESCALATE")
            escalate = True
            if authority in ("EXECUTE", "MANAGER_APPROVAL", "RECOMMEND_ONLY"):
                authority = "HUMAN_DECISION"

    # 7 · Current autonomy level (readiness gate) caps what may run without a human
    t.append(f"Current autonomy level: {autonomy_level}")
    if authority == "EXECUTE":
        if autonomy_level == "SUPERVISED":
            authority = "MANAGER_APPROVAL"
            t.append("Gate on HOLD → autonomy SUPERVISED → low-risk action needs manager approval")
        elif autonomy_level == "BOUNDED":
            authority = "RECOMMEND_ONLY"
            t.append("Autonomy REDUCED to BOUNDED → recommend only")
    elif authority == "MANAGER_APPROVAL" and autonomy_level == "BOUNDED":
        t.append("Autonomy BOUNDED → manager approval still required")

    needs_human = authority in ("MANAGER_APPROVAL", "HUMAN_DECISION")
    escalate = escalate or needs_human or authority in ("ABSTAIN", "BLOCK")
    t.append(f"FINAL: {AUTHORITY_TEXT[authority]}")
    return GovernanceResult(authority, AUTHORITY_TEXT[authority], needs_human, escalate, policy_status, t)
