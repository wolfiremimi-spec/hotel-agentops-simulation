import pandas as pd
import streamlit as st
from control_room import sim, ui

ui.header("10", "Methodology & limits", "How this was built, and what it cannot tell you")
st.markdown("#### Evidence labels")
st.markdown(" ".join(ui.tag(t) for t in ui.TAGS), unsafe_allow_html=True)
st.markdown("""
- **Live simulation**: computed now by the repository's Python engine (`hotel_agentops_sim`), the same code the 20 unit tests cover.
- **Workbook**: values from `Hotel_Food_Waste_Model.xlsx`, the modeled 12-week pilot (4 baseline + 8 agent weeks, 250 rooms).
- **Modeled simulation / assumption**: scenario data and new modeled assumptions (NA-01 to NA-15) the case study did not specify.
- **Interpretation**: the strategist's reading of the results.
""")
t1, t2, t3, t4 = st.tabs(["Disclosures & limits", "Modeled assumptions", "Parameters and their source cells", "Python and Excel"])
with t1:
    st.markdown("""
**This is a modeled simulation.** No hotel system is connected. Scenario data is labeled modeled simulation data. No result here is realized hotel performance.

- **One service is one observation.** MAPE, acceptance, override rate and escalation recall/precision are rates over many decisions; day-level rates are shown with
  their sample size and cannot move the gate below 20 decisions. Today's autonomy comes from the latest evaluated pilot week in the workbook (A8).
- **Waste scope is narrower than the pilot's.** The simulation models buffet overproduction and plate waste for four item groups, not spoilage or prep waste.
- **Some outcomes are pending.** Purchasing and banquet decisions take effect after the simulated day.
- **Escalation labels are analyst-set.** Recall and precision are scored against modeled ground-truth labels in the scenario file.
- **The case study illustrates −14%; the simulation computes −12.2%** from its inputs, and keeps the computed number rather than tuning inputs to match.
- **Economics** use illustrative cost assumptions from the workbook; food cost avoided is avoided cost, not revenue; coordination capacity is redeployed time, not cash.
""")
with t2:
    st.dataframe(pd.DataFrame([{"ID": a["id"], "Assumption": a["assumption"]} for a in sim.SCENARIO["new_modeled_assumptions"]]) if isinstance(sim.SCENARIO["new_modeled_assumptions"], list)
                 else pd.DataFrame(list(sim.SCENARIO["new_modeled_assumptions"].items()), columns=["ID", "Assumption"]), use_container_width=True, hide_index=True)
with t3:
    rows = []
    for k, v in sim.PARAMS.items():
        if isinstance(v, dict) and "value" in v and "source" in v:
            rows.append({"Parameter": k.replace("_", " "), "Value": str(v["value"])[:80], "Source": v["source"]})
    for k, v in sim.PARAMS["readiness_thresholds"].items():
        rows.append({"Parameter": "gate · " + k.replace("_", " "), "Value": f"{v['test']} {v['value']}", "Source": v["source"]})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Thresholds are not typed into the code: `tools/extract_parameters.py` reads them from the workbook with their source cells, and a test checks they still match.")
with t4:
    st.markdown("""
- **Python** answers *"What decision should the system make, and is it allowed?"*: agents, orchestration, governance, approval and the decision log.
- **Excel** answers *"What happened, and is the system creating measurable value?"*: modeled data, KPIs, AgentOps, the readiness gate and economics.
- **This app** is a front end on both: `control_room/sim.py` calls the package's own functions (no decision rule is re-implemented), and
  `tools/extract_app_data.py` copies the workbook's calculated values into `data/control_room_workbook.json`.
- Run locally: `pip install -r requirements.txt` then `streamlit run streamlit_app.py`. Command line: `python -m hotel_agentops_sim demo`. Tests: `python -m unittest -v`.
""")
ui.footer()
