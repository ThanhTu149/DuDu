# Thiết kế giao diện DuDu

Mục tiêu thị giác: **bảng điều phối của người làm vận hành**, không phải landing page.
Người dùng là điều phối viên nhìn màn hình 8 tiếng/ngày, nên ưu tiên mật độ thông tin,
số liệu thẳng cột, ít màu, không hiệu ứng.

Tham chiếu: bảng điều khiển của Grab Merchant, Bee Delivery (bản web cho merchant),
Linear, và các ops console của hãng vận tải. Điểm chung: nền sáng, chữ đậm, một màu nhấn.

## 1. Bảng màu

| Vai trò | Mã | Dùng ở đâu |
|---|---|---|
| `paper` | `#f5f2ec` | nền toàn màn hình (giấy ấm, không trắng tinh) |
| `paper-2` | `#faf8f4` | mặt phẳng của panel/phiếu |
| `ink` | `#15171c` | chữ chính, rail trái, marker kho |
| `ink-2` | `#4d535c` | chữ phụ, nhãn |
| `ink-3` | `#858b94` | chú thích, số thứ tự |
| `line` | `#ddd7cb` | viền 1px của panel |
| `accent` | `#c9490e` | nút chính, tuyến đang chọn, nhãn "chặn" |
| `teal` | `#2c6b52` | trạng thái tốt, thanh tải trong định mức |
| `alert` | `#b3261e` | đơn trễ, vượt tải |
| `amber` | `#d99a06` | cảnh báo mềm |

Quy tắc: một màn hình chỉ có **một** màu nhấn nóng (accent). Không dùng gradient, không
bóng đổ ngoài 1 lớp mờ rất nhẹ cho modal. Không dùng emoji.

## 2. Chữ

- Bộ chữ: `Be Vietnam Pro` → dự phòng `Segoe UI` (Windows), `system-ui`.
  Chọn Be Vietnam Pro vì dấu tiếng Việt đẹp ở cỡ nhỏ; nếu chưa cài thì Segoe UI vẫn ổn.
- Số liệu: font mono có `font-variant-numeric: tabular-nums` để cột số không nhảy.
- Thang cỡ: 10 / 11 / 12.5 / 14 / 17 / 20 (px).
- Nhãn mục: 11–12px, in hoa, giãn chữ `.12em`.

## 3. Khoảng cách và hình khối

- Đơn vị 8px; panel cách nhau 14px; padding trong panel 12–16px.
- Bán kính: panel 10px, nút 8px, nhãn 4–6px.
- Viền 1px `line`; panel không đổ bóng.

## 4. Bố cục

```
┌────┬───────────────────────────────────────────────────────────────┐
│    │ topbar: thương hiệu · ca · seed/đơn · [Lập kế hoạch]           │
│rail├──────────────────────────────────┬────────────────────────────┤
│ 64 │ bản đồ (SVG, tỷ lệ 1000×640)      │ 4 KPI · danh sách tuyến    │
│ px │                                  │ · 2 nút hành động          │
│    ├──────────────────────────────────┴────────────────────────────┤
│    │ nhật ký tác tử (trái) │ đối chiếu cơ sở luật (phải)            │
└────┴───────────────────────────────────────────────────────────────┘
```

## 5. Thành phần

| Thành phần | Trạng thái cần có |
|---|---|
| Nút chính | thường / hover / đang tính (disabled + chữ "Đang tính…") |
| Thẻ tuyến | thường / hover / đang chọn / quá tải (thanh đỏ) |
| KPI | có số / chưa chạy (`—`) |
| Bảng so sánh | dòng tốt nhất tô nền `#fdf3ec` |
| Nhật ký tác tử | 4 nhãn: nhận biết / quyết định / hành động / kiểm tra |
| Vi phạm | 3 mức: chặn (đỏ) / cảnh báo (vàng) / ưu tiên (xanh) |

## 6. Bản đồ

- Chiếu equirectangular: kinh độ → x, vĩ độ → y, đệm 52px.
- Lưới 8×10 màu `#e5dfd3` để mắt bám được khoảng cách.
- Nút kho/cảng: ô vuông đen 8px. Bưu cục: vòng tròn trắng viền xám.
- Tuyến: đường thật lấy từ OSRM, rộng 3px, màu theo tài xế; tuyến đang chọn rộng 4.5px,
  các tuyến khác mờ còn 18%.
- Điểm giao: chấm 2.8px (trễ: 4px, đỏ). Rê chuột hiện mã đơn + giờ tới.

## 7. Figma — các bước dựng

Dùng file Figma (Pro Education) để làm **bộ thư viện** trình bày trong báo cáo, không phải
để thay giao diện web:

1. Tạo file `DuDu — Design System`, 3 trang: `Tokens`, `Components`, `Screens`.
2. Trang `Tokens`: tạo Color Styles đúng 9 màu ở mục 1; Text Styles đúng 6 cỡ ở mục 2;
   hiệu ứng 8px.
3. Trang `Components`: dựng 6 component (Nút, Thẻ tuyến, KPI, Nhãn mức độ, Bảng so sánh,
   Thanh tải) với biến thể `State = default / hover / active / disabled`.
4. Trang `Screens`: 3 frame 1600×950 — `Điều phối`, `So sánh chiến lược`, `Sau sự cố`.
   Chụp lại giao diện thật rồi dựng lại bằng component để hai bên khớp nhau.
5. Export PNG 2× cho báo cáo; chèn vào phụ lục "Thiết kế giao diện".

Việc dựng Figma **không chặn** tiến độ code: giao diện chạy được trước, Figma là bản
trình bày lại. Đừng dành quá 1 buổi cho phần này.

## 8. Bản v2 — sửa sau khi tự phản biện

Đợt rà soát thứ hai (đứng ở góc giảng viên) tìm ra các lỗ hổng dưới đây và đã sửa:

| Lỗ hổng | Cách sửa |
|---|---|
| Bấm vào điểm giao không có gì xảy ra | **Drawer chi tiết đơn**: mã đơn, cửa hàng, địa chỉ, hàng hoá, thu hộ, hạn giao, giờ tới, tài xế, thứ tự điểm, và các luật đã kích hoạt trên đơn đó |
| Không thấy chiều thời gian | **Drawer tuyến**: lịch giao theo giờ, mỗi điểm một dòng, đánh dấu trễ bằng số phút, đúng hạn bằng ✓ |
| Bản đồ thiếu bối cảnh | Thêm vùng đô thị (bao lồi), nhãn quận, mũi tên hướng tuyến, thước tỉ lệ km |
| Số liệu sai định dạng Việt | Đổi toàn bộ sang `toLocaleString('vi-VN')`: `446,5 phút`, `97,9%`, `1.000đ` |
| Không phản hồi khi bấm | Nút có trạng thái đang tính (spinner), **toast** báo xong/lỗi, nút CSV bật khi có kế hoạch |
| Không xuất được kế hoạch | Nút **CSV** xuất phiếu giao: tài xế, biển số, thứ tự, mã đơn, địa chỉ, giờ tới, trạng thái |
| Không tìm được đơn | Ô tìm kiếm theo mã đơn / cửa hàng / địa chỉ / quận, tô sáng điểm khớp và hiện `n/48` |
| Chỉ đẹp ở 1600px | Breakpoint 1460 / 1240 / 900: topbar gọn lại, bảng KPI 4 cột, bố cục xếp dọc và cuộn được |
| Rail toàn nút trang trí | Ba nút giờ đều có việc: điều phối (đóng drawer), cơ sở tri thức, so sánh chiến lược; có `aria-label` |

Bổ sung về khả năng truy cập: `:focus-visible` cho mọi phần tử tương tác, thẻ tuyến có
`role="button"` + `tabindex` + Enter/Space, `aria-live` cho toast, tôn trọng
`prefers-reduced-motion` (tắt spinner quay).

Bảng breakpoint:

| Bề rộng | Bố cục |
|---|---|
| > 1460 | đầy đủ: thương hiệu, ca trực, seed/đơn/ETA |
| 1240–1460 | ẩn phụ đề và giờ ca, giữ `48 đơn · 8 xe · seed 7` |
| 900–1240 | một cột: bản đồ trên, KPI + tuyến dưới, nhật ký cuối trang, cuộn dọc |
| < 900 | ẩn rail, topbar xuống dòng |

Ảnh cập nhật: `docs/hinh/giao-dien-dieu-phoi.png`, `giao-dien-tuyen.png`, `giao-dien-don.png`,
`giao-dien-luat.png`, `giao-dien-so-sanh.png`, `giao-dien-su-co.png`.

## 9. Bản v3 — bản đồ tương tác và chế độ xem gọn

Vấn đề của v2: bản đồ bị "hộp thư" (letterbox) trên màn hình rộng — với cửa sổ 1885×847,
khung SVG 1000×640 chỉ dùng được phần giữa, hai bên trống. Không phóng được, không kéo được.

Đã sửa:

| Thay đổi | Chi tiết |
|---|---|
| **Vừa khung theo tỉ lệ cửa sổ** | `fitView()` tính `viewBox` theo đúng tỉ lệ khung chứa và bao trọn 16 nút + lề, nên bản đồ luôn lấp đầy bề ngang |
| **Phóng / thu** | Nút +, −, lăn chuột (zoom tại vị trí con trỏ), phím `+`/`-`; nhãn `zoom 1,0×` góc dưới phải |
| **Kéo bản đồ** | Giữ chuột trái và kéo; kéo quá 6px thì bỏ qua cú click để không mở nhầm drawer |
| **Toàn màn hình** | Nút ⛶ hoặc phím `F` (Fullscreen API), thoát bằng `Esc` |
| **Thu gọn nhật ký** | Nút "Thu gọn" ở panel dưới: bản đồ được thêm ~190px chiều cao; trạng thái nhớ trong `localStorage` |
| **Hoàn tác sự cố** | Nút "↺ Kế hoạch gốc" trong dải so sánh sau sự cố |
| **Phím tắt** | `/` tìm kiếm · `F` toàn màn hình · `0` vừa khung · `+`/`-` phóng · `Esc` đóng |
| **Trạng thái lỗi** | API không chạy thì hiện màn hình "Không tải được dữ liệu" kèm lệnh chạy lại, không để trang trắng |

Chi tiết kỹ thuật đáng chú ý: các lớp nét (`leg`, `grid-line`, `city-hull`…) đặt
`vector-effect: non-scaling-stroke` để khi phóng to nét không dày lên; `touch-action: none`
trên khung bản đồ để kéo không bị trình duyệt cuộn trang.

Ảnh: `docs/hinh/giao-dien-dieu-phoi.png` (vừa khung), `giao-dien-zoom.png` (đã phóng và kéo),
`giao-dien-gon.png` (chế độ gọn), `giao-dien-tuyen.png` (drawer tuyến).
