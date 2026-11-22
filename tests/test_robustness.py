"""Smoke test cho script độ bền vững: tái lập được, cấu trúc đúng, không đụng global state."""

from __future__ import annotations

import unittest

import backend.dispatch.agent as agent_module
from backend.dispatch.network import load_network
from backend.dispatch.robustness import (
    radius_sensitivity,
    rounds_sensitivity,
    routing_aggregate,
    seed_rows,
)


class TestRobustnessTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()

    def test_seed_rows_reproducible(self) -> None:
        first = seed_rows(self.net, seeds=[7, 11], orders=12, vehicles=6)
        second = seed_rows(self.net, seeds=[7, 11], orders=12, vehicles=6)
        self.assertEqual([row["km"] for row in first], [row["km"] for row in second])
        self.assertTrue(all(row["on_time"] >= 0 for row in first))

    def test_rounds_sensitivity(self) -> None:
        rows = rounds_sensitivity(self.net, seeds=[7], rounds_list=(0, 2))
        self.assertEqual([row["rounds"] for row in rows], [0, 2])
        for row in rows:
            self.assertGreaterEqual(row["violations"], 0)
            self.assertGreater(row["km"], 0)

    def test_radius_sensitivity_restores_globals(self) -> None:
        before_edges = agent_module.congestion_edges
        before_hubs = agent_module.hubs_within
        rows = radius_sensitivity(self.net, seeds=[7], radii=(4.5,))
        self.assertEqual(len(rows), 1)
        self.assertGreaterEqual(rows[0]["extra_km"], 0)
        self.assertIs(agent_module.congestion_edges, before_edges)
        self.assertIs(agent_module.hubs_within, before_hubs)

    def test_routing_aggregate(self) -> None:
        result = routing_aggregate(self.net, seeds=[7], orders=12, vehicles=8)
        self.assertIn("deadline", result)
        self.assertEqual(len(result), 6)
        for item in result.values():
            self.assertGreater(item["km"]["mean"], 0)


if __name__ == "__main__":
    unittest.main()
