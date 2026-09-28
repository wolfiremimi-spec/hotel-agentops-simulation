import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from control_room import ui
from hotel_agentops_sim.agentops import MIN_SAMPLE
from product import app_state as S
from product import core


def fmt(key, v):
    if v is None:
        return "—"
    if key == "guest_fb_score":
        return f"{v:.2f}"
    if key == "policy_violations":
        return f"{v:.0f}"
    return f"{v:.1%}"


def page():
    ui.header("HOTEL AGENTOPS", "Performance & autonomy", "Autonomy is earned from your own results",
              f"The readiness gate uses this hotel's last {core.EVIDENCE_WINDOW_DAYS} days of decisions and close-outs. "
              "All eight checks must pass before any action runs without a manager. No single strong metric grants authority.")
    perf = S.performance_for(S.today())
    lvl = perf["autonomy"]
    st.markdown(f'<div class="ha-level"><b>Current autonomy: {ui.e(lvl)}</b><br>{ui.e(" · ".join(perf["autonomy_why"]))}</div>',
                unsafe_allow_html=True)
    ladder = st.columns(3)
    for col, (name, desc) in zip(ladder, [("BOUNDED", "Recommend only. Set when guests, policy or override drift raise a flag."),
                                          ("SUPERVISED", "Every action needs a manager. The starting level for a new hotel."),
                                          ("DELEGATED", "Low-risk, reversible actions may run alone. Needs all eight checks to pass.")]):
        with col:
            with st.container(border=True):
                st.markdown(f"{ui.pill(name, 'ok' if name == lvl else 'neutral')}", unsafe_allow_html=True)
                st.caption(desc)

    if perf["gaps"]:
        st.markdown("**Evidence still needed before the gate can be evaluated**")
        c = st.columns(2)
        c[0].progress(min(perf["decided"] / MIN_SAMPLE, 1.0), text=f"Manager decisions: {perf['decided']}/{MIN_SAMPLE}")
        n_closed = sum(1 for d in S.days() if d.get("closeout") and d["closeout"].get("forecast_ape") is not None
                       and d["service_date"] >= perf["window_start"])
        c[1].progress(min(n_closed / core.MIN_CLOSEOUTS, 1.0),
                      text=f"Closed-out services with a forecast: {n_closed}/{core.MIN_CLOSEOUTS}")

    st.markdown("**Readiness gate: this hotel's evidence**")
    st.dataframe(pd.DataFrame([{"Check": c["metric"], "This hotel": fmt(c["key"], c["value"]),
                                "Required": f"{c['test']} {fmt(c['key'], c['threshold'])}",
                                "Result": "—" if c["pass"] is None else ("PASS" if c["pass"] else "FAIL")}
                               for c in perf["gate"]["checks"]]), use_container_width=True, hide_index=True)
    st.caption(f"Gate: {perf['gate']['result']} · first blocker: {perf['gate']['first_blocker']}. Escalation recall and "
               "precision are scored against your hotel's escalation policy (which decision types must reach a person).")

    closed = [d for d in S.days() if d.get("closeout")]
    if not closed:
        st.info("Close out services to see waste, forecast accuracy and savings here.")
    else:
        tot_w = sum(d["closeout"]["waste_kg"] for d in closed)
        tot_e = sum(d["closeout"]["standing_plan_waste_estimate_kg"] for d in closed)
        cost = float(S.profile()["waste_cost_per_kg"])
        apes = [d["closeout"]["forecast_ape"] for d in closed if d["closeout"].get("forecast_ape") is not None]
        k = st.columns(4)
        k[0].metric("Services closed out", len(closed))
        k[1].metric("Waste recorded", f"{tot_w:.1f} kg")
        k[2].metric("Waste avoided vs standing par (estimate)", f"{tot_e - tot_w:.1f} kg", f"≈ ${(tot_e - tot_w) * cost:,.0f}",
                    delta_color="off")
        k[3].metric("Average forecast error", f"{sum(apes) / len(apes):.1%}" if apes else "—")
        x = [d["service_date"] for d in closed]
        fig = go.Figure()
        fig.add_bar(name="Standing par (estimate)", x=x, y=[d["closeout"]["standing_plan_waste_estimate_kg"] for d in closed],
                    marker_color=ui.GRAY)
        fig.add_bar(name="Recorded waste", x=x, y=[d["closeout"]["waste_kg"] for d in closed], marker_color=ui.FOREST)
        fig.update_layout(title="Waste per service (kg)", barmode="group", height=320, yaxis_title="kg")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Recorded waste is weighed by the kitchen. The standing-par bar is an estimate, and a lower bound on "
                   "days an item ran out.")
        so = [d for d in closed if d["closeout"]["stockouts"]]
        if so:
            st.warning(f"{len(so)} of {len(closed)} closed services had a stockout. Guest experience outranks waste: "
                       "review these with the chef.")

    if perf["weekly_override_rates"]:
        st.markdown("**Human override rate by week** (drift rule: this week > 1.5 × the trailing 3-week average reduces autonomy)")
        st.dataframe(pd.DataFrame({"Week": list(range(1, len(perf["weekly_override_rates"]) + 1)),
                                   "Override rate": [f"{r:.0%}" for r in perf["weekly_override_rates"]]}),
                     hide_index=True)


page()
ui.footer("Hotel AgentOps pilot application.")
