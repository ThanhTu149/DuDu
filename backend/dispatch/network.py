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

    def astar(
        self,
        start: str,
        goal: str,
        blocked: set[str] | None = None,
        blocked_edges: set[frozenset[str]] | None = None,
    ) -> tuple[list[str], float]:
        """A* trên đồ thị đầy đủ. Trả về (đường đi, chi phí giây).

        `blocked` là các nút không được đi qua (trừ điểm đầu/cuối); `blocked_edges` là
        các cặp nút bị cấm đi thẳng — hai tham số này dùng khi mô phỏng kẹt xe/ngập:
        chặng nào rơi vào vùng chặn thì A* phải tìm đường vòng qua nút khác.
        """
        import heapq

        blocked = blocked or set()
        banned = {frozenset(edge) for edge in (blocked_edges or set())}
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
                if nxt == current or nxt in visited:
                    continue
                if nxt in blocked and nxt != goal:
                    continue
                if frozenset((current, nxt)) in banned:
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


CITY_CENTER = (10.7769, 106.7009)   # Nhà thờ Đức Bà — tâm vùng kẹt xe mô phỏng


def hubs_within(net: "Network", radius_km: float, center: tuple[float, float] = CITY_CENTER) -> list[str]:
    """Các nút nằm trong bán kính `radius_km` quanh tâm (dùng cho vùng kẹt xe)."""
    return [
        hub_id for hub_id in net.order
        if haversine_km(center, net.hubs[hub_id]) <= radius_km
    ]


def congestion_edges(net: "Network", radius_km: float = 4.5) -> set[frozenset[str]]:
    """Các chặng đi thẳng xuyên qua vùng kẹt: hai đầu đều nằm trong bán kính.

    Khi có sự cố kẹt xe, những chặng này bị coi là ``kẹt`` — xe phải vòng ra vành đai
    thay vì đi xuyên qua, đúng cách một điều độ viên thật tránh ùn tắc.
    """
    inside = hubs_within(net, radius_km)
    return {
        frozenset((a, b))
        for index, a in enumerate(inside)
        for b in inside[index + 1:]
    }


class RoutingView:
    """Lớp bọc :class:`Network`: chặng nào bị chặn thì dùng A* tìm đường vòng.

    Các module xếp tuyến và kiểm tra luật chỉ gọi ``dur`` / ``dist`` / ``dur_min`` nên
    chỉ cần truyền view này vào là toàn bộ phép tính dùng chi phí đường vòng, không phải
    sửa thuật toán.
    """

    def __init__(self, base: Network, blocked_edges: set[frozenset[str]] | None = None) -> None:
        self.base = base
        self.blocked_edges = set(blocked_edges or ())
        self.hubs = base.hubs
        self.order = base.order
        self.index = base.index
        self.duration = base.duration
        self.distance = base.distance
        self.detours: list[dict] = []
        self._cache: dict[tuple[str, str], tuple[float, float]] = {}

    def _leg(self, a: str, b: str) -> tuple[float, float]:
        key = (a, b)
        if key in self._cache:
            return self._cache[key]
        if a == b:
            result = (0.0, 0.0)
        elif frozenset((a, b)) in self.blocked_edges:
            path, seconds = self.base.astar(a, b, blocked_edges=self.blocked_edges)
            meters = sum(self.base.dist(p, q) for p, q in zip(path, path[1:]))
            self.detours.append({
                "from": a, "to": b, "path": path,
                "km": round(meters / 1000.0, 2),
                "extra_km": round((meters - self.base.dist(a, b)) / 1000.0, 2),
            })
            result = (seconds, meters)
        else:
            result = (self.base.dur(a, b), self.base.dist(a, b))
        self._cache[key] = result
        return result

    # -- giao diện giống Network -----------------------------------------
    def dur(self, a: str, b: str) -> float:
        return float(self._leg(a, b)[0])

    def dist(self, a: str, b: str) -> float:
        return float(self._leg(a, b)[1])

    def dur_min(self, a: str, b: str) -> float:
        return self.dur(a, b) / 60.0

    def hub(self, hub_id: str) -> Hub:
        return self.base.hub(hub_id)

    def heuristic(self, a: str, b: str) -> float:
        return self.base.heuristic(a, b)

    def summary(self, legs: list[tuple[str, str]] | None = None) -> dict:
        """Thống kê các chặng A* phải đi vòng.

        Nếu truyền `legs` (các cặp nút thực sự nằm trên tuyến cuối), chỉ tính những chặng
        đó — tránh trường hợp thuật toán thử nhiều phương án (2-opt tính trước ma trận)
        làm thống kê "đi vòng" bị phồng lên dù tuyến cuối không dùng các chặng ấy.
        """
        items = self.detours
        if legs is not None:
            used = {frozenset(pair) for pair in legs if pair[0] != pair[1]}
            items = [item for item in self.detours if frozenset((item["from"], item["to"])) in used]
        return {
            "detour_legs": len(items),
            "extra_km": round(sum(item["extra_km"] for item in items), 2),
            "paths": items[:6],
        }
