# Module máy học: dự đoán thời gian giao (ETA)

Mục 2.3 của báo cáo nằm ở đây.

## Dữ liệu

| Hạng mục | Giá trị |
|---|---|
| Nguồn | NYC TLC — *Yellow Taxi Trip Data*, tháng 01/2024 (parquet công khai, không cần tài khoản) |
| Bản ghi gốc | ~3 triệu chuyến |
| Sau lọc + lấy mẫu | 200.000 chuyến — chia temporal: 152.073 huấn luyện / 47.927 kiểm tra |
| Nhãn | `duration_min` = giờ trả − giờ đón (thời gian chạy thật) |
| Đặc trưng | quãng đường (km), giờ, thứ, cuối tuần, ban đêm, cao điểm, sin/cos của giờ |

Lọc bỏ chuyến lỗi: thời gian ngoài 2–180 phút, quãng đường ngoài 0,3–60 km, tốc độ
ngoài 3–90 km/h (đây là các dòng đồng hồ bấm sai hoặc khách huỷ giữa đường).

**Vì sao không dùng dữ liệu TP.HCM?** Không có bộ hành trình GPS công khai. Nhóm dùng dữ
liệu thật ở đô thị lớn để học *quan hệ* giữa quãng đường, giờ và thời gian chạy; phần áp
dụng về TP.HCM chỉ lấy **hình dạng ùn tắc theo giờ**, còn thời gian nền vẫn là OSRM. Giới
hạn này ghi rõ trong báo cáo, không giấu.

Tải dữ liệu:

```powershell
# ~50 MB, một lần là đủ
curl.exe -L -o data/raw/yellow_tripdata_2024-01.parquet `
  https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet
python ml/build_dataset.py
python ml/train_eta.py
```

Không có mạng thì `build_dataset.py` tự sinh dữ liệu dự phòng từ ma trận OSRM, ghi cột
`nguon = mo_phong` để không ai nhầm là dữ liệu thật.

Khi dựng lại dataset (thêm cột `day` để chia temporal) phải chạy `--force`:

```powershell
python ml/build_dataset.py --force
python ml/train_eta.py
```

## Hai giao thức chia dữ liệu

- **Temporal (chính)**: train ngày 1–24, test ngày 25–31 — giống triển khai thật, không rò rỉ
  chuyến cùng ngày. Đây là số liệu dùng trong báo cáo.
- **Random 80/20 (tham khảo)**: cách chia phổ biến nhưng dễ lạc quan; kết quả nằm trong
  `eta_metrics.json` ở khoá `results_random`.

Hai giao thức chênh nhau ≤ 0,06 phút MAE → kết luận không phụ thuộc cách chia.

## Kết quả (temporal — chính)

| Mô hình | MAE toàn bộ | MAE cao điểm | MAE giờ thường | RMSE | R² |
|---|---|---|---|---|---|
| Hồi quy tuyến tính | 4,69 phút | 4,84 | 4,63 | 7,06 | 0,635 |
| **Random Forest** | **3,55 phút** | **3,68** | **3,49** | **5,91** | **0,745** |
| Gradient Boosting | 3,49 | 3,61 | 3,44 | 5,84 | 0,750 |

Random Forest giảm 24% MAE so với hồi quy tuyến tính. Gradient Boosting chỉ nhỉnh hơn
0,06 phút → mô hình cây đã đủ tốt, không cần thêm mô hình nặng.

## Lưu mô hình để API nạp nhanh

`eta_rf.joblib` được lưu **không nén** (`compress=0`): dung lượng ~109 MB (không commit vì
`.gitignore` đã chặn) nhưng API nạp trong ~0,2 giây thay vì 2–3 giây nếu nén. Server còn
nạp sẵn mô hình ở luồng nền lúc khởi động (`lifespan`) nên request đầu tiên không bị chậm.

## Cách dùng trong hệ thống

- `EtaModel.predict_native(distance_km, hour, weekday)` — trả lời khách "đơn này bao lâu".
- `EtaModel.hour_factor(hour)` — hệ số ùn tắc so với 12h trưa (0h: 0,71 · 7h: 0,94 ·
  8h: 1,03 · 17h: 1,08), nhân lên thời gian free-flow của OSRM.
- `POST /api/plan` với `{"eta": "ml"}` để xếp tuyến có tính ùn tắc.

## Giới hạn cần nói trong báo cáo

1. Dữ liệu NYC, không phải TP.HCM — mức ùn tắc thật của TP.HCM cao hơn, nên hệ số ở đây
   là cận dưới.
2. Chỉ một tháng dữ liệu, chưa học được mùa mưa hay dịp lễ.
3. Chưa có đặc trưng thời tiết thật trong dữ liệu; `is_rain` chỉ có ở bản dự phòng.



## Đánh giá nâng cao

```powershell
python ml/advanced_eval.py --report   # -> docs/ket-qua-eta-nang-cao.md
```

Ba phần: tuning HistGradientBoosting bằng rolling-origin CV, khoảng tin cậy thực nghiệm 80%
(học phân vị phần dư theo nhóm dự đoán), và ablation từng nhóm đặc trưng. Script chỉ ghi báo
cáo, không ghi đè mô hình hay `eta_metrics.json` đang dùng cho demo.

## Hiệu chuẩn khoảng tin cậy

```powershell
python ml/calibrate_eta.py   # -> ml/models/eta_quantiles.json (commit được, ~1 KB)
```

Học phân vị 10%/90% phần dư theo 10 nhóm dự đoán trên ngày 25–27, đo độ phủ trên ngày 28–31;
API dùng file này cho `GET /api/eta/interval`.
