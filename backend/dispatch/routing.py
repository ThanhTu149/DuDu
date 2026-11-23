"""Xếp tuyến cho từng tài xế: Nearest Neighbor, cải tiến 2-opt, và lịch giao.

Đầu vào là danh sách đơn đã chia cho từng xe (xem assignment.py). Đầu ra là một Route
có thứ tự điểm giao, ETA từng điểm, tổng quãng đường và cờ trễ hẹn.

Có hai hàm mục tiêu để 2-opt tối ưu, và đây cũng là một thí nghiệm của báo cáo:

  - `distance`: chỉ giảm tổng thời gian di chuyển. Tuyến ngắn nhất nhưng dễ trễ đơn gấp.
  - `deadline`: thời gian di chuyển + phạt mỗi phút trễ hẹn. Tuyến dài hơn một chút
    nhưng giữ được cam kết với khách.
"""

from __future__ import annotations

from functools import lru_cache

from dataclasses import dataclass, field

from .network import Network

BASE_MINUTE = 8 * 60  # 08:00
DEFAULT_LATE_PENALTY = 8.0  # mỗi phút trễ tính như 8 phút chạy xe


@dataclass
class Stop:
    order_id: str
    code: str
    hub_id: str
    lat: float
    lon: float
    arrive_min: float          # phút kể từ 00:00
    service_min: float
    late: bool
    late_min: float
    priority: str
    weight_kg: float


@dataclass
class Route:
    vehicle_id: str
    plate: str
    driver: str
    kind: str
    label: str
    stops: list[Stop] = field(default_factory=list)
    legs: list[dict] = field(default_factory=list)
    total_min: float = 0.0
    total_km: float = 0.0
    load_kg: float = 0.0
    load_l: float = 0.0
    late_count: int = 0
    late_minutes: float = 0.0
    over_capacity: bool = False

    def as_dict(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "plate": self.plate,
            "driver": self.driver,
            "kind": self.kind,
            "label": self.label,
            "stops": [s.__dict__ for s in self.stops],
            "legs": self.legs,
            "total_min": round(self.total_min, 1),
            "total_km": round(self.total_km, 2),
            "load_kg": round(self.load_kg, 1),
            "load_l": round(self.load_l, 1),
            "late_count": self.late_count,
            "late_minutes": round(self.late_minutes, 1),
            "over_capacity": self.over_capacity,
        }


@lru_cache(maxsize=4096)
def _travel(net: Network, a: str, b: str, speed_factor: float) -> tuple[float, float]:
    """(phút, km) giữa 2 nút, đã nhân hệ số chậm của loại xe.

    Có cache vì 2-opt gọi hàm này hàng triệu lần cho cùng một cặp nút — kết quả trả về
    hoàn toàn giống bản không cache (cùng phép tính, cache chỉ bỏ lặp lại).
    """
    return net.dur_min(a, b) * speed_factor, net.dist(a, b) / 1000.0


def route_length(net: Network, start: str, sequence: list[str], speed_factor: float) -> float:
    """Tổng thời gian di chuyển (phút) của một thứ tự giao, chưa tính phục vụ."""
    total = 0.0
    current = start
    for nxt in sequence:
        total += _travel(net, current, nxt, speed_factor)[0]
        current = nxt
    return total


def sequence_score(
    net: Network,
    start: str,
    sequence: list[tuple[str, str]],
    speed_factor: float,
    orders_by_id: dict[str, dict] | None = None,
    late_penalty: float = 0.0,
    start_min: float = BASE_MINUTE,
    eta_model=None,
) -> float:
    """Chi phí của một thứ tự giao: thời gian chạy + (tuỳ chọn) phạt trễ hẹn."""
    clock = start_min
    current = start
    travel = 0.0
    lateness = 0.0
    for order_id, hub_id in sequence:
        minutes, _ = _travel(net, current, hub_id, speed_factor)
        if eta_model is not None:
            # hour_factor nhận giờ trong ngày (0–23), không phải số phút kể từ 00:00
            minutes *= eta_model.hour_factor(int(clock) // 60 % 24)
        clock += minutes
        travel += minutes
        if orders_by_id is not None and late_penalty:
            order = orders_by_id[order_id]
            due = start_min + order["promised_min"]
            lateness += max(0.0, clock - due)
        clock += orders_by_id[order_id]["service_min"] if orders_by_id else 0.0
        current = hub_id
    return travel + late_penalty * lateness


def nearest_neighbor(net: Network, start: str, dests: list[tuple[str, str]], speed_factor: float) -> list[tuple[str, str]]:
    """Tham lam: luôn đi tới điểm gần nhất còn lại.

    dests: [(order_id, hub_id)]. Trả về cùng định dạng, đã sắp thứ tự.
    """
    remaining = list(dests)
    ordered: list[tuple[str, str]] = []
    current = start
    while remaining:
        best = min(remaining, key=lambda item: net.dur(current, item[1]))
        ordered.append(best)
        remaining.remove(best)
        current = best[1]
    return ordered


def clarke_wright(net: Network, start: str, dests: list[tuple[str, str]], speed_factor: float) -> list[tuple[str, str]]:
    """Tiết kiệm Clarke–Wright: gộp hai tuyến nếu tiết kiệm được quãng đường.

    Ý tưởng: bắt đầu mỗi điểm là một tuyến riêng, tính tiết kiệm khi nối i–j
    `s = d(0,i) + d(0,j) − d(i,j)`, xét từ tiết kiệm lớn nhất xuống, nối được thì nối.
    Khác Nearest Neighbor ở chỗ nó nhìn toàn cục ngay từ đầu thay vì đi từng bước tham lam.

    Trả về thứ tự giao của một xe (mỗi xe được gọi riêng, xem `schedule_route`).
    """
    n = len(dests)
    if n <= 2:
        return list(dests)

    hubs = [hub for _, hub in dests]
    to_depot = [net.dur_min(start, hub) * speed_factor for hub in hubs]
    between = [[net.dur_min(hubs[i], hubs[j]) * speed_factor for j in range(n)] for i in range(n)]

    savings = [
        (to_depot[i] + to_depot[j] - between[i][j], i, j)
        for i in range(n)
        for j in range(n)
        if i != j
    ]
    savings.sort(reverse=True)

    route_of = list(range(n))
    routes: dict[int, list[int]] = {i: [i] for i in range(n)}

    for value, i, j in savings:
        if value <= 1e-9:
            break
        left, right = route_of[i], route_of[j]
        if left == right:
            continue
        a, b = routes[left], routes[right]
        if a[-1] == i and b[0] == j:
            merged = a + b
        elif a[0] == i and b[-1] == j:
            merged = b + a
        elif a[-1] == i and b[-1] == j:
            merged = a + b[::-1]
        elif a[0] == i and b[0] == j:
            merged = a[::-1] + b
        else:
            continue
        routes[left] = merged
        for node in merged:
            route_of[node] = left
        del routes[right]

    # Một xe có thể sinh nhiều "tuyến con" khi gộp bị chặn; nối chúng lại thành một
    # thứ tự giao duy nhất (đoạn nối giữa hai tuyến con là bước nhảy, 2-opt sẽ dọn sau).
    order: list[int] = []
    for route in sorted(routes.values(), key=len, reverse=True):
        order.extend(route)
    return [dests[index] for index in order]


def two_opt(
    net: Network,
    start: str,
    sequence: list[tuple[str, str]],
    speed_factor: float,
    orders_by_id: dict[str, dict] | None = None,
    late_penalty: float = 0.0,
    start_min: float = BASE_MINUTE,
    max_pass: int = 40,
    eta_model=None,
) -> tuple[list[tuple[str, str]], int]:
    """Cải tiến 2-opt: đảo một đoạn nếu chi phí giảm. Trả về (thứ tự mới, số lần cải thiện).

    Để chạy được ca 200 đơn (~25 điểm/tuyến), chi phí từng phương án được tính bằng
    các mảng cục bộ (ma trận chặng, giờ hẹn, thời gian phục vụ) thay vì gọi lại
    `sequence_score` cho mỗi lần đảo — cùng công thức, cùng thứ tự cộng, nên kết quả
    giống hệt bản cũ (đã đối chiếu bằng test hồi quy).
    """
    size = len(sequence)
    if size < 2:
        return list(sequence), 0

    hubs = [start] + [hub_id for _order_id, hub_id in sequence]
    # leg[a][b] = số phút từ hubs[a] tới điểm b (điểm 0 là sequence[0])
    leg = [[0.0] * size for _ in range(size + 1)]
    for a in range(size + 1):
        row = leg[a]
        hub_a = hubs[a]
        for b in range(size):
            row[b] = net.dur_min(hub_a, hubs[b + 1]) * speed_factor

    due = [0.0] * size
    service = [0.0] * size
    if orders_by_id is not None:
        for index, (order_id, _hub) in enumerate(sequence):
            order = orders_by_id[order_id]
            due[index] = start_min + order["promised_min"]
            service[index] = order["service_min"]
    multipliers = None
    if eta_model is not None:
        # Tái hiện đúng cách sequence_score cũ gọi eta_model.hour_factor(clock)
        multipliers = [eta_model.hour_factor(hour) for hour in range(24)]
    penalise = bool(orders_by_id is not None and late_penalty)

    def score(order_indices: list[int]) -> float:
        clock = start_min
        travel = 0.0
        lateness = 0.0
        previous = 0
        for index in order_indices:
            minutes = leg[previous][index]
            if multipliers is not None:
                minutes *= multipliers[int(clock) // 60 % 24]
            clock += minutes
            travel += minutes
            if penalise:
                late = clock - due[index]
                if late > 0:
                    lateness += late
            clock += service[index]
            previous = index + 1  # hubs[index + 1] là nút của điểm vừa ghé
        return travel + late_penalty * lateness

    order_indices = list(range(size))
    best_indices = list(order_indices)
    best_cost = score(best_indices)
    improvements = 0
    for _ in range(max_pass):
        improved = False
        for i in range(size - 1):
            for j in range(i + 1, size):
                candidate = best_indices[:i] + best_indices[i : j + 1][::-1] + best_indices[j + 1 :]
                cost = score(candidate)
                if cost + 1e-6 < best_cost:
                    best_indices, best_cost, improved = candidate, cost, True
                    improvements += 1
        if not improved:
            break
    return [sequence[index] for index in best_indices], improvements


def schedule_route(
    net: Network,
    vehicle: dict,
    orders: list[dict],
    strategy: str = "deadline",
    start_min: float = BASE_MINUTE,
    late_penalty: float = DEFAULT_LATE_PENALTY,
    eta_model=None,
) -> Route:
    """Dựng Route hoàn chỉnh: thứ tự giao, ETA, tổng km, cờ trễ.

    `eta_model` (tuỳ chọn) nhân thêm hệ số ùn tắc theo giờ lên thời gian free-flow của
    OSRM — xem ml/eta_model.py.
    """
    speed_factor = float(vehicle.get("speed_factor", 1.0))
    start_hub = vehicle["start_hub"]
    dests = [(o["id"], o["dest_hub"]) for o in orders]
    by_id = {o["id"]: o for o in orders}

    if not dests:
        return Route(vehicle_id=vehicle["id"], plate=vehicle["plate"], driver=vehicle["driver"],
                     kind=vehicle["kind"], label=vehicle["label"])

    if strategy == "random":
        sequence = list(dests)
    elif strategy == "nearest":
        sequence = nearest_neighbor(net, start_hub, dests, speed_factor)
    elif strategy == "savings":
        sequence = clarke_wright(net, start_hub, dests, speed_factor)
    elif strategy == "savings_2opt":
        sequence, _ = two_opt(net, start_hub, clarke_wright(net, start_hub, dests, speed_factor), speed_factor)
    elif strategy == "two_opt":
        sequence, _ = two_opt(net, start_hub, nearest_neighbor(net, start_hub, dests, speed_factor), speed_factor)
    else:  # "deadline"
        sequence, _ = two_opt(
            net,
            start_hub,
            nearest_neighbor(net, start_hub, dests, speed_factor),
            speed_factor,
            orders_by_id=by_id,
            late_penalty=late_penalty,
            start_min=start_min,
            eta_model=eta_model,
        )

    route = Route(vehicle_id=vehicle["id"], plate=vehicle["plate"], driver=vehicle["driver"],
                  kind=vehicle["kind"], label=vehicle["label"])

    clock = start_min
    current = start_hub
    for order_id, hub_id in sequence:
        order = by_id[order_id]
        minutes, km = _travel(net, current, hub_id, speed_factor)
        if eta_model is not None:
            # hour_factor nhận giờ trong ngày (0–23), không phải số phút kể từ 00:00
            minutes *= eta_model.hour_factor(int(clock) // 60 % 24)
        route.legs.append({
            "from": current,
            "to": hub_id,
            "min": round(minutes, 1),
            "km": round(km, 2),
            "order_id": order_id,
        })
        clock += minutes
        route.total_min += minutes
        route.total_km += km
        route.load_kg += order["weight_kg"]
        route.load_l += order["volume_l"]

        due = start_min + order["promised_min"]
        late_min = max(0.0, clock - due)
        route.stops.append(Stop(
            order_id=order_id,
            code=order["code"],
            hub_id=hub_id,
            lat=order["lat"],
            lon=order["lon"],
            arrive_min=round(clock, 1),
            service_min=order["service_min"],
            late=late_min > 0.5,
            late_min=round(late_min, 1),
            priority=order["priority"],
            weight_kg=order["weight_kg"],
        ))
        if late_min > 0.5:
            route.late_count += 1
            route.late_minutes += late_min
        clock += order["service_min"]
        current = hub_id

    route.total_min += sum(o["service_min"] for o in orders)
    route.over_capacity = route.load_kg > vehicle["capacity_kg"] * 1.001 or route.load_l > vehicle["capacity_l"] * 1.001
    return route


def plan_routes(
    net: Network,
    vehicles: list[dict],
    assignment: dict[str, list[dict]],
    strategy: str = "deadline",
    start_min: float = BASE_MINUTE,
    eta_model=None,
    time_multiplier: float = 1.0,
) -> list[Route]:
    """Lập tuyến cho cả đội.

    `time_multiplier` mô phỏng một sự cố làm toàn bộ lưu thông chậm lại (kẹt xe diện rộng,
    mưa lớn): thời gian di chuyển nhân lên, quãng đường không đổi.
    """
    fleet = (
        vehicles if abs(time_multiplier - 1.0) < 1e-9
        else [{**v, "speed_factor": v.get("speed_factor", 1.0) * time_multiplier} for v in vehicles]
    )
    return [
        schedule_route(net, vehicle, assignment.get(vehicle["id"], []), strategy, start_min, eta_model=eta_model)
        for vehicle in fleet
    ]


def summarize(routes: list[Route]) -> dict:
    total_km = sum(r.total_km for r in routes)
    total_min = sum(r.total_min for r in routes)
    late = sum(r.late_count for r in routes)
    late_minutes = sum(r.late_minutes for r in routes)
    over = sum(1 for r in routes if r.over_capacity)
    served = sum(len(r.stops) for r in routes)
    return {
        "vehicles_used": sum(1 for r in routes if r.stops),
        "orders": served,
        "total_km": round(total_km, 2),
        "total_min": round(total_min, 1),
        "avg_min_per_stop": round(total_min / served, 1) if served else 0.0,
        "late_count": late,
        "late_minutes": round(late_minutes, 1),
        "on_time_rate": round((served - late) / served * 100, 1) if served else 0.0,
        "over_capacity_routes": over,
    }


def clock_label(minutes_from_midnight: float) -> str:
    hour = int(minutes_from_midnight // 60) % 24
    minute = int(round(minutes_from_midnight % 60))
    if minute == 60:
        hour, minute = (hour + 1) % 24, 0
    return f"{hour:02d}:{minute:02d}"

