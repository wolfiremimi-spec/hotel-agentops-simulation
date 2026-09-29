"""AI agents: verification, permissions, fallback, parallelism and caching, against a simulated Gemini."""
import copy
import json
import os
import sys
import threading
import time

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2])
os.chdir(REPO)
sys.path.insert(0, REPO)
import requests  # noqa: E402

from product import core  # noqa: E402
from product.ai_agents import AIConfig  # noqa: E402

ok = []


def check(n, c, d=""):
    ok.append(bool(c))
    print(("PASS " if c else "FAIL ") + n + (f"  [{str(d)[:400]}]" if d and not c else ""))


class R:
    def __init__(self, code, body=None):
        self.status_code, self._b = code, body or {}

    def json(self):
        return self._b


def fc(name, args, cid="x"):
    return R(200, {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": name, "id": cid, "args": args}}]}}]})


SCRIPT = {}          # agent keyword -> list of (args for read calls...) then submit args
LOG, TIMES, MODE = [], {}, {"fail": None, "sleep": 0.0}
LOCK = threading.Lock()


def which(system):
    for k in ("Demand Agent", "Inventory Agent", "Waste Agent", "Production Agent", "Orchestrator"):
        if f"You are the {k}" in system:
            return k


def fake_post(url, timeout=None, headers=None, json=None):
    agent = which(json["systemInstruction"]["parts"][0]["text"])
    with LOCK:
        LOG.append({"agent": agent, "body": copy.deepcopy(json)})
        TIMES.setdefault(agent, []).append(time.time())
    if MODE["sleep"]:
        time.sleep(MODE["sleep"])
    if MODE["fail"]:
        return R(MODE["fail"])
    rounds = sum(1 for c in json["contents"] if c["role"] == "model")
    plan = SCRIPT[agent]
    step = plan[min(rounds, len(plan) - 1)]
    return fc(*step)


requests.post = fake_post
p = core.demo_profile()
base_inputs = core.demo_inputs(p)
from control_room import sim  # noqa: E402
ref, _, _ = sim.run()
GATE = (ref.gate, ref.autonomy, ref.autonomy_why)


def run(inputs=None, choices=None, cfg=None):
    cfg = cfg or AIConfig(api_key="k", models=["gemini-test"])
    res, pending, scen, meta = core.run_morning(p, inputs or base_inputs, [], choices, "F&B Manager", GATE, "08:02", ai=cfg)
    return res, meta, cfg


def good_script(covers=450):
    SCRIPT.clear()
    SCRIPT.update({
        "Demand Agent": [("read_source", {"source": "reservations"}), ("read_source", {"source": "inventory"}),
                         ("get_rule_based_analysis", {}),
                         ("submit", {"expected_covers": covers, "confidence_adjustment": -0.03,
                                     "rationale": "Front desk notes a 40-guest tour group, all breakfast-inclusive.",
                                     "evidence": ["front_desk_notes"]})],
        "Inventory Agent": [("read_source", {"source": "inventory"}),
                            ("submit", {"exclude_carry_over_groups": ["fruit_yogurt"],
                                        "rationale": "Kitchen notes: yogurt tub left out overnight."})],
        "Waste Agent": [("read_source", {"source": "waste_history"}),
                        ("submit", {"chronic_overproduction": ["pastry_bread", "hot_line"], "stockout_prone": [],
                                    "rationale": "Pastry chronic; I also think hot line is overproduced."})],
        "Production Agent": [("submit", {"buffers": {"pastry_bread": 0.5, "hot_line": 0.05, "fruit_yogurt": 0.08,
                                                     "cold_cuts_cheese": 0.08}, "rationale": "Tight on hot line."})],
        "Orchestrator": [("submit", {"escalate": False, "note": "Signals combine sensibly."})],
    })


# 1 · all agents answer
good_script()
inputs = dict(base_inputs, front_desk_notes="Tour group of 40 arriving tonight, all breakfast-inclusive.",
              kitchen_notes="Greek yogurt tub left out overnight, discard.")
LOG.clear(); TIMES.clear()
res, meta, cfg = run(inputs)
reps = {r["agent"]: r for r in meta["ai_agents"]}
check("all five AI roles ran and reported", set(reps) == {"Demand Agent", "Inventory Agent", "Waste Agent", "Production Agent", "Orchestrator"}, list(reps))
denied = [c for e in LOG if e["agent"] == "Demand Agent" for c in e["body"]["contents"]
          for part in c["parts"] if "functionResponse" in part and "PERMISSION DENIED" in json.dumps(part)]
check("Demand Agent reading inventory was DENIED by the engine's least-privilege view", bool(denied))
got_notes = [c for e in LOG if e["agent"] == "Demand Agent" for c in e["body"]["contents"]
             for part in c["parts"] if "functionResponse" in part and "Tour group of 40" in json.dumps(part)]
check("Demand Agent read the front-desk notes through its tool", bool(got_notes))
check("demand adjustment within ±15% accepted (420 → 450)", reps["Demand Agent"]["status"] == "adjusted" and "420 → 450" in reps["Demand Agent"]["changes"][0], reps["Demand Agent"])
d418 = res.records[0]
check("the plan reflects the AI forecast (D-0418 no longer the 188 → 165 kg cut)", "188 → 165" not in d418["Recommendation"], d418["Recommendation"])
check("AI lowered its confidence (never raised): 92.7% → 89.7%", d418["Confidence"] == "89.7%", d418["Confidence"])
check("Inventory Agent excluded the yogurt carry-over (can only reduce stock)", reps["Inventory Agent"]["status"] == "adjusted"
      and res.traces["D-0418"]["details"]["usable_carry_over_kg"]["fruit_yogurt"] == 0.0)
wv = " ".join(reps["Waste Agent"]["verification"])
check("Waste Agent: hot line 'chronic' REJECTED (avg leftover 2% < 15%)", "hot_line chronic rejected" in wv, wv)
check("Waste Agent: dropping the hot-line stockout flag was refused (safety)", "kept stockout-prone flags" in wv, wv)
pv = " ".join(reps["Production Agent"]["verification"])
check("Production Agent: 50% pastry buffer clamped to 15%, hot line raised to 12% (stockout-prone)",
      "pastry_bread buffer 50% → 15%" in pv and "hot_line buffer 5% → 12%" in pv, pv)
chg = abs(res.traces["D-0418"]["details"]["change"])
expected_auth = "Agent executes (delegated)" if chg <= 0.10 else "Agent recommends · manager approves"
check(f"governance still decides from the rules: {chg:.1%} change → {d418['Risk']} risk → {expected_auth}",
      d418["Required Authority"] == expected_auth and (d418["Risk"] == "LOW") == (chg <= 0.10), (chg, d418["Risk"], d418["Required Authority"]))
check("policy check still passes (no planned stockout possible)", d418["Policy Status"] == "PASS")
starts = {a: min(t) for a, t in TIMES.items()}

# 2 · parallel execution of the three specialists
good_script()
MODE["sleep"] = 0.3
LOG.clear(); TIMES.clear()
t0 = time.time()
run(dict(base_inputs, front_desk_notes="parallel test"))
MODE["sleep"] = 0.0
first = {a: min(t) for a, t in TIMES.items()}
spread = max(first[a] for a in ("Demand Agent", "Inventory Agent", "Waste Agent")) - min(first[a] for a in ("Demand Agent", "Inventory Agent", "Waste Agent"))
check("Demand, Inventory and Waste agents start in parallel (case study: asyncio.gather)", spread < 0.15, f"spread {spread:.2f}s")

# 3 · out-of-bounds forecast is rejected, rule-based used
good_script(covers=600)
res2, meta2, _ = run(dict(base_inputs, front_desk_notes="huge conference"))
r2 = {r["agent"]: r for r in meta2["ai_agents"]}["Demand Agent"]
check("forecast of 600 (+43%) REJECTED by verification → statistical 420 covers used",
      r2["status"] == "rejected" and res2.traces[res2.records[0]["Decision ID"]]["details"]["expected_covers"] == 420, r2)

# 4 · orchestrator can escalate, never de-escalate
good_script()
SCRIPT["Orchestrator"] = [("submit", {"escalate": True, "note": "Tour group plus wedding swing: have the chef confirm."})]
res3, meta3, _ = run(dict(base_inputs, front_desk_notes="escalate test"))
check("AI orchestrator escalation → D-0418 becomes a mandatory human decision",
      res3.records[0]["Required Authority"] == "Human decision · mandatory escalation", res3.records[0]["Required Authority"])
check("…and the rule trace says why", any("AI orchestrator escalated" in l for l in res3.traces[res3.records[0]["Decision ID"]]["governance"]["rule_trace"]))

# 5 · model unavailable → every agent falls back, result identical to the rule-based engine
MODE["fail"] = 429
res4, meta4, _ = run(dict(base_inputs, front_desk_notes="outage"))
MODE["fail"] = None
keys = ["Decision ID", "Recommendation", "Required Authority", "Confidence", "Execution Status"]
check("AI outage → all five report 'fallback'", all(r["status"] == "fallback" for r in meta4["ai_agents"]), [r["status"] for r in meta4["ai_agents"]])
check("…and decisions are identical to the rule-based engine (the kitchen always gets a plan)",
      [[r[k] for k in keys] for r in res4.records] == [[r[k] for k in keys] for r in ref.records])

# 6 · caching: the saved plan uses exactly the proposals the manager reviewed
good_script()
cfg = AIConfig(api_key="k", models=["gemini-test"])
LOG.clear()
a, _, _ = run(dict(inputs, front_desk_notes="cache test"), None, cfg)
n_calls = len(LOG)
SCRIPT["Demand Agent"][-1] = ("submit", {"expected_covers": 430, "rationale": "different answer"})
b, meta_b, _ = run(dict(inputs, front_desk_notes="cache test"), {"production_adjustment": {"choice": "approve"}}, cfg)
check("preview and approval reuse the same AI proposals (no new model calls)", len(LOG) == n_calls, f"{n_calls} → {len(LOG)}")
check("…so the approved plan equals the reviewed plan", a.records[0]["Recommendation"] == b.records[0]["Recommendation"])

# 7 · rule-based mode unchanged
res5, _, _, meta5 = core.run_morning(p, base_inputs, [], None, "F&B Manager", GATE, "08:02", ai=None)
check("rule-based mode reproduces the case study exactly",
      [[r[k] for k in keys] for r in res5.records] == [[r[k] for k in keys] for r in ref.records] and meta5["ai_agents"] == [])
print(f"\n{sum(ok)}/{len(ok)} checks passed")
