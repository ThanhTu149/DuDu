"""Dựng bộ dữ liệu huấn luyện cho mô hình ETA.

Nguồn thật: một tháng dữ liệu chuyến taxi vàng của NYC TLC (bản parquet công khai,
không cần tài khoản). Mỗi dòng là một chuyến thật: quãng đường (đồng hồ), giờ đón,
giờ trả. Nhãn `duration_min` là thời gian chạy thật -> đây chính là bài toán dự đoán
thời gian di chuyển mà đề 32 yêu cầu.

Vì sao dùng dữ liệu NYC chứ không lấy GPS TP.HCM? Không có bộ dữ liệu hành trình
TP.HCM công khai. Nhóm dùng dữ liệu thật ở thành phố khác để huấn luyện, sau đó
hiệu chỉnh tốc độ về TP.HCM bằng ma trận OSRM (xem `city_factor` trong train_eta.py),
và ghi rõ giới hạn này trong báo cáo.

    python ml/build_dataset.py            # dùng cache nếu đã có
    python ml/build_dataset.py --force    # dựng lại từ parquet

Nếu chưa tải parquet, script sinh dữ liệu dự phòng từ ma trận OSRM (có ghi rõ
`nguon = mo_phong` trong file CSV) để cả nhóm vẫn chạy được.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
RAW_PARQUET = ROOT / "data" / "raw" / "yellow_tripdata_2024-01.parquet"
MATRIX = ROOT / "data" / "processed" / "matrix.json"
OUT_TRAIN = ROOT / "data" / "processed" / "eta_train.csv"
OUT_TEST = ROOT / "data" / "processed" / "eta_test.csv"

MILES_TO_KM = 1.609344
SAMPLE_SIZE = 200_000
SEED = 20261121


def _peak_mask(hours: np.ndarray, weekdays: np.ndarray) -> np.ndarray:
    morning = (hours >= 7) & (hours <= 9)
    evening = (hours >= 16) & (hours <= 19)
    weekend = weekdays >= 5
    return (~weekend) & (morning | evening)


def from_nightly_taxi() -> pd.DataFrame:
    """Đọc parquet thật của NYC TLC, lọc nhiễu, đổi đơn vị, thêm đặc trưng thời gian."""
    columns = ["tpep_pickup_datetime", "tpep_dropoff_datetime", "trip_distance", "passenger_count", "PULocationID"]
    raw = pd.read_parquet(RAW_PARQUET, columns=columns)

    pickup = pd.to_datetime(raw["tpep_pickup_datetime"], errors="coerce")
    dropoff = pd.to_datetime(raw["tpep_dropoff_datetime"], errors="coerce")
    duration = (dropoff - pickup).dt.total_seconds() / 60.0
    distance_km = raw["trip_distance"].astype(float) * MILES_TO_KM

    frame = pd.DataFrame({
        "distance_km": distance_km,
        "duration_min": duration,
        "hour": pickup.dt.hour,
        "weekday": pickup.dt.dayofweek,
        "day": pickup.dt.day,
        "passenger": raw["passenger_count"].fillna(0).astype(int),
        "pu_zone": raw["PULocationID"].astype(int),
    })

    # Lọc chuyến lỗi: thời gian âm/phi thực tế, quãng đường 0, tốc độ vô lý
    frame = frame[
        frame["duration_min"].between(2, 180)
        & frame["distance_km"].between(0.3, 60)
        & frame["hour"].notna()
        & frame["weekday"].notna()
        & (frame["passenger"] <= 6)
    ]
    frame["speed_kmh"] = frame["distance_km"] / (frame["duration_min"] / 60)
    frame = frame[frame["speed_kmh"].between(3, 90)]

    frame["is_peak"] = _peak_mask(frame["hour"].to_numpy(), frame["weekday"].to_numpy()).astype(int)
    frame["is_weekend"] = (frame["weekday"] >= 5).astype(int)
    frame["is_night"] = ((frame["hour"] >= 22) | (frame["hour"] <= 5)).astype(int)
    frame["hour_sin"] = np.sin(2 * np.pi * frame["hour"] / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * frame["hour"] / 24)
    frame["nguon"] = "nyc_tlc"
    return frame


def from_matrix_fallback(n: int = 12_000) -> pd.DataFrame:
    """Dự phòng khi chưa tải được parquet: sinh chuyến từ ma trận OSRM + hệ số giao thông."""
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    ids = matrix["ids"]
    durations = np.array(matrix["duration_s"], dtype=float)
    distances = np.array(matrix["distance_m"], dtype=float)
    rng = np.random.default_rng(SEED)

    picks = rng.integers(0, len(ids), size=(n, 2))
    dist_km = distances[picks[:, 0], picks[:, 1]] / 1000.0
    base_min = durations[picks[:, 0], picks[:, 1]] / 60.0
    hours = rng.integers(0, 24, size=n)
    weekdays = rng.integers(0, 7, size=n)
    peak = _peak_mask(hours, weekdays)

    congestion = np.where(peak, rng.uniform(1.55, 2.15, size=n), rng.uniform(0.95, 1.2, size=n))
    rain = rng.random(n) < 0.18
    congestion = congestion * np.where(rain, rng.uniform(1.1, 1.35, size=n), 1.0)
    noise = rng.normal(1.0, 0.08, size=n)

    frame = pd.DataFrame({
        "distance_km": dist_km,
        "duration_min": base_min * congestion * noise,
        "hour": hours,
        "weekday": weekdays,
        "passenger": rng.integers(1, 3, size=n),
        "pu_zone": 0,
    })
    frame["is_peak"] = peak.astype(int)
    frame["is_weekend"] = (weekdays >= 5).astype(int)
    frame["is_night"] = ((hours >= 22) | (hours <= 5)).astype(int)
    frame["hour_sin"] = np.sin(2 * np.pi * hours / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * hours / 24)
    frame["nguon"] = "mo_phong"
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description="Dựng dataset ETA")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if OUT_TRAIN.exists() and not args.force:
        existing = pd.read_csv(OUT_TRAIN, nrows=1)
        print(f"[cache] đã có {OUT_TRAIN.relative_to(ROOT)} (nguồn={existing['nguon'][0]})")
        return 0

    started = time.time()
    if RAW_PARQUET.exists():
        print(f"[data] đọc {RAW_PARQUET.name} …")
        frame = from_nightly_taxi()
        source = "nyc_tlc"
    else:
        print("[data] chưa có parquet, sinh dữ liệu dự phòng từ ma trận OSRM")
        frame = from_matrix_fallback()
        source = "mo_phong"

    if len(frame) > SAMPLE_SIZE:
        frame = frame.sample(SAMPLE_SIZE, random_state=SEED).reset_index(drop=True)

    frame = frame.drop(columns=["speed_kmh"], errors="ignore")
    shuffled = frame.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    split = int(len(shuffled) * 0.8)
    train, test = shuffled.iloc[:split], shuffled.iloc[split:]

    OUT_TRAIN.parent.mkdir(parents=True, exist_ok=True)
    train.to_csv(OUT_TRAIN, index=False, float_format="%.3f")
    test.to_csv(OUT_TEST, index=False, float_format="%.3f")

    print(f"[ok] nguồn={source} · {len(frame):,} chuyến · train {len(train):,} / test {len(test):,} "
          f"· {time.time() - started:.1f}s")
    print(f"     trung vị: {frame['duration_min'].median():.1f} phút · "
          f"{frame['distance_km'].median():.1f} km · "
          f"{frame['distance_km'].median() / (frame['duration_min'].median() / 60):.1f} km/h")
    return 0


if __name__ == "__main__":
    sys.exit(main())

