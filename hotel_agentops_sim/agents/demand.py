"""Demand Agent: 'What demand should we expect?'   READ PMS, reservations, POS, events · WRITE none."""
from __future__ import annotations

from ..models import AgentOutput

ABNORMAL_EVENT_CHANGE = 0.25        # NA-08


class DemandAgent:
    name = "Demand Agent"
    question = "What demand should we expect?"
    READS = ["pms_occupancy", "reservations", "pos_history", "event_schedule"]
    WRITES: list[str] = []          # cannot write anything, cannot purchase

    def run(self, view) -> AgentOutput:
        pms, pos = view.get("pms_occupancy"), view.get("pos_history")
        history = pos["last_4_saturdays"]
        # NA-01: covers per occupied room from the last four comparable services
        covers_per_room = sum(h["covers"] for h in history) / sum(h["occupied_rooms"] for h in history)
        expected = round(pms["occupied_rooms"] * covers_per_room)
        last_week = history[0]["covers"]
        change = expected / last_week - 1
        # NA-02: confidence = 1 - trailing MAPE
        apes = pos["last_7_services_forecast_ape"]
        trailing_mape = sum(apes) / len(apes)
        confidence = round(1 - trailing_mape, 3)
        per_cover = pos["consumption_kg_per_cover"]
        expected_consumption = {g: round(expected * kg, 1) for g, kg in per_cover.items()}

        events = []
        for ev in (view.get("event_schedule") or {}).get("events", []):
            ev_change = ev["revised_covers"] / ev["guaranteed_covers"] - 1
            events.append({**ev, "change": round(ev_change, 3), "abnormal": abs(ev_change) > ABNORMAL_EVENT_CHANGE})

        signal = f"Expected covers {'up' if change > 0 else 'down'} {abs(change):.0%} vs last Saturday ({last_week} → {expected})"
        return AgentOutput(
            agent=self.name, question=self.question, reads=self.READS, confidence=confidence,
            outputs={
                "occupied_rooms": pms["occupied_rooms"], "rooms": pms["rooms"],
                "covers_per_occupied_room": round(covers_per_room, 3),
                "expected_covers": expected, "last_week_covers": last_week, "demand_change": round(change, 3),
                "trailing_mape": round(trailing_mape, 4), "expected_consumption_kg": expected_consumption,
                "consumption_kg_per_cover": per_cover, "events": events, "demand_signal": signal,
            },
        )
