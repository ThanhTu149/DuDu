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

## 10. Bản v4 — bảng đơn, dòng thời gian, in phiếu

| Thêm | Chi tiết |
|---|---|
| **Danh sách đơn** | Nút "Danh sách đơn" ở rail trái mở drawer rộng 780px: 48 đơn, sắp xếp bằng cách bấm tiêu đề cột, lọc theo trạng thái và quận, tìm theo mã/cửa hàng. Bấm một dòng mở chi tiết đơn (có nút quay lại danh sách) |
| **Dòng thời gian** | Tab thứ hai ở panel dưới: mỗi tài xế một hàng, trục 08:00–12:00, mỗi điểm giao là một khối màu theo tuyến, khối đỏ là đơn trễ. Rê chuột xem mã đơn + giờ |
| **In phiếu giao** | Nút "In" dựng vùng in riêng (`#print-area`) rồi gọi `window.print()`: mỗi tuyến một bảng, có cột ký nhận, ngắt trang giữa các tuyến |
| **Khung xương khi tính** | Danh sách tuyến thay bằng 4 thẻ skeleton nhấp nháy, bản đồ phủ lớp "Đang lập kế hoạch…", tôn trọng `prefers-reduced-motion` |
| **Design tokens** | `docs/design-system/tokens.json` theo định dạng W3C DTCG — import thẳng vào Figma bằng plugin Tokens Studio |

Cách dùng token cho Figma: cài plugin **Tokens Studio for Figma** → Import → chọn
`docs/design-system/tokens.json`. Toàn bộ màu, cỡ chữ, khoảng cách, bán kính, breakpoint và
kích thước panel sẽ thành biến trong Figma, dựng lại giao diện chỉ là kéo component.

Trạng thái tab được nhớ trong phiên: mở "Dòng thời gian" thì panel dưới cao lên 306px và tự mở
rộng nếu đang ở chế độ gọn.

Ảnh: `giao-dien-don-hang.png`, `giao-dien-gantt.png`, `giao-dien-in.png`.

### Đưa bộ thiết kế vào Figma

**Lưu ý:** File → Import của Figma chỉ nhận `.fig`, `.sketch`, ảnh — **không nhận JSON**.
Đưa `tokens.json` vào bằng cách đó sẽ báo "Unsupported file format". Có hai đường đúng:

**Đường 1 — plugin Tokens Studio (khuyến nghị, có biến thật)**

1. Figma → menu chính → **Plugins → Manage plugins** → tìm "Tokens Studio for Figma" → Run.
2. Trong plugin: **Import** → chọn `docs/design-system/tokens.studio.json`
   (bản này dùng định dạng Tokens Studio: `value`/`type`; bản `tokens.json` là DTCG cho công cụ khác).
3. Bấm **Create styles/variables** để đẩy thành Figma Variables, rồi dùng trực tiếp trong mọi frame.

**Đường 2 — kéo SVG (không cần plugin, có ngay bản xem)**

1. Mở `docs/design-system/style-sheet.svg`.
2. Kéo tệp vào canvas Figma (hoặc Ctrl+Shift+K, chọn tệp).
3. Figma đọc SVG thành **layer vector**: mỗi ô màu, mỗi dòng chữ sửa được; bung nhóm để lấy
   từng swatch, từng mẫu chữ, từng component (nút, chip biển số, nhãn mức, thẻ KPI).

Ảnh xem trước: `docs/design-system/style-sheet.png`.

## 11. Bản v5 — sửa theo phản biện UX/UI

Đợt rà soát thứ ba chỉ ra các điểm sau; bảng ghi nguyên nhân và cách xử lý.

| Vấn đề | Cách xử lý |
|---|---|
| Khung tuyến bị bóp, chỉ lộ một dòng | Đưa 4 KPI ra **dải ngang** dưới header; cột phải giờ chỉ còn danh sách tuyến, thẻ gọn hơn (3 dòng thay vì 4) nên thấy 4 tuyến cùng lúc |
| Lệch số vi phạm giữa KPI / dải sự cố / bảng luật | Một nguồn duy nhất: KPI ghi `0 chặn · 3 cảnh báo`, dải sự cố ghi `3 vi phạm · 0 chặn · 3 cảnh báo`, bảng luật cũng cùng chuỗi; tab lọc có số đếm |
| Rớt chữ ở dải 160→187 km, nhãn HÀNH ĐỘNG xuống dòng | Delta pill đổi thành 2 tầng: số lớn `187 km` + pill `+27 km`, khoá `white-space: nowrap`; nhãn bước đổi sang pill màu cố định, không wrap |
| Header lặp `48 đơn · 8 xe · seed 7` | Bỏ khỏi header; Seed/Đơn/ETA gom vào popover **Cấu hình giả lập ▾**, dòng meta chuyển vào cuối popover |
| Nút sự cố không cho biết đang bật | Nút đang chạy chuyển nền đỏ nhạt + viền đỏ + chấm nhấp nháy; thêm nút `↺` hoàn tác trong dải so sánh |
| Chú thích bản đồ nói "điểm giao màu cam" nhưng chấm nhiều màu | Chú thích sửa thành "màu theo tuyến"; điểm trễ có viền đỏ + vòng pulse; điểm giao có vùng bấm 9px |
| Không thấy số thứ tự / hướng tuyến khi chọn | Chọn tuyến: tuyến khác mờ 0.1, tuyến đang chọn hiện số thứ tự 1→2→3 và mũi tên hướng |
| Bấm điểm giao phải dò bảng khác | **Thẻ nổi trên bản đồ**: cửa hàng, mã đơn, hạn giao, giờ tới, thu hộ, hàng, kèm nút "Chi tiết" |
| Nhãn địa điểm bị đường kẻ đè | `paint-order: stroke` + viền `--paper-2` 3px cho nhãn quận và tên nút |
| Nhật ký là danh sách phẳng | Đổi thành **timeline dọc**: đường kẻ, chấm màu theo bước, pill màu (xanh dương nhận biết, cam hành động, xanh lá kiểm tra), **thời gian thật** `+14 ms` đo trong tác tử |
| Bảng luật chỉ để đọc | Thêm lọc `Tất cả (6) / Chặn (3) / Cảnh báo (3)`; bấm một vi phạm thì bản đồ **zoom vào đúng điểm** và mở chi tiết đơn |
| Số liệu không thẳng cột | Toàn bộ số dùng `font-variant-numeric: tabular-nums` (font mono sẵn có) |
| Rail không có nhãn | Thêm tooltip khi rê chuột (`data-label`), vẫn giữ `aria-label` cho trình đọc màn hình |
| Bản đồ bị hộp thư | `fitView()` tính `viewBox` theo tỉ lệ khung chứa (đã làm ở v4) |

Ghi chú kỹ thuật: `pointerdown` không còn `setPointerCapture` ngay — chỉ giữ chuột khi đã kéo quá 6px,
nếu không thì cú click bị chuyển sang thẻ `<svg>` và thẻ nổi không bao giờ mở.

Ảnh: `giao-dien-dieu-phoi.png`, `giao-dien-cau-hinh.png`, `giao-dien-the-noi.png`, `giao-dien-su-co.png`.

## 12. Bản v6 — sửa 6 tiểu tiết, 4 lỗi và 2 điểm nhấn

| Góp ý | Cách xử lý |
|---|---|
| Bản đồ co cụm giữa khoảng trắng | Lưới nền đổi từ 10×8 đường cố định sang **pattern phủ toàn khung nhìn**, nên khi zoom/kéo không còn mảng trắng; mức fit mặc định tăng 1,08× và nhãn luôn hiển thị `1,0×` |
| Bảng đơn cắt đuôi biển số, có thanh cuộn ngang | Drawer rộng 880px, cỡ chữ bảng 11px, padding hẹp lại → `scrollWidth = clientWidth`, không phải kéo ngang; cột trạng thái bọc badge xanh/đỏ/xám |
| Hai dòng R04 trùng nhau | Dòng mô tả phụ thêm **mã đơn · cửa hàng**, nên hai đơn khác nhau hiện rõ khác nhau |
| Cột `đầu → còn` một màu | Thêm 3 mức màu: `0 → 0` xám nhạt, `x → 0` xanh lá (tác tử dọn sạch), `x → x` vàng cam; mã luật sắp tăng dần trong mỗi nhóm (R01, R02, R03, R08, R12) |
| Thuật ngữ lẫn `hungarian` / `Hungary` | Thống nhất "Hungarian" ở cả nhật ký và bảng so sánh; bảng so sánh thêm pill **Đang dùng** và tô đỏ ô số xấu (trễ, quá tải) |
| Scrollbar dày, footer lặp số liệu | Scrollbar mảnh 6px; bỏ hẳn cụm `48 điểm giao · 446,5 phút` ở chân bản đồ (đã có ở dải KPI) |
| **Lỗi** lệch delta (160→176 nhưng +15) | Tính chênh lệch trên số **đã làm tròn** hiển thị: 176 − 160 = 16 |
| **Lỗi** số phút ở đáy bản đồ không cập nhật | Xoá cụm đó; số phút chỉ còn ở `kpi-note` và luôn lấy từ metrics mới |
| **Lỗi** danh sách tuyến bị ép khi bật sự cố | Dải so sánh rời khỏi cột phải, thành **băng ngang full-width** dưới dải KPI, cột tài xế giữ nguyên chiều cao |
| **Lỗi** icon rail kẹt sau khi đóng modal | `closeModal()` trả trạng thái active về mục Điều phối (Esc, nút ×, bấm nền đều đi qua hàm này) |
| Nhãn `12:00` bị cắt | Bề rộng chart trừ 46px và nhãn cuối neo `text-anchor="end"` |
| Chưa thấy sự cố nằm ở đâu | **Marker đỏ nhấp nháy + nhãn** `XE HỎNG` / `KHO ĐÓNG` / `KẸT XE` đặt đúng toạ độ, vẽ lại theo kế hoạch mới |
| Highlight Gantt chưa đồng bộ | Hàng của tuyến đang chọn được tô nền cam nhạt, khớp với thẻ tuyến bên phải |

Phát hiện thêm khi làm: bộ phím tắt (`/`, `F`, `0`, `+`, `-`, `Esc`) trước đó **chưa từng hoạt động** vì
handler cũ bị ghi đè — nay đã chạy đúng và `Esc` cũng đóng drawer/modal đúng thứ tự.

## 13. Bản v7 — nhận diện thương hiệu và 6 điểm còn lại

### Hình ảnh thương hiệu

- `web/assets/banner.jpg` (1024×572) — banner giới thiệu, nền kem khớp `#faf5e8`, ba trụ cột in trên ảnh.
- `web/assets/avatar.jpg` (1086×1086) — chân dung điều phối viên, dùng làm mascot và favicon.

Ba vị trí đặt ảnh, không chỗ nào đè lên bản đồ hay số liệu:

| Vị trí | Chi tiết |
|---|---|
| Logo rail trái | Thay ô chữ "D" bằng avatar bo góc 10px; hover phóng 1,05 và viền cam; tooltip "DuDu — Giới thiệu hệ thống"; favicon đổi theo |
| Modal giới thiệu | Tự mở lần đầu (cờ `localStorage.dudu_intro_seen`), hoặc mở lại bằng avatar / chữ DuDu trên header; banner hiển thị trọn 16:9 (không cắt chữ) trên nền kem, 3 thẻ mô tả ba bài toán, CTA "Bắt đầu điều phối →", checkbox "Không tự hiện lại"; đóng bằng CTA, ×, Esc, bấm nền |
| Toast trạng thái | Giữ nguyên, không chèn ảnh để tránh rối |

### Sáu điểm còn lại

| Góp ý | Cách xử lý | Kiểm chứng |
|---|---|---|
| Dải sự cố 2 tầng, ép lùn bản đồ | Nén thành **một dòng 48px**: `Sự cố Xe hỏng │ Quãng đường 187 km (+27) │ Đơn trễ 2 (+1) │ Vi phạm chặn 3 (+3) │ ↺ Hoàn tác` | Đo được `height = 48` ở 1366 và 1920 |
| Tràn lề phải ở "Kho đóng" | Nút hoàn tác đổi sang `inline-flex` rộng 92px, không wrap; dòng `… phút xe chạy` cắt ellipsis thay vì đẩy khung | `scrollWidth = 1366/1920 = viewport`, nút ↺ kết thúc ở 1352/1902 |
| Bản đồ còn thừa khoảng trắng | Zoom mặc định 1,08× → **1,22×**, lưới nền phủ toàn khung | Nhãn `zoom 1,0×` (mức fit mới) |
| Icon rail kẹt khi đóng drawer/modal | `closeDrawer()` và `closeModal()` đều trả active về Điều phối | Esc sau khi mở bảng so sánh → `dispatch` |
| So sánh chiến lược thiếu nhãn, lệch tên | Đổi "Hungary — bài toán gán" → **Hungarian**; thêm pill **Đang dùng** cho cả dòng chia đơn và dòng xếp tuyến | 2 pill, đúng hai dòng đang chạy |
| R06 gắn mã đơn lẻ | Luật cấp tài xế (R06, R10) hiển thị **biển số · loại xe** thay vì mã đơn | "51G-160.82 · Xe tải nhỏ 500kg" |
| Câu chữ Kẹt xe tự mâu thuẫn | Đổi thành "…tăng 40%; tác tử sẽ tính lại tuyến nên quãng đường có thể thay đổi" | Đọc lại từ API |

Ảnh: `giao-dien-gioi-thieu.png`, `giao-dien-dieu-phoi-1366.png`, `giao-dien-su-co.png`.

## 14. Bản v8 — tương phản, phân vai font, nhãn bản đồ

Lý do: khi chiếu máy chiếu, chữ phụ xám nhạt bị bạc; badge tiếng Việt dùng mono làm dấu mũ bị bí.

| Hạng mục | Trước | Sau |
|---|---|---|
| Chữ chính | `#15171c` | `#1c1917` (ấm hơn, không gắt) |
| Chữ phụ / nhãn KPI | `#858b94` | `#57534e` (đo được `rgb(87,83,78)`) |
| Chữ mờ còn lại | `#858b94` | `#6b6560` |
| Badge tiếng Việt (NHẬN BIẾT, CHẶN, CẢNH BÁO) | mono | **sans** — chỉ số/mã/giờ giữ mono |
| Nhãn nút & quận trên bản đồ | 8,5–10px | **11px**, màu `#3f3f46`, halo 2,5px |
| Dòng bảng đơn | 11px / padding 6px | **13px / padding 10px** (dòng cao 40px) |
| Dải KPI | số và đơn vị rời nhau | chân chữ thẳng, đơn vị 12,5px màu đậm; `97,9%` không còn hở |
| Viền bản đồ | nhãn sát mép khi zoom 1,22× | padding trên/dưới 74 đơn vị + zoom 1,12× → nhãn cách viền 14–15px |

Bốn tiểu tiết còn lại:

- Luật mức chặn còn sót sau sự cố tô **đỏ** (`.num.bad`), không còn vàng như cảnh báo.
- Khi đang mô phỏng sự cố, cột số của bảng luật đổi nhãn thành **“Sau sự cố”** và chỉ hiện một số, thay vì `0 → 4` gây hiểu nhầm.
- Nhật ký sự cố dùng câu đúng ngữ cảnh: xe hỏng → “8 xe còn lại nhận 48 đơn”; kẹt xe/kho đóng → “Phân bổ lại 48 đơn cho 8 xe”.
- Badge “2 trễ” trên thẻ tài xế chuyển thành **pill nền đỏ nhạt**, đồng bộ với “3 chặn”; chữ `NHÓM 14` ở rail được nâng lên và sáng hơn; avatar bo 12px kèm viền kem mờ.

Token trong `docs/design-system/` đã cập nhật theo bảng màu mới.

## 15. Bản v9 — Biệt đội DuDu luôn hiện diện

Banner trước đây chỉ sống trong modal chào mừng; giờ nó thành một phần của bảng điều phối.

### Thẻ nổi “Biệt đội Tác tử DuDu”

- Neo trong `.map-wrap` ở góc dưới-trái (`left: 14px; bottom: 40px`), rộng **222px**, cao 184px.
- Ảnh banner 16:9 trong khung 16:10, `object-fit: cover` + `transform: scale(1.62)` với gốc `96% 58%`
  để **khoanh đúng cụm nhân vật**: DuDu đeo tai nghe, Gấu Nâu, Gấu Trúc, Gấu Trắng — không dính chữ “DuDu” bên trái.
- Nền thẻ `rgba(250,245,232,.95)` + `backdrop-filter: blur(6px)`, viền `#e5dccb`, bo 12px, khớp ngôn ngữ thiết kế.
- Dòng trạng thái sống, cập nhật theo state thật:

| Tình huống | Câu hiển thị |
|---|---|
| Vừa lập kế hoạch | “Biệt đội đã tối ưu **48 đơn** · Đúng giờ 97,9%” |
| Đang xử lý sự cố | “Xe hỏng rồi! Tác tử đang chia lại tuyến…” |
| Xe hỏng xong | “Đã gánh lại **48 đơn** cho các xe còn lại!” |
| Kẹt xe xong | “Kẹt xe diện rộng — đã tính lại ETA & tuyến mới · **2 trễ**” |
| Kho đóng xong | “Kho đóng — đã điều xe sang kho khác và lập lại tuyến!” |

- Bấm ảnh → mở modal giới thiệu; nút `–` thu gọn thành pill `[avatar] Biệt đội DuDu ↗`; bấm pill bung lại.
- Tự thu gọn khi khung bản đồ hẹp hơn **820px** (đo ở 800×700: `mapW = 762` → pill hiện, thẻ ẩn).

### Hai điểm chạm khác

- **Rail trái** có thêm mục “Giới thiệu DuDu” (icon bóng đèn) mở lại modal bất cứ lúc nào; avatar và chữ DuDu trên header vẫn mở được. `localStorage` chỉ quyết định việc **tự bật lần đầu**, không khoá việc mở tay.
- **Nhật ký tác tử** có avatar 20px kèm chấm xanh online trước tiêu đề; **toast** có avatar 22px ở đầu câu.

### Lỗi bố cục phát hiện thêm

Ở màn hình ≤900px, `.app` khai báo `grid-template-columns: 0 1fr` và ẩn rail, nên `.shell` rơi vào cột 0px → toàn bộ nội dung co về 0, nút “Lập kế hoạch” bị KPI đè lên. Đã sửa thành `1fr`, đồng thời đặt lại lưới `.shell` 4 hàng ở cuối tệp CSS để thắng các rule cũ.

Ảnh: `giao-dien-dieu-phoi.png`, `giao-dien-su-co.png`, `giao-dien-gioi-thieu.png`.

## 16. Bản v10 — ba tiểu tiết cuối

| Góp ý | Cách sửa |
|---|---|
| Ảnh thẻ nổi cắt mất đầu Gấu Nâu và chỏm tóc DuDu | Đổi khung sang `16 / 9.6`, `object-position` và gốc phóng về **`100% 34%`**, scale **1,66** — lộ trọn đầu Gấu Nâu, tóc DuDu, Gấu Trúc và Gấu Trắng; đẩy hẳn chữ “DuDu” của banner ra ngoài khung |
| Câu trạng thái rớt dòng `97,9%` | Rút còn **“48 đơn tối ưu · Đúng giờ 97,9%”**, cỡ 10,5px, `nowrap` + ellipsis (đo: `scrollWidth = clientWidth = 220`) |
| Banner trong modal lộ hai dải trắng hai bên | Modal hẹp còn **740px**, ảnh `width: 100%`, bỏ `object-fit: contain`, bo góc trên; nút × tròn mờ tối nổi trên ảnh |
| Tooltip mặc định của trình duyệt ở bảng luật | Bỏ `title`, thay bằng mũi tên `↗` màu cam hiện dần khi hover, ngăn bằng `aria-label` |
| Chữ dọc “NHÓM 14” | Đổi thành **“DuDu”** |
