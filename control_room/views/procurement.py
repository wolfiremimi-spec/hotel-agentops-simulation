import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from control_room import ui
from product import core, ordering

APP_URL = "https://hotel-agentops.streamlit.app"
GL = core.GROUP_LABEL
PATTERN = {"stockout_prone": ("RAN OUT", "hold"), "chronic_overproduction": ("OFTEN LEFT OVER", "warn"), "normal": ("STEADY", "ok")}
CHOICES = ["Approve", "Modify", "Reject", "Request more context"]

ui.header("05", "Procurement", "Next week's order: buy less of what's left over, more of what runs out",
          "The Procurement Agent turns the hotel's recorded services into next week's supplier order per item group. "
          "Purchasing is a manager decision in the case study's decision rights, so nothing is ordered until you decide.")
ui.banner()
ui.flow(["Close-outs", "Waste & stockout patterns", "Procurement Agent", "Governance", "Your decision", "Supplier order"],
        active="Procurement Agent")

p = core.demo_profile()
ev = ordering.evidence(p, [])
start = ordering.next_monday(p["demo_anchor_date"])
dates = ordering.week_dates(start)
base = {c["date"]: c["expected_covers"] for c in ordering.default_covers(ev, dates)}

# ---------------------------------------------------------------- 1 · the week
st.markdown("#### 1 · Next week's expected covers " + ui.tag("MODELED SIMULATION"), unsafe_allow_html=True)
PRESETS = {
    "Case-study week": lambda d, c: c,
    "Quiet week (weekdays −25%)": lambda d, c: round(c * (0.75 if core.weekday(d) not in ("Saturday", "Sunday") else 1)),
    "Conference midweek (Tue–Thu +30%)": lambda d, c: round(c * (1.3 if core.weekday(d) in ("Tuesday", "Wednesday", "Thursday") else 1)),
}
st.session_state.setdefault("pr_preset", "Case-study week")
st.session_state.setdefault("pr_v", 0)
b = st.columns(len(PRESETS) + 1)
for col, name in zip(b, PRESETS):
    if col.button(name, use_container_width=True, type="primary" if st.session_state.pr_preset == name else "secondary",
                  key=f"pr_p_{name}"):
        st.session_state.pr_preset = name
        st.session_state.pr_v += 1
        st.session_state.pop("pr_decision", None)
        st.rerun()
preset = PRESETS[st.session_state.pr_preset]
frame = pd.DataFrame([{"Date": d, "Day": core.weekday(d), "Expected covers": float(preset(d, base[d]))} for d in dates])
cov = st.data_editor(frame, hide_index=True, use_container_width=True, disabled=["Date", "Day"],
                     key=f"pr_cov_{st.session_state.pr_v}",
                     column_config={"Expected covers": st.column_config.NumberColumn(min_value=0, max_value=5000, step=1)})
st.caption("The case study records Saturday services only, so every day starts from the Saturday average (382 covers). "
           "Use a preset or edit any day.")
covers = [{"date": r["Date"], "day": r["Day"], "expected_covers": int(r["Expected covers"] or 0)} for r in cov.to_dict("records")]

# ---------------------------------------------------------------- 2 · evidence + policy
st.markdown("#### 2 · What the agent learned from the hotel's services " + ui.tag("MODELED SIMULATION"), unsafe_allow_html=True)
c = st.columns(4)
for i, g in enumerate(core.GROUPS):
    cls, why = ordering.classify(ev, g)
    with c[i]:
        with st.container(border=True):
            st.markdown(f"{ui.pill(PATTERN[cls][0], PATTERN[cls][1])}&nbsp; <b>{ui.e(GL[g])}</b>", unsafe_allow_html=True)
            st.caption(why)

with st.expander("Policy what-if: safety buffers (the guardrails the agent orders within)"):
    s = st.columns(3)
    buffers = {
        "stockout_prone": s[0].slider("Where guests ran short (%)", 2, 15, int(ordering.BUFFER["stockout_prone"] * 100), key="pr_b1") / 100,
        "normal": s[1].slider("Steady groups (%)", 2, 15, int(ordering.BUFFER["normal"] * 100), key="pr_b2") / 100,
        "chronic_overproduction": s[2].slider("Often left over (%)", 2, 15, int(ordering.BUFFER["chronic_overproduction"] * 100),
                                              key="pr_b3") / 100,
    }
    st.caption("Same 2–15% range the morning Production Agent works within. A bigger buffer protects guests and buys more.")

rec = ordering.recommend(p, ev, covers, {}, buffers)
lines = rec["lines"]
cost = float(p["waste_cost_per_kg"])

# ---------------------------------------------------------------- 3 · recommendation
st.markdown("#### 3 · The Procurement Agent's recommendation", unsafe_allow_html=True)
total_s = sum(l["suggested_kg"] for l in lines.values())
total_p = sum(l["standing_par_kg"] for l in lines.values())
k = st.columns(4)
k[0].metric("Expected covers", f"{rec['total_covers']:,}")
k[1].metric("Suggested order", f"{total_s:,.0f} kg", f"{total_s - total_p:+,.0f} kg vs standing par", delta_color="inverse")
k[2].metric("Potential waste avoided", f"{rec['waste_avoided_estimate_kg']:,.0f} kg", "estimate", delta_color="off")
k[3].metric("Potential saving", ui.usd(rec["waste_avoided_estimate_kg"] * cost), f"at ${cost:.2f}/kg · estimate", delta_color="off")
ui.card("Procurement Agent · rule-based", ui.e(ordering.rule_explanation(rec)))

fig = go.Figure()
x = [GL[g] for g in core.GROUPS]
fig.add_bar(name="Standing par order", x=x, y=[lines[g]["standing_par_kg"] for g in core.GROUPS], marker_color=ui.GRAY,
            text=[f"{lines[g]['standing_par_kg']:.0f}" for g in core.GROUPS], textposition="outside")
fig.add_bar(name="Suggested order", x=x, y=[lines[g]["suggested_kg"] for g in core.GROUPS], marker_color=ui.FOREST,
            text=[f"{lines[g]['suggested_kg']:.0f}" for g in core.GROUPS], textposition="outside")
fig.add_scatter(name="Expected use", x=x, y=[lines[g]["expected_use_kg"] for g in core.GROUPS], mode="markers",
                marker=dict(symbol="line-ew-open", size=46, color=ui.SAND, line=dict(width=3)))
fig.update_layout(title="Next week's order by item group (kg)", barmode="group", height=360, yaxis_title="kg")
st.plotly_chart(fig, use_container_width=True)
st.dataframe(pd.DataFrame([{"Item group": l["label"], "Pattern": PATTERN[l["pattern"]][0].title(), "Why": l["why"],
                            "Expected use (kg)": l["expected_use_kg"], "Buffer": f"{l['buffer']:.0%}",
                            "Standing par (kg)": l["standing_par_kg"], "Suggested (kg)": l["suggested_kg"],
                            "Difference (kg)": l["difference_kg"]} for l in lines.values()]),
             hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- 4 · governance + decision
st.markdown("#### 4 · Governance and your decision", unsafe_allow_html=True)
below_par = [g for g in core.GROUPS if lines[g]["difference_kg"] > 0]
st.markdown('<div class="cr-trace">' + ui.e("\n".join([
    "DECISION TYPE  purchasing_adjustment (supplier order for the week of " + start + ")",
    "RISK           MEDIUM · reversible before the supplier's cut-off",
    "RULE           Purchasing changes always reach a person (case-study decision rights)",
    "GUARDRAIL      Order ≥ expected use for every group; stockout-prone groups carry ≥ 12% buffer by default",
    "AUTHORITY      Human decision required → F&B Manager",
    "AI LIMIT       An AI agent may raise an order for guest safety, never cut one (verified before it counts)",
])) + "</div>", unsafe_allow_html=True)

choice = st.radio("Your decision", CHOICES, index=None, horizontal=True, key=f"pr_choice_{st.session_state.pr_v}")
final = {g: lines[g]["suggested_kg"] for g in core.GROUPS}
reason = ""
if choice == "Modify":
    m = st.columns(4)
    final = {g: m[i].number_input(f"{GL[g]} (kg)", 0.0, 10000.0, float(lines[g]["suggested_kg"]), 1.0,
                                  key=f"pr_mod_{g}_{st.session_state.pr_v}") for i, g in enumerate(core.GROUPS)}
    short = [g for g in core.GROUPS if final[g] < lines[g]["expected_use_kg"] - 0.05]
    if short:
        st.warning("Below expected use (stockout risk for guests): " + ", ".join(GL[g] for g in short))
if choice in ("Modify", "Reject", "Request more context"):
    reason = st.text_input("Reason (required: overrides become learning cases)", key=f"pr_reason_{st.session_state.pr_v}",
                           placeholder="e.g. supplier minimum order, a conference booked on Wednesday")
if st.button("Record decision", type="primary", disabled=choice is None, key="pr_record"):
    if choice != "Approve" and not reason.strip():
        st.error("Give a reason. Every override is recorded and reviewed.")
    else:
        st.session_state.pr_decision = {"choice": choice, "reason": reason.strip(), "final": final,
                                        "at": dt.datetime.now().strftime("%H:%M:%S")}

d = st.session_state.get("pr_decision")
if d:
    status = {"Approve": "EXECUTED · order sent as suggested", "Modify": "EXECUTED · order sent with your changes",
              "Reject": "NOT EXECUTED · standing par order stands", "Request more context": "ON HOLD · manager asked the agent for more context"}
    rows = [f"HUMAN          {d['choice'].upper()} by F&B Manager at {d['at']}" + (f" · reason: {d['reason']}" if d["reason"] else ""),
            f"ACTION         {status[d['choice']]}"]
    if d["choice"] in ("Approve", "Modify"):
        rows.append("ORDER          " + " · ".join(f"{GL[g]} {d['final'][g]:.0f} kg" for g in core.GROUPS))
        saved = sum(lines[g]["standing_par_kg"] - d["final"][g] for g in core.GROUPS)
        rows.append(f"VS PAR         {saved:+.0f} kg less bought than standing par (estimate)")
    if d["choice"] != "Approve":
        rows.append("LEARNING       Override logged as a learning case for human review (nothing retrains automatically)")
    st.markdown('<div class="cr-trace">' + ui.e("\n".join(rows)) + "</div>", unsafe_allow_html=True)

src = {x["source"]: x["baseline"] for x in ui.WB["waste_by_source"]}
# ---------------------------------------------------------------- 5 · close the loop
if d and d["choice"] in ("Approve", "Modify"):
    st.markdown("#### 5 · Run the week: did the order fit? " + ui.tag("MODELED SIMULATION"), unsafe_allow_html=True)
    st.caption("Enter how many guests actually came. Usage is modeled as actual covers × the case study's consumption per "
               "cover. In the pilot app this comes from each day's close-out instead.")
    wk = pd.DataFrame([{"Date": c_["date"], "Day": c_["day"], "Expected": c_["expected_covers"],
                        "Actual covers": float(c_["expected_covers"])} for c_ in covers])
    wk = st.data_editor(wk, hide_index=True, use_container_width=True, disabled=["Date", "Day", "Expected"],
                        key=f"pr_week_{st.session_state.pr_v}_{d['at']}",
                        column_config={"Actual covers": st.column_config.NumberColumn(min_value=0, max_value=5000, step=1)})
    actual = int(wk["Actual covers"].fillna(0).sum())
    used = {g: actual * ev["per_cover"][g] for g in core.GROUPS}
    order = {"week_start": start, "lines": {g: {"ordered_kg": d["final"][g], "standing_par_kg": lines[g]["standing_par_kg"]}
                                            for g in core.GROUPS}}
    res = ordering.accuracy(order, used, 7)
    m = st.columns(3)
    m[0].metric("Order accuracy", "—" if res["accuracy"] is None else f"{res['accuracy']:.0%}", "1 − |ordered − used| ÷ used",
                delta_color="off")
    m[1].metric("Bought beyond use", f"{res['surplus_kg']:.0f} kg", f"standing par: {res['par_surplus_kg']:.0f} kg",
                delta_color="off")
    m[2].metric("Actual vs expected covers", f"{actual:,}", f"{actual - rec['total_covers']:+,}", delta_color="off")
    st.dataframe(pd.DataFrame([{"Item group": l["label"], "Ordered (kg)": l["ordered_kg"], "Used (kg)": l["used_kg"],
                                "Surplus (+) / short (−) kg": l["surplus_kg"], "Standing par (kg)": l["standing_par_kg"],
                                "Result": "Short" if l["short"] else "Covered"} for l in res["lines"].values()]),
                 hide_index=True, use_container_width=True)
    learn = dict(ev, last_order=res)
    shifts = [(GL[g], ordering.classify(learn, g)) for g in core.GROUPS if res["lines"][g]["short"]]
    if shifts:
        st.markdown('<div class="cr-trace">' + ui.e("\n".join(
            [f"LEARNING       {n}: {why} → next week's order gets the stockout-prone buffer" for n, (_, why) in shifts]))
            + "</div>", unsafe_allow_html=True)
    else:
        st.caption("Every group was covered, so next week's suggestion keeps its patterns. Try more guests than expected to "
                   "see the agent learn from a shortfall.")

ui.why(f"Overproduction is the largest waste source in the workbook ({src['Overproduction']} of {src['Total']} kg at baseline). "
       f"On the recorded Saturdays pastry averaged {ev['avg_leftover_pct']['pastry_bread']:.0f}% left over, while the hot line "
       f"ran out in {ev['stockouts']['hot_line']} of {ev['services']}.",
       "A single par level can't fix both: it over-buys one group and under-buys the other.",
       "Order by pattern: trim what's chronically left over, add buffer where guests ran short.",
       "The agent recommends per group; a manager approves every order; the AI can only make orders safer.")
st.markdown(f"Use it with your own hotel's data: **[Next week's order in the pilot app ↗]({APP_URL})**")
ui.footer("Order figures are modeled from the case study's recorded Saturdays; savings are estimates.")
