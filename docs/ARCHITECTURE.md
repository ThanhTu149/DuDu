# Kiến trúc DuDu

## Luồng một lần lập kế hoạch

```
Kịch bản (16 nút + 48 đơn)                      data/hubs.json, scenario.py
        │
        ▼
[1] Mạng lưới  ── ma trận thời gian/khoảng cách thật từ OSRM ── network.py
        │
        ▼
[2] Chia đơn cho tài xế   ── chia lô theo tải ── ghép lô–xe bằng Hungary  assignment.py
        │
        ▼
[3] Xếp tuyến từng xe     ── Nearest Neighbor → 2-opt ── ETA từng điểm    routing.py
        │
        ▼
[4] Đối chiếu cơ sở luật  ── 8 luật IF–THEN, suy diễn tiến, có giải trình  rules.py
        │
        ▼
[5] Tác tử sửa và lặp     ── vi phạm → đổi xe → lập lại tuyến → kiểm tra   agent.py
        │
        ▼
   Kế hoạch + số liệu + nhật ký quyết định  ──►  API  ──►  giao diện
```

## Ranh giới module

| Module | Trách nhiệm | Không làm gì |
|---|---|---|
| `network.py` | nạp ma trận, A*, khoảng cách chim bay | không quyết định gì |
| `assignment.py` | chia đơn thành lô, ghép lô với xe | không xếp thứ tự trong tuyến |
| `routing.py` | thứ tự giao, ETA, tổng km | không đổi xe của đơn |
| `rules.py` | cơ sở luật, giải trình | không tự sửa kế hoạch |
| `agent.py` | vòng lặp nhận biết–quyết định–hành động | không tự tính tuyến, chỉ gọi lại |
| `app.py` | API mỏng | không chứa thuật toán |
| `web/` | hiển thị và thao tác | không tự tính toán gì |

Quy ước: mọi module thuật toán nhận `Network` + danh sách dict thuần, trả về dict hoặc
dataclass có `as_dict()`. Nhờ vậy API và giao diện không phụ thuộc vào chi tiết cài đặt.

## API

| Endpoint | Việc |
|---|---|
| `GET /api/health` | kiểm tra sống, số nút, số luật |
| `GET /api/hubs` | 16 nút + khung bao để vẽ bản đồ |
| `GET /api/scenario?seed&orders` | kịch bản tái lập được |
| `POST /api/plan` | chạy tác tử: tuyến, số liệu, vi phạm, nhật ký |
| `POST /api/incident` | sự cố xe hỏng / kẹt xe (A* đi vòng) / kho đóng → chia lại |
| `GET /api/compare` | bảng so sánh chiến lược cho báo cáo |
| `GET /api/rules` | danh sách luật để hiển thị |
| `GET /api/geometry?a&b` | đường đi thật giữa 2 nút (có cache) |

## Ghi chú kỹ thuật

- **A\* dùng ở đâu trong hệ thống thật?** Khi mô phỏng "kẹt xe diện rộng", các nút nằm trong
  bán kính 4,5 km quanh tâm thành phố bị chặn **đi thẳng** với nhau (`congestion_edges`).
  Tác tử bọc mạng lưới bằng `RoutingView`: chặng nào bị chặn thì gọi A* tìm đường vòng qua
  nút khác, rồi cộng km/phút của đường vòng vào kế hoạch. Nhật ký ghi rõ "A* tìm đường vòng
  tránh vùng ùn tắc: N chặng, +X km" để giảng viên thấy thuật toán thật sự chạy, không phải
  khai báo cho có. Heuristic dùng đường chim bay chia tốc độ tối đa 70 km/h nên không vượt
  chi phí thật (điều kiện admissible); kiểm thử `tests/test_network.py` khẳng định đường
  vòng không đi qua chặng bị cấm và luôn đắt hơn đường trực tiếp.
- **Vì sao 2-opt có hai hàm mục tiêu?** Một tuyến ngắn nhất chưa chắc giao đúng hẹn. Báo cáo
  so sánh hai biến thể để thấy rõ đánh đổi km ↔ tỷ lệ đúng giờ.
- **Vì sao có bước sửa tải sau Hungary?** Hungary tối thiểu chi phí, không biết ràng buộc
  sức chứa theo từng xe; bước sửa chuyển đơn nhỏ nhất sang xe còn chỗ.
- **Vì sao đơn được làm tròn về nút mạng?** 16 nút đại diện cho 16 khu vực; toạ độ thật của
  đơn lệch trong bán kính ~1 km để bản đồ không chồng điểm, còn định tuyến dùng nút.

