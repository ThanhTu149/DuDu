"""Tách 4 nhân vật khỏi banner DuDu thành sticker PNG nền trong suốt.

Cách làm: khoanh vùng từng nhân vật trên banner gốc, rồi làm sạch nền bằng flood-fill
từ mép ảnh (nền kem phẳng, chỉ cần loang từ biên vào). Nhờ vậy nét viền nhân vật được
giữ nguyên, không phải "xóa nền" bằng AI nên chạy offline, kết quả tất định.

Chạy:  python tools/make_stickers.py
Kết quả: web/assets/stickers/{dudu,gau-nau,gau-truc,gau-trang}.png
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
BANNER = ROOT / "web" / "assets" / "banner.jpg"
OUT = ROOT / "web" / "assets" / "stickers"
CACHE = ROOT / ".cache" / "stickers"

# (tên, hộp cắt x0,y0,x1,y1) — toạ độ dò trên banner 1024×572
CROPS: dict[str, tuple[str, int, int, int, int]] = {
    "dudu": ("DuDu điều phối viên", 500, 28, 780, 316),
    "gau-nau": ("Gấu Nâu xếp hàng", 776, 52, 1000, 214),
    "gau-truc": ("Gấu Trúc đọc máy tính bảng", 846, 200, 1024, 528),
    "gau-trang": ("Gấu Trắng vẽ bản đồ", 602, 288, 792, 470),
}

BACKDROP = (250, 245, 232)   # màu nền kem đo từ góc ảnh
TOLERANCE = 26               # khoảng cách màu tối đa để coi là nền
TARGET_WIDTH = 640           # xuất 2x so với bản gốc, đủ nét cho màn hình retina


def background_mask(pixel: tuple[int, int, int]) -> bool:
    dr = pixel[0] - BACKDROP[0]
    dg = pixel[1] - BACKDROP[1]
    db = pixel[2] - BACKDROP[2]
    return dr * dr + dg * dg + db * db <= TOLERANCE * TOLERANCE


def remove_background(image: Image.Image) -> Image.Image:
    """Loang từ 4 mép ảnh, xoá các điểm thuộc nền; ruột nhân vật được giữ vì nằm sau viền."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    seen = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        for y in (0, height - 1):
            queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        index = y * width + x
        if seen[index]:
            continue
        seen[index] = 1
        if not background_mask(pixels[x, y][:3]):
            continue
        pixels[x, y] = (0, 0, 0, 0)
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    # Làm mềm mép trong suốt một chút để không bị răng cưa khi đặt lên nền khác
    alpha = rgba.getchannel("A").filter(ImageFilter.GaussianBlur(0.6))
    rgba.putalpha(alpha)
    return rgba


def trim(image: Image.Image, margin: int = 6) -> Image.Image:
    box = image.getchannel("A").point(lambda value: 255 if value > 8 else 0).getbbox()
    if not box:
        return image
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0 - margin), max(0, y0 - margin)
    x1, y1 = min(image.width, x1 + margin), min(image.height, y1 + margin)
    return image.crop((x0, y0, x1, y1))


def main() -> int:
    if not BANNER.exists():
        raise SystemExit(f"Không thấy banner: {BANNER}")
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    banner = Image.open(BANNER)

    previews: list[tuple[str, Image.Image]] = []
    for slug, (label, x0, y0, x1, y1) in CROPS.items():
        crop = banner.crop((x0, y0, x1, y1))
        sticker = trim(remove_background(crop))
        scale = TARGET_WIDTH / sticker.width
        sticker = sticker.resize(
            (TARGET_WIDTH, max(1, round(sticker.height * scale))), Image.LANCZOS
        )
        path = OUT / f"{slug}.png"
        sticker.save(path, optimize=True)

        # ảnh xem trước đặt trên nền caro để thấy rõ vùng trong suốt
        tile = Image.new("RGBA", sticker.size, (255, 255, 255, 255))
        for ty in range(0, tile.height, 16):
            for tx in range(0, tile.width, 16):
                if (tx // 16 + ty // 16) % 2 == 0:
                    tile.paste((228, 228, 228, 255), (tx, ty, tx + 16, ty + 16))
        tile.alpha_composite(sticker)
        previews.append((label, tile))
        print(f"[ok] {slug:<10} {label:<28} {sticker.width}×{sticker.height}  {path.name}")

    if previews:
        pad = 12
        width = sum(item.width for _, item in previews) + pad * (len(previews) + 1)
        height = max(item.height for _, item in previews) + pad * 2
        sheet = Image.new("RGB", (width, height), (245, 242, 236))
        x = pad
        for _, image in previews:
            sheet.paste(image.convert("RGB"), (x, pad))
            x += image.width + pad
        sheet.save(CACHE / "sticker-preview.png")
        print(f"[ok] ảnh xem trước: {CACHE / 'sticker-preview.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())



