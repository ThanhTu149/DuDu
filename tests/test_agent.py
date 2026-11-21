"""Kiểm thử tác tử điều phối và động cơ luật."""

from __future__ import annotations

import unittest

from backend.dispatch.agent import DispatcherAgent
from backend.dispatch.network import load_network
from backend.dispatch.scenario import build_scenario


class TestAgentPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()
        cls.scenario = build_scenario(cls.net, seed=7, n_orders=24, n_vehicles=4)

    def _agent(self) -> DispatcherAgent:
        return DispatcherAgent(self.net, self.scenario["vehicles"], self.scenario["orders"])

    def test_plan_shape(self) -> None:
        plan = self._agent().plan()
        for key in ("routes", "metrics", "violations", "steps", "strategy"):
            self.assertIn(key, plan)
        self.assertEqual(plan["metrics"]["orders"], 24)
        self.assertGreater(plan["metrics"]["total_km"], 0.0)

    def test_plan_is_deterministic(self) -> None:
        first = self._agent().plan()["metrics"]
        second = self._agent().plan()["metrics"]
        self.assertAlmostEqual(first["total_km"], second["total_km"])
        self.assertEqual(first["late_count"], second["late_count"])

    def test_metrics_match_violations(self) -> None:
        plan = self._agent().plan()
        violations = plan["violations"]
        blocked = [item for item in violations if item["level"] == "chan"]
        self.assertEqual(plan["metrics"]["violations"], len(violations))
        self.assertEqual(plan["metrics"]["blocked"], len(blocked))

    def test_steps_have_timing_and_stages(self) -> None:
        plan = self._agent().plan()
        self.assertGreaterEqual(len(plan["steps"]), 4)
        stages = {step["stage"] for step in plan["steps"]}
        self.assertTrue({"perceive", "decide", "verify"} <= stages)
        self.assertGreaterEqual(plan["steps"][-1]["ms"], plan["steps"][0]["ms"])


class TestIncidents(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()
        cls.scenario = build_scenario(cls.net, seed=7, n_orders=24, n_vehicles=4)

    def _agent(self) -> DispatcherAgent:
        return DispatcherAgent(self.net, self.scenario["vehicles"], self.scenario["orders"])

    def test_breakdown_removes_vehicle(self) -> None:
        agent = self._agent()
        broken = agent.vehicles[0]["id"]
        result = agent.handle_incident("breakdown", vehicle_id=broken)
        self.assertEqual(len(agent.vehicles), len(self.scenario["vehicles"]) - 1)
        self.assertEqual(result["metrics"]["orders"], 24)
        self.assertTrue(any("xe hỏng" in step["title"].lower() for step in result["steps"]))

    def test_congestion_uses_astar_detour(self) -> None:
        result = self._agent().handle_incident("congestion")
        titles = [step["title"] for step in result["steps"]]
        self.assertTrue(any("A*" in title for title in titles), "phải có bước A* tìm đường vòng")
        self.assertTrue(any("vòng" in step["detail"] for step in result["steps"]))

    def test_congestion_takes_longer_than_baseline(self) -> None:
        baseline = self._agent().plan()["metrics"]["total_min"]
        congested = self._agent().handle_incident("congestion")["metrics"]["total_min"]
        self.assertGreater(congested, baseline)

    def test_depot_closed_moves_start_hub(self) -> None:
        agent = self._agent()
        warehouse = agent.vehicles[0]["start_hub"]
        result = agent.handle_incident("depot_closed", hub_id=warehouse)
        self.assertTrue(all(vehicle["start_hub"] != warehouse for vehicle in agent.vehicles))
        self.assertEqual(result["metrics"]["orders"], 24)

    def test_unknown_incident_still_plans(self) -> None:
        result = self._agent().handle_incident("khong_ton_tai")
        self.assertIn("metrics", result)


if __name__ == "__main__":
    unittest.main()

