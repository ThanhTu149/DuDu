# DuDu — Trung tâm điều phối giao hàng nội thành

Bài tập lớn học phần **Trí tuệ nhân tạo (121033)** — Trường Đại học Giao thông Vận tải TP.HCM.

DuDu là một bảng điều phối (dispatch console) cho bài toán giao hàng chặng cuối ở TP.HCM:
nhận đơn → dự đoán thời gian giao (ETA) → chia đơn cho tài xế → xếp tuyến → kiểm tra
ràng buộc vận hành và giải trình lại quyết định.

Ngoài dữ liệu sinh theo seed, hệ thống nhận **đơn hàng thật từ CSV** (tối đa 200 dòng, kiểm
tra từng dòng), lưu **lịch sử kế hoạch** vào SQLite và có endpoint khôi phục lại kế hoạch cũ.
Đề tài phát triển từ các gợi ý **31 (tối ưu tuyến đường), 32 (dự đoán ETA), 33 (phân bổ
đơn hàng)** trong danh sách đề tài của học phần.

## Bốn học phần kiến thức được dùng

| Chương | Nội dung | Nằm ở đâu trong dự án |
|---|---|---|
| 1. Tác tử | Tác tử dựa trên mục tiêu/tiện ích, tác tử phản ứng | `backend/dispatch/agent.py` |
| 2. Tìm kiếm | A\* tìm đường vòng khi kẹt xe, VRP, heuristic Nearest Neighbor / 2-opt / Clarke–Wright | `backend/dispatch/network.py`, `routing.py` |
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

## Chạy web

### Cách 1 — bấm đúp `run.bat` (nhanh nhất)

Mở thư mục repo bằng File Explorer → bấm đúp **`run.bat`**. Script tự tìm Python có đủ
`fastapi`/`uvicorn` (theo thứ tự: biến `DUDU_PYTHON` → `.venv` → `python` trên PATH → bản
Python của DeepSeek Harness nếu có), khởi động server và tự mở trình duyệt ở
`http://127.0.0.1:8000`. Nếu cổng 8000 bận vì DuDu đang chạy sẵn, nó chỉ mở trình duyệt;
nếu bận vì app khác, nó tự nhảy sang 8010/8020… Đóng cửa sổ đen là tắt server.

Không cần làm gì thêm: `data/processed/matrix.json` (ma trận OSRM) và `geometry.json` đã
commit sẵn nên web chạy được ngay, kể cả khi không có mạng.

### Cách 2 — chạy tay bằng lệnh

```powershell
# 1. Cài phụ thuộc (một lần). Python 3.11+
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Chạy server, rồi mở http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Máy đã có sẵn Python đủ thư viện (không muốn tạo venv) thì bỏ qua bước 1 và thay
`.venv\Scripts\python.exe` bằng `python`.

### Docker (tuỳ chọn)

```powershell
docker build -t dudu .
docker run --rm -p 8000:8000 dudu
# mở http://127.0.0.1:8000
```

Ảnh Docker dựa trên `python:3.11-slim`, có `HEALTHCHECK` gọi `/api/health`. Mô hình ETA và
dữ liệu thô không nằm trong ảnh — thiếu mô hình thì web vẫn chạy bằng OSRM free-flow.

### Mô hình ETA (tuỳ chọn)

Tệp `ml/models/eta_rf.joblib` (~105 MB) **không commit** vì nặng. Nếu thiếu, web vẫn chạy
bình thường: nút "ETA mô hình" dùng OSRM free-flow và API trả `warnings`. Muốn bật mô hình
thật:

```powershell
# tải parquet NYC TLC (~48 MB) vào data/raw/ rồi:
python ml/build_dataset.py --force
python ml/train_eta.py
```

### Chạy lại dữ liệu/kết quả (tuỳ chọn)

```powershell
python data/build_matrix.py            # gọi OSRM sinh lại ma trận (cần mạng)
python -m backend.dispatch.evaluate --report   # sinh bảng kết quả VRP
python -m unittest discover -s tests -v        # 74 ca kiểm thử
```

## Dữ liệu

- **Mạng đường TP.HCM**: OpenStreetMap qua OSRM công khai (`router.project-osrm.org`).
  Khoảng cách và thời gian di chuyển là số thật, không phải tự bịa.
- **Điểm giao**: 16 nút thật (cảng Cát Lái, ICD Sóng Thần, chợ đầu mối Bình Điền,
  các bưu cục quận…) + đơn hàng sinh theo seed để tái lập được kết quả.
- **ETA**: xem `ml/README.md` — dữ liệu hành trình thật, có hiệu chỉnh về bối cảnh TP.HCM.

## Kết quả thực nghiệm (sinh tự động, tái lập được)

Hai script dưới đây sinh báo cáo trong `docs/`, seed cố định nên chạy lại ra đúng từng con số:

```powershell
python -m backend.dispatch.optimal --report     # -> docs/ket-qua-toi-uu.md
python -m backend.dispatch.robustness --report  # -> docs/ket-qua-do-ben.md
python ml/advanced_eval.py --report             # -> docs/ket-qua-eta-nang-cao.md
```

- **Optimality gap xếp tuyến** (`docs/ket-qua-toi-uu.md`): so 6 chiến lược sắp thứ tự giao
  với thứ tự tối ưu (Held–Karp) trên cùng phân công. NN + 2-opt chỉ lệch **1,4%** (lớn nhất
  2,9%), Nearest Neighbor lệch 2,8%, thứ tự nhập đơn lệch 17,6%.
- **Độ bền vững** (`docs/ket-qua-do-ben.md`): 30 seed × (48 đơn, 8 xe) cho quãng đường
  179,5 ± 36,3 km, đúng giờ 99,4 ± 1,3%; 2-opt giảm 29,3% quãng đường so với thứ tự nhập đơn;
  chiến lược `deadline` thêm 9,7% km nhưng kéo đơn trễ từ 2,23 xuống 0,27.
- **Độ nhạy tham số**: `max_rounds` hội tụ sau 4 vòng; bán kính vùng ùn tắc 2→8 km làm A*
  phải đi vòng 3,5→227,4 km, là căn cứ chọn mặc định 4,5 km.
- **ETA nâng cao** (`docs/ket-qua-eta-nang-cao.md`): tuning 7 cấu hình HGB bằng rolling-origin
  CV (3 fold); khoảng tin cậy 80% học từ phân vị phần dư đạt độ phủ **82,0%** so với 40,0% của
  baseline ±15%; bỏ nhóm đặc trưng giờ làm MAE tăng 3,489 → 3,806 phút.
- **Cơ sở luật** (`docs/co-luat.md`): nguồn nghiệp vụ, ma trận xung đột ưu tiên và bảng đối
  chiếu 21 ca kiểm thử cho R01–R12; `docs/ARCHITECTURE.md` có 4 sơ đồ Mermaid (kiến trúc, vòng
  đời tác tử, luồng dữ liệu, xử lý sự cố bằng A*).
- **Hiệu năng API** (`docs/ket-qua-hieu-nang.md`): 48 đơn ~16 ms, 96 đơn ~91 ms, 144 đơn
  ~180 ms, 200 đơn ~5,2 s (2-opt O(n³) trên tuyến dài); 8 luồng × 5 request không lỗi, kết
  quả nhất quán nhờ cache + lock. Chạy lại bằng `python tools/bench_api.py --report`.

## Kiểm thử tự động

Repo có bộ kiểm thử cho phần lõi (không cần cài mô hình, không gọi mạng):

```powershell
pip install -r requirements.txt -r requirements-dev.txt   # dev cần httpx cho test HTTP
python -m unittest discover -s tests -v
```

69 ca kiểm thử trong `tests/` phủ năm nhóm: mạng lưới và A* (gồm cả việc A* bắt buộc phải
đi vòng khi chặng bị chặn), bài toán gán Hungarian (đối chiếu với vét cạn), xếp tuyến
(2-opt không bao giờ làm xấu kết quả, tổng km khớp), và tác tử + API + toàn vẹn dữ liệu.
GitHub Actions chạy lại toàn bộ ở mỗi lần push: `.github/workflows/ci.yml`.

## Hạn chế đã biết

Nói rõ để người đọc không hiểu nhầm số liệu là thực tế TP.HCM:

1. **Dữ liệu ETA là taxi New York, không phải TP.HCM.** Mô hình học quan hệ quãng đường –
   giờ – thứ → thời lượng, rồi hiệu chỉnh hệ số ùn tắc theo khung giờ khi dự đoán. Chưa có
   dữ liệu GPS xe giao hàng thật ở TP.HCM để kiểm chứng.
2. **Đồ thị chỉ có 16 nút** (bưu cục, cảng, chợ đầu mối). Khoảng cách giữa các nút là số thật
   từ OSRM, nhưng tuyến trong phố nhỏ không được mô hình hoá; đây là mức trừu tượng phù hợp
   cho bài toán chia đơn, không phải chỉ đường từng ngõ.
3. **Đơn hàng mô phỏng theo seed**, không phải lô đơn thật. Ưu điểm là tái lập được kết quả.
4. **A\* trên đồ thị đầy đủ**: nếu không có chặn, đường tối ưu luôn là đi thẳng, nên A\* chỉ
   thật sự có tác dụng khi mô phỏng kẹt xe (một số chặng xuyên tâm bị chặn, xe phải vòng).
5. **Chưa có dữ liệu giao thông thời gian thực**, hệ số ùn tắc là giả định theo khung giờ.
6. **ETA hiển thị trên bản đồ chỉ là ước lượng**, kế hoạch giả định thời gian phục vụ cố định
   tại mỗi điểm.

## Giấy phép

Mã nguồn: **MIT** — xem `LICENSE`.
Dữ liệu bản đồ: OpenStreetMap / OSRM, theo **ODbL 1.0**, cần ghi công "© OpenStreetMap contributors".
Chi tiết nguồn dữ liệu, cách tái tạo: `docs/DATA.md`.

## Ghi chú

Repo dùng commit theo từng bước công việc nhỏ, chia theo mảng để lịch sử đọc được như nhật
ký làm việc. Xem `docs/PLAN.md` để biết tiến độ.

Sinh viên thực hiện: Lê Thanh Tú — Nhóm 14.

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
| `docs/co-luat.md` | Nguồn gốc 12 luật, ma trận xung đột ưu tiên, độ phủ kiểm thử |
| `docs/ket-qua-toi-uu.md` | Optimality gap phần xếp tuyến (Held–Karp) |
| `docs/ket-qua-do-ben.md` | 30 seed, so sánh chiến lược, độ nhạy tham số |
| `docs/ket-qua-eta-nang-cao.md` | Tuning CV, khoảng tin cậy 80%, ablation đặc trưng ETA |
| `docs/ket-qua-hieu-nang.md` | Độ trễ API theo số đơn, gọi đồng thời, giới hạn hiệu năng |
| `docs/import-csv.md` | Định dạng CSV nhập đơn, API lịch sử kế hoạch, file mẫu |
| `docs/DATA.md` | Nguồn dữ liệu, giấy phép, cách tái tạo |
| `docs/REVIEW.md` | Tự đánh giá điểm yếu và những gì đã khắc phục |
| `docs/design-system/tailwind-snippets.md` | Snippet Tailwind (tương đương Dev Mode của Figma) |
| `docs/WORKFLOW.md` | Quy ước: mọi thay đổi đều phải push; script `tools/push.ps1` tự kiểm thử rồi push |

Các tệp kết quả đều sinh tự động bằng lệnh trong mã nguồn, chạy lại thực nghiệm là số liệu
tự khớp.











