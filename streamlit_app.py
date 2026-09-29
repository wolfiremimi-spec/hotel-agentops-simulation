"""Hotel AgentOps Control Room: an interactive front end for the hotel_agentops_sim simulation."""
import streamlit as st

st.set_page_config(page_title="Hotel AgentOps Control Room", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
from control_room import ui  # noqa: E402
ui.setup()

from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent


def page(path, **kw):
    """A page, or None if its file is missing, so one missing file can never take the whole Control Room down."""
    return st.Page(path, **kw) if (HERE / path).is_file() else None


pages = {
    "Overview": [page("control_room/views/01_mission_control.py", title="Mission Control", default=True)],
    "Run the system": [
        page("control_room/views/02_live_service.py", title="Live Service: You Decide"),
        page("control_room/views/03_scenario_lab.py", title="Scenario Lab"),
        page("control_room/views/04_failure_lab.py", title="Failure Lab"),
        page("control_room/views/procurement.py", title="Procurement: Next Week's Order"),
    ],
    "Govern and prove": [
        page("control_room/views/05_readiness_gate.py", title="Readiness Gate & Autonomy"),
        page("control_room/views/06_agentops.py", title="AgentOps & Learning"),
        page("control_room/views/07_business_value.py", title="Business Value"),
    ],
    "How it works": [
        page("control_room/views/08_architecture.py", title="Architecture & Decision Rights"),
        page("control_room/views/09_methodology.py", title="Methodology & Limits"),
    ],
}
pages = {group: [p for p in items if p is not None] for group, items in pages.items()}
nav = st.navigation({g: items for g, items in pages.items() if items})
with st.sidebar:
    st.markdown("**Hotel AgentOps**  \nControl Room")
    st.caption("Modeled simulation · no hotel systems connected")
    st.caption("Built by Amelia Wolfire")
nav.run()
