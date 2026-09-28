"""Product core: turns a real hotel's profile, today's inputs and its own history into the engine's scenario,
runs the governed morning, scores the evening close-out, and computes autonomy from the hotel's own record.

Nothing here re-implements a decision rule. Agents, orchestration, governance, the readiness gate and the
outcome arithmetic all come from hotel_agentops_sim. This module only assembles inputs and records results.
"""
from __future__ import annotations

import copy
import datetime as dt
from statistics import mean

from control_room.sim import WebApproval
from hotel_agentops_sim.agentops import GATE_ORDER, MIN_SAMPLE, autonomy_level, day_metrics, drift, evaluate_gate
from hotel_agentops_sim.context import STALE_AFTER_HOURS
from hotel_agentops_sim.engine import run_service
from hotel_agentops_sim.learning import learning_cases
from hotel_agentops_sim.models import ToolCall
from hotel_agentops_sim.orchestrator import GROUP_LABEL
from hotel_agentops_sim.outcome import STOCKOUT_SCORE_PENALTY, serve
from hotel_agentops_sim.parameters import load_parameters, load_scenario, thresholds

PARAMS = load_parameters()
CASE = load_scenario()
GROUPS = list(GROUP_LABEL)                        # the four breakfast item groups the agents plan
SOURCES = PARAMS["required_context_sources"]["value"]
HISTORY_NEEDED = 4                                # comparable services the Demand and Waste agents use (NA-01, NA-05)
EVIDENCE_WINDOW_DAYS = 28                         # the hotel's own track record used by the readiness gate
MIN_CLOSEOUTS = 4                                 # closed-out services before forecast accuracy counts
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Starting menu: the items staff can search for when they record stock. Each hotel can edit its own list in Setup.
FOOD_ITEMS = {
    "pastry_bread": ["Pastry & bread", "Croissants", "Pain au chocolat", "Danish pastries", "Muffins", "Scones", "Bagels",
                     "Sourdough loaf", "Whole-grain rolls", "White sandwich bread", "Gluten-free bread", "Banana bread",
                     "Pancake batter", "Waffle batter"],
    "hot_line": ["Scrambled eggs", "Shell eggs (egg station)", "Bacon", "Pork sausages", "Chicken sausages",
                 "Vegetarian sausages", "Hash browns", "Roasted potatoes", "Baked beans", "Grilled tomatoes",
                 "Sautéed mushrooms", "Porridge / oatmeal", "Smoked tofu"],
    "fruit_yogurt": ["Greek yogurt", "Plain yogurt", "Flavoured yogurt", "Plant-based yogurt", "Fresh fruit salad",
                     "Sliced melon", "Pineapple", "Mixed berries", "Bananas", "Whole apples & oranges", "Granola",
                     "Bircher muesli", "Chia pudding", "Fresh orange juice"],
    "cold_cuts_cheese": ["Sliced ham", "Smoked turkey", "Salami", "Prosciutto", "Smoked salmon", "Cheddar",
                         "Swiss / Emmental", "Brie", "Fresh mozzarella", "Cream cheese", "Cottage cheese", "Hummus"],
}
OUTLETS = ["Lobby cafe (lunch)", "Staff canteen", "Room service", "Banquets & events", "Pool bar", "Food donation partner"]


def menu_items(profile: dict) -> dict:
    """The hotel's searchable item list per group (the starting menu until the hotel edits it)."""
    saved = profile.get("menu_items") or {}
    return {g: list(saved.get(g) or FOOD_ITEMS[g]) for g in GROUPS}


def item_groups(profile: dict) -> dict:
    """Item name → the group the agents plan it under."""
    return {item: g for g, items in menu_items(profile).items() for item in items}


def outlets(profile: dict) -> list:
    own = (profile.get("alternative_outlet") or "").strip()
    return ([own] if own else []) + [o for o in OUTLETS if o != own]


# ---------------------------------------------------------------------------
# Hotel profile
# ---------------------------------------------------------------------------
def default_profile(name: str = "") -> dict:
    """A starting profile. Values are the case study's modeled defaults until the hotel replaces them."""
    hd = CASE["hotel_data"]
    return {
        "hotel_name": name,
        "rooms": hd["pms_occupancy"]["rooms"],
        "service_name": "Breakfast",
        "consumption_kg_per_cover": dict(hd["pos_history"]["consumption_kg_per_cover"]),
        "standing_plan_kg": {g: CASE["kitchen_standing_plan_kg"][g] for g in GROUPS},
        "waste_cost_per_kg": PARAMS["waste_cost_per_kg"]["value"],
        "context_threshold": PARAMS["context_completeness_threshold"]["value"],
        "delegated_range": PARAMS["delegated_prep_range"]["value"],
        "alternative_outlet": hd["inventory"]["near_expiry"][0]["alternative_outlet"],
        "approver": "F&B Manager",
        "escalation_policy": {k: v for k, v in CASE["ground_truth_escalation_required"].items() if not k.startswith("_")},
        "baseline_history": [],
        "first_decision_number": 1,
        "defaults_from_case_study": True,
    }


def demo_profile() -> dict:
    """The case-study hotel, with its modeled history, for a clearly labeled demo workspace."""
    p = default_profile("Demo hotel (modeled case-study data)")
    hd = CASE["hotel_data"]
    rates, stock = hd["waste_history"]["leftover_rate_last_4_saturdays"], hd["waste_history"]["stockouts_last_4_saturdays"]
    anchor = dt.date(2026, 10, 3)                                 # a Saturday
    rows = []
    for i, h in enumerate(hd["pos_history"]["last_4_saturdays"]):  # index 0 = most recent (as in the engine)
        rows.append({"date": (anchor - dt.timedelta(days=7 * (i + 1))).isoformat(),
                     "occupied_rooms": h["occupied_rooms"], "covers": h["covers"],
                     "leftover_pct": {g: round(rates[g][i] * 100, 1) for g in GROUPS},
                     "stockout": {g: i < stock[g] for g in GROUPS}})
    for i, ape in enumerate(hd["pos_history"]["last_7_services_forecast_ape"]):
        rows.append({"date": (anchor - dt.timedelta(days=i + 1)).isoformat(), "forecast_error_pct": round(ape * 100, 1)})
    p["baseline_history"] = rows
    p["first_decision_number"] = CASE["first_decision_number"]
    p["demo_anchor_date"] = anchor.isoformat()
    return p


def demo_inputs(profile: dict) -> dict:
    """The case study's Saturday morning, as a manager would enter it."""
    hd = CASE["hotel_data"]
    inv = hd["inventory"]
    return {
        "service_date": profile.get("demo_anchor_date"),
        "occupied_rooms": hd["pms_occupancy"]["occupied_rooms"], "in_house_guests": hd["pms_occupancy"]["in_house_guests"],
        "pms_age_hours": hd["pms_occupancy"]["as_of_hours"],
        "breakfast_inclusive_rooms": hd["reservations"]["breakfast_inclusive_rooms"],
        "outside_breakfast_bookings": hd["reservations"]["outside_breakfast_bookings"],
        "reservations_age_hours": hd["reservations"]["as_of_hours"],
        "inventory_age_hours": inv["as_of_hours"],
        "carry_over_kg": dict(inv["carry_over_kg"]),
        "within_shelf_life": dict(hd["shelf_life"]["carry_over_within_shelf_life"]),
        "near_expiry": [dict(n) for n in inv["near_expiry"]],
        "open_orders": [dict(o) for o in inv["open_orders"]],
        "events": [dict(e) for e in hd["event_schedule"]["events"]],
        "events_confirmed": True, "events_age_hours": hd["event_schedule"]["as_of_hours"],
        "guest_fb_score": hd["guest_experience_signal"]["recent_guest_fb_score"],
        "open_fb_complaints": hd["guest_experience_signal"]["open_fb_complaints"],
        "guest_age_hours": hd["guest_experience_signal"]["as_of_hours"],
    }


def blank_inputs(service_date: str) -> dict:
    return {"service_date": service_date, "occupied_rooms": None, "in_house_guests": None, "pms_age_hours": 1,
            "breakfast_inclusive_rooms": None, "outside_breakfast_bookings": 0, "reservations_age_hours": 1,
            "inventory_age_hours": None, "carry_over_kg": {g: 0.0 for g in GROUPS},
            "within_shelf_life": {g: True for g in GROUPS}, "near_expiry": [], "open_orders": [],
            "events": [], "events_confirmed": False, "events_age_hours": 1,
            "guest_fb_score": None, "open_fb_complaints": 0, "guest_age_hours": 12}


def _whole(x):
    x = float(x)
    return int(x) if x.is_integer() else x


def weekday(date_str: str) -> str:
    return WEEKDAYS[dt.date.fromisoformat(date_str).weekday()]


# ---------------------------------------------------------------------------
# History: the hotel's baseline rows plus every closed-out service
# ---------------------------------------------------------------------------
def closed_rows(days: list[dict]) -> list[dict]:
    rows = []
    for d in days:
        c = d.get("closeout")
        if not c:
            continue
        rows.append({"date": d["service_date"], "occupied_rooms": d["inputs"].get("occupied_rooms"), "covers": c["actual_covers"],
                     "predicted_covers": c.get("predicted_covers"), "leftover_pct": c["leftover_pct"],
                     "stockout": c["stockout"], "consumption_kg_per_cover": c.get("consumption_kg_per_cover"),
                     "source": "close-out"})
    return rows


def history(profile: dict, days: list[dict]) -> list[dict]:
    rows = [dict(r, source="baseline") for r in profile.get("baseline_history", [])] + closed_rows(days)
    return sorted(rows, key=lambda r: r["date"], reverse=True)          # most recent first


def _ape(r):
    if r.get("forecast_error_pct") is not None:
        return r["forecast_error_pct"] / 100
    if r.get("predicted_covers") and r.get("covers"):
        return abs(r["predicted_covers"] - r["covers"]) / r["covers"]
    return None


def derived_history(profile: dict, days: list[dict], service_date: str) -> dict:
    """What the agents will see from history for this service date (only services before it)."""
    rows = [r for r in history(profile, days) if r["date"] < service_date]
    wd = weekday(service_date)
    comparable = [r for r in rows if weekday(r["date"]) == wd and r.get("covers") and r.get("occupied_rooms")][:HISTORY_NEEDED]
    waste_rows = [r for r in rows if weekday(r["date"]) == wd and r.get("leftover_pct")][:HISTORY_NEEDED]
    apes = [a for a in (_ape(r) for r in rows) if a is not None][:7]
    learned = [r["consumption_kg_per_cover"] for r in comparable if r.get("consumption_kg_per_cover")]
    per_cover = dict(profile["consumption_kg_per_cover"])
    per_cover_source = "hotel profile"
    if len(learned) >= HISTORY_NEEDED:
        per_cover = {g: round(mean(x[g] for x in learned), 4) for g in GROUPS}
        per_cover_source = f"learned from the last {len(learned)} {wd} close-outs"
    return {"weekday": wd, "comparable": comparable, "waste_rows": waste_rows, "apes": apes,
            "per_cover": per_cover, "per_cover_source": per_cover_source,
            "has_pos": len(comparable) >= HISTORY_NEEDED and len(apes) >= 1,
            "has_waste": len(waste_rows) >= HISTORY_NEEDED}


# ---------------------------------------------------------------------------
# Morning: inputs → scenario → governed run
# ---------------------------------------------------------------------------
def build_scenario(profile: dict, inputs: dict, days: list[dict], number_start: int, run_clock: str) -> tuple[dict, dict]:
    """Returns (scenario in the engine's format, a note of which sources were provided)."""
    date = inputs["service_date"]
    hx = derived_history(profile, days, date)
    hd, provided = {}, {}
    if inputs.get("occupied_rooms") is not None:
        hd["pms_occupancy"] = {"as_of_hours": inputs.get("pms_age_hours") or 0, "rooms": profile["rooms"],
                               "occupied_rooms": int(inputs["occupied_rooms"]),
                               "in_house_guests": inputs.get("in_house_guests")}
    if inputs.get("breakfast_inclusive_rooms") is not None:
        hd["reservations"] = {"as_of_hours": inputs.get("reservations_age_hours") or 0,
                              "breakfast_inclusive_rooms": int(inputs["breakfast_inclusive_rooms"]),
                              "outside_breakfast_bookings": int(inputs.get("outside_breakfast_bookings") or 0)}
        if (inputs.get("front_desk_notes") or "").strip():
            hd["reservations"]["front_desk_notes"] = inputs["front_desk_notes"].strip()[:2000]
    if hx["has_pos"]:
        hd["pos_history"] = {"as_of_hours": 0,
                             "last_4_saturdays": [{"occupied_rooms": int(r["occupied_rooms"]), "covers": int(r["covers"])}
                                                  for r in hx["comparable"]],
                             "last_7_services_forecast_ape": [round(a, 4) for a in hx["apes"]],
                             "consumption_kg_per_cover": hx["per_cover"]}
    if inputs.get("inventory_age_hours") is not None:
        outlet = profile.get("alternative_outlet") or "another outlet"
        hd["inventory"] = {"as_of_hours": inputs["inventory_age_hours"],
                           "carry_over_kg": {g: float(inputs["carry_over_kg"].get(g) or 0.0) for g in GROUPS},
                           "near_expiry": [{"item": n["item"], "group": n["group"], "kg": float(n["kg"]),
                                            "expires_in_days": int(n.get("expires_in_days") or 1),
                                            "alternative_outlet": n.get("alternative_outlet") or outlet}
                                           for n in inputs.get("near_expiry", []) if n.get("item") and n.get("kg")],
                           "open_orders": [{"order_id": o.get("order_id") or f"PO-{i + 1}", "item": o.get("item") or GROUP_LABEL[o["group"]],
                                            "group": o["group"], "kg": _whole(o["kg"]), "delivery": o.get("delivery", ""),
                                            "supplier": o.get("supplier", "")}
                                           for i, o in enumerate(inputs.get("open_orders", [])) if o.get("group") and o.get("kg")]}
        if (inputs.get("kitchen_notes") or "").strip():
            hd["inventory"]["kitchen_notes"] = inputs["kitchen_notes"].strip()[:2000]
        hd["shelf_life"] = {"as_of_hours": inputs["inventory_age_hours"],
                            "carry_over_within_shelf_life": {g: bool(inputs["within_shelf_life"].get(g, True)) for g in GROUPS}}
    if hx["has_waste"]:
        hd["waste_history"] = {"as_of_hours": 0,
                               "leftover_rate_last_4_saturdays": {g: [round(r["leftover_pct"][g] / 100, 4) for r in hx["waste_rows"]]
                                                                  for g in GROUPS},
                               "stockouts_last_4_saturdays": {g: sum(bool(r["stockout"].get(g)) for r in hx["waste_rows"])
                                                              for g in GROUPS}}
    if inputs.get("events_confirmed"):
        hd["event_schedule"] = {"as_of_hours": inputs.get("events_age_hours") or 0,
                                "events": [{"event_id": e.get("event_id") or f"EV-{i + 1}", "name": e["name"], "date": e.get("date", ""),
                                            "guaranteed_covers": int(e["guaranteed_covers"]), "revised_covers": int(e["revised_covers"]),
                                            "planned_production_kg": float(e["planned_production_kg"])}
                                           for i, e in enumerate(inputs.get("events", []))
                                           if e.get("name") and e.get("guaranteed_covers") and e.get("revised_covers") is not None
                                           and e.get("planned_production_kg")]}
    if inputs.get("guest_fb_score") is not None:
        hd["guest_experience_signal"] = {"as_of_hours": inputs.get("guest_age_hours") or 0,
                                         "recent_guest_fb_score": float(inputs["guest_fb_score"]),
                                         "open_fb_complaints": int(inputs.get("open_fb_complaints") or 0)}
    for s in SOURCES:
        provided[s] = s in hd
    scenario = {
        "scenario_id": f"{date}", "service": f"{hx['weekday']} {profile.get('service_name') or 'Breakfast'}".strip(),
        "service_date": date, "run_clock": run_clock, "first_decision_number": number_start,
        "hotel_data": hd, "kitchen_standing_plan_kg": {g: float(profile["standing_plan_kg"][g]) for g in GROUPS},
        "ground_truth_escalation_required": dict(profile.get("escalation_policy") or {}),
    }
    return scenario, {"provided": provided, "history": hx}


def params_for(profile: dict) -> dict:
    p = copy.deepcopy(PARAMS)
    p["context_completeness_threshold"]["value"] = float(profile["context_threshold"])
    p["delegated_prep_range"]["value"] = float(profile["delegated_range"])
    p["waste_cost_per_kg"]["value"] = float(profile["waste_cost_per_kg"])
    return p


def next_decision_number(profile: dict, days: list[dict]) -> int:
    used = [int(r["Decision ID"].split("-")[1]) for d in days if d.get("run") for r in d["run"]["records"]]
    return max(used) + 1 if used else int(profile.get("first_decision_number") or 1)


def run_morning(profile: dict, inputs: dict, days: list[dict], choices: dict | None, approver: str, gate_result: tuple,
                run_clock: str | None = None, ai=None):
    """Run the governed morning. With choices=None, returns what would be routed to a human (nothing is saved).
    ai: an ai_agents.AIConfig to run the specialists as AI agents (with verification and rule-based fallback)."""
    prior = [d for d in days if d["service_date"] != inputs["service_date"]]
    scenario, meta = build_scenario(profile, inputs, prior, next_decision_number(profile, prior),
                                    run_clock or dt.datetime.now().strftime("%H:%M"))
    agents = None
    if ai is not None:
        from product.ai_agents import build_agents
        ai.reports = []
        agents = build_agents(ai)
    approval = WebApproval(choices or {}, approver=approver)
    res = run_service(scenario, params_for(profile), mode="scripted", approval=approval,
                      say=lambda *a, **k: None, gate_result=gate_result, agents=agents)
    meta["agent_mode"] = "AI agents (Gemini) with output verification" if ai is not None else "Rule-based agents"
    meta["ai_agents"] = sorted(list(ai.reports), key=lambda r: ["Demand Agent", "Inventory Agent", "Waste Agent",
                                                               "Production Agent", "Orchestrator"].index(r["agent"])
                               if r["agent"] in ("Demand Agent", "Inventory Agent", "Waste Agent", "Production Agent",
                                                 "Orchestrator") else 9) if ai is not None else []
    return res, approval.seen, scenario, meta


def serialize_run(res, scenario: dict, meta: dict) -> dict:
    """Everything needed to audit and close out the day, as plain JSON."""
    return {
        "records": res.records, "traces": res.traces,
        "tool_calls": [{"name": c.name, "ok": c.ok, "note": c.note} for c in res.tool_calls],
        "executions": [{"name": c.name, "ok": c.ok, "note": c.note} for c in res.executions],
        "gate": res.gate, "autonomy": res.autonomy, "autonomy_why": res.autonomy_why,
        "context": {"completeness": res.context.completeness, "status": res.context.status,
                    "missing": res.context.missing, "stale": res.context.stale, "fallback": res.context.fallback},
        "learning": res.learning, "scenario": scenario, "sources_provided": meta["provided"],
        "per_cover_source": meta["history"]["per_cover_source"],
        "agent_mode": meta.get("agent_mode", "Rule-based agents"), "ai_agents": meta.get("ai_agents", []),
    }


# ---------------------------------------------------------------------------
# Evening: close-out with what actually happened
# ---------------------------------------------------------------------------
def production_record(run: dict) -> dict | None:
    return next((r for r in run["records"] if r["Decision Type"] in ("production_adjustment", "abstain_missing_context")), None)


def plan_served(run: dict) -> tuple[dict, dict]:
    """(plan the kitchen actually served, usable carry-over) for this day."""
    rec = production_record(run)
    scen = run["scenario"]
    standing = scen["kitchen_standing_plan_kg"]
    if rec is None:
        return dict(standing), {}
    tr = run["traces"][rec["Decision ID"]]
    plan = tr["action"].get("final_plan_kg") or (rec.get("_outcome_actual") or {}).get("plan_to_serve_kg") or standing
    usable = (tr.get("details") or {}).get("usable_carry_over_kg") or {}
    shelf = (scen["hotel_data"].get("shelf_life") or {}).get("carry_over_within_shelf_life", {})
    if rec["Decision Type"] == "abstain_missing_context":
        usable = {g: kg for g, kg in usable.items() if shelf.get(g, True)}
    return {g: float(plan[g]) for g in GROUPS}, {g: float(usable.get(g, 0.0)) for g in GROUPS}


def close_out(run: dict, profile: dict, actual_covers: int, leftover_kg: dict, stockout: dict,
              plate_waste_kg: float = 0.0, guest_fb_score: float | None = None, recorded_by: str = "",
              notes: str = "") -> tuple[dict, dict]:
    """Scores the day from what the kitchen recorded. Returns (updated run, close-out summary)."""
    run = copy.deepcopy(run)
    plan, usable = plan_served(run)
    rec = production_record(run)
    covers = max(int(actual_covers), 1)
    lines, consumed_pc, left_pct = {}, {}, {}
    for g in GROUPS:
        available = plan[g] + usable.get(g, 0.0)
        left = min(max(float(leftover_kg.get(g) or 0.0), 0.0), available)
        consumed = available - left
        consumed_pc[g] = round(consumed / covers, 4)
        left_pct[g] = round(left / available * 100, 1) if available else 0.0
        lines[g] = {"produced_kg": round(plan[g], 1), "available_kg": round(available, 1), "consumed_kg": round(consumed, 1),
                    "leftover_kg": round(left, 1), "stockout": bool(stockout.get(g))}
    stockouts = [g for g in GROUPS if stockout.get(g)]
    waste = round(sum(l["leftover_kg"] for l in lines.values()) + float(plate_waste_kg or 0.0), 1)
    predicted = None
    if rec is not None:
        predicted = (run["traces"][rec["Decision ID"]].get("details") or {}).get("expected_covers")
    ape = round(abs(predicted - covers) / covers, 4) if predicted else None
    # Estimate only: the standing plan served against today's observed consumption. Where a group stocked out,
    # true demand is unknown, so the estimate is marked as a lower bound.
    standing = run["scenario"]["kitchen_standing_plan_kg"]
    est = serve(standing, usable, covers, consumed_pc, (float(plate_waste_kg or 0.0) / covers))
    cost = float(profile["waste_cost_per_kg"])
    summary = {
        "actual_covers": covers, "predicted_covers": predicted, "forecast_ape": ape,
        "lines": lines, "leftover_pct": left_pct, "stockout": {g: bool(stockout.get(g)) for g in GROUPS},
        "stockouts": stockouts, "plate_waste_kg": round(float(plate_waste_kg or 0.0), 1), "waste_kg": waste,
        "standing_plan_waste_estimate_kg": est["waste_kg"], "estimate_is_lower_bound": bool(stockouts),
        "waste_avoided_estimate_kg": round(est["waste_kg"] - waste, 1),
        "waste_cost_avoided_estimate": round((est["waste_kg"] - waste) * cost, 2),
        "consumption_kg_per_cover": None if stockouts else consumed_pc,
        "guest_fb_score": guest_fb_score, "recorded_by": recorded_by, "notes": notes,
        "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    if rec is not None:
        act = dict(rec.get("_outcome_actual") or {})
        act.update({"actual_covers": covers, "predicted_covers": predicted, "forecast_ape": ape, "waste_kg": waste,
                    "stockouts": stockouts, "counterfactual_waste_kg": est["waste_kg"], "lines": lines,
                    "guest_fb_score": guest_fb_score if guest_fb_score is not None else
                    round(float((run["scenario"]["hotel_data"].get("guest_experience_signal") or {}).get(
                        "recent_guest_fb_score", 4.6)) - STOCKOUT_SCORE_PENALTY * len(stockouts), 2)})
        rec["_outcome_actual"] = act
        rec["_forecast_ape"] = ape if rec["Decision Type"] == "production_adjustment" else None
        rec["Actual Outcome"] = (f"{covers} actual covers" + (f" vs {predicted} predicted ({ape:.1%} error)" if ape is not None else "")
                                 + f" · waste {waste} kg recorded · standing plan estimate {est['waste_kg']} kg"
                                 + (" (lower bound: stockout)" if stockouts else ""))
        rec["Waste Impact"] = f"{waste - est['waste_kg']:+.1f} kg (estimate)"
        rec["Guest Impact"] = f"Stockout in {', '.join(GROUP_LABEL[g] for g in stockouts)}" if stockouts else "No stockouts"
        rec["Financial Impact"] = f"${(est['waste_kg'] - waste) * cost:,.2f} (estimate)"
        run["traces"][rec["Decision ID"]]["outcome"] = {"summary": rec["Actual Outcome"], "actual": act}
        run["traces"][rec["Decision ID"]]["kpi_contribution"]["forecast_ape"] = rec["_forecast_ape"]
    run["learning"] = learning_cases(run["records"], PARAMS["override_categories"])
    return run, summary


# ---------------------------------------------------------------------------
# Earned autonomy: AgentOps and the readiness gate from the hotel's own record
# ---------------------------------------------------------------------------
CAP_LINES = ("Gate on HOLD → autonomy SUPERVISED → low-risk action needs manager approval",
             "Autonomy REDUCED to BOUNDED → recommend only")


def scoring_records(window: list[dict]) -> list[dict]:
    """Records as the gate scores them. An escalation caused only by the current autonomy level (a low-risk action held
    for approval because the gate is on HOLD) reflects the gate's caution, not the agents' judgment, so it does not
    count against escalation precision. Otherwise a supervised hotel could never demonstrate precision."""
    out = []
    for d in window:
        for r in d["run"]["records"]:
            trace = d["run"]["traces"][r["Decision ID"]]["governance"]["rule_trace"]
            forced = any(line in CAP_LINES for line in trace) and not any("ESCALATE" in line for line in trace)
            out.append(dict(r, Escalation="NO") if forced and r["Escalation"] == "YES" else r)
    return out


def _tools(items):
    return [ToolCall(i["name"], i["ok"], i.get("note", "")) for i in items]


def performance(profile: dict, days: list[dict], as_of: str | None = None) -> dict:
    as_of = as_of or dt.date.today().isoformat()
    start = (dt.date.fromisoformat(as_of) - dt.timedelta(days=EVIDENCE_WINDOW_DAYS)).isoformat()
    window = [d for d in days if d.get("run") and start <= d["service_date"] < as_of or
              (d.get("run") and d["service_date"] == as_of and d.get("closeout"))]
    records = scoring_records(window)
    calls = _tools([c for d in window for c in d["run"]["tool_calls"]])
    execs = _tools([c for d in window for c in d["run"]["executions"]])
    m = day_metrics(records, calls, execs)
    closed = [d for d in window if d.get("closeout")]
    apes = [d["closeout"]["forecast_ape"] for d in closed if d["closeout"].get("forecast_ape") is not None]
    scores = [d["closeout"]["guest_fb_score"] if d["closeout"].get("guest_fb_score") is not None
              else (d.get("inputs") or {}).get("guest_fb_score") for d in closed]
    scores = [x for x in scores if x is not None]
    th = thresholds(PARAMS)
    evidence = {
        "recommendation_acceptance": m["recommendation_acceptance"]["value"],
        "escalation_recall": m["escalation_recall"]["value"],
        "escalation_precision": m["escalation_precision"]["value"],
        "tool_reliability": m["tool_reliability"]["value"],
        "human_override_rate": m["human_override_rate"]["value"],
        "forecast_mape": mean(apes) if len(apes) >= MIN_CLOSEOUTS else None,
        "guest_fb_score": round(mean(scores), 2) if scores else None,
        "policy_violations": m["policy_violations"]["value"],
    }
    decided = m["recommendation_acceptance"]["den"]
    gaps = []
    if decided < MIN_SAMPLE:
        gaps.append(f"{decided}/{MIN_SAMPLE} manager decisions")
    if len(apes) < MIN_CLOSEOUTS:
        gaps.append(f"{len(apes)}/{MIN_CLOSEOUTS} closed-out services with a forecast")
    missing = [lbl for k, lbl in GATE_ORDER if evidence[k] is None]
    if missing and not gaps:
        gaps.append("no data yet for " + ", ".join(missing))

    weekly = {}
    this_week = dt.date.fromisoformat(as_of).isocalendar()[:2]
    first_week = dt.date.fromisoformat(start).isocalendar()[:2]
    for d in window:
        wk = dt.date.fromisoformat(d["service_date"]).isocalendar()[:2]
        if wk in (this_week, first_week):              # the drift rule compares completed weeks only
            continue
        dec = [r for r in d["run"]["records"] if r["_decided"]]
        weekly.setdefault(wk, [0, 0])
        weekly[wk][0] += sum(r["Override"] == "YES" for r in dec)
        weekly[wk][1] += len(dec)
    rates = [o / n for o, n in (weekly[k] for k in sorted(weekly)) if n]
    rule = PARAMS["drift_rule"]
    drift_state = drift(rates, rule["multiplier"], rule["trailing_weeks"]) if len(rates) > rule["trailing_weeks"] else \
        {"current": rates[-1] if rates else None, "trailing_avg": None, "limit": None, "drift": False}

    if gaps:
        checks = [{"metric": lbl, "key": k, "value": evidence[k], "test": th[k][1], "threshold": th[k][0], "pass": None}
                  for k, lbl in GATE_ORDER]
        gate = {"result": "HOLD", "first_blocker": "Not enough evidence yet", "checks": checks, "failed": None,
                "insufficient": gaps}
        why = []
        if evidence["guest_fb_score"] is not None and evidence["guest_fb_score"] < th["guest_fb_score"][0]:
            why.append(f"Guest F&B {evidence['guest_fb_score']:.2f} < {th['guest_fb_score'][0]:.2f} → REDUCE AUTONOMY")
        if evidence["policy_violations"]:
            why.append("Policy violations > 0 → REDUCE AUTONOMY")
        if drift_state["drift"]:
            why.append(f"Override rate {drift_state['current']:.0%} > 1.5 × trailing {drift_state['trailing_avg']:.0%}"
                       " → REDUCE AUTONOMY + INVESTIGATE")
        level = "BOUNDED" if why else "SUPERVISED"
        why = why or [f"Not enough of this hotel's own evidence yet ({'; '.join(gaps)}) → HOLD AUTONOMY: "
                      "no delegated execution"]
    else:
        gate = evaluate_gate(evidence, th)
        level, why = autonomy_level(gate, evidence, th, drift_state)
    return {"as_of": as_of, "window_start": start, "evidence": evidence, "metrics": m, "gate": gate, "autonomy": level,
            "autonomy_why": why, "gaps": gaps, "drift": drift_state, "weekly_override_rates": rates,
            "days_in_window": len(window), "closed_in_window": len(closed), "decided": decided}


def gate_tuple(perf: dict) -> tuple:
    return perf["gate"], perf["autonomy"], perf["autonomy_why"]
