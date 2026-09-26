"""Override learning loop: RECOMMENDATION → HUMAN OVERRIDE → OUTCOME → ROOT CAUSE → SYSTEM IMPROVEMENT.

Overrides are evidence to evaluate, never an automatic retrain. Each case opens with status
'OPEN · evaluate' and a proposed improvement taken from the workbook's Overrides tab."""
from __future__ import annotations


def learning_cases(records: list[dict], categories: list[dict]) -> list[dict]:
    improvement = {c["reason"]: c["system_improvement"] for c in categories}
    cases = []
    for r in records:
        if r["Override"] != "YES":
            continue
        cases.append({
            "Decision ID": r["Decision ID"], "Override Reason": r["Override Reason"], "Agent(s)": r["Agent(s)"],
            "Decision Type": r["Decision Type"], "Risk": r["Risk"], "Original Recommendation": r["AI Recommendation"],
            "Human Action": r["Final Action"], "Actual Outcome": r["Actual Outcome"],
            "Root Cause (hypothesis)": f"Agent lacked a signal the manager had: {r['Override Reason'].lower()}"
                                       + (f" ({r['_note']})" if r.get("_note") else ""),
            "Outcome Evidence": _evidence(r.get("_outcome_actual") or {}),
            "Proposed System Improvement": improvement.get(r["Override Reason"], "Review with the agent owner"),
            "Status": "OPEN · evaluate before any change (no automatic retraining)",
        })
    return cases


def _evidence(actual: dict) -> str:
    """Compare what the human's action produced with what the AI's plan would have produced (same demand)."""
    if actual.get("ai_plan_waste_kg") is None:
        return "Outcome not yet observable (measured later)"
    ai, human = actual["ai_plan_waste_kg"], actual["waste_kg"]
    ai_so, human_so = actual.get("ai_plan_stockouts") or [], actual.get("stockouts") or []
    verdict = ("favors the AI plan" if ai < human and not ai_so else
               "favors the human decision" if human < ai or (ai_so and not human_so) else "is neutral")
    return (f"AI plan: {ai} kg waste, stockouts {', '.join(ai_so) or 'none'} · human action: {human} kg, "
            f"stockouts {', '.join(human_so) or 'none'} → this single service {verdict} (1 observation, not a verdict)")
