"""Inventory Agent: 'What do we already have?'   READ inventory, procurement, shelf life · WRITE inventory recommendation."""
from __future__ import annotations

from ..models import AgentOutput


class InventoryAgent:
    name = "Inventory Agent"
    question = "What do we already have?"
    READS = ["inventory", "shelf_life"]           # procurement (open orders) arrives inside the inventory feed
    WRITES = ["inventory_recommendation"]

    def run(self, view) -> AgentOutput:
        inv, shelf = view.get("inventory"), view.get("shelf_life")
        within = (shelf or {}).get("carry_over_within_shelf_life", {})
        usable, excluded = {}, []
        for group, kg in inv["carry_over_kg"].items():
            if within.get(group, False):          # NA-12: only stock inside its shelf life is usable
                usable[group] = kg
            else:
                usable[group] = 0.0
                if kg:
                    excluded.append(f"{group}: {kg} kg past shelf life, not usable")
        near = inv.get("near_expiry", [])
        actions = [{"type": "inventory_transfer", "item": n["item"], "group": n["group"], "kg": n["kg"],
                    "to": n["alternative_outlet"], "expires_in_days": n["expires_in_days"]} for n in near]
        risk = "Near-expiry surplus: " + ", ".join(f"{n['kg']} kg {n['item']}" for n in near) if near else "No expiry risk"
        return AgentOutput(
            agent=self.name, question=self.question, reads=self.READS,
            confidence=1.0,           # measured stock, not a forecast (feed freshness is checked by governance)
            outputs={"usable_carry_over_kg": usable, "excluded": excluded, "near_expiry": near,
                     "open_orders": inv.get("open_orders", []), "inventory_risk": risk,
                     "recommended_inventory_actions": actions},
        )
