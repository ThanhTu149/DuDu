# Kế hoạch thực hiện — DuDu

**Đề tài:** Hệ thống điều phối giao hàng nội thành TP.HCM (phát triển từ các đề tài 31, 32, 33)
**Học phần:** Trí tuệ nhân tạo — 121033 · UTH

---

## 1. Mục tiêu và phạm vi

Sản phẩm cuối kỳ gồm ba phần:

1. **Phần mềm chạy được**: nhận một lô đơn hàng, tự chia cho đội xe, xếp tuyến, dự đoán
   ETA, kiểm tra ràng buộc vận hành và xuất ra kế hoạch có giải trình.
2. **Báo cáo**: mỗi mảng lý thuyết (tác tử / tìm kiếm / logic / máy học) là một chương,
   có bảng so sánh với baseline và phân tích kết quả.
3. **Thuyết trình + demo trực tiếp** trên giao diện DuDu.

**Phạm vi:** 16 nút mạng lưới thật ở TP.HCM, 40–60 đơn mỗi kịch bản, 8 tài xế.
Không làm thanh toán, không làm app tài xế, không làm bản đồ offline.

**Ngoài phạm vi (ghi rõ để tránh bị hỏi):** tối ưu đa mục tiêu đầy đủ, học tăng cường,
dữ liệu giao thông thời gian thực.

---

## 2. Sáu giai đoạn

| # | Giai đoạn | Nội dung | Tiêu chí nghiệm thu |
|---|---|---|---|
| P0 | Nền móng | Repo, cấu trúc, ma trận OSRM 16×16 | `python data/build_matrix.py` sinh ma trận thật; commit rõ ràng theo từng bước |
| P1 | Máy học | Dataset ETA, hồi quy tuyến tính vs Random Forest | Bảng MAE tách giờ cao điểm / thường + biểu đồ |
| P2 | Tìm kiếm | A\*, Nearest Neighbor, 2-opt, Clarke–Wright | Bảng so sánh các chiến lược trên cùng bộ đơn, % cải thiện |
| P3 | Phân bổ + Logic | Hungary; cơ sở luật 12 luật + giải trình | Log suy diễn từng đơn; số vi phạm mức chặn về 0 |
| P4 | Tác tử + Giao diện | Vòng lặp điều phối, sự kiện động, giao diện | Demo bấm được: nhận đơn → lập kế hoạch → sự cố → lập lại |
| P5 | Hoàn thiện | Viết báo cáo, tập thuyết trình | Chạy thử 10 phút trước hạn 3 ngày |

Chi tiết từng đầu việc nhỏ: xem `docs/TASKS.md`.

---

## 3. Nhóm thực hiện

Nhóm 14 gồm 01 thành viên: Lê Thanh Tú — 049206004778. Toàn bộ các mảng dưới đây do một
người thực hiện, chia theo thứ tự làm để dễ theo dõi tiến độ:

| Thứ tự | Mảng | Sản phẩm |
|---|---|---|
| 1 | Mạng lưới, dữ liệu OSRM | `data/`, `backend/dispatch/network.py` |
| 2 | Chia đơn và xếp tuyến | `backend/dispatch/{assignment,routing}.py` |
| 3 | Cơ sở luật và tác tử | `backend/dispatch/{rules,agent}.py` |
| 4 | Mô hình ETA | `ml/` |
| 5 | Giao diện và API | `web/`, `backend/app.py` |

Commit chia theo từng mảng để lịch sử đọc được như nhật ký làm việc.

---

## 4. Tự soát trước khi nộp (trước hạn 1 tuần)

- [x] Thuật ngữ: rà toàn bộ báo cáo, thống nhất "tác tử", "trạng thái", "hàm heuristic",
      "cơ sở tri thức", "độ đo" — không dùng lẫn "bot/agent/AI model".
- [x] Lập luận: mỗi kỹ thuật phải có (a) vì sao chọn, (b) baseline, (c) số liệu, (d) kết luận.
- [x] Hình thức: font, lề, số trang, đánh số hình/bảng, tài liệu tham khảo.
- [x] Chạy lại `python -m backend.dispatch.evaluate --report` để số liệu trong báo cáo khớp repo.
- [x] Thuyết trình thử 10 phút, bấm giờ, có người phản biện.

---

## 5. Rủi ro và cách chặn

| Rủi ro | Xác suất | Cách chặn |
|---|---|---|
| Dữ liệu ETA không tải được | Trung bình | Có bộ sinh dự phòng theo seed, ghi rõ nguồn |
| Tuần cuối mới ghép module | Cao | API chốt từ P0, mỗi module có endpoint riêng từ đầu |
| Demo lỗi mạng khi bảo vệ | Cao | Ma trận đã cache trong repo; tuyến vẽ được bằng cache |
| Ôm quá nhiều kỹ thuật | Trung bình | Mỗi kỹ thuật có bản tối thiểu; nâng cấp sau khi đủ |

