# Kết quả đối chiếu cơ sở luật

Ba kịch bản seed 7, 11, 23 · 48 đơn · 8 xe. Số liệu sinh bằng `python -m backend.dispatch.rule_stats --report`.

| Luật | Nội dung | Mức | Hành động | Vòng đầu | Sau khi sửa |
|---|---|---|---|---|---|
| R08 | Trọng tải vượt sức chứa | chặn | chuyen_xe | 0 | 0 |
| R01 | Hàng tươi sống quá 2 giờ | chặn | danh_dau | 0 | 0 |
| R02 | Xe tải vào nội thành giờ cấm | chặn | chuyen_xe | 9 | 0 |
| R03 | Hàng cồng kềnh không đi xe máy | chặn | chuyen_xe | 0 | 0 |
| R04 | Thu hộ tiền mặt lớn | cảnh báo | danh_dau | 7 | 10 |
| R05 | Đơn hoả tốc trễ cam kết | cảnh báo | danh_dau | 0 | 0 |
| R06 | Tài xế quá nhiều điểm trong ca | cảnh báo | danh_dau | 3 | 3 |
| R07 | Hàng dễ vỡ trên xe máy | cảnh báo | danh_dau | 0 | 0 |
| R09 | Hàng điện tử giá trị cao | cảnh báo | danh_dau | 1 | 1 |
| R10 | Tuyến dài quá 4 giờ liên tục | cảnh báo | danh_dau | 0 | 0 |
| R11 | Ngoại thành sau giờ tan tầm | cảnh báo | doi_gio | 0 | 0 |
| R12 | Kiện nặng không đi xe máy | chặn | chuyen_xe | 1 | 0 |

## Kết quả điều phối của ba ca

| Seed | Quãng đường (km) | Đơn trễ | Vi phạm vòng đầu | Còn lại sau khi sửa |
|---|---|---|---|---|
| 7 | 160.3 | 1 | 5 | 3 |
| 11 | 212.2 | 0 | 8 | 5 |
| 23 | 171.5 | 0 | 8 | 6 |

## Cách đọc

- Luật mức **chặn** (R01, R02, R03, R08, R12) buộc tác tử phải sửa kế hoạch trước khi chốt; nếu không sửa được thì đơn bị đánh dấu chuyển người điều phối. Cột "sau khi sửa" của các luật này phải bằng 0 mới coi là kế hoạch hợp lệ.
- Luật mức **cảnh báo** (R04, R05, R06, R07, R09, R10, R11) không chặn kế hoạch, chỉ nhắc tài xế hoặc điều phối viên xử lý thêm. Số của nhóm này có thể *tăng* sau khi sửa, vì đổi xe làm thay đổi tuyến nên có thêm đơn rơi vào ngưỡng — đây là hiện tượng thật, không phải lỗi đếm.
- Vì vậy chỉ số đáng báo cáo là **số vi phạm mức chặn còn lại sau khi sửa**, không phải tổng số vi phạm.
