import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from control_room import ui

W = ui.WB; ao = W["agentops_weekly"]; wk = [a["week"] for a in ao]

ui.header("07", "AgentOps & learning", "Operating an agent system means measuring it like a team member",
          "Quality, safety, reliability and business value, tracked every week, with every human override turned into a system improvement.")
ui.banner()

st.markdown("#### Control room KPIs, week A8 " + ui.tag("WORKBOOK"), unsafe_allow_html=True)
cats = ["QUALITY", "SAFETY", "RELIABILITY", "BUSINESS"]
cols = st.columns(4)
for col, cat in zip(cols, cats):
    with col:
        st.markdown(f"**{cat.title()}**")
        for k in [x for x in W["control_room"] if x["category"] == cat]:
            v = k["value"]
            txt = (ui.usd(v) if v > 1000 else (f"{v:.2f}" if v > 1.5 or k["kpi"].startswith("Guest") else ("0" if v == 0 else f"{v:.1%}"))) if isinstance(v, (int, float)) else v
            if "Hours" in k["kpi"]: txt = f"{v:.1f} h"
            tgt = f"{k['test']} {k['target']:.0%}" if isinstance(k["target"], float) and k["target"] < 1.5 else (f"{k['test']} {k['target']}" if k["target"] not in (None, "") else "outcome")
            st.metric(k["kpi"], txt, tgt, delta_color="off")

c1, c2 = st.columns(2)
with c1:
    fig = go.Figure()
    fig.add_scatter(x=wk, y=[a["acceptance"] for a in ao], name="Recommendation acceptance", mode="lines+markers", line=dict(color=ui.FOREST, width=2))
    fig.add_scatter(x=wk, y=[a["recall"] for a in ao], name="Escalation recall", mode="lines+markers", line=dict(color=ui.MOSS, width=2))
    fig.add_scatter(x=wk, y=[a["override_rate"] for a in ao], name="Human override rate", mode="lines+markers", line=dict(color=ui.SAND, width=2))
    fig.update_layout(title="Trust indicators by pilot week", height=340, yaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)
with c2:
    fig = go.Figure(go.Bar(x=wk, y=[a["recommendations"] for a in ao], marker_color=ui.SAGE, name="Recommendations",
                           text=[a["recommendations"] for a in ao], textposition="outside"))
    fig.add_bar(x=wk, y=[a["accepted"] for a in ao], marker_color=ui.FOREST, name="Accepted")
    fig.update_layout(title="Recommendations and acceptances per week", barmode="overlay", height=340)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("#### Every override is a lesson " + ui.tag("WORKBOOK"), unsafe_allow_html=True)
ov = W["overrides"]
l, r = st.columns([1, 1.25])
with l:
    fig = go.Figure(go.Bar(y=[o["reason"] for o in ov], x=[o["count"] for o in ov], orientation="h", marker_color=ui.FOREST,
                           text=[f"{o['count']} · {o['share']:.0%}" for o in ov], textposition="outside"))
    fig.update_layout(title=f"Why managers overrode the AI ({sum(o['count'] for o in ov)} overrides, A1-A8)", height=340, yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)
with r:
    st.markdown('<table class="cr-table"><tr><th>Override reason</th><th>System improvement</th></tr>' + "".join(
        f"<tr><td><b>{ui.e(o['reason'])}</b></td><td>{ui.e(o['improvement'])}</td></tr>" for o in ov) + "</table>", unsafe_allow_html=True)
    st.caption("The reason split is a modeled diagnostic tagging of the pilot overrides (illustrative). Improvements are evaluated before any change; nothing retrains automatically.")

ch = W["coordination_hours"]
fig = go.Figure(go.Bar(x=[c["week"] for c in ch], y=[c["hours"] for c in ch], marker_color=[ui.GRAY] + [ui.MOSS] * (len(ch) - 1), text=[c["hours"] for c in ch], textposition="outside"))
fig.update_layout(title="Manager coordination hours per week", height=280, yaxis_title="hours")
st.plotly_chart(fig, use_container_width=True)

ui.why(f"Acceptance rose from {ao[0]['acceptance']:.0%} to {ao[-1]['acceptance']:.0%} and overrides fell from {ao[0]['override_rate']:.0%} to {ao[-1]['override_rate']:.0%} over eight modeled weeks; missing context was the top override reason.",
       "Overrides are the richest signal an agent system produces: they show exactly where the model lacks context.",
       "Tracking quality, safety and reliability together keeps efficiency gains from hiding risk.",
       "Close the loop: override → root cause → proposed improvement → evaluate → change.")
ui.footer()
