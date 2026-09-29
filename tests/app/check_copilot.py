import json
import os, sys, json, copy
sys.path.insert(0, os.path.dirname(__file__)); import stlite
REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2]); os.chdir(REPO); sys.path.insert(0, REPO)
import requests
H, st = stlite.H, sys.modules["streamlit"]
ok = []
def check(n, c, d=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (f"  [{str(d)[:300]}]" if d and not c else ""))
class R:
    def __init__(s, c, b): s.status_code, s._b = c, b
    def json(s): return s._b
calls, script = [], []
requests.post = lambda url, **k: (json.dumps(k["json"]), calls.append(copy.deepcopy(k["json"])), script.pop(0))[2]
def fc(name, args): return R(200, {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": name, "id": "c1", "args": args}}]}}]})
def tx(t): return R(200, {"candidates": [{"content": {"role": "model", "parts": [{"text": t}]}}]})
st.secrets.clear(); st.secrets["GEMINI_API_KEY"] = "k"
H.session_state.clear(); H.values.clear(); H.nav_target = None
stlite.run_app("hotel_app.py"); H.clicks.add("ha_demo"); stlite.run_app("hotel_app.py"); H.session_state["ha_hotel"]["profile"]["agent_mode"] = "rules"
H.clicks.add("Save this morning's data and ask the agents"); stlite.run_app("hotel_app.py")
hid = H.session_state["ha_hotel"]["id"]; mem = H.session_state["ha_memory"]["hotels"][hid]
before = copy.deepcopy(mem["days"])
H.nav_target = "product/views/copilot.py"
script += [fc("what_if", {"inventory_age_hours": 14}), tx("D-0418 would be **blocked**: stale inventory.")]
H.chat_input_value = "What if inventory was counted 14 hours ago?"; stlite.run_app("hotel_app.py")
res = calls[1]["contents"][2]["parts"][0]["functionResponse"]["response"]["result"]
check("what_if ran the real engine on this hotel's morning (stale → BLOCKED)", res["decisions"][0]["status"] == "BLOCKED" and res["stale"] == ["inventory", "shelf_life"], res.get("decisions", res))
check("what_if saved nothing", mem["days"] == before)
check("answer shown with 'Show the work'", "blocked" in "\n".join(" ".join(o[1:]) for o in H.out) and any(o[0] == "expander" for o in H.out))
check("system prompt says DEMO workspace", "DEMO workspace" in calls[0]["systemInstruction"]["parts"][0]["text"])
script += [fc("get_performance", {}), tx("Autonomy is SUPERVISED.")]
H.chat_input_value = "Why SUPERVISED?"; stlite.run_app("hotel_app.py")
perf = calls[-1]["contents"][-1]["parts"][0]["functionResponse"]["response"]["result"]
check("get_performance returns the earned-autonomy gaps", perf["autonomy"] == "SUPERVISED" and perf["evidence_gaps"], perf)
script += [fc("get_decision", {"decision_id": "D-9999"}), tx("No such decision.")]
H.chat_input_value = "Explain D-9999"; stlite.run_app("hotel_app.py")
check("unknown decision → tool error to the model, no crash", "error" in calls[-1]["contents"][-1]["parts"][0]["functionResponse"]["response"]["result"])
print(f"\n{sum(ok)}/{len(ok)} checks passed")
