# Module máy học: dự đoán thời gian giao (ETA)

Chương 4 của báo cáo nằm ở đây.

## Dữ liệu

| Hạng mục | Giá trị |
|---|---|
| Nguồn | NYC TLC — *Yellow Taxi Trip Data*, tháng 01/2024 (parquet công khai, không cần tài khoản) |
| Bản ghi gốc | ~3 triệu chuyến |
| Sau lọc + lấy mẫu | 200.000 chuyến (160.000 huấn luyện / 40.000 kiểm tra) |
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

## Kết quả

| Mô hình | MAE toàn bộ | MAE cao điểm | MAE giờ thường | RMSE | R² |
|---|---|---|---|---|---|
| Hồi quy tuyến tính | 4,65 phút | 4,88 | 4,56 | 6,94 | 0,652 |
| **Random Forest** | **3,54 phút** | **3,78** | **3,44** | **5,79** | **0,758** |

Random Forest giảm 24% MAE so với hồi quy tuyến tính. Chênh lệch rõ hơn ở giờ cao điểm
(1,10 phút) so với giờ thường (1,12 phút) — tức mô hình cây bắt được ngưỡng phi tuyến
mà đường thẳng không bắt được, dù mức chênh không lớn vì dữ liệu NYC chỉ trong một tháng.

## Cách dùng trong hệ thống

- `EtaModel.predict_native(distance_km, hour, weekday)` — trả lời khách "đơn này bao lâu".
- `EtaModel.hour_factor(hour)` — hệ số ùn tắc so với 12h trưa (0h: 0,76 · 7h: 1,06 ·
  8h: 1,10 · 17h: 1,16), nhân lên thời gian free-flow của OSRM.
- `POST /api/plan` với `{"eta": "ml"}` để xếp tuyến có tính ùn tắc.

## Giới hạn cần nói trong báo cáo

1. Dữ liệu NYC, không phải TP.HCM — mức ùn tắc thật của TP.HCM cao hơn, nên hệ số ở đây
   là cận dưới.
2. Chỉ một tháng dữ liệu, chưa học được mùa mưa hay dịp lễ.
3. Chưa có đặc trưng thời tiết thật trong dữ liệu; `is_rain` chỉ có ở bản dự phòng.
