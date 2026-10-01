import plotly.graph_objects as go
import streamlit as st
from control_room import ui

W = ui.WB; E = W["economics"]; WC = W["waste_cost"]; CASES = W["sensitivity_cases"]

ui.header("08", "Business value", "Is it worth it, net of the AI's own cost?",
          "The economics from the case-study workbook, recalculated live with the same formulas. Food cost avoided is avoided cost, not new revenue.")
ui.banner("<b>Modeled economics.</b> Scenario drivers and cost lines are illustrative assumptions from the workbook; edit them to test the case.")

steps = W["waste_cost_steps"]
fig = go.Figure(go.Waterfall(x=[s["step"] for s in steps], y=[s["amount"] for s in steps],
                             measure=["absolute"] + ["relative"] * (len(steps) - 2) + ["total"], connector=dict(line=dict(color=ui.LINE)),
                             decreasing=dict(marker_color=ui.MOSS), totals=dict(marker_color=ui.FOREST), increasing=dict(marker_color=ui.ALERT),
                             text=[ui.usd(abs(s["amount"])) for s in steps], textposition="outside"))
fig.update_layout(title=f"Annual waste cost: {ui.usd(WC['baseline'])} → {ui.usd(steps[-1]['amount'])} ({WC['reduction']:.1%} lower)", height=340, yaxis_tickprefix="$")
st.plotly_chart(fig, use_container_width=True)

st.markdown("#### Value calculator " + ui.tag("WORKBOOK") + ui.tag("ASSUMPTION"), unsafe_allow_html=True)
KEYS = ("waste_reduction", "adoption", "cost_multiplier", "volume_index")
def load(name):
    c = CASES[name]
    st.session_state.update({"wr": round(c["waste_reduction"] * 100, 1), "ad": round(c["adoption"] * 100), "cm": float(c["cost_multiplier"]), "vi": float(c["volume_index"])})
if "wr" not in st.session_state: load("Base")
b = st.columns([1, 1, 1, 3])
for col, n in zip(b, CASES): col.button(n, on_click=load, args=(n,), use_container_width=True)

l, r = st.columns([1, 1.3])
with l:
    wr = st.slider("Waste reduction (%)", 0.0, 50.0, step=0.1, key="wr") / 100
    ad = st.slider("Adoption rate (%)", 50, 100, key="ad") / 100
    cm = st.slider("AI operating-cost multiplier (×)", 0.5, 2.0, step=0.05, key="cm")
    vi = st.slider("Food purchasing volume index (×)", 0.8, 1.2, step=0.05, key="vi")
    with st.expander("Cost lines and one-time investment"):
        lines = {k: st.number_input(k, 0, 100000, int(v), 500, key=f"cl_{k}") for k, v in E["cost_lines"].items()}
        one = {k: st.number_input(k, 0, 200000, int(v), 1000, key=f"ot_{k}") for k, v in E["one_time_lines"].items()}
# Workbook formulas (Sensitivity!B8:D13 and Economics!B3:B27)
food = WC["baseline"] * vi * wr * ad
coord = E["coordination_value"] * ad
gross = food + coord
ai_cost = sum(lines.values()) * cm
one_time = sum(one.values())
net = gross - ai_cost
payback = one_time / (net / 12) if net > 0 else float("nan")
with r:
    k = st.columns(2)
    k[0].metric("Gross annual benefit", ui.usd(gross)); k[1].metric("Annual AI operating cost", ui.usd(ai_cost))
    k = st.columns(2)
    k[0].metric("Net annual benefit", ui.usd(net)); k[1].metric("Payback on one-time cost", "never" if net <= 0 else f"{payback:.1f} months", f"one-time {ui.usd(one_time)}", delta_color="off")
    fig = go.Figure(go.Bar(x=["Food cost avoided", "Coordination capacity", "AI operating cost", "Net annual benefit"], y=[food, coord, -ai_cost, net],
                           marker_color=[ui.MOSS, ui.SAGE, ui.ALERT, ui.FOREST], text=[ui.usd(v) for v in (food, coord, -ai_cost, net)], textposition="outside"))
    fig.update_layout(height=300, yaxis_tickprefix="$", title="Annual value, net of the AI's own cost")
    st.plotly_chart(fig, use_container_width=True)
base = CASES["Base"]
st.caption(f"Check: the workbook's Base case gives net {ui.usd(base['net_annual'])} and payback {base['payback_months']:.1f} months; "
           "with the Base preset and default cost lines this calculator reproduces those values. Coordination capacity is redeployed manager time, not a cash saving.")

ui.why(f"In the full modeled pilot, {ui.usd(E['food_cost_avoided'])} of annual food cost is avoided against {ui.usd(E['annual_ai_cost'])} of annual AI operating cost; "
       f"even the Conservative case pays back in {CASES['Conservative']['payback_months']:.0f} months.",
       "The case depends mostly on waste reduction and adoption, not on AI costs.",
       "The value case should be tested at conservative assumptions, not sold at the upside.",
       "Fund a bounded pilot; scale only if waste reduction and adoption hold, as measured by the readiness gate.")
ui.footer()
