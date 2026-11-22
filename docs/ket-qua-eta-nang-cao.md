# Đánh giá nâng cao mô hình ETA

Sinh tự động bằng `python ml/advanced_eval.py --report`.

## 1. Tuning hyperparameter bằng rolling-origin CV

Ba fold theo thời gian: train ngày 1–14 → validate 15–17; train 1–17 → validate 18–20;
train 1–20 → validate 21–24. Chỉ chọn cấu hình HistGradientBoosting; RandomForest giữ
tham số mặc định để tránh tốn thời gian (đã có kết quả so sánh ở `docs/ket-qua-eta.md`).

| max_iter | learning_rate | max_leaf_nodes | MAE CV trung bình |
|---:|---:|---:|---:|
| 300 | 0.08 | 63 | 3.511 |
| 200 | 0.10 | 31 | 3.504 |
| 300 | 0.06 | 31 | 3.504 |
| 300 | 0.10 | 63 | 3.510 |
| 400 | 0.06 | 63 | 3.512 |
| 250 | 0.12 | 31 | 3.508 |
| 350 | 0.08 | 127 | 3.520 |

Cấu hình tốt nhất: **max_iter=200, learning_rate=0.1, max_leaf_nodes=31** (CV MAE 3.504).
Trên tập test temporal, cấu hình này đạt MAE **3.485** so với **3.489** của cấu hình mặc định (+0.1%).

## 2. Khoảng tin cậy thực nghiệm (80%)

Học phân vị 10%/90% của phần dư trên giai đoạn calibration (ngày 25–27), chia theo 10
nhóm thời gian dự đoán; kiểm tra độ phủ trên giai đoạn evaluation (ngày 28–31).

| Phương pháp | Độ phủ thực tế | Độ rộng TB (phút) |
|---|---:|---:|
| Phân vị phần dư theo nhóm dự đoán | **82.0%** | 11.42 |
| Baseline ±15% thời gian dự đoán | 40.0% | 4.30 |

- Độ phủ cao điểm 80.3%, ngoài cao điểm 82.9% (n = 25682 chuyến).
- Cách làm này cho phép API/UI trả kèm khoảng ± để điều phối viên biết mức bất định,
  thay vì chỉ một con số ETA duy nhất.

## 3. Ablation đặc trưng

HistGradientBoosting, train ngày 1–24, test ngày 25–31; MAE (phút) và chênh lệch so với
mô hình đầy đủ.

| Biến thể | Số đặc trưng | MAE | Δ MAE |
|---|---:|---:|---:|
| đầy đủ (8 đặc trưng) | 8 | 3.489 | +0.000 |
| bỏ giờ trong ngày | 5 | 3.806 | +0.317 |
| bỏ cờ cao điểm / cuối tuần / ban đêm | 5 | 3.490 | +0.001 |
| bỏ thứ trong tuần | 7 | 3.550 | +0.061 |
| chỉ có quãng đường | 1 | 4.019 | +0.530 |
| chỉ có thời gian | 7 | 8.042 | +4.553 |

Đọc kết quả: quãng đường vẫn là đặc trưng quyết định; các đặc trưng thời gian đóng góp
phần còn lại và đặc biệt quan trọng khi so sánh cao điểm với ngoài cao điểm.
