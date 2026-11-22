"""Bọc mô hình ETA đã huấn luyện để phần còn lại của hệ thống dùng được.

Ba cách dùng:

  - `predict_native(distance_km, hour, weekday)` — dự đoán theo đúng miền dữ liệu huấn
    luyện (chuyến taxi NYC). Dùng để trả lời khách hoặc để kiểm tra mô hình.
  - `interval_native(...)` — khoảng tin cậy 80% học từ phân vị phần dư
    (`ml/calibrate_eta.py` lưu trong `ml/models/eta_quantiles.json`).
  - `hcm_minutes(osrm_min, hour)` — áp lên thời gian free-flow của OSRM TP.HCM bằng hệ số
    ùn tắc theo giờ mà mô hình học được. Đây là cách dùng trong xếp tuyến: OSRM cho biết
    đi bao lâu khi đường thoáng, mô hình cho biết giờ đó đường đông gấp mấy lần.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parent / "models"
RF_PATH = MODEL_DIR / "eta_rf.joblib"
METRICS_PATH = MODEL_DIR / "eta_metrics.json"
QUANTILES_PATH = MODEL_DIR / "eta_quantiles.json"


class EtaModel:
    def __init__(self, regressor, metrics: dict, quantiles: dict | None = None) -> None:
        self.regressor = regressor
        self.metrics = metrics
        self.features = metrics["features"]
        self.multiplier = {int(k): float(v) for k, v in metrics["hour_multiplier"].items()}
        # Khoảng tin cậy 80% học từ phân vị phần dư; có thể thiếu nếu chưa hiệu chuẩn
        self.quantiles = quantiles

    @classmethod
    def load(cls) -> "EtaModel | None":
        if not RF_PATH.exists() or not METRICS_PATH.exists():
            return None
        from joblib import load

        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        quantiles = None
        if QUANTILES_PATH.exists():
            try:
                quantiles = json.loads(QUANTILES_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                quantiles = None
        return cls(load(RF_PATH), metrics, quantiles)

    # -- dự đoán -- ------------------------------------------------------
    def _vector(self, distance_km: float, hour: int, weekday: int) -> np.ndarray:
        is_weekend = int(weekday >= 5)
        is_night = int(hour >= 22 or hour <= 5)
        is_peak = int(not is_weekend and (7 <= hour <= 9 or 16 <= hour <= 19))
        return np.array([[
            distance_km, hour, weekday, is_weekend, is_night, is_peak,
            float(np.sin(2 * np.pi * hour / 24)), float(np.cos(2 * np.pi * hour / 24)),
        ]])

    def predict_native(self, distance_km: float, hour: int, weekday: int = 2) -> float:
        """Thời gian dự đoán (phút) theo miền dữ liệu huấn luyện."""
        return float(self.regressor.predict(self._vector(distance_km, hour, weekday))[0])

    def interval_native(self, distance_km: float, hour: int, weekday: int = 2) -> dict:
        """Khoảng tin cậy 80% cho một chặng theo miền dữ liệu huấn luyện."""
        predicted = self.predict_native(distance_km, hour, weekday)
        if not self.quantiles or not self.quantiles.get("bins"):
            return {
                "predicted_min": round(predicted, 2),
                "low_min": None,
                "high_min": None,
                "coverage": None,
                "method": "chưa hiệu chuẩn",
            }
        bins = self.quantiles["bins"]
        chosen = next((item for item in bins if predicted <= item["upper_min"]), bins[-1])
        low = max(0.1, predicted + float(chosen["q10"]))
        high = max(low + 0.1, predicted + float(chosen["q90"]))
        return {
            "predicted_min": round(predicted, 2),
            "low_min": round(low, 2),
            "high_min": round(high, 2),
            "coverage": float(self.quantiles.get("nominal_coverage", 0.8)),
            "method": self.quantiles.get("method", "residual_deciles_by_predicted_duration"),
        }

    def interval_summary(self) -> dict | None:
        if not self.quantiles:
            return None
        return {
            "nominal_coverage": self.quantiles.get("nominal_coverage"),
            "coverage_actual": self.quantiles.get("coverage_actual"),
            "mean_width_min": self.quantiles.get("mean_width_min"),
            "bins": len(self.quantiles.get("bins", [])),
            "calibration_rows": self.quantiles.get("calibration_rows"),
        }

    def hour_factor(self, hour: int) -> float:
        return self.multiplier.get(int(hour) % 24, 1.0)

    def hcm_minutes(self, osrm_min: float, hour: float) -> float:
        """Nhân thời gian free-flow với hệ số ùn tắc của giờ xuất phát."""
        return osrm_min * self.hour_factor(int(hour) // 60 % 24)

    def as_dict(self) -> dict:
        return {
            "available": True,
            "test_mae": self.metrics["results"]["random_forest"]["all"]["mae"],
            "test_mae_peak": self.metrics["results"]["random_forest"]["peak"]["mae"],
            "rows": self.metrics["rows"],
            "source": self.metrics.get("source"),
            "trained_at": self.metrics.get("trained_at"),
            "interval": self.interval_summary(),
        }
