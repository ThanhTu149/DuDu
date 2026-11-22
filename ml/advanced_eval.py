"""Đánh giá nâng cao cho mô hình ETA: tuning bằng CV theo thời gian, khoảng tin cậy, ablation.

Sinh báo cáo:

    python ml/advanced_eval.py --report

Ba phần (đều dùng đúng giao thức temporal: train 24 ngày đầu, test 7 ngày cuối tháng):

1. **Tuning hyperparameter** bằng rolling-origin CV (3 fold: train 1–14 → validate 15–17;
   1–17 → 18–20; 1–20 → 21–24), lưới nhỏ cho HistGradientBoosting; so cấu hình tốt nhất
   với cấu hình mặc định đang dùng trên tập test temporal.
2. **Khoảng tin cậy thực nghiệm**: chia test thành calibration (ngày 25–27) và evaluation
   (ngày 28–31), học phân vị 10%/90% của phần dư theo 10 nhóm thời gian dự đoán, đo độ phủ
   thực tế của khoảng 80% so với baseline "±15%".
3. **Ablation đặc trưng**: bỏ từng nhóm đặc trưng (giờ, cờ cao điểm, thứ trong tuần) và thử
   mô hình chỉ có quãng đường / chỉ có thời gian để định lượng đóng góp.

Lưu ý: script chỉ ghi báo cáo, **không ghi đè** mô hình hay `ml/models/eta_metrics.json`
đang dùng cho bản demo.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
TRAIN = ROOT / "data" / "processed" / "eta_train.csv"
TEST = ROOT / "data" / "processed" / "eta_test.csv"
MODEL_DIR = ROOT / "ml" / "models"
SEED = 20261121

FEATURES = ["distance_km", "hour", "weekday", "is_weekend", "is_night", "is_peak", "hour_sin", "hour_cos"]
TARGET = "duration_min"
GROUPS = {
    "giờ trong ngày": ["hour", "hour_sin", "hour_cos"],
    "cờ cao điểm / cuối tuần / ban đêm": ["is_peak", "is_weekend", "is_night"],
    "thứ trong tuần": ["weekday"],
}

DEFAULT_HGB = {"max_iter": 300, "learning_rate": 0.08, "max_leaf_nodes": 63}
GRID = [
    DEFAULT_HGB,
    {"max_iter": 200, "learning_rate": 0.10, "max_leaf_nodes": 31},
    {"max_iter": 300, "learning_rate": 0.06, "max_leaf_nodes": 31},
    {"max_iter": 300, "learning_rate": 0.10, "max_leaf_nodes": 63},
    {"max_iter": 400, "learning_rate": 0.06, "max_leaf_nodes": 63},
    {"max_iter": 250, "learning_rate": 0.12, "max_leaf_nodes": 31},
    {"max_iter": 350, "learning_rate": 0.08, "max_leaf_nodes": 127},
]
FOLDS = [
    ((1, 14), (15, 17)),
    ((1, 17), (18, 20)),
    ((1, 20), (21, 24)),
]


def load_frame() -> pd.DataFrame:
    if not TRAIN.exists() or not TEST.exists():
        raise SystemExit("Chưa có dataset. Chạy: python ml/build_dataset.py --force")
    return pd.concat([pd.read_csv(TRAIN), pd.read_csv(TEST)], ignore_index=True)


def fit_hgb(train: pd.DataFrame, features: list[str], config: dict | None = None) -> HistGradientBoostingRegressor:
    model = HistGradientBoostingRegressor(random_state=SEED, **(config or DEFAULT_HGB))
    model.fit(train[features].to_numpy(), train[TARGET].to_numpy())
    return model


def mae(model, frame: pd.DataFrame, features: list[str]) -> float:
    predicted = model.predict(frame[features].to_numpy())
    return float(mean_absolute_error(frame[TARGET].to_numpy(), predicted))


def tune(frame: pd.DataFrame) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    for config in GRID:
        scores: list[float] = []
        for (train_from, train_to), (val_from, val_to) in FOLDS:
            train = frame[(frame["day"] >= train_from) & (frame["day"] <= train_to)]
            valid = frame[(frame["day"] >= val_from) & (frame["day"] <= val_to)]
            model = fit_hgb(train, FEATURES, config)
            scores.append(mae(model, valid, FEATURES))
        rows.append({**config, "cv_mae": statistics.fmean(scores), "folds": scores})
    best = min(rows, key=lambda row: row["cv_mae"])
    return rows, best


def uncertainty(frame: pd.DataFrame) -> dict:
    model_path = MODEL_DIR / "eta_rf.joblib"
    if not model_path.exists():
        raise SystemExit("Chưa có ml/models/eta_rf.joblib — chạy python ml/train_eta.py trước.")
    model = load(model_path)
    frame = frame.copy()
    frame["pred"] = model.predict(frame[FEATURES].to_numpy())
    frame["residual"] = frame[TARGET] - frame["pred"]
    calib = frame[(frame["day"] >= 25) & (frame["day"] <= 27)].copy()
    evaluation = frame[frame["day"] >= 28].copy()

    # Ưu tiên dùng đúng bảng phân vị đã xuất cho API (ml/calibrate_eta.py) để số liệu
    # trong báo cáo, API và UI khớp nhau; chỉ khi thiếu file mới chia lại nhóm tại chỗ.
    quantiles_path = MODEL_DIR / "eta_quantiles.json"
    calib_count = int(len(calib))
    if quantiles_path.exists():
        saved = json.loads(quantiles_path.read_text(encoding="utf-8"))
        bins = saved.get("bins") or []
        calib_count = int(saved.get("calibration_rows") or len(calib))
        lower = []
        upper = []
        for predicted in evaluation["pred"]:
            chosen = next((item for item in bins if float(predicted) <= item["upper_min"]), bins[-1])
            lower.append(float(predicted) + float(chosen["q10"]))
            upper.append(float(predicted) + float(chosen["q90"]))
        evaluation["lower"] = lower
        evaluation["upper"] = upper
    else:
        calib["bin"] = pd.qcut(calib["pred"], 10, labels=False, duplicates="drop")
        quantiles = calib.groupby("bin")["residual"].quantile([0.1, 0.9]).unstack()
        evaluation["bin"] = pd.qcut(evaluation["pred"], 10, labels=False, duplicates="drop")

        lower = []
        upper = []
        for _, row in evaluation.iterrows():
            index = min(int(row["bin"]) if pd.notna(row["bin"]) else 0, len(quantiles) - 1)
            lower.append(row["pred"] + quantiles.iloc[index][0.1])
            upper.append(row["pred"] + quantiles.iloc[index][0.9])
        evaluation["lower"] = lower
        evaluation["upper"] = upper
    inside = (evaluation[TARGET] >= evaluation["lower"]) & (evaluation[TARGET] <= evaluation["upper"])
    width = evaluation["upper"] - evaluation["lower"]

    naive_lower = evaluation["pred"] * 0.85
    naive_upper = evaluation["pred"] * 1.15
    naive_inside = (evaluation[TARGET] >= naive_lower) & (evaluation[TARGET] <= naive_upper)

    peak = evaluation["is_peak"] == 1
    return {
        "n_calib": calib_count,
        "n_eval": int(len(evaluation)),
        "coverage": float(inside.mean()),
        "width": float(width.mean()),
        "mae": float(mean_absolute_error(evaluation[TARGET], evaluation["pred"])),
        "coverage_peak": float(inside[peak].mean()) if peak.any() else 0.0,
        "coverage_off_peak": float(inside[~peak].mean()) if (~peak).any() else 0.0,
        "naive_coverage": float(naive_inside.mean()),
        "naive_width": float((naive_upper - naive_lower).mean()),
    }


def ablation(frame: pd.DataFrame) -> list[dict]:
    train = frame[frame["day"] <= 24]
    test = frame[frame["day"] >= 25]
    rows: list[dict] = []
    variants = [("đầy đủ (8 đặc trưng)", list(FEATURES))]
    for name, dropped in GROUPS.items():
        variants.append((f"bỏ {name}", [feature for feature in FEATURES if feature not in dropped]))
    variants.append(("chỉ có quãng đường", ["distance_km"]))
    variants.append(("chỉ có thời gian", [feature for feature in FEATURES if feature != "distance_km"]))
    for label, features in variants:
        model = fit_hgb(train, features)
        rows.append({"variant": label, "features": features, "mae": mae(model, test, features)})
    full = rows[0]["mae"]
    for row in rows:
        row["delta"] = row["mae"] - full
    return rows


def write_report(tuning_rows: list[dict], best: dict, best_test_mae: float, default_test_mae: float,
                 uncertainty_row: dict, ablation_rows: list[dict], path: Path) -> Path:
    lines = [
        "# Đánh giá nâng cao mô hình ETA",
        "",
        "Sinh tự động bằng `python ml/advanced_eval.py --report`.",
        "",
        "## 1. Tuning hyperparameter bằng rolling-origin CV",
        "",
        "Ba fold theo thời gian: train ngày 1–14 → validate 15–17; train 1–17 → validate 18–20;",
        "train 1–20 → validate 21–24. Chỉ chọn cấu hình HistGradientBoosting; RandomForest giữ",
        "tham số mặc định để tránh tốn thời gian (đã có kết quả so sánh ở `docs/ket-qua-eta.md`).",
        "",
        "| max_iter | learning_rate | max_leaf_nodes | MAE CV trung bình |",
        "|---:|---:|---:|---:|",
    ]
    for row in tuning_rows:
        lines.append(
            f"| {row['max_iter']} | {row['learning_rate']:.2f} | {row['max_leaf_nodes']} | {row['cv_mae']:.3f} |"
        )
    lines += [
        "",
        f"Cấu hình tốt nhất: **max_iter={best['max_iter']}, learning_rate={best['learning_rate']}, "
        f"max_leaf_nodes={best['max_leaf_nodes']}** (CV MAE {best['cv_mae']:.3f}).",
        f"Trên tập test temporal, cấu hình này đạt MAE **{best_test_mae:.3f}** so với "
        f"**{default_test_mae:.3f}** của cấu hình mặc định "
        f"({(default_test_mae - best_test_mae) / default_test_mae * 100:+.1f}%).",
        "",
        "## 2. Khoảng tin cậy thực nghiệm (80%)",
        "",
        "Học phân vị 10%/90% của phần dư trên giai đoạn calibration (ngày 25–27), chia theo 10",
        "nhóm thời gian dự đoán; kiểm tra độ phủ trên giai đoạn evaluation (ngày 28–31).",
        "",
        "| Phương pháp | Độ phủ thực tế | Độ rộng TB (phút) |",
        "|---|---:|---:|",
        f"| Phân vị phần dư theo nhóm dự đoán | **{uncertainty_row['coverage'] * 100:.1f}%** | {uncertainty_row['width']:.2f} |",
        f"| Baseline ±15% thời gian dự đoán | {uncertainty_row['naive_coverage'] * 100:.1f}% | {uncertainty_row['naive_width']:.2f} |",
        "",
        f"- Độ phủ cao điểm {uncertainty_row['coverage_peak'] * 100:.1f}%, ngoài cao điểm "
        f"{uncertainty_row['coverage_off_peak'] * 100:.1f}% (n = {uncertainty_row['n_eval']} chuyến).",
        "- Cách làm này cho phép API/UI trả kèm khoảng ± để điều phối viên biết mức bất định,",
        "  thay vì chỉ một con số ETA duy nhất.",
        "",
        "## 3. Ablation đặc trưng",
        "",
        "HistGradientBoosting, train ngày 1–24, test ngày 25–31; MAE (phút) và chênh lệch so với",
        "mô hình đầy đủ.",
        "",
        "| Biến thể | Số đặc trưng | MAE | Δ MAE |",
        "|---|---:|---:|---:|",
    ]
    for row in ablation_rows:
        lines.append(
            f"| {row['variant']} | {len(row['features'])} | {row['mae']:.3f} | {row['delta']:+.3f} |"
        )
    lines += [
        "",
        "Đọc kết quả: quãng đường vẫn là đặc trưng quyết định; các đặc trưng thời gian đóng góp",
        "phần còn lại và đặc biệt quan trọng khi so sánh cao điểm với ngoài cao điểm.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Đánh giá nâng cao mô hình ETA")
    parser.add_argument("--report", action="store_true", help="ghi docs/ket-qua-eta-nang-cao.md")
    args = parser.parse_args()

    started = time.time()
    frame = load_frame()
    print(f"dataset: {len(frame):,} dòng")
    tuning_rows, best = tune(frame)
    print("tuning xong, cấu hình tốt nhất:", best["cv_mae"], {k: best[k] for k in DEFAULT_HGB})

    train = frame[frame["day"] <= 24]
    test = frame[frame["day"] >= 25]
    default_model = fit_hgb(train, FEATURES)
    default_test_mae = mae(default_model, test, FEATURES)
    best_model = fit_hgb(train, FEATURES, {key: best[key] for key in DEFAULT_HGB})
    best_test_mae = mae(best_model, test, FEATURES)
    print(f"test temporal — mặc định {default_test_mae:.3f} · tốt nhất {best_test_mae:.3f}")

    uncertainty_row = uncertainty(frame)
    print(f"độ phủ khoảng 80%: {uncertainty_row['coverage'] * 100:.1f}% "
          f"(naive {uncertainty_row['naive_coverage'] * 100:.1f}%)")

    ablation_rows = ablation(frame)
    print("ablation:", {row["variant"]: round(row["mae"], 3) for row in ablation_rows})

    if args.report:
        target = write_report(
            tuning_rows, best, best_test_mae, default_test_mae, uncertainty_row, ablation_rows,
            ROOT / "docs" / "ket-qua-eta-nang-cao.md",
        )
        print(f"[report] ghi {target.relative_to(ROOT)}")
    print(f"xong sau {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
