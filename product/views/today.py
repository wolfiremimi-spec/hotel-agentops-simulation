import datetime as dt

import pandas as pd
import streamlit as st

from control_room import sim, ui
from product import app_state as S
from product import printsheet, site, tour
from product import core

GL = sim.GROUP_LABEL
CHOICE_MAP = {"Approve": "approve", "Modify": "modify", "Reject": "reject", "Request more context": "more_context"}


NUM = "number"


def table(rows, cols):
    """An editable table with fixed column types, so empty tables still accept numbers."""
    df = pd.DataFrame(rows or [], columns=list(cols))
    for c, kind in cols.items():
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64") if kind == NUM else df[c].astype("object")
    return df


def section(num, title):
    st.markdown(f'<div class="ha-sec"><div class="n">{ui.e(num)}</div><div class="t">{ui.e(title)}</div></div>',
                unsafe_allow_html=True)


def level_banner(perf):
    lvl = perf["autonomy"]
    st.markdown(f'<div class="ha-level"><b>Autonomy today: {ui.e(lvl)}</b> · {ui.e(perf["autonomy_why"][0])}</div>',
                unsafe_allow_html=True)


def kitchen_sheet(run):
    plan, usable = core.plan_served(run)
    standing = run["scenario"]["kitchen_standing_plan_kg"]
    rows = [{"Item group": GL[g], "Prepare (kg)": round(plan[g], 1), "Usable carry-over (kg)": round(usable.get(g, 0.0), 1),
             "Standing par (kg)": standing[g], "Change vs par": f"{plan[g] / standing[g] - 1:+.0%}" if standing[g] else "—"}
            for g in core.GROUPS]
    return pd.DataFrame(rows)


STATUS_KIND = {"accepted": "ok", "adjusted": "warn", "rejected": "hold", "fallback": "neutral"}
STATUS_TEXT = {"accepted": "ACCEPTED", "adjusted": "ADJUSTED · VERIFIED", "rejected": "REJECTED BY VERIFICATION",
               "fallback": "RULE-BASED FALLBACK"}


def agent_panel(mode, reports):
    """What each AI agent concluded, what it changed, and what verification allowed."""
    st.markdown(f"**How the agents reasoned** · {ui.e(mode or 'Rule-based agents')}", unsafe_allow_html=True)
    if not reports:
        st.caption("Rule-based agents: fixed, auditable logic (the case study's deterministic baseline)." +
                   ("" if S.ai_available() else " Add a GEMINI_API_KEY to run the specialists as AI agents."))
        return
    for r in reports:
        with st.container(border=True):
            st.markdown(f"{ui.pill(STATUS_TEXT.get(r['status'], r['status']).upper(), STATUS_KIND.get(r['status'], 'neutral'))} "
                        f"&nbsp;<b>{ui.e(r['agent'])}</b>" + (f" · {ui.e(r['model'])}" if r.get("model") else ""),
                        unsafe_allow_html=True)
            if r.get("rationale"):
                st.markdown(f"_{ui.e(r['rationale'])}_", unsafe_allow_html=True)
            bits = []
            if r.get("changes"):
                bits.append("Changed: " + "; ".join(r["changes"]))
            if r.get("verification"):
                bits.append("Verification: " + "; ".join(r["verification"]))
            if r.get("tools"):
                bits.append("Tools used: " + ", ".join(t for t in r["tools"] if t != "submit"))
            if r.get("error"):
                bits.append("Why the fallback: " + r["error"])
            if bits:
                st.caption(" · ".join(bits))


def show_saved(day, date):
    run = day["run"]
    rec = core.production_record(run)
    st.success(f"Today's plan is saved ({day['status']}). Autonomy that morning: {run['autonomy']} · context "
               f"{run['context']['completeness']:.0%}.")
    st.markdown("**Kitchen production sheet**")
    sheet = kitchen_sheet(run)
    st.dataframe(sheet, use_container_width=True, hide_index=True)
    plan, usable = core.plan_served(run)
    ins = day.get("inputs") or {}
    html_sheet = printsheet.build(
        S.hotel()["name"], S.profile().get("service_name", "Breakfast"), date, plan, usable,
        run["scenario"]["kitchen_standing_plan_kg"],
        [{"id": r["Decision ID"], "what": r["Recommendation"], "who": r["Human Decision"], "status": r["Execution Status"]}
         for r in run["records"]],
        approver=next((r.get("Approver") for r in run["records"] if r.get("Approver")), "") or S.profile().get("approver", ""),
        autonomy=run.get("autonomy", ""), carry_items=core.carry_over_rows(ins),
        transfers=[r["Recommendation"] for r in run["records"] if r["Decision Type"] == "inventory_transfer"
                   and str(r["Execution Status"]).startswith("EXECUTED")],
        note="demo · modeled data" if S.is_demo() else "")
    d1, d2 = st.columns(2)
    d1.download_button("Printable kitchen sheet (open, then print or save as PDF)", html_sheet.encode(),
                       f"kitchen_sheet_{date}.html", "text/html", key=f"td_print_{date}", type="primary",
                       use_container_width=True)
    d2.download_button("Download the kitchen sheet (CSV)", sheet.to_csv(index=False).encode(), f"kitchen_sheet_{date}.csv",
                       "text/csv", key=f"td_dl_{date}", use_container_width=True)
    if rec is not None and rec["Decision Type"] == "abstain_missing_context":
        st.warning("The system abstained this morning (not enough data), so the kitchen serves its standing par.")
    with st.expander(f"How the agents reasoned · {run.get('agent_mode', 'Rule-based agents')}"):
        agent_panel(run.get("agent_mode"), run.get("ai_agents"))
    st.markdown("**Decisions this morning**")
    st.dataframe(pd.DataFrame([{"ID": r["Decision ID"], "Decision": sim.TYPE_LABEL.get(r["Decision Type"], r["Decision Type"]),
                                "Recommendation": r["Recommendation"], "Authority": r["Required Authority"],
                                "Human decision": r["Human Decision"], "Status": r["Execution Status"]}
                               for r in run["records"]]), use_container_width=True, hide_index=True)
    c = st.columns(2)
    if day.get("closeout"):
        c[0].info("This service is closed out. Its results feed your performance record.")
    else:
        if c[0].button("Close out this service after breakfast →", type="primary", use_container_width=True,
                       key=f"td_goto_co_{date}"):
            st.session_state.co_date = date
            st.switch_page("product/views/closeout.py")
        if c[1].button("Re-plan this morning", use_container_width=True, key=f"td_replan_{date}"):
            st.session_state[f"td_replan_{date}_on"] = True
            st.rerun()


def inputs_form(date, base):
    p = S.profile()
    k = f"_{date}"
    groups_of = core.item_groups(p)
    for r in ((base.get("near_expiry") or []) + (base.get("open_orders") or []) + core.carry_over_rows(base)
              + (st.session_state.get(f"td_prefill_{date}") or [])):   # keep items saved before a menu edit
        if r.get("item") and r.get("group"):
            groups_of.setdefault(r["item"], r["group"])
    with st.form(f"td_form{k}"):
        t1, t2, t3, t4 = st.tabs(["Occupancy & reservations", "Inventory", "Events", "Guest signal"])
        with t1:
            c = st.columns(3)
            occ = c[0].number_input(f"Occupied rooms tonight (of {p['rooms']})", 0, int(p["rooms"]),
                                    value=base.get("occupied_rooms"), step=1, key=f"td_occ{k}", placeholder="required")
            guests = c[1].number_input("In-house guests", 0, 20000, value=base.get("in_house_guests"), step=1, key=f"td_guests{k}")
            pms_age = c[2].number_input("PMS figure age (hours)", 0.0, 72.0, float(base.get("pms_age_hours") or 1), 0.5,
                                        key=f"td_pmsage{k}")
            c = st.columns(3)
            bi = c[0].number_input("Breakfast-inclusive rooms", 0, int(p["rooms"]), value=base.get("breakfast_inclusive_rooms"),
                                   step=1, key=f"td_bi{k}", placeholder="required")
            ob = c[1].number_input("Outside breakfast bookings", 0, 2000, int(base.get("outside_breakfast_bookings") or 0), 1,
                                   key=f"td_ob{k}")
            res_age = c[2].number_input("Reservations age (hours)", 0.0, 72.0, float(base.get("reservations_age_hours") or 1),
                                        0.5, key=f"td_resage{k}")
            fd_notes = st.text_area("Front-desk notes (groups arriving, early check-outs, anything unusual)",
                                    base.get("front_desk_notes") or "", key=f"td_fdnotes{k}",
                                    help="The AI Demand Agent reads these; the rule-based agents can't.")
        with t2:
            items = sorted(groups_of, key=str.lower)
            item_col = st.column_config.SelectboxColumn("Item (type to search)", options=items, required=True, width="medium",
                                                        help="Start typing, e.g. 'yog', and pick from the suggestions. "
                                                             "Edit this list in Hotel setup → Menu & par levels.")
            inv_age = st.number_input(f"Hours since the inventory count (more than {core.STALE_AFTER_HOURS['inventory']} "
                                      "hours counts as stale and blocks inventory-dependent actions)", 0.0, 240.0,
                                      value=None if base.get("inventory_age_hours") is None else float(base["inventory_age_hours"]),
                                      step=0.5, key=f"td_invage{k}", placeholder="required")
            st.caption("Carry-over from yesterday · click **+** to add a row, type the item, enter the kg and untick "
                       "anything past its shelf life (it won't be counted as usable)")
            prefill = st.session_state.get(f"td_prefill_{date}")
            carry_df = pd.DataFrame(prefill or core.carry_over_rows(base) or [], columns=["item", "kg", "within_shelf_life"])
            carry_df["item"] = carry_df["item"].astype("object")
            carry_df["kg"] = pd.to_numeric(carry_df["kg"], errors="coerce").astype("float64")
            carry_df["within_shelf_life"] = carry_df["within_shelf_life"].fillna(True).astype("bool")
            carry_ed = st.data_editor(carry_df, num_rows="dynamic", use_container_width=True, key=f"td_carry{k}_{st.session_state.get(f'td_prefill_v_{date}', 0)}",
                                      column_config={"item": item_col,
                                                     "kg": st.column_config.NumberColumn("kg", min_value=0.0, max_value=500.0,
                                                                                         step=0.5, required=True),
                                                     "within_shelf_life": st.column_config.CheckboxColumn(
                                                         "Within shelf life", default=True)})
            kit_notes = st.text_area("Kitchen notes (quality issues, deliveries, equipment)", base.get("kitchen_notes") or "",
                                     key=f"td_kitnotes{k}", help="The AI Inventory Agent reads these.")
            st.caption("Near-expiry stock that could go to another outlet · click **+** to add a row, then type the item name")
            near = st.data_editor(table(base.get("near_expiry"), {"item": "text", "kg": NUM, "expires_in_days": NUM,
                                                                  "alternative_outlet": "text"}),
                                  num_rows="dynamic", use_container_width=True, key=f"td_near{k}",
                                  column_config={"item": item_col,
                                                 "kg": st.column_config.NumberColumn("kg", min_value=0.0, step=0.5),
                                                 "expires_in_days": st.column_config.NumberColumn("Expires in (days)", min_value=0,
                                                                                                  max_value=30, step=1),
                                                 "alternative_outlet": st.column_config.SelectboxColumn(
                                                     "Could go to", options=core.outlets(p))})
            st.caption("Open supplier orders (the agents may recommend reducing chronic-waste items)")
            orders = st.data_editor(table(base.get("open_orders"), {"order_id": "text", "item": "text", "kg": NUM,
                                                                    "delivery": "text", "supplier": "text"}),
                                    num_rows="dynamic", use_container_width=True, key=f"td_orders{k}",
                                    column_config={"order_id": st.column_config.TextColumn("Order #"), "item": item_col,
                                                   "kg": st.column_config.NumberColumn("kg", min_value=0.0, step=1.0),
                                                   "delivery": st.column_config.TextColumn("Delivery"),
                                                   "supplier": st.column_config.TextColumn("Supplier")})
        with t3:
            ev_ok = st.checkbox("I have checked the events calendar (tick even if there are no events)",
                                bool(base.get("events_confirmed")), key=f"td_evok{k}")
            events = st.data_editor(table(base.get("events"), {"name": "text", "date": "text", "guaranteed_covers": NUM,
                                                      "revised_covers": NUM, "planned_production_kg": NUM}),
                                    num_rows="dynamic", use_container_width=True, key=f"td_events{k}",
                                    column_config={"guaranteed_covers": st.column_config.NumberColumn(min_value=0, step=1),
                                                   "revised_covers": st.column_config.NumberColumn(min_value=0, step=1),
                                                   "planned_production_kg": st.column_config.NumberColumn(min_value=0.0)})
            st.caption("A revised count more than 25% away from the guarantee is abnormal demand and always goes to a person.")
        with t4:
            c = st.columns(2)
            gs = c[0].number_input("Recent guest F&B score (1–5)", 1.0, 5.0, value=base.get("guest_fb_score"), step=0.01,
                                   key=f"td_gs{k}", placeholder="required")
            cm = c[1].number_input("Open F&B complaints", 0, 500, int(base.get("open_fb_complaints") or 0), 1, key=f"td_cm{k}")
        go = st.form_submit_button("Save this morning's data and ask the agents", type="primary", use_container_width=True)
    if not go:
        return None

    def rows(df):
        return [{kk: (None if pd.isna(v) else v) for kk, v in r.items()} for r in df.to_dict("records")]

    def item_rows(df):
        out = []
        for r in rows(df):
            if r.get("item") in groups_of:
                r["group"] = groups_of[r["item"]]          # the group comes from the menu, not from typing
                out.append(r)
        return out
    carry_items = [dict(r, within_shelf_life=bool(r.get("within_shelf_life", True))) for r in item_rows(carry_ed)
                   if r.get("kg")]
    carry, shelf = core.carry_over_totals(carry_items)
    return {
        "service_date": date, "occupied_rooms": occ, "in_house_guests": guests, "pms_age_hours": pms_age,
        "breakfast_inclusive_rooms": bi, "outside_breakfast_bookings": ob, "reservations_age_hours": res_age,
        "inventory_age_hours": inv_age, "carry_over_kg": carry, "within_shelf_life": shelf, "carry_over_items": carry_items,
        "near_expiry": item_rows(near), "open_orders": item_rows(orders), "events": rows(events), "events_confirmed": ev_ok,
        "events_age_hours": 1, "guest_fb_score": gs, "open_fb_complaints": cm, "guest_age_hours": 12,
        "front_desk_notes": fd_notes, "kitchen_notes": kit_notes,
    }


def recommend_and_approve(date, inputs, perf):
    p = S.profile()
    ai = S.ai_config()
    with st.spinner("The agents are analyzing this morning…" if ai else "Running the agents…"):
        res, pending, scenario, meta = core.run_morning(p, inputs, S.days(), None, p["approver"], core.gate_tuple(perf), ai=ai)
    agent_panel(meta.get("agent_mode"), meta.get("ai_agents"))
    ctx = res.context
    cols = st.columns(4)
    for i, s in enumerate(core.SOURCES):
        stt = ctx.status.get(s, "missing")
        cols[i % 4].markdown(f"{ui.pill('OK' if stt == 'ok' else stt.upper(), 'ok' if stt == 'ok' else 'hold')} "
                             f"&nbsp;{sim.SOURCE_LABEL[s]}", unsafe_allow_html=True)
    hx = meta["history"]
    st.caption(f"Context completeness {ctx.completeness:.0%} (your policy requires {p['context_threshold']:.0%}). "
               f"History used: {len(hx['comparable'])} previous {hx['weekday']}s for demand, {len(hx['waste_rows'])} for "
               f"waste, {len(hx['apes'])} recent forecast errors. Consumption per cover: {hx['per_cover_source']}.")
    if not hx["has_pos"] or not hx["has_waste"]:
        st.warning(f"This hotel doesn't have {core.HISTORY_NEEDED} previous {hx['weekday']} services on record yet, so "
                   "covers or waste history counts as missing. Add baseline history in Hotel setup, or close out more "
                   "services; the system will abstain until it has enough.")

    auto = [r for r in res.records if r["Required Authority"].startswith("Agent executes")]
    stopped = [r for r in res.records if r["Execution Status"].startswith(("BLOCKED", "ABSTAINED"))]
    if auto:
        st.caption("Handled by the agents on delegated authority: " + " · ".join(
            f"{r['Decision ID']} {r['Recommendation']}" for r in auto))
    for r in stopped:
        tr = res.traces[r["Decision ID"]]["governance"]["rule_trace"]
        st.warning(f"**{r['Decision ID']} · {sim.TYPE_LABEL.get(r['Decision Type'], r['Decision Type'])}: "
                   f"{r['Execution Status']}.** {r['Recommendation']}  \nRule: {tr[-2] if len(tr) > 1 else tr[-1]}")

    choices, missing_notes, k = {}, [], f"_{date}"
    for pd_ in pending:
        wkey = f"{pd_.decision_id}_{pd_.decision_type}{k}"
        with st.container(border=True):
            top = st.columns([3, 1])
            top[0].markdown(f"**{pd_.decision_id} · {sim.TYPE_LABEL.get(pd_.decision_type, pd_.decision_type)}**  \n"
                            f"{ui.e(pd_.recommendation)}")
            top[1].markdown(ui.pill(pd_.authority, ui.authority_kind(pd_.authority)), unsafe_allow_html=True)
            m = st.columns(3)
            m[0].metric("Confidence", f"{pd_.confidence:.1%}")
            m[1].metric("Risk", pd_.risk)
            m[2].metric("Reversibility", pd_.reversibility)
            st.markdown(f"**Why:** {ui.e(pd_.reason)}  \n**Expected impact:** {ui.e(pd_.expected_impact)}")
            if pd_.lines:
                st.dataframe(pd.DataFrame([{"Item group": GL.get(l["group"], l["group"]), "Expected need (kg)": l["expected_consumption_kg"],
                                            "AI plan (kg)": l["planned_kg"], "Standing par (kg)": l["standing_plan_kg"],
                                            "Change": f"{l['change']:+.0%}", "Buffer": f"{l['buffer']:.0%}"} for l in pd_.lines]),
                             use_container_width=True, hide_index=True)
            with st.expander("Governance rule trace: why this needs you"):
                st.markdown('<div class="cr-trace">' + ui.e("\n".join(pd_.rule_trace)) + "</div>", unsafe_allow_html=True)
            c = st.columns([1.3, 1, 1.6])
            opts = ["Approve", "Modify", "Reject", "Request more context"] if pd_.modifiable else ["Approve", "Reject",
                                                                                                "Request more context"]
            pick = c[0].radio("Your decision", opts, index=None, key=f"td_ch_{wkey}")
            if pick is None:
                c[1].caption("No decision yet")
                choices[pd_.decision_type] = {"choice": None}
                continue
            ch = {"choice": CHOICE_MAP[pick]}
            if pick == "Modify":
                ch["new_change_pct"] = c[1].number_input("New change vs standing par (%)" if pd_.decision_type == "production_adjustment"
                                                         else "New change vs current order (%)", -50.0, 50.0, -8.0, 1.0,
                                                         key=f"td_pct_{wkey}")
            if pick in ("Modify", "Reject"):
                ch["reason"] = c[2].selectbox("Reason (feeds the learning loop)", sim.CATEGORIES, key=f"td_rs_{wkey}")
            if pick == "Request more context":
                ch["note"] = c[2].text_input("What do you need to know?", key=f"td_nt_{wkey}")
                if not str(ch["note"]).strip():
                    missing_notes.append(pd_.decision_type)
            choices[pd_.decision_type] = ch

    approver = st.text_input("Approved by", p["approver"], key=f"td_by{k}")
    label = "Save my decisions and today's plan" if pending else "Confirm and save today's plan"
    if st.button(label, type="primary", use_container_width=True, key=f"td_submit{k}"):
        open_ = [t for t, c_ in choices.items() if c_.get("choice") is None]
        if open_:
            st.error("Decision required for: " + ", ".join(sim.TYPE_LABEL.get(t, t) for t in open_))
            return
        if missing_notes:
            st.error("Say what context you need for: " + ", ".join(sim.TYPE_LABEL.get(t, t) for t in missing_notes))
            return
        if not approver.strip():
            st.error("Enter who approved the plan.")
            return
        final, _, scen, meta2 = core.run_morning(p, inputs, S.days(), choices, approver.strip(), core.gate_tuple(perf),
                                                 ai=S.ai_config())
        run = core.serialize_run(final, scen, meta2)
        store, hid = S.get_store(), S.hotel()["id"]
        store.save_day(hid, date, status="approved", inputs=inputs, run=run, closeout=None)
        store.log(hid, approver.strip(), "plan_approved", {
            "service_date": date, "autonomy": final.autonomy,
            "decisions": [{"id": r["Decision ID"], "type": r["Decision Type"], "authority": r["Required Authority"],
                           "human": r["Human Decision"], "status": r["Execution Status"]} for r in final.records]})
        st.session_state.pop(f"td_replan_{date}_on", None)
        st.session_state.pop(f"td_inputs_{date}", None)
        S.invalidate()
        st.rerun()


def page():
    site.page_header("Today's plan", "This morning's production plan",
              "Enter this morning's figures. The agents recommend, governance routes each decision, and you approve "
              "what needs you. The saved plan becomes the kitchen's production sheet.", photo="band_ingredients.jpg")
    tour.hint("product/views/today.py")
    if S.is_demo():
        ui.banner("<b>Demo workspace.</b> Modeled case-study data; the D-0418 morning is prefilled. Nothing is saved after you leave.")
    date = st.date_input("Service date", dt.date.fromisoformat(S.today()), key="td_date").isoformat()
    day = next((d for d in S.days() if d["service_date"] == date), None)
    perf = S.performance_for(date)
    level_banner(perf)

    if day and day.get("run") and not st.session_state.get(f"td_replan_{date}_on"):
        show_saved(day, date)
        return
    if day and day.get("closeout"):
        st.info("This service is already closed out, so its plan can't be changed.")
        return

    section("01", "This morning's data")
    if f"td_inputs_{date}" not in st.session_state:
        if day and day.get("inputs"):
            base = day["inputs"]
        elif S.is_demo() and date == S.profile().get("demo_anchor_date"):
            base = core.demo_inputs(S.profile())
        else:
            base = core.blank_inputs(date)
        st.session_state[f"td_base_{date}"] = base
    base = st.session_state.get(f"td_inputs_{date}") or st.session_state[f"td_base_{date}"]
    prev = next((d for d in sorted(S.days(), key=lambda d: d["service_date"], reverse=True)
                 if d["service_date"] < date and (d.get("inputs") or {}).get("carry_over_items")), None)
    if prev:
        names = list(dict.fromkeys(r["item"] for r in prev["inputs"]["carry_over_items"]))
        c = st.columns([1.3, 2])
        if c[0].button(f"↺ Start carry-over from {prev['service_date']}'s items", use_container_width=True,
                       key=f"td_prefill_btn_{date}",
                       help="Fills the carry-over table with the same items as last time, with the kg left blank "
                            "so you only weigh and enter today's amounts. Rows left blank aren't counted."):
            st.session_state[f"td_prefill_{date}"] = [{"item": r["item"], "group": r["group"], "kg": None,
                                                       "within_shelf_life": True}
                                                      for r in {r["item"]: r for r in prev["inputs"]["carry_over_items"]}.values()]
            st.session_state[f"td_prefill_v_{date}"] = st.session_state.get(f"td_prefill_v_{date}", 0) + 1
            st.rerun()
        c[1].caption(f"Last recorded: {', '.join(names[:6])}{'…' if len(names) > 6 else ''}")
    submitted = inputs_form(date, base)
    if submitted is not None:
        st.session_state[f"td_inputs_{date}"] = submitted
        S.get_store().save_day(S.hotel()["id"], date, status="draft", inputs=submitted)
        S.invalidate()
        st.rerun()
    inputs = st.session_state.get(f"td_inputs_{date}")
    if inputs is None:
        st.info("Fill in this morning's data, then save it to get the agents' recommendations.")
        return
    section("02", "Recommendations and your decisions")
    recommend_and_approve(date, inputs, perf)


page()
site.app_footer()
