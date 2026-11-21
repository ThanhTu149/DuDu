"""Chia đơn cho tài xế.

Bài toán: mỗi đơn phải về đúng một tài xế, tải trọng không vượt sức chứa, và tổng
thời gian di chuyển của đội là nhỏ nhất.

Cách làm trong dự án (hai bước, giải thích được rõ ràng):
  1. Chia lô: gom đơn thành đúng k lô cân bằng tải trọng, ưu tiên giữ đơn cùng khu
     vực nằm chung một lô (bước "bin packing" có ý thức địa lý).
  2. Ghép lô với xe: bài toán gán (assignment problem), giải bằng thuật toán Hungary.
     Ma trận chi phí = thời gian xe chạy từ điểm xuất phát tới khu vực của lô; lô nào
     vượt sức chứa của xe bị gán chi phí vô cùng để không bao giờ được chọn.

Ba chiến lược để so sánh trong báo cáo: random — greedy (xe gần nhất còn chỗ) — hungarian.
"""

from __future__ import annotations

from .network import Network

BIG = 1e9


def hungarian(cost: list[list[float]]) -> list[int]:
    """Thuật toán Hungary (Jonker-Volgenant, O(n^3)) cho ma trận chữ nhật.

    Trả về danh sách `match` với match[i] = chỉ số cột ghép với hàng i.
    """
    rows, cols = len(cost), len(cost[0])
    size = max(rows, cols)
    a = [[cost[i][j] if i < rows and j < cols else BIG for j in range(size)] for i in range(size)]

    inf = float("inf")
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)

    for i in range(1, size + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = inf
            j1 = -1
            for j in range(1, size + 1):
                if used[j]:
                    continue
                cur = a[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(size + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    match = [-1] * rows
    for j in range(1, size + 1):
        if p[j] != 0 and p[j] <= rows and j <= cols:
            match[p[j] - 1] = j - 1
    return match


def _load(orders: list[dict]) -> tuple[float, float]:
    return sum(o["weight_kg"] for o in orders), sum(o["volume_l"] for o in orders)


def partition_batches(net: Network, orders: list[dict], vehicles: list[dict]) -> list[list[dict]]:
    """Chia đơn thành các lô, mỗi lô "vừa" một xe trong đội.

    Cách làm: quét đơn theo một vòng cung quanh trọng tâm thành phố (đơn gần nhau về
    địa lý nằm cạnh nhau), rồi lần lượt đổ vào lô của từng xe — xe sức chứa lớn nhất
    được đổ trước. Một lô đóng lại khi (a) thêm đơn nữa là vượt sức chứa của xe đó, hoặc
    (b) đã đạt khoảng 85% định mức chia theo tỉ lệ sức chứa.
    """
    if not orders or not vehicles:
        return []

    fleet = sorted(vehicles, key=lambda v: (v["capacity_kg"], v["capacity_l"]), reverse=True)
    total_kg = sum(o["weight_kg"] for o in orders)
    total_l = sum(o["volume_l"] for o in orders)
    fleet_kg = sum(v["capacity_kg"] for v in fleet)
    fleet_l = sum(v["capacity_l"] for v in fleet)

    by_hub: dict[str, list[dict]] = {}
    for order in orders:
        by_hub.setdefault(order["dest_hub"], []).append(order)

    hubs = list(by_hub)
    if len(hubs) > 1:
        import math

        lat0 = sum(net.hub(h).lat for h in hubs) / len(hubs)
        lon0 = sum(net.hub(h).lon for h in hubs) / len(hubs)
        hubs.sort(key=lambda h: math.atan2(net.hub(h).lat - lat0, net.hub(h).lon - lon0))

    sweep: list[dict] = []
    for hub_id in hubs:
        sweep.extend(sorted(by_hub[hub_id], key=lambda o: -o["weight_kg"]))

    batches: list[list[dict]] = [[]]
    loads: list[list[float]] = [[0.0, 0.0]]

    def vehicle_for(index: int) -> dict:
        return fleet[min(index, len(fleet) - 1)]

    for order in sweep:
        index = len(batches) - 1
        vehicle = vehicle_for(index)
        target_kg = total_kg * vehicle["capacity_kg"] / fleet_kg
        target_l = total_l * vehicle["capacity_l"] / fleet_l
        cur_kg, cur_l = loads[index]

        fits = cur_kg + order["weight_kg"] <= vehicle["capacity_kg"] and cur_l + order["volume_l"] <= vehicle["capacity_l"]
        balanced = cur_kg >= target_kg * 0.85 or cur_l >= target_l * 0.85
        if batches[index] and (not fits or balanced) and len(batches) < len(fleet):
            batches.append([])
            loads.append([0.0, 0.0])
            index += 1
            cur_kg, cur_l = 0.0, 0.0
        batches[index].append(order)
        loads[index] = [cur_kg + order["weight_kg"], cur_l + order["volume_l"]]

    # Đơn còn dư (nhiều đơn hơn sức chứa dự kiến): dồn vào lô còn nhiều chỗ nhất
    return [b for b in batches if b]


def _vehicle_penalty(vehicle: dict, batch: list[dict], net: Network) -> float:
    weight, volume = _load(batch)
    penalty = 0.0
    if weight > vehicle["capacity_kg"] * 1.001 or volume > vehicle["capacity_l"] * 1.001:
        penalty += BIG
    # Đơn hoả tốc không giao bằng xe tải lớn (kẹt xe, khó dừng đỗ)
    if vehicle["kind"] == "xe_tai" and any(o["priority"] == "hoa_toc" for o in batch):
        penalty += 25.0
    return penalty


def _batch_anchor(batch: list[dict]) -> str:
    """Nút đại diện của lô: nút xuất hiện nhiều đơn nhất."""
    counts: dict[str, int] = {}
    for order in batch:
        counts[order["dest_hub"]] = counts.get(order["dest_hub"], 0) + 1
    return max(counts, key=counts.get)


def _loads(assignment: dict[str, list[dict]], vehicles: list[dict]) -> dict[str, tuple[float, float]]:
    return {v["id"]: _load(assignment.get(v["id"], [])) for v in vehicles}


def repair_capacity(
    assignment: dict[str, list[dict]], vehicles: list[dict], max_moves: int = 500
) -> tuple[dict[str, list[dict]], int]:
    """Sửa lô vượt tải: chuyển dần đơn nhỏ nhất sang xe còn chỗ.

    Bước gán bằng Hungary không nhìn thấy ràng buộc tải trọng theo từng xe, nên sau khi
    gán cần một vòng sửa. Số lần chuyển được ghi lại để báo cáo ("đã sửa n lô").
    """
    vehicles_by_id = {v["id"]: v for v in vehicles}
    moves = 0
    for _ in range(max_moves):
        loads = _loads(assignment, vehicles)
        over = [
            vid for vid, (kg, litre) in loads.items()
            if kg > vehicles_by_id[vid]["capacity_kg"] * 1.001 or litre > vehicles_by_id[vid]["capacity_l"] * 1.001
        ]
        if not over:
            break
        source = max(over, key=lambda vid: loads[vid][0] / max(vehicles_by_id[vid]["capacity_kg"], 1e-6))
        orders = assignment[source]
        if not orders:
            break
        order = min(orders, key=lambda o: (o["weight_kg"], o["volume_l"]))
        targets = [
            vid for vid in assignment
            if vid != source
            and loads[vid][0] + order["weight_kg"] <= vehicles_by_id[vid]["capacity_kg"] * 1.001
            and loads[vid][1] + order["volume_l"] <= vehicles_by_id[vid]["capacity_l"] * 1.001
        ]
        if not targets:
            break
        target = max(targets, key=lambda vid: vehicles_by_id[vid]["capacity_kg"] - loads[vid][0])
        orders.remove(order)
        assignment[target].append(order)
        moves += 1
    return assignment, moves


def assign_hungarian(net: Network, orders: list[dict], vehicles: list[dict]) -> dict[str, list[dict]]:
    if not orders or not vehicles:
        return {v["id"]: [] for v in vehicles}
    batches = partition_batches(net, orders, vehicles)

    cost = []
    for batch in batches:
        anchor = _batch_anchor(batch)
        row = []
        for vehicle in vehicles:
            row.append(net.dur_min(vehicle["start_hub"], anchor) + _vehicle_penalty(vehicle, batch, net))
        cost.append(row)

    match = hungarian(cost)
    result: dict[str, list[dict]] = {v["id"]: [] for v in vehicles}
    for batch_index, vehicle_index in enumerate(match):
        if vehicle_index < 0 or batch_index >= len(batches):
            continue
        result[vehicles[vehicle_index]["id"]].extend(batches[batch_index])
    return repair_capacity(result, vehicles)[0]


def assign_greedy(net: Network, orders: list[dict], vehicles: list[dict]) -> dict[str, list[dict]]:
    """Baseline: mỗi đơn (theo ưu tiên) về xe gần nhất còn đủ tải."""
    result: dict[str, list[dict]] = {v["id"]: [] for v in vehicles}
    remaining = {v["id"]: (v["capacity_kg"], v["capacity_l"]) for v in vehicles}
    ordered = sorted(orders, key=lambda o: (o["priority"] != "hoa_toc", -o["weight_kg"]))

    for order in ordered:
        candidates = [
            v for v in vehicles
            if remaining[v["id"]][0] >= order["weight_kg"] and remaining[v["id"]][1] >= order["volume_l"]
        ] or list(vehicles)
        vehicle = min(candidates, key=lambda v: net.dur(v["start_hub"], order["dest_hub"]))
        result[vehicle["id"]].append(order)
        kg, litre = remaining[vehicle["id"]]
        remaining[vehicle["id"]] = (kg - order["weight_kg"], litre - order["volume_l"])
    return repair_capacity(result, vehicles)[0]


def assign_random(net: Network, orders: list[dict], vehicles: list[dict], seed: int = 0) -> dict[str, list[dict]]:
    """Baseline: chia vòng tròn theo thứ tự đơn — như điều phối thủ công."""
    import random

    rng = random.Random(seed)
    shuffled = list(orders)
    rng.shuffle(shuffled)
    result: dict[str, list[dict]] = {v["id"]: [] for v in vehicles}
    for index, order in enumerate(shuffled):
        result[vehicles[index % len(vehicles)]["id"]].append(order)
    return result


def assign_savings(net: Network, orders: list[dict], vehicles: list[dict]) -> dict[str, list[dict]]:
    """Clarke–Wright ở cấp đội xe: tự gộp đơn thành tuyến, không cần bước chia lô trước.

    Mỗi tuyến bị chặn bởi hạn mức tải trung bình của đội (`tổng sức chứa / số xe`), nên
    số tuyến sinh ra xấp xỉ số xe. Sau đó mỗi tuyến được gán cho xe nhỏ nhất còn đủ sức
    chứa; tuyến nào không vừa thì đẩy sang xe lớn hơn, cuối cùng vẫn qua vòng sửa tải.
    """
    if not orders or not vehicles:
        return {v["id"]: [] for v in vehicles}

    fleet_kg = sum(v["capacity_kg"] for v in vehicles) / len(vehicles)
    fleet_l = sum(v["capacity_l"] for v in vehicles) / len(vehicles)
    limit_kg, limit_l = fleet_kg * 0.92, fleet_l * 0.92

    n = len(orders)
    start_hubs = [v["start_hub"] for v in vehicles]
    # Khoảng cách từ "kho chung" (dùng nút khởi hành gần nhất) tới từng đơn
    depot = start_hubs[0]
    to_depot = [net.dur_min(depot, o["dest_hub"]) for o in orders]
    between = [
        [net.dur_min(orders[i]["dest_hub"], orders[j]["dest_hub"]) for j in range(n)]
        for i in range(n)
    ]

    savings = [
        (to_depot[i] + to_depot[j] - between[i][j], i, j)
        for i in range(n)
        for j in range(n)
        if i != j
    ]
    savings.sort(reverse=True)

    route_of = list(range(n))
    routes: dict[int, list[int]] = {i: [i] for i in range(n)}
    load = {i: (orders[i]["weight_kg"], orders[i]["volume_l"]) for i in range(n)}

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
        kg = load[left][0] + load[right][0]
        litre = load[left][1] + load[right][1]
        if kg > limit_kg or litre > limit_l:
            continue
        routes[left] = merged
        load[left] = (kg, litre)
        for node in merged:
            route_of[node] = left
        del routes[right]

    ordered_routes = sorted(routes.values(), key=lambda r: -sum(orders[k]["weight_kg"] for k in r))
    result: dict[str, list[dict]] = {v["id"]: [] for v in vehicles}
    remaining_vehicles = sorted(vehicles, key=lambda v: (v["capacity_kg"], v["capacity_l"]))
    for route in ordered_routes:
        kg = sum(orders[k]["weight_kg"] for k in route)
        litre = sum(orders[k]["volume_l"] for k in route)
        fit = [v for v in remaining_vehicles if v["capacity_kg"] >= kg and v["capacity_l"] >= litre]
        vehicle = fit[0] if fit else remaining_vehicles[-1]
        result[vehicle["id"]].extend(orders[k] for k in route)
        remaining_vehicles.remove(vehicle)
        if not remaining_vehicles:
            remaining_vehicles = sorted(vehicles, key=lambda v: (v["capacity_kg"], v["capacity_l"]))

    return repair_capacity(result, vehicles)[0]


STRATEGIES = {
    "random": assign_random,
    "greedy": assign_greedy,
    "savings": assign_savings,
    "hungarian": assign_hungarian,
}
