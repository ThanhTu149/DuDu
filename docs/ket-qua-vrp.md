# Kết quả thí nghiệm xếp tuyến theo quy mô

Sinh tự động bằng `python -m backend.dispatch.evaluate --report`. Cùng một kịch bản (seed 7, 8 xe, cách chia đơn Hungary), chỉ đổi chiến lược sắp thứ tự giao.

| Số đơn | Thứ tự nhập | Nearest Neighbor | NN + 2-opt | Clarke–Wright | C-W + 2-opt |
|---|---|---|---|---|---|
| 48 | 184.1 km | 146.7 km | 146.7 km | 158.3 km | 146.7 km |
| 96 | 250.3 km | 159.0 km | 156.0 km | 167.4 km | 156.0 km |
| 144 | 617.0 km | 186.1 km | 166.8 km | 197.3 km | 166.8 km |

## Tỉ lệ đúng giờ

| Số đơn | Thứ tự nhập | Nearest Neighbor | NN + 2-opt | Clarke–Wright | C-W + 2-opt |
|---|---|---|---|---|---|
| 48 | 87.5% | 91.7% | 91.7% | 93.8% | 91.7% |
| 96 | 82.3% | 84.4% | 82.3% | 82.3% | 81.2% |
| 144 | 61.8% | 76.4% | 74.3% | 67.4% | 74.3% |

## Mức cải thiện của C-W + 2-opt so với Nearest Neighbor

| Số đơn | 48 | 96 | 144 |
|---|---|---|---|
| Giảm quãng đường | 0.0% | 1.9% | 10.4% |

## Cách đọc bảng

- Ở 48 đơn mỗi tuyến chỉ 6 điểm, Nearest Neighbor đã gần tối ưu nên 2-opt không cải thiện; ở 144 đơn mỗi tuyến 18 điểm, 2-opt giảm 10,4% quãng đường. Kết luận: 2-opt đáng dùng khi tuyến dài, không phải lúc nào cũng đáng.
- Clarke–Wright (dựng tuyến bằng tiết kiệm) *không* vượt Nearest Neighbor khi chỉ sắp thứ tự cho một danh sách điểm có sẵn, vì nó được thiết kế để quyết định gộp tuyến ở cấp đội xe. Ở cấp đội xe (xem bảng chia đơn trong báo cáo), nó cạnh tranh với tham lam nhưng kém Hungary vì bỏ qua hạn giao.
- Cột "Thứ tự nhập" là mốc xấu nhất — tương đương điều phối viên giao đơn theo thứ tự đơn đến, không sắp gì.
