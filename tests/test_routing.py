"""Kiểm thử xếp tuyến: Nearest Neighbor, 2-opt, Clarke–Wright, lập kế hoạch cả đội."""

from __future__ import annotations

import unittest

from backend.dispatch.assignment import assign_hungarian
from backend.dispatch.network import load_network
from backend.dispatch.routing import (
    BASE_MINUTE,
    clarke_wright,
    nearest_neighbor,
    plan_routes,
    route_length,
    schedule_route,
    sequence_score,
    summarize,
    two_opt,
)
from backend.dispatch.scenario import build_scenario


class TestRoutingOnScenario(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()
        scenario = build_scenario(cls.net, seed=7, n_orders=24, n_vehicles=4)
        cls.orders = scenario["orders"]
        cls.vehicles = scenario["vehicles"]
        cls.assignment = assign_hungarian(cls.net, cls.orders, cls.vehicles)
        # chọn xe nhiều đơn nhất để các ca kiểm thử 2-opt/Clarke–Wright không bị bỏ qua
        cls.vehicle = max(cls.vehicles, key=lambda v: len(cls.assignment[v["id"]]))
        cls.dests = [(o["id"], o["dest_hub"]) for o in cls.assignment[cls.vehicle["id"]]]

    def test_nearest_neighbor_is_permutation(self) -> None:
        if not self.dests:
            self.skipTest("xe không có đơn")
        sequence = nearest_neighbor(self.net, self.vehicle["start_hub"], self.dests, 1.0)
        self.assertEqual(sorted(item[0] for item in sequence), sorted(item[0] for item in self.dests))

    def test_clarke_wright_is_permutation(self) -> None:
        if len(self.dests) < 2:
            self.skipTest("cần ít nhất hai điểm")
        sequence = clarke_wright(self.net, self.vehicle["start_hub"], self.dests, 1.0)
        self.assertEqual(sorted(item[0] for item in sequence), sorted(item[0] for item in self.dests))

    def test_two_opt_never_worse(self) -> None:
        if len(self.dests) < 4:
            self.skipTest("cần ít nhất bốn điểm để đảo chặng")
        sequence = nearest_neighbor(self.net, self.vehicle["start_hub"], self.dests, 1.0)
        before = sequence_score(self.net, self.vehicle["start_hub"], sequence, 1.0)
        improved, improvements = two_opt(self.net, self.vehicle["start_hub"], sequence, 1.0)
        after = sequence_score(self.net, self.vehicle["start_hub"], improved, 1.0)
        self.assertLessEqual(after, before + 1e-6)
        self.assertGreaterEqual(improvements, 0)
        self.assertEqual(sorted(item[0] for item in improved), sorted(item[0] for item in sequence))

    def test_two_opt_matches_reference_implementation(self) -> None:
        """Bản 2-opt tối ưu (mảng cục bộ) phải cho đúng thứ tự như bản tham chiếu chậm."""
        if len(self.dests) < 4:
            self.skipTest("cần ít nhất bốn điểm để đảo chặng")
        from backend.dispatch.routing import DEFAULT_LATE_PENALTY

        by_id = {order["id"]: order for order in self.assignment[self.vehicle["id"]]}
        start = self.vehicle["start_hub"]
        speed = self.vehicle["speed_factor"]
        sequence = nearest_neighbor(self.net, start, self.dests, speed)

        best = list(sequence)
        best_cost = sequence_score(
            self.net, start, best, speed, by_id, DEFAULT_LATE_PENALTY, BASE_MINUTE, None
        )
        improvements = 0
        for _ in range(40):
            improved = False
            for i in range(len(best) - 1):
                for j in range(i + 1, len(best)):
                    candidate = best[:i] + list(reversed(best[i : j + 1])) + best[j + 1 :]
                    cost = sequence_score(
                        self.net, start, candidate, speed, by_id, DEFAULT_LATE_PENALTY, BASE_MINUTE, None
                    )
                    if cost + 1e-6 < best_cost:
                        best, best_cost, improved = candidate, cost, True
                        improvements += 1
            if not improved:
                break

        new_sequence, new_improvements = two_opt(
            self.net, start, sequence, speed, by_id, DEFAULT_LATE_PENALTY, BASE_MINUTE
        )
        self.assertEqual(new_sequence, best)
        self.assertEqual(new_improvements, improvements)

    def test_eta_multiplier_uses_hour_of_day(self) -> None:
        """Hệ số ùn tắc phải lấy theo giờ trong ngày, không phải số phút kể từ 00:00."""
        if not self.dests:
            self.skipTest("xe không có đơn")

        class FakeEta:
            def hour_factor(self, hour: int) -> float:
                return 2.0 if int(hour) % 24 == 8 else 1.0

        start = self.vehicle["start_hub"]
        speed = self.vehicle["speed_factor"]
        sequence = self.dests[:1]
        base = sequence_score(self.net, start, sequence, speed)
        scaled = sequence_score(self.net, start, sequence, speed, eta_model=FakeEta())
        # BASE_MINUTE = 08:00 nên chặng đầu phải bị nhân 2
        self.assertAlmostEqual(scaled, base * 2.0, places=6)

        route = schedule_route(
            self.net, self.vehicle, self.assignment[self.vehicle["id"]][:1],
            strategy="nearest", start_min=BASE_MINUTE, eta_model=FakeEta(),
        )
        plain = schedule_route(
            self.net, self.vehicle, self.assignment[self.vehicle["id"]][:1],
            strategy="nearest", start_min=BASE_MINUTE,
        )
        self.assertAlmostEqual(route.legs[0]["min"], plain.legs[0]["min"] * 2.0, places=1)

    def test_route_length_matches_sum_of_legs(self) -> None:
        # route_length trả về tổng thời gian di chuyển (phút), chưa gồm thời gian phục vụ
        hubs = [self.vehicle["start_hub"]] + [hub for _, hub in self.dests]
        expected = sum(self.net.dur_min(a, b) for a, b in zip(hubs, hubs[1:]))
        self.assertAlmostEqual(route_length(self.net, self.vehicle["start_hub"], hubs[1:], 1.0), expected)

    def test_schedule_route_shape(self) -> None:
        orders = self.assignment[self.vehicle["id"]]
        if not orders:
            self.skipTest("xe không có đơn")
        route = schedule_route(self.net, self.vehicle, orders, strategy="deadline", start_min=BASE_MINUTE)
        self.assertEqual(route.vehicle_id, self.vehicle["id"])
        self.assertGreaterEqual(route.total_km, 0.0)
        self.assertGreaterEqual(route.total_min, 0.0)
        self.assertLessEqual(route.late_count, len(route.stops))


class TestFleetPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()
        scenario = build_scenario(cls.net, seed=11, n_orders=24, n_vehicles=4)
        cls.orders = scenario["orders"]
        cls.vehicles = scenario["vehicles"]
        cls.assignment = assign_hungarian(cls.net, cls.orders, cls.vehicles)

    def test_plan_routes_covers_orders(self) -> None:
        routes = plan_routes(self.net, self.vehicles, self.assignment)
        served = [stop.order_id for route in routes for stop in route.stops]
        self.assertEqual(sorted(served), sorted(order["id"] for order in self.orders))

    def test_summary_is_consistent(self) -> None:
        routes = plan_routes(self.net, self.vehicles, self.assignment)
        metrics = summarize(routes)
        self.assertEqual(metrics["orders"], sum(len(route.stops) for route in routes))
        self.assertGreaterEqual(metrics["on_time_rate"], 0.0)
        self.assertLessEqual(metrics["on_time_rate"], 100.0)
        self.assertAlmostEqual(
            metrics["total_km"],
            round(sum(route.total_km for route in routes), 2),
        )

    def test_time_multiplier_slows_down_but_keeps_distance_objective(self) -> None:
        # Với chiến lược xếp tuyến theo quãng đường (savings), hệ số chậm không đổi thứ tự
        # nên tổng km giữ nguyên; riêng tổng thời gian phải tăng.
        normal = plan_routes(self.net, self.vehicles, self.assignment, strategy="savings", time_multiplier=1.0)
        slower = plan_routes(self.net, self.vehicles, self.assignment, strategy="savings", time_multiplier=1.4)
        self.assertAlmostEqual(
            sum(route.total_km for route in normal), sum(route.total_km for route in slower), places=6
        )
        self.assertGreater(
            sum(route.total_min for route in slower), sum(route.total_min for route in normal)
        )


if __name__ == "__main__":
    unittest.main()



