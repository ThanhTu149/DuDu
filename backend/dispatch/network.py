"""Mạng lưới giao thông: nạp ma trận OSRM, tìm đường A*, tính khoảng cách chim bay."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HUBS_FILE = ROOT / "data" / "hubs.json"
MATRIX_FILE = ROOT / "data" / "processed" / "matrix.json"

EARTH_R_KM = 6371.0
# Tốc độ tối đa dùng cho heuristic A*: 70 km/h. Heuristic phải không vượt quá chi phí
# thật (tính bất đẳng thức tam giác), chọn cao hơn tốc độ thực tế sẽ làm A* trả sai.
MAX_SPEED_KMH = 70.0


@dataclass(frozen=True)
class Hub:
    id: str
    name: str
    kind: str
    district: str
    lat: float
    lon: float


def haversine_km(a: Hub | tuple[float, float], b: Hub | tuple[float, float]) -> float:
    lat1, lon1 = (a.lat, a.lon) if isinstance(a, Hub) else a
    lat2, lon2 = (b.lat, b.lon) if isinstance(b, Hub) else b
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(h))


class Network:
    """Đồ thị đầy đủ trên các nút, trọng số lấy từ OSRM (giây và mét)."""

    def __init__(self, hubs: list[Hub], duration_s: list[list[float]], distance_m: list[list[float]]) -> None:
        self.hubs = {h.id: h for h in hubs}
        self.order = [h.id for h in hubs]
        self.index = {hub_id: i for i, hub_id in enumerate(self.order)}
        self.duration = duration_s
        self.distance = distance_m

    # -- truy vấn cơ bản -------------------------------------------------
    def dur(self, a: str, b: str) -> float:
        """Thời gian di chuyển (giây) giữa hai nút."""
        return float(self.duration[self.index[a]][self.index[b]])

    def dist(self, a: str, b: str) -> float:
        """Khoảng cách (mét) giữa hai nút."""
        return float(self.distance[self.index[a]][self.index[b]])

    def dur_min(self, a: str, b: str) -> float:
        return self.dur(a, b) / 60.0

    def hub(self, hub_id: str) -> Hub:
        return self.hubs[hub_id]

    # -- A* ---------------------------------------------------------------
    def heuristic(self, a: str, b: str) -> float:
        """Cận dưới của thời gian còn lại (giây): đường chim bay / tốc độ tối đa."""
        return haversine_km(self.hubs[a], self.hubs[b]) / MAX_SPEED_KMH * 3600.0

    def astar(self, start: str, goal: str, blocked: set[str] | None = None) -> tuple[list[str], float]:
        """A* trên đồ thị đầy đủ. Trả về (đường đi, chi phí giây).

        Với đồ thị đầy đủ và chi phí thoả bất đẳng thức tam giác, đường đi tối ưu
        gần như luôn là đường trực tiếp; A* ở đây dùng để (a) đúng yêu cầu học phần,
        (b) tìm đường vòng khi một nút bị chặn (ngập, cấm tải).
        """
        import heapq

        blocked = blocked or set()
        if start == goal:
            return [start], 0.0
        open_heap: list[tuple[float, int, str]] = [(self.heuristic(start, goal), 0, start)]
        g_score = {start: 0.0}
        parent: dict[str, str] = {}
        visited: set[str] = set()
        counter = 0
        while open_heap:
            _, _, current = heapq.heappop(open_heap)
            if current in visited:
                continue
            visited.add(current)
            if current == goal:
                path = [current]
                while path[-1] != start:
                    path.append(parent[path[-1]])
                return list(reversed(path)), g_score[goal]
            for nxt in self.order:
                if nxt in blocked or nxt == current or nxt in visited:
                    continue
                tentative = g_score[current] + self.dur(current, nxt)
                if tentative < g_score.get(nxt, math.inf):
                    g_score[nxt] = tentative
                    parent[nxt] = current
                    counter += 1
                    heapq.heappush(open_heap, (tentative + self.heuristic(nxt, goal), counter, nxt))
        raise ValueError(f"Không có đường từ {start} tới {goal}")


def load_network() -> Network:
    hubs_raw = json.loads(HUBS_FILE.read_text(encoding="utf-8"))["nodes"]
    hubs = [Hub(**{k: n[k] for k in ("id", "name", "kind", "district", "lat", "lon")}) for n in hubs_raw]
    matrix = json.loads(MATRIX_FILE.read_text(encoding="utf-8"))
    if matrix["ids"] != [h.id for h in hubs]:
        raise RuntimeError("Ma trận OSRM lệch với data/hubs.json — chạy lại python data/build_matrix.py")
    return Network(hubs, matrix["duration_s"], matrix["distance_m"])
