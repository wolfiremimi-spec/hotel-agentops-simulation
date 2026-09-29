"""Guided tour for demo visitors: six steps through one full day, ticked off from what the visitor has actually done."""
from __future__ import annotations

import re

import streamlit as st

from control_room import ui
from product import app_state as S

STEPS = [
    ("plan", "Save the morning's data", "product/views/today.py",
     "The D-0418 morning is prefilled from the case study. Scroll down and click **Save this morning's data and ask the "
     "agents**."),
    ("decide", "Make your decisions", "product/views/today.py",
     "Four agents have recommended; governance decided which calls need you. For each one, choose **Approve**, **Modify**, "
     "**Reject** or **Request more context**, then click **Save my decisions and today's plan**. Nothing is pre-selected: you hold the authority."),
    ("close", "Close out breakfast", "product/views/closeout.py",
     "Record what actually happened. Click **Fill with the case study's modeled result**, then **Save the close-out**: the day is scored "
     "against the kitchen's standing par."),
    ("log", "Follow one decision end to end", "product/views/decision_log.py",
     "Every decision is here with its authority, your choice and the governance rule trace. Pick **D-0418** under "
     "*Follow one decision end to end*."),
    ("autonomy", "See how autonomy is earned", "product/views/performance.py",
     "The readiness gate: eight checks on the hotel's own record. Autonomy is earned from results, never granted by "
     "confidence."),
    ("order", "Approve next week's order", "product/views/orders.py",
     "The Procurement Agent turns the hotel's services into next week's supplier order: less where food is left over, "
     "more where guests ran short. Review it and click **Approve and log this order**."),
]


def mark(step: str) -> None:
    """Record that a visitor reached a page-based step."""
    if not S.is_demo():
        return
    done = status()
    earlier = [k for k, *_ in STEPS[:[k for k, *_ in STEPS].index(step)]]
    if all(done[k] for k in earlier):                    # count it only in order, once there is something to see
        st.session_state[f"ha_tour_{step}"] = True


def _anchor_day():
    date = S.profile().get("demo_anchor_date")
    return date, next((d for d in S.days() if d["service_date"] == date), None)


def status() -> dict:
    date, day = _anchor_day()
    return {
        "plan": bool((day and day.get("inputs")) or st.session_state.get(f"td_inputs_{date}")),
        "decide": bool(day and day.get("run")),
        "close": bool(day and day.get("closeout")),
        "log": bool(st.session_state.get("ha_tour_log")),
        "autonomy": bool(st.session_state.get("ha_tour_autonomy")),
        "order": bool(S.profile().get("orders")),
    }


def next_step():
    done = status()
    return next((s for s in STEPS if not done[s[0]]), None)


def sidebar() -> None:
    if not S.is_demo() or st.session_state.get("ha_tour_hidden"):
        return
    done = status()
    n = sum(done.values())
    nxt = next_step()
    st.markdown(f"**Guided tour** · {n}/{len(STEPS)}")
    st.progress(n / len(STEPS))
    for key, title, path, _ in STEPS:
        if done[key]:
            st.markdown(f"<span style='color:{ui.MOSS}'>✓</span> <span style='color:{ui.MUTE}'>{ui.e(title)}</span>",
                        unsafe_allow_html=True)
        elif nxt and key == nxt[0]:
            st.page_link(path, label=f"→ {title}", icon=None)
        else:
            st.markdown(f"<span style='color:{ui.GRAY}'>○</span> {ui.e(title)}", unsafe_allow_html=True)
    if nxt is None:
        st.success("Tour complete. You've run a full governed day: plan, decide, close out, audit, earn autonomy, order.")
    if st.button("Hide tour", key="ha_tour_hide", use_container_width=True):
        st.session_state.ha_tour_hidden = True
        st.rerun()


def hint(page_path: str) -> None:
    """A 'you are here' card at the top of the page the next tour step happens on."""
    if not S.is_demo() or st.session_state.get("ha_tour_hidden"):
        return
    nxt = next_step()
    if nxt is None or nxt[2] != page_path:
        return
    i = [s[0] for s in STEPS].index(nxt[0]) + 1
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", ui.e(nxt[3])))
    st.markdown(f'<div class="ha-tour"><div class="k">Guided tour · step {i} of {len(STEPS)}</div>'
                f'<div class="t">{ui.e(nxt[1])}</div><p>{body}</p></div>', unsafe_allow_html=True)
