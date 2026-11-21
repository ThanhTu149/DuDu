"""Sinh ma trận khoảng cách / thời gian di chuyển giữa các nút mạng lưới.

Nguồn: OSRM công khai (mạng đường OpenStreetMap). Mỗi cặp nút được OSRM định tuyến
thật trên đường bộ TP.HCM, sau đó lưu lại để cả nhóm dùng chung, không phải gọi mạng
lại mỗi lần chạy.

    python data/build_matrix.py            # dùng cache nếu còn hợp lệ
    python data/build_matrix.py --force    # gọi lại OSRM

Kết quả: data/processed/matrix.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Windows: console mặc định cp1252 nên in tiếng Việt sẽ lỗi — ép UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
HUBS_FILE = ROOT / "data" / "hubs.json"
OUT_FILE = ROOT / "data" / "processed" / "matrix.json"

OSRM = "https://router.project-osrm.org"
UA = "DuDu-BTL-AI/1.0 (bai tap lon mon Tri tue nhan tao - UTH)"


def load_hubs() -> list[dict]:
    with HUBS_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)["nodes"]


def _fingerprint(nodes: list[dict]) -> str:
    payload = json.dumps(
        [[n["id"], round(n["lat"], 6), round(n["lon"], 6)] for n in nodes],
        separators=(",", ":"),
    )
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def _get_json(url: str, tries: int = 4) -> dict:
    last: Exception | None = None
    for attempt in range(tries):
        request = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Không gọi được OSRM sau {tries} lần: {last}")


def fetch_table(nodes: list[dict]) -> tuple[list[list[float]], list[list[float]]]:
    """Một lệnh /table duy nhất cho cả ma trận — OSRM trả về N x N."""
    coords = ";".join(f"{n['lon']:.6f},{n['lat']:.6f}" for n in nodes)
    url = f"{OSRM}/table/v1/driving/{coords}?annotations=duration,distance"
    data = _get_json(url)
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM trả lỗi: {data.get('code')} — {data.get('message')}")
    return data["durations"], data["distances"]


def build(force: bool = False) -> dict:
    nodes = load_hubs()
    stamp = _fingerprint(nodes)

    if OUT_FILE.exists() and not force:
        cached = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        if cached.get("hub_fingerprint") == stamp:
            print(f"[cache] {OUT_FILE.relative_to(ROOT)} — {len(nodes)} nút, không cần gọi lại OSRM")
            return cached

    print(f"[osrm] đang lấy ma trận {len(nodes)}x{len(nodes)} …")
    durations, distances = fetch_table(nodes)

    payload = {
        "source": OSRM,
        "profile": "driving",
        "hub_fingerprint": stamp,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ids": [n["id"] for n in nodes],
        "duration_s": durations,   # giây
        "distance_m": distances,   # mét
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] ghi {OUT_FILE.relative_to(ROOT)} ({OUT_FILE.stat().st_size // 1024} KB)")
    return payload


def leg_geometry(a: tuple[float, float], b: tuple[float, float]) -> dict:
    """Đường đi thật giữa 2 toạ độ, dạng GeoJSON — dùng để vẽ tuyến trên bản đồ."""
    url = (
        f"{OSRM}/route/v1/driving/{a[1]:.6f},{a[0]:.6f};{b[1]:.6f},{b[0]:.6f}"
        "?overview=full&geometries=geojson&steps=false"
    )
    data = _get_json(url, tries=2)
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError("Không tìm được đường đi giữa hai điểm")
    route = data["routes"][0]
    return {
        "type": "LineString",
        "coordinates": route["geometry"]["coordinates"],
        "distance_m": route["distance"],
        "duration_s": route["duration"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sinh ma trận khoảng cách từ OSRM")
    parser.add_argument("--force", action="store_true", help="bỏ qua cache, gọi lại OSRM")
    args = parser.parse_args()
    build(force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
