"""Outcome step: what 'actually happened' after the decision (MODELED).

The observed demand comes from the scenario file and is never shown to the agents before they
decide. The outcome depends on the FINAL action (approved, modified, rejected or abstained), so a
human override changes the result, and the prediction can be compared with the actual."""
from __future__ import annotations

from .models import Outcome

STOCKOUT_SCORE_PENALTY = 0.05      # NA-10


def serve(plan_kg: dict, usable: dict, covers: int, per_cover: dict, plate_rate: float) -> dict:
    lines, stockouts = {}, []
    for g, kg in plan_kg.items():
        available = kg + usable.get(g, 0.0)
        demand = covers * per_cover[g]
        consumed = min(available, demand)
        if demand > available + 1e-9:
            stockouts.append(g)
        lines[g] = {"produced_kg": round(kg, 1), "available_kg": round(available, 1), "demand_kg": round(demand, 1),
                    "consumed_kg": round(consumed, 1), "leftover_kg": round(available - consumed, 1)}
    over = sum(l["leftover_kg"] for l in lines.values())
    plate = covers * plate_rate
    return {"lines": lines, "stockouts": stockouts, "overproduction_kg": round(over, 1),
            "plate_waste_kg": round(plate, 1), "waste_kg": round(over + plate, 1),
            "production_kg": round(sum(plan_kg.values()), 1),
            "consumption_kg": round(sum(l["consumed_kg"] for l in lines.values()), 1)}


def production_outcome(rec, final_plan: dict | None, observed: dict, standing: dict, cost_per_kg: float,
                       guest_baseline: float, executed: bool) -> Outcome:
    covers = observed["actual_covers"]
    per_cover, plate = observed["actual_consumption_kg_per_cover"], observed["plate_waste_kg_per_cover"]
    usable = rec.details.get("usable_carry_over_kg", {})
    plan = final_plan if executed and final_plan else standing
    actual = serve(plan, usable, covers, per_cover, plate)
    baseline = serve(standing, usable, covers, per_cover, plate)          # what the standing plan would have done
    ai_plan = serve(rec.details["plan_kg"], usable, covers, per_cover, plate) if rec.details.get("plan_kg") else None
    score = round(guest_baseline - STOCKOUT_SCORE_PENALTY * len(actual["stockouts"]), 2)
    predicted = rec.details.get("expected_covers")
    ape = abs(predicted - covers) / covers if predicted else None
    saved = round(baseline["waste_kg"] - actual["waste_kg"], 1)
    actual.update({"actual_covers": covers, "predicted_covers": predicted,
                   "forecast_ape": round(ape, 4) if ape is not None else None,
                   "waste_per_cover": round(actual["waste_kg"] / covers, 4),
                   "guest_fb_score": score, "plan_used": "AI plan (final action)" if executed else "Kitchen standing plan",
                   "counterfactual_waste_kg": baseline["waste_kg"],
                   "ai_plan_waste_kg": ai_plan["waste_kg"] if ai_plan else None,
                   "ai_plan_stockouts": ai_plan["stockouts"] if ai_plan else None,
                   "operational_exception": observed.get("operational_exception", "None")})
    return Outcome(
        execution_status="EXECUTED" if executed else "NOT EXECUTED (standing plan used)",
        actual=actual, waste_impact_kg=-saved,
        guest_impact=(f"Stockout in {', '.join(actual['stockouts'])}; score {score:.2f}"
                      if actual["stockouts"] else f"No stockouts; score {score:.2f}"),
        financial_impact_usd=round(saved * cost_per_kg, 2),
        summary=(f"{covers} actual covers vs {predicted} predicted ({ape:.1%} error) · waste {actual['waste_kg']} kg "
                 f"vs {baseline['waste_kg']} kg on the standing plan" if ape is not None else ""))


def pending_outcome(execution_status: str, plan_used: str, plan_kg: dict) -> Outcome:
    """A real morning: nothing has happened yet. The kitchen records the result after service (close-out)."""
    return Outcome(execution_status=execution_status,
                   actual={"plan_used": plan_used, "plan_to_serve_kg": {g: round(kg, 1) for g, kg in plan_kg.items()}},
                   summary="PENDING: record actual covers and leftovers after service to score this decision.")


def simple_outcome(rec, executed: bool, cost_per_kg: float) -> Outcome:
    t = rec.decision_type
    if not executed:
        return Outcome("NOT EXECUTED", {}, None, "None", None, "No action taken.")
    if t == "inventory_transfer":
        kg = rec.details["kg"]
        return Outcome("EXECUTED", {"transferred_kg": kg}, -kg, "None", round(kg * cost_per_kg, 2),
                       f"{kg:.0f} kg moved before expiry (assumes the receiving outlet uses it).")
    if t == "flag_overproduction":
        return Outcome("EXECUTED", {"flag": "posted"}, None, "None", None, "Flag posted for the chef; no direct impact.")
    if t in ("purchasing_adjustment", "banquet_production_change"):
        return Outcome("EXECUTED", {}, None, "None", None,
                       "PENDING: impact is measured when the order is delivered / the event is served.")
    return Outcome("EXECUTED", {}, None, "None", None, "")
