"""Kiểm thử tự động cho phần lõi của DuDu.

Chạy:  python -m unittest discover -s tests -v      (không cần cài thêm gì)
Hoặc:  pytest tests -q                              (nếu đã cài pytest)

Toàn bộ test chỉ dùng dữ liệu đã commit trong repo (data/hubs.json +
data/processed/matrix.json), không gọi mạng, không cần mô hình ETA.
"""
