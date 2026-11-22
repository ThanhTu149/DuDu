"""Đo khoảng cách tới thứ tự giao tối ưu (optimality gap của phần xếp tuyến).

Với ca nhỏ (12–24 đơn, 8 xe), mỗi tuyến chỉ 1–5 điểm nên có thể tìm **thứ tự giao tối ưu**
bằng vét cạn hoán vị cho đúng phân công mà Hungarian đã chọn. Từ đó tách bạch:

- **Gap xếp tuyến** = (km của heuristic − km của thứ tự tối ưu) / km tối ưu.
- Gap này đo riêng chất lượng sắp thứ tự giao (Nearest Neighbor, 2-opt, Clarke–Wright,
  thứ tự ưu tiên hạn giao), không lẫn với phần chia đơn.

Module còn có `exact_vrp()` — giải chính xác cả chia đơn + xếp tuyến cho ca ≤ 8 đơn bằng
quy hoạch động bitmask, dùng làm công cụ kiểm chứng trong `tests/test_optimal.py`. Nghiệm
tối ưu đó không có hạn giao và không có phí sử dụng xe, nên chỉ nên đọc như cận dưới cho
quãng đường, không phải "phương án vận hành tốt nhất".

Chạy báo cáo:

    python -m backend.dispatch.optimal --report
"""

from __future__ import annotations

import argparse
import statistics
from itertools import permutations
from pathlib import Path

from .assignment import STRATEGIES
from .evaluate import ROUTING_LABELS
from .network import Network, load_network
from .routing import BASE_MINUTE, plan_routes, summarize
from .scenario import build_scenario

ROOT = Path(__file__).resolve().parents[2]
MAX_EXACT_ORDERS = 8


def _open_route_km(net: Network, start_hub: str, dest_hubs: list[str]) -> float:
    """Tuyến mở: start_hub → các điểm → hết (không quay về kho)."""
    total = 0.0
    current = start_hub
    for hub_id in dest_hubs:
        total += net.dist(current, hub_id) / 1000.0
        current = hub_id
    return total


def _best_order_km(net: Network, start_hub: str, items: list[dict]) -> float:
    """Thứ tự giao ngắn nhất cho một danh sách đơn (Held–Karp, tuyến mở).

    Dùng quy hoạch động trên tập con nên chịu được tuyến tới ~16 điểm, trong khi vét cạn
    hoán vị chỉ dùng được cho tuyến ngắn. Với tuyến ≤ 6 điểm, kết quả trùng khớp vét cạn.
    """
    n = len(items)
    if n == 0:
        return 0.0
    if n > 16:
        raise ValueError(f"tuyến có {n} điểm — quá lớn để tìm thứ tự tối ưu")

    hubs = [item["dest_hub"] for item in items]
    full = (1 << n) - 1
    inf = float("inf")
    # dp[mask][last] = chi phí nhỏ nhất đi start → ... → last, đã ghé đúng tập mask
    dp = [[inf] * n for _ in range(full + 1)]
    for index in range(n):
        dp[1 << index][index] = net.dist(start_hub, hubs[index]) / 1000.0
    for mask in range(1, full + 1):
        for last in range(n):
            current = dp[mask][last]
            if current == inf or not (mask >> last & 1):
                continue
            for nxt in range(n):
                if mask >> nxt & 1:
                    continue
                candidate = current + net.dist(hubs[last], hubs[nxt]) / 1000.0
                next_mask = mask | (1 << nxt)
                if candidate < dp[next_mask][nxt]:
                    dp[next_mask][nxt] = candidate
    return min(dp[full])


def exact_vrp(net: Network, orders: list[dict], vehicles: list[dict]) -> dict:
    """Nghiệm tối ưu cho VRP nhỏ (≤ 8 đơn) bằng bitmask DP.

    Trả về {"km": float, "assignment": {vehicle_id: [order_id, ...]}, "served": int}.
    Ràng buộc: mỗi đơn phục vụ đúng một lần, tải trọng kg/lít không vượt sức chứa.
    """
    n = len(orders)
    if n > MAX_EXACT_ORDERS:
        raise ValueError(f"exact_vrp chỉ nhận tối đa {MAX_EXACT_ORDERS} đơn, nhận {n}")
    if n == 0:
        return {"km": 0.0, "assignment": {v["id"]: [] for v in vehicles}, "served": 0}

    full = (1 << n) - 1
    mask_count = full + 1

    per_vehicle: list[list[float | None]] = []
    for vehicle in vehicles:
        weight = [0.0] * mask_count
        volume = [0.0] * mask_count
        for mask in range(1, mask_count):
            low = mask & -mask
            index = low.bit_length() - 1
            previous = mask ^ low
            weight[mask] = weight[previous] + orders[index]["weight_kg"]
            volume[mask] = volume[previous] + orders[index]["volume_l"]

        costs: list[float | None] = [None] * mask_count
        for mask in range(1, mask_count):
            if weight[mask] > vehicle["capacity_kg"] * 1.001:
                continue
            if volume[mask] > vehicle["capacity_l"] * 1.001:
                continue
            indices = [i for i in range(n) if mask >> i & 1]
            best = float("inf")
            for sequence in permutations(indices):
                km = _open_route_km(net, vehicle["start_hub"], [orders[i]["dest_hub"] for i in sequence])
                if km < best:
                    best = km
            costs[mask] = best
        per_vehicle.append(costs)

    inf = float("inf")
    dp = [inf] * mask_count
    dp[0] = 0.0
    picks: list[list[int]] = []
    for vehicle_index in range(len(vehicles)):
        next_dp = list(dp)  # xe này không nhận đơn
        pick = [0] * mask_count
        for mask in range(mask_count):
            if dp[mask] == inf:
                continue
            remaining = full ^ mask
            subset = remaining
            while subset:
                cost = per_vehicle[vehicle_index][subset]
                if cost is not None and dp[mask] + cost < next_dp[mask | subset]:
                    next_dp[mask | subset] = dp[mask] + cost
                    pick[mask | subset] = subset
                subset = (subset - 1) & remaining
        picks.append(pick)
        dp = next_dp

    if dp[full] == inf:
        raise ValueError("Không có phương án khả thi với sức chứa hiện tại")

    assignment: dict[str, list[str]] = {v["id"]: [] for v in vehicles}
    mask = full
    for vehicle_index in range(len(vehicles) - 1, -1, -1):
        subset = picks[vehicle_index][mask]
        if subset:
            vehicle_id = vehicles[vehicle_index]["id"]
            assignment[vehicle_id] = [orders[i]["id"] for i in range(n) if subset >> i & 1]
            mask ^= subset

    return {"km": round(dp[full], 3), "assignment": assignment, "served": n}


def route_optimal_km(net: Network, scenario: dict, assignment: dict[str, list[dict]]) -> float:
    """Tổng km nếu mỗi tuyến được xếp thứ tự giao tối ưu (Held–Karp, tuyến ≤ 16 điểm)."""
    total = 0.0
    for vehicle in scenario["vehicles"]:
        items = assignment.get(vehicle["id"], [])
        if len(items) > 16:
            raise ValueError(f"tuyến {vehicle['id']} có {len(items)} điểm — quá lớn để tối ưu")
        total += _best_order_km(net, vehicle["start_hub"], items)
    return total


def routing_gap_rows(
    net: Network,
    cases: list[tuple[int, int]],
    seeds: list[int],
) -> dict[str, dict]:
    """Với mỗi chiến lược xếp tuyến: gap so với thứ tự tối ưu trên cùng phân công."""
    result: dict[str, dict] = {}
    for key, _label in ROUTING_LABELS:
        result[key] = {"label": _label, "kms": [], "gaps": [], "late": [], "on_time": []}

    for orders_count, vehicles_count in cases:
        for seed in seeds:
            scenario = build_scenario(net, seed=seed, n_orders=orders_count, n_vehicles=vehicles_count)
            assignment = STRATEGIES["hungarian"](net, scenario["orders"], scenario["vehicles"])
            optimal = route_optimal_km(net, scenario, assignment)
            for key, _label in ROUTING_LABELS:
                routes = plan_routes(net, scenario["vehicles"], assignment, strategy=key, start_min=BASE_MINUTE)
                summary = summarize(routes)
                result[key]["kms"].append(summary["total_km"])
                result[key]["gaps"].append((summary["total_km"] - optimal) / optimal * 100)
                result[key]["late"].append(summary["late_count"])
                result[key]["on_time"].append(summary["on_time_rate"])
    return result


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def write_report(result: dict[str, dict], cases: list[tuple[int, int]], seeds: list[int], path: Path) -> Path:
    baseline = result["random"]
    best = result["two_opt"]
    lines = [
        "# Khoảng cách tới thứ tự giao tối ưu (routing optimality gap)",
        "",
        "Sinh tự động bằng `python -m backend.dispatch.optimal --report`.",
        "",
        "## Cách đo",
        "",
        "Với mỗi ca thử (2 quy mô × 3 seed), giữ nguyên phân công đơn của Hungarian rồi so",
        "quãng đường của từng chiến lược xếp tuyến với **thứ tự giao tối ưu** tìm bằng quy",
        "hoạch động giữ nhớ (Held–Karp, tuyến mở). Công cụ đã được đối chiếu độc lập với vét",
        "cạn hoán vị trong `tests/test_optimal.py`.",
        "Gap = (km heuristic − km tối ưu)/km tối ưu.",
        "",
        "Ca thử: " + ", ".join(f"{orders} đơn/{vehicles} xe" for orders, vehicles in cases)
        + f" · seed {', '.join(str(seed) for seed in seeds)}.",
        "",
        "## Kết quả",
        "",
        "| Chiến lược xếp tuyến | Quãng đường TB (km) | Gap TB | Gap lớn nhất | Đơn trễ TB | Đúng giờ TB |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, _label in ROUTING_LABELS:
        item = result[key]
        lines.append(
            f"| {item['label']} | {_mean(item['kms']):.1f} | {_mean(item['gaps']):+.1f}% | "
            f"{max(item['gaps']):+.1f}% | {_mean(item['late']):.2f} | {_mean(item['on_time']):.1f}% |"
        )
    improvement = (1 - _mean(best["kms"]) / _mean(baseline["kms"])) * 100
    lines += [
        "",
        "## Đọc kết quả",
        "",
        f"- **NN + 2-opt** gần tối ưu nhất: gap trung bình **{_mean(best['gaps']):.1f}%**, lớn nhất",
        f"  {max(best['gaps']):.1f}% — đây là lý do 2-opt hầu như không còn gì để cải thiện khi",
        "  mỗi tuyến chỉ vài điểm.",
        f"- **Nearest Neighbor** thuần có gap {_mean(result['nearest']['gaps']):.1f}%; 2-opt kéo",
        f"  xuống {_mean(best['gaps']):.1f}% và giảm {improvement:.1f}% quãng đường so với thứ tự",
        "  nhập đơn.",
        f"- **Clarke–Wright ở cấp thứ tự giao** gap {_mean(result['savings']['gaps']):.1f}% vì nó được",
        "  thiết kế để gộp tuyến ở cấp đội xe, không phải sắp thứ tự cho một danh sách điểm có sẵn.",
        f"- **NN + 2-opt theo hạn giao** giữ gap tương đương 2-opt thuần nhưng đổi lại số đơn trễ",
        f"  trung bình {_mean(result['deadline']['late']):.2f} so với {_mean(best['late']):.2f} —",
        "  đây là cơ sở để hệ thống chọn chiến lược `deadline` làm mặc định.",
        "",
        "## Kiểm chứng công cụ",
        "",
        "`exact_vrp()` (giải chính xác cả chia đơn + xếp tuyến cho ca ≤ 8 đơn, bitmask DP) được",
        "đối chiếu với vét cạn độc lập trong `tests/test_optimal.py`; gap chia đơn chỉ nên đọc như",
        "cận dưới vì nghiệm tối ưu không có hạn giao và không có phí sử dụng xe.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Đo routing optimality gap")
    parser.add_argument("--report", action="store_true", help="ghi docs/ket-qua-toi-uu.md")
    args = parser.parse_args()

    net = load_network()
    cases = [(12, 8), (24, 8)]
    seeds = [7, 11, 21]
    result = routing_gap_rows(net, cases, seeds)
    print(f"{'chiến lược':<30}{'km TB':>8}{'gap TB':>9}{'gap max':>9}{'trễ TB':>8}{'đúng giờ':>10}")
    for key, _label in ROUTING_LABELS:
        item = result[key]
        print(f"{item['label']:<30}{_mean(item['kms']):>8.1f}{_mean(item['gaps']):>8.1f}%"
              f"{max(item['gaps']):>8.1f}%{_mean(item['late']):>8.2f}{_mean(item['on_time']):>9.1f}%")
    if args.report:
        target = write_report(result, cases, seeds, ROOT / "docs" / "ket-qua-toi-uu.md")
        print(f"\n[report] ghi {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

