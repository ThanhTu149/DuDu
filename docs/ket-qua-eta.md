# Kết quả máy học: dự đoán ETA

Số liệu dưới đây sinh ra bằng `python ml/train_eta.py` (seed cố định, chạy lại ra đúng
từng số). Dùng trực tiếp cho chương 4 của báo cáo.

## Bộ dữ liệu

- Nguồn: NYC TLC *Yellow Taxi Trip Data* 01/2024, bản parquet công khai.
- Sau khi lọc nhiễu và lấy mẫu: **200.000 chuyến** (16 ngày đầu tháng 1 trải đủ các thứ
  trong tuần, nên vẫn có cuối tuần).
- Nhãn: thời gian chạy thật (phút). Đặc trưng: quãng đường, giờ, thứ, cuối tuần, ban đêm,
  cao điểm, sin/cos giờ. Cột `day` chỉ dùng để chia dữ liệu, **không** đưa vào đặc trưng
  (tránh rò rỉ thông tin thời gian).

## Hai giao thức đánh giá

| Giao thức | Huấn luyện | Kiểm tra | Vì sao dùng |
|---|---|---|---|
| **Temporal (chính)** | ngày 1–24 (152.073 chuyến) | ngày 25–31 (47.927 chuyến) | Giống triển khai thật: học quá khứ, kiểm tra tương lai. Không có chuyến nào của cùng ngày nằm ở cả hai tập |
| Random 80/20 (tham khảo) | 160.000 | 40.000 | Cách nhiều báo cáo vẫn làm, nhưng dễ lạc quan vì cùng ngày có thể nằm cả hai tập |

Cả hai giao thức cho kết quả gần như trùng nhau (chênh ≤ 0,06 phút MAE), tức kết luận
không phụ thuộc vào cách chia. Đây là điểm nên nói khi bảo vệ.

## Kết quả — giao thức temporal (chính)

| Mô hình | MAE toàn bộ | MAE cao điểm | MAE giờ thường | RMSE | R² |
|---|---|---|---|---|---|
| Hồi quy tuyến tính | 4,69 | 4,84 | 4,63 | 7,06 | 0,635 |
| **Random Forest** | **3,55** | **3,68** | **3,49** | **5,91** | **0,745** |
| Gradient Boosting | 3,49 | 3,61 | 3,44 | 5,84 | 0,750 |

Đơn vị MAE/RMSE: phút.

## Kết quả — giao thức random 80/20 (tham khảo)

| Mô hình | MAE | MAE cao điểm | MAE giờ thường | RMSE | R² |
|---|---|---|---|---|---|
| Hồi quy tuyến tính | 4,59 | 4,80 | 4,50 | 6,81 | 0,655 |
| Random Forest | 3,49 | 3,72 | 3,39 | 5,64 | 0,763 |
| Gradient Boosting | 3,43 | 3,65 | 3,34 | 5,57 | 0,769 |

## Đọc kết quả

- Random Forest giảm **1,14 phút MAE (24%)** so với hồi quy tuyến tính và tăng R² từ 0,64
  lên 0,75. Mô hình cây bắt được ngưỡng phi tuyến (cao điểm, ban đêm) mà đường thẳng bỏ sót.
- Gradient Boosting chỉ nhỉnh hơn Random Forest **0,06 phút** — tức một mô hình cây đã đủ
  tốt, không cần thêm mô hình nặng. Đây là lập luận để giữ Random Forest (nhẹ, dễ giải thích)
  thay vì chạy theo mô hình phức tạp hơn.
- Khoảng cách hai mô hình *không* nới rộng ở giờ cao điểm như kỳ vọng ban đầu — dữ liệu chỉ
  một tháng, chênh lệch giao thông theo giờ ở NYC tháng 1 không lớn. Kết luận trung thực,
  nên ghi vào báo cáo thay vì tô hồng.

## Hệ số ùn tắc theo giờ (dùng cho TP.HCM)

| Giờ | 0h | 7h | 8h | 12h | 17h | 18h |
|---|---|---|---|---|---|---|
| Hệ số so với 12h trưa | 0,71 | 0,94 | 1,03 | 1,00 | 1,08 | 1,05 |

Cách hiểu: cùng một quãng đường, chạy 17h mất gấp 1,08 lần so với 12h trưa.
Lưu ý: OSRM trả thời gian *free-flow*, còn mô hình chỉ cung cấp **hình dạng ùn tắc theo
giờ**; không bê nguyên tốc độ tuyệt đối của taxi New York sang TP.HCM.

## Ảnh hưởng lên kế hoạch điều phối

Cùng lô 48 đơn, seed 7, cùng cách chia đơn Hungary, cùng chiến lược xếp tuyến có hạn giao:

| Cách tính thời gian | Tổng phút xe chạy | Đơn trễ | Phút trễ | Tổng km |
|---|---|---|---|---|
| OSRM free-flow | 446,5 | 1 | 7,6 | 160,3 |
| OSRM × hệ số ùn tắc (mô hình) | 417,5 | 0 | 0,0 | 190,6 |

Nhận xét trung thực: kế hoạch "biết ùn tắc" **không** làm xe chạy nhanh hơn — nó chấp nhận
đi xa hơn **+30 km** để né những chặng rơi vào giờ chậm, đổi lấy **0 đơn trễ** thay vì 1 đơn
trễ 7,6 phút. Tổng phút ước tính thấp hơn vì bộ xếp tuyến chọn thứ tự ít rơi vào khung giờ
xấu; con số này là thời gian *theo mô hình*, không phải đồng hồ thực.

Đây là lập luận nên dùng khi bảo vệ: mô hình không tạo ra tốc độ, nó làm **kế hoạch trung
thực và biết đánh đổi hơn**.

## Giới hạn

1. Dữ liệu NYC, không phải TP.HCM → hệ số ùn tắc thật của TP.HCM cao hơn, nên kết quả trên
   là cận dưới.
2. Một tháng dữ liệu, chưa có mùa mưa, ngày lễ.
3. Đặc trưng thời tiết chưa có trong dữ liệu thật (chỉ có ở bản sinh dự phòng).
4. Tập test temporal chỉ 7 ngày cuối tháng — đủ để so sánh mô hình nhưng chưa đủ để kết luận
   về mùa vụ.
