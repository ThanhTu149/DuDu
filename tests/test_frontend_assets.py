"""Kiểm tra mọi tài sản tham chiếu trong frontend đều tồn tại (chống 404 khi demo).

Đọc index.html, app.css, app.js tìm các đường dẫn /assets/... rồi đối chiếu với thư mục
web/. Cũng kiểm tra favicon và các tệp bắt buộc khác.

Chạy cùng bộ test:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

TEXT_FILES = {
    "index.html": WEB / "index.html",
    "app.css": WEB / "assets" / "app.css",
    "app.js": WEB / "assets" / "app.js",
}
ASSET_PATTERN = re.compile(r"""/assets/[A-Za-z0-9._/-]+""")
REQUIRED_FILES = [
    "index.html",
    "assets/app.css",
    "assets/app.js",
    "assets/banner.jpg",
    "assets/avatar.jpg",
    "assets/DuDu_Name.png",
    "assets/favicon.png",
    "assets/favicon-180.png",
    "assets/stickers/dudu.png",
    "assets/stickers/gau-nau.png",
    "assets/stickers/gau-truc.png",
    "assets/stickers/gau-trang.png",
    "assets/markers/xe-hong.svg",
    "assets/markers/ket-xe.svg",
    "assets/markers/kho-dong.svg",
    "assets/icons/truck.svg",
    "assets/icons/scooter.svg",
    "assets/icons/package.svg",
    "assets/icons/warehouse.svg",
    "assets/icons/clock.svg",
    "assets/icons/warning.svg",
    "assets/icons/route.svg",
    "assets/icons/chip.svg",
]


class TestFrontendAssets(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        for relative in REQUIRED_FILES:
            with self.subTest(file=relative):
                self.assertTrue((WEB / relative).exists(), f"thiếu tệp {relative}")

    def test_every_asset_reference_resolves(self) -> None:
        missing: list[str] = []
        for name, path in TEXT_FILES.items():
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for reference in set(ASSET_PATTERN.findall(text)):
                target = WEB / reference.lstrip("/")
                if not target.exists():
                    missing.append(f"{name} -> {reference}")
        self.assertEqual(missing, [], "có tài sản được tham chiếu nhưng không tồn tại")

    def test_index_has_meta_and_favicon(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        for needle in ('rel="icon"', 'apple-touch-icon', 'name="description"', 'name="viewport"'):
            self.assertIn(needle, html, f"index.html thiếu {needle}")

    def test_theme_tokens_consistent(self) -> None:
        css = (WEB / "assets" / "app.css").read_text(encoding="utf-8")
        # chế độ tối phải định nghĩa lại bề mặt sáng, nếu không sẽ có nền trắng chói
        for token in ("--paper", "--paper-2", "--ink", "--surface", "--line"):
            self.assertIn(token, css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn("--surface:", css.split('[data-theme="dark"]', 1)[1])

    def test_map_legend_matches_symbols(self) -> None:
        # chú thích phải dùng đúng 2 huy hiệu + 2 chấm như trên bản đồ, không còn chấm/vuông cũ
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn("lg-badge--depot", html)
        self.assertIn("lg-badge--hub", html)
        self.assertIn("lg-dot--route", html)
        self.assertIn("lg-dot--late", html)
        self.assertNotIn("swatch sw-depot", html)
        js = (WEB / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("updateHubGlyphs", js)
        self.assertIn("HUB_GLYPHS", js)

    def test_mobile_nav_present(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="mobile-nav"', html)
        self.assertEqual(html.count("mob-btn"), 4)


if __name__ == "__main__":
    unittest.main()


