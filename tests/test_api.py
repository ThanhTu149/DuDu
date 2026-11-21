"""Kiểm thử nhanh lớp API và tính toàn vẹn dữ liệu đã commit."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.dispatch.network import HUBS_FILE, MATRIX_FILE, load_network

ROOT = Path(__file__).resolve().parents[1]


class TestApiSurface(unittest.TestCase):
    def test_app_imports(self) -> None:
        from backend.app import app

        paths = {getattr(route, "path", "") for route in app.routes}
        for expected in ("/api/health", "/api/hubs", "/api/scenario", "/api/plan", "/api/incident"):
            self.assertIn(expected, paths)

    def test_index_and_assets_exist(self) -> None:
        for name in ("index.html", "assets/app.css", "assets/app.js"):
            self.assertTrue((ROOT / "web" / name).exists(), name)


class TestCommittedData(unittest.TestCase):
    def test_hubs_file(self) -> None:
        payload = json.loads(HUBS_FILE.read_text(encoding="utf-8"))
        nodes = payload["nodes"]
        self.assertEqual(len(nodes), 16)
        ids = [node["id"] for node in nodes]
        self.assertEqual(len(ids), len(set(ids)), "id nút không được trùng")
        for node in nodes:
            self.assertTrue(10.5 < node["lat"] < 11.2, node["id"])
            self.assertTrue(106.3 < node["lon"] < 107.1, node["id"])

    def test_matrix_matches_hubs(self) -> None:
        net = load_network()
        matrix = json.loads(MATRIX_FILE.read_text(encoding="utf-8"))
        self.assertEqual(matrix["ids"], net.order)
        self.assertEqual(len(matrix["distance_m"]), len(net.order))

    def test_matrix_distance_reasonable(self) -> None:
        net = load_network()
        for a in net.order:
            for b in net.order:
                if a == b:
                    self.assertEqual(net.dist(a, b), 0.0)
                else:
                    self.assertGreater(net.dist(a, b), 0.0)
                    self.assertLess(net.dist(a, b), 80_000, f"{a}->{b} quá xa cho nội thành")


if __name__ == "__main__":
    unittest.main()
