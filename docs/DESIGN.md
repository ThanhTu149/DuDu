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
