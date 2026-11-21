"""Huấn luyện và đánh giá mô hình dự đoán thời gian giao (ETA).

Hai mô hình để so sánh — đây là nội dung chương Máy học của báo cáo:

  1. Hồi quy tuyến tính nhiều biến (baseline dễ giải thích, sai số hệ thống vì quan hệ
     thời gian–quãng đường không tuyến tính khi tắc đường).
  2. Random Forest (nhiều cây quyết định, bắt được ngưỡng phi tuyến: giờ cao điểm,
     cuối tuần, ban đêm).

Đánh giá tách riêng giờ cao điểm và giờ thường, vì đó là chỗ hai mô hình khác nhau rõ
nhất, và cũng là câu hỏi giảng viên hay hỏi.

Sau khi huấn luyện, script tính `city_factor` — hệ số đổi tốc độ NYC → TP.HCM dựa trên
ma trận OSRM — rồi lưu tất cả vào `ml/models/`.

    python ml/train_eta.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
TRAIN = ROOT / "data" / "processed" / "eta_train.csv"
TEST = ROOT / "data" / "processed" / "eta_test.csv"
MATRIX = ROOT / "data" / "processed" / "matrix.json"
MODEL_DIR = ROOT / "ml" / "models"

FEATURES = ["distance_km", "hour", "weekday", "is_weekend", "is_night", "is_peak", "hour_sin", "hour_cos"]
TARGET = "duration_min"


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not TRAIN.exists() or not TEST.exists():
        raise SystemExit("Chưa có dataset. Chạy: python ml/build_dataset.py")
    return pd.read_csv(TRAIN), pd.read_csv(TEST)


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }


def hcm_reference_min_per_km() -> float:
    """Thời gian/km thực tế trên mạng đường TP.HCM theo OSRM (dùng để hiệu chỉnh)."""
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    durations = np.array(matrix["duration_s"], dtype=float) / 60.0
    distances = np.array(matrix["distance_m"], dtype=float) / 1000.0
    mask = distances > 0.5
    return float(np.median(durations[mask] / distances[mask]))


def main() -> int:
    train, test = load()
    x_train, y_train = train[FEATURES].to_numpy(), train[TARGET].to_numpy()
    x_test, y_test = test[FEATURES].to_numpy(), test[TARGET].to_numpy()
    peak = test["is_peak"].to_numpy() == 1

    models = {
        "linear": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=120, max_depth=16, min_samples_leaf=8, n_jobs=-1, random_state=20261121
        ),
    }

    results: dict[str, dict] = {}
    fitted: dict[str, object] = {}
    started = time.time()
    for name, model in models.items():
        model.fit(x_train, y_train)
        predicted = model.predict(x_test)
        results[name] = {
            "all": metrics(y_test, predicted),
            "peak": metrics(y_test[peak], predicted[peak]),
            "off_peak": metrics(y_test[~peak], predicted[~peak]),
        }
        fitted[name] = model
        print(f"[{name}] MAE {results[name]['all']['mae']:.2f} phút · "
              f"cao điểm {results[name]['peak']['mae']:.2f} · "
              f"thường {results[name]['off_peak']['mae']:.2f}")

    # Hệ số ùn tắc theo giờ: cùng quãng đường, giờ h chậm hơn 12h trưa bao nhiêu lần.
    # Đây là thứ dùng được cho TP.HCM: OSRM cho thời gian free-flow, mô hình cho *hình
    # dạng* ùn tắc trong ngày — không bê nguyên tốc độ tuyệt đối của NYC sang.
    rf = fitted["random_forest"]
    hours = np.arange(24)
    grid = []
    for hour in hours:
        for distance in (3.0, 6.0, 10.0, 15.0, 25.0):
            grid.append([distance, hour, 2, 0, 1 if (hour >= 22 or hour <= 5) else 0,
                         1 if (7 <= hour <= 9 or 16 <= hour <= 19) else 0,
                         float(np.sin(2 * np.pi * hour / 24)), float(np.cos(2 * np.pi * hour / 24))])
    grid_pred = rf.predict(np.array(grid)).reshape(len(hours), 5)
    median_by_hour = np.median(grid_pred, axis=1)
    hour_multiplier = (median_by_hour / median_by_hour[12]).round(3)

    baseline = rf.predict(x_test)
    nyc_min_per_km = float(np.median(baseline / test["distance_km"].to_numpy()))

    importance = None
    if hasattr(rf, "feature_importances_"):
        importance = {
            name: float(value)
            for name, value in sorted(zip(FEATURES, rf.feature_importances_), key=lambda kv: -kv[1])
        }

    payload = {
        "features": FEATURES,
        "target": TARGET,
        "rows": {"train": int(len(train)), "test": int(len(test))},
        "source": str(train["nguon"].iloc[0]) if "nguon" in train else "unknown",
        "results": results,
        "feature_importance": importance,
        "hour_multiplier": {int(hour): float(value) for hour, value in zip(hours, hour_multiplier)},
        "speed_note": {
            "nyc_min_per_km": nyc_min_per_km,
            "hcm_osrm_min_per_km": hcm_reference_min_per_km(),
            "note": "OSRM là thời gian free-flow, dữ liệu NYC là thời gian thực có ùn tắc; "
                    "vì vậy chỉ dùng mô hình để suy ra hình dạng ùn tắc theo giờ.",
        },
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": round(time.time() - started, 1),
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    dump(fitted["random_forest"], MODEL_DIR / "eta_rf.joblib", compress=3)
    dump(fitted["linear"], MODEL_DIR / "eta_linear.joblib", compress=3)
    (MODEL_DIR / "eta_metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n== Bảng cho báo cáo (MAE, phút) ==")
    print(f"{'mô hình':<16}{'toàn bộ':>10}{'cao điểm':>12}{'thường':>10}{'RMSE':>9}{'R²':>8}")
    for name in models:
        row = results[name]
        print(f"{name:<16}{row['all']['mae']:>10.2f}{row['peak']['mae']:>12.2f}"
              f"{row['off_peak']['mae']:>10.2f}{row['all']['rmse']:>9.2f}{row['all']['r2']:>8.3f}")
    print(f"\nlưu model vào {MODEL_DIR.relative_to(ROOT)}")
    print("hệ số ùn tắc theo giờ (so với 12h): " + " ".join(
        f"{hour}h:{value:.2f}" for hour, value in payload["hour_multiplier"].items() if hour in (0, 7, 8, 12, 17, 18)
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())

