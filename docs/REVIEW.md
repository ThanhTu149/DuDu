# Tự đánh giá: nếu chấm repo này như giảng viên thì thấy gì

Mục này ghi lại những điểm yếu mình tự nhận ra khi soi repo bằng con mắt người chấm,
và đã xử lý đến đâu. Cái nào chưa xử lý được thì nói rõ lý do thay vì che.

## Đã khắc phục trong đợt rà soát này

| Điểm yếu (góc nhìn giảng viên) | Mức | Đã xử lý |
|---|---|---|
| **Không có kiểm thử tự động** — không chứng minh được code chạy đúng, sửa là vỡ | Nặng | Thêm `tests/` gồm **44 ca** `unittest`: mạng lưới/A*, Hungarian đối chiếu vét cạn, 2-opt không làm xấu, tác tử, API, toàn vẹn dữ liệu. Chạy: `python -m unittest discover -s tests -v` |
| **Không có CI** — không ai kiểm tra mỗi lần push | Nặng | `.github/workflows/ci.yml`: cài phụ thuộc, chạy test, `node --check` cho JS, import API |
| **README hứa A\* nhưng code không gọi A\*** — điểm yếu chết người nếu giảng viên grep | Nặng | A* được nối thật: thêm `RoutingView` + `congestion_edges`; sự cố kẹt xe chặn các chặng xuyên tâm, A* tìm đường vòng, nhật ký ghi "A* tìm đường vòng tránh vùng ùn tắc: 5 chặng, +29,0 km". Có test riêng khẳng định đường vòng không đi qua chặng bị cấm |
| **Chia train/test ngẫu nhiên** cho dữ liệu thời gian → dễ rò rỉ, kết quả lạc quan | Trung bình | Thêm giao thức **temporal** (train ngày 1–24, test ngày 25–31) làm kết quả chính; giữ random 80/20 để so sánh. Hai giao thức chênh ≤ 0,06 phút MAE → kết luận vững |
| **Chỉ có hai mô hình**, không có mốc trên mạnh hơn | Nhẹ | Thêm **Gradient Boosting** (`HistGradientBoosting`); chỉ hơn Random Forest 0,06 phút → chứng minh cây đã đủ tốt, không cần mô hình nặng |
| **Không có LICENSE** | Nhẹ | Thêm giấy phép **MIT** |
| **Không nói rõ dữ liệu lấy từ đâu, giấy phép gì** | Trung bình | Thêm `docs/DATA.md`: nguồn NYC TLC, OSM/OSRM theo ODbL, cách tái tạo, phần nào mô phỏng |
| **Không có phần "hạn chế"** — dễ bị hỏi xoáy khi bảo vệ | Trung bình | Thêm mục **Hạn chế đã biết** trong README (6 điểm) và mục "Giới hạn" trong `docs/ket-qua-eta.md` |
| **Số liệu trong docs dễ trôi** so với code sau khi sửa | Nhẹ | Số ETA cập nhật lại theo lần huấn luyện mới; ghi rõ hai giao thức và cách chạy lại |

## Chưa khắc phục được (và vì sao)

| Điểm yếu | Vì sao chưa sửa |
|---|---|
| **Dữ liệu ETA là taxi New York, không phải TP.HCM** | Không có bộ hành trình GPS công khai của xe giao hàng TP.HCM. Cách đang dùng: học *quan hệ* quãng đường–giờ–thứ, chỉ lấy **hình dạng ùn tắc theo giờ**, còn thời gian nền là OSRM. Đã ghi rõ là giả định |
| **Chỉ 16 nút mạng** | Bài toán ở mức chia đơn và xếp tuyến giữa các khu vực; muốn chỉ đường từng con hẻm phải có dữ liệu GPS và bản đồ số lớn hơn nhiều |
| **Đơn hàng mô phỏng theo seed** | Lô đơn thật của doanh nghiệp không công khai. Ưu điểm bù lại: tái lập được 100% kết quả |
| **Không có dữ liệu giao thông thời gian thực** | Cần API của đơn vị vận hành (Google/HERE) có phí; hệ số ùn tắc là giả định theo khung giờ |
| **Chưa kiểm thử giao diện tự động trong CI** | Cần Chromium + Playwright trong CI (nặng); hiện kiểm bằng script Playwright chạy tay, còn CI chỉ `node --check` |
| **Báo cáo/slide không nằm trong repo** | Theo yêu cầu nộp bài tách riêng; repo chỉ chứa mã nguồn và tài liệu kỹ thuật |

## Cách tự kiểm tra trong 1 phút

```powershell
python -m unittest discover -s tests -v     # 44 ca
python ml/train_eta.py                      # in cả hai giao thức
python -m backend.dispatch.rule_stats       # thống kê luật
```

Nếu chạy đúng, số liệu sẽ khớp với `docs/ket-qua-eta.md`, `docs/ket-qua-luat.md`.
