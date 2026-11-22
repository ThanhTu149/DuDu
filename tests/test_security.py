"""Kiểm thử lớp bảo mật: API key tuỳ chọn, giới hạn tần suất, security headers."""

from __future__ import annotations

import os
import unittest
import uuid

try:  # httpx chỉ cần cho test HTTP
    from fastapi.testclient import TestClient

    from backend.app import app

    HAVE_HTTP_CLIENT = True
except ImportError:  # pragma: no cover
    HAVE_HTTP_CLIENT = False
    app = None  # type: ignore[assignment]


@unittest.skipUnless(HAVE_HTTP_CLIENT, "cần cài httpx: pip install -r requirements-dev.txt")
class TestSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def setUp(self) -> None:
        self._saved = {key: os.environ.get(key) for key in ("DUDU_API_KEY", "DUDU_RATE_LIMIT")}
        os.environ.pop("DUDU_API_KEY", None)
        os.environ.pop("DUDU_RATE_LIMIT", None)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _plan(self, headers: dict | None = None):
        return self.client.post(
            "/api/plan",
            json={"seed": 7, "orders": 12, "vehicles": 6},
            headers=headers or {},
        )

    def test_health_is_public_even_with_api_key(self) -> None:
        os.environ["DUDU_API_KEY"] = "secret-key"
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["security"]["auth_required"])
        self.assertEqual(payload["security"]["rate_limit_per_minute"], 120)

    def test_api_key_required_and_accepted(self) -> None:
        os.environ["DUDU_API_KEY"] = "secret-key"
        self.assertEqual(self._plan().status_code, 401)
        self.assertEqual(self._plan({"X-API-Key": "wrong"}).status_code, 401)
        accepted = self._plan({"X-API-Key": "secret-key", "X-Client-Id": f"auth-{uuid.uuid4()}"})
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["metrics"]["orders"], 12)

    def test_rate_limit_returns_429_with_retry_after(self) -> None:
        os.environ["DUDU_RATE_LIMIT"] = "2"
        client_id = f"rate-{uuid.uuid4()}"
        headers = {"X-Client-Id": client_id}
        self.assertEqual(self._plan(headers).status_code, 200)
        self.assertEqual(self._plan(headers).status_code, 200)
        limited = self._plan(headers)
        self.assertEqual(limited.status_code, 429)
        self.assertIn("Retry-After", limited.headers)
        self.assertIn("detail", limited.json())

    def test_rate_limit_separate_per_client(self) -> None:
        os.environ["DUDU_RATE_LIMIT"] = "1"
        first = {"X-Client-Id": f"a-{uuid.uuid4()}"}
        second = {"X-Client-Id": f"b-{uuid.uuid4()}"}
        self.assertEqual(self._plan(first).status_code, 200)
        self.assertEqual(self._plan(first).status_code, 429)
        self.assertEqual(self._plan(second).status_code, 200)

    def test_security_headers_present(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("Referrer-Policy"), "no-referrer")
        policy = response.headers.get("Content-Security-Policy", "")
        self.assertIn("default-src 'self'", policy)
        self.assertIn("script-src 'self'", policy)

    def test_health_rate_limit_config_reported(self) -> None:
        os.environ["DUDU_RATE_LIMIT"] = "30"
        payload = self.client.get("/api/health").json()
        self.assertEqual(payload["security"]["rate_limit_per_minute"], 30)


if __name__ == "__main__":
    unittest.main()

