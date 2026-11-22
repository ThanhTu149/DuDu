# Build: docker build -t dudu .
# Run:   docker run --rm -p 8000:8000 dudu
# Mở:    http://127.0.0.1:8000
#
# Ảnh chỉ chứa code + dữ liệu đã commit (ma trận OSRM, geometry, hubs).
# Mô hình ETA (~105 MB) và dữ liệu thô không nằm trong ảnh: nếu thiếu, web vẫn chạy và
# nút "ETA mô hình" tự dùng OSRM free-flow (API trả warnings).

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
