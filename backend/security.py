"""Bảo mật tuỳ chọn cho API: API key và giới hạn tần suất endpoint nặng.

Mặc định web chạy mở như bản demo. Bật bảo vệ bằng biến môi trường:

- ``DUDU_API_KEY``: nếu đặt, mọi request ``/api/*`` (trừ ``/api/health``) phải kèm header
  ``X-API-Key`` đúng giá trị; thiếu/sai trả 401.
- ``DUDU_RATE_LIMIT``: số request nặng tối đa mỗi phút cho một client (mặc định 120). Endpoint
  tính là nặng: ``/api/plan*``, ``/api/incident``, ``/api/compare``. Quá hạn trả 429 kèm
  header ``Retry-After``.

Client được nhận diện theo header ``X-Client-Id`` (nếu có) hoặc địa chỉ kết nối. Header này
tiện cho test/benchmark cục bộ; khi triển khai thật nên dựa vào IP/proxy tin cậy.
"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

AUTH_EXEMPT_PATHS = {"/api/health"}
HEAVY_PREFIXES = ("/api/plan", "/api/incident", "/api/compare")
WINDOW_SECONDS = 60.0
DEFAULT_RATE_LIMIT = 120


def configured_api_key() -> str:
    return os.environ.get("DUDU_API_KEY", "").strip()


def configured_rate_limit() -> int:
    try:
        return max(1, int(os.environ.get("DUDU_RATE_LIMIT", str(DEFAULT_RATE_LIMIT))))
    except ValueError:
        return DEFAULT_RATE_LIMIT


class SecurityMiddleware(BaseHTTPMiddleware):
    """Chặn theo API key (nếu cấu hình) và giới hạn tần suất endpoint nặng."""

    def __init__(self, app) -> None:  # noqa: ANN001 - kiểu ASGI app
        super().__init__(app)
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_prune = time.monotonic()

    async def dispatch(self, request, call_next):  # noqa: ANN001
        path = request.url.path
        if path.startswith("/api/"):
            key = configured_api_key()
            if key and path not in AUTH_EXEMPT_PATHS:
                provided = request.headers.get("x-api-key", "").strip()
                if provided != key:
                    return JSONResponse(
                        {"detail": "thiếu hoặc sai X-API-Key"},
                        status_code=401,
                        headers={"WWW-Authenticate": "ApiKey"},
                    )

            if path.startswith(HEAVY_PREFIXES):
                client = request.headers.get("x-client-id") or (
                    request.client.host if request.client else "unknown"
                )
                limited = self._consume(client)
                if limited is not None:
                    return JSONResponse(
                        {"detail": f"quá giới hạn {configured_rate_limit()} request/phút — thử lại sau {limited} giây"},
                        status_code=429,
                        headers={"Retry-After": str(limited)},
                    )

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; "
            "img-src 'self' data:; script-src 'self'; connect-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com",
        )
        return response

    def _consume(self, client: str) -> int | None:
        """Ghi nhận một request; trả số giây phải chờ nếu vượt hạn, None nếu hợp lệ."""
        now = time.monotonic()
        limit = configured_rate_limit()
        with self._lock:
            self._prune(now)
            bucket = self._hits[client]
            while bucket and now - bucket[0] > WINDOW_SECONDS:
                bucket.popleft()
            if len(bucket) >= limit:
                return max(1, math.ceil(WINDOW_SECONDS - (now - bucket[0])))
            bucket.append(now)
            return None

    def _prune(self, now: float) -> None:
        """Dọn client cũ theo chu kỳ để bộ nhớ không phình khi bị quét nhiều IP."""
        if now - self._last_prune < WINDOW_SECONDS:
            return
        for client in list(self._hits):
            bucket = self._hits[client]
            while bucket and now - bucket[0] > WINDOW_SECONDS:
                bucket.popleft()
            if not bucket:
                self._hits.pop(client, None)
        self._last_prune = now
