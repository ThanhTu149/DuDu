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

Cùng lô 48 đơn, seed 7, cùng cách chia đơn Hungary, cùng chiến lược xếp tuyến có hạn giao.
Hệ số ùn tắc được áp theo **giờ trong ngày** (0–23) tại thời điểm xuất phát mỗi chặng:

| Cách tính thời gian | Tổng phút xe chạy | Đơn trễ | Phút trễ | Tổng km |
|---|---|---|---|---|
| OSRM free-flow | 446,5 | 1 | 7,6 | 160,3 |
| OSRM × hệ số ùn tắc (mô hình) | 450,2 | 1 | 8,6 | 160,3 |

Nhận xét trung thực: khi tính đúng hệ số theo giờ, kế hoạch "biết ùn tắc" dự báo tổng thời
gian **dài hơn free-flow 3,7 phút (+0,8%)**, quãng đường và số đơn trễ không đổi. So sánh
thêm seed 11 và 21 cũng cho kết quả tương tự (+0,7–1,0% thời gian, cùng km và số trễ) — mô
hình không tìm được thứ tự giao rẻ hơn vì thời gian thực tế tăng đều trên mọi chặng.

Đây là kết luận đúng bản chất: **mô hình không tạo ra tốc độ**. Giá trị của nó nằm ở chỗ
ETA sát thực tế hơn, có khoảng tin cậy 80% (xem `docs/ket-qua-eta-nang-cao.md`), và giúp
điều phối viên thấy trước nguy cơ trễ thay vì tin vào con số free-flow lạc quan. Muốn giảm
trễ thật cần đổi lịch xuất phát/đội xe, không chỉ đổi thứ tự giao.

## Giới hạn

1. Dữ liệu NYC, không phải TP.HCM → hệ số ùn tắc thật của TP.HCM cao hơn, nên kết quả trên
   là cận dưới.
2. Một tháng dữ liệu, chưa có mùa mưa, ngày lễ.
3. Đặc trưng thời tiết chưa có trong dữ liệu thật (chỉ có ở bản sinh dự phòng).
4. Tập test temporal chỉ 7 ngày cuối tháng — đủ để so sánh mô hình nhưng chưa đủ để kết luận
   về mùa vụ.

## Đánh giá nâng cao

Xem `docs/ket-qua-eta-nang-cao.md` (sinh bằng `python ml/advanced_eval.py --report`):
tuning hyperparameter bằng rolling-origin CV, khoảng tin cậy thực nghiệm 80% và ablation
đặc trưng. Kết quả chính: cấu hình HGB mặc định đã gần tối ưu theo CV; khoảng 80% đạt độ phủ
81,3% (baseline ±15% chỉ 40,0%); bỏ nhóm đặc trưng giờ làm MAE tăng lên 3,806 phút.

