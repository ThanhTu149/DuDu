"""Kiểm thử dọn bản ghi trùng trong lịch sử (không cần HTTP)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from backend.dispatch import history


class TestHistoryDedupe(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._old_db = os.environ.get("DUDU_DB")
        os.environ["DUDU_DB"] = str(Path(self._tempdir.name) / "history.sqlite3")
        history._INITIALIZED_PATH = None
        history.clear()

    def tearDown(self) -> None:
        if self._old_db is None:
            os.environ.pop("DUDU_DB", None)
        else:
            os.environ["DUDU_DB"] = self._old_db
        history._INITIALIZED_PATH = None
        self._tempdir.cleanup()

    def _insert_raw(self, kind: str, summary: dict, request: dict) -> None:
        history.init()
        with history.closing(history._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO plans (created_at, kind, summary_json, request_json, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                ("2026-01-01T00:00:00+00:00", kind, json.dumps(summary), json.dumps(request), "{}"),
            )

    def test_recent_collapses_identical_records(self) -> None:
        summary = {"source": "plan", "seed": 7, "orders": 48, "total_km": 160.3}
        request = {"seed": 7, "orders": 48, "vehicles": 8}
        for _ in range(4):
            self._insert_raw("plan", summary, request)
        self._insert_raw("plan", {**summary, "seed": 11}, {**request, "seed": 11})
        history.init()
        self.assertEqual(history.count(), 5)  # trước khi dọn
        rows = history.recent(limit=20)
        self.assertEqual(len(rows), 2)
        self.assertEqual(history.count(), 2)

    def test_save_deduplicates_identical_latest(self) -> None:
        request = {"seed": 7, "orders": 48, "vehicles": 8}
        result = {"seed": 7, "metrics": {"orders": 48, "total_km": 160.3, "violations": 3}}
        first = history.save("plan", request, result)
        second = history.save("plan", request, result)
        self.assertEqual(first, second)
        self.assertEqual(history.count(), 1)
        third = history.save("plan", {**request, "vehicles": 6}, result)
        self.assertNotEqual(third, first)
        self.assertEqual(history.count(), 2)


if __name__ == "__main__":
    unittest.main()
