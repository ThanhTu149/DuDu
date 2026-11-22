# Hiệu năng API và an toàn khi gọi đồng thời

Sinh tự động bằng `python tools/bench_api.py --report` (TestClient trong cùng tiến
trình, không tính độ trễ mạng).

## 1. Độ trễ `/api/plan` theo số đơn

Mỗi cấu hình 5 lần, cùng seed 7 và 8 xe. Lần đầu gồm cả sinh kịch bản; các lần
sau dùng cache LRU nên nhanh hơn rõ rệt.

| Số đơn | Lần đầu (ms) | Trung vị (ms) | p95 (ms) | Ghi chú |
|---:|---:|---:|---:|---|
| 24 | 20 | 18 | 21 | đã cache từ warmup |
| 48 | 22 | 21 | 23 | có sinh kịch bản |
| 96 | 56 | 55 | 56 | có sinh kịch bản |
| 144 | 100 | 94 | 128 | có sinh kịch bản |
| 200 | 1238 | 1212 | 1238 | có sinh kịch bản |

## 2. Độ trễ `/api/incident` (kẹt xe, 48 đơn, có A* tìm đường vòng)

| Lần | Độ trễ (ms) |
|---:|---:|
| 1 | 37 |
| 2 | 50 |
| 3 | 69 |
| 4 | 34 |
| 5 | 53 |

Trung vị: **50 ms**, p95: **69 ms**.

## 3. Gọi đồng thời

- 8 luồng × 5 request = **40 request**, tổng thời gian 1.74 s.
- Thông lượng: **22.9 request/s**; trung vị 285 ms, p95 497 ms.
- Số lỗi: **0**.
- Kết quả cùng payload trùng khớp giữa các luồng: **có** (cache `_scenarios` có lock).

Chữ ký kết quả theo payload (total_km, trễ, vi phạm):

- `7/48`: (160.34, 1, 3)
- `11/96`: (231.84, 10, 19)

## Nhận xét

- 24–144 đơn: dưới ~150 ms, thoải mái cho thao tác tương tác; ca mặc định 48 đơn chỉ
  khoảng 25 ms nhờ cache kịch bản.
- 200 đơn (tuyến ~25 điểm) mất ~1,2 s thay vì ~5 s trước đây: 2-opt đã được viết lại
  để tính chi phí từng phương án bằng mảng cục bộ (ma trận chặng, giờ hẹn, phục vụ)
  thay vì gọi `sequence_score` hàng triệu lần — cùng công thức, cùng kết quả, nhanh
  hơn ~2,4× (API nhanh hơn ~4× vì bỏ thêm overhead). Vẫn là O(n³) nên nếu cần 500+
  đơn/thời gian thực thì bước tiếp theo là đánh giá delta O(1) hoặc cửa sổ lân cận.
- Cache kịch bản, cache chặng đường và lock giữ cho kết quả đồng nhất khi nhiều request
  chạy song song; không thấy lỗi hay sai lệch metrics.
- Đây là benchmark trong cùng tiến trình (đo logic + FastAPI), không thay thế đo tải
  thật qua mạng; con số tuyệt đối phụ thuộc máy chạy.
