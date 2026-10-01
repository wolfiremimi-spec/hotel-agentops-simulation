"""A hanging AI service must never make the morning wait: agents fall back within the time budget."""
import os, sys, time
sys.path.insert(0, os.path.dirname(__file__)); import stlite  # noqa
REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2]); os.chdir(REPO); sys.path.insert(0, REPO)
import requests
calls = []
def hang(url, timeout=None, **k):
    calls.append(timeout); time.sleep(min(timeout, 30)); raise requests.Timeout("simulated hang")
requests.post = hang
from product import core
from product.ai_agents import AIConfig
ok = []
def check(n, c, d=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n + ("" if c else f"  [{d}]"))
p = core.demo_profile(); i = core.demo_inputs(p)
cfg = AIConfig(api_key="x", budget_s=4)
t0 = time.monotonic(); res, pending, scen, meta = core.run_morning(p, i, [], None, "F&B Manager", None, ai=cfg); dt = time.monotonic() - t0
check("hanging AI: morning finishes within the budget", dt < 7, round(dt, 1))
check("every agent fell back to its rule-based analysis", all(r["status"] == "fallback" for r in cfg.reports), [(r["agent"], r["status"]) for r in cfg.reports])
check("still the case-study recommendation", any("12.2%" in r["Recommendation"] for r in res.records))
n = len(calls); t0 = time.monotonic()
core.run_morning(p, i, [], None, "F&B Manager", None, ai=AIConfig(api_key="x", budget_s=4, cache=cfg.cache, state=cfg.state))
check("re-run (saving decisions) doesn't wait again", time.monotonic() - t0 < 1.5 and len(calls) == n, (round(time.monotonic() - t0, 1), len(calls) - n))
print(f"\n{sum(ok)}/{len(ok)} checks passed")
