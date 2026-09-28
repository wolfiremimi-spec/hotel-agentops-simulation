import streamlit as st
from control_room import sim, ui
from hotel_agentops_sim.agents import DemandAgent, InventoryAgent, ProductionAgent, WasteAgent

ui.header("09", "Architecture & decision rights", "AI is the mechanism, not the goal",
          "Seven layers, four specialists with least-privilege access, one orchestrator with no purchasing authority, and explicit rules for who may act.")

LAYERS = [("1 · Enterprise data", "PMS / occupancy · POS covers and consumption · inventory · procurement · waste tracking · events · guest experience"),
          ("2 · Context + memory", "Current operational state · history · previous decisions and outcomes · business rules · hotel policies"),
          ("3 · Specialized agents", "Demand · Inventory · Waste · Production"),
          ("4 · Orchestration", "Task decomposition · coordination · shared state · conflict resolution · recommendation synthesis"),
          ("5 · Governance + control", "Identity · least-privilege permissions · thresholds · risk scoring · hard constraints · human approval · escalation · reversibility · audit"),
          ("6 · Action", "Adjust production · reallocate inventory · recommend purchasing changes · flag overproduction · escalate exceptions"),
          ("7 · Observability + AgentOps", "Log decisions · monitor outcomes · prediction vs actual · capture overrides · detect drift · reassess autonomy")]
for i, (a, b) in enumerate(LAYERS):
    dark = a.startswith(("4", "5"))
    st.markdown(f'<div style="display:grid;grid-template-columns:230px 1fr;gap:14px;padding:10px 14px;margin-bottom:5px;border-radius:5px;'
                f'background:{ui.FOREST if dark else ui.LINEN};color:{"#fff" if dark else ui.INK}"><b style="color:{ui.SAND if dark else ui.FOREST}">{a}</b><span>{b}</span></div>',
                unsafe_allow_html=True)
st.caption("Objective: minimize food waste and unnecessary operating cost, subject to the guest-experience floor, food safety, service levels, inventory, purchasing policy and human decision rights.")

st.markdown("#### Four specialists, each with only the access its role needs " + ui.tag("LIVE SIMULATION"), unsafe_allow_html=True)
st.caption("Read directly from the agent classes in the code. Any read outside an agent's list raises an error.")
cols = st.columns(4)
for col, A in zip(cols, [DemandAgent, InventoryAgent, WasteAgent, ProductionAgent]):
    with col:
        reads = ", ".join(sim.SOURCE_LABEL.get(r, r) for r in A.READS) or "No raw data: approved signals only"
        writes = ", ".join(A.WRITES) or "Nothing (cannot write or purchase)"
        ui.card(A.__name__.replace("Agent", " Agent"), f"<b>Reads</b><br>{ui.e(reads)}<br><br><b>Writes</b><br>{ui.e(writes)}")
ui.card("Orchestrator", "Coordinates the agents and synthesizes recommendations. No agent, including the orchestrator, holds purchasing write permission: "
        "every purchase-order change goes to a human.", dark=True)

st.markdown("#### Who may act: decision rights")
st.markdown('<table class="cr-table"><tr><th>Situation</th><th>Authority</th><th>Example in the simulation</th></tr>' + "".join(
    f"<tr><td>{a}</td><td>{ui.pill(b, ui.authority_kind(b))}</td><td>{c}</td></tr>" for a, b, c in [
        ("LOW risk, reversible, inside ±10% delegated range, gate PASS", "Agent executes (delegated)", "Flag chronic pastry overproduction; transfer 6 kg near-expiry yogurt"),
        ("MEDIUM risk (change 10-25%) or no agent write permission", "Agent recommends · manager approves", "Breakfast plan −12.2%; purchase-order change"),
        ("HIGH risk, abnormal event demand, unresolved agent conflict", "Human decision · mandatory escalation", "Wedding brunch guarantee changed −32%"),
        ("Confidence below 80%", "Recommend only · no execution", "Forecast error above 20%"),
        ("Context completeness below 95%", "Abstain · escalate to manager", "PMS occupancy feed missing"),
        ("Hard constraint violated or stale inventory", "Blocked · escalate", "Plan below expected consumption (planned stockout)")]) + "</table>", unsafe_allow_html=True)

st.markdown("#### The governance check, in order")
ui.flow(["1 Context completeness", "2 Policy / hard constraints", "3 Risk + reversibility", "4 Permissions", "5 Confidence (can only lower authority)",
         "6 Failure-mode rules", "7 Autonomy level from the gate", "Final authority"], active="Final authority")
st.caption("Every rule that fires is written to the decision's rule trace (see Live Service → Audit trail). Source: `governance.evaluate()`.")

ui.why("The Demand Agent cannot write anything; the Production Agent reads only the approved plan; no agent can purchase.",
       "Splitting one big model into four narrow specialists makes each decision explainable and each permission auditable.",
       "Least privilege plus explicit decision rights is what lets an operator delegate safely.",
       "Specialists recommend, the orchestrator reconciles, governance decides who acts, and humans own material decisions.")
ui.footer()
