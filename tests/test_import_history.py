"""Kiểm thử nhập đơn từ CSV và lưu lịch sử kế hoạch (SQLite)."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path

from backend.dispatch.import_orders import MAX_IMPORT_ROWS, parse_orders_csv
from backend.dispatch.network import load_network

try:  # httpx chỉ cần cho phần API
    from fastapi.testclient import TestClient

    from backend.app import app

    HAVE_HTTP_CLIENT = True
except ImportError:  # pragma: no cover - máy chưa cài httpx
    HAVE_HTTP_CLIENT = False
    app = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "data" / "samples" / "don-hang-mau.csv"
HEADER = "ma_don,diem_giao,khoi_luong_kg,the_tich_l,hang_hoa,cod,uu_tien,hen_giao_phut\n"


class TestParseOrdersCsv(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.net = load_network()

    def test_sample_file_parses(self) -> None:
        parsed = parse_orders_csv(SAMPLE_CSV.read_text(encoding="utf-8"), self.net)
        self.assertEqual(parsed["count"], 12)
        self.assertEqual(parsed["warnings"], [])
        order = parsed["orders"][0]
        for key in ("id", "code", "dest_hub", "lat", "lon", "weight_kg", "volume_l",
                    "goods", "goods_label", "priority", "priority_label", "promised_min", "service_min"):
            self.assertIn(key, order)
        self.assertIn(order["dest_hub"], self.net.hubs)

    def test_accepts_english_headers_and_hub_names(self) -> None:
        csv = "order_id,dest_hub,weight_kg,volume_l\nX1,Cảng Cát Lái,2.0,5\n"
        parsed = parse_orders_csv(csv, self.net)
        self.assertEqual(parsed["orders"][0]["dest_hub"], "cat-lai")
        self.assertEqual(parsed["orders"][0]["id"], "X1")

    def test_skips_invalid_rows_with_warnings(self) -> None:
        csv = HEADER + "A,q1,2.0,5\nB,khong-co,2.0,5\nC,q3,abc,5\nD,q5,2.0,5\n"
        parsed = parse_orders_csv(csv, self.net)
        self.assertEqual(parsed["count"], 2)
        self.assertEqual(len(parsed["warnings"]), 2)
        self.assertTrue(any("không có trong mạng" in warning for warning in parsed["warnings"]))

    def test_rejects_missing_columns(self) -> None:
        with self.assertRaises(ValueError):
            parse_orders_csv("ma_don,khoi_luong_kg\nX1,2\n", self.net)

    def test_rejects_empty_or_all_invalid(self) -> None:
        with self.assertRaises(ValueError):
            parse_orders_csv("", self.net)
        with self.assertRaises(ValueError):
            parse_orders_csv(HEADER + "A,khong-co,2.0,5\n", self.net)

    def test_caps_number_of_rows(self) -> None:
        rows = "".join(f"DH-{index},q1,2.0,5\n" for index in range(MAX_IMPORT_ROWS + 5))
        parsed = parse_orders_csv(HEADER + rows, self.net)
        self.assertEqual(parsed["count"], MAX_IMPORT_ROWS)
        self.assertTrue(any("tối đa" in warning for warning in parsed["warnings"]))

    def test_goods_and_priority_normalized(self) -> None:
        csv = HEADER + "A,q1,2.0,5,khong-hop-le,0,khong-hop-le,\n"
        parsed = parse_orders_csv(csv, self.net)
        order = parsed["orders"][0]
        self.assertEqual(order["goods"], "thuong")
        self.assertEqual(order["priority"], "tieu_chuan")
        self.assertEqual(order["promised_min"], 240)
        self.assertTrue(parsed["warnings"])


@unittest.skipUnless(HAVE_HTTP_CLIENT, "cần cài httpx: pip install -r requirements-dev.txt")
class TestImportAndHistoryApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._old_db = os.environ.get("DUDU_DB")
        os.environ["DUDU_DB"] = str(Path(cls._tempdir.name) / "history.sqlite3")
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)
        if cls._old_db is None:
            os.environ.pop("DUDU_DB", None)
        else:
            os.environ["DUDU_DB"] = cls._old_db
        cls._tempdir.cleanup()

    def test_template_download(self) -> None:
        response = self.client.get("/api/orders/template")
        self.assertEqual(response.status_code, 200)
        self.assertIn("diem_giao", response.text)

    def test_import_plan_from_csv(self) -> None:
        csv = SAMPLE_CSV.read_text(encoding="utf-8")
        response = self.client.post("/api/plan/import", json={"csv": csv, "seed": 7, "vehicles": 6})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["metrics"]["orders"], 12)
        self.assertEqual(payload["import"]["count"], 12)
        self.assertEqual(payload["import"]["warnings"], [])
        self.assertIsNotNone(payload["history_id"])

    def test_import_invalid_csv_returns_400(self) -> None:
        response = self.client.post("/api/plan/import", json={"csv": "khong-phai-csv", "seed": 7})
        self.assertEqual(response.status_code, 400)
        self.assertIn("CSV không hợp lệ", response.json()["detail"])

    def test_history_list_and_detail(self) -> None:
        csv = SAMPLE_CSV.read_text(encoding="utf-8")
        created = self.client.post("/api/plan/import", json={"csv": csv, "seed": 11, "vehicles": 6}).json()
        listing = self.client.get("/api/history?limit=5").json()
        self.assertTrue(listing["items"])
        ids = [item["id"] for item in listing["items"]]
        self.assertIn(created["history_id"], ids)

        detail = self.client.get(f"/api/history/{created['history_id']}").json()
        self.assertEqual(detail["kind"], "import")
        self.assertEqual(detail["payload"]["metrics"]["orders"], 12)

    def test_history_unknown_id_returns_404(self) -> None:
        response = self.client.get("/api/history/999999")
        self.assertEqual(response.status_code, 404)

    def test_plan_endpoint_saves_history(self) -> None:
        response = self.client.post("/api/plan", json={"seed": 7, "orders": 12, "vehicles": 6})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()["history_id"])


if __name__ == "__main__":
    unittest.main()

