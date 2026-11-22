"""Kiểm thử khoảng tin cậy ETA: logic phân nhóm dự đoán và endpoint API (nếu có mô hình)."""

from __future__ import annotations

import unittest

import numpy as np

from ml.eta_model import RF_PATH, EtaModel

FEATURES = ["distance_km", "hour", "weekday", "is_weekend", "is_night", "is_peak", "hour_sin", "hour_cos"]


class _DummyRegressor:
    def __init__(self, value: float = 10.0) -> None:
        self.value = value

    def predict(self, _x) -> np.ndarray:  # noqa: ANN001
        return np.array([self.value])


def _metrics() -> dict:
    return {
        "features": FEATURES,
        "hour_multiplier": {str(hour): 1.0 for hour in range(24)},
        "results": {"random_forest": {"all": {"mae": 3.5}, "peak": {"mae": 4.0}}},
        "rows": {"train": 100, "test": 20},
        "source": "test",
        "trained_at": "2026-01-01T00:00:00",
    }


def _quantiles() -> dict:
    return {
        "nominal_coverage": 0.8,
        "coverage_actual": 0.81,
        "mean_width_min": 11.0,
        "calibration_rows": 100,
        "method": "residual_deciles_by_predicted_duration",
        "bins": [
            {"upper_min": 5.0, "q10": -1.0, "q90": 2.0},
            {"upper_min": 15.0, "q10": -2.0, "q90": 4.0},
            {"upper_min": 30.0, "q10": -3.0, "q90": 6.0},
        ],
    }


class TestEtaInterval(unittest.TestCase):
    def test_interval_uses_matching_bin(self) -> None:
        model = EtaModel(_DummyRegressor(10.0), _metrics(), _quantiles())
        result = model.interval_native(8.0, 17, 2)
        self.assertAlmostEqual(result["predicted_min"], 10.0)
        self.assertAlmostEqual(result["low_min"], 8.0)   # 10 + (-2)
        self.assertAlmostEqual(result["high_min"], 14.0)  # 10 + 4
        self.assertEqual(result["coverage"], 0.8)

    def test_interval_clamps_low_at_positive(self) -> None:
        quantiles = _quantiles()
        quantiles["bins"][1]["q10"] = -50.0
        model = EtaModel(_DummyRegressor(10.0), _metrics(), quantiles)
        result = model.interval_native(3.0, 8, 2)
        self.assertGreater(result["low_min"], 0)
        self.assertGreater(result["high_min"], result["low_min"])

    def test_interval_without_calibration(self) -> None:
        model = EtaModel(_DummyRegressor(10.0), _metrics(), None)
        result = model.interval_native(5.0, 9, 2)
        self.assertIsNone(result["low_min"])
        self.assertIsNone(result["high_min"])
        self.assertIsNone(model.interval_summary())

    def test_summary_reports_calibration(self) -> None:
        model = EtaModel(_DummyRegressor(10.0), _metrics(), _quantiles())
        summary = model.interval_summary()
        self.assertEqual(summary["bins"], 3)
        self.assertAlmostEqual(summary["coverage_actual"], 0.81)


@unittest.skipUnless(RF_PATH.exists(), "máy chưa có mô hình ETA — bỏ qua test endpoint")
class TestEtaIntervalApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from fastapi.testclient import TestClient

            from backend.app import app

            cls.client_context = TestClient(app)
            cls.client = cls.client_context.__enter__()
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("cần httpx")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def test_interval_endpoint(self) -> None:
        response = self.client.get("/api/eta/interval", params={"distance_km": 8, "hour": 17, "weekday": 2})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertLess(payload["low_min"], payload["predicted_min"])
        self.assertGreater(payload["high_min"], payload["predicted_min"])
        self.assertEqual(payload["coverage"], 0.8)

    def test_info_includes_interval_summary(self) -> None:
        payload = self.client.get("/api/eta/info").json()
        self.assertIn("interval", payload)
        self.assertGreaterEqual(payload["interval"]["bins"], 1)


if __name__ == "__main__":
    unittest.main()
