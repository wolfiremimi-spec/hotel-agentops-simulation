"""Production Agent: 'What should we prepare?'   READ approved plan only · WRITE production system, within threshold.

Two phases, preserving the case study's permissions:
  draft()   - sizes the plan from the other agents' signals (it reads no raw hotel data).
  execute() - writes a plan to the production system ONLY with a governance authorization.
"""
from __future__ import annotations

from ..models import AgentOutput, ToolCall

BUFFER_STANDARD, BUFFER_CHRONIC, BUFFER_STOCKOUT = 0.08, 0.03, 0.12     # NA-04


class NotAuthorized(PermissionError):
    pass


class ProductionAgent:
    name = "Production Agent"
    question = "What should we prepare?"
    READS: list[str] = []                     # signals only, no raw sources
    WRITES = ["production_plan"]

    def draft(self, demand: AgentOutput, inventory: AgentOutput, waste: AgentOutput, standing_plan: dict) -> AgentOutput:
        exp = demand.outputs["expected_consumption_kg"]
        usable = inventory.outputs["usable_carry_over_kg"]
        chronic, stockout = waste.outputs["chronic_overproduction"], waste.outputs["stockout_prone"]
        plan, lines = {}, []
        for group, need in exp.items():
            buffer = BUFFER_CHRONIC if group in chronic else BUFFER_STOCKOUT if group in stockout else BUFFER_STANDARD
            kg = round(max(need * (1 + buffer) - usable.get(group, 0.0), 0.0), 1)
            plan[group] = kg
            lines.append({"group": group, "expected_consumption_kg": need, "buffer": buffer,
                          "usable_carry_over_kg": usable.get(group, 0.0), "planned_kg": kg,
                          "standing_plan_kg": standing_plan[group],
                          "change": round(kg / standing_plan[group] - 1, 3)})
        total, standing = round(sum(plan.values()), 1), round(sum(standing_plan[g] for g in plan), 1)
        return AgentOutput(
            agent=self.name, question=self.question, reads=["(signals from Demand, Inventory, Waste agents)"],
            confidence=demand.confidence,
            outputs={"plan_kg": plan, "lines": lines, "planned_total_kg": total, "standing_total_kg": standing,
                     "change": round(total / standing - 1, 4)},
        )

    def execute(self, plan: dict, authorization: str | None) -> ToolCall:
        if not authorization:
            raise NotAuthorized("Production Agent may only write an approved or delegated plan.")
        return ToolCall("write:production_plan", ok=True, note=f"authorized by {authorization}")
