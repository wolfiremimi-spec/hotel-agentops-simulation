import copy

import streamlit as st
from control_room import sim, ui

# ---------------------------------------------------------------------------
# Case-study baseline (D-0418). Every default below is read from the scenario
# and parameter files, never typed in, so the page cannot drift from the model.
# ---------------------------------------------------------------------------
S0 = sim.SCENARIO
hd = S0["hotel_data"]
ev0 = hd["event_schedule"]["events"][0]
WEEKS = list(sim.PARAMS["gate_evidence_by_week"])
FEED_OPTIONS = ["OK", "Missing", "Stale", "API failure"]
FEED_MODE = {"Missing": "missing", "Stale": "stale", "API failure": "api_failure"}

DEFAULTS = {
    "lab_occ": hd["pms_occupancy"]["occupied_rooms"],
    "lab_ape": round(sum(hd["pos_history"]["last_7_services_forecast_ape"]) / 7 * 100, 1),
    "lab_pastry": round(sum(hd["waste_history"]["leftover_rate_last_4_saturdays"]["pastry_bread"]) / 4 * 100),
    "lab_stockouts": hd["waste_history"]["stockouts_last_4_saturdays"]["hot_line"],
    "lab_yogurt": float(hd["inventory"]["near_expiry"][0]["kg"]),
    "lab_wedding": ev0["revised_covers"],
    "lab_cth": int(round(sim.PARAMS["context_completeness_threshold"]["value"] * 100)),
    "lab_drange": int(round(sim.PARAMS["delegated_prep_range"]["value"] * 100)),
    "lab_week": WEEKS[-1],
}
for _s in sim.SOURCES:
    DEFAULTS[f"feed_{_s}"] = "OK"

INPUT_LABEL = {
    "lab_occ": "Occupied rooms",
    "lab_ape": "Recent forecast error (%)",
    "lab_pastry": "Pastry & bread leftover (%)",
    "lab_stockouts": "Hot-line stockouts (of 4)",
    "lab_yogurt": "Near-expiry Greek yogurt (kg)",
    "lab_wedding": "Wedding brunch covers",
    "lab_cth": "Context completeness required (%)",
    "lab_drange": "Delegated production range (± %)",
    "lab_week": "Readiness evidence week",
}
for _s in sim.SOURCES:
    INPUT_LABEL[f"feed_{_s}"] = f"{sim.SOURCE_LABEL[_s]} feed"

# Stress tests only set existing controls. The engine calculates every result.
PRESETS = [
    ("demand", "Demand drop", {"lab_occ": 150},
     "PMS reports 150 occupied rooms instead of 231."),
    ("forecast", "Forecast failure", {"lab_ape": 22.0},
     "Recent forecast error rises to 22%, so demand confidence falls below 80%."),
    ("wedding", "Wedding surge", {"lab_wedding": 180},
     f"Sunday wedding brunch revised to 180 covers against a {ev0['guaranteed_covers']}-cover guarantee."),
    ("stale", "Stale inventory", {"feed_inventory": "Stale"},
     "The inventory feed is out of date."),
    ("outage", "Data outage", {"feed_pms_occupancy": "Missing", "feed_reservations": "Missing"},
     "PMS occupancy and reservations stop arriving."),
    ("evidence", "Weak evidence", {"lab_week": "A6"},
     "Readiness evidence from week A6 instead of the latest week."),
]
PRESET_BY_ID = {p[0]: p for p in PRESETS}

# ---------------------------------------------------------------------------
# Session state: controls, last scenario run, active preset
# ---------------------------------------------------------------------------
for _k, _v in DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v
if "lab_ran" not in st.session_state:
    st.session_state.lab_ran = None
if "lab_preset" not in st.session_state:
    st.session_state.lab_preset = None


def current_inputs() -> dict:
    return {k: st.session_state[k] for k in DEFAULTS}


def apply_preset(preset_id: str) -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    for k, v in PRESET_BY_ID[preset_id][2].items():
        st.session_state[k] = v
    st.session_state.lab_preset = preset_id
    st.session_state.lab_ran = current_inputs()


def reset_to_case_study() -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    st.session_state.lab_preset = None
    st.session_state.lab_ran = None


def record_manual_run() -> None:
    inputs = current_inputs()
    st.session_state.lab_ran = inputs
    match = [pid for pid, _, changes, _ in PRESETS if inputs == {**DEFAULTS, **changes}]
    st.session_state.lab_preset = match[0] if match else None


# ---------------------------------------------------------------------------
# Presentation helpers (palette and classes come from ui)
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<style>
.lab-sec {{ margin: 2.2rem 0 .6rem; }}
.lab-sec .n {{ font-size: .72rem; font-weight: 700; letter-spacing: .18em; color: {ui.SAND}; }}
.lab-sec .t {{ font-size: 1.25rem; font-weight: 700; color: {ui.FOREST}; margin-top: .1rem; }}
.lab-headline {{ background: {ui.FOREST}; color: {ui.WHITE}; border-radius: 6px; padding: 16px 20px; margin-bottom: 12px; }}
.lab-headline b {{ display: block; font-size: .7rem; letter-spacing: .18em; color: {ui.SAND}; margin-bottom: 4px; }}
.lab-headline span {{ font-size: 1.3rem; font-weight: 700; line-height: 1.3; }}
.lab-headline p {{ margin: 6px 0 0; font-size: .92rem; color: {ui.LINEN}; }}
.lab-tiles {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px; }}
.lab-tile {{ background: {ui.WHITE}; border: 1px solid {ui.LINE}; border-top: 3px solid {ui.GRAY}; border-radius: 4px; padding: 10px 12px; }}
.lab-tile.ch {{ border-top-color: {ui.SAND}; background: {ui.LINEN}; }}
.lab-tile b {{ display: block; font-size: .64rem; letter-spacing: .12em; text-transform: uppercase; color: {ui.MUTE}; margin-bottom: 4px; }}
.lab-tile .v {{ font-size: 1.05rem; font-weight: 700; color: {ui.FOREST}; }}
.lab-tile .v s {{ color: {ui.MUTE}; font-weight: 500; text-decoration: none; }}
.lab-auth {{ border-left: 3px solid {ui.SAND}; background: {ui.LINEN}; padding: 10px 14px; margin-bottom: 8px; border-radius: 0 4px 4px 0; }}
.lab-auth b {{ color: {ui.FOREST}; }}
.lab-auth .arrow {{ color: {ui.SAND}; font-weight: 700; padding: 0 6px; }}
.lab-chain {{ display: grid; grid-template-columns: repeat(5, 1fr); border: 1px solid {ui.LINE}; border-radius: 6px; overflow: hidden; margin-bottom: 12px; }}
.lab-chain > div {{ padding: 10px 12px; border-right: 1px solid {ui.LINE}; background: {ui.WHITE}; font-size: .86rem; line-height: 1.45; }}
.lab-chain > div:last-child {{ border-right: 0; }}
.lab-chain b {{ display: block; font-size: .62rem; letter-spacing: .14em; text-transform: uppercase; color: {ui.MOSS}; margin-bottom: 4px; }}
.lab-cmp tr.ch td {{ background: {ui.LINEN}; }}
.lab-cmp tr.ch td:first-child {{ border-left: 3px solid {ui.SAND}; }}
@media (max-width: 800px) {{ .lab-tiles {{ grid-template-columns: repeat(2, 1fr); }} .lab-chain {{ grid-template-columns: 1fr; }}
  .lab-chain > div {{ border-right: 0; border-bottom: 1px solid {ui.LINE}; }} }}
</style>
""",
    unsafe_allow_html=True,
)


def section(num: str, title: str) -> None:
    st.markdown(f'<div class="lab-sec"><div class="n">{ui.e(num)}</div><div class="t">{ui.e(title)}</div></div>',
                unsafe_allow_html=True)


def fmt_input(key: str, value) -> str:
    if key == "lab_ape":
        return f"{float(value):.1f}%"
    if key in ("lab_pastry", "lab_cth"):
        return f"{value}%"
    if key == "lab_drange":
        return f"±{value}%"
    if key == "lab_yogurt":
        return f"{float(value):.1f} kg"
    return str(value)


# ---------------------------------------------------------------------------
# 01 · Purpose
# ---------------------------------------------------------------------------
ui.header("03", "Scenario lab", "Change the hotel's morning. Watch the decisions change.",
          "Stress-test the operating model by changing demand, forecast quality, waste history, event demand, data reliability "
          "or governance policy. Then see how the same decision system changes its recommendations, authority, escalation "
          "behavior and modeled outcomes.")
ui.banner("<b>Modeled implementation simulation · No live hotel systems are connected.</b> The case-study scenario (D-0418) "
          "is modeled, and every what-if input is your assumption. Agents are rule-based Python, not a language model.")
ui.flow(["Change the conditions", "Run the same operating model", "See what changed", "Understand why",
         "Trace it to the evidence"])

# ---------------------------------------------------------------------------
# 02 · Try a stress test
# ---------------------------------------------------------------------------
section("02", "Try a stress test")
st.caption("Each test changes one condition from the case study and runs the real engine. Nothing is pre-calculated.")
pc = st.columns(len(PRESETS))
for i, (pid, label, _changes, desc) in enumerate(PRESETS):
    pc[i].button(label, key=f"preset_{pid}", help=desc, on_click=apply_preset, args=(pid,), use_container_width=True,
                 type="primary" if st.session_state.lab_preset == pid else "secondary")
active = PRESET_BY_ID.get(st.session_state.lab_preset)
rc = st.columns([3, 1])
rc[0].caption(f"Active stress test: **{active[1]}** · {active[3]}" if active else
              "Hover a stress test to see the single condition it changes.")
rc[1].button("Reset to case study", key="preset_reset", help="Restore every control to the D-0418 case-study values.",
             on_click=reset_to_case_study, use_container_width=True)

# ---------------------------------------------------------------------------
# 03 · Your assumptions
# ---------------------------------------------------------------------------
section("03", "Your assumptions")
st.caption("Scenario Lab isolates system behavior. Manager responses are held constant so changes can be attributed to "
           "scenario inputs and governance rules. Use Live Service: You Decide to make the human decisions yourself.")

with st.form("lab"):
    t_hotel, t_feeds, t_gov = st.tabs(["Hotel conditions", "Data feeds", "Governance & readiness"])
    with t_hotel:
        c = st.columns(3)
        c[0].slider("Occupied rooms (of 250)", 120, 250, key="lab_occ")
        c[1].slider("Recent forecast error, trailing 7 services (%)", 2.0, 30.0, step=0.5, key="lab_ape",
                    help="Sets forecast confidence (1 − error). Below 80% confidence the system may only recommend.")
        c[2].slider("Pastry & bread leftover, last 4 Saturdays (%)", 0, 45, key="lab_pastry")
        c = st.columns(3)
        c[0].slider("Hot-line stockouts, last 4 Saturdays", 0, 4, key="lab_stockouts")
        c[1].slider("Near-expiry Greek yogurt (kg)", 0.0, 15.0, step=0.5, key="lab_yogurt")
        c[2].slider(f"Wedding brunch revised covers (guarantee {ev0['guaranteed_covers']})", 60, 180, key="lab_wedding",
                    help="More than a 25% change vs the guarantee counts as abnormal event demand (human review).")
    with t_feeds:
        c = st.columns(4)
        for i, s in enumerate(sim.SOURCES):
            c[i % 4].selectbox(sim.SOURCE_LABEL[s], FEED_OPTIONS, key=f"feed_{s}")
        st.caption("Missing lowers context completeness · Stale blocks execution of inventory-dependent actions · "
                   "API failure falls back to the last cached extract and escalates.")
    with t_gov:
        c = st.columns(3)
        c[0].slider("Context completeness required (%)", 75, 100, key="lab_cth",
                    help="Below this share of the eight required sources, the system abstains and escalates.")
        c[1].slider("Delegated production range (± %)", 5, 25, key="lab_drange",
                    help="Changes inside this range are LOW risk and may run without a manager (if the gate allows).")
        c[2].selectbox("Readiness evidence week", WEEKS, key="lab_week",
                       help="Sets today's autonomy level through the eight-metric readiness gate.")

    # ---------------------------------------------------------------------------
    # 04 · Run my scenario
    # ---------------------------------------------------------------------------
    st.form_submit_button("Run my scenario", type="primary", use_container_width=True, on_click=record_manual_run)

ran = st.session_state.lab_ran
if ran is None:
    st.info("Pick a stress test or set your own assumptions, then press **Run my scenario**.")
    ui.footer()
    st.stop()

# ---------------------------------------------------------------------------
# Run the case study and the scenario through the same engine
# ---------------------------------------------------------------------------
s = copy.deepcopy(S0)
h = s["hotel_data"]
h["pms_occupancy"]["occupied_rooms"] = ran["lab_occ"]
h["pos_history"]["last_7_services_forecast_ape"] = [ran["lab_ape"] / 100] * 7
h["waste_history"]["leftover_rate_last_4_saturdays"]["pastry_bread"] = [ran["lab_pastry"] / 100] * 4
h["waste_history"]["stockouts_last_4_saturdays"]["hot_line"] = ran["lab_stockouts"]
h["inventory"]["near_expiry"][0]["kg"] = ran["lab_yogurt"]
h["event_schedule"]["events"][0]["revised_covers"] = ran["lab_wedding"]
failures = {src: FEED_MODE[ran[f"feed_{src}"]] for src in sim.SOURCES if ran[f"feed_{src}"] != "OK"}
params = sim.params_with(context_threshold=ran["lab_cth"] / 100, delegated_range=ran["lab_drange"] / 100)

base, _, _ = sim.run()
try:
    mine, _, _ = sim.run(s, params=params, evidence=sim.evidence_for(ran["lab_week"]), failures=failures)
except Exception as ex:                                          # a combination the engine does not support
    st.error(f"This combination could not be simulated ({type(ex).__name__}: {ex}). Try restoring a data feed.")
    ui.footer()
    st.stop()

changed_inputs = [k for k in DEFAULTS if ran[k] != DEFAULTS[k]]
if st.session_state.lab_preset:
    run_label = f"Stress test: {PRESET_BY_ID[st.session_state.lab_preset][1]}"
elif changed_inputs:
    run_label = "Your custom scenario"
else:
    run_label = "Case-study values"


def production_record(res):
    """The breakfast decision, or the abstention that replaced it."""
    return next((r for r in res.records if r["Decision Type"] in ("production_adjustment", "abstain_missing_context")), None)


def outcome(res) -> dict:
    rec = production_record(res)
    return (rec or {}).get("_outcome_actual") or {}


def counts(res) -> dict:
    return {
        "human": sum(r["Human Approval Required"] == "YES" for r in res.records),
        "auto": sum(r["Required Authority"].startswith("Agent executes") and r["Execution Status"] == "EXECUTED"
                    for r in res.records),
        "blocked": sum(r["Execution Status"].startswith(("BLOCKED", "ABSTAINED")) for r in res.records),
        "escalated": sum(r["Escalation"] == "YES" for r in res.records),
    }


def keyed(res) -> dict:
    """Match decisions by type (and order within a type): IDs renumber when a decision appears or disappears."""
    out, seen = {}, {}
    for r in res.records:
        t = r["Decision Type"]
        seen[t] = seen.get(t, 0) + 1
        out[(t, seen[t])] = r
    return out


def dlabel(r) -> str:
    return sim.TYPE_LABEL.get(r["Decision Type"], r["Decision Type"])


LEVEL_RANK = {"BOUNDED": 0, "SUPERVISED": 1, "DELEGATED": 2}
cb, cm = counts(base), counts(mine)
ob, om = outcome(base), outcome(mine)
kb, km = keyed(base), keyed(mine)
auth_changes = [(kb[k], km[k]) for k in kb if k in km and kb[k]["Required Authority"] != km[k]["Required Authority"]]
status_changes = [(kb[k], km[k]) for k in kb if k in km and kb[k]["Execution Status"] != km[k]["Execution Status"]
                  and kb[k]["Required Authority"] == km[k]["Required Authority"]]
dropped = [kb[k] for k in kb if k not in km]
added = [km[k] for k in km if k not in kb]
changed_keys = {k for k in km if k not in kb or km[k]["Required Authority"] != kb[k]["Required Authority"]
                or km[k]["Execution Status"] != kb[k]["Execution Status"]
                or km[k]["Recommendation"] != kb[k]["Recommendation"]}

# ---------------------------------------------------------------------------
# 05 · What changed?
# ---------------------------------------------------------------------------
section("05", "What changed?")
st.markdown(f"Results for **{ui.e(run_label)}**, compared with the case study. " + ui.tag("MODELED SIMULATION"),
            unsafe_allow_html=True)

if LEVEL_RANK[mine.autonomy] < LEVEL_RANK[base.autonomy] or cm["auto"] < cb["auto"] or cm["blocked"] > cb["blocked"]:
    headline = "The system reduced its authority"
elif LEVEL_RANK[mine.autonomy] > LEVEL_RANK[base.autonomy] or cm["auto"] > cb["auto"]:
    headline = "Your policy delegated more authority to the agents"
elif auth_changes or dropped or added:
    headline = "Decision rights shifted"
elif changed_keys or ob != om:
    headline = "Same decision rights, different plan"
else:
    headline = "No material change"

if headline == "No material change":
    sub = ("The scenario stayed within the same decision and governance boundaries as the case study: same authority, "
           "same actions, same modeled outcome.")
else:
    parts = []
    if mine.autonomy != base.autonomy:
        parts.append(f"autonomy {base.autonomy} → {mine.autonomy}")
    if cm["auto"] != cb["auto"]:
        parts.append(f"decisions executed without a human {cb['auto']} → {cm['auto']}")
    if cm["blocked"] != cb["blocked"]:
        parts.append(f"blocked or abstained {cb['blocked']} → {cm['blocked']}")
    if len(auth_changes):
        parts.append(f"{len(auth_changes)} decision{'s' if len(auth_changes) != 1 else ''} changed authority")
    if dropped or added:
        parts.append(f"{len(base.records)} → {len(mine.records)} decisions raised")
    sub = ("Compared with the case study: " + "; ".join(parts) + ".") if parts else \
        "Authority is unchanged, but the recommendation or its modeled outcome moved."
st.markdown(f'<div class="lab-headline"><b>HEADLINE</b><span>{ui.e(headline)}</span><p>{ui.e(sub)}</p></div>',
            unsafe_allow_html=True)


def tile(label: str, a, b) -> str:
    ch = str(a) != str(b)
    val = f"<s>{ui.e(a)} →</s> {ui.e(b)}" if ch else ui.e(b)
    return f'<div class="lab-tile{" ch" if ch else ""}"><b>{ui.e(label)}</b><div class="v">{val}</div></div>'


def kg(o, key):
    return f"{o[key]:.1f} kg" if o and o.get(key) is not None else "—"


def stockouts_text(o):
    if not o:
        return "—"
    return str(len(o.get("stockouts", [])))


tiles = [
    tile("Autonomy level", base.autonomy, mine.autonomy),
    tile("Readiness gate", base.gate["result"], mine.gate["result"]),
    tile("Context completeness", f"{base.context.completeness:.0%}", f"{mine.context.completeness:.0%}"),
    tile("Executed without a human", cb["auto"], cm["auto"]),
    tile("Needing a human", cb["human"], cm["human"]),
    tile("Blocked / abstained", cb["blocked"], cm["blocked"]),
    tile("Breakfast waste (modeled)", kg(ob, "waste_kg"), kg(om, "waste_kg")),
    tile("Stockouts (modeled)", stockouts_text(ob), stockouts_text(om)),
    tile("Guest F&B score (modeled)", f"{ob['guest_fb_score']:.2f}" if ob else "—",
         f"{om['guest_fb_score']:.2f}" if om else "—"),
]
st.markdown('<div class="lab-tiles">' + "".join(tiles) + "</div>", unsafe_allow_html=True)

if auth_changes:
    st.markdown("**Authority changed**")
    for rb, rm in auth_changes:
        st.markdown(f'<div class="lab-auth"><b>{ui.e(rm["Decision ID"])} · {ui.e(dlabel(rm))}</b><br>'
                    f'{ui.e(rb["Required Authority"])}<span class="arrow">→</span>{ui.e(rm["Required Authority"])}'
                    f' &nbsp;·&nbsp; {ui.e(rm["Execution Status"])}</div>', unsafe_allow_html=True)
for rb, rm in status_changes:
    st.markdown(f'<div class="lab-auth"><b>{ui.e(rm["Decision ID"])} · {ui.e(dlabel(rm))}</b><br>'
                f'Execution {ui.e(rb["Execution Status"])}<span class="arrow">→</span>{ui.e(rm["Execution Status"])}</div>',
                unsafe_allow_html=True)
if dropped:
    st.caption("No longer raised in your scenario: " + " · ".join(dlabel(r) for r in dropped))
if added:
    st.caption("New in your scenario: " + " · ".join(f"{r['Decision ID']} {dlabel(r)}" for r in added))

hotel_inputs = {"lab_occ", "lab_ape", "lab_pastry", "lab_stockouts", "lab_yogurt", "lab_wedding"}
if ob and hotel_inputs.intersection(changed_inputs):
    st.caption(f"Outcomes are scored against the case study's modeled service ({ob['actual_covers']} actual covers). "
               "Changing the inputs changes what the system plans and who may approve it, not how many guests came.")

# ---------------------------------------------------------------------------
# 06 · Why did it change?
# ---------------------------------------------------------------------------
section("06", "Why did it change?")

if not changed_inputs:
    st.write("Every input matches the case study, so the engine reproduces the case-study decisions exactly.")
else:
    st.markdown("**Your inputs:** " + " · ".join(
        f"{ui.e(INPUT_LABEL[k])} {ui.e(fmt_input(k, DEFAULTS[k]))} → **{ui.e(fmt_input(k, ran[k]))}**"
        for k in changed_inputs), unsafe_allow_html=True)

g1, g2 = st.columns(2)
with g1:
    gate_lines = [f"READINESS GATE (evidence week {ran['lab_week']}): {mine.gate['result']}",
                  f"First blocker: {mine.gate['first_blocker']}"]
    for chk in mine.gate["checks"]:
        if not chk["pass"]:
            v, t = chk["value"], chk["threshold"]
            vv = f"{v:.2f}" if chk["key"] == "guest_fb_score" else (f"{v:.0f}" if chk["key"] == "policy_violations" else f"{v:.1%}")
            tt = f"{t:.2f}" if chk["key"] == "guest_fb_score" else (f"{t:.0f}" if chk["key"] == "policy_violations" else f"{t:.0%}")
            gate_lines.append(f"✗ {chk['metric']} {vv} (needs {chk['test']} {tt})")
    gate_lines += [f"→ {w}" for w in mine.autonomy_why]
    gate_lines.append("Rule: all eight metrics must pass. No single strong metric grants additional authority.")
    st.markdown('<div class="cr-trace">' + ui.e("\n".join(gate_lines)) + "</div>", unsafe_allow_html=True)
with g2:
    ctx_lines = [f"CONTEXT: {len(mine.context.present)}/{len(mine.context.required)} sources · completeness "
                 f"{mine.context.completeness:.0%} (requirement {ran['lab_cth']}%)"]
    for label, names in (("Missing", mine.context.missing), ("Stale", mine.context.stale),
                         ("Fallback (API failure)", mine.context.fallback)):
        if names:
            ctx_lines.append(f"{label}: " + ", ".join(sim.SOURCE_LABEL.get(n, n) for n in names))
    if mine.context.completeness < ran["lab_cth"] / 100:
        ctx_lines.append("→ Below requirement: the system abstains and escalates instead of recommending.")
    elif not (mine.context.missing or mine.context.stale or mine.context.fallback):
        ctx_lines.append("All required sources loaded.")
    ctx_lines.append(f"Delegated production range: ±{ran['lab_drange']}% (changes inside it are LOW risk).")
    st.markdown('<div class="cr-trace">' + ui.e("\n".join(ctx_lines)) + "</div>", unsafe_allow_html=True)

explain = [(kb.get(k), km[k]) for k in km if k in changed_keys]
if explain:
    st.markdown("**Input → rule → authority → action → modeled outcome**")
    st.caption("Rules shown are the governance lines that fired in your scenario but not in the case study, "
               "taken directly from the decision's rule trace.")
    for rb, rm in explain:
        t_mine = mine.traces[rm["Decision ID"]]["governance"]["rule_trace"]
        t_base = base.traces[rb["Decision ID"]]["governance"]["rule_trace"] if rb else []
        new_rules = [x for x in t_mine if x not in t_base and not x.startswith(("Context completeness ", "FINAL:"))]
        if not new_rules:
            new_rules = [x for x in t_mine if x.startswith("Risk ")] or ["Same rules as the case study"]
        rec_text = rm["Recommendation"] if not rb or rb["Recommendation"] == rm["Recommendation"] else \
            f"{rm['Recommendation']} (case study: {rb['Recommendation']})"
        cells = [
            ("Decision", f"{ui.e(rm['Decision ID'])} · {ui.e(dlabel(rm))}<br>{ui.e(rec_text)}"),
            ("Rule that fired", "<br>".join(ui.e(x) for x in new_rules)),
            ("Authority", ui.e(rm["Required Authority"]) + (f"<br><small>was {ui.e(rb['Required Authority'])}</small>"
                                                             if rb and rb["Required Authority"] != rm["Required Authority"] else "")),
            ("Action", ui.e(rm["Final Action"]) + f"<br><small>{ui.e(rm['Execution Status'])}</small>"),
            ("Modeled outcome", ui.e(rm["Actual Outcome"] or "—")),
        ]
        st.markdown('<div class="lab-chain">' + "".join(f"<div><b>{a}</b>{b}</div>" for a, b in cells) + "</div>",
                    unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 07 · Case study vs your scenario
# ---------------------------------------------------------------------------
section("07", "Case-study scenario vs your scenario")


def summary(res):
    prod = production_record(res)
    act = (prod or {}).get("_outcome_actual") or {}
    c_ = counts(res)
    return {"Autonomy level": res.autonomy, "Readiness gate": f"{res.gate['result']} (first blocker: {res.gate['first_blocker']})",
            "Context completeness": f"{res.context.completeness:.0%}", "Decisions logged": len(res.records),
            "Needing a human": c_["human"], "Executed without a human": c_["auto"], "Blocked / abstained": c_["blocked"],
            "Escalated": c_["escalated"],
            "Production decision": prod["Recommendation"] if prod else "—",
            "Production authority": prod["Required Authority"] if prod else "—",
            "Production status": prod["Execution Status"] if prod else "—",
            "Actual waste (kg)": act.get("waste_kg", "—"),
            "Waste under standing plan (kg)": act.get("counterfactual_waste_kg", "—"),
            "Stockouts": ", ".join(sim.GROUP_LABEL.get(x, x) for x in act.get("stockouts", [])) or ("none" if act else "—"),
            "Guest F&B score": act.get("guest_fb_score", "—")}


a_, b_ = summary(base), summary(mine)
rows_html = "".join(
    f'<tr class="{"ch" if str(a_[k]) != str(b_[k]) else ""}"><td>{ui.e(k)}</td><td>{ui.e(a_[k])}</td>'
    f'<td>{ui.e(b_[k])}</td><td>{"● changed" if str(a_[k]) != str(b_[k]) else ""}</td></tr>'
    for k in a_)
st.markdown('<table class="cr-table lab-cmp"><thead><tr><th>Measure</th><th>Case study (D-0418)</th><th>Your scenario</th>'
            '<th></th></tr></thead><tbody>' + rows_html + "</tbody></table>", unsafe_allow_html=True)
st.caption("Both columns are computed by the same engine on this page. " + ui.tag("MODELED SIMULATION"),
           unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 08 · Why this design?
# ---------------------------------------------------------------------------
section("08", "Why this design?")
bp = next((r for r in base.records if r["Decision Type"] == "production_adjustment"), None)
if bp is not None:
    bd = base.traces[bp["Decision ID"]]["details"]
    evidence_text = (f"{bp['Decision ID']} carries {bp['Confidence']} confidence yet still needs the manager: a "
                     f"{abs(bd['change']):.1%} production change is {bp['Risk']} risk because it exceeds the "
                     f"±{sim.PARAMS['delegated_prep_range']['value']:.0%} delegated range. High confidence does not itself grant authority.")
else:
    evidence_text = "High confidence does not itself grant authority: risk, reversibility, policy and context decide who may act."
ui.why(evidence_text,
       "Autonomy is conditional. It depends on the data, the stakes, and the system's recent track record—not on model confidence alone.",
       "No single strong metric grants additional authority. All eight readiness checks must pass, and autonomy moves "
       "BOUNDED → SUPERVISED → DELEGATED only on evidence. Full autonomy is not the goal.",
       "Keep governance parameters explicit and adjustable, and test every policy change in simulation before it reaches a live kitchen.")

# ---------------------------------------------------------------------------
# 09 · Every decision in your scenario
# ---------------------------------------------------------------------------
section("09", "Every decision in your scenario")
st.caption("● marks a decision that differs from the case study.")
for key, r in km.items():
    mark = "● " if key in changed_keys else ""
    tr = mine.traces[r["Decision ID"]]
    with st.expander(f"{mark}{r['Decision ID']} · {dlabel(r)} → {r['Required Authority']} · {r['Execution Status']}"):
        st.markdown(f"**Recommendation:** {ui.e(r['Recommendation'])}  \n"
                    f"**Reason:** {ui.e(tr['recommendation']['reason'])}  \n"
                    f"**Agents:** {ui.e(r['Agent(s)'])}")
        m = st.columns(4)
        m[0].markdown(f"**Confidence**  \n{r['Confidence']}")
        m[1].markdown(f"**Risk · reversibility**  \n{r['Risk']} · {r['Reversibility']}")
        m[2].markdown(f"**Human required**  \n{r['Human Approval Required']}")
        m[3].markdown(f"**Escalated**  \n{r['Escalation']}")
        st.markdown(f"**Policy:** {ui.e(r['Policy Status'])}  \n**Final action:** {ui.e(r['Final Action'])} → "
                    f"{ui.e(r['Execution Status'])}")
        st.markdown('<div class="cr-trace">' + ui.e("\n".join(tr["governance"]["rule_trace"])) + "</div>",
                    unsafe_allow_html=True)
        if r["Actual Outcome"]:
            st.caption("Modeled outcome: " + r["Actual Outcome"])

# ---------------------------------------------------------------------------
# 10 · Continue the experience
# ---------------------------------------------------------------------------
section("10", "Continue the experience")
cc = st.columns([2, 1])
cc[0].write("Scenario Lab held the manager's responses constant. In Live Service you take the manager's seat: "
            "approve, modify, reject or ask for more context, and see the modeled result of your own calls.")
if cc[1].button("Live Service: You Decide →", type="primary", use_container_width=True, key="goto_live_service"):
    st.switch_page("control_room/views/02_live_service.py")
ui.footer()
