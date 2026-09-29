import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from control_room import sim, ui

ui.header(
    "02",
    "Live service: you decide",
    "You are the F&B manager. The agents recommend; you hold the authority.",
    "Saturday breakfast, 08:02. The system reads eight hotel data sources, four specialist agents reason, the orchestrator combines them, "
    "and governance decides which actions need you. Make your calls, then run the service and see what actually happened.",
)
ui.banner()

# ---------------------------------------------------------------------------
# Session state: workflow flags survive every Streamlit rerun
# ---------------------------------------------------------------------------
if "live_service_started" not in st.session_state:
    st.session_state.live_service_started = False

# ---------------------------------------------------------------------------
# 0 · Start screen
# ---------------------------------------------------------------------------
if not st.session_state.live_service_started:
    st.markdown("### Ready to run today's service?")
    st.write(
        "You're the F&B manager for Saturday breakfast. "
        "The agents will analyze hotel demand, reservations, inventory, "
        "waste, events, shelf life, and guest-experience signals before "
        "bringing you their recommendations."
    )

    st.info(
        "YOUR JOB: Review each recommendation that needs your authority and decide "
        "whether to approve, modify, reject, or ask for more context."
    )

    if st.button(
        "Start live service →",
        type="primary",
        use_container_width=True,
        key="start_live_service",
    ):
        st.session_state.live_service_started = True
        st.session_state.pop("live_choices", None)
        st.rerun()

    st.caption(
        "About 60 seconds · No setup required · Uses modeled scenario data"
    )

    ui.footer()
    st.stop()

# ---------------------------------------------------------------------------
# Pre-service analysis (decisions before any human choice)
# ---------------------------------------------------------------------------
pre, pre_log, pending = sim.run()
sec = sim.sections(pre_log)

st.success(
    "✓ Pre-service analysis ready — 8 hotel signals read · "
    "4 specialist agents analyzed the situation · "
    "Orchestrator resolved conflicts · Governance rules applied"
)

st.markdown(
    "**Review the analysis below, then make the decisions that will shape today's service.**"
)

# ---------------------------------------------------------------------------
# 1 · What the system sees
# ---------------------------------------------------------------------------
st.markdown("#### 1 · What the system sees " + ui.tag("LIVE SIMULATION"), unsafe_allow_html=True)
ctx = pre.context
cols = st.columns(4)
for i, s in enumerate(sim.SOURCES):
    stt = ctx.status[s]
    cols[i % 4].markdown(
        f"{ui.pill('OK' if stt == 'ok' else stt.upper(), 'ok' if stt == 'ok' else 'hold')} &nbsp;{sim.SOURCE_LABEL[s]}",
        unsafe_allow_html=True,
    )
st.caption(
    f"Context completeness {ctx.completeness:.0%} "
    f"(threshold {sim.PARAMS['context_completeness_threshold']['value']:.0%} for any delegated action)."
)

a1, a2 = st.columns([1.2, 1])
with a1:
    st.markdown("**Specialist agents** (each reads only what its role needs)")
    st.markdown(
        '<div class="cr-trace">' + ui.e("\n".join(l.strip() for l in sec["③"][1:])) + "</div>",
        unsafe_allow_html=True,
    )
with a2:
    st.markdown("**Orchestrator**")
    orch = " ".join(l.strip() for l in sec["④"]).replace("④ ORCHESTRATOR · ", "")
    ui.card("Conflict check", ui.e(orch), dark=True)

# ---------------------------------------------------------------------------
# 2 · Decisions awaiting you
# ---------------------------------------------------------------------------
delegated = [r for r in pre.records if r["Required Authority"].startswith("Agent executes")]
st.markdown("#### 2 · Decisions awaiting you")
if delegated:
    st.caption(
        "Handled without you (low risk, reversible, inside delegated limits): "
        + " · ".join(
            f"{r['Decision ID']} {sim.TYPE_LABEL.get(r['Decision Type'], r['Decision Type'])}"
            for r in delegated
        )
    )

CHOICE_MAP = {
    "Approve": "approve",
    "Modify": "modify",
    "Reject": "reject",
    "Request more context": "more_context",
}

choices = {}
missing_notes = []

for p in pending:
    wkey = f"{p.decision_id}_{p.decision_type}"
    with st.container(border=True):
        top = st.columns([3, 1])
        top[0].markdown(
            f"**{p.decision_id} · {sim.TYPE_LABEL.get(p.decision_type, p.decision_type)}**  \n{ui.e(p.recommendation)}"
        )
        top[1].markdown(ui.pill(p.authority, ui.authority_kind(p.authority)), unsafe_allow_html=True)

        m = st.columns(4)
        m[0].metric("Confidence", f"{p.confidence:.1%}")
        m[1].metric("Risk", p.risk)
        m[2].metric("Reversibility", p.reversibility)
        m[3].metric("Needs", "Manager" if "manager" in p.authority.lower() else "Human decision")

        st.markdown(
            f"**Why the AI recommends it:** {ui.e(p.reason)}  \n**Expected impact:** {ui.e(p.expected_impact)}"
        )

        if p.lines:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Item group": sim.GROUP_LABEL.get(l["group"], l["group"]),
                            "Expected need (kg)": l["expected_consumption_kg"],
                            "AI plan (kg)": l["planned_kg"],
                            "Standing plan (kg)": l["standing_plan_kg"],
                            "Change": f"{l['change']:+.0%}",
                            "Buffer": f"{l['buffer']:.0%}",
                        }
                        for l in p.lines
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("Governance rule trace: why this needs a human"):
            st.markdown(
                '<div class="cr-trace">' + ui.e("\n".join(p.rule_trace)) + "</div>",
                unsafe_allow_html=True,
            )

        c = st.columns([1.3, 1, 1.6])
        if p.modifiable:
            opts = ["Approve", "Modify", "Reject", "Request more context"]
        else:
            opts = ["Approve", "Reject", "Request more context"]

        pick = c[0].radio(
            "Your decision",
            opts,
            index=None,
            key=f"ch_{wkey}",
            horizontal=False,
        )

        if pick is None:
            c[1].caption("No decision yet: choose one to continue.")
            choices[p.decision_type] = {"choice": None}
            continue

        ch = {"choice": CHOICE_MAP[pick]}
        if pick == "Modify":
            ch["new_change_pct"] = c[1].number_input(
                "New change vs standing plan (%)"
                if p.decision_type == "production_adjustment"
                else "New change vs current order (%)",
                -50.0,
                50.0,
                -8.0,
                1.0,
                key=f"pct_{wkey}",
            )
        if pick in ("Modify", "Reject"):
            ch["reason"] = c[2].selectbox(
                "Override reason (feeds the learning loop)",
                sim.CATEGORIES,
                key=f"rs_{wkey}",
            )
        if pick == "Request more context":
            ch["note"] = c[2].text_input(
                "What context do you need?",
                "Confirm group check-ins before I sign off.",
                key=f"nt_{wkey}",
            )
            if not str(ch["note"]).strip():
                missing_notes.append(p.decision_type)
        choices[p.decision_type] = ch

# If the manager changes any decision after a run, the old outcome no longer
# matches the current choices, so it is cleared and must be re-submitted.
if "live_choices" in st.session_state and st.session_state["live_choices"] != choices:
    del st.session_state["live_choices"]
    st.warning("Your decisions changed since the last run. Submit again to re-run the service.")

if st.button(
    "Submit my decisions and run the service",
    type="primary",
    use_container_width=True,
    key="submit_live_decisions",
):
    incomplete = [
        decision_type
        for decision_type, decision in choices.items()
        if decision.get("choice") is None
    ]

    if incomplete:
        st.error(
            "Decision required — review each recommendation and make a choice "
            "before running the service. Still open: "
            + ", ".join(sim.TYPE_LABEL.get(t, t) for t in incomplete)
        )
    elif missing_notes:
        st.error(
            "Please describe the context you need before running the service: "
            + ", ".join(sim.TYPE_LABEL.get(t, t) for t in missing_notes)
        )
    else:
        st.session_state["live_choices"] = choices
        st.rerun()

if "live_choices" not in st.session_state:
    st.info("Make your calls above, then run the service to see the outcome.")
    ui.footer()
    st.stop()

# ---------------------------------------------------------------------------
# 3 · What happened (runs only after every human decision is complete)
# ---------------------------------------------------------------------------
res, log, _ = sim.run(choices=st.session_state["live_choices"])

st.markdown("#### 3 · What happened " + ui.tag("MODELED SIMULATION"), unsafe_allow_html=True)
st.dataframe(
    pd.DataFrame(
        [
            {
                "Decision": r["Decision ID"],
                "Type": sim.TYPE_LABEL.get(r["Decision Type"], r["Decision Type"]),
                "Authority": r["Required Authority"],
                "Human decision": r["Human Decision"],
                "Status": r["Execution Status"],
                "Outcome": r["Actual Outcome"],
            }
            for r in res.records
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

prod = next((r for r in res.records if r["Decision Type"] == "production_adjustment"), None)
if prod is not None and not prod["Execution Status"].startswith("BLOCKED"):
    from product import core as _core
    from product import printsheet
    _standing = _core.CASE["kitchen_standing_plan_kg"]
    _plan, _usable = printsheet.plan_from_trace(res.traces[prod["Decision ID"]], _standing)
    st.download_button(
        "Printable kitchen sheet for this plan (open, then print or save as PDF)",
        printsheet.build(
            "Case-study hotel (modeled)", "Saturday breakfast", "D-0418 service", _plan, _usable, _standing,
            [{"id": r["Decision ID"], "what": r["Recommendation"], "who": r["Human Decision"], "status": r["Execution Status"]}
             for r in res.records],
            approver=prod.get("Approver") or "F&B Manager",
            transfers=[r["Recommendation"] for r in res.records if r["Decision Type"] == "inventory_transfer"
                       and str(r["Execution Status"]).startswith("EXECUTED")],
            note="Control Room · modeled simulation",
        ).encode(),
        "kitchen_sheet_D-0418.html",
        "text/html",
        key="dl_kitchen_sheet",
    )

if prod is not None:
    act = prod["_outcome_actual"] or {}
    if prod["Execution Status"].startswith("BLOCKED"):
        ui.card(
            "Policy block",
            f"Your modification was blocked: {ui.e(prod['Policy Status'])}. "
            "The system will not execute a plan that guarantees a stockout, even when a manager asks.",
            dark=True,
        )
    elif act:
        k = st.columns(4)
        k[0].metric(
            "Actual covers",
            f"{act['actual_covers']}",
            f"predicted {act['predicted_covers']}",
            delta_color="off",
        )
        k[1].metric(
            "Food waste",
            f"{act['waste_kg']:.1f} kg",
            f"{act['waste_kg'] - act['counterfactual_waste_kg']:+.1f} kg vs standing plan",
            delta_color="inverse",
        )
        k[2].metric(
            "Stockouts",
            str(len(act["stockouts"])),
            ", ".join(act["stockouts"]) or "none",
            delta_color="off",
        )
        k[3].metric(
            "Guest F&B score",
            f"{act['guest_fb_score']:.2f}",
            "floor 4.60",
            delta_color="off",
        )

        ln = act["lines"]
        groups = list(ln)
        names = [sim.GROUP_LABEL.get(g, g) for g in groups]
        fig = go.Figure()
        fig.add_bar(
            name="Available (plan + carry-over)",
            x=names,
            y=[ln[g]["available_kg"] for g in groups],
            marker_color=ui.SAND,
        )
        fig.add_bar(
            name="Consumed by guests",
            x=names,
            y=[ln[g]["consumed_kg"] for g in groups],
            marker_color=ui.FOREST,
        )
        fig.update_layout(
            title=f"What was put out vs what guests ate ({act['plan_used']})",
            barmode="group",
            height=320,
            yaxis_title="kg",
        )
        st.plotly_chart(fig, use_container_width=True)
    st.caption(prod["Actual Outcome"])

# ---------------------------------------------------------------------------
# 4 · AgentOps and learning
# ---------------------------------------------------------------------------
st.markdown("#### 4 · AgentOps and learning")
m = res.metrics
rows = []
for metric_key, label in [
    ("recommendation_acceptance", "Acceptance"),
    ("human_override_rate", "Override rate"),
    ("escalation_recall", "Escalation recall"),
    ("escalation_precision", "Escalation precision"),
    ("tool_reliability", "Tool reliability"),
]:
    v = m[metric_key]
    rows.append(
        {
            "Metric": label,
            "Today": "—" if v["value"] is None else f"{v['value']:.0%}",
            "n": f"{v['num']}/{v['den']}",
            "Can move the gate?": "Yes" if v["sufficient"] else "No: sample below 20 decisions",
        }
    )
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

if res.learning:
    st.markdown("**Your overrides became learning cases** (no automatic retraining):")
    st.dataframe(
        pd.DataFrame(res.learning)[
            [
                "Decision ID",
                "Human Action",
                "Override Reason",
                "Root Cause (hypothesis)",
                "Proposed System Improvement",
                "Status",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# 5 · Audit trail
# ---------------------------------------------------------------------------
st.markdown("#### 5 · Audit trail")
t1, t2 = st.columns([1, 2])
with t1:
    trace_pick = st.selectbox(
        "Follow one decision end to end",
        list(res.traces),
        key="audit_trace_pick",
    )
    st.download_button(
        "Download decision log (CSV)",
        sim.log_csv(res),
        "decision_log.csv",
        "text/csv",
        use_container_width=True,
        key="dl_decision_log",
    )
    st.download_button(
        "Download all traces (JSON)",
        sim.traces_json(res),
        "traces.json",
        "application/json",
        use_container_width=True,
        key="dl_traces",
    )
with t2:
    if trace_pick is not None:
        t = res.traces[trace_pick]
        r = t["recommendation"]
        h = t["human"]
        o = t["outcome"] or {}

        if h:
            human_line = f"{h['choice'].upper()} by {h['approver']} at {h['timestamp']}"
            if h["override"]:
                human_line += f" · override: {h['override_reason']}"
        else:
            human_line = "none (no human step)"

        lines = [
            f"INPUT        context completeness {t['input']['completeness']:.1%}",
            f"AGENT        {r['recommendation']}",
            f"             why: {r['reason']}",
            f"             confidence {r['confidence']:.1%} · risk {r['risk_level']} · reversibility {r['reversibility']}",
            "GOVERNANCE   " + "\n             ".join(t["governance"]["rule_trace"]),
            "HUMAN        " + human_line,
            f"ACTION       {t['action']['final_action']} → {t['action']['status']}",
            f"OUTCOME      {o.get('summary', '')}",
            f"KPI          escalated {t['kpi_contribution']['escalated']} · "
            f"escalation required {t['kpi_contribution']['escalation_required']}",
        ]
        st.markdown('<div class="cr-trace">' + ui.e("\n".join(lines)) + "</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Replay: clear this page's decisions so the service can be run again
# ---------------------------------------------------------------------------
st.markdown("")
if st.button(
    "↺ Run the service again with different decisions",
    use_container_width=True,
    key="reset_live_service",
):
    for state_key in list(st.session_state.keys()):
        if state_key == "live_choices" or state_key == "audit_trace_pick" or state_key.startswith(("ch_", "pct_", "rs_", "nt_")):
            del st.session_state[state_key]
    st.session_state.live_service_started = False
    st.rerun()

ui.why(
    "A 12.2% production change exceeds the ±10% delegated range, so a 92.7%-confident agent still needs the manager.",
    "Confidence is not authority. Risk, reversibility, policy, permissions and context decide who may act.",
    "Humans stay accountable for material changes, and every override becomes structured learning data.",
    "Route by decision rights, log every step, and let the readiness gate, not the model, grant autonomy.",
)
ui.footer()
