# Kết quả máy học: dự đoán ETA

Số liệu dưới đây sinh ra bằng `python ml/train_eta.py` (seed cố định, chạy lại ra đúng
từng số). Dùng trực tiếp cho chương 4 của báo cáo.

## Bộ dữ liệu

- Nguồn: NYC TLC *Yellow Taxi Trip Data* 01/2024, bản parquet công khai.
- Sau khi lọc nhiễu và lấy mẫu: **200.000 chuyến**, chia 80/20 → 160.000 huấn luyện,
  40.000 kiểm tra.
- Nhãn: thời gian chạy thật (phút). Đặc trưng: quãng đường, giờ, thứ, cuối tuần, ban đêm,
  cao điểm, sin/cos giờ.

## Kết quả

| Mô hình | MAE toàn bộ | MAE cao điểm | MAE giờ thường | RMSE | R² |
|---|---|---|---|---|---|
| Hồi quy tuyến tính | 4,65 | 4,88 | 4,56 | 6,94 | 0,652 |
| **Random Forest** | **3,54** | **3,78** | **3,44** | **5,79** | **0,758** |

Đơn vị MAE/RMSE: phút.

**Đọc kết quả:** Random Forest giảm 1,11 phút MAE (24%) và tăng R² từ 0,65 lên 0,76.
Khoảng cách giữa hai mô hình *không* nới rộng ở giờ cao điểm như kỳ vọng ban đầu — lý do
là dữ liệu chỉ có một tháng, chênh lệch giao thông theo giờ ở NYC tháng 1 không lớn. Đây là
một kết luận trung thực, nên ghi vào báo cáo thay vì tô hồng.

## Hệ số ùn tắc theo giờ (trích)

| Giờ | 0h | 7h | 8h | 12h | 17h |
|---|---|---|---|---|---|
| Hệ số so với 12h trưa | 0,76 | 1,06 | 1,10 | 1,00 | 1,16 |

Cách hiểu: cùng một quãng đường, chạy 17h mất gấp 1,16 lần so với 12h trưa.

## Ảnh hưởng lên kế hoạch điều phối

Cùng lô 48 đơn, seed 7, cùng cách chia đơn Hungary:

| Cách tính thời gian | Tổng phút xe chạy | Đơn trễ | Phút trễ |
|---|---|---|---|
| OSRM free-flow | 446,5 | 1 | 8 |
| OSRM × hệ số ùn tắc (mô hình) | 452,4 | 1 | 1 |

Nhận xét: kế hoạch "biết ùn tắc" chậm hơn 1,3% nhưng giảm mạnh số phút trễ, vì bộ xếp
tuyến có hạn giao biết phải dồn đơn gấp lên trước. Đây là lập luận nên dùng khi bảo vệ:
mô hình không làm xe chạy nhanh hơn, nó làm **kế hoạch trung thực hơn**.

## Giới hạn

1. Dữ liệu NYC, không phải TP.HCM → hệ số ùn tắc thật của TP.HCM cao hơn, nên kết quả trên
   là cận dưới.
2. Một tháng dữ liệu, chưa có mùa mưa, ngày lễ.
3. Đặc trưng thời tiết chưa có trong dữ liệu thật (chỉ có ở bản sinh dự phòng).
