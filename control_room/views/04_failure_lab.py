import contextlib
import io

import streamlit as st
from control_room import sim, ui
from hotel_agentops_sim.__main__ import failure_matrix

TH = {k: v["value"] for k, v in sim.PARAMS["readiness_thresholds"].items()}
CTX_THRESHOLD = sim.PARAMS["context_completeness_threshold"]["value"]
EV0 = sim.SCENARIO["hotel_data"]["event_schedule"]["events"][0]
EV_CHANGE = EV0["revised_covers"] / EV0["guaranteed_covers"] - 1

# ---------------------------------------------------------------------------
# The case study's failure-mode table (page 8): the requirement each row is checked against.
# "how" describes how failure_matrix() in the repository triggers the row; "kind" says whether it
# runs a full service or evaluates the readiness-gate rules directly; "tests" names the unit tests
# in tests/test_simulation.py that cover the same guarantee.
# ---------------------------------------------------------------------------
SPEC = {
    "Missing PMS data": {
        "required": "Abstain", "match": lambda r: "ABSTAIN" in r.upper(),
        "how": "PMS occupancy source removed", "kind": "Service run",
        "tests": ["test_missing_context_abstains", "test_missing_context_refuses_to_act"]},
    "POS API failure": {
        "required": "Fallback + escalate", "match": lambda r: "FALLBACK" in r.upper() and "ESCALATE" in r.upper(),
        "how": "POS history feed returns an API error", "kind": "Service run", "tests": []},
    "Inventory feed stale": {
        "required": "Block execution", "match": lambda r: r.upper().startswith("BLOCKED"),
        "how": "Inventory feed marked stale", "kind": "Service run",
        "tests": ["test_stale_inventory_blocks_execution"]},
    "Abnormal event demand": {
        "required": "Human review", "match": lambda r: "human decision" in r.lower(),
        "how": f"Case-study scenario as modeled: wedding guarantee {EV0['guaranteed_covers']} → {EV0['revised_covers']} covers "
               f"({EV_CHANGE:+.0%})", "kind": "Service run", "tests": []},
    "Low confidence": {
        "required": "Recommend only", "match": lambda r: "recommend only" in r.lower(),
        "how": "Trailing forecast error raised to 20–28%", "kind": "Service run",
        "tests": ["test_low_confidence_recommends_only"]},
    "Conflicting agents": {
        "required": "Escalate", "match": lambda r: "escalation" in r.lower() or "escalate" in r.lower(),
        "how": "Pastry waste history lowered and standing plan raised, so no waste evidence explains the plan",
        "kind": "Service run", "tests": ["test_unresolved_conflict_escalates"]},
    "High-risk action": {
        "required": "Human approval", "match": lambda r: "human decision" in r.lower() or "manager approves" in r.lower(),
        "how": "Case-study scenario as modeled: banquet resize is HIGH risk, LOW reversibility", "kind": "Service run",
        "tests": ["test_confidence_is_not_authority"]},
    "Policy violation": {
        "required": "Block", "match": lambda r: r.upper().startswith("BLOCKED"),
        "how": "Manager modifies D-0418 to −35%", "kind": "Service run",
        "tests": ["test_human_modification_is_policy_checked"]},
    "Guest score deterioration": {
        "required": "Reduce autonomy", "match": lambda r: "BOUNDED" in r,
        "how": f"Gate evidence with guest F&B score 4.55 (floor {TH['guest_fb_score']:.2f})", "kind": "Gate rule check",
        "tests": ["test_guest_breach_reduces_autonomy"]},
    "Rising overrides": {
        "required": "Reduce autonomy + investigate", "match": lambda r: "BOUNDED" in r and "INVESTIGATE" in r.upper(),
        "how": "Latest weekly override rate set to 23%", "kind": "Gate rule check",
        "tests": ["test_override_drift_reduces_autonomy"]},
}

# ---------------------------------------------------------------------------
# Page-level styles (palette from ui)
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<style>
.fl-sec {{ margin: 2.2rem 0 .6rem; }}
.fl-sec .n {{ font-size: .72rem; font-weight: 700; letter-spacing: .18em; color: {ui.SAND}; }}
.fl-sec .t {{ font-size: 1.25rem; font-weight: 700; color: {ui.FOREST}; margin-top: .1rem; }}
.fl-score {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: .4rem 0 1rem; }}
.fl-score > div {{ background: {ui.FOREST}; color: {ui.WHITE}; border-radius: 6px; padding: 14px 16px; }}
.fl-score b {{ display: block; font-size: 1.9rem; line-height: 1.1; color: {ui.WHITE}; }}
.fl-score span {{ font-size: .82rem; color: {ui.LINEN}; }}
.fl-kicker {{ font-size: .66rem; font-weight: 700; letter-spacing: .16em; color: {ui.SAND}; }}
.fl-big {{ font-size: 1.9rem; font-weight: 700; color: {ui.FOREST}; line-height: 1.1; margin: .5rem 0 .1rem; }}
.fl-big small {{ font-size: .95rem; color: {ui.MUTE}; font-weight: 500; }}
.fl-meaning {{ margin-top: .6rem; color: {ui.FOREST}; font-weight: 600; line-height: 1.4; }}
.fl-quote {{ border-left: 3px solid {ui.SAND}; padding: 6px 14px; margin: 1.4rem 0 .4rem; font-size: 1.1rem;
             font-weight: 600; color: {ui.FOREST}; }}
.fl-ok {{ color: {ui.MOSS}; font-weight: 700; }} .fl-no {{ color: {ui.ALERT}; font-weight: 700; }}
.fl-kind {{ display: inline-block; font-size: .64rem; font-weight: 700; letter-spacing: .06em; padding: 1px 6px; border-radius: 3px;
            border: 1px solid {ui.GRAY}; color: {ui.MUTE}; white-space: nowrap; }}
.fl-tests {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .74rem; color: {ui.MUTE}; }}
@media (max-width: 800px) {{ .fl-score {{ grid-template-columns: 1fr; }} }}
</style>
""",
    unsafe_allow_html=True,
)


def section(num: str, title: str) -> None:
    st.markdown(f'<div class="fl-sec"><div class="n">{ui.e(num)}</div><div class="t">{ui.e(title)}</div></div>',
                unsafe_allow_html=True)


@st.cache_data
def matrix():
    with contextlib.redirect_stdout(io.StringIO()):
        return failure_matrix(sim.PARAMS)


# ---------------------------------------------------------------------------
# The three failure tests (each runs the real engine)
# ---------------------------------------------------------------------------
def test_missing_context():
    s = sim.modified(sim.SCENARIO, hotel_data__pms_occupancy=None)
    res, _, _ = sim.run(s)
    r = res.records[-1]
    ok = r["Execution Status"].startswith("ABSTAINED") and not res.executions
    present = len(res.context.present)
    required = len(res.context.required)
    return {
        "ok": ok,
        "big": f"{res.context.completeness:.1%}", "vs": f"vs {CTX_THRESHOLD:.0%} required",
        "injected": f"PMS occupancy feed removed · {present} of {required} sources",
        "did": [f"Decision {r['Decision ID']}: {r['Execution Status']}",
                "No production recommendation issued · kitchen keeps its standing plan",
                f"Executions attempted: {len(res.executions)}"],
        "meaning": "The system refused to act and escalated to the manager.",
    }


def test_tool_reliability():
    ev = sim.evidence_for("A6")
    g, _level, _ = sim.gate(ev)
    res, _, _ = sim.run(evidence=ev)
    others = [c for c in g["checks"] if c["key"] != "tool_reliability"]
    others_pass = all(c["pass"] for c in others)
    delegated = [r for r in res.records if r["Required Authority"].startswith("Agent executes")]
    ok = g["result"] == "HOLD" and g["first_blocker"] == "Tool reliability" and others_pass and not delegated
    tr = next(c for c in g["checks"] if c["key"] == "tool_reliability")
    low = [r["Decision ID"] for r in res.records if r["Risk"] == "LOW"]
    return {
        "ok": ok,
        "big": f"{tr['value']:.1%}", "vs": f"vs ≥ {tr['threshold']:.0%} required",
        "injected": "Week A6 tool reliability, from the Excel workbook",
        "did": [f"{sum(c['pass'] for c in others)} of {len(others)} other thresholds pass",
                f"Gate {g['result']} · first blocker: {g['first_blocker']} · autonomy {res.autonomy}",
                "Low-risk actions now need manager approval: " + (", ".join(low) or "none")],
        "meaning": "One failed threshold holds autonomy. Strong metrics cannot average it away.",
    }


def test_guest_score():
    ev = sim.evidence_for(None, guest_fb_score=4.55, week="A8 with guest score 4.55 (test)")
    g, _level, _ = sim.gate(ev)
    res, _, _ = sim.run(evidence=ev)
    flagged = [r for r in res.records if r["Decision Type"] == "guardrail_escalation"]
    alone = [r for r in res.records if r["Required Authority"].startswith("Agent executes")]
    ok = g["result"] == "HOLD" and res.autonomy == "BOUNDED" and bool(flagged) and not alone
    return {
        "ok": ok,
        "big": f"{ev['guest_fb_score']:.2f}", "vs": f"vs ≥ {TH['guest_fb_score']:.2f} floor",
        "injected": "Guest F&B score set to 4.55 (test input)",
        "did": [f"Gate {g['result']} · autonomy {res.autonomy}",
                f"Guardrail escalation logged: {flagged[0]['Decision ID'] if flagged else '—'}",
                f"Actions executed without a human: {len(alone)}"],
        "meaning": "Efficiency never outranks the guest guardrail: flag, escalate, reduce autonomy, human review.",
    }


TESTS = [("01", "Missing critical context", test_missing_context),
         ("02", "Tool reliability below threshold", test_tool_reliability),
         ("03", "Guest score below the floor", test_guest_score)]
results = [(num, name, fn()) for num, name, fn in TESTS]

rows = matrix()
checked = []
for failure, detect_rule, response in rows:
    spec = SPEC.get(failure)
    checked.append({"failure": failure, "detection": detect_rule, "response": response, "spec": spec,
                    "match": bool(spec) and spec["match"](response)})
n_tests_pass = sum(r["ok"] for _, _, r in results)
n_match = sum(c["match"] for c in checked)
n_unit = sum(bool(c["spec"] and c["spec"]["tests"]) for c in checked)

# ---------------------------------------------------------------------------
# 01 · Purpose
# ---------------------------------------------------------------------------
ui.header("04", "Failure lab", "A system you can trust is one you have tried to break",
          "The case study defines how the system must behave when data fails, confidence drops or guests are at risk. "
          "Break it yourself, then see every failure mode checked against that specification.")
ui.banner("<b>Modeled implementation simulation · No live hotel systems are connected.</b> Every result below is computed "
          "by the repository's engine when this page loads. Scenario data and results are modeled, not realized hotel performance.")
st.markdown(
    '<div class="fl-score">'
    f'<div><b>{n_tests_pass}/{len(results)}</b><span>failure tests passed</span></div>'
    f'<div><b>{n_match}/{len(checked)}</b><span>failure modes produce the response the case study specifies</span></div>'
    f'<div><b>{n_unit}/{len(checked)}</b><span>also covered by a dedicated unit test in the repository</span></div>'
    "</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 02 · Break it yourself (interactive: any combination, full service run)
# ---------------------------------------------------------------------------
LOW_CONF_APE = [0.25, 0.22, 0.28, 0.20, 0.24, 0.26, 0.21]          # same inputs as failure_matrix()
OVERRIDE_HISTORY = [w["value"] for w in sim.PARAMS["override_rate_history"]]
BREAKS = {
    "PMS feed missing": "pms",
    "POS API failure": "pos",
    "Inventory feed stale": "stale",
    "Low forecast confidence": "conf",
    "Agents disagree": "conflict",
    "Manager cuts 35%": "policy",
    "Guest score drops to 4.55": "guest",
    "Overrides spike to 23%": "drift",
}
BREAK_HELP = {
    "pms": "PMS occupancy data stops arriving.",
    "pos": "The POS history API times out; the last cached extract is used.",
    "stale": "The inventory feed is out of date.",
    "conf": "Recent forecast error rises to 20–28%, so demand confidence falls below 80%.",
    "conflict": "Pastry waste history drops and the standing plan rises, so no waste evidence explains the plan.",
    "policy": "The manager edits the breakfast plan to −35% instead of approving it.",
    "guest": "Readiness evidence shows a guest F&B score of 4.55.",
    "drift": "This week's human override rate jumps to 23%.",
}

if "fl_pick" not in st.session_state:
    st.session_state.fl_pick = []
if "fl_ran" not in st.session_state:
    st.session_state.fl_ran = None


def run_breaks(codes):
    """One full breakfast service with every chosen failure present at once."""
    s = sim.SCENARIO
    failures, choices, evidence, history = {}, {}, None, None
    if "pms" in codes:
        failures["pms_occupancy"] = "missing"
    if "pos" in codes:
        failures["pos_history"] = "api_failure"
    if "stale" in codes:
        failures["inventory"] = "stale"
    if "conf" in codes:
        s = sim.modified(s, hotel_data__pos_history__last_7_services_forecast_ape=LOW_CONF_APE)
    if "conflict" in codes:
        s = sim.modified(s, hotel_data__waste_history__leftover_rate_last_4_saturdays__pastry_bread=[0.1, 0.12, 0.09, 0.11],
                         kitchen_standing_plan_kg__pastry_bread=60.0)
    if "policy" in codes:
        choices["production_adjustment"] = {"choice": "modify", "new_change_pct": -35, "reason": "Forecast disagreement"}
    if "guest" in codes:
        evidence = sim.evidence_for(None, guest_fb_score=4.55, week="A8 with guest score 4.55 (test)")
    if "drift" in codes:
        history = OVERRIDE_HISTORY[:-1] + [0.23]
    res, _, _ = sim.run(s, choices=choices, evidence=evidence, failures=failures, override_history=history)
    return res


def detection(code, res):
    """(detected?, evidence line) read from the run's own traces and autonomy reasons."""
    lines = [ln for t in res.traces.values() for ln in t["governance"]["rule_trace"]]
    abstained = any(r["Execution Status"].startswith("ABSTAINED") for r in res.records)

    def find(fragment):
        return next((ln for ln in lines if fragment in ln), None)

    if code == "pms":
        hit = find("BELOW THRESHOLD")
        return (hit is not None, hit or "PMS feed loaded")
    if code in ("guest", "drift"):
        key = "Guest F&B" if code == "guest" else "Override rate"
        hit = next((w for w in res.autonomy_why if key in w), None)
        return (hit is not None, hit or "")
    if code == "policy":
        rec = next((r for r in res.records if r["Policy Status"].startswith("VIOLATION (modification)")), None)
        if rec:
            return True, f"{rec['Decision ID']} manager edit blocked · {rec['Policy Status']}"
    else:
        hit = find({"pos": "Fallback data in use", "stale": "Stale feed", "conf": "Low confidence",
                    "conflict": "Unresolved conflict"}[code])
        if hit:
            return True, hit
    if abstained:
        return False, "Not reached: the system abstained before any recommendation was made, so this check never ran."
    return False, "Not reached: an earlier rule had already stopped the decision this failure would affect."


def clear_breaks():
    st.session_state.fl_pick = []
    st.session_state.fl_ran = None


section("02", "Break it yourself")
st.write("Choose one failure or several, then run a full breakfast service with all of them present at once. "
         "The engine decides what happens: nothing here is scripted.")
pick = st.pills("Failures to inject", list(BREAKS), selection_mode="multi", key="fl_pick",
                help="Each failure changes one input to the real engine. Pick several to combine them.")
b1, b2, b3 = st.columns([2, 1, 3])
if b1.button("Run the service with these failures", type="primary", use_container_width=True, key="fl_run",
             disabled=not pick):
    st.session_state.fl_ran = list(pick)
b2.button("Clear", use_container_width=True, key="fl_clear", on_click=clear_breaks)
if pick:
    b3.caption(" · ".join(BREAK_HELP[BREAKS[p]] for p in pick))
else:
    b3.caption("Abnormal event demand and a high-risk banquet decision are already part of the case-study morning.")

ran_breaks = st.session_state.fl_ran
if ran_breaks:
    if sorted(ran_breaks) != sorted(pick or []):
        st.warning("Your selection changed. The results below are for the last run: " + ", ".join(ran_breaks) + ".")
    normal, _, _ = sim.run()
    broken = run_breaks([BREAKS[b] for b in ran_breaks])

    def tally(res):
        return {
            "auto": sum(r["Required Authority"].startswith("Agent executes") and r["Execution Status"] == "EXECUTED"
                        for r in res.records),
            "stopped": sum(r["Execution Status"].startswith(("BLOCKED", "ABSTAINED")) for r in res.records),
            "human": sum(r["Human Approval Required"] == "YES" or r["Execution Status"] == "ESCALATED" for r in res.records),
        }

    tn, tb = tally(normal), tally(broken)

    def ftile(label, a, b):
        ch = str(a) != str(b)
        val = f"{ui.e(a)} → <b>{ui.e(b)}</b>" if ch else ui.e(b)
        return (f'<div style="background:{ui.LINEN if ch else ui.WHITE};border:1px solid {ui.LINE};'
                f'border-top:3px solid {ui.SAND if ch else ui.GRAY};border-radius:4px;padding:10px 12px">'
                f'<div style="font-size:.64rem;letter-spacing:.12em;text-transform:uppercase;color:{ui.MUTE}">{ui.e(label)}</div>'
                f'<div style="font-size:1.05rem;font-weight:600;color:{ui.FOREST}">{val}</div></div>')

    st.markdown(f"**Normal morning vs your broken morning** {ui.tag('LIVE SIMULATION')}", unsafe_allow_html=True)
    st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:12px">'
                + ftile("Autonomy level", normal.autonomy, broken.autonomy)
                + ftile("Context completeness", f"{normal.context.completeness:.1%}", f"{broken.context.completeness:.1%}")
                + ftile("Executed without a human", tn["auto"], tb["auto"])
                + ftile("Blocked / abstained", tn["stopped"], tb["stopped"])
                + ftile("Sent to a human", tn["human"], tb["human"])
                + "</div>", unsafe_allow_html=True)

    st.markdown("**What the system detected**")
    det_rows = ""
    for b in ran_breaks:
        ok, line = detection(BREAKS[b], broken)
        mark = '<span class="fl-ok">Detected ✓</span>' if ok else f'<span style="color:{ui.MUTE};font-weight:700">Not reached</span>'
        det_rows += f"<tr><td><b>{ui.e(b)}</b></td><td>{mark}</td><td>{ui.e(line)}</td></tr>"
    st.markdown('<table class="cr-table"><thead><tr><th>Failure</th><th>Result</th><th>Rule that fired (from the trace)</th>'
                "</tr></thead><tbody>" + det_rows + "</tbody></table>", unsafe_allow_html=True)
    st.caption("“Not reached” is a safe outcome, not a miss: an earlier rule already stopped the action, so the later check "
               "had nothing to evaluate. Rules run in order: context, policy, risk, confidence, failure modes, autonomy level.")

    st.markdown("**Every decision in the broken morning**")
    dec_rows = "".join(
        f"<tr><td>{ui.e(r['Decision ID'])}</td><td>{ui.e(sim.TYPE_LABEL.get(r['Decision Type'], r['Decision Type']))}</td>"
        f"<td>{ui.e(r['Required Authority'])}</td><td>{ui.e(r['Execution Status'])}</td></tr>"
        for r in broken.records)
    st.markdown('<table class="cr-table"><thead><tr><th>ID</th><th>Decision</th><th>Authority</th><th>Status</th></tr></thead>'
                "<tbody>" + dec_rows + "</tbody></table>", unsafe_allow_html=True)
    if tb["auto"] == 0:
        st.success("Under these failures, nothing ran without a human. Every action was blocked, withheld or sent to a person.")
    else:
        st.info(f"{tb['auto']} low-risk, reversible action{'s' if tb['auto'] != 1 else ''} still ran on delegated authority: "
                "the failures you chose do not affect those decisions, and the readiness gate still allows delegation.")

# ---------------------------------------------------------------------------
# 03 · Three failure tests
# ---------------------------------------------------------------------------
section("03", "Three failure tests")
st.markdown("Each test breaks one thing the system depends on, then shows what the system did about it. "
            + ui.tag("LIVE SIMULATION"), unsafe_allow_html=True)
cols = st.columns(3)
for col, (num, name, r) in zip(cols, results):
    with col:
        with st.container(border=True):
            st.markdown(f'<div class="fl-kicker">SCENARIO {num}</div>'
                        f"{ui.pill('PASS' if r['ok'] else 'FAIL', 'ok' if r['ok'] else 'hold')} &nbsp;<b>{ui.e(name)}</b>"
                        f'<div class="fl-big">{ui.e(r["big"])} <small>{ui.e(r["vs"])}</small></div>',
                        unsafe_allow_html=True)
            st.caption("Injected: " + r["injected"])
            st.markdown('<div class="cr-trace">' + ui.e("\n".join(r["did"])) + "</div>", unsafe_allow_html=True)
            st.markdown(f'<div class="fl-meaning">{ui.e(r["meaning"])}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 04 · Requirement traceability: all ten failure modes
# ---------------------------------------------------------------------------
section("04", "All ten failure modes: specified vs executed")
st.caption("Left: the response the case study requires (page 8). Right: what the simulation actually did, computed now by "
           "`failure_matrix()`. The check is automatic, so a regression in the engine would show here as ✗.")

body = ""
for i, c in enumerate(checked):
    spec = c["spec"] or {}
    mark = '<span class="fl-ok">✓</span>' if c["match"] else '<span class="fl-no">✗</span>'
    tests = "<br>".join(ui.e(t) for t in spec.get("tests", [])) or "Matrix run only"
    body += (f"<tr><td>{i + 1:02d}</td>"
             f"<td><b>{ui.e(c['failure'])}</b><br><small>{ui.e(spec.get('how', ''))}</small></td>"
             f"<td>{ui.e(c['detection'])}</td>"
             f"<td>{ui.e(spec.get('required', 'Not in case-study table'))}</td>"
             f"<td>{mark} {ui.e(c['response'])}<br><span class=\"fl-kind\">{ui.e(spec.get('kind', ''))}</span></td>"
             f'<td class="fl-tests">{tests}</td></tr>')
st.markdown('<table class="cr-table"><thead><tr><th>#</th><th>Failure · how it was triggered</th><th>Detection</th>'
            "<th>Case study requires</th><th>Simulation response</th><th>Unit test</th></tr></thead><tbody>"
            + body + "</tbody></table>", unsafe_allow_html=True)
st.caption("Service run: a full breakfast service is simulated with the failure present. Gate rule check: the readiness-gate "
           "and drift rules are evaluated directly on the modified evidence. Rows 04 and 07 are part of the case-study "
           "scenario itself, so no extra injection is needed. The repository's 20 automated tests run separately from this page.")

st.markdown('<div class="fl-quote">Knowing when to abstain is a capability, not a failure.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 05 · Why this design?
# ---------------------------------------------------------------------------
section("05", "Why this design?")
ui.why("Missing data leads to abstention, stale data blocks execution, API failures fall back and escalate, event swings go to "
       "humans, and a manager edit that would plan a stockout is blocked by policy.",
       "Failure handling is designed in, not bolted on: every mode has a detection rule and a defined response.",
       "Operators can see exactly how the system behaves on its worst day before they trust it on a normal one.",
       "Treat failure modes as tested requirements, with the same rigor as the happy path.")

# ---------------------------------------------------------------------------
# 06 · Continue
# ---------------------------------------------------------------------------
section("06", "Continue the experience")
cc = st.columns([2, 1])
cc[0].write("Failures reduce authority. The readiness gate is how authority is earned back: all eight metrics must pass, "
            "week by week, before any action runs without a manager.")
if cc[1].button("Readiness Gate & Autonomy →", type="primary", use_container_width=True, key="goto_readiness"):
    st.switch_page("control_room/views/06_readiness_gate.py")
ui.footer()
