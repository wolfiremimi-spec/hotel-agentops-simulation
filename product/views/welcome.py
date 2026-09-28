import streamlit as st

from control_room import ui
from product import app_state as S
from product import core

st.markdown(
    '<div class="ha-hero"><div class="k">HOTEL AGENTOPS · PILOT</div>'
    "<h1>Cut breakfast waste without cutting guest experience.</h1>"
    "<p>Four specialist agents read your hotel's occupancy, reservations, inventory, waste history and events each "
    "morning and recommend the production plan. Governance rules decide what they may do alone and what needs your "
    "approval. Every decision is logged, every service is scored, and autonomy is earned from your own results.</p></div>",
    unsafe_allow_html=True,
)
ui.flow(["Enter this morning's data", "Agents recommend", "Governance routes", "You approve", "Kitchen serves",
         "Close out", "Autonomy earned"])

db = S.database_configured()
c1, c2, c3 = st.columns(3)

with c1:
    with st.container(border=True):
        st.markdown("**Set up your hotel**")
        st.caption("Create a private workspace. You'll get an access code; keep it safe, it's how you and your team get back in.")
        with st.form("ha_create"):
            name = st.text_input("Hotel name", key="ha_new_name")
            rooms = st.number_input("Rooms", 10, 3000, 250, 1, key="ha_new_rooms")
            approver = st.text_input("Who approves the plan? (name or role)", "F&B Manager", key="ha_new_approver")
            go = st.form_submit_button("Create workspace", type="primary", use_container_width=True, disabled=not db)
        if not db:
            st.caption("Saving hotels needs the database, which isn't connected on this deployment yet.")
        if go:
            if not name.strip():
                st.error("Please enter your hotel's name.")
            else:
                p = core.default_profile(name.strip())
                p["rooms"], p["approver"] = int(rooms), approver.strip() or "F&B Manager"
                store = S.get_store("live")
                hid, code = store.create_hotel(name.strip(), p)
                store.log(hid, p["approver"], "workspace_created", {"rooms": p["rooms"]})
                S.open_workspace("live", {"id": hid, "name": name.strip(), "profile": p})
                st.session_state.ha_new_code = code
                st.rerun()

with c2:
    with st.container(border=True):
        st.markdown("**Open your workspace**")
        st.caption("Enter the access code you received when the workspace was created.")
        with st.form("ha_open"):
            code = st.text_input("Access code", placeholder="XXXX-XXXX-XXXX", key="ha_code_in")
            go = st.form_submit_button("Open", use_container_width=True, disabled=not db)
        if go:
            row = S.get_store("live").open_hotel(code)
            if row is None:
                st.error("No workspace matches that code. Check it and try again.")
            else:
                S.open_workspace("live", row)
                st.rerun()

with c3:
    with st.container(border=True):
        st.markdown("**Try the demo hotel**")
        st.caption("The 250-room hotel from the case study, preloaded with its modeled history and the D-0418 Saturday "
                   "morning. Run a full day: approve, close out, see the audit trail. Nothing is saved.")
        if st.button("Open the demo", use_container_width=True, key="ha_demo"):
            store = S.get_store("demo")
            p = core.demo_profile()
            hid, _ = store.create_hotel(p["hotel_name"], p)
            store.log(hid, "Demo", "workspace_created", {"demo": True})
            S.open_workspace("demo", store.get_hotel(hid))
            st.rerun()

st.markdown("")
st.markdown("**What it is, and what it isn't**")
st.markdown(
    "- **It is** a working decision-support tool for a hotel pilot. Data comes in by form each morning, results by "
    "close-out each evening, and everything is stored and auditable.\n"
    "- **It isn't** connected to your PMS, POS or inventory system. Those integrations would come in a funded "
    "pilot, and until then the manager enters the figures.\n"
    "- **The agents are rule-based and deterministic.** The optional copilot uses an AI model to explain and "
    "run what-ifs, but it never decides who may act.\n"
    "- **Access is by private workspace code:** a pilot-grade control, not single sign-on.")
ui.footer("Hotel AgentOps pilot application.")
