"""Tests for the governance guarantees the case study promises. Run: python -m unittest -v"""
import unittest
import warnings

warnings.filterwarnings("ignore", module="openpyxl")
from pathlib import Path

from hotel_agentops_sim import governance
from hotel_agentops_sim.agentops import autonomy_level, drift, evaluate_gate
from hotel_agentops_sim.agents import DemandAgent, ProductionAgent
from hotel_agentops_sim.agents.production import NotAuthorized
from hotel_agentops_sim.context import ContextManager, ContextPermissionError
from hotel_agentops_sim.engine import run_service
from hotel_agentops_sim.models import Recommendation
from hotel_agentops_sim.parameters import load_parameters, load_scenario, modified, thresholds, value

P = load_parameters()
S = load_scenario()
QUIET = dict(mode="scripted", say=lambda *a, **k: None)


def evidence(week=None, **kw):
    src = P["gate_evidence_by_week"][week] if week else P["latest_gate_evidence"]
    ev = {k: v["value"] for k, v in src.items()}
    ev.update(kw)
    return ev


def ctx(failures=None):
    return ContextManager.load(S["hotel_data"], value(P, "required_context_sources"), failures)


def rec(risk="LOW", conf=0.99, rev="HIGH", **details):
    return Recommendation("D-9999", "08:00", "flag_overproduction", "test", ["Waste Agent"], "test", "test",
                          conf, risk, rev, 1.0, details={"executor": "Waste Agent", "write_scope": "waste_insight", **details})


class Governance(unittest.TestCase):
    def evaluate(self, r, level="DELEGATED", failures=None, conflict=None):
        return governance.evaluate(r, context=ctx(failures), autonomy_level=level, context_threshold=0.95,
                                   delegated_range=0.10, conflict=conflict)

    def test_confidence_is_not_authority(self):
        g = self.evaluate(rec(risk="HIGH", conf=0.99, rev="LOW"))
        self.assertEqual(g.authority, "HUMAN_DECISION")

    def test_low_risk_is_delegated_only_when_gate_passes(self):
        self.assertEqual(self.evaluate(rec(), "DELEGATED").authority, "EXECUTE")
        self.assertEqual(self.evaluate(rec(), "SUPERVISED").authority, "MANAGER_APPROVAL")
        self.assertEqual(self.evaluate(rec(), "BOUNDED").authority, "RECOMMEND_ONLY")

    def test_low_confidence_recommends_only(self):
        self.assertEqual(self.evaluate(rec(conf=0.70)).authority, "RECOMMEND_ONLY")

    def test_missing_context_abstains(self):
        g = self.evaluate(rec(), failures={"pms_occupancy": "missing"})
        self.assertEqual(g.authority, "ABSTAIN")
        self.assertTrue(g.escalate)

    def test_stale_inventory_blocks_execution(self):
        g = self.evaluate(rec(depends_on_inventory=True), failures={"inventory": "stale"})
        self.assertEqual(g.authority, "BLOCK")

    def test_unresolved_conflict_escalates(self):
        r = rec(risk="MEDIUM")
        r.decision_type = "production_adjustment"
        r.details.update(executor="Production Agent", write_scope="production_plan",
                         plan_kg={"a": 10.0}, expected_consumption_kg={"a": 9.0}, usable_carry_over_kg={})
        g = self.evaluate(r, conflict={"conflict": True, "resolved": False, "note": "test"})
        self.assertEqual(g.authority, "HUMAN_DECISION")

    def test_no_agent_may_write_purchasing(self):
        r = rec(risk="MEDIUM", rev="LOW")
        r.details.update(executor=None, write_scope="purchasing")
        self.assertTrue(self.evaluate(r).human_approval_required)


class LeastPrivilege(unittest.TestCase):
    def test_agent_cannot_read_outside_its_permissions(self):
        with self.assertRaises(ContextPermissionError):
            ctx().view(DemandAgent.READS).get("inventory")

    def test_production_agent_cannot_write_without_authorization(self):
        with self.assertRaises(NotAuthorized):
            ProductionAgent().execute({"a": 1.0}, authorization=None)


class ReadinessGate(unittest.TestCase):
    def test_a6_holds_on_tool_reliability_alone(self):
        g = evaluate_gate(evidence("A6"), thresholds(P))
        self.assertEqual((g["result"], g["first_blocker"], g["failed"]), ("HOLD", "Tool reliability", 1))

    def test_matches_workbook_for_every_pilot_week(self):
        for week, row in P["gate_evidence_by_week"].items():
            g = evaluate_gate({k: v["value"] for k, v in row.items()}, thresholds(P))
            self.assertEqual(g["result"], row["gate"]["value"], week)

    def test_no_averaging(self):
        ev = evidence(tool_reliability=0.989, recommendation_acceptance=1.0, escalation_recall=1.0)
        self.assertEqual(evaluate_gate(ev, thresholds(P))["result"], "HOLD")

    def test_guest_breach_reduces_autonomy(self):
        ev = evidence(guest_fb_score=4.55)
        level, _ = autonomy_level(evaluate_gate(ev, thresholds(P)), ev, thresholds(P),
                                  drift([w["value"] for w in P["override_rate_history"]]))
        self.assertEqual(level, "BOUNDED")

    def test_override_drift_reduces_autonomy(self):
        hist = [w["value"] for w in P["override_rate_history"]][:-1] + [0.23]
        self.assertTrue(drift(hist)["drift"])


class EndToEnd(unittest.TestCase):
    def test_d0418_reproduces_case_study_trace(self):
        res = run_service(S, P, **QUIET)
        r = next(r for r in res.records if r["Decision ID"] == "D-0418")
        o = res.traces["D-0418"]["outcome"]["actual"]
        self.assertEqual((o["predicted_covers"], o["actual_covers"]), (420, 409))
        self.assertAlmostEqual(o["forecast_ape"], 0.0269, places=4)
        self.assertEqual(r["Required Authority"], "Agent recommends · manager approves")
        self.assertEqual(r["Risk"], "MEDIUM")

    def test_missing_context_refuses_to_act(self):
        res = run_service(modified(S, hotel_data__pms_occupancy=None), P, **QUIET)
        self.assertEqual(len(res.executions), 0)
        self.assertTrue(res.records[-1]["Execution Status"].startswith("ABSTAINED"))

    def test_human_modification_is_policy_checked(self):
        s = modified(S, scripted_manager_choices__production_adjustment={"choice": "modify", "new_change_pct": -35,
                                                                        "reason": "Forecast disagreement"})
        r = next(r for r in run_service(s, P, **QUIET).records if r["Decision ID"] == "D-0418")
        self.assertEqual(r["Execution Status"], "BLOCKED")

    def test_outcome_depends_on_the_human_decision(self):
        s = modified(S, scripted_manager_choices__production_adjustment={"choice": "reject", "reason": "Special event"})
        rejected = run_service(s, P, **QUIET).traces["D-0418"]["outcome"]["actual"]
        approved = run_service(S, P, **QUIET).traces["D-0418"]["outcome"]["actual"]
        self.assertGreater(rejected["waste_kg"], approved["waste_kg"])

    def test_every_record_has_a_trace(self):
        res = run_service(S, P, **QUIET)
        self.assertEqual({r["Decision ID"] for r in res.records}, set(res.traces))


class SourceOfTruth(unittest.TestCase):
    def test_parameters_match_workbook(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl not installed")
        xlsx = Path(__file__).resolve().parents[1] / P["workbook"]
        if not xlsx.exists():
            self.skipTest(f"{P['workbook']} not next to the project")
        wb = openpyxl.load_workbook(xlsx, data_only=True)
        for item in P["readiness_thresholds"].values():
            sheet, ref = item["source"].split("!")
            self.assertEqual(wb[sheet][ref].value, item["value"], item["source"])


if __name__ == "__main__":
    unittest.main()
