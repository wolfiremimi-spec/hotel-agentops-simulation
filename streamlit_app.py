"""Hotel AgentOps Control Room: an interactive front end for the hotel_agentops_sim simulation."""
import streamlit as st

st.set_page_config(page_title="Hotel AgentOps Control Room", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
from control_room import ui  # noqa: E402
ui.setup()

pages = {
    "Overview": [st.Page("control_room/views/01_mission_control.py", title="Mission Control", default=True)],
    "Run the system": [
        st.Page("control_room/views/02_live_service.py", title="Live Service: You Decide"),
        st.Page("control_room/views/03_scenario_lab.py", title="Scenario Lab"),
        st.Page("control_room/views/04_failure_lab.py", title="Failure Lab"),
    ],
    "Govern and prove": [
        st.Page("control_room/views/05_readiness_gate.py", title="Readiness Gate & Autonomy"),
        st.Page("control_room/views/06_agentops.py", title="AgentOps & Learning"),
        st.Page("control_room/views/07_business_value.py", title="Business Value"),
    ],
    "How it works": [
        st.Page("control_room/views/08_architecture.py", title="Architecture & Decision Rights"),
        st.Page("control_room/views/09_methodology.py", title="Methodology & Limits"),
    ],
}
nav = st.navigation(pages)
with st.sidebar:
    st.markdown("**Hotel AgentOps**  \nControl Room")
    st.caption("Modeled simulation · no hotel systems connected")
    st.caption("Built by Amelia Wolfire")
nav.run()
