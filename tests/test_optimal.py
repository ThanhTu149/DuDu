"""Kiểm chứng công cụ đo optimality gap (routing gap + exact VRP nhỏ)."""

from __future__ import annotations

import itertools
import unittest

from backend.dispatch.network import Network, load_network
from backend.dispatch.optimal import (
    MAX_EXACT_ORDERS,
    _best_order_km,
    _open_route_km,
    exact_vrp,
    route_optimal_km,
    routing_gap_rows,
)
from backend.dispatch.scenario import build_scenario


def _orders(hubs: list[str]) -> list[dict]:
    return [
        {"id": f"T{i}", "dest_hub": hub, "weight_kg": 2.0, "volume_l": 2.0}
        for i, hub in enumerate(hubs, start=1)
    ]


def _vehicles(starts: list[str]) -> list[dict]:
    return [
        {"id": f"V{i}", "start_hub": start, "capacity_kg": 1000.0, "capacity_l": 1000.0, "speed_factor": 1.0}
        for i, start in enumerate(starts, start=1)
    ]


def _brute_exact(net: Network, orders: list[dict], vehicles: list[dict]) -> float:
    """Vét cạn độc lập: mọi cách chia đơn × mọi thứ tự giao trong từng xe."""
    best = float("inf")
    for combo in itertools.product(range(len(vehicles)), repeat=len(orders)):
        total = 0.0
        feasible = True
        for vehicle_index, vehicle in enumerate(vehicles):
            indices = [i for i, slot in enumerate(combo) if slot == vehicle_index]
            if not indices:
                continue
            weight = sum(orders[i]["weight_kg"] for i in indices)
            volume = sum(orders[i]["volume_l"] for i in indices)
            if weight > vehicle["capacity_kg"] or volume > vehicle["capacity_l"]:
                feasible = False
                break
            best_route = min(
                _open_route_km(net, vehicle["start_hub"], [orders[i]["dest_hub"] for i in perm])
                for perm in itertools.permutations(indices)
            )
            total += best_route
        if feasible and total < best:
            best = total
    return best


class TestOptimalTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()

    def test_best_order_matches_bruteforce(self) -> None:
        hubs = ["q1", "q10", "binh-thanh", "nha-be", "q7"]
        orders = _orders(hubs)
        dp = _best_order_km(self.net, "tan-binh", orders)
        brute = min(
            _open_route_km(self.net, "tan-binh", [orders[i]["dest_hub"] for i in perm])
            for perm in itertools.permutations(range(len(orders)))
        )
        self.assertAlmostEqual(dp, brute, places=6)

    def test_exact_vrp_matches_bruteforce(self) -> None:
        orders = _orders(["q1", "q3", "q10"])
        vehicles = _vehicles(["tan-binh", "q7"])
        result = exact_vrp(self.net, orders, vehicles)
        # exact_vrp làm tròn 3 chữ số thập phân\n        self.assertAlmostEqual(result["km"], _brute_exact(self.net, orders, vehicles), delta=1e-3)
        served = [order_id for ids in result["assignment"].values() for order_id in ids]
        self.assertCountEqual(served, [o["id"] for o in orders])

    def test_exact_vrp_respects_capacity(self) -> None:
        orders = _orders(["q1", "q3", "q10", "q5"])
        # Hai xe nhỏ: mỗi xe 5 kg → mỗi xe chỉ chở được 2 đơn 2 kg
        vehicles = [
            {"id": "V1", "start_hub": "tan-binh", "capacity_kg": 5.0, "capacity_l": 5.0, "speed_factor": 1.0},
            {"id": "V2", "start_hub": "q7", "capacity_kg": 5.0, "capacity_l": 5.0, "speed_factor": 1.0},
        ]
        result = exact_vrp(self.net, orders, vehicles)
        for vehicle_id, ids in result["assignment"].items():
            self.assertLessEqual(len(ids) * 2.0, 5.0 + 1e-9, vehicle_id)

    def test_exact_vrp_rejects_oversized(self) -> None:
        orders = _orders(["q1"] * (MAX_EXACT_ORDERS + 1))
        with self.assertRaises(ValueError):
            exact_vrp(self.net, orders, _vehicles(["tan-binh"]))

    def test_route_optimal_uses_scenario_assignment(self) -> None:
        scenario = build_scenario(self.net, seed=7, n_orders=12, n_vehicles=8)
        assignment = {v["id"]: [] for v in scenario["vehicles"]}
        for index, order in enumerate(scenario["orders"]):
            assignment[scenario["vehicles"][index % 4]["id"]].append(order)
        total = route_optimal_km(self.net, scenario, assignment)
        self.assertGreater(total, 0.0)

    def test_gap_rows_are_consistent(self) -> None:
        result = routing_gap_rows(self.net, cases=[(12, 8)], seeds=[7])
        # 2-opt tối ưu theo thời gian nên quãng đường có thể lệch vài phần nghìn %
        self.assertGreater(result["two_opt"]["gaps"][0], -0.5)
        self.assertGreater(result["nearest"]["gaps"][0], -1e-9)
        # 2-opt không thể tệ hơn thứ tự nhập trên cùng phân công
        self.assertLessEqual(result["two_opt"]["kms"][0], result["random"]["kms"][0] + 1e-6)


if __name__ == "__main__":
    unittest.main()

