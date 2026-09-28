import plotly.graph_objects as go
import streamlit as st
from control_room import sim, ui

W = ui.WB
g, level, why_lvl = sim.gate(sim.evidence_for())
ww = W["weekly_waste"]; mape = W["forecast_mape"]; eco = W["economics"]; guest = W["guest"]
base_avg = sum(x["kg"] for x in ww if x["phase"] == "Baseline") / 4; last4 = sum(x["kg"] for x in ww[-4:]) / 4

ui.header("01", "Mission control", "Can AI make hospitality waste less, without costing guests or profit?",
          "A governed, closed-loop multi-agent system for hotel food waste. This control room runs the real simulation code behind the case study.", image="band_control.jpg")
ui.banner()
st.markdown("### Try the system yourself")
st.write(
    "Step into the role of the hotel operator. Run a service scenario, "
    "review the agents' recommendations, and make the final decision yourself."
)

if st.button("Run the system →", type="primary", use_container_width=True):
    st.switch_page("control_room/views/02_live_service.py")

st.caption("About 60 seconds · No setup required · Uses modeled scenario data")
st.markdown("#### Modeled 12-week pilot " + ui.tag("WORKBOOK"), unsafe_allow_html=True)
k = st.columns(5)
k[0].metric("Food waste", f"{last4:.0f} kg/wk", f"{(last4/base_avg-1)*100:.1f}% vs {base_avg:.0f} baseline", delta_color="inverse")
k[1].metric("Forecast error (MAPE)", ui.pct(mape[-1]["mape"], 1), f"from {ui.pct(sum(x['mape'] for x in mape[:4])/4, 1)} baseline", delta_color="off")
k[2].metric("Guest F&B score", f"{guest[-1]['guest_score']:.2f}", "floor 4.60 held every week", delta_color="off")
k[3].metric("Waste cost avoided", ui.usd(eco["food_cost_avoided"]), "per year", delta_color="off")
k[4].metric("Payback", f"{eco['payback_months']:.1f} months", f"net {ui.usd(eco['net_annual'])}/yr after AI costs", delta_color="off")

c1, c2 = st.columns([1.35, 1])
with c1:
    fig = go.Figure(go.Bar(x=[x["week"] for x in ww], y=[x["kg"] for x in ww], marker_color=[ui.GRAY if x["phase"] == "Baseline" else ui.FOREST for x in ww],
                           text=[x["kg"] for x in ww], textposition="outside", hovertemplate="%{x}: %{y} kg<extra></extra>"))
    fig.add_hline(y=base_avg, line_dash="dot", line_color=ui.SAND, annotation_text=f"baseline avg {base_avg:.0f} kg", annotation_position="top right")
    fig.update_layout(title="Weekly food waste: 4 baseline weeks, then 8 weeks with agents", height=330, yaxis_title="kg per week")
    st.plotly_chart(fig, use_container_width=True)
with c2:
    ws = [x for x in W["waste_by_source"] if x["source"] != "Total"]
    fig = go.Figure()
    fig.add_bar(name="Baseline", y=[x["source"] for x in ws], x=[x["baseline"] for x in ws], orientation="h", marker_color=ui.GRAY)
    fig.add_bar(name="With agents", y=[x["source"] for x in ws], x=[x["with_agents"] for x in ws], orientation="h", marker_color=ui.FOREST,
                text=[f"{x['change']*100:+.0f}%" if x["change"] else "0%" for x in ws], textposition="outside")
    fig.update_layout(title="Where the waste came from (kg/week)", barmode="group", height=330, yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("#### The system right now " + ui.tag("LIVE SIMULATION"), unsafe_allow_html=True)
s = st.columns([1, 1, 2])
with s[0]: ui.card("Readiness gate · week A8", f"{ui.pill(g['result'], 'ok' if g['result'] == 'PASS' else 'hold')} &nbsp; first blocker: {g['first_blocker']}")
with s[1]: ui.card("Autonomy level", f"{ui.pill(level, 'ok' if level == 'DELEGATED' else 'warn')}")
with s[2]: ui.card("What that means", ui.e(why_lvl[0]))
st.write("")
ui.flow(["Hotel data", "Context", "4 specialist agents", "Orchestrator", "Governance", "Human approval", "Action", "Outcome", "AgentOps", "Readiness gate"])
st.caption("Every material decision follows this loop. Try it yourself in **Live Service: You Decide**, or break it on purpose in **Scenario Lab** and **Failure Lab**.")

ui.why("Waste fell 37.8% in the modeled pilot while the guest score stayed above its 4.60 floor, and forecast error fell by more than half.",
       "The problem was never a lack of data; it was disconnected decisions across forecasting, inventory, production and waste.",
       "An agent system only earns trust if every decision is governed, traceable and reversible, with humans deciding what matters.",
       "Four specialist agents, one orchestrator, explicit decision rights and a readiness gate that controls autonomy.")
ui.footer()
