"""Lưu lịch sử kế hoạch vào SQLite để reload trang không mất kết quả.

Mỗi lần lập kế hoạch (kịch bản, nhập CSV, hoặc xử lý sự cố) được ghi một dòng gồm:
  - metadata truy vấn (seed, số đơn, số xe, chiến lược),
  - tóm tắt metrics,
  - toàn bộ payload JSON để UI khôi phục lại kế hoạch.

API đọc: `GET /api/history` và `GET /api/history/{id}`.

Đường dẫn DB mặc định `data/processed/history.sqlite3` (đã gitignore). Đặt biến môi trường
`DUDU_DB` để đổi đường dẫn — test dùng biến này với file tạm.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "processed" / "history.sqlite3"
_INIT_LOCK = threading.Lock()
_INITIALIZED_PATH: str | None = None


def db_path() -> Path:
    return Path(os.environ.get("DUDU_DB", str(DEFAULT_DB)))


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def init() -> None:
    global _INITIALIZED_PATH
    resolved = str(db_path().resolve())
    with _INIT_LOCK:
        if _INITIALIZED_PATH == resolved:
            return
        with closing(_connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
        _INITIALIZED_PATH = resolved


def save(kind: str, request: dict, result: dict) -> int | None:
    """Ghi một kế hoạch; lỗi ghi không được làm hỏng request chính (trả None)."""
    try:
        init()
        metrics = result.get("metrics", {})
        summary = {
            "seed": result.get("seed"),
            "orders": metrics.get("orders"),
            "vehicles": metrics.get("vehicles_used"),
            "total_km": metrics.get("total_km"),
            "total_min": metrics.get("total_min"),
            "late_count": metrics.get("late_count"),
            "on_time_rate": metrics.get("on_time_rate"),
            "violations": metrics.get("violations"),
            "blocked": metrics.get("blocked"),
        }
        payload = json.dumps(result, ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()
        with closing(_connect()) as connection, connection:
            cursor = connection.execute(
                "INSERT INTO plans (created_at, kind, summary_json, request_json, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (now, kind, json.dumps(summary, ensure_ascii=False),
                 json.dumps(request, ensure_ascii=False), payload),
            )
            return int(cursor.lastrowid)
    except Exception:
        return None


def recent(limit: int = 20) -> list[dict]:
    try:
        init()
        with closing(_connect()) as connection, connection:
            rows = connection.execute(
                "SELECT id, created_at, kind, summary_json FROM plans ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    except Exception:
        return []
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "kind": row["kind"],
            "summary": json.loads(row["summary_json"]),
        }
        for row in rows
    ]


def get(plan_id: int) -> dict | None:
    try:
        init()
        with closing(_connect()) as connection, connection:
            row = connection.execute(
                "SELECT id, created_at, kind, request_json, payload_json FROM plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "kind": row["kind"],
        "request": json.loads(row["request_json"]),
        "payload": json.loads(row["payload_json"]),
    }


