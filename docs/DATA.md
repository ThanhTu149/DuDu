# Nguồn dữ liệu và giấy phép

Tài liệu này ghi rõ dữ liệu nào lấy từ đâu, dùng giấy phép gì, và cái gì do dự án tự sinh.
Mục đích: người chấm mở repo là biết ngay số liệu có thật hay tự bịa, và dùng lại có hợp lệ không.

## 1. Mạng đường và ma trận khoảng cách

| Hạng mục | Chi tiết |
|---|---|
| Nguồn | OpenStreetMap (OSM) |
| Cách lấy | [OSRM công khai](https://project-osrm.org/) `router.project-osrm.org` — `data/build_matrix.py` gọi endpoint `/table` và `/route` |
| Dữ liệu đã lưu | `data/processed/matrix.json` (thời gian giây + khoảng cách mét cho 16×16 cặp nút), `data/processed/geometry.json` (polyline tuyến đường để vẽ bản đồ) |
| Giấy phép | Dữ liệu OSM: **ODbL 1.0** — khi dùng lại phải ghi công "© OpenStreetMap contributors" |
| Ghi chú | OSRM công khai có giới hạn tần suất; toàn bộ kết quả đã cache trong repo để chạy offline, không gọi lại mạng trừ khi bấm "sinh lại ma trận" |

`data/hubs.json` là 16 điểm do nhóm chọn (cảng Cát Lái, ICD Sóng Thần, chợ đầu mối Bình Điền,
bưu cục các quận…). Toạ độ lấy từ OSM/Nominatim và đã làm tròn 4 chữ số thập phân.

## 2. Dữ liệu huấn luyện ETA

| Hạng mục | Chi tiết |
|---|---|
| Nguồn | NYC TLC *Yellow Taxi Trip Data*, tháng 01/2024, tệp parquet công khai |
| Địa chỉ | `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet` (47,6 MB) |
| Giấy phép | Dữ liệu công khai của thành phố New York, cho phép dùng lại và phân tích |
| Dùng gì | 200.000 chuyến mẫu: giờ đón, thứ, quãng đường, thời lượng chuyến |
| Tự sinh | `ml/build_dataset.py` lọc, tính đặc trưng, chia tập train/test; tệp CSV sinh ra **không commit** (xem `.gitignore`) |
| Không commit | Tệp parquet gốc và CSV sinh ra; chỉ commit `ml/models/eta_metrics.json` để giữ số liệu đánh giá |

**Lưu ý phương pháp:** dữ liệu là taxi New York, không phải TP.HCM. Mô hình học quan hệ
"quãng đường + giờ + thứ → thời lượng", sau đó được hiệu chỉnh hệ số ùn tắc về khung giờ
TP.HCM khi dự đoán. Đây là giả định mô phỏng, không phải mô hình giao thông thực của TP.HCM —
xem phần "Hạn chế" trong README.

## 3. Đơn hàng và đội xe

- Đơn hàng **sinh bằng seed** (`backend/dispatch/scenario.py`): mã đơn, cửa hàng, khối lượng,
  thể tích, tiền thu hộ, khung giờ cam kết. Cùng seed → cùng lô đơn, tái lập được 100%.
- Đội xe (8 xe mặc định, cấu hình 2–8 xe) và tài xế là dữ liệu mô phỏng, không phải người thật.
- Toạ độ điểm giao lấy từ các nút có thật ở TP.HCM, không phát sinh toạ độ ngẫu nhiên ngoài
  bán kính cho phép.

## 4. Hình ảnh thương hiệu

`web/assets/banner.jpg` và `web/assets/avatar.jpg` do nhóm tự tạo cho đồ án, dùng trong giao diện.
Không dùng logo hay nhân vật có bản quyền của bên thứ ba.

## 5. Giấy phép mã nguồn

Mã nguồn phát hành theo giấy phép **MIT** (xem `LICENSE`). Riêng dữ liệu OSM vẫn theo ODbL,
không bị giấy phép MIT của mã nguồn thay thế.
