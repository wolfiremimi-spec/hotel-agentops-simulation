"""Command line.

    python -m hotel_agentops_sim run            # interactive: you are the F&B manager
    python -m hotel_agentops_sim run --auto     # reproducible demo choices
    python -m hotel_agentops_sim test missing-context | tool-reliability | guest-score
    python -m hotel_agentops_sim failure-matrix # all 10 failure modes from the case study
    python -m hotel_agentops_sim trace D-0418   # follow one decision end to end
    python -m hotel_agentops_sim demo           # everything above, non-interactive
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agentops import evaluate_gate
from .control_view import render, render_gate
from .decision_log import write_run
from .engine import run_service
from .parameters import load_parameters, load_scenario, modified, thresholds

RUNS = Path(__file__).resolve().parents[1] / "runs"
BANNER = ("HOTEL AGENTOPS SIMULATION · Agentic AI for Sustainable Hospitality (Amelia Wolfire)\n"
          "MODELED SIMULATION · no real hotel systems connected · results are not realized performance")


def _evidence(params, source_week: str | None = None, **overrides) -> dict:
    src = params["gate_evidence_by_week"][source_week] if source_week else params["latest_gate_evidence"]
    ev = {k: v["value"] for k, v in src.items()}
    ev["week"] = source_week or ev.get("week")
    ev.update(overrides)
    return ev


def _run(name, scenario, params, mode, quiet=False, **kw):
    say = (lambda *a, **k: None) if quiet else print
    res = run_service(scenario, params, mode=mode, say=say, **kw)
    summary = write_run(res, name, RUNS / name)
    return res, summary


def cmd_run(args, params):
    scenario = load_scenario()
    print(BANNER)
    res, _ = _run("day1", scenario, params, "scripted" if args.auto else "interactive", quiet=args.quiet)
    print("\n⑧ AGENTOPS + ⑨ READINESS GATE")
    print(render_gate(res.gate))
    print(render(res))
    print(f"\nOutputs: {RUNS / 'day1'}  (decision_log.csv · outcomes.csv · override_learning.csv · traces/ · agentops_summary.json)")


def test_missing_context(params, quiet=False):
    print("\n══ FAILURE TEST 1 · MISSING CRITICAL CONTEXT (PMS occupancy removed) ══")
    s = modified(load_scenario(), hotel_data__pms_occupancy=None)
    res, _ = _run("test1_missing_context", s, params, "scripted", quiet)
    r = res.records[-1]
    ok = r["Execution Status"].startswith("ABSTAINED") and not res.executions
    print(f"\n   CONTEXT CHECK → FAIL ({res.context.completeness:.1%}) → ABSTAIN → ESCALATE → LOG EVENT {r['Decision ID']}")
    print(f"   Executions attempted: {len(res.executions)} · Result: {'PASS — the system refused to act' if ok else 'FAIL'}")
    return ok


def test_tool_reliability(params, quiet=False):
    print("\n══ FAILURE TEST 2 · TOOL RELIABILITY < 99% (week A6 evidence from the workbook) ══")
    ev = _evidence(params, "A6")
    gate = evaluate_gate(ev, thresholds(params))
    print(render_gate(gate))
    others = all(c["pass"] for c in gate["checks"] if c["key"] != "tool_reliability")
    res, _ = _run("test2_tool_reliability", load_scenario(), params, "scripted", quiet, evidence=ev)
    delegated = [r for r in res.records if r["Required Authority"].startswith("Agent executes")]
    ok = gate["result"] == "HOLD" and gate["first_blocker"] == "Tool reliability" and others and not delegated
    print(f"\n   Every other mandatory metric passes: {others} · Gate: {gate['result']} · Autonomy: {res.autonomy}")
    print(f"   Low-risk actions that were delegated at A8 now need approval: "
          f"{', '.join(r['Decision ID'] + ' ' + r['Decision Type'] for r in res.records if r['Risk'] == 'LOW')}")
    print(f"   Result: {'PASS — one failed threshold holds autonomy (the A6 lesson)' if ok else 'FAIL'}")
    return ok


def test_guest_score(params, quiet=False):
    print("\n══ FAILURE TEST 3 · GUEST F&B SCORE < 4.60 ══")
    ev = _evidence(params, None, guest_fb_score=4.55, week="A8 with guest score 4.55 (test)")
    gate = evaluate_gate(ev, thresholds(params))
    print(render_gate(gate))
    res, _ = _run("test3_guest_score", load_scenario(), params, "scripted", quiet, evidence=ev)
    flagged = [r for r in res.records if r["Decision Type"] == "guardrail_escalation"]
    executed_alone = [r for r in res.records if r["Required Authority"].startswith("Agent executes")]
    ok = gate["result"] == "HOLD" and res.autonomy == "BOUNDED" and flagged and not executed_alone
    print(f"\n   FLAG → ESCALATE ({flagged[0]['Decision ID'] if flagged else '—'}) → REDUCE AUTONOMY ({res.autonomy}) → HUMAN REVIEW")
    print(f"   Result: {'PASS — efficiency no longer outranks the guest guardrail' if ok else 'FAIL'}")
    return ok


def failure_matrix(params):
    """Exercise each row of the case study's failure-mode table (p.8)."""
    from .agentops import autonomy_level, drift
    base = load_scenario()
    rows = []

    def gov_of(res, dtype):
        r = next((r for r in res.records if r["Decision Type"] == dtype), None)
        return r

    def run(s, **kw):
        return run_service(s, params, mode="scripted", say=lambda *a, **k: None, **kw)

    r = run(modified(base, hotel_data__pms_occupancy=None)).records[-1]
    rows.append(("Missing PMS data", "Context check", r["Execution Status"]))
    res = run(base, failures={"pos_history": "api_failure"})
    rows.append(("POS API failure", "Tool monitoring", "FALLBACK + ESCALATE" if res.context.fallback and
                 gov_of(res, "production_adjustment")["Escalation"] == "YES" else "not detected"))
    res = run(base, failures={"inventory": "stale"})
    rows.append(("Inventory feed stale", "Timestamp check", gov_of(res, "production_adjustment")["Execution Status"]
                 + " (" + gov_of(res, "production_adjustment")["Required Authority"] + ")"))
    res = run(base)
    rows.append(("Abnormal event demand", "Distribution shift", gov_of(res, "banquet_production_change")["Required Authority"]))
    low = modified(base, hotel_data__pos_history__last_7_services_forecast_ape=[0.25, 0.22, 0.28, 0.2, 0.24, 0.26, 0.21])
    res = run(low)
    rows.append(("Low confidence", "Confidence threshold", gov_of(res, "production_adjustment")["Required Authority"]
                 + f" (conf {gov_of(res, 'production_adjustment')['Confidence']})"))
    nowaste = modified(base, hotel_data__waste_history__leftover_rate_last_4_saturdays__pastry_bread=[0.1, 0.12, 0.09, 0.11],
                       kitchen_standing_plan_kg__pastry_bread=60.0)
    res = run(nowaste)
    rows.append(("Conflicting agents", "Orchestrator conflict", gov_of(res, "production_adjustment")["Required Authority"]))
    res = run(base)
    rows.append(("High-risk action", "Risk classification", gov_of(res, "banquet_production_change")["Required Authority"]))
    s = dict(base)
    s = modified(base, scripted_manager_choices__production_adjustment={"choice": "modify", "new_change_pct": -35,
                                                                       "reason": "Forecast disagreement"})
    res = run(s)
    rows.append(("Policy violation", "Hard constraint", gov_of(res, "production_adjustment")["Execution Status"]
                 + " (manager's −35% would plan a stockout)"))
    th = thresholds(params)
    ev = _evidence(params, None, guest_fb_score=4.55)
    lvl, _ = autonomy_level(evaluate_gate(ev, th), ev, th, drift([w["value"] for w in params["override_rate_history"]]))
    rows.append(("Guest score deterioration", "Experience guardrail", f"Autonomy → {lvl} (REDUCE AUTONOMY)"))
    hist = [w["value"] for w in params["override_rate_history"]][:-1] + [0.23]
    d = drift(hist)
    ev = _evidence(params, None)
    lvl, why = autonomy_level(evaluate_gate(ev, th), ev, th, d)
    rows.append(("Rising overrides", "AgentOps drift signal", f"Autonomy → {lvl} (REDUCE + INVESTIGATE: "
                 f"{d['current']:.0%} > 1.5 × {d['trailing_avg']:.1%})"))

    print("\n══ FAILURE-MODE MATRIX · every row executed, not described ══")
    print(f"   {'FAILURE':<26}{'DETECTION':<24}SYSTEM RESPONSE")
    for f, det, resp in rows:
        print(f"   {f:<26}{det:<24}{resp}")
    return rows


def cmd_trace(args, params):
    path = RUNS / args.run / "traces" / f"{args.decision_id}.json"
    if not path.exists():
        sys.exit(f"No trace at {path}. Run 'python -m hotel_agentops_sim run --auto' first.")
    t = json.loads(path.read_text())
    print(f"TRACE {t['decision_id']}  (INPUT → AGENT → GOVERNANCE → HUMAN → ACTION → OUTCOME → KPI)\n")
    print("INPUT        completeness", f"{t['input']['completeness']:.1%}", "·", t["input"]["context_status"])
    r = t["recommendation"]
    print(f"AGENT        {r['recommendation']}\n             why: {r['reason']}\n             confidence {r['confidence']:.1%} · risk {r['risk_level']} · reversibility {r['reversibility']}")
    print("GOVERNANCE   " + "\n             ".join(t["governance"]["rule_trace"]))
    h = t["human"]
    print("HUMAN        " + (f"{h['choice'].upper()} by {h['approver']} at {h['timestamp']}"
                             + (f" · override: {h['override_reason']}" if h["override"] else "") if h else "none (no human step)"))
    print(f"ACTION       {t['action']['final_action']} → {t['action']['status']}")
    o = t["outcome"] or {}
    print(f"OUTCOME      {o.get('summary', '')}")
    print(f"KPI          {t['kpi_contribution']}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hotel_agentops_sim", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run one breakfast service end to end")
    r.add_argument("--auto", action="store_true", help="use the scenario's scripted manager choices")
    r.add_argument("--quiet", action="store_true")
    t = sub.add_parser("test", help="run a failure test")
    t.add_argument("name", choices=["missing-context", "tool-reliability", "guest-score"])
    sub.add_parser("failure-matrix", help="execute all 10 failure modes")
    tr = sub.add_parser("trace", help="follow one decision end to end")
    tr.add_argument("decision_id")
    tr.add_argument("--run", default="day1")
    sub.add_parser("demo", help="non-interactive: day run, three failure tests, failure matrix")
    args = ap.parse_args(argv)
    params = load_parameters()

    if args.cmd == "run":
        cmd_run(args, params)
    elif args.cmd == "test":
        ok = {"missing-context": test_missing_context, "tool-reliability": test_tool_reliability,
              "guest-score": test_guest_score}[args.name](params)
        sys.exit(0 if ok else 1)
    elif args.cmd == "failure-matrix":
        failure_matrix(params)
    elif args.cmd == "trace":
        cmd_trace(args, params)
    elif args.cmd == "demo":
        args.auto, args.quiet = True, False
        cmd_run(args, params)
        results = [test_missing_context(params, True), test_tool_reliability(params, True), test_guest_score(params, True)]
        failure_matrix(params)
        print(f"\nFailure tests passed: {sum(results)}/3")
        print("\nNext: python -m hotel_agentops_sim trace D-0418")


if __name__ == "__main__":
    main()
