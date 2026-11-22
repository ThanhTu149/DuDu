# Khoảng cách tới thứ tự giao tối ưu (routing optimality gap)

Sinh tự động bằng `python -m backend.dispatch.optimal --report`.

## Cách đo

Với mỗi ca thử (2 quy mô × 3 seed), giữ nguyên phân công đơn của Hungarian rồi so
quãng đường của từng chiến lược xếp tuyến với **thứ tự giao tối ưu** tìm bằng quy
hoạch động giữ nhớ (Held–Karp, tuyến mở). Công cụ đã được đối chiếu độc lập với vét
cạn hoán vị trong `tests/test_optimal.py`.
Gap = (km heuristic − km tối ưu)/km tối ưu.

Ca thử: 12 đơn/8 xe, 24 đơn/8 xe · seed 7, 11, 21.

## Kết quả

| Chiến lược xếp tuyến | Quãng đường TB (km) | Gap TB | Gap lớn nhất | Đơn trễ TB | Đúng giờ TB |
|---|---:|---:|---:|---:|---:|
| Thứ tự nhập | 105.6 | +17.6% | +28.6% | 0.33 | 98.6% |
| Nearest Neighbor | 92.6 | +2.8% | +5.5% | 0.00 | 100.0% |
| NN + 2-opt | 91.7 | +1.4% | +2.9% | 0.00 | 100.0% |
| Clarke–Wright | 110.2 | +20.8% | +41.1% | 0.17 | 99.3% |
| C-W + 2-opt | 92.4 | +1.9% | +5.9% | 0.00 | 100.0% |
| NN + 2-opt (hạn giao) | 91.7 | +1.4% | +2.9% | 0.00 | 100.0% |

## Đọc kết quả

- **NN + 2-opt** gần tối ưu nhất: gap trung bình **1.4%**, lớn nhất
  2.9% — đây là lý do 2-opt hầu như không còn gì để cải thiện khi
  mỗi tuyến chỉ vài điểm.
- **Nearest Neighbor** thuần có gap 2.8%; 2-opt kéo
  xuống 1.4% và giảm 13.1% quãng đường so với thứ tự
  nhập đơn.
- **Clarke–Wright ở cấp thứ tự giao** gap 20.8% vì nó được
  thiết kế để gộp tuyến ở cấp đội xe, không phải sắp thứ tự cho một danh sách điểm có sẵn.
- **NN + 2-opt theo hạn giao** giữ gap tương đương 2-opt thuần nhưng đổi lại số đơn trễ
  trung bình 0.00 so với 0.00 —
  đây là cơ sở để hệ thống chọn chiến lược `deadline` làm mặc định.

## Kiểm chứng công cụ

`exact_vrp()` (giải chính xác cả chia đơn + xếp tuyến cho ca ≤ 8 đơn, bitmask DP) được
đối chiếu với vét cạn độc lập trong `tests/test_optimal.py`; gap chia đơn chỉ nên đọc như
cận dưới vì nghiệm tối ưu không có hạn giao và không có phí sử dụng xe.
