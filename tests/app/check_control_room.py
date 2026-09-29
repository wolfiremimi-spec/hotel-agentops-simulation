import os, sys, glob
sys.path.insert(0, os.path.dirname(__file__)); import stlite
REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2]); os.chdir(REPO); sys.path.insert(0, REPO)
H, st = stlite.H, sys.modules["streamlit"]
ok = []
def check(n, c, d=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n + ("" if c else f"  [{str(d)[:500]}]"))
def text(): return "\n".join(" ".join(map(str, o[1:])) for o in H.out)
def errs(): return [o for o in H.out if o[0] in ("exception",)]
for f in sorted(glob.glob("control_room/views/*.py")):
    H.session_state.clear(); H.values.clear(); H.clicks.clear(); H.nav_target = f
    try:
        stlite.run_app("streamlit_app.py"); check(f"renders {os.path.basename(f)}", not errs(), errs())
    except Exception as ex:
        check(f"renders {os.path.basename(f)}", False, repr(ex))
P = "control_room/views/procurement.py"
H.session_state.clear(); H.values.clear(); H.clicks.clear(); H.nav_target = P
stlite.run_app("streamlit_app.py"); t = text()
check("recommendation shown", "Order less pastry" in t and "Order more hot line" in t, t[-1500:])
check("header numbered 05", "05" in t and "Procurement" in t)
H.clicks.add("pr_p_Quiet week (weekdays −25%)"); stlite.run_app("streamlit_app.py")
check("preset switches", H.session_state["pr_preset"].startswith("Quiet") and H.session_state["pr_v"] == 1)
v = H.session_state["pr_v"]
H.values[f"pr_choice_{v}"] = "Reject"; H.clicks.add("pr_record"); stlite.run_app("streamlit_app.py"); t = text()
check("reject without reason is refused", "pr_decision" not in H.session_state and "Give a reason" in t, t[-600:])
H.values[f"pr_reason_{v}"] = "Supplier minimum"; H.clicks.add("pr_record"); stlite.run_app("streamlit_app.py"); t = text()
check("reject with reason recorded", (H.session_state.get("pr_decision") or {}).get("choice") == "Reject" and "NOT EXECUTED" in t, t[-600:])
H.values[f"pr_choice_{v}"] = "Approve"; H.clicks.add("pr_record"); stlite.run_app("streamlit_app.py"); t = text()
check("approve recorded with order line", "EXECUTED · order sent as suggested" in t and "ORDER " in t, t[-800:])
t = text()
check("run-the-week section after approval", "Run the week" in t and "Order accuracy" in t, t[-1200:])
print(f"\n{sum(ok)}/{len(ok)} checks passed (with loop)")
