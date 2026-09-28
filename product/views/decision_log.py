import csv
import io
import json

import pandas as pd
import streamlit as st

from control_room import sim, ui
from product import app_state as S
from product import site


def page():
    site.page_header("Decision log & audit", "Every decision, who made it, and why",
              "Each recommendation is logged with its authority, the human decision, what was executed and the rule "
              "trace behind it. Close-outs add the actual outcome.")
    days = [d for d in S.days() if d.get("run")]
    if not days:
        st.info("No decisions yet. Approve a morning plan on Today's plan and it appears here.")
        return
    rows = []
    for d in sorted(days, key=lambda x: x["service_date"], reverse=True):
        for r in d["run"]["records"]:
            rows.append({"Service date": d["service_date"], **{k: v for k, v in r.items() if not k.startswith("_")}})
    df = pd.DataFrame(rows)
    c = st.columns(3)
    types = sorted(df["Decision Type"].unique())
    pick_t = c[0].multiselect("Decision type", types, format_func=lambda t: sim.TYPE_LABEL.get(t, t), key="dl_types")
    statuses = sorted(df["Execution Status"].unique())
    pick_s = c[1].multiselect("Status", statuses, key="dl_status")
    only_over = c[2].checkbox("Only human overrides", key="dl_over")
    view = df
    if pick_t:
        view = view[view["Decision Type"].isin(pick_t)]
    if pick_s:
        view = view[view["Execution Status"].isin(pick_s)]
    if only_over:
        view = view[view["Override"] == "YES"]
    st.dataframe(view[["Service date", "Decision ID", "Recommendation", "Risk", "Required Authority", "Human Decision",
                       "Execution Status", "Actual Outcome"]], use_container_width=True, hide_index=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(df.columns))
    w.writeheader()
    w.writerows(rows)
    d1, d2 = st.columns(2)
    d1.download_button("Download the full decision log (CSV)", buf.getvalue().encode(), "decision_log.csv", "text/csv",
                       use_container_width=True, key="dl_csv")
    traces = {r["Decision ID"]: d["run"]["traces"][r["Decision ID"]] for d in days for r in d["run"]["records"]}
    d2.download_button("Download every trace (JSON)", json.dumps(traces, indent=2, default=str).encode(), "traces.json",
                       "application/json", use_container_width=True, key="dl_json")

    st.markdown("**Follow one decision end to end**")
    ids = list(view["Decision ID"]) or list(df["Decision ID"])
    did = st.selectbox("Decision", ids, key="dl_pick")
    t = traces[did]
    r = t["recommendation"]
    h = t.get("human")
    o = t.get("outcome") or {}
    lines = [f"INPUT        context completeness {t['input']['completeness']:.1%}",
             f"AGENT        {r['recommendation']}", f"             why: {r['reason']}",
             f"             confidence {r['confidence']:.1%} · risk {r['risk_level']} · reversibility {r['reversibility']}",
             "GOVERNANCE   " + "\n             ".join(t["governance"]["rule_trace"]),
             "HUMAN        " + ((f"{h['choice'].upper()} by {h['approver']} at {h['timestamp']}"
                                 + (f" · override: {h['override_reason']}" if h.get("override") else "")
                                 + (f" · note: {h['note']}" if h.get("note") else "")) if h else "none (no human step)"),
             f"ACTION       {t['action']['final_action']} → {t['action']['status']}",
             f"OUTCOME      {o.get('summary', '')}"]
    st.markdown('<div class="cr-trace">' + ui.e("\n".join(lines)) + "</div>", unsafe_allow_html=True)
    day_of = next(d for d in days if did in d["run"]["traces"])
    reps = day_of["run"].get("ai_agents") or []
    st.caption(f"Agents that morning: {day_of['run'].get('agent_mode', 'Rule-based agents')}")
    if reps:
        with st.expander("What each AI agent concluded that morning, and what verification allowed"):
            for r in reps:
                st.markdown(f"**{ui.e(r['agent'])}** · {ui.e(r['status'])}" + (f" · {ui.e(r['model'])}" if r.get("model") else "")
                            + (f"  \n_{ui.e(r['rationale'])}_" if r.get("rationale") else "")
                            + (f"  \nChanged: {ui.e('; '.join(r['changes']))}" if r.get("changes") else "")
                            + (f"  \nVerification: {ui.e('; '.join(r['verification']))}" if r.get("verification") else "")
                            + (f"  \nFallback reason: {ui.e(r['error'])}" if r.get("error") else ""), unsafe_allow_html=True)

    learning = [c_ for d in days for c_ in d["run"].get("learning", [])]
    if learning:
        st.markdown("**Overrides become learning cases** (reviewed by people; nothing retrains automatically)")
        st.dataframe(pd.DataFrame(learning)[["Decision ID", "Human Action", "Override Reason", "Outcome Evidence",
                                             "Proposed System Improvement", "Status"]], use_container_width=True, hide_index=True)

    st.markdown("**Audit trail**")
    st.caption("Append-only: entries can't be edited or deleted." if not S.is_demo() else "Demo audit trail (not saved).")
    audit = S.get_store().list_audit(S.hotel()["id"])
    st.dataframe(pd.DataFrame([{"When (UTC)": a["at"], "Who": a["actor"], "Action": a["action"].replace("_", " "),
                                "Detail": json.dumps(a.get("detail") or {}, default=str)[:300]} for a in audit]),
                 use_container_width=True, hide_index=True)


page()
site.app_footer()
