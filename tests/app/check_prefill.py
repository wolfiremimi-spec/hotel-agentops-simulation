import os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__)); import stlite
REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2]); os.chdir(REPO); sys.path.insert(0, REPO)
H, st = stlite.H, sys.modules["streamlit"]
ok = []
def check(n, c, d=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n + ("" if c else f"  [{d}]"))
H.clicks.add("ha_demo"); stlite.run_app("hotel_app.py")
from product import app_state as S, core
today = dt.date.fromisoformat(S.today()); prev = (today - dt.timedelta(days=1)).isoformat()
store = S.get_store(); hid = S.hotel()["id"]
inp = core.blank_inputs(prev); inp["carry_over_items"] = [
    {"item": "Croissants", "group": "pastry_bread", "kg": 3.0, "within_shelf_life": True},
    {"item": "Greek yogurt", "group": "fruit_yogurt", "kg": 2.0, "within_shelf_life": True},
    {"item": "Croissants", "group": "pastry_bread", "kg": 1.0, "within_shelf_life": False}]
store.save_day(hid, prev, status="draft", inputs=inp); S.invalidate()
H.values["td_date"] = today + dt.timedelta(days=1)
H.nav_target = "product/views/today.py"; stlite.run_app("hotel_app.py")
d = (today + dt.timedelta(days=1)).isoformat()
check("prefill button offered", any(o[0] == "button" and "Start carry-over from" in str(o[1]) for o in H.out), [o for o in H.out if o[0]=="button"][:8])
H.clicks.add(f"td_prefill_btn_{d}"); stlite.run_app("hotel_app.py")
pf = H.session_state.get(f"td_prefill_{d}")
check("two unique items prefilled with blank kg", pf and [r["item"] for r in pf] == ["Croissants", "Greek yogurt"] and all(r["kg"] is None for r in pf), pf)
eds = [o for o in H.out if o[0] == "data_editor" and str(o[1]).startswith(f"td_carry_{d}")]
check("carry-over table re-keyed and shows 2 rows", eds and eds[-1][1].endswith("_1") and int(eds[-1][2]) == 2, eds)
print(f"\n{sum(ok)}/{len(ok)} checks passed")
