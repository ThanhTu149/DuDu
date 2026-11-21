"""Bọc mô hình ETA đã huấn luyện để phần còn lại của hệ thống dùng được.

Hai cách dùng:

  - `predict_native(distance_km, hour, weekday)` — dự đoán theo đúng miền dữ liệu huấn
    luyện (chuyến taxi NYC). Dùng để trả lời khách hoặc để kiểm tra mô hình.
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


class EtaModel:
    def __init__(self, regressor, metrics: dict) -> None:
        self.regressor = regressor
        self.metrics = metrics
        self.features = metrics["features"]
        self.multiplier = {int(k): float(v) for k, v in metrics["hour_multiplier"].items()}

    @classmethod
    def load(cls) -> "EtaModel | None":
        if not RF_PATH.exists() or not METRICS_PATH.exists():
            return None
        from joblib import load

        return cls(load(RF_PATH), json.loads(METRICS_PATH.read_text(encoding="utf-8")))

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
        }
