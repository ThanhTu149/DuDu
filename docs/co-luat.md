# Cơ sở tri thức R01–R12 — nguồn gốc, xung đột và độ phủ kiểm thử

Tài liệu này đi kèm `backend/dispatch/rules.py`: giải thích 12 luật IF–THEN, thứ tự ưu tiên,
các cặp luật có thể cùng kích hoạt trên một sự kiện và cách engine xử lý, cùng bảng đối chiếu
mỗi luật với kiểm thử tự động tương ứng (`tests/test_rules.py`).

## 1. Bảng luật

Cột "cơ sở nghiệp vụ" mô tả nguyên tắc vận hành mà luật mô phỏng; đây là **giả lập phục vụ
học phần**, không trích dẫn văn bản pháp lý cụ thể. Mọi luật đều dựa trên dữ liệu mà hệ thống
thực sự có (đơn hàng, xe, giờ tới dự kiến, quận) — không có luật nào cần dữ liệu ngoài.

| Mã | Tên luật | Mức | Hành động | Ưu tiên | Cơ sở nghiệp vụ | Test |
|---|---|---|---:|---|---|---|
| R01 | Hàng tươi sống quá 2 giờ | chặn | đánh dấu | 1 | Hàng tươi sống phải tới tay người nhận trong 2 giờ để đảm bảo chất lượng | `test_r01_fresh_goods_over_two_hours` |
| R02 | Xe tải vào nội thành giờ cấm | chặn | chuyển xe | 2 | Khung giờ hạn chế xe tải vào nội đô (06:00–09:00, 16:00–20:00 theo kịch bản mô phỏng) | `test_r02_truck_ban_hours` |
| R03 | Hàng cồng kềnh không đi xe máy | chặn | chuyển xe | 3 | Thể tích kiện vượt thùng xe máy thì phải dùng xe tải | `test_r03_bulky_on_motorcycle` |
| R04 | Thu hộ tiền mặt lớn | cảnh báo | đánh dấu | 4 | Đơn COD lớn cần giao tận tay, đối chiếu tiền trước khi ký | `test_r04_large_cod` |
| R05 | Đơn hoả tốc trễ cam kết | cảnh báo | đánh dấu | 5 | Cam kết hoả tốc có SLA ngắn; trễ phải báo khách trước giờ hẹn | `test_r05_express_late` |
| R06 | Tài xế quá nhiều điểm trong ca | cảnh báo | đánh dấu | 6 | Định mức điểm/ca theo loại xe (xe máy 12, xe tải 20) để tránh quá tải lao động | `test_r06_too_many_stops` |
| R07 | Hàng dễ vỡ trên xe máy | cảnh báo | đánh dấu | 7 | Tuyến dài + xe máy khó cố định kiện dễ vỡ → yêu cầu đóng gói chống sốc | `test_r07_fragile_on_motorcycle_with_long_route` |
| R08 | Trọng tải vượt sức chứa | chặn | chuyển xe | 0 | Không xuất phát khi tổng tải tuyến vượt 100% sức chứa xe | `test_r08_over_capacity` |
| R09 | Hàng điện tử giá trị cao | cảnh báo | đánh dấu | 8 | Hàng điện tử thu hộ từ 2 triệu phải giao tận tay, ký nhận | `test_r09_high_value_electronics` |
| R10 | Tuyến dài quá 4 giờ liên tục | cảnh báo | đánh dấu | 9 | Chạy liên tục quá 240 phút cần nghỉ 15 phút trước điểm cuối | `test_r10_route_over_four_hours` |
| R11 | Ngoại thành sau giờ tan tầm | cảnh báo | đổi giờ | 10 | Giao ngoại thành sau 17:00 dễ kẹt đường về, khó kịp chuyến tiếp | `test_r11_outer_district_after_rush` |
| R12 | Kiện nặng không đi xe máy | chặn | chuyển xe | 11 | Kiện đơn lẻ > 8 kg vượt khả năng chở an toàn của xe máy | `test_r12_heavy_parcel_on_motorcycle` |

## 2. Cơ chế suy diễn và xử lý xung đột

`RuleEngine.evaluate()` chạy **suy diễn tiến** trên tập sự kiện `Facts` của từng điểm giao:

1. Duyệt luật theo `priority` tăng dần (số nhỏ chạy trước).
2. Luật kích hoạt → tạo `Verdict` kèm câu giải thích có số liệu (`detail`) để UI hiển thị.
3. Gặp luật mức **chặn** đầu tiên → dừng suy diễn cho điểm giao đó (các luật sau không xét).
4. Các luật mức **cảnh báo** xếp chồng được: cùng một điểm giao có thể có nhiều cảnh báo.

Hệ quả cần nắm khi đọc kết quả:

- **Chặn luôn thắng cảnh báo**: nếu R08 (ưu tiên 0) kích hoạt, R02/R03/R12 không được xét dù
  chúng cũng đúng. Đây là lý do bảng vi phạm trên UI có thể chỉ hiện một luật cho một đơn.
- **Ưu tiên quyết định luật chặn nào được chọn**: R01 (1) thắng R02 (2), R02 thắng R03 (3)…
  Việc đánh số ưu tiên là chủ ý nghiệp vụ: an toàn thực phẩm và tải trọng xét trước thời gian.

### Ma trận cặp luật có thể cùng đúng

| Cặp | Quan hệ | Cách engine xử lý |
|---|---|---|
| R08 × R01/R02/R03/R12 | cả hai đều mức chặn | R08 (ưu tiên 0) thắng, các luật còn lại bị bỏ qua |
| R01 × R02 | hai luật chặn | R01 (ưu tiên 1) thắng nếu hàng tươi sống tới muộn |
| R02 × R03 | hai luật chặn | R02 (2) thắng khi xe tải vào nội đô giờ cấm; R03 chỉ xét khi R02 không đúng |
| R03 × R12 | hai luật chặn, cùng điều kiện xe máy | R03 (3) thắng nếu kiện vượt 50 L; R12 (11) chỉ hiện khi R03 không đúng |
| R04 × R09 | hai cảnh báo, chồng điều kiện COD | cả hai hiện (cảnh báo xếp chồng) |
| R05 × R04 | hai cảnh báo | cả hai hiện nếu đơn vừa hoả tốc trễ vừa COD lớn |
| R06 × R07/R10 | ba cảnh báo về tải lao động | có thể hiện cùng lúc trên cùng tuyến |
| R11 × R02 | R02 chỉ áp dụng quận nội thành, R11 chỉ áp dụng ngoại thành | loại trừ nhau theo `district` |

Ca kiểm thử tương ứng: `test_blocking_rule_stops_inference`,
`test_warnings_can_stack_but_stop_after_first_block` trong `tests/test_rules.py`.

## 3. Độ phủ kiểm thử

`tests/test_rules.py` gồm 21 ca:

- 1 ca kiểm tra danh mục (đủ 12 luật, mã không trùng, câu luật có "NẾU", mức hợp lệ).
- 12 ca dương — mỗi luật R01–R12 có đúng một ca kích hoạt.
- 4 ca âm — sự kiện trung tính và các trường hợp biên (hàng tươi còn hạn, xe tải ngoài giờ
  cấm, kiện nhẹ trên xe máy) không được kích hoạt luật.
- 3 ca điều khiển suy diễn — thứ tự ưu tiên, dừng sau luật chặn, `Verdict` mang đúng ngữ
  cảnh (mã đơn, mức, giải thích) để UI "Giải trình" hiển thị lại.

Chạy riêng:

```powershell
python -m unittest tests.test_rules -v
```
