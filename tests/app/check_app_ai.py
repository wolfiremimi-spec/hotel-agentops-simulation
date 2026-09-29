import os, sys, copy, json
sys.path.insert(0, os.path.dirname(__file__)); import stlite
REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2]); os.chdir(REPO); sys.path.insert(0, REPO)
import requests
H, st = stlite.H, sys.modules["streamlit"]
ok = []
def check(n, c, d=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (f"  [{str(d)[:300]}]" if d and not c else ""))
class R:
    def __init__(s, c, b): s.status_code, s._b = c, b
    def json(s): return s._b
def fc(n, a): return R(200, {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": n, "id": "i", "args": a}}]}}]})
SCRIPT = {"Demand Agent": [("read_source", {"source": "reservations"}), ("submit", {"expected_covers": 445, "rationale": "Tour group of 40 in the front-desk notes."})],
          "Inventory Agent": [("submit", {"exclude_carry_over_groups": [], "rationale": "Stock looks fine."})],
          "Waste Agent": [("submit", {"chronic_overproduction": ["pastry_bread", "hot_line"], "stockout_prone": ["hot_line"], "rationale": "Pastry chronic."})],
          "Production Agent": [("submit", {"buffers": {"pastry_bread": 0.03, "hot_line": 0.12, "fruit_yogurt": 0.08, "cold_cuts_cheese": 0.08}, "rationale": "Standard."})],
          "Orchestrator": [("submit", {"escalate": False, "note": "Consistent."})]}
calls = []
def fake(url, timeout=None, headers=None, json=None):
    sysmsg = json["systemInstruction"]["parts"][0]["text"]
    agent = next((k for k in SCRIPT if f"You are the {k}" in sysmsg), None)
    calls.append(agent)
    rounds = sum(1 for c in json["contents"] if c["role"] == "model")
    step = SCRIPT[agent][min(rounds, len(SCRIPT[agent]) - 1)]
    return fc(*step)
requests.post = fake
st.secrets.clear(); st.secrets["GEMINI_API_KEY"] = "k"
H.session_state.clear(); H.values.clear(); H.nav_target = None
stlite.run_app("hotel_app.py"); t = "\n".join(" ".join(o[1:]) for o in H.out)
check("welcome describes AI specialist agents", "four AI" in t and "Demand Agent" in t)
H.clicks.add("ha_demo"); stlite.run_app("hotel_app.py")
date = "2026-10-03"
H.values[f"td_fdnotes_{date}"] = "Tour group of 40 arriving tonight, all breakfast-inclusive."
H.clicks.add("Save this morning's data and ask the agents"); stlite.run_app("hotel_app.py")
t = "\n".join(" ".join(o[1:]) for o in H.out)
check("agent panel shows AI mode", "AI agents (Gemini) with output verification" in t)
check("Waste Agent's unsupported claim shown as verified/adjusted with the rejection reason", "hot_line chronic rejected" in t, t[-1500:])
check("Demand Agent adjustment shown (420 → 445)", "covers 420 → 445" in t)
check("notes were saved with the morning's inputs", any("Tour group" in json.dumps(d.get("inputs")) for d in H.session_state["ha_memory"]["hotels"][H.session_state["ha_hotel"]["id"]]["days"].values()))
n = len(calls)
radios = [k for k in H.session_state if k.startswith("td_ch_")]
for k in radios: H.values[k] = "Approve"
H.clicks.add(f"td_submit_{date}"); stlite.run_app("hotel_app.py")
for k in radios: H.values[k] = "Approve"
H.clicks.add(f"td_submit_{date}"); stlite.run_app("hotel_app.py")
t = "\n".join(" ".join(o[1:]) for o in H.out)
day = H.session_state["ha_memory"]["hotels"][H.session_state["ha_hotel"]["id"]]["days"][date]
check("plan saved with all five agent reports", day["status"] == "approved" and len(day["run"]["ai_agents"]) == 5, day["status"])
check("approval reused the reviewed AI proposals (no new model calls)", len(calls) == n, (n, len(calls)))
check("saved view offers the agents' reasoning", "How the agents reasoned · AI agents" in t)
H.nav_target = "product/views/decision_log.py"; stlite.run_app("hotel_app.py"); t = "\n".join(" ".join(o[1:]) for o in H.out)
check("decision log shows the agent mode and reasoning for that morning", "Agents that morning: AI agents" in t and "Tour group of 40" in t)
H.nav_target = "product/views/setup.py"; stlite.run_app("hotel_app.py")
H.values["su_mode"] = "Rule-based agents"; H.clicks.add("Save setup"); stlite.run_app("hotel_app.py")
check("setup can switch to rule-based agents", H.session_state["ha_hotel"]["profile"]["agent_mode"] == "rules")
print(f"\n{sum(ok)}/{len(ok)} checks passed")
