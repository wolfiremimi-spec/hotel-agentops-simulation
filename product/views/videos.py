import streamlit as st

from product import app_state as S
from product import site

VIDEOS = site.HOW_TO_VIDEOS


def page():
    if S.hotel() is None:
        if st.button("← Back to the website", key="hv_back"):
            st.switch_page("product/views/welcome.py")
    site.page_header("How-to videos", "See exactly how Hotel AgentOps works",
                     "Two short walkthroughs recorded in this app. Video 1 runs through the demo hotel; video 2 shows "
                     "how a hotel sets up its own workspace. Captions are on screen, so no sound is needed.",
                     photo="band_today.jpg")
    pick = st.session_state.pop("hv_pick", None)
    order = sorted(VIDEOS, key=lambda v: v["key"] != pick)
    for col, v in zip(st.columns(2, gap="large"), order):
        with col, st.container(border=True):
            st.markdown(f'<div class="ha-vid"><span class="n">{site.e(v["label"])} · {site.e(v["length"])}</span>'
                        f'<h3>{site.e(v["title"])}</h3><p>{site.e(v["summary"])}</p></div>', unsafe_allow_html=True)
            st.video(str(site.ASSETS / "videos" / v["file"]))
            st.caption(v["note"])
    if S.hotel() is None:
        c = st.columns([1, 1, 2])
        if c[0].button("Try the live demo →", type="primary", use_container_width=True, key="hv_demo"):
            st.session_state.hv_open_demo = True
            st.switch_page("product/views/welcome.py")
        if c[1].button("Set up your hotel", use_container_width=True, key="hv_setup"):
            st.switch_page("product/views/welcome.py")


page()
site.app_footer("The videos use the demo's modeled data and a fictional example hotel.")
