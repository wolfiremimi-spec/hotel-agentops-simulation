"""End-to-end: click through the product app (demo + a live workspace on a simulated Supabase)."""
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
import stlite  # noqa: E402

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2])
os.chdir(REPO)
sys.path.insert(0, REPO)
import requests  # noqa: E402

H, st = stlite.H, sys.modules["streamlit"]
APP = "hotel_app.py"
ok = []


def check(n, c, d=""):
    ok.append(bool(c))
    print(("PASS " if c else "FAIL ") + n + (f"  [{str(d)[:300]}]" if d and not c else ""))


def text():
    return "\n".join(" ".join(o[1:]) for o in H.out)


def fresh():
    H.session_state.clear(); H.values.clear(); H.clicks.clear(); H.nav_target = None


def run(**clicks_values):
    return stlite.run_app(APP)


# ---------------------------------------------------------------- simulated Supabase (PostgREST subset)
DB = {"hotels": [], "service_days": [], "audit_events": []}
CALLS = []


class Resp:
    def __init__(self, code, body=None):
        self.status_code, self._b = code, body
        self.text = "" if body is None else json.dumps(body)

    def json(self):
        return self._b


def fake_request(method, url, params=None, json=None, headers=None, timeout=None):
    CALLS.append((method, url, dict(params or {}), headers))
    assert headers["apikey"] == "sb_secret_TEST" and "Authorization" not in headers, headers
    table = url.rsplit("/", 1)[1]
    rows = DB[table]
    params = dict(params or {})
    filt = {k: v[3:] for k, v in params.items() if isinstance(v, str) and v.startswith("eq.")}
    match = [r for r in rows if all(str(r.get(k)) == v for k, v in filt.items())]
    if method == "GET":
        out = match
        if params.get("order", "").startswith("service_date"):
            out = sorted(out, key=lambda r: r["service_date"], reverse=params["order"].endswith("desc"))
        if params.get("order", "").startswith("at"):
            out = sorted(out, key=lambda r: r["at"], reverse=True)
        sel = params.get("select")
        if sel:
            out = [{k: r.get(k) for k in sel.split(",")} for r in out]
        return Resp(200, out)
    if method == "POST":
        body = dict(json)
        if table == "hotels":
            if any(r["access_hash"] == body["access_hash"] for r in rows):
                return Resp(409, {"message": "duplicate"})
            body.setdefault("id", f"h{len(rows) + 1}")
        if table == "audit_events":
            body.setdefault("at", f"2026-10-03T00:00:{len(rows):02d}")
        if params.get("on_conflict"):
            keys = params["on_conflict"].split(",")
            existing = next((r for r in rows if all(r.get(k) == body.get(k) for k in keys)), None)
            if existing:
                existing.update(body)
                return Resp(201, [existing])
        rows.append(body)
        return Resp(201, [body] if "representation" in (headers.get("Prefer") or "") else None)
    if method == "PATCH":
        for r in match:
            r.update(json)
        return Resp(204, None)
    if method == "DELETE":
        DB[table] = [r for r in rows if r not in match]
        return Resp(204, None)
    raise AssertionError(method)


requests.request = fake_request

# ================================================================ A · demo workspace
fresh()
run()
t = text()
check("welcome page: three entry points", all(x in t for x in ["Create a workspace", "Open your workspace", "Explore the demo hotel"]))
check("welcome: honest 'what it isn't' section", "Connected to your PMS, POS or inventory system" in t)
check("no database configured → create/open disabled with a note", "isn't connected on this deployment" in t)

H.clicks.add("ha_demo"); run(); t = text()
print("DEBUG page", getattr(H, "current_page", None), "|", "production plan" in t); check("demo opens on Today's plan", H.current_page == "product/views/today.py")
check("demo banner shown", "Demo workspace." in t)
check("new-hotel autonomy starts SUPERVISED (no own evidence)", "Autonomy today: SUPERVISED" in t, t[:600])
date = H.session_state["td_date"].isoformat() if hasattr(H.session_state["td_date"], "isoformat") else H.session_state["td_date"]
check("demo date is the case-study Saturday", date == "2026-10-03", date)

H.clicks.add("Save this morning's data and ask the agents"); run(); t = text()
radios = [k for k in H.session_state if k.startswith("td_ch_")]
check("agents ran: recommendations rendered", "Recommendations and your decisions" in t and "D-0418" in t)
check("context 100%: all eight sources OK", t.count("OK &nbsp;") == 8 or "Context completeness 100%" in t, t[:400])
check("SUPERVISED → all five decisions need the manager", len(radios) == 5, radios)
check("D-0418 still the case-study recommendation (12.2%, 188 → 165 kg)", "Reduce breakfast production by 12.2% (188 → 165 kg)" in t)
check("draft inputs saved", any(d["status"] == "draft" for d in H.session_state["ha_memory"]["hotels"][H.session_state["ha_hotel"]["id"]]["days"].values()))

H.clicks.add(f"td_submit_{date}"); run(); t = text()
check("submit with no decisions → error, nothing saved", "Decision required for" in t and "Today's plan is saved" not in t)
for k in radios:
    H.values[k] = "Approve"
H.values[[k for k in radios if "purchasing" in k][0]] = "Modify"
H.clicks.add(f"td_submit_{date}"); run()
for k in radios:
    H.values[k] = "Approve"
H.values[[k for k in radios if "purchasing" in k][0]] = "Modify"
H.clicks.add(f"td_submit_{date}"); run(); t = text()
check("approved plan saved and shown", "Today's plan is saved (approved)" in t, t[-800:])
check("kitchen production sheet shown with download", "Kitchen production sheet" in t and any(o[0] == "download" for o in H.out))
check("decisions table shows the modification", "MODIFY" in t)

H.clicks.add(f"td_goto_co_{date}"); run(); t = text()
check("close-out page opened for that date", H.current_page == "product/views/closeout.py" and "What the kitchen served" in t)
H.clicks.add(f"co_fill_{date}"); run()
check("demo fill sets actual covers 409", H.session_state.get(f"co_cov_{date}") == 409)
H.clicks.add("Save the close-out"); run(); t = text()
check("close-out saved: waste 23.3 kg vs 47.3 kg estimate (case study)", "23.3 kg" in t and "47.3 kg" in t, t[-600:])
check("forecast error 2.7%", "2.7%" in t)

H.nav_target = "product/views/decision_log.py"; run(); t = text()
check("decision log lists all five decisions with outcome", "D-0418" in t and "D-0422" in t and "409 actual covers" in t)
check("audit trail shows plan approval and close-out", "plan approved" in t and "service closed out" in t)
check("override (purchase-order modify) became a learning case", "Overrides become learning cases" in t)

H.nav_target = "product/views/performance.py"; run(); t = text()
check("performance: evidence progress shown (5/20 decisions)", "Manager decisions: 5/20" in t, t[:800])
check("performance: waste avoided estimate 24.0 kg", "24.0 kg" in t)

H.nav_target = "product/views/setup.py"; run(); t = text()
check("setup renders with baseline history editor", any(o[0] == "data_editor" and o[1] == "su_hist" for o in H.out))
H.values["su_drange"] = 15
H.clicks.add("Save setup"); run(); t = text()
check("setup saves policy change", H.session_state["ha_hotel"]["profile"]["delegated_range"] == 0.15 and "Setup saved" in t)

H.nav_target = "product/views/copilot.py"; run(); t = text()
check("copilot without key: clear message, no crash", "isn't switched on" in t)

H.clicks.add("ha_leave"); H.nav_target = None; run(); t = text()
check("leaving returns to welcome", "Explore the demo hotel" in t and H.session_state.get("ha_hotel") is None)

# ================================================================ B · live workspace on the database
fresh()
st.secrets.update({"SUPABASE_URL": "https://abc.supabase.co", "SUPABASE_SECRET_KEY": "sb_secret_TEST", "APP_SALT": "pepper"})
run(); t = text()
check("database configured → create enabled", "isn't connected on this deployment" not in t)
H.clicks.add("Create workspace"); run(); t = text()
check("create without a name → error", "Please enter your hotel's name." in t)
H.values.update({"ha_new_name": "Harbour View Hotel", "ha_new_rooms": 180, "ha_new_approver": "Maria Lopez"})
H.clicks.add("Create workspace"); run(); t = text()
code = H.session_state.get("ha_new_code")
check("workspace created in the database", len(DB["hotels"]) == 1 and DB["hotels"][0]["name"] == "Harbour View Hotel")
check("access code shown once, only its hash stored",
      code and code in t and code not in json.dumps(DB) and len(DB["hotels"][0]["access_hash"]) == 64)
H.clicks.add("ha_code_ack"); run(); t = text()
check("code dismissed after acknowledging", "ha_new_code" not in H.session_state and code not in t)

H.nav_target = "product/views/today.py"; run()
d2 = H.session_state["td_date"].isoformat()
H.values.update({f"td_occ_{d2}": 150, f"td_bi_{d2}": 110, f"td_invage_{d2}": 3.0, f"td_gs_{d2}": 4.7, f"td_evok_{d2}": True})
H.clicks.add("Save this morning's data and ask the agents"); run(); t = text()
check("new hotel without history: warns it will abstain", "doesn't have 4 previous" in t, t[-900:])
check("…and the engine abstains (context 75% < 95%)", "ABSTAINED" in t and "Context completeness 75%" in t)
H.clicks.add(f"td_submit_{d2}"); run(); t = text()
check("abstention day saved to the database", any(r["service_date"] == d2 and r["status"] == "approved" for r in DB["service_days"]))
check("kitchen told to use standing par", "abstained this morning" in t)

hash_before = DB["hotels"][0]["access_hash"]
H.clicks.add("ha_leave"); H.nav_target = None; run()
H.values["ha_code_in"] = "wrong-code"; H.clicks.add("Open"); run(); t = text()
check("wrong code rejected", "No workspace matches that code" in t)
H.values["ha_code_in"] = code.lower().replace("-", " ")
H.clicks.add("Open"); run(); t = text()
check("reopen with the code (any case/spacing) → same hotel and its saved day",
      H.session_state.get("ha_hotel", {}).get("name") == "Harbour View Hotel" and "Today's plan is saved" in t, t[:500])
check("every DB call used the secret key on the apikey header only", all(c[3]["apikey"] == "sb_secret_TEST" for c in CALLS))
check("audit events written (created + plan approved)", len(DB["audit_events"]) == 2, len(DB["audit_events"]))

# database failure is shown, not a crash
real = requests.request
requests.request = lambda *a, **k: Resp(500, {"message": "boom"})
H.nav_target = "product/views/decision_log.py"; H.session_state.pop("ha_days", None); r = run(); t = text()
check("database error → friendly message, page still renders", "Database error (HTTP 500)" in t, t[-400:])
requests.request = real
print(f"\n{sum(ok)}/{len(ok)} checks passed")
