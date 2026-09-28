"""AI specialist agents (case study layer 3) with output verification (layer 5).

Each agent is a language model (Gemini) that answers its role's question from the case study, using tools. It can only
read the sources its role grants: reads go through the engine's least-privilege AgentView, which raises on anything
else. It must finish by calling a typed `submit` tool. Its proposal is then verified against hard bounds before use.

The verification principle: an AI agent may make the system MORE cautious, never less. It may lower its own confidence
but never raise it; escalate a conflict but never quietly resolve one; flag a group only with evidence in the data.
Governance, the policy check (no planned stockouts) and the readiness gate are untouched. If the model fails or its
output fails verification, the rule-based agent's analysis is used and the fallback is logged.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field

from hotel_agentops_sim.agents import DemandAgent, InventoryAgent, ProductionAgent, WasteAgent
from hotel_agentops_sim.agents.production import BUFFER_CHRONIC, BUFFER_STANDARD, BUFFER_STOCKOUT
from hotel_agentops_sim.context import ContextPermissionError
from hotel_agentops_sim.models import AgentOutput
from hotel_agentops_sim.orchestrator import GROUP_LABEL
from product import agent as llm

SOURCES = ["pms_occupancy", "reservations", "pos_history", "inventory", "shelf_life", "waste_history", "event_schedule",
           "guest_experience_signal"]
MAX_DEMAND_ADJUSTMENT = 0.15        # the AI may move expected covers at most ±15% from the statistical forecast
MAX_CONFIDENCE_CUT = 0.20           # and may lower (never raise) forecast confidence by up to 20 points
CHRONIC_EVIDENCE = 0.15             # a group may be called chronic overproduction only if avg leftover ≥ 15%
BUFFER_RANGE = (0.02, 0.15)         # production buffers the AI may choose from
MAX_ROUNDS = 5


@dataclass
class AIConfig:
    api_key: str
    models: list = field(default_factory=lambda: list(llm.FALLBACK_MODELS))
    cache: dict = field(default_factory=dict)          # proposals keyed by agent + inputs, so reruns are identical
    state: dict = field(default_factory=dict)          # remembers which model answered
    reports: list = field(default_factory=list)        # one entry per agent for the audit trail


def _key(name, payload) -> str:
    return name + ":" + hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:24]


def _ask(cfg: AIConfig, name: str, system: str, brief: dict, tools: dict, submit_schema: dict,
         fingerprint=None) -> tuple[dict, list]:
    """Tool-using loop that ends when the model calls `submit`. Cached by the brief plus the data the agent can read."""
    k = _key(name, {"brief": brief, "data": fingerprint})
    if k in cfg.cache:
        hit = cfg.cache[k]
        return copy.deepcopy(hit["proposal"]), hit["steps"] + [{"tool": "(cached proposal reused)", "args": {}}]
    decls = [t["decl"] for t in tools.values()] + [{"name": "submit", "description": "Submit your final analysis. Call exactly once.",
                                                    "parameters": submit_schema}]
    contents = [{"role": "user", "parts": [{"text": json.dumps(brief, default=str)}]}]
    steps = []
    for _ in range(MAX_ROUNDS):
        data = llm.call_model(contents, system, decls, cfg.api_key, cfg.models, cfg.state)
        cands = data.get("candidates") or []
        if not cands or not cands[0].get("content", {}).get("parts"):
            raise llm.AgentError("the model returned no answer")
        content = cands[0]["content"]
        content.setdefault("role", "model")
        contents.append(content)
        calls = [p["functionCall"] for p in content["parts"] if "functionCall" in p]
        if not calls:
            contents.append({"role": "user", "parts": [{"text": "Call the submit tool with your analysis."}]})
            continue
        parts = []
        for c in calls:
            nm, args = c.get("name"), c.get("args") or {}
            if nm == "submit":
                steps.append({"tool": "submit", "args": args})
                cfg.cache[k] = {"proposal": copy.deepcopy(args), "steps": steps}
                return args, steps
            fn = tools.get(nm, {}).get("fn")
            try:
                result = fn(args) if fn else {"error": f"unknown tool {nm}"}
            except ContextPermissionError as ex:
                result = {"error": f"PERMISSION DENIED: {ex}"}
            except Exception as ex:                              # keep the loop alive; the model sees the error
                result = {"error": f"{type(ex).__name__}: {ex}"}
            steps.append({"tool": nm, "args": args, "result_summary": str(result)[:200]})
            fr = {"name": nm, "response": {"result": result}}
            if c.get("id"):
                fr["id"] = c["id"]
            parts.append({"functionResponse": fr})
        contents.append({"role": "user", "parts": parts})
    raise llm.AgentError("the agent did not submit an analysis in time")


def _read_tool(view):
    return {"read_source": {
        "decl": {"name": "read_source", "description": "Read one source from the shared hotel context. Access is limited to "
                                                       "the sources your role may read; others are denied.",
                 "parameters": {"type": "object", "properties": {"source": {"type": "string", "enum": SOURCES}},
                                "required": ["source"]}},
        "fn": lambda a: view.get(a.get("source"))}}


def _baseline_tool(name, output):
    return {"get_rule_based_analysis": {
        "decl": {"name": "get_rule_based_analysis", "description": f"The deterministic {name} analysis of the same data "
                                                                  "(statistical baseline you may refine within bounds)."},
        "fn": lambda a: output.outputs | {"confidence": output.confidence}}}


def _system(role, question, reads, writes, bounds):
    return (f"You are the {role} in a hotel's governed multi-agent food production system. Your question: \"{question}\" "
            f"You may READ: {reads}. You may WRITE: {writes}. You cannot purchase, execute, or approve anything. "
            "Use read_source for the data you need and get_rule_based_analysis for the statistical baseline. "
            "Look for signals the rules miss, especially free-text notes. Ground every judgment in data you read; "
            f"do not invent numbers. Bounds: {bounds} Then call submit exactly once with a short, specific rationale "
            "(what you saw, what you changed, why). If nothing justifies a change, submit the baseline unchanged.")


def _report(cfg, agent, status, rationale="", changes=None, checks=None, steps=None, error=""):
    cfg.reports.append({"agent": agent, "status": status, "model": cfg.state.get("model"), "rationale": rationale,
                        "changes": changes or [], "verification": checks or [], "tools": [s["tool"] for s in steps or []],
                        "error": error})


# ---------------------------------------------------------------------------
class AIDemandAgent(DemandAgent):
    def __init__(self, cfg: AIConfig):
        self.cfg = cfg

    def run(self, view) -> AgentOutput:
        base = super().run(view)
        out = copy.deepcopy(base)
        brief = {"task": "Forecast breakfast covers for this service.", "sources_you_may_read": self.READS}
        seen = {s: view.get(s) for s in self.READS}
        schema = {"type": "object", "properties": {
            "expected_covers": {"type": "integer"},
            "confidence_adjustment": {"type": "number", "description": "0 or negative: lower confidence if the data is shaky"},
            "rationale": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}}}, "required": ["expected_covers", "rationale"]}
        try:
            p, steps = _ask(self.cfg, "demand", _system(
                self.name, self.question, "PMS, reservations (incl. front-desk notes), POS history, events", "none",
                f"expected_covers within ±{MAX_DEMAND_ADJUSTMENT:.0%} of the statistical forecast "
                f"({base.outputs['expected_covers']}); confidence may only go down, by at most {MAX_CONFIDENCE_CUT:.0%}."),
                brief, {**_read_tool(view), **_baseline_tool(self.name, base)}, schema, seen)
        except Exception as ex:
            _report(self.cfg, self.name, "fallback", error=str(ex))
            return base
        checks, stat = [], base.outputs["expected_covers"]
        try:
            covers = int(round(float(p.get("expected_covers", stat))))
        except (TypeError, ValueError):
            covers = stat
            checks.append("expected_covers not a number → statistical forecast kept")
        lo, hi = round(stat * (1 - MAX_DEMAND_ADJUSTMENT)), round(stat * (1 + MAX_DEMAND_ADJUSTMENT))
        if not lo <= covers <= hi:
            _report(self.cfg, self.name, "rejected", p.get("rationale", ""), [], [f"expected_covers {covers} outside the "
                    f"allowed {lo}–{hi} → REJECTED, rule-based forecast used"], steps)
            return base
        cut = float(p.get("confidence_adjustment") or 0.0)
        if cut > 0:
            checks.append(f"confidence increase {cut:+.2f} not allowed → ignored")
            cut = 0.0
        cut = max(cut, -MAX_CONFIDENCE_CUT)
        changes = []
        if covers != stat:
            last = base.outputs["last_week_covers"]
            per = base.outputs["consumption_kg_per_cover"]
            change = covers / last - 1
            out.outputs.update(expected_covers=covers, demand_change=round(change, 3),
                               expected_consumption_kg={g: round(covers * kg, 1) for g, kg in per.items()},
                               demand_signal=(f"Expected covers {'up' if change > 0 else 'down'} {abs(change):.0%} vs the "
                                              f"last comparable service ({last} → {covers}; AI-adjusted from the statistical "
                                              f"forecast of {stat})"))
            changes.append(f"covers {stat} → {covers}")
        if cut < 0:
            out.confidence = round(max(base.confidence + cut, 0.0), 3)
            changes.append(f"confidence {base.confidence:.1%} → {out.confidence:.1%}")
        out.notes = list(out.notes) + ["AI: " + str(p.get("rationale", ""))[:300]]
        out.outputs["ai_rationale"] = str(p.get("rationale", ""))[:500]
        _report(self.cfg, self.name, "adjusted" if changes else "accepted", p.get("rationale", ""), changes,
                checks or ["within bounds"], steps)
        return out


class AIInventoryAgent(InventoryAgent):
    def __init__(self, cfg: AIConfig):
        self.cfg = cfg

    def run(self, view) -> AgentOutput:
        base = super().run(view)
        out = copy.deepcopy(base)
        brief = {"task": "Decide what stock is usable today and flag risks.", "sources_you_may_read": self.READS}
        seen = {s: view.get(s) for s in self.READS}
        schema = {"type": "object", "properties": {
            "exclude_carry_over_groups": {"type": "array", "items": {"type": "string", "enum": list(GROUP_LABEL)},
                                          "description": "Groups whose carry-over should NOT be used (quality, notes)"},
            "rationale": {"type": "string"}}, "required": ["rationale"]}
        try:
            p, steps = _ask(self.cfg, "inventory", _system(
                self.name, self.question, "inventory (incl. kitchen notes), procurement, shelf life", "inventory recommendation",
                "you may exclude carry-over you judge unusable, but never add stock that isn't recorded."),
                brief, {**_read_tool(view), **_baseline_tool(self.name, base)}, schema, seen)
        except Exception as ex:
            _report(self.cfg, self.name, "fallback", error=str(ex))
            return base
        changes = []
        for g in p.get("exclude_carry_over_groups") or []:
            if g in out.outputs["usable_carry_over_kg"] and out.outputs["usable_carry_over_kg"][g] > 0:
                changes.append(f"{GROUP_LABEL[g]} carry-over {out.outputs['usable_carry_over_kg'][g]} kg excluded")
                out.outputs["usable_carry_over_kg"][g] = 0.0
                out.outputs["excluded"] = list(out.outputs["excluded"]) + [f"{g}: excluded by AI judgment"]
        out.outputs["ai_rationale"] = str(p.get("rationale", ""))[:500]
        _report(self.cfg, self.name, "adjusted" if changes else "accepted", p.get("rationale", ""), changes,
                ["can only reduce usable stock"], steps)
        return out


class AIWasteAgent(WasteAgent):
    def __init__(self, cfg: AIConfig):
        self.cfg = cfg

    def run(self, view) -> AgentOutput:
        base = super().run(view)
        out = copy.deepcopy(base)
        wh = view.get("waste_history")
        avg, stock = base.outputs["avg_leftover_rate"], wh["stockouts_last_4_saturdays"]
        brief = {"task": "Explain where and why food is lost; classify groups.", "sources_you_may_read": self.READS}
        seen = {s: view.get(s) for s in self.READS}
        schema = {"type": "object", "properties": {
            "chronic_overproduction": {"type": "array", "items": {"type": "string", "enum": list(GROUP_LABEL)}},
            "stockout_prone": {"type": "array", "items": {"type": "string", "enum": list(GROUP_LABEL)}},
            "rationale": {"type": "string"}}, "required": ["chronic_overproduction", "stockout_prone", "rationale"]}
        try:
            p, steps = _ask(self.cfg, "waste", _system(
                self.name, self.question, "waste logs, POS consumption", "waste insights",
                f"a group may be chronic overproduction only if its average leftover is ≥ {CHRONIC_EVIDENCE:.0%}; "
                "a group may be stockout-prone only if it ran out at least once; groups the rules flag as stockout-prone stay flagged."),
                brief, {**_read_tool(view), **_baseline_tool(self.name, base)}, schema, seen)
        except Exception as ex:
            _report(self.cfg, self.name, "fallback", error=str(ex))
            return base
        checks = []
        chronic = []
        for g in p.get("chronic_overproduction") or []:
            if g in avg and avg[g] >= CHRONIC_EVIDENCE:
                chronic.append(g)
            elif g in avg:
                checks.append(f"{g} chronic rejected: avg leftover {avg[g]:.0%} < {CHRONIC_EVIDENCE:.0%}")
        prone = list(base.outputs["stockout_prone"])
        for g in p.get("stockout_prone") or []:
            if g not in prone:
                if stock.get(g, 0) >= 1:
                    prone.append(g)
                else:
                    checks.append(f"{g} stockout-prone rejected: no stockouts on record")
        dropped = [g for g in base.outputs["stockout_prone"] if g not in (p.get("stockout_prone") or [])]
        if dropped:
            checks.append("kept stockout-prone flags the AI dropped (safety): " + ", ".join(dropped))
        changes = []
        if sorted(chronic) != sorted(base.outputs["chronic_overproduction"]):
            changes.append(f"chronic {base.outputs['chronic_overproduction']} → {chronic}")
        if sorted(prone) != sorted(base.outputs["stockout_prone"]):
            changes.append(f"stockout-prone {base.outputs['stockout_prone']} → {prone}")
        out.outputs.update(chronic_overproduction=chronic, stockout_prone=prone,
                           likely_source={g: "overproduction" for g in chronic},
                           waste_risk_signal="HIGH" if chronic else "NORMAL",
                           historical_pattern=("; ".join([f"{g}: avg leftover {avg[g]:.0%}" for g in chronic]
                                                         + [f"{g}: stocked out {stock.get(g, 0)} of last 4" for g in prone])
                                               or "No chronic pattern") + " (AI-reviewed)",
                           ai_rationale=str(p.get("rationale", ""))[:500])
        out.confidence = min([sum(r > 0.20 for r in wh["leftover_rate_last_4_saturdays"][g]) /
                              len(wh["leftover_rate_last_4_saturdays"][g]) for g in chronic], default=1.0)
        _report(self.cfg, self.name, "adjusted" if changes else "accepted", p.get("rationale", ""), changes,
                checks or ["evidence checks passed"], steps)
        return out


class AIProductionAgent(ProductionAgent):
    """Sizes the plan from the other agents' signals only (it reads no raw hotel data). Execution stays authorized-only."""

    def __init__(self, cfg: AIConfig):
        self.cfg = cfg

    def draft(self, demand, inventory, waste, standing_plan):
        base = super().draft(demand, inventory, waste, standing_plan)
        chronic, stockout = waste.outputs["chronic_overproduction"], waste.outputs["stockout_prone"]
        base_buf = {l["group"]: l["buffer"] for l in base.outputs["lines"]}
        brief = {"task": "Choose a safety buffer per item group for tomorrow's plan.",
                 "signals": {"expected_consumption_kg": demand.outputs["expected_consumption_kg"],
                             "usable_carry_over_kg": inventory.outputs["usable_carry_over_kg"],
                             "chronic_overproduction": chronic, "stockout_prone": stockout,
                             "demand_notes": demand.outputs.get("ai_rationale", ""),
                             "rule_based_buffers": base_buf, "standing_plan_kg": standing_plan}}
        schema = {"type": "object", "properties": {
            "buffers": {"type": "object", "properties": {g: {"type": "number"} for g in GROUP_LABEL}},
            "rationale": {"type": "string"}}, "required": ["buffers", "rationale"]}
        try:
            p, steps = _ask(self.cfg, "production", _system(
                self.name, self.question, "the other agents' signals only (no raw data)", "production plan, within threshold",
                f"each buffer between {BUFFER_RANGE[0]:.0%} and {BUFFER_RANGE[1]:.0%}; stockout-prone groups at least "
                f"{BUFFER_STOCKOUT:.0%}. Governance decides whether the plan may run."),
                brief, {}, schema)
        except Exception as ex:
            _report(self.cfg, self.name, "fallback", error=str(ex))
            return base
        checks, buffers = [], {}
        for g, need in demand.outputs["expected_consumption_kg"].items():
            try:
                b = float((p.get("buffers") or {}).get(g, base_buf[g]))
            except (TypeError, ValueError):
                b = base_buf[g]
            b2 = min(max(b, BUFFER_RANGE[0]), BUFFER_RANGE[1])
            if g in stockout:
                b2 = max(b2, BUFFER_STOCKOUT)
            if abs(b2 - b) > 1e-9:
                checks.append(f"{g} buffer {b:.0%} → {b2:.0%} (bounds)")
            buffers[g] = b2
        usable = inventory.outputs["usable_carry_over_kg"]
        plan, lines = {}, []
        for g, need in demand.outputs["expected_consumption_kg"].items():
            kg = round(max(need * (1 + buffers[g]) - usable.get(g, 0.0), 0.0), 1)
            plan[g] = kg
            lines.append({"group": g, "expected_consumption_kg": need, "buffer": buffers[g],
                          "usable_carry_over_kg": usable.get(g, 0.0), "planned_kg": kg,
                          "standing_plan_kg": standing_plan[g], "change": round(kg / standing_plan[g] - 1, 3)})
        total, stand = round(sum(plan.values()), 1), round(sum(standing_plan[g] for g in plan), 1)
        changes = [f"{g} buffer {base_buf[g]:.0%} → {buffers[g]:.0%}" for g in buffers if abs(buffers[g] - base_buf[g]) > 1e-9]
        _report(self.cfg, self.name, "adjusted" if changes else "accepted", p.get("rationale", ""), changes,
                checks or ["within bounds"], steps)
        return AgentOutput(agent=self.name, question=self.question, reads=["(signals from Demand, Inventory, Waste agents)"],
                           confidence=demand.confidence,
                           outputs={"plan_kg": plan, "lines": lines, "planned_total_kg": total, "standing_total_kg": stand,
                                    "change": round(total / stand - 1, 4), "ai_rationale": str(p.get("rationale", ""))[:500]})


def conflict_reviewer(cfg: AIConfig):
    """Orchestrator review: the AI may escalate a plan for a human's eyes, never mark an unresolved conflict resolved."""
    def review(conflict, demand, waste, draft):
        brief = {"task": "Review how the agents' signals combine. Escalate if something looks wrong for guests or the kitchen.",
                 "rule_based_conflict_check": conflict,
                 "demand": {k: demand.outputs.get(k) for k in ("expected_covers", "demand_change", "demand_signal", "ai_rationale")},
                 "waste": {k: waste.outputs.get(k) for k in ("chronic_overproduction", "stockout_prone", "historical_pattern")},
                 "production": {"change": draft.outputs["change"], "lines": draft.outputs["lines"]}}
        schema = {"type": "object", "properties": {"escalate": {"type": "boolean"}, "note": {"type": "string"}},
                  "required": ["escalate", "note"]}
        try:
            p, steps = _ask(cfg, "orchestrator", (
                "You are the Orchestrator: \"How do these signals combine into one operational decision?\" You coordinate; you "
                "execute nothing and have no purchasing authority. Review the combined plan. If the signals conflict in a way "
                "that could hurt guests or the kitchen, escalate for a human. You can escalate, but you cannot resolve a "
                "conflict the rules left unresolved. Call submit once with escalate and a one-sentence note."), brief, {}, schema)
        except Exception as ex:
            _report(cfg, "Orchestrator", "fallback", error=str(ex))
            return {}
        if p.get("escalate"):
            _report(cfg, "Orchestrator", "adjusted", p.get("note", ""), ["escalated for human review"], ["escalation allowed"], steps)
            return {"conflict": True, "resolved": False,
                    "note": (conflict.get("note", "") + " · AI orchestrator escalated: " + str(p.get("note", ""))[:200]).strip(" ·")}
        _report(cfg, "Orchestrator", "accepted", p.get("note", ""), [], ["no change to the rule-based conflict result"], steps)
        return {}
    return review


def build_agents(cfg: AIConfig) -> dict:
    return {"demand": AIDemandAgent(cfg), "inventory": AIInventoryAgent(cfg), "waste": AIWasteAgent(cfg),
            "production": AIProductionAgent(cfg), "conflict_review": conflict_reviewer(cfg)}
