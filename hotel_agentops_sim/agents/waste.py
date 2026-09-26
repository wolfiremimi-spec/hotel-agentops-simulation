"""Waste Agent: 'Where and why are we losing food?'   READ waste logs, POS consumption · WRITE waste insights."""
from __future__ import annotations

from ..models import AgentOutput

CHRONIC_LEFTOVER = 0.20     # NA-05
CHRONIC_MIN_SERVICES = 3    # NA-05: in at least 3 of the last 4
STOCKOUT_MIN_SERVICES = 2   # NA-04: repeated stockouts


class WasteAgent:
    name = "Waste Agent"
    question = "Where and why are we losing food?"
    READS = ["waste_history", "pos_history"]
    WRITES = ["waste_insight"]

    def run(self, view) -> AgentOutput:
        wh = view.get("waste_history")
        rates, stockouts = wh["leftover_rate_last_4_saturdays"], wh["stockouts_last_4_saturdays"]
        chronic, stockout_prone, avg_leftover, consistency = [], [], {}, {}
        for group, history in rates.items():
            hits = sum(r > CHRONIC_LEFTOVER for r in history)
            avg_leftover[group] = round(sum(history) / len(history), 3)
            consistency[group] = hits / len(history)
            if hits >= CHRONIC_MIN_SERVICES:
                chronic.append(group)
            if stockouts.get(group, 0) >= STOCKOUT_MIN_SERVICES:
                stockout_prone.append(group)
        pattern = "; ".join(
            [f"{g}: leftover above {CHRONIC_LEFTOVER:.0%} in {int(consistency[g]*4)} of last 4 Saturdays (avg {avg_leftover[g]:.0%})"
             for g in chronic] +
            [f"{g}: stocked out in {stockouts[g]} of last 4 Saturdays" for g in stockout_prone]) or "No chronic pattern"
        confidence = min([consistency[g] for g in chronic], default=1.0)
        return AgentOutput(
            agent=self.name, question=self.question, reads=self.READS, confidence=confidence,
            outputs={"chronic_overproduction": chronic, "stockout_prone": stockout_prone,
                     "avg_leftover_rate": avg_leftover,
                     "likely_source": {g: "overproduction" for g in chronic},
                     "waste_risk_signal": "HIGH" if chronic else "NORMAL", "historical_pattern": pattern},
        )
