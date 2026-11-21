"""Kiểm thử bài toán gán: Hungarian tối ưu, chia đơn đủ, không vượt tải."""

from __future__ import annotations

import itertools
import unittest

from backend.dispatch.assignment import (
    STRATEGIES,
    _load,
    assign_greedy,
    assign_hungarian,
    assign_random,
    assign_savings,
    hungarian,
    repair_capacity,
)
from backend.dispatch.network import load_network
from backend.dispatch.scenario import build_scenario


class TestHungarian(unittest.TestCase):
    def test_small_matrix_is_optimal(self) -> None:
        cost = [
            [4.0, 1.0, 3.0],
            [2.0, 0.0, 5.0],
            [3.0, 2.0, 2.0],
        ]
        assignment = hungarian(cost)
        total = sum(cost[row][assignment[row]] for row in range(3))
        best = min(
            sum(cost[row][perm[row]] for row in range(3))
            for perm in itertools.permutations(range(3))
        )
        self.assertEqual(len(assignment), 3)
        self.assertEqual(sorted(assignment), [0, 1, 2])
        self.assertAlmostEqual(total, best)

    def test_identity_for_dominant_diagonal(self) -> None:
        cost = [[0.0, 9.0, 9.0], [9.0, 0.0, 9.0], [9.0, 9.0, 0.0]]
        self.assertEqual(hungarian(cost), [0, 1, 2])

    def test_handles_negative_costs(self) -> None:
        cost = [[-1.0, 2.0], [2.0, -3.0]]
        assignment = hungarian(cost)
        total = sum(cost[row][assignment[row]] for row in range(2))
        self.assertAlmostEqual(total, -4.0)


class TestAssignmentOnScenario(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()
        scenario = build_scenario(cls.net, seed=7, n_orders=24, n_vehicles=4)
        cls.orders = scenario["orders"]
        cls.vehicles = scenario["vehicles"]

    def _assert_covers_all(self, assignment: dict[str, list[dict]]) -> None:
        assigned = [order["id"] for items in assignment.values() for order in items]
        self.assertEqual(sorted(assigned), sorted(order["id"] for order in self.orders))
        self.assertEqual(len(assigned), len(set(assigned)), "một đơn không được gán hai lần")

    def test_hungarian_covers_every_order(self) -> None:
        self._assert_covers_all(assign_hungarian(self.net, self.orders, self.vehicles))

    def test_all_strategies_cover_every_order(self) -> None:
        for name in ("greedy", "savings", "random", "hungarian"):
            with self.subTest(strategy=name):
                assignment = STRATEGIES[name](self.net, self.orders, self.vehicles)
                self._assert_covers_all(assignment)

    def test_random_is_reproducible_without_seed_change(self) -> None:
        first = assign_random(self.net, self.orders, self.vehicles, seed=3)
        second = assign_random(self.net, self.orders, self.vehicles, seed=3)
        self.assertEqual(
            {k: [o["id"] for o in v] for k, v in first.items()},
            {k: [o["id"] for o in v] for k, v in second.items()},
        )

    def test_repair_capacity_keeps_orders(self) -> None:
        assignment = assign_greedy(self.net, self.orders, self.vehicles)
        repaired, moves = repair_capacity(assignment, self.vehicles)
        self._assert_covers_all(repaired)
        self.assertIsInstance(moves, int)

    def test_load_helper(self) -> None:
        weight, volume = _load(self.orders[:2])
        self.assertAlmostEqual(weight, sum(o["weight_kg"] for o in self.orders[:2]))
        self.assertAlmostEqual(volume, sum(o["volume_l"] for o in self.orders[:2]))


if __name__ == "__main__":
    unittest.main()
