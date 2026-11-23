"""Kiểm thử mạng lưới, A* và lớp RoutingView (đường vòng khi kẹt xe)."""

from __future__ import annotations

import unittest

from backend.dispatch.network import (
    RoutingView,
    congestion_edges,
    haversine_km,
    hubs_within,
    load_network,
)


class TestHaversine(unittest.TestCase):
    def test_zero_distance(self) -> None:
        self.assertAlmostEqual(haversine_km((10.77, 106.70), (10.77, 106.70)), 0.0, places=6)

    def test_known_distance(self) -> None:
        # Nhà thờ Đức Bà → Bến Thành, khoảng 0,7 km trên thực tế
        distance = haversine_km((10.7798, 106.6990), (10.7725, 106.6980))
        self.assertGreater(distance, 0.5)
        self.assertLess(distance, 1.5)

    def test_symmetry(self) -> None:
        a, b = (10.80, 106.65), (10.72, 106.75)
        self.assertAlmostEqual(haversine_km(a, b), haversine_km(b, a), places=9)


class TestNetwork(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()

    def test_hub_count(self) -> None:
        self.assertEqual(len(self.net.order), 16)

    def test_diagonal_zero(self) -> None:
        for hub_id in self.net.order:
            self.assertEqual(self.net.dur(hub_id, hub_id), 0.0)
            self.assertEqual(self.net.dist(hub_id, hub_id), 0.0)

    def test_matrix_matches_hubs(self) -> None:
        self.assertEqual(set(self.net.order), set(self.net.hubs))
        self.assertEqual(len(self.net.duration), 16)
        self.assertEqual(len(self.net.duration[0]), 16)

    def test_durations_positive_between_distinct_hubs(self) -> None:
        for a in self.net.order[:4]:
            for b in self.net.order[:4]:
                if a != b:
                    self.assertGreater(self.net.dur(a, b), 0.0)

    def test_astar_direct_when_free(self) -> None:
        path, seconds = self.net.astar("q1", "binh-thanh")
        self.assertGreaterEqual(len(path), 2)
        self.assertEqual(path[0], "q1")
        self.assertEqual(path[-1], "binh-thanh")
        self.assertAlmostEqual(seconds, self.net.dur("q1", "binh-thanh"), places=6)

    def test_astar_detour_avoids_blocked_edge(self) -> None:
        edges = congestion_edges(self.net, radius_km=4.5)
        self.assertGreater(len(edges), 0)
        a, b = sorted(next(iter(edges)))
        path, seconds = self.net.astar(a, b, blocked_edges=edges)
        self.assertEqual(path[0], a)
        self.assertEqual(path[-1], b)
        self.assertGreaterEqual(len(path), 3, "phải đi vòng qua nút khác")
        for left, right in zip(path, path[1:]):
            self.assertNotIn(frozenset((left, right)), edges)
        self.assertGreater(seconds, self.net.dur(a, b))

    def test_astar_raises_when_no_route(self) -> None:
        blocked = {hub for hub in self.net.order if hub not in {"q1", "q10"}}
        banned = {frozenset(("q1", "q10"))}
        with self.assertRaises(ValueError):
            self.net.astar("q1", "q10", blocked=blocked, blocked_edges=banned)


class TestRoutingView(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()
        edges = congestion_edges(cls.net, radius_km=4.5)
        cls.edges = edges
        cls.a, cls.b = sorted(next(iter(edges)))
        cls.view = RoutingView(cls.net, edges)

    def test_detour_is_longer(self) -> None:
        self.assertGreater(self.view.dur(self.a, self.b), self.net.dur(self.a, self.b))
        self.assertGreater(self.view.dist(self.a, self.b), self.net.dist(self.a, self.b))

    def test_detour_recorded_once_per_pair(self) -> None:
        view = RoutingView(self.net, self.edges)
        view.dur(self.a, self.b)
        view.dist(self.a, self.b)
        self.assertEqual(view.summary()["detour_legs"], 1)
        self.assertGreater(view.summary()["extra_km"], 0.0)

    def test_summary_can_filter_to_used_legs(self) -> None:
        # 2-opt tính trước ma trận nên có thể chạm chặng bị chặn không nằm trên tuyến cuối;
        # thống kê phải lọc theo các chặng thực sự dùng để không báo "đi vòng" khống.
        view = RoutingView(self.net, self.edges)
        view.dur(self.a, self.b)
        self.assertEqual(view.summary()["detour_legs"], 1)
        self.assertEqual(view.summary([])["detour_legs"], 0)
        self.assertEqual(view.summary([(self.a, self.b)])["detour_legs"], 1)
        self.assertGreater(view.summary([(self.a, self.b)])["extra_km"], 0.0)

    def test_unblocked_leg_matches_network(self) -> None:
        view = RoutingView(self.net, self.edges)
        free = ("q1", "cat-lai") if frozenset(("q1", "cat-lai")) not in self.edges else ("tan-binh", "cat-lai")
        self.assertAlmostEqual(view.dur(*free), self.net.dur(*free), places=6)
        self.assertEqual(view.detours, [])

    def test_hubs_within_radius(self) -> None:
        inside = hubs_within(self.net, radius_km=4.5)
        self.assertIn("q1", inside)
        self.assertNotIn("cat-lai", inside)


if __name__ == "__main__":
    unittest.main()
