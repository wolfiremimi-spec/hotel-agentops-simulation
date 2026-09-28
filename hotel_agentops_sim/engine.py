"""Runs one service through the whole operating system:

HOTEL DATA → CONTEXT → SPECIALIST AGENTS → ORCHESTRATOR → RECOMMENDATION → GOVERNANCE CHECK
→ HUMAN APPROVAL (if required) → ACTION → ACTUAL OUTCOME → AGENTOPS → READINESS GATE
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import governance
from .agentops import autonomy_level, day_metrics, drift, evaluate_gate
from .agents import DemandAgent, InventoryAgent, ProductionAgent, WasteAgent
from .approval import ApprovalQueue
from .context import ContextManager
from .learning import learning_cases
from .models import GovernanceResult, HumanDecision, Recommendation, ToolCall
from .orchestrator import GROUP_LABEL, Orchestrator
from .outcome import production_outcome, simple_outcome
from .parameters import thresholds as load_thresholds, value


class SimClock:
    """Simulated clock so every run is reproducible."""

    def __init__(self, start: str):
        h, m = map(int, start.split(":"))
        self.minutes = h * 60 + m

    def now(self) -> str:
        return f"{self.minutes // 60:02d}:{self.minutes % 60:02d}"

    def tick(self, minutes: int = 1) -> str:
        self.minutes += minutes
        return self.now()


@dataclass
class RunResult:
    scenario_id: str
    service: str
    records: list[dict]
    traces: dict
    tool_calls: list
    executions: list
    gate: dict
    autonomy: str
    autonomy_why: list[str]
    context: object
    metrics: dict = field(default_factory=dict)
    learning: list[dict] = field(default_factory=list)
    guardrail_events: list[str] = field(default_factory=list)


def _scaled_plan(rec: Recommendation, new_change_pct: float) -> dict:
    standing = sum(rec.details["standing_plan_kg"][g] for g in rec.details["plan_kg"])
    target = standing * (1 + new_change_pct / 100)
    factor = target / sum(rec.details["plan_kg"].values())
    return {g: round(kg * factor, 1) for g, kg in rec.details["plan_kg"].items()}


def run_service(scenario: dict, params: dict, *, evidence: dict | None = None, override_history: list | None = None,
                failures: dict | None = None, mode: str = "scripted", approval: ApprovalQueue | None = None,
                say=print) -> RunResult:
    th = load_thresholds(params)
    ctx_threshold = value(params, "context_completeness_threshold")
    delegated_range = value(params, "delegated_prep_range")
    cost_kg = value(params, "waste_cost_per_kg")
    categories = [c["reason"] for c in params["override_categories"]]
    observed = scenario["observed_outcome"]
    truth = scenario["ground_truth_escalation_required"]
    standing = {k: v for k, v in scenario["kitchen_standing_plan_kg"].items() if not k.startswith("_")}
    guest_base = scenario["hotel_data"].get("guest_experience_signal", {}).get("recent_guest_fb_score", 4.6)
    clock = SimClock(scenario["run_clock"])
    approval = approval or ApprovalQueue(mode, scenario.get("scripted_manager_choices"), categories, output_fn=say)

    # ---- Readiness gate → today's autonomy level -----------------------------------------------
    if evidence is None:
        evidence = {k: v["value"] for k, v in params["latest_gate_evidence"].items()}
    history = override_history or [w["value"] for w in params["override_rate_history"]]
    gate = evaluate_gate(evidence, th)
    drift_state = drift(history, params["drift_rule"]["multiplier"], params["drift_rule"]["trailing_weeks"])
    level, level_why = autonomy_level(gate, evidence, th, drift_state)
    say(f"\n① READINESS GATE (evidence week {evidence.get('week', 'custom')}): {gate['result']}"
        f" · first blocker: {gate['first_blocker']} → autonomy level {level}")
    for w in level_why:
        say(f"   {w}")

    # ---- Hotel data → context ------------------------------------------------------------------
    ctx = ContextManager.load(scenario["hotel_data"], value(params, "required_context_sources"), failures)
    say(f"\n② CONTEXT · {clock.now()} · {len(ctx.present)}/{len(ctx.required)} sources · completeness {ctx.completeness:.1%}")
    for s in ctx.required:
        say(f"   {'✓' if ctx.status[s] == 'ok' else '!' if ctx.status[s] in ('fallback', 'stale') else '✗'} "
            f"{s:<24} {ctx.status[s]}")

    tool_calls: list[ToolCall] = list(ctx.tool_calls)
    executions: list[ToolCall] = []
    records, traces, guardrail = [], {}, []
    number = scenario["first_decision_number"]

    def record(rec: Recommendation, gov, human: HumanDecision | None, final_action: str, exec_status: str,
               outcome, policy_violation_executed=False, forecast_ape=None) -> dict:
        decided = human is not None and human.choice in ("approve", "modify", "reject")
        row = {
            "Decision ID": rec.decision_id, "Timestamp": rec.timestamp, "Service": rec.service,
            "Agent(s)": " + ".join(rec.agents), "Recommendation": rec.recommendation,
            "Confidence": f"{rec.confidence:.1%}", "Risk": rec.risk_level, "Reversibility": rec.reversibility,
            "Context Completeness": f"{rec.context_completeness:.1%}", "Policy Status": gov.policy_status,
            "Required Authority": gov.required_authority, "Human Approval Required": "YES" if gov.human_approval_required else "NO",
            "AI Recommendation": rec.recommendation,
            "Human Decision": (human.choice.upper().replace("_", " ") + f" ({human.approver})") if human else "None (no human step)",
            "Final Action": final_action, "Override": "YES" if human and human.override else "NO",
            "Override Reason": human.override_reason if human else "", "Execution Status": exec_status,
            "Actual Outcome": outcome.summary if outcome else "",
            "Waste Impact": "" if not outcome or outcome.waste_impact_kg is None else f"{outcome.waste_impact_kg:+.1f} kg",
            "Guest Impact": outcome.guest_impact if outcome else "",
            "Financial Impact": "" if not outcome or outcome.financial_impact_usd is None else f"${outcome.financial_impact_usd:,.2f}",
            "Escalation": "YES" if gov.escalate else "NO",
            "AgentOps Status": "Logged · counts updated" + (" · outcome pending" if outcome and "PENDING" in outcome.summary else ""),
            "Decision Type": rec.decision_type, "Approver": human.approver if human else "",
            "Decision Timestamp": human.timestamp if human else "", "Scenario": scenario["scenario_id"],
            # private fields for metrics (not written to the CSV)
            "_decided": decided, "_accepted": decided and human.choice == "approve",
            "_escalation_required": truth.get(rec.decision_type, False),
            "_policy_violation_executed": policy_violation_executed, "_forecast_ape": forecast_ape,
            "_note": human.note if human else "",
            "_outcome_actual": (outcome.actual if outcome else {}),
        }
        records.append(row)
        traces[rec.decision_id] = {
            "decision_id": rec.decision_id, "input": {"context_status": ctx.status, "completeness": ctx.completeness},
            "recommendation": {k: getattr(rec, k) for k in ("decision_type", "recommendation", "reason", "confidence",
                                                            "risk_level", "reversibility", "expected_impact")},
            "details": rec.details, "governance": {"authority": gov.authority, "rule_trace": gov.rule_trace},
            "human": human.__dict__ if human else None, "action": {"final_action": final_action, "status": exec_status},
            "outcome": outcome.__dict__ if outcome else None,
            "kpi_contribution": {"forecast_ape": forecast_ape, "escalated": gov.escalate,
                                 "escalation_required": truth.get(rec.decision_type, False)},
        }
        return row

    # ---- Guardrail / drift breaches: FLAG → ESCALATE → REDUCE AUTONOMY → HUMAN REVIEW ----------
    if level == "BOUNDED":
        for why in level_why:
            kind = "override_drift_investigation" if "Override rate" in why else "guardrail_escalation"
            rec = Recommendation(
                decision_id=f"D-{number:04d}", timestamp=clock.now(), decision_type=kind, service=scenario["service"],
                agents=["AgentOps monitor"], recommendation="Reduce autonomy to BOUNDED and request human review",
                reason=why, confidence=1.0, risk_level="HIGH", reversibility="HIGH", context_completeness=ctx.completeness)
            steps = ["FLAG: " + why, "ESCALATE to F&B leadership and Risk / Governance",
                     "REDUCE AUTONOMY: all agent actions limited to recommend-only or manager approval",
                     "HUMAN REVIEW required before autonomy can be restored"]
            gov = GovernanceResult("HUMAN_DECISION", "Human review · mandatory escalation", True, True, "PASS", steps)
            say(f"\n⚑ GUARDRAIL · {rec.decision_id}")
            for line in steps:
                say(f"   {line}")
            record(rec, gov, None, "Autonomy reduced to BOUNDED · awaiting human review", "ESCALATED", None)
            guardrail.append(why)
            number += 1

    # ---- Abstention: the system refuses to act without enough context --------------------------
    if ctx.completeness < ctx_threshold:
        rec = Recommendation(
            decision_id=f"D-{number:04d}", timestamp=clock.tick(2), decision_type="abstain_missing_context",
            service=scenario["service"], agents=["Orchestrator"],
            recommendation="No production recommendation issued. Kitchen keeps its standing plan until the missing data is restored.",
            reason=f"Required context missing: {', '.join(ctx.missing)}.", confidence=0.0, risk_level="MEDIUM",
            reversibility="HIGH", context_completeness=ctx.completeness,
            details={"usable_carry_over_kg": scenario["hotel_data"].get("inventory", {}).get("carry_over_kg", {})})
        gov = governance.evaluate(rec, context=ctx, autonomy_level=level, context_threshold=ctx_threshold,
                                  delegated_range=delegated_range)
        say(f"\n③ GOVERNANCE · {rec.decision_id}")
        for line in gov.rule_trace:
            say(f"   {line}")
        say(f"   ESCALATED to {approval.approver}: '{rec.reason} No AI action taken.'")
        out = production_outcome(rec, None, observed, standing, cost_kg, guest_base, executed=False)
        out.summary = "Standing plan served. " + f"Waste {out.actual['waste_kg']} kg · {out.actual['actual_covers']} covers."
        record(rec, gov, None, "No AI action · abstained and escalated", "ABSTAINED · ESCALATED", out)
        return _finish(scenario, records, traces, tool_calls, executions, gate, level, level_why, ctx, params, guardrail)

    # ---- Specialist agents ---------------------------------------------------------------------
    demand = DemandAgent().run(ctx.view(DemandAgent.READS))
    inventory = InventoryAgent().run(ctx.view(InventoryAgent.READS))
    waste = WasteAgent().run(ctx.view(WasteAgent.READS))
    producer = ProductionAgent()
    draft = producer.draft(demand, inventory, waste, standing)
    tool_calls += [ToolCall(f"agent:{a}", ok=True) for a in ("demand", "inventory", "waste", "production.draft")]
    say("\n③ SPECIALIST AGENTS")
    say(f"   Demand     {demand.outputs['demand_signal']} · confidence {demand.confidence:.1%}"
        f" (1 − trailing MAPE {demand.outputs['trailing_mape']:.1%})")
    say(f"   Inventory  usable carry-over {inventory.outputs['usable_carry_over_kg']} · {inventory.outputs['inventory_risk']}")
    say(f"   Waste      {waste.outputs['historical_pattern']}")
    say(f"   Production draft {draft.outputs['standing_total_kg']:.0f} → {draft.outputs['planned_total_kg']:.0f} kg "
        f"({draft.outputs['change']:+.1%}) · " + ", ".join(f"{GROUP_LABEL[l['group']]} {l['change']:+.0%}" for l in draft.outputs["lines"]))

    orch = Orchestrator(delegated_range)
    clock.tick(2)
    recs, conflict = orch.coordinate(number=number, clock=clock.now, service=scenario["service"],
                                     completeness=ctx.completeness, demand=demand, inventory=inventory,
                                     waste=waste, production=draft, standing_plan=standing)
    say(f"\n④ ORCHESTRATOR · {len(recs)} recommendations · conflict check: {conflict['note']}")

    for rec in recs:
        gov = governance.evaluate(rec, context=ctx, autonomy_level=level, context_threshold=ctx_threshold,
                                  delegated_range=delegated_range, conflict=conflict)
        rec.policy_status, rec.required_authority = gov.policy_status, gov.required_authority
        rec.human_approval_required = gov.human_approval_required
        say(f"\n⑤ GOVERNANCE · {rec.decision_id} · {rec.recommendation}")
        for line in gov.rule_trace:
            say(f"   {line}")

        human, final_plan, final_action, executed, violation = None, None, "", False, False
        if gov.authority in ("MANAGER_APPROVAL", "HUMAN_DECISION"):
            human = approval.route(rec, gov, at=_plus(rec.timestamp, 3))
            if human.choice == "approve":
                executed, final_plan, final_action = True, rec.details.get("plan_kg"), rec.recommendation
            elif human.choice == "modify" and rec.decision_type == "production_adjustment":
                final_plan = _scaled_plan(rec, human.final_change_pct)
                problems = governance.policy_check(rec, final_plan)
                if problems:
                    say("   ✗ Manager modification BLOCKED by policy: " + "; ".join(problems))
                    gov.policy_status = "VIOLATION (modification): " + "; ".join(problems)
                    final_action, final_plan = "Modification blocked · kitchen keeps standing plan", None
                    gov.escalate = True
                else:
                    executed = True
                    final_action = f"Modified by manager to {human.final_change_pct:+.0f}% ({sum(final_plan.values()):.0f} kg)"
            elif human.choice == "modify":
                executed = True
                final_action = f"Modified by manager to {human.final_change_pct:+.0f}%"
            elif human.choice == "reject":
                final_action = "Rejected · no change"
            else:
                final_action = "Held · more context requested"
        elif gov.authority == "EXECUTE":
            executed, final_plan, final_action = True, rec.details.get("plan_kg"), rec.recommendation + " (delegated)"
        elif gov.authority == "RECOMMEND_ONLY":
            final_action = "Shown to manager as a recommendation · not executed"
        else:
            final_action = "No action · " + gov.authority.lower()

        # ---- Action: only the authorized agent may write ----
        if executed:
            auth = f"{rec.decision_id}:{human.approver if human else 'delegated'}"
            if rec.details.get("executor") == "Production Agent":
                call = producer.execute(final_plan or {}, authorization=auth)
            elif rec.details.get("executor"):
                call = ToolCall(f"write:{rec.details['write_scope']}", ok=True, note=f"authorized by {auth}")
            else:
                call = ToolCall("write:purchase_order (entered by manager)", ok=True, note=f"authorized by {auth}")
            executions.append(call)
            tool_calls.append(call)
        status = ("EXECUTED" if executed else "BLOCKED" if gov.authority == "BLOCK" or final_action.startswith("Modification blocked")
                  else "AWAITING CONTEXT" if human and human.choice == "more_context"
                  else "NOT EXECUTED")
        say(f"⑥ ACTION · {final_action} → {status}")

        # ---- Outcome ----
        if rec.decision_type == "production_adjustment":
            out = production_outcome(rec, final_plan, observed, standing, cost_kg, guest_base, executed)
            ape = out.actual["forecast_ape"]
            say(f"⑦ OUTCOME · {out.summary} · {out.guest_impact}")
        else:
            out, ape = simple_outcome(rec, executed, cost_kg), None
            say(f"⑦ OUTCOME · {out.summary}")
        record(rec, gov, human, final_action, status, out, violation, ape)

    return _finish(scenario, records, traces, tool_calls, executions, gate, level, level_why, ctx, params, guardrail)


def _plus(hhmm: str, minutes: int) -> str:
    h, m = map(int, hhmm.split(":"))
    t = h * 60 + m + minutes
    return f"{t // 60:02d}:{t % 60:02d}"


def _finish(scenario, records, traces, tool_calls, executions, gate, level, level_why, ctx, params, guardrail):
    res = RunResult(scenario["scenario_id"], scenario["service"], records, traces, tool_calls, executions,
                    gate, level, level_why, ctx, guardrail_events=guardrail)
    res.metrics = day_metrics(records, tool_calls, executions)
    res.learning = learning_cases(records, params["override_categories"])
    return res
