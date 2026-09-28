"""Operational control view: what the AI did today and whether it is still allowed to do it.
Complements the executive Excel dashboard (which reports value over weeks) rather than duplicating it."""
from __future__ import annotations


def _pct(m):
    if m.get("value") is None:
        return "n/a"
    s = f"{m['value']:.1%}"
    if "den" in m:
        s += f"  (n={m['den']}{'' if m.get('sufficient') else ', below min sample'})"
    return s


def render(result, width: int = 78) -> str:
    recs = result.records
    count = lambda pred: sum(1 for r in recs if pred(r))
    prod = next((t["outcome"]["actual"] for t in result.traces.values()
                 if t.get("outcome") and t["outcome"].get("actual", {}).get("actual_covers")), None)
    m = result.metrics
    bar = "═" * width
    lines = [bar, f" OPERATIONAL CONTROL VIEW · {result.service} · {result.scenario_id} · MODELED SIMULATION", bar,
             " TODAY'S AI ACTIVITY",
             f"   Recommendations {len(recs):>3}   Executed {count(lambda r: r['Execution Status'] == 'EXECUTED'):>3}"
             f"   Awaiting approval {count(lambda r: r['Execution Status'] == 'AWAITING CONTEXT'):>3}",
             f"   Escalated       {count(lambda r: r['Escalation'] == 'YES'):>3}   "
             f"Abstained {count(lambda r: r['Execution Status'].startswith('ABSTAINED')):>3}"
             f"   Overridden {count(lambda r: r['Override'] == 'YES'):>3}   Blocked {m['policy_blocks']:>3}",
             " SYSTEM HEALTH",
             f"   Context completeness  {result.context.completeness:.1%}",
             f"   Tool / API reliability {_pct(m['tool_reliability'])}",
             f"   Forecast (this service) " + (f"APE {prod['forecast_ape']:.1%} · {prod['predicted_covers']} predicted vs {prod['actual_covers']} actual" if prod and prod.get('forecast_ape') is not None else "n/a"),
             f"   Execution failures    {_pct(m['execution_failure_rate'])}",
             f"   Policy violations     {m['policy_violations']['value']} executed · {m['policy_blocks']} blocked before execution",
             " BUSINESS HEALTH"]
    if prod:
        lines += [f"   Food waste            {prod['waste_kg']} kg (standing plan would have been {prod['counterfactual_waste_kg']} kg)",
                  f"   Waste per cover       {prod['waste_per_cover']:.3f} kg",
                  f"   Overproduction        {prod['overproduction_kg']} kg",
                  f"   Guest F&B (modeled)   {prod['guest_fb_score']:.2f}" + (f" · stockout: {', '.join(prod['stockouts'])}" if prod['stockouts'] else " · no stockouts")]
    else:
        lines.append("   No service outcome recorded")
    pending = count(lambda r: r["Execution Status"] in ("AWAITING CONTEXT", "ESCALATED"))
    lines += [" GOVERNANCE",
              f"   Current authority level  {result.autonomy}",
              f"   Readiness gate           {result.gate['result']} · first blocker: {result.gate['first_blocker']}",
              f"   Pending human decisions  {pending}",
              " DAY RATES (accumulate toward the gate; one day is not enough evidence)",
              f"   Acceptance {_pct(m['recommendation_acceptance'])}",
              f"   Override   {_pct(m['human_override_rate'])}",
              f"   Esc. recall {_pct(m['escalation_recall'])}   precision {_pct(m['escalation_precision'])}",
              bar]
    return "\n".join(lines)


def render_gate(gate: dict) -> str:
    out = []
    for c in gate["checks"]:
        v = c["value"]
        shown = f"{v:.2f}" if c["key"] == "guest_fb_score" else str(v) if c["key"] == "policy_violations" else f"{v:.1%}"
        t = c["threshold"]
        tt = f"{t:.2f}" if c["key"] == "guest_fb_score" else str(t) if c["key"] == "policy_violations" else f"{t:.0%}"
        out.append(f"   {'✓' if c['pass'] else '✗'} {c['metric']:<18} {shown:>7}  {c['test']} {tt}")
    out.append(f"   RESULT: {gate['result']} · first blocker: {gate['first_blocker']} · failed checks: {gate['failed']}")
    return "\n".join(out)
