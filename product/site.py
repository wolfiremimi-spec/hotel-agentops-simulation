"""Hotel AgentOps design system: global styles, the product website (landing page) and in-app components.

Every figure shown on the website comes from the engine at render time (the demo hotel, modeled data) or from the
case study's specification. HTML is emitted on single lines because Streamlit's markdown treats indented lines as code.
"""
from __future__ import annotations

import functools
import html

import streamlit as st

from control_room import sim

FOREST, FOREST2, MOSS, SAGE, SAND = "#1F3A2F", "#2B4E3F", "#4F7A63", "#A9BFAE", "#C7A877"
LINEN, PAPER, INK, MUTE, LINE, WHITE, ALERT = "#F5F2EA", "#FBFAF6", "#17211C", "#5F6B63", "#E4E1D8", "#FFFFFF", "#A4493D"
CONTROL_ROOM_URL = "https://hotel-agentops-control-room.streamlit.app"
GITHUB_URL = "https://github.com/wolfiremimi-spec/hotel-agentops-simulation"
CASE_STUDY_URL = GITHUB_URL + "/blob/main/Hospitality%20x%20Sustainability%20x%20Agentic%20AI%20Case%20Study%20.pdf"

e = lambda x: html.escape(str(x))  # noqa: E731


def _one_line(s: str) -> str:
    return "".join(line.strip() for line in s.splitlines())


def md(markup: str) -> None:
    st.markdown(_one_line(markup), unsafe_allow_html=True)


LOGO = (f'<svg class="ws-logo" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="{FOREST}"/>'
        f'<path d="M9 22.5c0-7.2 5.2-12.6 14-13.5-.4 8.6-5.6 13.9-13 14.1" fill="none" stroke="{SAND}" stroke-width="2.2" '
        f'stroke-linecap="round" stroke-linejoin="round"/><path d="M10 22l7.5-7.5" stroke="{WHITE}" stroke-width="2.2" '
        'stroke-linecap="round"/></svg>')

CHECK = (f'<svg viewBox="0 0 20 20" class="ws-ic" aria-hidden="true"><circle cx="10" cy="10" r="10" fill="{MOSS}"/>'
         f'<path d="M6 10.2l2.6 2.6L14 7.6" fill="none" stroke="{WHITE}" stroke-width="2" stroke-linecap="round" '
         'stroke-linejoin="round"/></svg>')

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {{ --forest:{FOREST}; --moss:{MOSS}; --sand:{SAND}; --linen:{LINEN}; --paper:{PAPER}; --ink:{INK}; --mute:{MUTE}; --line:{LINE}; }}
html, body, .stApp, [class*="css"], .stMarkdown, button, input, textarea {{ font-family: Inter, 'Helvetica Neue', Arial, sans-serif; }}
.stApp {{ background: {PAPER}; color: {INK}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
footer, #MainMenu {{ visibility: hidden; }}
.block-container {{ max-width: 1180px; padding-top: 2.4rem; padding-bottom: 3rem; }}
h1, h2, h3, h4 {{ color: {FOREST} !important; letter-spacing: -0.02em; }}
/* buttons */
.stButton button, .stFormSubmitButton button, .stDownloadButton button, [data-testid^="stBaseButton"] {{ border-radius: 10px; font-weight: 600; padding: .5rem 1rem; transition: all .15s ease; }}
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {{ background: {FOREST}; border: 1px solid {FOREST}; color: {WHITE}; box-shadow: 0 1px 2px rgba(23,33,28,.15); }}
.stButton button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {{ background: {FOREST2}; border-color: {FOREST2}; color: {WHITE}; }}
.stButton button[kind="secondary"], [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {{ background: {WHITE}; border: 1px solid {LINE}; color: {FOREST}; }}
.stButton button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover {{ border-color: {FOREST}; color: {FOREST}; }}
/* inputs, cards, tabs, expanders */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], .stNumberInput > div > div {{ border-radius: 10px !important; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px; }}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{ background: {WHITE}; }}
[data-testid="stForm"] {{ border: 1px solid {LINE}; border-radius: 12px; background: {PAPER}; }}
[data-testid="stExpander"] details {{ border-radius: 12px; border-color: {LINE}; background: {WHITE}; }}
[data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {LINE}; }}
[data-baseweb="tab"] {{ font-weight: 600; color: {MUTE}; }}
[data-baseweb="tab"][aria-selected="true"] {{ color: {FOREST}; }}
[data-baseweb="tab-highlight"] {{ background: {FOREST}; }}
[data-testid="stMetric"] {{ background: {WHITE}; border: 1px solid {LINE}; border-top: 3px solid {FOREST}; border-radius: 12px; padding: 12px 16px 14px; }}
[data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 12px; overflow: hidden; }}
[data-testid="stAlert"] {{ border-radius: 12px; }}
.cr-banner {{ border-radius: 10px; border-left-width: 3px; }}
.cr-trace {{ border-radius: 10px; }}
/* sidebar */
[data-testid="stSidebar"] {{ background: {WHITE}; border-right: 1px solid {LINE}; }}
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] {{ border-radius: 8px; }}
[data-testid="stSidebarNavLink"][aria-current="page"], [data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {LINEN}; }}
.ws-side-brand {{ display: flex; align-items: center; gap: 10px; margin: 2px 0 14px; }}
.ws-side-brand b {{ font-size: 1rem; color: {FOREST}; letter-spacing: -.01em; }}
.ws-side-brand span {{ display: block; font-size: .72rem; color: {MUTE}; font-weight: 500; }}
.ws-workspace {{ border: 1px solid {LINE}; border-radius: 12px; padding: 10px 12px; margin: 6px 0 10px; background: {PAPER}; }}
.ws-workspace .k {{ font-size: .66rem; letter-spacing: .12em; text-transform: uppercase; color: {MUTE}; font-weight: 700; }}
.ws-workspace .n {{ font-weight: 700; color: {FOREST}; margin-top: 2px; }}
.ws-workspace .s {{ font-size: .75rem; color: {MUTE}; margin-top: 4px; }}
.ws-logo {{ width: 30px; height: 30px; flex: none; }}
.ws-ic {{ width: 18px; height: 18px; flex: none; }}
/* in-app page header */
.ws-ph {{ margin: 0 0 1.2rem; padding-bottom: 1rem; border-bottom: 1px solid {LINE}; }}
.ws-ph .eyebrow {{ display: inline-block; font-size: .7rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: {MOSS}; background: {LINEN}; border-radius: 999px; padding: 4px 10px; }}
.ws-ph h1 {{ font-size: 2rem !important; line-height: 1.15; margin: .55rem 0 .35rem !important; padding: 0 !important; font-weight: 800; }}
.ws-ph p {{ color: {MUTE}; font-size: 1.02rem; max-width: 74ch; margin: 0; }}
.ha-sec .n {{ color: {SAND} !important; }}
.ha-level {{ padding: 12px 16px; margin: .4rem 0 1rem; border-radius: 12px !important; background: {WHITE} !important; border: 1px solid {LINE}; border-left: 4px solid {SAND} !important; }}
.ws-appfoot {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid {LINE}; display: flex; flex-wrap: wrap; gap: 8px 18px; justify-content: space-between; font-size: .78rem; color: {MUTE}; }}
.ws-appfoot a {{ color: {FOREST}; text-decoration: none; font-weight: 600; }}
/* website */
.ws-nav {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 0 18px; }}
.ws-brand {{ display: flex; align-items: center; gap: 10px; text-decoration: none !important; }}
.ws-brand b {{ font-size: 1.08rem; color: {FOREST}; letter-spacing: -.01em; white-space: nowrap; }}
.ws-brand .tag {{ font-size: .64rem; font-weight: 700; letter-spacing: .08em; color: {MOSS}; border: 1px solid {SAGE}; border-radius: 999px; padding: 2px 8px; }}
.ws-links {{ display: flex; align-items: center; gap: 22px; }}
.ws-links a {{ color: {INK} !important; text-decoration: none !important; font-size: .9rem; font-weight: 500; opacity: .8; }}
.ws-links a:hover {{ opacity: 1; }}
.ws-links a.cta {{ opacity: 1; color: {WHITE} !important; background: {FOREST}; border-radius: 10px; padding: 8px 14px; font-weight: 600; white-space: nowrap; }}
.ws-eyebrow {{ display: inline-flex; align-items: center; gap: 8px; font-size: .78rem; font-weight: 600; color: {FOREST}; background: {WHITE}; border: 1px solid {LINE}; border-radius: 999px; padding: 5px 12px 5px 6px; box-shadow: 0 1px 2px rgba(23,33,28,.04); }}
.ws-eyebrow i {{ white-space: nowrap; flex: none; font-style: normal; font-size: .66rem; font-weight: 700; letter-spacing: .06em; color: {WHITE}; background: {MOSS}; border-radius: 999px; padding: 2px 8px; }}
.ws-h1 {{ font-size: 3.2rem; line-height: 1.04; font-weight: 800; letter-spacing: -0.035em; color: {FOREST}; margin: 18px 0 16px; }}
.ws-h1 em {{ font-style: normal; color: {MOSS}; }}
.ws-lede {{ font-size: 1.14rem; line-height: 1.6; color: {MUTE}; max-width: 36rem; margin: 0 0 22px; }}
.ws-btn {{ display: inline-flex; align-items: center; justify-content: center; height: 40px; padding: 0 16px; border-radius: 10px; font-weight: 600; font-size: .95rem; text-decoration: none !important; width: 100%; box-sizing: border-box; }}
.ws-btn.ghost {{ background: {WHITE}; color: {FOREST} !important; border: 1px solid {LINE}; }}
.ws-btn.ghost:hover {{ border-color: {FOREST}; }}
.ws-fine {{ font-size: .8rem; color: {MUTE}; margin-top: 12px; }}
.ws-window {{ background: {WHITE}; border: 1px solid {LINE}; border-radius: 16px; box-shadow: 0 24px 60px -24px rgba(31,58,47,.35), 0 2px 6px rgba(23,33,28,.06); overflow: hidden; }}
.ws-window .bar {{ display: flex; align-items: center; gap: 6px; padding: 10px 14px; border-bottom: 1px solid {LINE}; background: {PAPER}; }}
.ws-window .bar i {{ width: 9px; height: 9px; border-radius: 50%; background: {LINE}; display: inline-block; }}
.ws-window .bar span {{ margin-left: 8px; font-size: .74rem; color: {MUTE}; font-weight: 600; }}
.ws-window .body {{ padding: 16px 18px 18px; }}
.ws-row {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; }}
.ws-chip {{ display: inline-flex; align-items: center; gap: 6px; font-size: .68rem; font-weight: 700; letter-spacing: .06em; border-radius: 999px; padding: 3px 9px; white-space: nowrap; }}
.ws-chip.ok {{ background: #E3EEE7; color: {FOREST}; }} .ws-chip.warn {{ background: #F4ECDD; color: #7A5B22; }} .ws-chip.dark {{ background: {FOREST}; color: {WHITE}; }}
.ws-rec {{ border: 1px solid {LINE}; border-radius: 12px; padding: 12px 14px; margin: 12px 0; }}
.ws-rec .id {{ font-size: .7rem; font-weight: 700; color: {MUTE}; letter-spacing: .06em; }}
.ws-rec .t {{ font-weight: 700; color: {INK}; font-size: .98rem; margin: 3px 0 8px; line-height: 1.35; }}
.ws-kpis {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }}
.ws-kpis div {{ background: {PAPER}; border-radius: 8px; padding: 7px 9px; }}
.ws-kpis b {{ display: block; font-size: .95rem; color: {FOREST}; }}
.ws-kpis span {{ font-size: .66rem; color: {MUTE}; text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }}
.ws-agents {{ display: grid; gap: 7px; margin: 10px 0 12px; }}
.ws-agent {{ display: flex; gap: 9px; align-items: flex-start; font-size: .8rem; line-height: 1.35; }}
.ws-agent b {{ color: {INK}; }} .ws-agent span {{ color: {MUTE}; }}
.ws-gov {{ font-size: .78rem; color: #7A5B22; background: #FBF6EC; border: 1px solid #EFE2C6; border-radius: 10px; padding: 8px 10px; }}
.ws-actions {{ display: grid; grid-template-columns: 1.3fr 1fr 1fr; gap: 8px; margin-top: 12px; }}
.ws-actions span {{ text-align: center; font-size: .8rem; font-weight: 600; border-radius: 8px; padding: 7px 0; border: 1px solid {LINE}; color: {FOREST}; }}
.ws-actions span.p {{ background: {FOREST}; color: {WHITE}; border-color: {FOREST}; }}
.ws-cap {{ font-size: .74rem; color: {MUTE}; text-align: center; margin-top: 10px; }}
.ws-stats {{ display: grid; grid-template-columns: repeat(4, 1fr); border: 1px solid {LINE}; border-radius: 16px; background: {WHITE}; margin: 44px 0 8px; overflow: hidden; }}
.ws-stats div {{ padding: 20px 22px; border-right: 1px solid {LINE}; }}
.ws-stats div:last-child {{ border-right: 0; }}
.ws-stats b {{ display: block; font-size: 1.9rem; font-weight: 800; color: {FOREST}; letter-spacing: -.02em; line-height: 1.1; }}
.ws-stats span {{ font-size: .86rem; color: {MUTE}; }}
.ws-sec {{ margin: 76px 0 26px; text-align: center; }}
.ws-sec .k {{ font-size: .76rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: {MOSS}; }}
.ws-sec h2 {{ font-size: 2.2rem !important; font-weight: 800; line-height: 1.12; margin: 10px auto 12px !important; padding: 0 !important; max-width: 30ch; }}
.ws-sec p {{ color: {MUTE}; font-size: 1.05rem; line-height: 1.6; max-width: 44rem; margin: 0 auto; }}
.ws-steps {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; }}
.ws-step {{ background: {WHITE}; border: 1px solid {LINE}; border-radius: 14px; padding: 18px 16px; position: relative; }}
.ws-step .n {{ width: 30px; height: 30px; border-radius: 9px; background: {LINEN}; color: {FOREST}; font-weight: 800; font-size: .85rem; display: flex; align-items: center; justify-content: center; }}
.ws-step h4 {{ font-size: 1rem !important; margin: 12px 0 6px !important; padding: 0 !important; font-weight: 700; }}
.ws-step p {{ font-size: .86rem; color: {MUTE}; line-height: 1.5; margin: 0; }}
.ws-step .t {{ position: absolute; top: 18px; right: 16px; font-size: .7rem; color: {MUTE}; font-weight: 600; }}
.ws-grid4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
.ws-card {{ background: {WHITE}; border: 1px solid {LINE}; border-radius: 16px; padding: 20px; }}
.ws-card .role {{ font-size: .7rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: {MOSS}; }}
.ws-card h4 {{ font-size: 1.15rem !important; margin: 6px 0 8px !important; padding: 0 !important; font-weight: 800; }}
.ws-card q {{ display: block; color: {INK}; font-size: .95rem; line-height: 1.45; margin-bottom: 14px; }}
.ws-card .lbl {{ font-size: .64rem; font-weight: 700; letter-spacing: .12em; color: {MUTE}; margin: 10px 0 5px; }}
.ws-tags {{ display: flex; flex-wrap: wrap; gap: 5px; }}
.ws-tags span {{ font-size: .74rem; background: {LINEN}; color: {FOREST}; border-radius: 6px; padding: 3px 7px; font-weight: 500; }}
.ws-tags.w span {{ background: #EEF3EF; }}
.ws-tags.x span {{ background: #F6ECEA; color: {ALERT}; }}
.ws-orch {{ margin-top: 14px; background: {FOREST}; color: {WHITE}; border-radius: 16px; padding: 20px 22px; display: grid; grid-template-columns: 1.2fr 2fr; gap: 20px; align-items: center; }}
.ws-orch .role {{ color: {SAND}; font-size: .7rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }}
.ws-orch h4 {{ color: {WHITE} !important; font-size: 1.2rem !important; margin: 6px 0 0 !important; padding: 0 !important; font-weight: 800; }}
.ws-orch p {{ color: #DCE6DF; margin: 0; line-height: 1.55; font-size: .95rem; }}
.ws-split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 22px; align-items: stretch; }}
.ws-points {{ display: grid; gap: 14px; }}
.ws-point {{ display: flex; gap: 12px; background: {WHITE}; border: 1px solid {LINE}; border-radius: 14px; padding: 16px 18px; }}
.ws-point h4 {{ font-size: 1rem !important; margin: 0 0 4px !important; padding: 0 !important; font-weight: 700; }}
.ws-point p {{ margin: 0; font-size: .9rem; color: {MUTE}; line-height: 1.55; }}
.ws-ladder {{ background: {WHITE}; border: 1px solid {LINE}; border-radius: 16px; padding: 22px; display: flex; flex-direction: column; gap: 10px; }}
.ws-ladder .hd {{ font-size: .72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: {MUTE}; }}
.ws-tier {{ border-radius: 12px; padding: 14px 16px; border: 1px solid {LINE}; }}
.ws-tier b {{ font-size: .8rem; letter-spacing: .1em; }}
.ws-tier p {{ margin: 4px 0 0; font-size: .88rem; line-height: 1.5; }}
.ws-tier.t3 {{ background: {FOREST}; border-color: {FOREST}; color: {WHITE}; margin-right: 0; }}
.ws-tier.t3 p {{ color: #DCE6DF; }} .ws-tier.t3 b {{ color: {SAND}; }}
.ws-tier.t2 {{ background: {LINEN}; margin-right: 8%; }} .ws-tier.t2 b {{ color: {FOREST}; }} .ws-tier.t2 p {{ color: {INK}; }}
.ws-tier.t1 {{ background: {WHITE}; margin-right: 16%; }} .ws-tier.t1 b {{ color: {MUTE}; }} .ws-tier.t1 p {{ color: {MUTE}; }}
.ws-gate {{ display: flex; gap: 5px; flex-wrap: wrap; margin-top: 6px; }}
.ws-gate span {{ font-size: .7rem; border: 1px solid {LINE}; border-radius: 6px; padding: 3px 7px; color: {FOREST}; background: {PAPER}; }}
.ws-proof {{ display: grid; grid-template-columns: 1.1fr 1fr 1fr 1fr; gap: 0; border: 1px solid {LINE}; border-radius: 16px; background: {WHITE}; overflow: hidden; }}
.ws-proof > div {{ padding: 22px; border-right: 1px solid {LINE}; }}
.ws-proof > div:last-child {{ border-right: 0; }}
.ws-proof .lead {{ background: {LINEN}; }}
.ws-proof .lead b {{ color: {FOREST}; font-size: 1.05rem; }}
.ws-proof .lead p {{ color: {MUTE}; font-size: .86rem; line-height: 1.5; margin: 6px 0 0; }}
.ws-proof .v {{ font-size: 2.1rem; font-weight: 800; color: {FOREST}; letter-spacing: -.02em; line-height: 1.1; }}
.ws-proof .l {{ font-size: .86rem; color: {MUTE}; margin-top: 4px; line-height: 1.4; }}
.ws-note {{ text-align: center; font-size: .78rem; color: {MUTE}; margin-top: 10px; }}
.ws-start-h {{ font-weight: 700; color: {FOREST}; font-size: 1.05rem; margin: 2px 0 2px; }}
.ws-start-p {{ color: {MUTE}; font-size: .88rem; line-height: 1.5; margin: 0 0 10px; }}
.ws-truth {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
.ws-truth .ws-card h4 {{ font-size: 1rem !important; }}
.ws-truth ul {{ margin: 0; padding-left: 1.1rem; color: {INK}; font-size: .92rem; line-height: 1.6; }}
.ws-foot {{ margin-top: 80px; background: {FOREST}; color: #DCE6DF; border-radius: 20px; padding: 34px 34px 26px; }}
.ws-foot .top {{ display: flex; justify-content: space-between; gap: 30px; flex-wrap: wrap; }}
.ws-foot .brand {{ display: flex; gap: 10px; align-items: center; }}
.ws-foot .brand b {{ color: {WHITE}; font-size: 1.1rem; }}
.ws-foot p {{ margin: 10px 0 0; max-width: 34rem; line-height: 1.55; font-size: .9rem; }}
.ws-foot .cols {{ display: flex; gap: 46px; }}
.ws-foot .cols div {{ display: flex; flex-direction: column; gap: 8px; font-size: .88rem; }}
.ws-foot .cols .h {{ color: {SAND}; font-size: .7rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }}
.ws-foot a {{ color: {WHITE} !important; text-decoration: none !important; }}
.ws-foot .legal {{ border-top: 1px solid rgba(255,255,255,.14); margin-top: 26px; padding-top: 16px; font-size: .76rem; color: #B9C8BE; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
@media (max-width: 900px) {{
  .ws-h1 {{ font-size: 2.3rem; }} .ws-links a:not(.cta), .ws-brand .tag {{ display: none; }}
  .ws-stats, .ws-grid4 {{ grid-template-columns: 1fr 1fr; }} .ws-stats div:nth-child(2) {{ border-right: 0; }}
  .ws-stats div:nth-child(-n+2) {{ border-bottom: 1px solid {LINE}; }}
  .ws-steps {{ grid-template-columns: 1fr; }} .ws-split, .ws-truth, .ws-orch {{ grid-template-columns: 1fr; }}
  .ws-proof {{ grid-template-columns: 1fr 1fr; }} .ws-proof > div {{ border-bottom: 1px solid {LINE}; }}
  .ws-sec h2 {{ font-size: 1.7rem !important; }}
}}
</style>
"""

LANDING_CSS = """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { padding-top: 1.2rem; }
.stApp { background: radial-gradient(1200px 520px at 78% -8%, #E7EFE9 0%, rgba(231,239,233,0) 60%), #FBFAF6; }
</style>
"""


def setup(landing: bool = False) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if landing:
        st.markdown(LANDING_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# In-app components
# ---------------------------------------------------------------------------
def page_header(eyebrow: str, title: str, sub: str = "") -> None:
    md(f'<div class="ws-ph"><span class="eyebrow">{e(eyebrow)}</span><h1>{e(title)}</h1>'
       + (f"<p>{e(sub)}</p>" if sub else "") + "</div>")


def app_footer(extra: str = "") -> None:
    md(f'<div class="ws-appfoot"><span>Hotel AgentOps · pilot application · modeled and hotel-entered data; no hotel '
       f'systems are connected.{(" " + e(extra)) if extra else ""}</span><span><a href="{CONTROL_ROOM_URL}" target="_blank">'
       f'Control Room ↗</a> &nbsp; <a href="{GITHUB_URL}" target="_blank">Source ↗</a></span></div>')


def sidebar_brand(workspace: dict | None, demo: bool) -> None:
    md(f'<div class="ws-side-brand">{LOGO}<div><b>Hotel AgentOps</b><span>Governed AI for food production</span></div></div>')
    if workspace:
        status = "Demo · modeled data · not saved" if demo else "Live workspace · saved"
        md(f'<div class="ws-workspace"><div class="k">Workspace</div><div class="n">{e(workspace["name"])}</div>'
           f'<div class="s">{e(status)}</div></div>')


# ---------------------------------------------------------------------------
# Website (landing page)
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def snapshot() -> dict:
    """Live engine output for the demo hotel (modeled case-study data), shown in the product preview."""
    res, _, _ = sim.run()
    rec = {r["Decision ID"]: r for r in res.records}
    prod = next(r for r in res.records if r["Decision Type"] == "production_adjustment")
    tr = res.traces[prod["Decision ID"]]
    det, act = tr["details"], tr["outcome"]["actual"]
    reason = tr["recommendation"]["reason"]
    inv = next((r for r in res.records if r["Decision Type"] == "inventory_transfer"), None)
    flag = next((r for r in res.records if r["Decision Type"] == "flag_overproduction"), None)
    head = prod["Recommendation"].split(":")[0]
    return {
        "id": prod["Decision ID"], "headline": head, "confidence": prod["Confidence"], "risk": prod["Risk"],
        "authority": prod["Required Authority"], "change": det["change"], "covers": det["expected_covers"],
        "demand": reason.split(". ")[0], "inventory": inv["Recommendation"] if inv else "No expiry risk",
        "waste": flag["Recommendation"].replace("Flag chronic overproduction: ", "Chronic overproduction: ") if flag else "",
        "range": sim.PARAMS["delegated_prep_range"]["value"], "waste_kg": act["waste_kg"],
        "standing_kg": act["counterfactual_waste_kg"], "actual_covers": act["actual_covers"],
        "predicted": act["predicted_covers"], "ape": act["forecast_ape"], "stockouts": len(act["stockouts"]),
        "decisions": len(rec), "gate_checks": len(res.gate["checks"]), "sources": len(sim.SOURCES),
    }


def nav() -> None:
    md(f'<div class="ws-nav"><a class="ws-brand" href="#top">{LOGO}<b>Hotel AgentOps</b><span class="tag">PILOT</span></a>'
       '<div class="ws-links"><a href="#how">How it works</a><a href="#agents">Agents</a><a href="#governance">Governance</a>'
       f'<a href="{CONTROL_ROOM_URL}" target="_blank">Control Room</a><a href="#get-started" class="cta">Get started</a></div></div>')


def hero_text() -> None:
    md('<div id="top"></div><span class="ws-eyebrow"><i>AGENTIC AI</i>Four specialist agents · one governed decision</span>'
       '<div class="ws-h1">Cut breakfast waste.<br><em>Keep every guest happy.</em></div>'
       '<p class="ws-lede">Hotel AgentOps plans each morning\'s food production with four AI specialist agents, then lets '
       'governance rules decide what can run on its own and what needs your approval. Autonomy is earned from your '
       'hotel\'s own results, never assumed.</p>')


def hero_fine() -> None:
    md('<div class="ws-fine">No sign-up for the demo · runs on the case study\'s modeled hotel · nothing is saved</div>')


def preview() -> None:
    s = snapshot()
    over = abs(s["change"]) > s["range"]
    md(f'<div class="ws-window"><div class="bar"><i></i><i></i><i></i><span>Today\'s plan · Saturday breakfast · 08:02</span></div>'
       f'<div class="body"><div class="ws-row"><b style="color:{FOREST}">Awaiting your decision</b>'
       f'<span class="ws-chip warn">MANAGER APPROVAL</span></div>'
       f'<div class="ws-rec"><div class="id">{e(s["id"])} · BREAKFAST PRODUCTION PLAN</div><div class="t">{e(s["headline"])}</div>'
       f'<div class="ws-kpis"><div><b>{e(s["confidence"])}</b><span>Confidence</span></div><div><b>{e(s["risk"].title())}</b>'
       f'<span>Risk</span></div><div><b>{s["covers"]}</b><span>Covers expected</span></div></div></div>'
       '<div class="ws-agents">'
       f'<div class="ws-agent">{CHECK}<div><b>Demand</b> <span>{e(s["demand"])}</span></div></div>'
       f'<div class="ws-agent">{CHECK}<div><b>Inventory</b> <span>{e(s["inventory"])}</span></div></div>'
       f'<div class="ws-agent">{CHECK}<div><b>Waste</b> <span>{e(s["waste"])}</span></div></div>'
       f'<div class="ws-agent">{CHECK}<div><b>Production</b> <span>{e(s["headline"].split("(")[-1].rstrip(")"))} plan drafted</span></div></div>'
       '</div>'
       + (f'<div class="ws-gov"><b>Why you?</b> {abs(s["change"]):.1%} change exceeds the ±{s["range"]:.0%} range the agents may '
          f'run alone. {e(s["confidence"])} confidence doesn\'t change that.</div>' if over else "")
       + '<div class="ws-actions"><span class="p">Approve</span><span>Modify</span><span>Reject</span></div></div></div>'
       '<div class="ws-cap">Live engine output for the demo hotel · modeled case-study data</div>')


def stats() -> None:
    s = snapshot()
    md('<div class="ws-stats">'
       '<div><b>4</b><span>AI specialist agents, each limited to its own data</span></div>'
       f'<div><b>{s["sources"]}</b><span>data sources checked before any action</span></div>'
       f'<div><b>{s["gate_checks"]}/{s["gate_checks"]}</b><span>readiness checks to earn autonomy</span></div>'
       '<div><b>100%</b><span>of decisions logged with their full rule trace</span></div></div>')


def section(anchor: str, kicker: str, title: str, sub: str = "") -> None:
    md(f'<div class="ws-sec" id="{e(anchor)}"><div class="k">{e(kicker)}</div><h2>{e(title)}</h2>'
       + (f"<p>{e(sub)}</p>" if sub else "") + "</div>")


def how_it_works() -> None:
    section("how", "How it works", "One loop, every service.",
            "A closed-loop decision system, not a one-time prediction. Each morning runs the same governed cycle.")
    steps = [("01", "Perceive", "Enter the morning", "Occupancy, reservations, inventory, events and the team's notes, in one form."),
             ("02", "Reason", "Agents analyse", "Demand, Inventory and Waste run in parallel; Production drafts the plan from their signals."),
             ("03", "Govern", "Rules route it", "Risk, reversibility, confidence and policy decide who may act on each recommendation."),
             ("04", "Act", "You decide", "Approve, modify, reject or ask for context. The kitchen gets its production sheet."),
             ("05", "Learn", "Close out", "Record covers and leftovers. Every service builds the record autonomy is earned from.")]
    md('<div class="ws-steps">' + "".join(
        f'<div class="ws-step"><div class="n">{n}</div><span class="t">{t}</span><h4>{e(h)}</h4><p>{e(p)}</p></div>'
        for n, t, h, p in steps) + "</div>")


def agents() -> None:
    section("agents", "The agents", "Four specialists beat one general model.",
            "Each agent answers one question with only the access its role requires, exactly as the case study specifies. "
            "Least privilege is enforced in code: a request outside an agent's role is denied.")
    cards = [("Demand Agent", "What demand should we expect?", ["PMS occupancy", "Reservations", "POS history", "Events", "Front-desk notes"],
              ["Nothing"], ["Cannot purchase"]),
             ("Inventory Agent", "What do we already have?", ["Inventory", "Procurement", "Shelf life", "Kitchen notes"],
              ["Inventory recommendation"], []),
             ("Waste Agent", "Where and why are we losing food?", ["Waste logs", "POS consumption"], ["Waste insights"], []),
             ("Production Agent", "What should we prepare?", ["Other agents' signals only"],
              ["Production plan, within threshold"], ["No raw data access"])]
    md('<div class="ws-grid4">' + "".join(
        f'<div class="ws-card"><div class="role">Specialist</div><h4>{e(n)}</h4><q>{e(q)}</q>'
        f'<div class="lbl">READS</div><div class="ws-tags">{"".join(f"<span>{e(x)}</span>" for x in r)}</div>'
        f'<div class="lbl">WRITES</div><div class="ws-tags w">{"".join(f"<span>{e(x)}</span>" for x in w)}</div>'
        + (f'<div class="lbl">LIMITS</div><div class="ws-tags x">{"".join(f"<span>{e(x)}</span>" for x in x_)}</div>' if x_ else "")
        + "</div>" for n, q, r, w, x_ in cards) + "</div>")
    md('<div class="ws-orch"><div><div class="role">Coordinator</div><h4>Orchestrator</h4></div>'
       '<p>“How do these signals combine into one operational decision?” It resolves conflicts between agents, for '
       'example rising demand against chronic pastry waste, and escalates what it can\'t explain. It executes nothing '
       'and has no purchasing authority.</p></div>')


def governance() -> None:
    s = snapshot()
    section("governance", "Governance", "Autonomy is earned, not assumed.",
            "Maximum autonomy isn't the goal. The right level of autonomy for the risk is.")
    points = [("Confidence is not authority",
               f"{s['id']} is {s['confidence']} confident, yet a {abs(s['change']):.1%} change exceeds the ±{s['range']:.0%} "
               "delegated range, so a manager approves it. Risk and reversibility decide who acts."),
              ("AI can only make the system more cautious",
               "Every AI output is verified against hard bounds. Agents may lower their confidence or escalate, never raise "
               "authority or remove a stockout warning. If an agent fails, a rule-based agent takes over."),
              ("Nothing happens off the record",
               "Every recommendation, rule, human decision and outcome is logged. The audit trail is append-only.")]
    left = '<div class="ws-points">' + "".join(
        f'<div class="ws-point">{CHECK}<div><h4>{e(h)}</h4><p>{e(p)}</p></div></div>' for h, p in points) + "</div>"
    gate = "".join(f"<span>{e(c)}</span>" for c in ["Acceptance ≥ 80%", "Recall ≥ 90%", "Precision ≥ 85%",
                                                     "Tool reliability ≥ 99%", "Overrides ≤ 15%", "MAPE ≤ 10%",
                                                     "Guest score ≥ 4.60", "0 policy violations"])
    right = ('<div class="ws-ladder"><div class="hd">The autonomy ladder</div>'
             '<div class="ws-tier t3"><b>DELEGATED</b><p>Low-risk, reversible actions run alone. Requires all eight checks '
             'on the hotel\'s own record.</p><div class="ws-gate">' + gate + '</div></div>'
             '<div class="ws-tier t2"><b>SUPERVISED</b><p>Every action needs a manager. Where every new hotel starts.</p></div>'
             '<div class="ws-tier t1"><b>BOUNDED</b><p>Recommend only. Triggered by a guest-score breach, a policy '
             'violation or rising overrides.</p></div></div>')
    md(f'<div class="ws-split">{left}{right}</div>')


def proof() -> None:
    s = snapshot()
    cut = 1 - s["waste_kg"] / s["standing_kg"]
    section("results", "Modeled result", "What one governed morning changes.",
            "Decision D-0418 from the case study, run end to end by the engine behind this product.")
    md('<div class="ws-proof"><div class="lead"><b>Saturday breakfast · 250-room hotel</b><p>Plan approved by the manager, '
       'served, then scored against what the kitchen\'s usual par would have done with the same guests.</p></div>'
       f'<div><div class="v">−{cut:.0%}</div><div class="l">food waste: {s["waste_kg"]} kg vs {s["standing_kg"]} kg on the standing plan</div></div>'
       f'<div><div class="v">{s["ape"]:.1%}</div><div class="l">forecast error: {s["actual_covers"]} actual vs {s["predicted"]} predicted covers</div></div>'
       f'<div><div class="v">{s["stockouts"]}</div><div class="l">stockouts, with the guest-score floor held</div></div></div>'
       '<div class="ws-note">Modeled implementation simulation · not realized hotel performance</div>')


def get_started_header() -> None:
    section("get-started", "Get started", "Try it in two minutes.",
            "Explore the demo hotel, or create a private workspace for your own property.")


def truth() -> None:
    md('<div class="ws-sec" style="margin-top:64px"><div class="k">Straight answers</div><h2>What it is, and what it isn\'t.</h2></div>'
       '<div class="ws-truth"><div class="ws-card"><div class="role">It is</div><h4>A working pilot application</h4><ul>'
       '<li>Daily planning with AI agents, approvals and a production sheet</li>'
       '<li>Close-out scoring, a full decision log and an append-only audit trail</li>'
       '<li>Autonomy computed from the hotel\'s own track record</li>'
       '<li>Built from the case study\'s specification and tested end to end</li></ul></div>'
       '<div class="ws-card"><div class="role">It isn\'t</div><h4>A finished enterprise integration</h4><ul>'
       '<li>Connected to your PMS, POS or inventory system: the manager enters the figures</li>'
       '<li>Validated in a live hotel yet: results shown here are modeled</li>'
       '<li>Letting AI decide who may act: decision rights are deterministic rules</li>'
       '<li>Single sign-on: access is by private workspace code</li></ul></div></div>')


def footer() -> None:
    md(f'<div class="ws-foot"><div class="top"><div><div class="brand">{LOGO}<b>Hotel AgentOps</b></div>'
       '<p>A governed, closed-loop multi-agent system for hotel food production. AI is the mechanism, not the goal.</p></div>'
       '<div class="cols"><div><span class="h">Product</span><a href="#how">How it works</a><a href="#agents">Agents</a>'
       '<a href="#governance">Governance</a></div><div><span class="h">Evidence</span>'
       f'<a href="{CONTROL_ROOM_URL}" target="_blank">Control Room ↗</a><a href="{CASE_STUDY_URL}" target="_blank">Case study ↗</a>'
       f'<a href="{GITHUB_URL}" target="_blank">Source code ↗</a></div></div></div>'
       '<div class="legal"><span>Built by Amelia Wolfire · Hospitality · Sustainability · Agentic AI</span>'
       '<span>Modeled implementation simulation · no live hotel systems are connected</span></div></div>')
