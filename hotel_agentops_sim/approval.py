"""Human approval step. Pauses the workflow and shows the manager what they need to decide.

interactive: a person types the decision (Approve / Modify / Reject / Request more context)
scripted:    reproducible demo choices from the scenario file (--auto)
"""
from __future__ import annotations

import textwrap

from .models import HumanDecision, Recommendation

MODIFIABLE = {"production_adjustment", "purchasing_adjustment"}


def _card(rec: Recommendation, gov, width=78) -> str:
    wrap = lambda s: textwrap.fill(s, width - 4, initial_indent="  ", subsequent_indent="  ")
    head = "MANDATORY ESCALATION · HUMAN DECISION" if gov.authority == "HUMAN_DECISION" else "APPROVAL REQUIRED"
    lines = ["", "┌" + "─" * (width - 2) + "┐", f"  {head} · {rec.decision_id} · {rec.service}",
             "└" + "─" * (width - 2) + "┘",
             "AI RECOMMENDATION", wrap(rec.recommendation), "WHY THE AI RECOMMENDED IT", wrap(rec.reason),
             f"CONFIDENCE  {rec.confidence:.1%}      RISK  {rec.risk_level}      REVERSIBILITY  {rec.reversibility}",
             f"AUTHORITY   {gov.required_authority}"]
    if rec.decision_type == "production_adjustment":
        lines.append("RELEVANT DATA")
        lines.append(f"  Expected covers {rec.details['expected_covers']} · context {rec.context_completeness:.0%} complete")
        for l in rec.details["lines"]:
            lines.append(f"  {l['group']:<17} need {l['expected_consumption_kg']:>5.1f} kg · plan {l['planned_kg']:>5.1f} kg"
                         f" (standing {l['standing_plan_kg']:>4.0f}, {l['change']:+.0%}) · buffer {l['buffer']:.0%}")
    lines += ["EXPECTED IMPACT", wrap(rec.expected_impact), ""]
    return "\n".join(lines)


class ApprovalQueue:
    def __init__(self, mode: str, choices: dict | None, categories: list[str], approver: str | None = None,
                 input_fn=input, output_fn=print):
        self.mode, self.choices, self.categories = mode, choices or {}, categories
        self.approver = approver or self.choices.get("approver", "F&B Manager")
        self.input, self.output = input_fn, output_fn

    def route(self, rec: Recommendation, gov, at: str) -> HumanDecision:
        self.output(_card(rec, gov))
        if self.mode == "scripted":
            c = self.choices.get(rec.decision_type, {"choice": "approve"})
            d = HumanDecision(choice=c["choice"], approver=self.approver, timestamp=at,
                              final_change_pct=c.get("new_change_pct"), override=c["choice"] in ("modify", "reject"),
                              override_reason=c.get("reason", ""), note=c.get("note", ""))
            self.output(f"  [scripted demo] {self.approver} chose: {d.choice.upper()}"
                        + (f" to {d.final_change_pct:+}%" if d.final_change_pct is not None else "")
                        + (f" · reason: {d.override_reason}" if d.override_reason else ""))
            return d
        return self._ask(rec, at)

    def _ask(self, rec: Recommendation, at: str) -> HumanDecision:
        opts = "[A]pprove  [M]odify  [R]eject  [C] request more context"
        while True:
            ans = self.input(f"  {opts}: ").strip().lower()[:1]
            if ans in ("a", "m", "r", "c"):
                break
        name = self.input(f"  Approver name [{self.approver}]: ").strip() or self.approver
        if ans == "a":
            return HumanDecision("approve", name, at)
        if ans == "c":
            note = self.input("  What context is needed? ").strip()
            return HumanDecision("more_context", name, at, note=note)
        pct = None
        if ans == "m" and rec.decision_type in MODIFIABLE:
            while pct is None:
                try:
                    pct = float(self.input("  New adjustment in % (e.g. -10): ").strip().replace("%", ""))
                except ValueError:
                    pass
        elif ans == "m":
            self.output("  This decision has no numeric setting to modify; treating as reject with a reason.")
            ans = "r"
        for i, c in enumerate(self.categories, 1):
            self.output(f"    {i}. {c}")
        reason = ""
        while not reason:
            pick = self.input("  Override reason (number): ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(self.categories):
                reason = self.categories[int(pick) - 1]
        note = self.input("  Note (optional): ").strip()
        return HumanDecision("modify" if ans == "m" else "reject", name, at, final_change_pct=pct,
                             override=True, override_reason=reason, note=note)
