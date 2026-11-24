"""Kiểm thử HTTP cho API FastAPI (dùng TestClient).

Cần `httpx` (nằm trong `requirements-dev.txt`). Nếu máy chưa cài, class test tự skip
để bộ test lõi vẫn chạy được, còn CI thì cài đủ nên luôn chạy.

    pip install -r requirements-dev.txt
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest

try:  # httpx là phụ thuộc chỉ dùng khi test HTTP
    from fastapi.testclient import TestClient

    from backend.app import app

    HAVE_HTTP_CLIENT = True
except ImportError:  # pragma: no cover - máy chưa cài httpx
    HAVE_HTTP_CLIENT = False
    app = None  # type: ignore[assignment]


@unittest.skipUnless(HAVE_HTTP_CLIENT, "cần cài httpx: pip install -r requirements-dev.txt")
class TestHttpApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    # -- thông tin hệ thống -------------------------------------------------
    def test_health(self) -> None:
        payload = self.client.get("/api/health").json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["hubs"], 16)
        self.assertEqual(payload["rules"], 12)
        self.assertIn("limits", payload)
        self.assertIn("eta_model", payload)

    def test_hubs(self) -> None:
        payload = self.client.get("/api/hubs").json()
        self.assertEqual(len(payload["hubs"]), 16)
        for hub in payload["hubs"]:
            self.assertTrue(10.5 < hub["lat"] < 11.2)
            self.assertTrue(106.3 < hub["lon"] < 107.1)

    def test_rules(self) -> None:
        rules = self.client.get("/api/rules").json()["rules"]
        self.assertEqual(len(rules), 12)
        self.assertTrue(all(set(("id", "title", "clause", "level", "priority")) <= set(r) for r in rules))

    # -- kịch bản -----------------------------------------------------------
    def test_scenario_is_deterministic(self) -> None:
        first = self.client.get("/api/scenario", params={"seed": 7, "orders": 8}).json()
        second = self.client.get("/api/scenario", params={"seed": 7, "orders": 8}).json()
        self.assertEqual([o["id"] for o in first["orders"]], [o["id"] for o in second["orders"]])
        self.assertEqual([v["id"] for v in first["vehicles"]], [v["id"] for v in second["vehicles"]])

    def test_scenario_rejects_bad_bounds(self) -> None:
        self.assertEqual(self.client.get("/api/scenario", params={"orders": 4}).status_code, 422)
        self.assertEqual(self.client.get("/api/scenario", params={"orders": 5000}).status_code, 422)
        self.assertEqual(self.client.get("/api/scenario", params={"vehicles": 99}).status_code, 422)

    # -- lập kế hoạch -------------------------------------------------------
    def test_plan_default_body(self) -> None:
        response = self.client.post("/api/plan")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metrics"]["orders"], 48)
        self.assertGreater(payload["metrics"]["total_km"], 0)
        self.assertIn("warnings", payload)

    def test_plan_all_assignment_strategies(self) -> None:
        for strategy in ("hungarian", "greedy", "savings", "random"):
            with self.subTest(strategy=strategy):
                response = self.client.post("/api/plan", json={"orders": 8, "assignment": strategy})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["metrics"]["orders"], 8)

    def test_plan_all_routing_strategies(self) -> None:
        for strategy in ("deadline", "nearest", "two_opt", "random", "savings", "savings_2opt"):
            with self.subTest(strategy=strategy):
                response = self.client.post("/api/plan", json={"orders": 8, "routing": strategy})
                self.assertEqual(response.status_code, 200)

    def test_plan_rejects_invalid_payload(self) -> None:
        cases = [
            {"orders": "abc"},
            {"orders": 5000},
            {"vehicles": 1},
            {"assignment": "khong_ton_tai"},
            {"routing": "bay_luon"},
            {"eta": "gpt"},
            {"seed": 0},
        ]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/plan", json=body).status_code, 422)

    def test_plan_eta_source(self) -> None:
        response = self.client.post("/api/plan", json={"orders": 8, "eta": "ml"})
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json()["warnings"], list)

    # -- sự cố --------------------------------------------------------------
    def test_incident_congestion_uses_astar(self) -> None:
        payload = self.client.post("/api/incident", json={"kind": "congestion", "orders": 8}).json()
        titles = [step["title"] for step in payload["steps"]]
        self.assertTrue(any("A*" in title for title in titles))
        self.assertIn("before", payload)
        self.assertIn("incident", payload)
        with_eta = self.client.post(
            "/api/incident", json={"kind": "congestion", "orders": 8, "eta": "ml"}
        )
        self.assertEqual(with_eta.status_code, 200)
        self.assertIn(with_eta.json()["strategy"]["eta"], ("osrm", "ml"))

    def test_incident_rejects_bad_kind(self) -> None:
        self.assertEqual(
            self.client.post("/api/incident", json={"kind": "khong_ton_tai"}).status_code, 422
        )

    def test_incident_rejects_unknown_hub(self) -> None:
        response = self.client.post(
            "/api/incident", json={"kind": "depot_closed", "hub_id": "khong_co"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("khong_co", response.json()["detail"])

    def test_incident_breakdown_needs_vehicle(self) -> None:
        response = self.client.post("/api/incident", json={"kind": "breakdown", "orders": 8})
        self.assertEqual(response.status_code, 400)
        self.assertIn("vehicle_id", response.json()["detail"])

    def test_incident_breakdown_with_real_vehicle(self) -> None:
        scenario = self.client.get("/api/scenario", params={"orders": 8}).json()
        vehicle_id = scenario["vehicles"][0]["id"]
        response = self.client.post(
            "/api/incident",
            json={"kind": "breakdown", "vehicle_id": vehicle_id, "orders": 8},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["routes"]), len(scenario["vehicles"]) - 1)

    # -- các endpoint khác ---------------------------------------------------
    def test_compare(self) -> None:
        payload = self.client.get("/api/compare", params={"orders": 8}).json()
        self.assertIn("assignment", payload)
        self.assertIn("routing", payload)
        self.assertEqual(len(payload["assignment"]), 4)
        self.assertGreaterEqual(len(payload["routing"]), 5)

    def test_geometry_unknown_hub(self) -> None:
        self.assertEqual(self.client.get("/api/geometry", params={"a": "abc", "b": "xyz"}).status_code, 404)

    def test_eta_info(self) -> None:
        payload = self.client.get("/api/eta/info").json()
        self.assertIn("available", payload)

    def test_unknown_route_404(self) -> None:
        self.assertEqual(self.client.get("/api/khong_ton_tai").status_code, 404)

    def test_validation_error_is_json(self) -> None:
        response = self.client.post("/api/plan", content="not-json", headers={"content-type": "application/json"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())


if __name__ == "__main__":
    unittest.main()
