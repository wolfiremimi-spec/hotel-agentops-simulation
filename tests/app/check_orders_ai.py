import os, sys
sys.path.insert(0, os.path.dirname(__file__)); import stlite
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
import requests
class R:
    status_code = 200
    def json(self):
        return {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": "submit", "args": {
            "explanation": "Cut pastry; add hot line.", "raise_buffer_pct": {"pastry_bread": -10, "hot_line": 9},
            "watch": ["Saturday hot line"]}}}]}}]}
requests.post = lambda *a, **k: R()
from product import core, ordering
from product.ai_agents import AIConfig
p = core.demo_profile(); ev = ordering.evidence(p, [])
cov = ordering.default_covers(ev, ordering.week_dates("2026-10-05"))
rec = ordering.recommend(p, ev, cov, {})
before = {g: l["suggested_kg"] for g, l in rec["lines"].items()}
rv = ordering.ai_review(rec, cov, ev, AIConfig(api_key="x"))
ok = [rv["status"] == "verified",
      rec["lines"]["pastry_bread"]["suggested_kg"] == before["pastry_bread"],
      abs(rec["lines"]["hot_line"]["buffer"] - 0.15) < 1e-9 and rec["lines"]["hot_line"]["suggested_kg"] > before["hot_line"],
      any("decrease" in x for x in rv["rejected"])]
print(rv["changes"], rv["rejected"]); print(f"{sum(ok)}/{len(ok)} AI verification checks passed")
