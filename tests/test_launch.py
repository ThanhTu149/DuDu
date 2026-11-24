"""Kiểm tra bộ chạy web một chạm (run.bat + tools/run-web.ps1) còn nguyên vẹn.

Mục đích: tránh trường hợp ai đó xoá/đổi tên launcher hoặc bỏ dòng khởi động uvicorn
khiến người dùng mở repo không biết chạy web thế nào.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestLauncher(unittest.TestCase):
    def test_run_bat_exists_and_calls_script(self) -> None:
        launcher = ROOT / "run.bat"
        self.assertTrue(launcher.exists(), "thiếu run.bat ở gốc repo")
        text = launcher.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("run-web.ps1", text)
        self.assertIn("ExecutionPolicy Bypass", text)

    def test_run_web_script_has_key_parts(self) -> None:
        script = ROOT / "tools" / "run-web.ps1"
        self.assertTrue(script.exists(), "thiếu tools/run-web.ps1")
        for ps1 in (ROOT / "tools").glob("*.ps1"):
            self.assertTrue(
                ps1.read_bytes().startswith(b"\xef\xbb\xbf"),
                f"{ps1.name} thiếu UTF-8 BOM nên Windows PowerShell 5.1 sẽ đọc nhầm mã hoá tiếng Việt",
            )
        text = script.read_text(encoding="utf-8-sig")
        for needle in ("Resolve-Python", "Test-DuDuRunning", "uvicorn", "backend.app:app", "requirements.txt"):
            self.assertIn(needle, text, f"run-web.ps1 thiếu {needle}")

    def test_readme_mentions_launcher(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("run.bat", readme)

    def test_docker_files_present(self) -> None:
        self.assertTrue((ROOT / "Dockerfile").exists())
        compose = ROOT / "docker-compose.yml"
        self.assertTrue(compose.exists())
        text = compose.read_text(encoding="utf-8")
        self.assertIn("8000:8000", text)
        self.assertIn("dudu", text)
        launcher = ROOT / "chay-bang-docker.bat"
        self.assertTrue(launcher.exists())
        self.assertIn("docker compose up", launcher.read_text(encoding="utf-8", errors="ignore"))

    def test_required_runtime_files_exist(self) -> None:
        self.assertTrue((ROOT / "requirements.txt").exists())
        self.assertTrue((ROOT / "requirements-lock.txt").exists())
        self.assertIn("==", (ROOT / "requirements-lock.txt").read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "data" / "processed" / "matrix.json").exists())
        self.assertTrue((ROOT / "backend" / "app.py").exists())


if __name__ == "__main__":
    unittest.main()


