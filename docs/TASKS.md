# Bảng việc

Theo dõi tiến độ các việc kỹ thuật. Quy ước chung:

- Repo: `DuDu`, chạy bằng Python đã cài `requirements.txt`.
- Kiểm tra nhanh: `python -m backend.dispatch.evaluate`.
- Chạy web: `python -m uvicorn backend.app:app --reload --port 8000`.
- Mỗi việc một nhánh `feat/<mã-việc>`; commit nhỏ, thông điệp mô tả việc đã làm.
- **Không sửa** `data/hubs.json` khi chưa chạy lại `python data/build_matrix.py`.
- Mọi module thuật toán: nhận `Network` + dict thuần, trả dict/dataclass có `as_dict()`.

---

## P1 — Máy học: dự đoán ETA  ✅

- `ml/build_dataset.py` sinh `data/processed/eta_{train,test}.csv` từ dữ liệu chuyến taxi thật.
- `ml/train_eta.py` huấn luyện hồi quy tuyến tính và Random Forest, in MAE/RMSE toàn bộ và
  tách giờ cao điểm, lưu `ml/models/` và `eta_metrics.json`.
- API: `GET /api/eta/info`, `GET /api/eta/predict`.
- Tích hợp: `POST /api/plan` với `{"eta": "ml"}` dùng hệ số ùn tắc theo giờ.

## P2 — Tìm kiếm: mở rộng thí nghiệm VRP  ✅

- `savings` (Clarke–Wright) có ở hai tầng: sắp thứ tự trong tuyến và chia tuyến cấp đội xe.
- `python -m backend.dispatch.evaluate --report` xuất `docs/ket-qua-vrp.md` + hai biểu đồ.
- Kết quả chính: 2-opt giảm 10,4% km ở 144 đơn; C-W kém NN khi chỉ sắp thứ tự.

**Còn lại (không bắt buộc):** biểu đồ tỉ lệ đúng giờ theo quy mô.

## P3 — Logic: cơ sở luật  ✅

- `rules.py` có 12 luật; màn hình "Cơ sở tri thức" hiển thị nhóm theo mức và số lần kích hoạt.
- `python -m backend.dispatch.rule_stats --report` sinh `docs/ket-qua-luat.md`.
- Kết quả: R02 chặn 9 lần → sửa hết; R12 chặn 1 lần → sửa hết; cảnh báo R04 tăng 7 → 10 sau
  khi đổi tuyến (đã giải thích trong tài liệu).

## P4 — Giao diện và tác tử  ✅

- Ba nút sự cố: xe hỏng, kẹt xe, kho đóng; API trả kèm `before` để so sánh trước–sau.
- Dải so sánh hiển thị quãng đường, đơn trễ, vi phạm.

## P5 — Hoàn thiện  🟡

- [x] Viết báo cáo và slide (nộp riêng, không nằm trong repo).
- [ ] Điền tên thành viên vào bảng phân công.
- [ ] Tập thuyết trình có bấm giờ, trước hạn 3 ngày.

---

## Chia việc theo người

| Việc | Người | Nhánh |
|---|---|---|
| P1 ETA | B | `feat/eta-ml` |
| P2 VRP | A | `feat/vrp-savings` |
| P3 luật | C | `feat/rules-12` |
| P4 giao diện | D | `feat/ui-incident` |
| P5 hoàn thiện | cả nhóm | `docs/report` |

Review chéo: người làm P1 review P2, P2 review P3, P3 review P4, P4 review P1.
