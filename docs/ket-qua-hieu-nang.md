# Hiệu năng API và an toàn khi gọi đồng thời

Sinh tự động bằng `python tools/bench_api.py --report` (TestClient trong cùng tiến
trình, không tính độ trễ mạng).

## 1. Độ trễ `/api/plan` theo số đơn

Mỗi cấu hình 5 lần, cùng seed 7 và 8 xe. Lần đầu gồm cả sinh kịch bản; các lần
sau dùng cache LRU nên nhanh hơn rõ rệt.

| Số đơn | Lần đầu (ms) | Trung vị (ms) | p95 (ms) | Ghi chú |
|---:|---:|---:|---:|---|
| 24 | 6 | 5 | 6 | đã cache từ warmup |
| 48 | 17 | 16 | 19 | có sinh kịch bản |
| 96 | 93 | 91 | 102 | có sinh kịch bản |
| 144 | 190 | 179 | 190 | có sinh kịch bản |
| 200 | 5119 | 5250 | 5390 | có sinh kịch bản |

## 2. Độ trễ `/api/incident` (kẹt xe, 48 đơn, có A* tìm đường vòng)

| Lần | Độ trễ (ms) |
|---:|---:|
| 1 | 40 |
| 2 | 22 |
| 3 | 20 |
| 4 | 22 |
| 5 | 17 |

Trung vị: **22 ms**, p95: **40 ms**.

## 3. Gọi đồng thời

- 8 luồng × 5 request = **40 request**, tổng thời gian 4.84 s.
- Thông lượng: **8.3 request/s**; trung vị 768 ms, p95 1883 ms.
- Số lỗi: **0**.
- Kết quả cùng payload trùng khớp giữa các luồng: **có** (cache `_scenarios` có lock).

Chữ ký kết quả theo payload (total_km, trễ, vi phạm):

- `7/48`: (160.34, 1, 3)
- `11/96`: (231.84, 10, 19)

## Nhận xét

- 24–144 đơn: dưới ~200 ms, thoải mái cho thao tác tương tác; ca mặc định 48 đơn chỉ
  khoảng 20 ms nhờ cache kịch bản.
- 200 đơn tăng vọt lên vài giây vì 2-opt là O(n³) trên tuyến ~25 điểm (6,8 triệu lần
  tính chặng đường). Cache chặng đường (`routing._travel` dùng lru_cache) đã rút ngắn
  đáng kể nhưng chưa triệt tiêu được độ phức tạp; hướng tối ưu tiếp theo là đánh giá
  delta O(1) cho 2-opt hoặc giới hạn cửa sổ lân cận khi tuyến dài.
- Cache kịch bản, cache chặng đường và lock giữ cho kết quả đồng nhất khi nhiều request
  chạy song song; không thấy lỗi hay sai lệch metrics.
- Đây là benchmark trong cùng tiến trình (đo logic + FastAPI), không thay thế đo tải
  thật qua mạng; con số tuyệt đối phụ thuộc máy chạy.
