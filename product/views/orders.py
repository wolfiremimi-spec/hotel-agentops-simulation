import csv
import datetime as dt
import io

import pandas as pd
import streamlit as st

from control_room import ui
from product import app_state as S
from product import tour
from product import core, ordering, site

GL = core.GROUP_LABEL
PATTERN = {"stockout_prone": ("RAN OUT", "hold"), "chronic_overproduction": ("OFTEN LEFT OVER", "neutral"),
           "normal": ("STEADY", "ok")}


def section(num, title):
    st.markdown(f'<div class="ha-sec"><div class="n">{ui.e(num)}</div><div class="t">{ui.e(title)}</div></div>',
                unsafe_allow_html=True)


def page():
    site.page_header("Next week's order", "What to order, and how to waste less",
                     "The Procurement Agent turns this hotel's own close-outs into next week's supplier order per item group: less "
                     "where food is usually left over, more where guests ran short. A manager approves every order.",
                     photo="band_order.jpg")
    tour.hint("product/views/orders.py")
    if S.is_demo():
        ui.banner("<b>Demo workspace.</b> Built from the case study's modeled history. Nothing is saved after you leave.")
    p = S.profile()
    days = S.days()
    ev = ordering.evidence(p, days)
    if not ev["services"]:
        st.info("The order suggestion learns from recorded services. Add baseline history in Hotel setup, or close out a "
                "few services, and it will appear here.")
        return

    start = st.date_input("Week starting", dt.date.fromisoformat(ordering.next_monday(S.today())), key="or_start").isoformat()
    dates = ordering.week_dates(start)

    section("01", "Expected covers next week")
    st.caption("Prefilled from this hotel's recorded services. Change any day you know will be different "
               "(a group arriving, a holiday, a quiet week).")
    base = pd.DataFrame(ordering.default_covers(ev, dates))
    base["expected_covers"] = pd.to_numeric(base["expected_covers"], errors="coerce").astype("float64")
    cov = st.data_editor(base, hide_index=True, use_container_width=True, key=f"or_cov_{start}",
                         disabled=["date", "day", "basis"],
                         column_config={"date": st.column_config.TextColumn("Date"),
                                        "day": st.column_config.TextColumn("Day"),
                                        "expected_covers": st.column_config.NumberColumn("Expected covers", min_value=0,
                                                                                         max_value=20000, step=1),
                                        "basis": st.column_config.TextColumn("Based on", width="large")})
    covers = [{"date": r["date"], "day": r["day"],
               "expected_covers": None if pd.isna(r["expected_covers"]) else int(r["expected_covers"])}
              for r in cov.to_dict("records")]
    if any(c["expected_covers"] is None for c in covers):
        st.warning("Enter expected covers for every day to get the suggestion.")
        return
    with st.expander("Stock already on hand at the start of the week (optional)"):
        c = st.columns(4)
        on_hand = {g: c[i].number_input(f"{GL[g]} (kg)", 0.0, 5000.0, 0.0, 1.0, key=f"or_oh_{g}_{start}")
                   for i, g in enumerate(core.GROUPS)}

    rec = ordering.recommend(p, ev, covers, on_hand)
    cfg = S.ai_config()
    review = None
    if cfg is not None:
        with st.spinner("The Procurement Agent is reviewing the order…"):
            review = ordering.ai_review(rec, covers, ev, cfg)

    section("02", "Suggested order")
    lines = rec["lines"]
    total_s = sum(l["suggested_kg"] for l in lines.values())
    total_p = sum(l["standing_par_kg"] for l in lines.values())
    cost = float(p["waste_cost_per_kg"])
    k = st.columns(4)
    k[0].metric("Expected covers", f"{rec['total_covers']:,}")
    k[1].metric("Suggested order", f"{total_s:,.0f} kg", f"{total_s - total_p:+,.0f} kg vs standing par", delta_color="inverse")
    k[2].metric("Potential waste avoided", f"{rec['waste_avoided_estimate_kg']:,.0f} kg", "estimate", delta_color="off")
    k[3].metric("Potential saving", f"${rec['waste_avoided_estimate_kg'] * cost:,.0f}", f"at ${cost:.2f}/kg · estimate",
                delta_color="off")

    with st.container(border=True):
        if review and review["status"] == "verified":
            st.markdown(f"{ui.pill('AI · VERIFIED', 'ok')} &nbsp;<b>Procurement Agent</b>"
                        + (f" · {ui.e(review['model'])}" if review.get("model") else ""), unsafe_allow_html=True)
            st.markdown(ui.e(review["explanation"] or ordering.rule_explanation(rec)), unsafe_allow_html=True)
            bits = []
            if review.get("watch"):
                bits.append("Watch: " + "; ".join(review["watch"]))
            if review.get("changes"):
                bits.append("Raised for guest safety: " + "; ".join(review["changes"]))
            if review.get("rejected"):
                bits.append("Verification blocked: " + "; ".join(review["rejected"]))
            bits.append("The AI can raise an order for guest safety, never cut one below expected use.")
            st.caption(" · ".join(bits))
        else:
            st.markdown(f"{ui.pill('RULE-BASED', 'neutral')} &nbsp;<b>Procurement Agent</b>", unsafe_allow_html=True)
            st.markdown(ui.e(ordering.rule_explanation(rec)), unsafe_allow_html=True)
            if review and review.get("error"):
                st.caption("The AI agent was unavailable, so the rule-based explanation is shown. Why: " + review["error"])

    table = pd.DataFrame([{
        "Item group": l["label"], "Pattern": PATTERN[l["pattern"]][0].title(), "Why": l["why"],
        "Expected use (kg)": l["expected_use_kg"], "Safety buffer": f"{l['buffer']:.0%}",
        "Standing par (kg)": l["standing_par_kg"], "Suggested (kg)": l["suggested_kg"],
        "Your order (kg)": l["suggested_kg"]} for l in lines.values()])
    edited = st.data_editor(table, hide_index=True, use_container_width=True, key=f"or_tbl_{start}",
                            disabled=[c for c in table.columns if c != "Your order (kg)"],
                            column_config={"Why": st.column_config.TextColumn(width="large"),
                                           "Your order (kg)": st.column_config.NumberColumn(min_value=0.0, step=1.0)})
    st.caption(f"Expected use = expected covers × consumption per cover ({rec['per_cover_source']}). Buffers: "
               f"{ordering.BUFFER['stockout_prone']:.0%} where guests ran short, {ordering.BUFFER['normal']:.0%} normally, "
               f"{ordering.BUFFER['chronic_overproduction']:.0%} where food is usually left over (15% or more on average). Savings are estimates: "
               "they assume stock bought above need ends up as waste.")

    final = {g: float(edited.iloc[i]["Your order (kg)"] or 0.0) for i, g in enumerate(core.GROUPS)}
    below = [g for g in core.GROUPS if final[g] + lines[g]["on_hand_kg"] < lines[g]["expected_use_kg"] - 0.05]
    changed = [g for g in core.GROUPS if abs(final[g] - lines[g]["suggested_kg"]) > 0.05]
    if below:
        st.warning("Below expected use (stockout risk for guests): " + ", ".join(GL[g] for g in below)
                   + ". A reason is required to approve.")

    section("03", "Approve the order")
    with st.form(f"or_approve_{start}"):
        c = st.columns([1, 2])
        approver = c[0].text_input("Approved by", p.get("approver", "F&B Manager"), key="or_approver")
        reason = c[1].text_input("Reason for changes" + (" (required)" if (changed or below) else " (optional)"),
                                 key="or_reason", placeholder="e.g. supplier minimum, a conference booked on Wednesday")
        go = st.form_submit_button("Approve and log this order", type="primary", use_container_width=True)
    if go:
        if (changed or below) and not reason.strip():
            st.error("Say why you changed the suggested order. It's recorded with the approval, like any override.")
        else:
            order = {"week_start": start, "approved_by": approver.strip() or "F&B Manager",
                     "approved_at": dt.datetime.now().isoformat(timespec="seconds"),
                     "agent": ("AI Procurement Agent (" + (review.get("model") or "Gemini") + ")")
                     if review and review["status"] == "verified" else "Rule-based Procurement Agent",
                     "total_covers": rec["total_covers"], "override": bool(changed), "reason": reason.strip(),
                     "lines": {g: {"suggested_kg": lines[g]["suggested_kg"], "ordered_kg": round(final[g], 1),
                                   "standing_par_kg": lines[g]["standing_par_kg"], "pattern": lines[g]["pattern"]}
                               for g in core.GROUPS}}
            store = S.get_store()
            h = S.hotel()
            new = dict(p, orders=[o for o in p.get("orders", []) if o["week_start"] != start] + [order])
            store.update_profile(h["id"], new)
            h["profile"] = new
            store.log(h["id"], order["approved_by"], "supplier_order_approved",
                      {"week_start": start, "ordered_kg": {g: order["lines"][g]["ordered_kg"] for g in core.GROUPS},
                       "override": order["override"], "reason": order["reason"]})
            st.success(f"Order for the week of {start} approved and logged in the audit trail.")

    orders = sorted(S.profile().get("orders", []), key=lambda o: o["week_start"], reverse=True)
    if orders:
        section("04", "Approved orders")
        st.dataframe(pd.DataFrame([{"Week of": o["week_start"], "Approved by": o["approved_by"], "Agent": o["agent"],
                                    **{f"{GL[g]} (kg)": o["lines"][g]["ordered_kg"] for g in core.GROUPS},
                                    "Changed by manager": "Yes" if o["override"] else "No", "Reason": o["reason"]}
                                   for o in orders]), hide_index=True, use_container_width=True)
        latest = orders[0]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Hotel", S.hotel()["name"]])
        w.writerow(["Week starting", latest["week_start"]])
        w.writerow(["Approved by", latest["approved_by"], latest["approved_at"]])
        w.writerow([])
        w.writerow(["Item group", "Order (kg)", "Suggested (kg)", "Standing par (kg)"])
        for g in core.GROUPS:
            ln = latest["lines"][g]
            w.writerow([GL[g], ln["ordered_kg"], ln["suggested_kg"], ln["standing_par_kg"]])
        st.download_button(f"Download the purchase order for {latest['week_start']} (CSV)", buf.getvalue().encode(),
                           f"purchase_order_{latest['week_start']}.csv", "text/csv", key="or_csv")


def order_results(p, days):
    evals = ordering.evaluate_orders(p, days)
    section("05" if p.get("orders") else "04", "How approved orders performed")
    if not evals:
        st.caption("Once services in an approved order's week are closed out, this compares what was ordered with what "
                   "the kitchen actually used, and next week's suggestion learns from any shortfall.")
        return
    for ev_ in evals[:3]:
        acc = ev_["accuracy"]
        with st.container(border=True):
            c = st.columns(4)
            c[0].metric(f"Week of {ev_['week_start']}", f"{ev_['days_recorded']} of 7 days", "closed out", delta_color="off")
            c[1].metric("Order accuracy", "—" if acc is None else f"{acc:.0%}", "1 − |ordered − used| ÷ used", delta_color="off")
            c[2].metric("Bought beyond use", f"{ev_['surplus_kg']:.0f} kg", "this order", delta_color="off")
            c[3].metric("At standing par", f"{ev_['par_surplus_kg']:.0f} kg", "beyond use (estimate)", delta_color="off")
            st.dataframe(pd.DataFrame([{"Item group": l["label"], "Ordered (kg, pro-rated)": l["ordered_kg"],
                                        "Used (kg)": l["used_kg"], "Surplus (+) / short (−) kg": l["surplus_kg"],
                                        "Standing par would have bought (kg)": l["standing_par_kg"],
                                        "Result": "Stockout" if l["stockout"] else ("Short" if l["short"] else "Covered")}
                                       for l in ev_["lines"].values()]), hide_index=True, use_container_width=True)
            short = [l["label"] for l in ev_["lines"].values() if l["short"]]
            if short:
                st.caption("Learning: " + ", ".join(short) + " ran short, so next week's suggestion gives "
                           + ("it" if len(short) == 1 else "them") + " the larger guest-safety buffer.")
    st.caption("Ordered amounts are pro-rated to the days closed out so far. Used = what the kitchen served and guests "
               "ate, from each close-out (available − leftover).")


def page_and_results():
    page()
    if S.hotel():
        order_results(S.profile(), S.days())


S.guard(page_and_results)
site.app_footer("Order suggestions are estimates from this hotel's own records; a manager approves every order.")
