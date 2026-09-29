import plotly.graph_objects as go
import streamlit as st
from control_room import sim, ui
from hotel_agentops_sim.agentops import GATE_ORDER

TH = sim.thresholds(sim.PARAMS); WEEKS = list(sim.PARAMS["gate_evidence_by_week"])
FMT = {"guest_fb_score": lambda v: f"{v:.2f}", "policy_violations": lambda v: f"{v:.0f}"}
fmt = lambda k, v: FMT.get(k, lambda x: f"{x:.1%}")(v)

ui.header("06", "Readiness gate & autonomy", "Autonomy is earned week by week, and one failed metric is enough to hold it",
          "Eight mandatory metrics. All must pass; there is no averaging. The first failure is the blocker, and the gate sets how much the agents may do alone.")
ui.banner()

st.markdown("#### The gate across the modeled pilot " + ui.tag("WORKBOOK"), unsafe_allow_html=True)
st.caption("Green = passes its threshold · red = fails. Column headers show each week's gate result.")
z, text = [], []
for key, label in GATE_ORDER:
    row, trow = [], []
    for w in WEEKS:
        ev = sim.evidence_for(w); t, op = TH[key]
        ok = {">=": ev[key] >= t, "<=": ev[key] <= t, "==": ev[key] == t}[op]
        row.append(1 if ok else 0); trow.append(fmt(key, ev[key]))
    z.append(row); text.append(trow)
fig = go.Figure(go.Heatmap(z=z, x=WEEKS, y=[l for _, l in GATE_ORDER], text=text, texttemplate="%{text}", colorscale=[[0, "#E9C9C3"], [1, "#CFE0D4"]],
                           showscale=False, xgap=3, ygap=3, hovertemplate="%{y} · %{x}: %{text}<extra></extra>"))
res_row = [sim.gate(sim.evidence_for(w))[0] for w in WEEKS]
fig.update_layout(height=400, margin=dict(t=40), yaxis=dict(autorange="reversed"),
                  xaxis=dict(side="top", tickvals=WEEKS, ticktext=[f"{w}<br>{g['result']}" for w, g in zip(WEEKS, res_row)]))
st.plotly_chart(fig, use_container_width=True)
st.caption("First blockers by week: " + " · ".join(f"{w}: {g['first_blocker']}" for w, g in zip(WEEKS, res_row)))

st.markdown("#### What-if: set the evidence yourself " + ui.tag("LIVE SIMULATION"), unsafe_allow_html=True)
start = st.selectbox("Start from week", WEEKS, index=len(WEEKS) - 1)
ev0 = sim.evidence_for(start)
left, right = st.columns([1, 1.1])
ev = {"week": f"{start} (what-if)"}
with left:
    for key, label in GATE_ORDER:
        t, op = TH[key]
        if key == "guest_fb_score":
            ev[key] = st.slider(f"{label} ({op} {t:.2f})", 4.3, 4.9, float(round(ev0[key], 2)), 0.01, key=f"g_{start}_{key}")
        elif key == "policy_violations":
            ev[key] = st.slider(f"{label} ({op} {t:.0f})", 0, 3, int(ev0[key]), key=f"g_{start}_{key}")
        else:
            ev[key] = st.slider(f"{label} ({op} {t:.0%})", 0.0, 100.0, round(ev0[key] * 100, 1), 0.1, key=f"g_{start}_{key}") / 100
with right:
    g, level, why = sim.gate(ev)
    st.markdown(f"### {ui.pill('GATE ' + g['result'], 'ok' if g['result'] == 'PASS' else 'hold')} &nbsp; {ui.pill('AUTONOMY ' + level, 'ok' if level == 'DELEGATED' else ('warn' if level == 'SUPERVISED' else 'hold'))}",
                unsafe_allow_html=True)
    st.markdown(f"**First blocker:** {g['first_blocker']} · **Failed checks:** {g['failed']} of 8")
    for w in why: st.markdown(f"- {ui.e(w)}")
    st.markdown('<table class="cr-table"><tr><th>Metric</th><th>Value</th><th>Test</th><th>Result</th></tr>' + "".join(
        f"<tr><td>{c['metric']}</td><td>{fmt(c['key'], c['value'])}</td><td>{c['test']} {fmt(c['key'], c['threshold'])}</td><td>{ui.pill('pass', 'ok') if c['pass'] else ui.pill('fail', 'hold')}</td></tr>"
        for c in g["checks"]) + "</table>", unsafe_allow_html=True)
    res, _, _ = sim.run(evidence=ev)
    st.markdown("**Effect on today's service:**")
    for r in res.records:
        st.markdown(f"{ui.pill(r['Required Authority'], ui.authority_kind(r['Required Authority']))} &nbsp;{r['Decision ID']} · {sim.TYPE_LABEL.get(r['Decision Type'], r['Decision Type'])}",
                    unsafe_allow_html=True)

st.markdown("#### The autonomy ladder")
l = st.columns(3)
with l[0]: ui.card("BOUNDED", "Guest-score breach, policy violation or override drift. Agents may only recommend; humans review.")
with l[1]: ui.card("SUPERVISED", "Gate on HOLD for any other reason. No delegated execution; low-risk actions need a manager.")
with l[2]: ui.card("DELEGATED", "Gate PASS. Low-risk, reversible actions inside the delegated range may execute alone.", dark=True)

st.markdown("#### Drift watch: override rate")
hist = sim.PARAMS["override_rate_history"]
vals = [h["value"] for h in hist]; wk = [h["week"] for h in hist]
m, tw = sim.PARAMS["drift_rule"]["multiplier"], sim.PARAMS["drift_rule"]["trailing_weeks"]
limit = [None] * tw + [m * sum(vals[i - tw:i]) / tw for i in range(tw, len(vals))]
fig = go.Figure()
fig.add_scatter(x=wk, y=vals, mode="lines+markers", name="Override rate", line=dict(color=ui.FOREST, width=2), marker=dict(size=8))
fig.add_scatter(x=wk, y=limit, mode="lines", name=f"Drift limit ({m}× trailing {tw}-week average)", line=dict(color=ui.SAND, dash="dash"))
fig.update_layout(height=300, yaxis_tickformat=".0%", title="A rising override rate reduces autonomy and triggers an investigation")
st.plotly_chart(fig, use_container_width=True)

ui.why("In the modeled pilot the gate held for six weeks; in week A6 tool reliability alone kept it on HOLD while every other metric passed.",
       "Averaging would have hidden the weakest link. A hard gate forces the team to fix it.",
       "Autonomy becomes a managed business decision with evidence, not a switch someone flips.",
       "All eight metrics must pass; guest, policy and drift breaches reduce autonomy immediately.")
ui.footer()
