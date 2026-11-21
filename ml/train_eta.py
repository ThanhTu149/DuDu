"""Huấn luyện và đánh giá mô hình dự đoán thời gian giao (ETA).

Ba mô hình để so sánh — đây là nội dung chương Máy học của báo cáo:

  1. Hồi quy tuyến tính nhiều biến (baseline dễ giải thích, sai số hệ thống vì quan hệ
     thời gian–quãng đường không tuyến tính khi tắc đường).
  2. Random Forest (nhiều cây quyết định, bắt được ngưỡng phi tuyến).
  3. Gradient Boosting (HistGradientBoosting của scikit-learn) — mô hình mạnh hơn cho
     dữ liệu dạng bảng, dùng làm mốc trên để kiểm tra Random Forest đã đủ tốt chưa.

Đánh giá dùng **hai giao thức chia dữ liệu** để tránh bị hỏi xoáy:

  * **temporal (chính)**: train 24 ngày đầu tháng, test 7 ngày cuối tháng. Giống mô hình
    thật sự được triển khai: huấn luyện trên quá khứ, kiểm tra trên tương lai.
  * **random (tham khảo)**: chia ngẫu nhiên 80/20 như nhiều bài báo cáo hay làm, nhưng dễ
    lạc quan vì cùng ngày có thể nằm cả hai tập.

Sau khi huấn luyện, script tính `hour_multiplier` — hệ số ùn tắc theo giờ — rồi lưu mô
hình và số liệu vào `ml/models/`.

    python ml/build_dataset.py --force   # nếu cần dựng lại dataset
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
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

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
SEED = 20261121


def load() -> pd.DataFrame:
    if not TRAIN.exists() or not TEST.exists():
        raise SystemExit("Chưa có dataset. Chạy: python ml/build_dataset.py --force")
    return pd.concat([pd.read_csv(TRAIN), pd.read_csv(TEST)], ignore_index=True)


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


def new_models() -> dict[str, object]:
    """Mô hình mới cho mỗi lần chia dữ liệu (tránh dùng lại trạng thái đã fit)."""
    return {
        "linear": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=120, max_depth=16, min_samples_leaf=8, n_jobs=-1, random_state=SEED
        ),
        "gradient_boosting": HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.08, max_leaf_nodes=63, random_state=SEED
        ),
    }


def evaluate(x_train, y_train, x_test, y_test, peak) -> tuple[dict, dict]:
    results: dict[str, dict] = {}
    fitted: dict[str, object] = {}
    for name, model in new_models().items():
        model.fit(x_train, y_train)
        predicted = model.predict(x_test)
        results[name] = {
            "all": metrics(y_test, predicted),
            "peak": metrics(y_test[peak], predicted[peak]),
            "off_peak": metrics(y_test[~peak], predicted[~peak]),
        }
        fitted[name] = model
    return results, fitted


def split_temporal(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = frame[frame["day"] <= 24]
    test = frame[frame["day"] >= 25]
    return train, test


def split_random(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return train_test_split(frame, test_size=0.2, random_state=SEED)


def fit_and_score(name: str, train: pd.DataFrame, test: pd.DataFrame) -> tuple[dict, dict, dict]:
    x_train, y_train = train[FEATURES].to_numpy(), train[TARGET].to_numpy()
    x_test, y_test = test[FEATURES].to_numpy(), test[TARGET].to_numpy()
    peak = test["is_peak"].to_numpy() == 1
    results, fitted = evaluate(x_train, y_train, x_test, y_test, peak)
    rows = {"train": int(len(train)), "test": int(len(test))}
    print(f"\n== Giao thức {name}: train {rows['train']:,} · test {rows['test']:,} ==")
    print(f"{'mô hình':<20}{'MAE':>8}{'MAE cao điểm':>14}{'MAE thường':>12}{'RMSE':>8}{'R²':>8}")
    for model_name, row in results.items():
        print(f"{model_name:<20}{row['all']['mae']:>8.2f}{row['peak']['mae']:>14.2f}"
              f"{row['off_peak']['mae']:>12.2f}{row['all']['rmse']:>8.2f}{row['all']['r2']:>8.3f}")
    return results, fitted, rows


def main() -> int:
    started = time.time()
    frame = load()
    has_day = "day" in frame.columns

    results_temporal = results_random = None
    fitted: dict = {}
    rows: dict = {}
    primary = "random"

    if has_day:
        train, test = split_temporal(frame)
        if len(test) > 500:
            results_temporal, fitted, rows = fit_and_score("temporal (chính)", train, test)
            primary = "temporal"

    train_r, test_r = split_random(frame)
    results_random, _, rows_random = fit_and_score("random 80/20 (tham khảo)", train_r, test_r)

    chosen_results = results_temporal if results_temporal is not None else results_random
    chosen_rows = rows if results_temporal is not None else rows_random
    test_frame = split_temporal(frame)[1] if results_temporal is not None else test_r

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

    baseline = rf.predict(test_frame[FEATURES].to_numpy())
    nyc_min_per_km = float(np.median(baseline / test_frame["distance_km"].to_numpy()))

    importance = None
    if hasattr(rf, "feature_importances_"):
        importance = {
            name: float(value)
            for name, value in sorted(zip(FEATURES, rf.feature_importances_), key=lambda kv: -kv[1])
        }

    payload = {
        "features": FEATURES,
        "target": TARGET,
        "rows": chosen_rows,
        "source": str(frame["nguon"].iloc[0]) if "nguon" in frame else "unknown",
        "split": primary,
        "evaluation_note": (
            "Chỉ số chính tính theo giao thức temporal (train 24 ngày đầu tháng, test 7 ngày "
            "cuối tháng) để tránh lạc quan do rò rỉ cùng ngày; kết quả chia ngẫu nhiên để "
            "trong results_random để so sánh."
            if primary == "temporal"
            else "Chưa có cột ngày nên chỉ chia ngẫu nhiên 80/20."
        ),
        "results": chosen_results,
        "results_random": results_random,
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
    (MODEL_DIR / "eta_metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nlưu mô hình vào {MODEL_DIR.relative_to(ROOT)} (giao thức chính: {primary})")
    print("hệ số ùn tắc theo giờ (so với 12h): " + " ".join(
        f"{hour}h:{value:.2f}"
        for hour, value in payload["hour_multiplier"].items()
        if hour in (0, 7, 8, 12, 17, 18)
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
