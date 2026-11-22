# Nhập đơn hàng từ CSV

Ngoài kịch bản sinh theo seed, DuDu nhận được danh sách đơn thật từ file CSV (tối đa 200
dòng). Dòng sai bị bỏ qua kèm cảnh báo, không làm hỏng cả lần nhập.

## Định dạng

Cột bắt buộc (chấp nhận tiêu đề tiếng Việt có/không dấu và tiếng Anh):

| Cột chuẩn | Bí danh | Ràng buộc |
|---|---|---|
| `diem_giao` | `dest_hub`, `diem_den`, `hub`, `diem` | mã nút (q1, q3, q5, q10, binh-thanh, tan-binh, go-vap, thu-duc, nha-be, q7, hoc-mon, cat-lai, tsn, song-than, binh-dien, tan-phu) hoặc đúng tên nút |
| `khoi_luong_kg` | `weight_kg`, `khoi_luong`, `kg` | 0,1–2000 kg |
| `the_tich_l` | `volume_l`, `the_tich`, `lit` | 0,5–10000 L |

Cột tuỳ chọn:

| Cột | Bí danh | Mặc định |
|---|---|---|
| `ma_don` | `order_id`, `id` | `DD-IMPORT-001`, … |
| `hang_hoa` | `goods`, `loai_hang` | `thuong` (tuoi_song / dien_tu / de_vo / thuong / cong_kenh) |
| `cod` | `thu_ho` | 0 |
| `uu_tien` | `priority`, `loai_don` | `tieu_chuan` (hoa_toc / tieu_chuan / tiet_kiem) |
| `hen_giao_phut` | `promised_min`, `sla_phut` | theo ưu tiên: hoả tốc 90, tiêu chuẩn 240, tiết kiệm 480 |
| `dich_vu_phut` | `service_min`, `phut_phuc_vu` | 5 phút (1–60) |
| `dia_chi` | `address` | sinh theo nút giao |
| `cua_hang` | `shop` | lấy ngẫu nhiên có seed |
| `dien_thoai` | `phone`, `sdt` | lấy ngẫu nhiên có seed |

File mẫu: `data/samples/don-hang-mau.csv` (12 đơn) hoặc tải qua `GET /api/orders/template`.

## API

| Endpoint | Việc |
|---|---|
| `GET /api/orders/template` | tải CSV mẫu |
| `POST /api/plan/import` | nhận `{csv, seed, vehicles, assignment, routing, eta}`, trả kế hoạch như `/api/plan` kèm `import: {count, warnings}` và `history_id` |
| `GET /api/history?limit=20` | 20 kế hoạch gần nhất (tóm tắt) |
| `GET /api/history/{id}` | khôi phục toàn bộ payload của một kế hoạch |

Ví dụ:

```powershell
$csv = Get-Content data/samples/don-hang-mau.csv -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/plan/import `
  -ContentType 'application/json' -Body (@{ csv = $csv; seed = 7; vehicles = 6 } | ConvertTo-Json)
```

## Trên giao diện

Nút **Nhập CSV** cạnh nút **Lập kế hoạch**: chọn file → gửi nội dung lên server → bản đồ, KPI,
Gantt, nhật ký và bảng luật được vẽ lại theo đúng danh sách đơn vừa nhập. Nếu có dòng bị bỏ
qua, toast hiển thị số dòng bị bỏ và chi tiết nằm trong `import.warnings`.

## Lịch sử kế hoạch

Mỗi lần lập kế hoạch (theo seed, nhập CSV hoặc xử lý sự cố) được lưu tự động vào SQLite
`data/processed/history.sqlite3` (đã gitignore): metadata truy vấn, metrics tóm tắt và toàn bộ
payload. Đổi đường dẫn bằng biến môi trường `DUDU_DB` (test dùng file tạm). Lỗi ghi lịch sử
không làm hỏng lần lập kế hoạch — API vẫn trả kết quả bình thường.

## Duyệt lịch sử trên giao diện

Nút **Lịch sử** cạnh nút **Nhập CSV** mở danh sách 20 kế hoạch gần nhất (kịch bản / nhập CSV /
sự cố). Bấm một dòng để khôi phục: bản đồ, KPI, tuyến theo tài xế, nhật ký, bảng luật và Gantt
được vẽ lại đúng như lúc lập; toast xác nhận số đơn, km, số trễ. Đóng bằng `Esc`, nút ×, hoặc
bấm nền.

`GET /api/history` có phân trang (`limit`, `offset`, trả thêm `total`); `DELETE /api/history/{id}`
xoá một bản ghi. Trên giao diện: nút **×** cạnh mỗi dòng để xoá (có xác nhận) và nút
**Tải thêm** khi còn bản ghi cũ hơn.
