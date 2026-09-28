"""Design system for the Control Room: the case study's forest / sand / linen palette, labels and reusable blocks."""
import html
import json
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

FOREST, MOSS, SAGE, SAND, LINEN, WHITE, INK = "#1F3A2F", "#4F7A63", "#A9BFAE", "#C7A877", "#F5F2EA", "#FFFFFF", "#26302B"
GRAY, LINE, MUTE, ALERT = "#CBD3CC", "#E3E6E0", "#5F6B63", "#A4493D"
FONT = "Inter, 'Helvetica Neue', Arial, sans-serif"
WB = json.loads((Path(__file__).resolve().parents[1] / "data" / "control_room_workbook.json").read_text())

pio.templates["controlroom"] = go.layout.Template(data=dict(bar=[go.Bar(cliponaxis=False)]), layout=go.Layout(
    font=dict(family=FONT, color=INK, size=13), paper_bgcolor=WHITE, plot_bgcolor=WHITE, colorway=[FOREST, SAND, MOSS, GRAY],
    margin=dict(l=10, r=30, t=56, b=10), hoverlabel=dict(bgcolor=WHITE, bordercolor=LINE, font=dict(color=INK, family=FONT)),
    xaxis=dict(gridcolor=LINE, zeroline=False, linecolor=LINE, tickfont=dict(color=MUTE), automargin=True),
    yaxis=dict(gridcolor=LINE, zeroline=False, linecolor=LINE, tickfont=dict(color=MUTE), automargin=True),
    legend=dict(orientation="h", yanchor="top", y=-0.2, x=0, font=dict(color=MUTE)),
    title=dict(font=dict(size=14, color=FOREST), x=0, xanchor="left")))
pio.templates.default = "controlroom"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown {{ font-family: {FONT}; color: {INK}; }}
.block-container {{ padding-top: 3.2rem; max-width: 1200px; }}
h1, h2, h3, h4 {{ color: {FOREST} !important; letter-spacing: -0.01em; }}
[data-testid="stSidebar"] {{ background: {LINEN}; border-right: 1px solid {LINE}; }}
[data-testid="stMetric"] {{ background: {WHITE}; border-top: 3px solid {FOREST}; padding: 10px 14px 12px; }}
[data-testid="stMetricLabel"] p {{ font-size: .72rem !important; letter-spacing: .12em; text-transform: uppercase; color: {MUTE} !important; font-weight: 600; }}
[data-testid="stMetricValue"] {{ color: {FOREST}; font-weight: 700; }}
.cr-kicker {{ font-size: .72rem; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; color: {SAND}; margin-bottom: .25rem; }}
.cr-title {{ font-size: 2.05rem; line-height: 1.15; font-weight: 700; color: {FOREST}; margin: 0 0 .4rem; max-width: 32ch; }}
.cr-sub {{ font-size: 1.02rem; color: {MUTE}; margin-bottom: 1rem; max-width: 72ch; }}
.cr-banner {{ background: {LINEN}; border-left: 3px solid {SAND}; padding: 8px 12px; font-size: .82rem; color: {MUTE}; margin-bottom: 1rem; }}
.cr-tag {{ display: inline-block; font-size: .64rem; font-weight: 700; letter-spacing: .08em; padding: 2px 7px; border-radius: 3px; margin: 0 4px 4px 0; vertical-align: middle; white-space: nowrap; }}
.t-sim {{ border: 1px dashed {MOSS}; color: {MOSS}; }} .t-wb {{ border: 1px solid {FOREST}; color: {FOREST}; }}
.t-asm {{ background: {LINEN}; color: {INK}; border: 1px solid {SAND}; }} .t-live {{ background: {FOREST}; color: {WHITE}; }}
.t-int {{ border: 1px solid {GRAY}; color: {MUTE}; }}
.cr-card {{ background: {LINEN}; border-radius: 6px; padding: 14px 16px; height: 100%; }}
.cr-card b.l {{ display: block; font-size: .66rem; letter-spacing: .14em; text-transform: uppercase; color: {MOSS}; margin-bottom: 4px; }}
.cr-card p {{ margin: 0; font-size: .95rem; line-height: 1.45; }}
.cr-dark {{ background: {FOREST}; color: {WHITE}; border-radius: 6px; padding: 16px 18px; height: 100%; }}
.cr-dark b.l {{ display: block; font-size: .66rem; letter-spacing: .16em; text-transform: uppercase; color: {SAND}; margin-bottom: 6px; }}
.cr-dark p {{ margin: 0; font-size: 1rem; line-height: 1.45; color: {WHITE}; }}
.cr-pill {{ display: inline-block; font-size: .72rem; font-weight: 700; letter-spacing: .08em; padding: 4px 10px; border-radius: 20px; }}
.p-ok {{ background: {MOSS}; color: #fff; }} .p-hold {{ background: {ALERT}; color: #fff; }} .p-warn {{ background: {SAND}; color: {INK}; }} .p-neutral {{ background: {GRAY}; color: {INK}; }}
.cr-trace {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .82rem; background: {LINEN}; border-radius: 6px; padding: 10px 12px; white-space: pre-wrap; line-height: 1.5; }}
.cr-why {{ border: 1px solid {LINE}; border-radius: 6px; overflow: hidden; margin: 1rem 0 1.4rem; }}
.cr-why-h {{ background: {FOREST}; color: {WHITE}; font-size: .72rem; font-weight: 700; letter-spacing: .18em; padding: 8px 14px; }}
.cr-why-g {{ display: grid; grid-template-columns: repeat(4, 1fr); }}
.cr-why-g > div {{ padding: 12px 14px; border-right: 1px solid {LINE}; background: {LINEN}; }}
.cr-why-g > div:last-child {{ border-right: 0; background: {WHITE}; border-left: 3px solid {FOREST}; }}
.cr-why-g b {{ display: block; font-size: .66rem; letter-spacing: .14em; text-transform: uppercase; color: {MOSS}; margin-bottom: 4px; }}
.cr-why-g p {{ font-size: .9rem; line-height: 1.45; margin: 0; }}
.cr-flow {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
.cr-flow span.s {{ padding: 7px 11px; border-radius: 4px; font-size: .8rem; font-weight: 600; background: {LINEN}; color: {FOREST}; }}
.cr-flow span.on {{ background: {FOREST}; color: {WHITE}; }} .cr-flow span.a {{ color: {SAND}; font-weight: 700; }}
.cr-table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
.cr-table th {{ text-align: left; font-size: .68rem; letter-spacing: .1em; text-transform: uppercase; color: {MUTE}; border-bottom: 2px solid {FOREST}; padding: 6px 8px; }}
.cr-table td {{ padding: 7px 8px; border-bottom: 1px solid {LINE}; vertical-align: top; }}
.cr-foot {{ margin-top: 2.2rem; padding-top: .7rem; border-top: 1px solid {LINE}; font-size: .78rem; color: {MUTE}; }}
@media (max-width: 800px) {{ .cr-why-g {{ grid-template-columns: 1fr; }} .cr-title {{ font-size: 1.6rem; }} }}
</style>
"""
TAGS = {"LIVE SIMULATION": "t-live", "MODELED SIMULATION": "t-sim", "WORKBOOK": "t-wb", "ASSUMPTION": "t-asm", "INTERPRETATION": "t-int"}
e = lambda x: html.escape(str(x))


def setup(): st.markdown(CSS, unsafe_allow_html=True)
def tag(label): return f'<span class="cr-tag {TAGS[label]}">{label}</span>'


def header(num, kicker, title, sub=""):
    st.markdown(f'<div class="cr-kicker">{e(num)} · {e(kicker)}</div><div class="cr-title">{e(title)}</div>' + (f'<div class="cr-sub">{sub}</div>' if sub else ""),
                unsafe_allow_html=True)


def banner(text=None):
    st.markdown(f'<div class="cr-banner">{text or "<b>Modeled simulation.</b> No hotel system is connected. Scenario data and results are modeled, not realized hotel performance."}</div>',
                unsafe_allow_html=True)


def card(label, text, dark=False):
    st.markdown(f'<div class="{"cr-dark" if dark else "cr-card"}"><b class="l">{label}</b><p>{text}</p></div>', unsafe_allow_html=True)


def pill(text, kind="neutral"): return f'<span class="cr-pill p-{kind}">{e(text)}</span>'


def authority_kind(auth: str) -> str:
    a = auth.lower()
    if a.startswith("agent executes"): return "ok"
    if a.startswith(("blocked", "abstain")): return "hold"
    if a.startswith(("human decision", "recommend only")): return "warn"
    return "neutral"


def why(evidence, insight, implication, decision):
    cells = [("Evidence", evidence), ("Insight", insight), ("Implication", implication), ("Decision", decision)]
    st.markdown('<div class="cr-why"><div class="cr-why-h">WHY THIS DESIGN?</div><div class="cr-why-g">' + "".join(f"<div><b>{a}</b><p>{b}</p></div>" for a, b in cells)
                + "</div></div>", unsafe_allow_html=True)


def flow(steps, active=None):
    st.markdown('<div class="cr-flow">' + '<span class="a">→</span>'.join(f'<span class="s{" on" if s == active else ""}">{e(s)}</span>' for s in steps) + "</div>",
                unsafe_allow_html=True)


def footer(extra=""):
    st.markdown(f'<div class="cr-foot">Hotel AgentOps Control Room · modeled simulation of the governed multi-agent system in the case study '
                f'<i>Agentic AI for Sustainable Hospitality</i> by Amelia Wolfire. No hotel system is connected; results are not realized performance. {extra}</div>',
                unsafe_allow_html=True)


def usd(v, d=0): return ("−" if v < 0 else "") + f"${abs(v):,.{d}f}"
def pct(v, d=0): return f"{v*100:.{d}f}%"
