import os, sys, copy
sys.path.insert(0, os.path.dirname(__file__)); import stlite
REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2]); os.chdir(REPO); sys.path.insert(0, REPO)
H, st = stlite.H, sys.modules["streamlit"]
ok = []
def check(n, c, d=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n + ("" if c else f"  [{str(d)[:600]}]"))
def text(): return "\n".join(" ".join(map(str, o[1:])) for o in H.out)
run = lambda: stlite.run_app("hotel_app.py")
exec(open(os.path.join(os.path.dirname(__file__), "tour_flow.py")).read())      # demo day planned, closed, order approved
from product import app_state as S, ordering
d0 = next(d for d in S.days() if d["service_date"] == "2026-10-03")
store = S.get_store(); hid = S.hotel()["id"]
c = copy.deepcopy(d0["closeout"]); c["stockout"]["hot_line"] = True
store.save_day(hid, "2026-10-10", status="closed", inputs=d0["inputs"], run=d0["run"], closeout=c); S.invalidate()
H.nav_target = "product/views/orders.py"; H.values["or_start"] = __import__("datetime").date(2026, 10, 12); run(); t = text()
check("results section shows the evaluated week", "How approved orders performed" in t and "Week of 2026-10-05" in t, t[-1500:])
check("accuracy metric shown", "Order accuracy" in t)
check("learning note for the short group", "Hot line ran short" in t or "Hot line" in t and "ran short" in t, t[-800:])
ev = ordering.evidence(S.profile(), S.days())
cls, why = ordering.classify(ev, "hot_line")
check("next suggestion learns: hot line stockout-prone because last order ran short", cls == "stockout_prone" and "last week's order" in why, why)
print(f"\n{sum(ok)}/{len(ok)} checks passed")
