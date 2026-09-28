import datetime as dt
import io

import pandas as pd
import streamlit as st

from control_room import sim, ui
from product import app_state as S
from product import core

GL = sim.GROUP_LABEL
HIST_COLS = (["date", "occupied_rooms", "covers", "forecast_error_pct"] + [f"leftover_pct_{g}" for g in core.GROUPS]
             + [f"ran_out_{g}" for g in core.GROUPS])


def history_frame(rows):
    out = []
    for r in rows:
        row = {"date": r["date"], "occupied_rooms": r.get("occupied_rooms"), "covers": r.get("covers"),
               "forecast_error_pct": r.get("forecast_error_pct")}
        for g in core.GROUPS:
            row[f"leftover_pct_{g}"] = (r.get("leftover_pct") or {}).get(g)
            row[f"ran_out_{g}"] = bool((r.get("stockout") or {}).get(g, False))
        out.append(row)
    df = pd.DataFrame(out, columns=HIST_COLS)
    for c in HIST_COLS:
        if c.startswith("ran_out_"):
            df[c] = df[c].fillna(False).astype(bool)
        elif c != "date":
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
        else:
            df[c] = df[c].astype("object")
    return df


def truthy(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return False
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "y", "x")
    return bool(v)


def rows_from_frame(df):
    rows, errors = [], []
    for i, r in df.iterrows():
        raw = r.get("date")
        if raw is None or (isinstance(raw, float) and pd.isna(raw)) or str(raw).strip() == "":
            continue
        try:
            date = dt.date.fromisoformat(str(raw).strip()[:10]).isoformat()
        except ValueError:
            errors.append(f"Row {i + 1}: '{raw}' is not a date (use YYYY-MM-DD)")
            continue

        def num(c):
            v = r.get(c)
            return None if v is None or pd.isna(v) else float(v)
        row = {"date": date}
        if num("occupied_rooms") is not None and num("covers") is not None:
            row["occupied_rooms"], row["covers"] = int(num("occupied_rooms")), int(num("covers"))
        if num("forecast_error_pct") is not None:
            row["forecast_error_pct"] = num("forecast_error_pct")
        lp = {g: num(f"leftover_pct_{g}") for g in core.GROUPS}
        if all(v is not None for v in lp.values()):
            row["leftover_pct"] = lp
            row["stockout"] = {g: truthy(r.get(f"ran_out_{g}")) for g in core.GROUPS}
        if len(row) == 1:
            errors.append(f"Row {i + 1} ({date}): no covers, forecast error or leftover figures")
            continue
        rows.append(row)
    return rows, errors


def page():
    ui.header("HOTEL AGENTOPS", "Hotel setup", "Your hotel, your menu, your rules",
              "The agents plan from these figures, and governance applies your policy. Changes apply from the next "
              "morning you plan; past decisions keep the settings they were made under.")
    p = dict(S.profile())
    if p.get("defaults_from_case_study"):
        st.warning("These starting figures are the case study's modeled hotel. Replace them with your hotel's own figures, "
                   "then save.")
    with st.form("su_form"):
        t1, t2, t3, t4 = st.tabs(["Hotel", "Menu & par levels", "Governance policy", "Baseline history"])
        with t1:
            c = st.columns(3)
            name = c[0].text_input("Hotel name", S.hotel()["name"], key="su_name")
            rooms = c[1].number_input("Rooms", 10, 3000, int(p["rooms"]), 1, key="su_rooms")
            service = c[2].text_input("Service name", p.get("service_name", "Breakfast"), key="su_service")
            c = st.columns(3)
            approver = c[0].text_input("Default approver", p.get("approver", "F&B Manager"), key="su_approver")
            outlet = c[1].text_input("Outlet that can use near-expiry stock", p.get("alternative_outlet", ""), key="su_outlet")
            cost = c[2].number_input("Food waste cost ($ per kg)", 0.0, 500.0, float(p["waste_cost_per_kg"]), 0.01,
                                     key="su_cost")
        with t2:
            st.caption("Average consumption per cover and the kitchen's standing par (what it prepares without AI). "
                       "After four closed-out services on the same weekday, consumption is learned from your own close-outs.")
            c = st.columns(4)
            per, par = {}, {}
            for i, g in enumerate(core.GROUPS):
                per[g] = c[i].number_input(f"{GL[g]} (kg per cover)", 0.0, 2.0, float(p["consumption_kg_per_cover"][g]), 0.001,
                                           format="%.3f", key=f"su_per_{g}")
                par[g] = c[i].number_input(f"{GL[g]} standing par (kg)", 0.0, 2000.0, float(p["standing_plan_kg"][g]), 0.5,
                                           key=f"su_par_{g}")
        with t3:
            c = st.columns(2)
            cth = c[0].slider("Context completeness required (%)", 75, 100, int(round(p["context_threshold"] * 100)),
                              key="su_cth", help="Below this share of the eight data sources, the system abstains.")
            drange = c[1].slider("Delegated production range (± %)", 5, 25, int(round(p["delegated_range"] * 100)),
                                 key="su_drange", help="Plan changes inside this range are LOW risk; larger ones need a manager.")
            st.caption("Escalation policy (which decision types must always reach a person). Used to score escalation "
                       "recall and precision.")
            st.dataframe(pd.DataFrame([{"Decision type": sim.TYPE_LABEL.get(k, k), "Must reach a person": "Yes" if v else "No"}
                                       for k, v in p["escalation_policy"].items()]), hide_index=True)
        with t4:
            st.caption(f"The agents need {core.HISTORY_NEEDED} previous services on the same weekday (covers, occupied "
                       "rooms and leftover %) and recent forecast errors. Enter what you have from before using this "
                       "tool; every close-out adds to it automatically.")
            hist = st.data_editor(history_frame(p.get("baseline_history", [])), num_rows="dynamic", use_container_width=True,
                                  key="su_hist", column_config={
                                      "date": st.column_config.TextColumn("Date (YYYY-MM-DD)"),
                                      **{f"leftover_pct_{g}": st.column_config.NumberColumn(f"{GL[g]} left %", min_value=0.0,
                                                                                            max_value=100.0) for g in core.GROUPS},
                                      **{f"ran_out_{g}": st.column_config.CheckboxColumn(f"{GL[g]} ran out") for g in core.GROUPS}})
        go = st.form_submit_button("Save setup", type="primary", use_container_width=True)
    if go:
        rows, errors = rows_from_frame(hist)
        if errors:
            st.error("Fix the baseline history first: " + "; ".join(errors))
            return
        if not name.strip():
            st.error("Enter the hotel name.")
            return
        new = dict(p, rooms=int(rooms), service_name=service.strip() or "Breakfast", approver=approver.strip() or "F&B Manager",
                   alternative_outlet=outlet.strip(), waste_cost_per_kg=float(cost), consumption_kg_per_cover=per,
                   standing_plan_kg=par, context_threshold=cth / 100, delegated_range=drange / 100,
                   baseline_history=rows, hotel_name=name.strip(), defaults_from_case_study=False)
        S.save_profile(new, name=name.strip(), actor=approver.strip())
        st.success("Setup saved. It applies from the next morning you plan.")

    st.markdown("**Import baseline history from a spreadsheet**")
    c = st.columns(2)
    c[0].download_button("Download the history template (CSV)", history_frame([]).to_csv(index=False).encode(),
                         "baseline_history_template.csv", "text/csv", use_container_width=True, key="su_tpl")
    up = c[1].file_uploader("Upload a filled template (CSV)", type=["csv"], key="su_up")
    if up is not None and st.button("Import these rows (replaces the baseline history)", key="su_import"):
        try:
            df = pd.read_csv(io.BytesIO(up.getvalue()), dtype={"date": str})
        except Exception as ex:                                  # malformed file
            st.error(f"Couldn't read that file ({type(ex).__name__}).")
            return
        missing = [c_ for c_ in ["date", "occupied_rooms", "covers"] if c_ not in df.columns]
        if missing:
            st.error("The file is missing columns: " + ", ".join(missing) + ". Start from the template.")
            return
        for c_ in HIST_COLS:
            if c_ not in df.columns:
                df[c_] = False if c_.startswith("ran_out_") else None
        rows, errors = rows_from_frame(df[HIST_COLS])
        if errors:
            st.error("; ".join(errors[:5]))
            return
        S.save_profile(dict(p, baseline_history=rows), actor=p.get("approver", ""))
        st.session_state.pop("su_hist", None)
        st.session_state.su_imported = len(rows)
        st.rerun()
    if st.session_state.get("su_imported") is not None:
        st.success(f"Imported {st.session_state.pop('su_imported')} history rows.")


page()
ui.footer("Hotel AgentOps pilot application.")
