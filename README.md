# DuDu — Trung tâm điều phối giao hàng nội thành

Bài tập lớn học phần **Trí tuệ nhân tạo (121033)** — Trường Đại học Giao thông Vận tải TP.HCM.

DuDu là một bảng điều phối (dispatch console) cho bài toán giao hàng chặng cuối ở TP.HCM:
nhận đơn → dự đoán thời gian giao (ETA) → chia đơn cho tài xế → xếp tuyến → kiểm tra
ràng buộc vận hành và giải trình lại quyết định.

Đề tài phát triển từ các gợi ý **31 (tối ưu tuyến đường), 32 (dự đoán ETA), 33 (phân bổ
đơn hàng)** trong danh sách đề tài của học phần.

## Bốn học phần kiến thức được dùng

| Chương | Nội dung | Nằm ở đâu trong dự án |
|---|---|---|
| 1. Tác tử | Tác tử dựa trên mục tiêu/tiện ích, tác tử phản ứng | `backend/dispatch/agent.py` |
| 2. Tìm kiếm | A\*, VRP, heuristic Nearest Neighbor / 2-opt | `backend/dispatch/routing.py` |
| 3. Logic – suy diễn | Cơ sở luật IF–THEN, giải trình chuỗi suy diễn | `backend/dispatch/rules.py` |
| 4. Máy học | Hồi quy tuyến tính, Random Forest dự đoán ETA | `ml/` |

## Cấu trúc thư mục

```
DuDu/
├── data/        dữ liệu điểm giao, ma trận khoảng cách thật (OSRM), dữ liệu huấn luyện
├── backend/     API (FastAPI) + 4 module thuật toán
├── ml/          huấn luyện và đánh giá mô hình ETA
├── web/         giao diện điều phối
└── docs/        kế hoạch, kiến trúc, thiết kế, báo cáo
```

## Chạy thử

```powershell
# 1. Cài phụ thuộc
pip install -r requirements.txt

# 2. Sinh ma trận khoảng cách (gọi OSRM, lưu cache vào data/processed/)
python data/build_matrix.py

# 3. Huấn luyện mô hình ETA
python ml/train_eta.py

# 4. Chạy server
python -m uvicorn backend.app:app --reload --port 8000
# mở http://127.0.0.1:8000
```

## Dữ liệu

- **Mạng đường TP.HCM**: OpenStreetMap qua OSRM công khai (`router.project-osrm.org`).
  Khoảng cách và thời gian di chuyển là số thật, không phải tự bịa.
- **Điểm giao**: 16 nút thật (cảng Cát Lái, ICD Sóng Thần, chợ đầu mối Bình Điền,
  các bưu cục quận…) + đơn hàng sinh theo seed để tái lập được kết quả.
- **ETA**: xem `ml/README.md` — dữ liệu hành trình thật, có hiệu chỉnh về bối cảnh TP.HCM.

## Ghi chú

Repo dùng commit theo từng bước công việc nhỏ, chia theo mảng để lịch sử đọc được như nhật
ký làm việc. Xem `docs/PLAN.md` để biết tiến độ.

Sinh viên thực hiện: Lê Thanh Tú — 049206004778 — Nhóm 14.

## Tài liệu

| Tệp | Nội dung |
|---|---|
| `docs/PLAN.md` | Kế hoạch, phạm vi, phân công, rủi ro |
| `docs/TASKS.md` | Bảng việc kỹ thuật và tiến độ |
| `docs/ARCHITECTURE.md` | Kiến trúc, ranh giới module, danh sách API |
| `docs/DESIGN.md` | Hệ thống thiết kế giao diện (màu, chữ, bố cục, component) |
| `docs/ket-qua-vrp.md` | Kết quả thí nghiệm xếp tuyến theo quy mô |
| `docs/ket-qua-eta.md` | Kết quả mô hình dự đoán thời gian giao |
| `docs/ket-qua-luat.md` | Thống kê kích hoạt 12 luật trên ba kịch bản |

Các tệp kết quả đều sinh tự động bằng lệnh trong mã nguồn, chạy lại thực nghiệm là số liệu
tự khớp.

