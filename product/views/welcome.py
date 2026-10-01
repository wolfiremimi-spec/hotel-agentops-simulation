import streamlit as st

from product import app_state as S
from product import core, site


def open_demo():
    store = S.get_store("demo")
    p = core.demo_profile()
    hid, _ = store.create_hotel(p["hotel_name"], p)
    store.log(hid, "Demo", "workspace_created", {"demo": True})
    S.open_workspace("demo", store.get_hotel(hid))
    st.rerun()


if st.session_state.pop("hv_open_demo", False):
    open_demo()

site.nav()
site.side_nav()

# ---------------------------------------------------------------- hero
left, right = st.columns([1.05, 1], gap="large", vertical_alignment="center")
with left:
    site.hero_text()
    b1, b2, _ = st.columns([1.1, 1, 0.4])
    if b1.button("Try the live demo →", type="primary", use_container_width=True, key="ha_demo"):
        open_demo()
    b2.markdown('<a class="ws-btn ghost" href="#get-started">Set up your hotel</a>', unsafe_allow_html=True)
    site.hero_fine()
with right:
    site.preview()

site.stats()

site.banner()

# ---------------------------------------------------------------- get started
site.get_started_header()
db = S.database_configured()
c1, c2, c3 = st.columns(3, gap="medium")

with c1:
    with st.container(border=True):
        site.md('<div class="ws-start-h">Explore the demo hotel</div><p class="ws-start-p">The 250-room hotel from the case '
                'study with its modeled history, on the D-0418 Saturday morning. Plan, approve, close out and audit a full '
                'day. Nothing is saved.</p>')
        if st.button("Open the demo", use_container_width=True, key="ha_demo_card", type="primary"):
            open_demo()

with c2:
    with st.container(border=True):
        site.md('<div class="ws-start-h">Create a workspace</div><p class="ws-start-p">A private workspace for your '
                'property. You\'ll receive an access code: it\'s how you and your team get back in.</p>')
        with st.form("ha_create", border=False):
            name = st.text_input("Hotel name", key="ha_new_name")
            rooms = st.number_input("Rooms", 10, 3000, 250, 1, key="ha_new_rooms")
            approver = st.text_input("Who approves the plan? (name or role)", "F&B Manager", key="ha_new_approver")
            go = st.form_submit_button("Create workspace", type="primary", use_container_width=True, disabled=not db)
        if not db:
            st.caption("Creating a workspace isn't available on this deployment. Try the demo instead.")
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

with c3:
    with st.container(border=True):
        site.md('<div class="ws-start-h">Open your workspace</div><p class="ws-start-p">Already set up? Enter the access '
                'code you received when the workspace was created.</p>')
        with st.form("ha_open", border=False):
            code = st.text_input("Access code", placeholder="XXXX-XXXX-XXXX", key="ha_code_in")
            go = st.form_submit_button("Open", use_container_width=True, disabled=not db)
        if go:
            row = S.get_store("live").open_hotel(code)
            if row is None:
                st.error("No workspace matches that code. Check it and try again.")
            else:
                S.open_workspace("live", row)
                st.rerun()

# ---------------------------------------------------------------- how-to videos
site.videos_header()
_, mid, _ = st.columns([1, 1.2, 1])
if mid.button("Watch the how-to videos →", type="primary", use_container_width=True, key="ha_videos"):
    st.switch_page("product/views/videos.py")
_, v1, v2, _ = st.columns([0.55, 1, 1, 0.55], gap="large")
for col, v in zip((v1, v2), site.HOW_TO_VIDEOS):
    with col:
        site.video_thumb(v)
        if st.button(f"▶ Play video {v['label'][-6]}", use_container_width=True, key=f"ha_play_{v['key']}"):
            st.session_state.hv_pick = v["key"]
            st.switch_page("product/views/videos.py")

site.how_it_works()
site.connected()
site.agents()
site.governance()
site.proof()
site.project()

site.truth()
site.about()
site.footer()
