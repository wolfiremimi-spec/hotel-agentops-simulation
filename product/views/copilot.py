import copy
import json

import streamlit as st

from control_room import sim, ui
from product import agent, core
from product import app_state as S
from product import site

MAX_QUESTIONS = 25
DROPPABLE = {"pms_occupancy": ("occupied_rooms", None), "reservations": ("breakfast_inclusive_rooms", None),
             "inventory": ("inventory_age_hours", None), "event_schedule": ("events_confirmed", False),
             "guest_experience_signal": ("guest_fb_score", None)}


def _day(date):
    return next((d for d in S.days() if d["service_date"] == date), None)


def _latest_date():
    ds = [d["service_date"] for d in S.days() if d.get("inputs")]
    return ds[-1] if ds else S.today()


def _decisions(records):
    return [{"id": r["Decision ID"], "decision": sim.TYPE_LABEL.get(r["Decision Type"], r["Decision Type"]),
             "recommendation": r["Recommendation"], "confidence": r["Confidence"], "risk": r["Risk"],
             "authority": r["Required Authority"], "human_decision": r["Human Decision"], "status": r["Execution Status"],
             "outcome": r["Actual Outcome"]} for r in records]


def t_list_services(args):
    return {"services": [{"date": d["service_date"], "status": d["status"],
                          "autonomy": (d.get("run") or {}).get("autonomy"),
                          "covers": (d.get("closeout") or {}).get("actual_covers"),
                          "waste_kg": (d.get("closeout") or {}).get("waste_kg"),
                          "stockouts": (d.get("closeout") or {}).get("stockouts")} for d in S.days()]}


def t_get_service(args):
    date = args.get("date") or _latest_date()
    d = _day(date)
    if not d or not d.get("run"):
        return {"date": date, "note": "No approved plan saved for this date."}
    run = d["run"]
    plan, usable = core.plan_served(run)
    return {"date": date, "status": d["status"], "autonomy": run["autonomy"], "autonomy_reasons": run["autonomy_why"],
            "context_completeness": f"{run['context']['completeness']:.0%}", "kitchen_plan_kg": plan,
            "usable_carry_over_kg": usable, "decisions": _decisions(run["records"]), "closeout": d.get("closeout")}


def t_get_decision(args):
    did = args.get("decision_id", "")
    for d in S.days():
        for r in (d.get("run") or {}).get("records", []):
            if r["Decision ID"] == did:
                t = d["run"]["traces"][did]
                return {"date": d["service_date"], **_decisions([r])[0], "reason": t["recommendation"]["reason"],
                        "rule_trace": t["governance"]["rule_trace"], "human": t.get("human"), "action": t["action"]}
    return {"error": f"No decision {did} in this workspace."}


def t_get_performance(args):
    perf = S.performance_for(S.today())
    return {"autonomy": perf["autonomy"], "autonomy_reasons": perf["autonomy_why"], "gate_result": perf["gate"]["result"],
            "first_blocker": perf["gate"]["first_blocker"], "evidence_gaps": perf["gaps"],
            "checks": [{"metric": c["metric"], "value": c["value"], "required": f"{c['test']} {c['threshold']}", "pass": c["pass"]}
                       for c in perf["gate"]["checks"]], "decisions_in_window": perf["decided"],
            "closed_services_in_window": perf["closed_in_window"], "window_days": core.EVIDENCE_WINDOW_DAYS}


def t_what_if(args):
    date = args.get("date") or _latest_date()
    d = _day(date)
    base = (d or {}).get("inputs") or st.session_state.get(f"td_inputs_{date}")
    if base is None and S.is_demo() and date == S.profile().get("demo_anchor_date"):
        base = core.demo_inputs(S.profile())
    if base is None:
        return {"error": f"No morning data entered for {date}. Enter it on Today's plan first."}
    inputs, prof, notes = copy.deepcopy(base), copy.deepcopy(S.profile()), []
    for k in ("occupied_rooms", "breakfast_inclusive_rooms", "inventory_age_hours", "guest_fb_score"):
        if args.get(k) is not None:
            inputs[k] = args[k]
    for g, kg in (args.get("carry_over_kg") or {}).items():
        if g in core.GROUPS:
            inputs["carry_over_kg"][g] = float(kg)
    revised = args.get("event_revised_covers") or []
    if isinstance(revised, dict):                                # older shape: {"name": covers}
        revised = [{"name": n, "revised_covers": c} for n, c in revised.items()]
    for name, cov in ((r.get("name") or "", r.get("revised_covers")) for r in revised if isinstance(r, dict)):
        hit = [e for e in inputs.get("events", []) if (e.get("name") or "").lower() == name.lower()]
        if hit:
            hit[0]["revised_covers"] = int(cov)
        else:
            notes.append(f"No event named {name!r} that morning")
    for src in args.get("remove_sources") or []:
        if src in DROPPABLE:
            key, val = DROPPABLE[src]
            inputs[key] = val
        else:
            notes.append(f"{src} is derived from history and can't be removed here")
    if args.get("context_threshold_pct") is not None:
        prof["context_threshold"] = min(max(float(args["context_threshold_pct"]), 75), 100) / 100
    if args.get("delegated_range_pct") is not None:
        prof["delegated_range"] = min(max(float(args["delegated_range_pct"]), 5), 25) / 100
    choices = args.get("manager_choices") or {}
    perf = core.performance(S.profile(), S.days(), date)
    others = [x for x in S.days() if x["service_date"] != date]
    res, pending, _, meta = core.run_morning(prof, inputs, others, choices, prof["approver"], core.gate_tuple(perf))
    return {"what_if_only": "Nothing was saved.", "date": date, "notes": notes, "autonomy": res.autonomy,
            "context_completeness": f"{res.context.completeness:.0%}", "missing": res.context.missing,
            "stale": res.context.stale, "decisions": _decisions(res.records),
            "rule_traces": {r["Decision ID"]: res.traces[r["Decision ID"]]["governance"]["rule_trace"] for r in res.records},
            "manager_responses": "Anything needing a person was approved unless manager_choices says otherwise."}


TOOLS = {"list_services": t_list_services, "get_service": t_get_service, "get_decision": t_get_decision,
         "get_performance": t_get_performance, "what_if": t_what_if}
CHOICE = {"type": "object", "properties": {"choice": {"type": "string", "enum": ["approve", "modify", "reject", "more_context"]},
                                           "new_change_pct": {"type": "number"},
                                           "reason": {"type": "string", "enum": sim.CATEGORIES}}, "required": ["choice"]}
DECLS = [
    {"name": "list_services", "description": "List every service in this hotel's workspace with status, autonomy, covers, waste and stockouts."},
    {"name": "get_service", "description": "The saved plan for one date: kitchen plan, every decision with authority and status, and the close-out if recorded.",
     "parameters": {"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD; default latest"}}}},
    {"name": "get_decision", "description": "One decision by ID (e.g. D-0418) with its reason, full governance rule trace, human decision and action.",
     "parameters": {"type": "object", "properties": {"decision_id": {"type": "string"}}, "required": ["decision_id"]}},
    {"name": "get_performance", "description": "This hotel's earned autonomy: readiness-gate checks from its own last 28 days, evidence gaps, first blocker."},
    {"name": "what_if", "description": ("Re-run one morning through the real agents and governance with changed inputs or policy, without saving. "
                                        "Only pass what the user wants changed."),
     "parameters": {"type": "object", "properties": {
         "date": {"type": "string", "description": "YYYY-MM-DD; default the latest morning with data"},
         "occupied_rooms": {"type": "integer"}, "breakfast_inclusive_rooms": {"type": "integer"},
         "inventory_age_hours": {"type": "number", "description": f"Over {core.STALE_AFTER_HOURS['inventory']} hours is stale"},
         "guest_fb_score": {"type": "number"},
         "carry_over_kg": {"type": "object", "properties": {g: {"type": "number"} for g in core.GROUPS}},
         "event_revised_covers": {"type": "array", "description": "Revised cover counts for named events that morning",
                                  "items": {"type": "object", "properties": {"name": {"type": "string"},
                                                                             "revised_covers": {"type": "integer"}},
                                            "required": ["name", "revised_covers"]}},
         "remove_sources": {"type": "array", "items": {"type": "string", "enum": list(DROPPABLE)}},
         "context_threshold_pct": {"type": "number"}, "delegated_range_pct": {"type": "number"},
         "manager_choices": {"type": "object", "properties": {"production_adjustment": CHOICE, "purchasing_adjustment": CHOICE,
                                                              "banquet_production_change": CHOICE}}}}},
]


def system_prompt():
    p = S.profile()
    return f"""You are the Ops Copilot inside Hotel AgentOps for {S.hotel()['name']} ({p['rooms']} rooms), helping the
F&B team understand their governed AI production planning.
{'This is a DEMO workspace using the case study modeled data.' if S.is_demo() else 'This is a real hotel workspace; data was entered by the hotel.'}
Rules:
1. Every number, decision, authority level and outcome you state must come from a tool result in this conversation. Never invent figures.
2. You explain; you never decide. Governance rules decide who may act. Quote the rule-trace line when authority matters.
   High confidence never grants authority by itself. Autonomy is earned from the hotel's own track record.
3. what_if changes nothing and saves nothing; say so. Waste figures labeled estimate are estimates.
4. If something isn't in the tools (other hotels, prices, live system data), say so plainly.
5. Style: direct answer first, then "Why" with the rule, then one line on what it means for the kitchen. Short bullets,
   decision IDs, about 180 words unless asked for more."""


def page():
    site.page_header("Ops copilot", "Ask about your plans, decisions and results",
              "An AI assistant that answers from this workspace's records and can re-run a morning with different "
              "figures. It explains; governance rules still decide who may act.", photo="band_copilot.jpg")
    key = S.secret("GEMINI_API_KEY")
    if not key:
        st.warning("The copilot isn't switched on for this deployment (it needs a GEMINI_API_KEY secret). Everything else works.")
        return
    for k, v in (("cp_hist", []), ("cp_chat", []), ("cp_asked", 0), ("cp_state", {})):
        st.session_state.setdefault(k, v)
    for m in st.session_state.cp_chat:
        with st.chat_message(m["role"], avatar="🌿" if m["role"] == "assistant" else None):
            st.markdown(m["text"])
            steps(m.get("steps"))
    q = st.chat_input("e.g. Why did D-0418 need my approval? What if inventory was counted 14 hours ago?", key="cp_in")
    if not st.session_state.cp_chat:
        st.caption("Try: “Summarise this morning's plan” · “Why is autonomy SUPERVISED?” · “What if the wedding is revised to 180 covers?”")
    if not q:
        return
    if st.session_state.cp_asked >= MAX_QUESTIONS:
        st.info(f"This session has used its {MAX_QUESTIONS} questions. Leave and reopen the workspace to continue.")
        return
    st.session_state.cp_asked += 1
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant", avatar="🌿"):
        saved = copy.deepcopy(st.session_state.cp_hist)
        try:
            with st.spinner("Checking your records…"):
                models = [m for m in [S.secret("GEMINI_MODEL")] if m] + agent.FALLBACK_MODELS
                answer, st_ = agent.run(q, st.session_state.cp_hist, system_prompt(), DECLS, TOOLS, key, models,
                                        st.session_state.cp_state)
        except agent.AgentError as ex:
            st.session_state.cp_hist = saved
            st.error(str(ex))
            return
        st.markdown(answer)
        steps(st_)
        st.session_state.cp_chat += [{"role": "user", "text": q}, {"role": "assistant", "text": answer, "steps": st_}]


def steps(items):
    if not items:
        return
    with st.expander(f"Show the work · {len(items)} tool call{'s' if len(items) != 1 else ''}"):
        for i, s in enumerate(items, 1):
            st.markdown(f"**{i}. `{s['tool']}`** " + (f"`{json.dumps(s['args'])}`" if s["args"] else ""))
            st.code(json.dumps(s["result"], indent=2, default=str)[:2500], language="json")


page()
site.app_footer("The copilot uses Google Gemini to explain; decisions come from the governed engine.")
