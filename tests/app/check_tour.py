import os, sys
sys.path.insert(0, os.path.dirname(__file__)); import stlite
REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2]); os.chdir(REPO); sys.path.insert(0, REPO)
H, st = stlite.H, sys.modules["streamlit"]
ok = []
def check(n, c, d=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n + ("" if c else f"  [{str(d)[:500]}]"))
def text(): return "\n".join(" ".join(map(str, o[1:])) for o in H.out)
run = lambda: stlite.run_app("hotel_app.py")
from product import tour
H.clicks.add("ha_demo"); run(); t = text()
check("step 1 hint on Today", "step 1 of 6" in t and "Save the morning" in t, t[:900])
check("sidebar shows 0/6", "Guided tour** · 0/6" in t, [l for l in t.splitlines() if "tour" in l.lower()][:5])
H.nav_target = "product/views/decision_log.py"; run()
check("visiting the log early does not tick it", not tour.status()["log"])
H.nav_target = "product/views/today.py"; run()
date = "2026-10-03"
H.clicks.add("Save this morning's data and ask the agents"); run(); t = text()
check("step 2 hint after saving data", "step 2 of 6" in t)
radios = [k for k in H.session_state if k.startswith("td_ch_")]
for k in radios: H.values[k] = "Approve"
H.clicks.add(f"td_submit_{date}"); run(); t = text()
check("plan saved → tour at 2/6", "Guided tour** · 2/6" in t, [l for l in t.splitlines() if "Guided" in l])
H.clicks.add(f"td_goto_co_{date}"); run(); t = text()
check("step 3 hint on close-out", "step 3 of 6" in t)
H.clicks.add(f"co_fill_{date}"); run(); H.clicks.add("Save the close-out"); run()
H.nav_target = "product/views/decision_log.py"; run(); t = text()
check("step 4 hint shown on log and then ticked", "step 4 of 6" in t and tour.status()["log"])
H.nav_target = "product/views/performance.py"; run(); t = text()
check("step 5 ticked on performance", tour.status()["autonomy"])
H.nav_target = "product/views/orders.py"; run(); t = text()
check("step 6 hint on orders", "step 6 of 6" in t, t[:600])
H.clicks.add("Approve and log this order"); run(); t = text()
check("tour complete", "Tour complete" in t and all(tour.status().values()), tour.status())
H.clicks.add("ha_tour_hide"); run(); t = text()
check("tour can be hidden", "Guided tour" not in t)
print(f"\n{sum(ok)}/{len(ok)} checks passed")
