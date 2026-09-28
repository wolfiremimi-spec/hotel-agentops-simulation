"""Hotel AgentOps: governed multi-agent decision support for hotel food production.

Main file for its own Streamlit app. Secrets: SUPABASE_URL, SUPABASE_SECRET_KEY (database), APP_SALT (optional),
GEMINI_API_KEY and GEMINI_MODEL (optional, for the copilot).
"""
import streamlit as st

st.set_page_config(page_title="Hotel AgentOps", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")

from control_room import ui  # noqa: E402
from product import app_state as S  # noqa: E402

ui.setup()
st.markdown(
    f"""
<style>
.ha-hero {{ background: {ui.FOREST}; color: {ui.WHITE}; border-radius: 8px; padding: 26px 28px; margin-bottom: 16px; }}
.ha-hero .k {{ font-size: .72rem; font-weight: 700; letter-spacing: .18em; color: {ui.SAND}; }}
.ha-hero h1 {{ color: {ui.WHITE} !important; font-size: 2rem; line-height: 1.15; margin: .3rem 0 .5rem; }}
.ha-hero p {{ color: {ui.LINEN}; margin: 0; max-width: 72ch; }}
.ha-sec {{ margin: 1.8rem 0 .5rem; }}
.ha-sec .n {{ font-size: .72rem; font-weight: 700; letter-spacing: .18em; color: {ui.SAND}; }}
.ha-sec .t {{ font-size: 1.2rem; font-weight: 700; color: {ui.FOREST}; margin-top: .1rem; }}
.ha-level {{ border-radius: 6px; padding: 12px 16px; margin: .4rem 0 1rem; background: {ui.LINEN}; border-left: 4px solid {ui.SAND}; }}
.ha-level b {{ color: {ui.FOREST}; }}
.ha-code {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 1.6rem; font-weight: 700; letter-spacing: .12em;
            color: {ui.FOREST}; background: {ui.LINEN}; border: 2px dashed {ui.SAND}; border-radius: 6px; padding: 12px 16px;
            display: inline-block; }}
@media (max-width: 800px) {{ .ha-hero h1 {{ font-size: 1.5rem; }} }}
</style>
""",
    unsafe_allow_html=True,
)

if S.hotel() is None:
    pages = [st.Page("product/views/welcome.py", title="Welcome", icon="🌿", default=True)]
else:
    pages = {
        "Daily operations": [
            st.Page("product/views/today.py", title="Today's plan", icon="☀️", default=True),
            st.Page("product/views/closeout.py", title="Close out service", icon="✅"),
        ],
        "Evidence": [
            st.Page("product/views/decision_log.py", title="Decision log & audit", icon="📋"),
            st.Page("product/views/performance.py", title="Performance & autonomy", icon="📈"),
        ],
        "Assist": [st.Page("product/views/copilot.py", title="Ops copilot", icon="💬")],
        "Hotel": [st.Page("product/views/setup.py", title="Hotel setup", icon="⚙️")],
    }

nav = st.navigation(pages)
with st.sidebar:
    st.markdown("**Hotel AgentOps**  \nGoverned AI for food production")
    h = S.hotel()
    if h:
        st.markdown(f"**{ui.e(h['name'])}**", unsafe_allow_html=True)
        st.caption("Demo workspace · modeled case-study data · nothing is saved after you leave" if S.is_demo()
                   else "Your hotel workspace · saved to the database")
        if st.button("Leave workspace", use_container_width=True, key="ha_leave"):
            S.close_workspace()
            st.rerun()
    st.caption("Built by Amelia Wolfire")
if st.session_state.get("ha_new_code"):
    with st.container(border=True):
        st.markdown("**Your workspace is ready. Save this access code now.**")
        st.markdown(f'<div class="ha-code">{ui.e(st.session_state.ha_new_code)}</div>', unsafe_allow_html=True)
        st.caption("It's the only way back into this hotel's workspace, for you and your team. It won't be shown again, "
                   "and it can't be recovered: store it in your password manager.")
        if st.button("I've saved the code", type="primary", key="ha_code_ack"):
            del st.session_state["ha_new_code"]
            st.rerun()
S.guard(nav.run)
