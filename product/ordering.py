"""Next week's supplier order: a governed recommendation built from the hotel's own close-outs.

The rules compute the order (transparent, reproducible). An optional AI Procurement Agent explains it and may only
make it safer for guests: it can raise a group's buffer, never lower an order below expected consumption.
Every order needs a manager's approval (purchasing is a manager decision in the case study's decision rights).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from statistics import mean

from product import core

GROUPS = core.GROUPS
LABEL = core.GROUP_LABEL
LOOKBACK = 8                   # recorded services used for waste and stockout patterns
BUFFER = {"stockout_prone": 0.12, "chronic_overproduction": 0.03, "normal": 0.06}
MAX_BUFFER = 0.15              # same ceiling as the morning Production Agent
CHRONIC_LEFTOVER_PCT = 15.0    # same threshold the Waste Agent uses


def next_monday(today: str) -> str:
    d = dt.date.fromisoformat(today)
    return (d + dt.timedelta(days=(7 - d.weekday()) % 7 or 7)).isoformat()


def week_dates(start: str) -> list[str]:
    d = dt.date.fromisoformat(start)
    return [(d + dt.timedelta(days=i)).isoformat() for i in range(7)]


def evidence(profile: dict, days: list[dict]) -> dict:
    """Patterns from the hotel's recorded services (baseline history + close-outs), most recent first."""
    rows = [r for r in core.history(profile, days) if r.get("covers")]
    recent = rows[:LOOKBACK]
    left = {g: [r["leftover_pct"][g] for r in recent if (r.get("leftover_pct") or {}).get(g) is not None] for g in GROUPS}
    outs = {g: sum(1 for r in recent if (r.get("stockout") or {}).get(g)) for g in GROUPS}
    learned = [r["consumption_kg_per_cover"] for r in rows if r.get("consumption_kg_per_cover")][:LOOKBACK]
    per_cover = dict(profile["consumption_kg_per_cover"])
    per_cover_source = "hotel setup"
    if len(learned) >= core.HISTORY_NEEDED:
        per_cover = {g: round(mean(x[g] for x in learned), 4) for g in GROUPS}
        per_cover_source = f"learned from the last {len(learned)} close-outs"
    by_wd = {}
    for r in rows:
        by_wd.setdefault(core.weekday(r["date"]), []).append(r["covers"])
    return {"services": len(recent), "avg_leftover_pct": {g: round(mean(v), 1) if v else None for g, v in left.items()},
            "stockouts": outs, "per_cover": per_cover, "per_cover_source": per_cover_source,
            "covers_by_weekday": {wd: round(mean(v[:4])) for wd, v in by_wd.items()},
            "covers_all": round(mean(r["covers"] for r in rows[:LOOKBACK])) if rows else None}


def default_covers(ev: dict, dates: list[str]) -> list[dict]:
    out = []
    for d in dates:
        wd = core.weekday(d)
        if wd in ev["covers_by_weekday"]:
            out.append({"date": d, "day": wd, "expected_covers": ev["covers_by_weekday"][wd],
                        "basis": f"average of recent {wd}s"})
        elif ev["covers_all"]:
            out.append({"date": d, "day": wd, "expected_covers": ev["covers_all"],
                        "basis": f"no {wd} history yet: average of all recorded services"})
        else:
            out.append({"date": d, "day": wd, "expected_covers": None, "basis": "no history: enter your estimate"})
    return out


def classify(ev: dict, g: str) -> tuple[str, str]:
    if ev["stockouts"][g]:
        n = ev["stockouts"][g]
        return "stockout_prone", f"ran out in {n} of the last {ev['services']} recorded services"
    lp = ev["avg_leftover_pct"][g]
    if lp is not None and lp >= CHRONIC_LEFTOVER_PCT:
        return "chronic_overproduction", f"{lp:.0f}% left over on average (≥ {CHRONIC_LEFTOVER_PCT:.0f}% is chronic)"
    return "normal", ("no stockouts; " + (f"{lp:.0f}% average leftover" if lp is not None else "no leftover data yet"))


def recommend(profile: dict, ev: dict, covers: list[dict], on_hand: dict, buffers: dict | None = None) -> dict:
    """The rule-based order for the week, per item group, against ordering at standing par. `buffers` overrides the
    default buffer per pattern (clamped to 2–15%, the Production Agent's range)."""
    buffers = {k: min(max(float((buffers or {}).get(k, v)), 0.02), MAX_BUFFER) for k, v in BUFFER.items()}
    total_covers = sum(int(c["expected_covers"] or 0) for c in covers)
    cost = float(profile["waste_cost_per_kg"])
    lines = {}
    for g in GROUPS:
        cls, why = classify(ev, g)
        buf = buffers[cls]
        need = total_covers * ev["per_cover"][g]
        oh = max(float(on_hand.get(g) or 0.0), 0.0)
        suggested = max(need * (1 + buf) - oh, 0.0)
        standing = max(float(profile["standing_plan_kg"][g]) * len(covers) - oh, 0.0)
        lines[g] = {"group": g, "label": LABEL[g], "pattern": cls, "why": why, "expected_use_kg": round(need, 1),
                    "buffer": buf, "on_hand_kg": round(oh, 1), "suggested_kg": round(suggested, 1),
                    "standing_par_kg": round(standing, 1), "difference_kg": round(standing - suggested, 1),
                    "ai_raise": 0.0}
    avoided = sum(max(l["difference_kg"], 0.0) for l in lines.values())
    return {"lines": lines, "total_covers": total_covers, "per_cover_source": ev["per_cover_source"],
            "waste_avoided_estimate_kg": round(avoided, 1), "waste_cost_avoided_estimate": round(avoided * cost, 2)}


# ---------------------------------------------------------------------------
# AI Procurement Agent (optional): explains, and may only raise buffers for guest safety
# ---------------------------------------------------------------------------
SYSTEM = """You are the Procurement Agent for a hotel breakfast kitchen, inside a governed multi-agent system.
The rules have already computed next week's supplier order per item group from the hotel's own close-outs.
Your job: explain the order to the F&B manager in plain language, and flag risks.
You may RAISE a group's safety buffer (at most +5 percentage points, total buffer at most 15%) if the evidence shows a
guest-experience risk the rules may underweight (e.g. repeated stockouts, a busy week). You may never lower an order.
Call `submit` once. Keep the explanation under 120 words: what to order less of and why, what to order more of and why,
and one line on what to watch. Use only the numbers provided; do not invent prices or supplier details."""


def _decl():
    return [{"name": "submit", "description": "Submit your explanation and any buffer increases.",
             "parameters": {"type": "object", "properties": {
                 "explanation": {"type": "string"},
                 "raise_buffer_pct": {"type": "object", "properties": {g: {"type": "number"} for g in GROUPS}},
                 "watch": {"type": "array", "items": {"type": "string"}}}, "required": ["explanation"]}}]


def ai_review(rec: dict, covers: list[dict], ev: dict, cfg) -> dict:
    """Returns {"status", "model", "explanation", "watch", "changes", "error"}; applies verified raises to `rec`."""
    from product import agent as llm
    brief = {"week": [{"date": c["date"], "day": c["day"], "expected_covers": c["expected_covers"]} for c in covers],
             "evidence": {"recorded_services": ev["services"], "avg_leftover_pct": ev["avg_leftover_pct"],
                          "stockouts": ev["stockouts"], "per_cover_source": ev["per_cover_source"]},
             "order": {g: {k: l[k] for k in ("pattern", "why", "expected_use_kg", "buffer", "on_hand_kg", "suggested_kg",
                                             "standing_par_kg")} for g, l in rec["lines"].items()}}
    key = "order:" + hashlib.sha256(json.dumps(brief, sort_keys=True, default=str).encode()).hexdigest()[:24]
    if key in cfg.cache:
        args = cfg.cache[key]
    else:
        try:
            data = llm.call_model([{"role": "user", "parts": [{"text": json.dumps(brief, default=str)}]}], SYSTEM,
                                  _decl(), cfg.api_key, cfg.models, cfg.state)
            parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            call = next((p["functionCall"] for p in parts if "functionCall" in p), None)
            if call is None:
                text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                if not text:
                    raise llm.AgentError("the model returned no analysis")
                args = {"explanation": text}
            else:
                args = call.get("args") or {}
        except llm.AgentError as ex:
            return {"status": "fallback", "model": None, "explanation": None, "watch": [], "changes": [], "error": str(ex)}
        cfg.cache[key] = args
    changes, rejected = [], []
    for g, pct in (args.get("raise_buffer_pct") or {}).items():
        if g not in rec["lines"]:
            continue
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            continue
        if pct <= 0:
            if pct < 0:
                rejected.append(f"{LABEL[g]}: a decrease was requested and ignored (the AI may only make orders safer)")
            continue
        l = rec["lines"][g]
        raise_by = min(pct / 100, 0.05, MAX_BUFFER - l["buffer"])
        if raise_by <= 0:
            rejected.append(f"{LABEL[g]}: already at the {MAX_BUFFER:.0%} buffer ceiling")
            continue
        l["ai_raise"] = round(raise_by, 3)
        l["buffer"] = round(l["buffer"] + raise_by, 3)
        new = max(l["expected_use_kg"] * (1 + l["buffer"]) - l["on_hand_kg"], 0.0)
        changes.append(f"{LABEL[g]}: buffer +{raise_by:.0%} → {new:.1f} kg (was {l['suggested_kg']} kg)")
        l["suggested_kg"] = round(new, 1)
        l["difference_kg"] = round(l["standing_par_kg"] - l["suggested_kg"], 1)
    avoided = sum(max(l["difference_kg"], 0.0) for l in rec["lines"].values())
    rec["waste_avoided_estimate_kg"] = round(avoided, 1)
    return {"status": "verified", "model": cfg.state.get("model"), "explanation": (args.get("explanation") or "").strip(),
            "watch": [str(w) for w in (args.get("watch") or [])][:4], "changes": changes, "rejected": rejected, "error": None}


def rule_explanation(rec: dict) -> str:
    less = [l for l in rec["lines"].values() if l["difference_kg"] > 0.5]
    more = [l for l in rec["lines"].values() if l["difference_kg"] < -0.5]
    parts = []
    if less:
        parts.append("Order less " + ", ".join(f"{l['label'].lower()} (−{l['difference_kg']:.0f} kg: {l['why']})" for l in less)
                     + " than standing par.")
    if more:
        parts.append("Order more " + ", ".join(f"{l['label'].lower()} (+{-l['difference_kg']:.0f} kg: {l['why']})" for l in more)
                     + ": guest experience outranks waste.")
    if not parts:
        parts.append("The suggested order is close to standing par for every group.")
    return " ".join(parts)
