# Độ bền vững và độ nhạy của bộ điều phối

Sinh tự động bằng `python -m backend.dispatch.robustness --report` (seed cố định nên
tái lập được từng con số).

## 1. 30 seed trên cùng cấu hình (48 đơn, 8 xe)

| Chỉ số | Trung bình | Độ lệch chuẩn | Nhỏ nhất | Lớn nhất |
|---|---:|---:|---:|---:|
| Tổng quãng đường (km) | 179.5 | 36.30 | 107.8 | 264.9 |
| Tổng thời gian (phút) | 457.7 | 46.59 | 372.6 | 553.3 |
| Số đơn trễ | 0.27 | 0.64 | 0 | 3 |
| Đúng giờ (%) | 99.4 | 1.33 | 93.8 | 100.0 |
| Vi phạm luật | 6.93 | 2.77 | 0 | 13 |
| Vi phạm mức chặn | 0.07 | 0.25 | 0 | 1 |
| Tuyến quá tải | 0.00 | 0.00 | 0 | 0 |

Khoảng biến thiên giữa các seed cho thấy một kịch bản đơn lẻ không đủ đại diện: báo cáo
chính nên dùng trung bình ± độ lệch chuẩn thay vì một con số của seed 7.

## 2. So sánh 6 chiến lược xếp tuyến trên cùng bộ seed

Cùng phân công Hungarian, chỉ đổi cách sắp thứ tự giao.

| Chiến lược | Quãng đường TB (km) | Độ lệch | Đơn trễ TB | Đúng giờ TB (%) |
|---|---:|---:|---:|---:|
| Thứ tự nhập | 231.3 | 64.78 | 4.23 | 91.2 |
| Nearest Neighbor | 171.0 | 32.36 | 1.83 | 96.2 |
| NN + 2-opt | 163.6 | 27.39 | 2.23 | 95.3 |
| Clarke–Wright | 193.4 | 30.35 | 3.07 | 93.6 |
| C-W + 2-opt | 164.5 | 26.83 | 2.23 | 95.3 |
| NN + 2-opt (hạn giao) | 179.4 | 38.08 | 0.27 | 99.4 |

Kết luận (ổn định trên toàn bộ seed, không phụ thuộc một lần chạy):

- So với thứ tự nhập đơn, NN + 2-opt giảm **29.3%** quãng đường; so với Nearest Neighbor thuần giảm **4.4%**.
- Chiến lược mặc định `deadline` chấp nhận thêm **9.7%** quãng đường để kéo số đơn trễ trung bình từ 2.23 xuống 0.27 và đúng giờ từ 95.3% lên 99.4% — đúng mục tiêu ưu tiên cam kết với khách.

## 3. Độ nhạy số vòng sửa vi phạm (`max_rounds`)

Trung bình trên 5 seed:

| max_rounds | Quãng đường (km) | Đơn trễ | Vi phạm | Vi phạm mức chặn |
|---:|---:|---:|---:|---:|
| 0 | 182.9 | 0.20 | 9.40 | 3.00 |
| 1 | 188.9 | 0.20 | 7.40 | 0.60 |
| 2 | 189.3 | 0.20 | 7.00 | 0.20 |
| 4 | 187.5 | 0.20 | 6.80 | 0.00 |
| 6 | 187.5 | 0.20 | 6.80 | 0.00 |

Từ 4 lên 6 vòng chỉ đổi 0.0 km và 0.00 vi phạm — vòng sửa đã hội tụ;
đây là căn cứ để chọn mặc định 4.

## 4. Độ nhạy bán kính vùng ùn tắc (kịch bản kẹt xe, trung bình 3 seed)

| Bán kính (km) | Quãng đường sau sự cố (km) | Đơn trễ | Vi phạm | Quãng đường đi vòng do A* (km) | Số chặng đi vòng |
|---:|---:|---:|---:|---:|---:|
| 2.0 | 184.9 | 1.33 | 8.67 | 3.5 | 0.7 |
| 3.0 | 184.9 | 1.33 | 8.67 | 3.5 | 0.7 |
| 4.5 | 196.2 | 2.67 | 8.00 | 29.3 | 4.7 |
| 6.0 | 213.9 | 3.33 | 8.67 | 168.2 | 15.3 |
| 8.0 | 237.1 | 3.67 | 8.67 | 227.4 | 19.0 |

Bán kính càng lớn càng nhiều chặng bị chặn và A* phải đi vòng, quãng đường tăng tương ứng.
Bảng này là căn cứ chọn 4,5 km cho kịch bản mặc định: đủ lớn để A* thực sự tìm đường vòng,
đủ nhỏ để kế hoạch vẫn khả thi trong ca 4 giờ.

## Cách chạy lại

```powershell
python -m backend.dispatch.robustness --report
```
