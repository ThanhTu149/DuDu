"""Hiệu chuẩn khoảng tin cậy cho ETA: học phân vị phần dư theo nhóm dự đoán.

Sinh `ml/models/eta_quantiles.json` (nhỏ, commit được) để API trả kèm khoảng tin cậy:

    python ml/calibrate_eta.py

Cách làm (cùng giao thức temporal như lúc huấn luyện):

- Calibration: ngày 25–27 của tháng (không nằm trong tập train ngày 1–24).
- Evaluation: ngày 28–31.
- Chia dự đoán thành 10 nhóm theo phân vị; học q10/q90 phần dư (thực tế − dự đoán) mỗi nhóm.
- Khoảng 80% = dự đoán + (q10, q90); đo lại độ phủ thực tế trên tập evaluation.

Chạy lại khi đổi mô hình ETA.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
TRAIN = ROOT / "data" / "processed" / "eta_train.csv"
TEST = ROOT / "data" / "processed" / "eta_test.csv"
MODEL = ROOT / "ml" / "models" / "eta_rf.joblib"
OUTPUT = ROOT / "ml" / "models" / "eta_quantiles.json"

FEATURES = ["distance_km", "hour", "weekday", "is_weekend", "is_night", "is_peak", "hour_sin", "hour_cos"]
TARGET = "duration_min"
NOMINAL = 0.8
N_BINS = 10


def load_test_frame() -> pd.DataFrame:
    if not TRAIN.exists() or not TEST.exists():
        raise SystemExit("Chưa có dataset. Chạy: python ml/build_dataset.py --force")
    frame = pd.concat([pd.read_csv(TRAIN), pd.read_csv(TEST)], ignore_index=True)
    return frame[frame["day"] >= 25].copy()


def main() -> int:
    if not MODEL.exists():
        raise SystemExit("Chưa có ml/models/eta_rf.joblib — chạy python ml/train_eta.py trước.")
    model = load(MODEL)
    frame = load_test_frame()
    frame["predicted"] = model.predict(frame[FEATURES].to_numpy())
    frame["residual"] = frame[TARGET] - frame["predicted"]

    calib = frame[(frame["day"] >= 25) & (frame["day"] <= 27)].copy()
    evaluation = frame[frame["day"] >= 28].copy()

    calib["bin"] = pd.qcut(calib["predicted"], N_BINS, labels=False, duplicates="drop")
    quantiles = calib.groupby("bin")["residual"].quantile([0.1, 0.9]).unstack()
    upper = calib.groupby("bin")["predicted"].max()

    bins = []
    for bin_index in quantiles.index:
        bins.append({
            "upper_min": round(float(upper.loc[bin_index]), 3),
            "q10": round(float(quantiles.loc[bin_index, 0.1]), 3),
            "q90": round(float(quantiles.loc[bin_index, 0.9]), 3),
        })
    bins.sort(key=lambda item: item["upper_min"])

    def interval_for(predicted: float) -> tuple[float, float]:
        chosen = next((item for item in bins if predicted <= item["upper_min"]), bins[-1])
        return predicted + chosen["q10"], predicted + chosen["q90"]

    lows = []
    highs = []
    for predicted in evaluation["predicted"]:
        low, high = interval_for(float(predicted))
        lows.append(low)
        highs.append(high)
    evaluation["low"] = lows
    evaluation["high"] = highs
    inside = (evaluation[TARGET] >= evaluation["low"]) & (evaluation[TARGET] <= evaluation["high"])
    widths = evaluation["high"] - evaluation["low"]

    payload = {
        "nominal_coverage": NOMINAL,
        "method": "residual_deciles_by_predicted_duration",
        "calibration_rows": int(len(calib)),
        "evaluation_rows": int(len(evaluation)),
        "coverage_actual": round(float(inside.mean()), 4),
        "mean_width_min": round(float(widths.mean()), 3),
        "bins": bins,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"đã ghi {OUTPUT.relative_to(ROOT)}")
    print(f"độ phủ thực tế: {payload['coverage_actual'] * 100:.1f}% (danh nghĩa {NOMINAL * 100:.0f}%)")
    print(f"độ rộng trung bình: {payload['mean_width_min']:.2f} phút · {len(bins)} nhóm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
