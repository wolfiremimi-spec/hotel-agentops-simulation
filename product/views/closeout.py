import pandas as pd
import streamlit as st

from control_room import sim, ui
from product import app_state as S
from product import site
from product import core

GL = sim.GROUP_LABEL


def page():
    site.page_header("Close out service", "What actually happened at breakfast",
              "Record actual covers and what was left over. This scores the day's decisions, measures real waste and "
              "forecast accuracy, and builds the track record that autonomy is earned from.")
    if S.is_demo():
        ui.banner("<b>Demo workspace.</b> You can fill in the case study's modeled result for the D-0418 morning.")
    open_days = [d for d in S.days() if d.get("run") and not d.get("closeout")]
    closed = [d for d in S.days() if d.get("closeout")]
    if not open_days:
        st.info("No approved plans are waiting to be closed out. Approve today's plan first." if not closed else
                "Every approved service is closed out. See Performance & autonomy for the results.")
        if closed:
            show_result(closed[-1])
        return
    dates = [d["service_date"] for d in open_days]
    pre = st.session_state.get("co_date")
    date = st.selectbox("Service to close out", dates, index=dates.index(pre) if pre in dates else len(dates) - 1,
                        key="co_pick")
    day = next(d for d in open_days if d["service_date"] == date)
    run = day["run"]
    plan, usable = core.plan_served(run)
    rec = core.production_record(run)
    predicted = (run["traces"][rec["Decision ID"]].get("details") or {}).get("expected_covers") if rec else None
    st.markdown("**What the kitchen served**")
    st.dataframe(pd.DataFrame([{"Item group": GL[g], "Prepared (kg)": round(plan[g], 1),
                                "Usable carry-over (kg)": round(usable.get(g, 0.0), 1),
                                "Available (kg)": round(plan[g] + usable.get(g, 0.0), 1)} for g in core.GROUPS]),
                 use_container_width=True, hide_index=True)
    if predicted:
        st.caption(f"The agents predicted {predicted} covers.")

    k = f"_{date}"
    if S.is_demo() and date == S.profile().get("demo_anchor_date"):
        if st.button("Fill with the case study's modeled result", key=f"co_fill{k}"):
            obs = core.CASE["observed_outcome"]
            st.session_state[f"co_cov{k}"] = int(obs["actual_covers"])
            for g in core.GROUPS:
                avail = plan[g] + usable.get(g, 0.0)
                demand = obs["actual_covers"] * obs["actual_consumption_kg_per_cover"][g]
                st.session_state[f"co_left_{g}{k}"] = round(max(avail - demand, 0.0), 1)
                st.session_state[f"co_so_{g}{k}"] = demand > avail + 1e-9
            st.session_state[f"co_plate{k}"] = round(obs["plate_waste_kg_per_cover"] * obs["actual_covers"], 1)
            st.rerun()

    with st.form(f"co_form{k}"):
        c = st.columns(3)
        covers = c[0].number_input("Actual covers served", 1, 20000, step=1, key=f"co_cov{k}", placeholder="required",
                                   **({} if f"co_cov{k}" in st.session_state else {"value": None}))
        plate = c[1].number_input("Plate waste (kg, optional)", 0.0, 1000.0, step=0.1, key=f"co_plate{k}")
        gs = c[2].number_input("Guest F&B score for this service (optional)", 1.0, 5.0, value=None, step=0.01,
                               key=f"co_gs{k}")
        st.caption("Leftover food at the end of service (kg), and whether the item ran out")
        c = st.columns(4)
        left, so = {}, {}
        for i, g in enumerate(core.GROUPS):
            avail = round(plan[g] + usable.get(g, 0.0), 1)
            left[g] = c[i].number_input(f"{GL[g]} left (of {avail} kg)", 0.0, float(max(avail, 0.0)), step=0.1,
                                        key=f"co_left_{g}{k}")
            so[g] = c[i].checkbox("Ran out", key=f"co_so_{g}{k}")
        who = st.text_input("Recorded by", S.profile().get("approver", ""), key=f"co_by{k}")
        notes = st.text_area("Notes (optional)", key=f"co_notes{k}")
        go = st.form_submit_button("Save the close-out", type="primary", use_container_width=True)
    if go:
        if not covers:
            st.error("Enter the actual number of covers.")
            return
        if not who.strip():
            st.error("Enter who recorded the close-out.")
            return
        new_run, summary = core.close_out(run, S.profile(), int(covers), left, so, plate or 0.0, gs, who.strip(), notes)
        store, hid = S.get_store(), S.hotel()["id"]
        store.save_day(hid, date, status="closed", run=new_run, closeout=summary)
        store.log(hid, who.strip(), "service_closed_out", {"service_date": date, "covers": summary["actual_covers"],
                                                           "waste_kg": summary["waste_kg"], "stockouts": summary["stockouts"]})
        S.invalidate()
        st.session_state.pop("co_date", None)
        st.session_state.co_last = date
        st.rerun()
    last = st.session_state.get("co_last")
    done = next((d for d in closed if d["service_date"] == last), None)
    if done:
        show_result(done)


def show_result(day):
    c = day["closeout"]
    st.markdown(f"**Result for {day['service_date']}**")
    k = st.columns(4)
    k[0].metric("Covers", c["actual_covers"], f"predicted {c['predicted_covers']}" if c.get("predicted_covers") else None,
                delta_color="off")
    k[1].metric("Waste recorded", f"{c['waste_kg']:.1f} kg")
    k[2].metric("Standing par, same service (estimate)", f"{c['standing_plan_waste_estimate_kg']:.1f} kg",
                "lower bound: an item ran out" if c.get("estimate_is_lower_bound") else None, delta_color="off")
    k[3].metric("Forecast error", f"{c['forecast_ape']:.1%}" if c.get("forecast_ape") is not None else "—")
    if c["stockouts"]:
        st.warning("Ran out: " + ", ".join(GL[g] for g in c["stockouts"]))
    st.caption("The standing-par figure is an estimate: the kitchen's usual par served against today's measured "
               "consumption. Waste recorded is what the kitchen weighed.")


page()
site.app_footer()
