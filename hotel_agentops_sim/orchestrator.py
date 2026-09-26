"""Orchestrator (case study layer 4): combines the specialist agents' signals into structured
recommendations. It coordinates; it has no unrestricted purchasing authority and executes nothing."""
from __future__ import annotations

from .models import AgentOutput, Recommendation

CONFLICT_DELTA = 0.05          # NA-09

GROUP_LABEL = {"pastry_bread": "Pastry & bread", "hot_line": "Hot line", "fruit_yogurt": "Fruit & yogurt",
               "cold_cuts_cheese": "Cold cuts & cheese"}


def production_risk(change: float, delegated_range: float) -> str:
    """NA-06: tiers by size of the total production change."""
    size = abs(change)
    if size <= delegated_range:
        return "LOW"
    return "MEDIUM" if size <= 0.25 else "HIGH"


class Orchestrator:
    name = "Orchestrator"

    def __init__(self, delegated_range: float):
        self.delegated_range = delegated_range

    @staticmethod
    def detect_conflict(demand: AgentOutput, production: AgentOutput, waste: AgentOutput) -> dict:
        d, p = demand.outputs["demand_change"], production.outputs["change"]
        opposite = (d > CONFLICT_DELTA and p < -CONFLICT_DELTA) or (d < -CONFLICT_DELTA and p > CONFLICT_DELTA)
        if not opposite:
            return {"conflict": False, "resolved": True, "note": "Demand and production point the same way."}
        explained = bool(waste.outputs["chronic_overproduction"]) if p < d else bool(waste.outputs["stockout_prone"])
        note = (f"Demand {d:+.0%} but production draft {p:+.0%}. "
                + ("Resolved: Waste Agent shows chronic overproduction in "
                   + ", ".join(GROUP_LABEL[g] for g in waste.outputs["chronic_overproduction"])
                   + ", so the plan raises what guests eat and cuts what they leave."
                   if explained else "Unresolved: no waste evidence explains the gap."))
        return {"conflict": True, "resolved": explained, "note": note}

    def coordinate(self, *, number: int, clock, service: str, completeness: float,
                   demand: AgentOutput, inventory: AgentOutput, waste: AgentOutput,
                   production: AgentOutput, standing_plan: dict) -> tuple[list[Recommendation], dict]:
        recs: list[Recommendation] = []
        conflict = self.detect_conflict(demand, production, waste)
        dout, pout, wout = demand.outputs, production.outputs, waste.outputs

        def rid():
            return f"D-{number + len(recs):04d}"

        # 1 · Breakfast production plan (the decision followed end to end)
        change = pout["change"]
        ups = [l for l in pout["lines"] if l["change"] > 0.005]
        downs = [l for l in pout["lines"] if l["change"] < -0.005]
        chronic = wout["chronic_overproduction"]
        chronic_names = ", ".join(GROUP_LABEL[g] for g in chronic)
        chronic_rates = ", ".join(format(wout["avg_leftover_rate"][g], ".0%") for g in chronic)
        stockout_names = ", ".join(GROUP_LABEL[g] for g in wout["stockout_prone"])
        why = dout["demand_signal"] + ". "
        if chronic:
            why += f"Historical waste shows chronic overproduction in {chronic_names} (avg leftover {chronic_rates}). "
        if stockout_names:
            why += f"{stockout_names} stocked out recently, so it is raised. "
        recs.append(Recommendation(
            decision_id=rid(), timestamp=clock(), decision_type="production_adjustment", service=service,
            agents=["Demand Agent", "Inventory Agent", "Waste Agent", "Production Agent", "Orchestrator"],
            recommendation=f"{'Reduce' if change < 0 else 'Increase'} breakfast production by {abs(change):.1%} "
                           f"({pout['standing_total_kg']:.0f} → {pout['planned_total_kg']:.0f} kg): "
                           + "; ".join(f"{GROUP_LABEL[l['group']]} {l['change']:+.0%}" for l in ups + downs),
            reason=why.strip(), confidence=demand.confidence,
            risk_level=production_risk(change, self.delegated_range), reversibility="HIGH",
            context_completeness=completeness,
            details={"plan_kg": pout["plan_kg"], "lines": pout["lines"], "change": change,
                     "standing_plan_kg": standing_plan, "expected_covers": dout["expected_covers"],
                     "expected_consumption_kg": dout["expected_consumption_kg"],
                     "usable_carry_over_kg": inventory.outputs["usable_carry_over_kg"], "conflict": conflict,
                     "executor": "Production Agent", "write_scope": "production_plan", "depends_on_inventory": True},
            expected_impact=f"About {pout['standing_total_kg'] - pout['planned_total_kg']:.0f} kg less food prepared, "
                            f"with every item group still covered above expected consumption."))

        # 2 · Flag chronic overproduction (low risk, highly reversible)
        for g in wout["chronic_overproduction"]:
            recs.append(Recommendation(
                decision_id=rid(), timestamp=clock(), decision_type="flag_overproduction", service=service,
                agents=["Waste Agent"], recommendation=f"Flag chronic overproduction: {GROUP_LABEL[g]}",
                reason=wout["historical_pattern"], confidence=waste.confidence, risk_level="LOW",
                reversibility="HIGH", context_completeness=completeness,
                details={"group": g, "executor": "Waste Agent", "write_scope": "waste_insight", "depends_on_inventory": False},
                expected_impact="Chef sees the pattern on the daily board; no production change by itself."))

        # 3 · Inventory transfer of near-expiry surplus (low risk, moderately reversible)
        for a in inventory.outputs["recommended_inventory_actions"]:
            recs.append(Recommendation(
                decision_id=rid(), timestamp=clock(), decision_type="inventory_transfer", service=service,
                agents=["Inventory Agent"],
                recommendation=f"Transfer {a['kg']:.0f} kg {a['item']} to {a['to']}",
                reason=f"{a['kg']:.0f} kg expires in {a['expires_in_days']} day and is surplus to today's breakfast need.",
                confidence=inventory.confidence, risk_level="LOW", reversibility="MODERATE",
                context_completeness=completeness,
                details={**a, "executor": "Inventory Agent", "write_scope": "inventory_recommendation",
                         "depends_on_inventory": True},
                expected_impact=f"Avoids up to {a['kg']:.0f} kg of expiry waste."))

        # 4 · Purchasing adjustment for chronic groups with an open order (medium risk, low reversibility)
        for po in inventory.outputs["open_orders"]:
            g = po["group"]
            if g in wout["chronic_overproduction"]:
                cut = round(wout["avg_leftover_rate"][g], 2)
                recs.append(Recommendation(
                    decision_id=rid(), timestamp=clock(), decision_type="purchasing_adjustment", service=service,
                    agents=["Inventory Agent", "Waste Agent", "Orchestrator"],
                    recommendation=f"Reduce {po['order_id']} ({po['item']}) by {cut:.0%}: {po['kg']} → {po['kg'] * (1 - cut):.0f} kg",
                    reason=f"Average leftover for {GROUP_LABEL[g]} is {cut:.0%} across the last 4 Saturdays.",
                    confidence=min(inventory.confidence, waste.confidence), risk_level="MEDIUM", reversibility="LOW",
                    context_completeness=completeness,
                    details={"order": po, "change": -cut, "executor": None, "write_scope": "purchasing",
                             "depends_on_inventory": True},
                    expected_impact=f"About {po['kg'] * cut:.0f} kg less {po['item'].lower()} bought per order."))

        # 5 · Banquet production change (always HIGH risk: case study p.7)
        for ev in dout["events"]:
            if ev["abnormal"]:
                new_kg = round(ev["planned_production_kg"] * ev["revised_covers"] / ev["guaranteed_covers"], 1)
                recs.append(Recommendation(
                    decision_id=rid(), timestamp=clock(), decision_type="banquet_production_change", service=service,
                    agents=["Demand Agent", "Production Agent", "Orchestrator"],
                    recommendation=f"Resize {ev['name']} production {ev['planned_production_kg']} → {new_kg} kg "
                                   f"({ev['guaranteed_covers']} → {ev['revised_covers']} covers)",
                    reason=f"Guarantee changed {ev['change']:+.0%}; abnormal event demand.",
                    confidence=demand.confidence, risk_level="HIGH", reversibility="LOW",
                    context_completeness=completeness,
                    details={"event": ev, "new_kg": new_kg, "abnormal_event": True, "executor": "Production Agent",
                             "write_scope": "production_plan", "depends_on_inventory": False},
                    expected_impact=f"About {ev['planned_production_kg'] - new_kg:.0f} kg less banquet food prepared."))
        return recs, conflict
