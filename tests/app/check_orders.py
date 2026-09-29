import os, sys, json, copy
sys.path.insert(0, os.path.dirname(__file__)); import stlite
REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2]); os.chdir(REPO); sys.path.insert(0, REPO)
H, st = stlite.H, sys.modules["streamlit"]
ok = []
def check(n, c, d=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n + ("" if c else f"  [{str(d)[:400]}]"))
def text(): return "\n".join(" ".join(map(str, o[1:])) for o in H.out)
H.clicks.add("ha_demo"); stlite.run_app("hotel_app.py")
H.nav_target = "product/views/orders.py"; stlite.run_app("hotel_app.py"); t = text()
check("orders page renders", "Suggested order" in t and "Approve the order" in t, t[-1500:])
check("rule-based explanation mentions ordering less pastry and more hot line", "Order less pastry" in t and "Order more hot line" in t, t[-2500:])
check("no errors", not any(o[0] in ("error", "exception") for o in H.out), [o for o in H.out if o[0] in ("error","exception")])
# approve unchanged order
from product import app_state as S
import datetime as dt
from product import ordering
wk = ordering.next_monday(S.today())
H.clicks.add("Approve and log this order"); stlite.run_app("hotel_app.py"); t = text()
orders = S.profile().get("orders", [])
check("order approved and stored", orders and orders[-1]["week_start"] == wk, (orders, t[-800:]))
audit = S.get_store().list_audit(S.hotel()["id"])
check("approval in audit trail", any(a["action"] == "supplier_order_approved" for a in audit), [a["action"] for a in audit])
check("purchase order download offered", ("Download the purchase order for " + wk) in str(H.out), [o for o in H.out if "ownload" in str(o)])
print(f"\n{sum(ok)}/{len(ok)} checks passed")
