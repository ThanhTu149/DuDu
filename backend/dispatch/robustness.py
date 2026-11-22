"""Độ bền vững của bộ điều phối: nhiều seed, so sánh chiến lược xếp tuyến, độ nhạy tham số.

Sinh báo cáo (dùng cho chương đánh giá):

    python -m backend.dispatch.robustness --report

Nội dung:

1. **30 seed** — cùng cấu hình (48 đơn, 8 xe): trung bình/độ lệch chuẩn của quãng đường,
   thời gian, số đơn trễ, vi phạm… để tránh kết luận dựa trên một kịch bản may mắn.
2. **So sánh 6 chiến lược xếp tuyến** trên cùng 30 seed, cùng phân công Hungarian.
3. **Độ nhạy `max_rounds`** — số vòng sửa vi phạm của tác tử.
4. **Độ nhạy bán kính vùng ùn tắc** — 2 / 3 / 4,5 / 6 / 8 km (mặc định 4,5 km, multiplier
   1,4 giữ nguyên); đo quãng đường, số trễ, vi phạm và quãng đường đi vòng do A*.
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import backend.dispatch.agent as agent_module
from .agent import DispatcherAgent
from .assignment import STRATEGIES
from .evaluate import ROUTING_LABELS
from .network import Network, load_network
from .routing import BASE_MINUTE, plan_routes, summarize
from .scenario import build_scenario

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEEDS = list(range(1, 31))
SENSITIVITY_SEEDS = [7, 11, 21, 31, 41]
RADIUS_SEEDS = [7, 11, 21]


def _agg(values: list[float]) -> dict:
    return {
        "mean": statistics.fmean(values) if values else 0.0,
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
    }


def seed_rows(net: Network, seeds: list[int], orders: int = 48, vehicles: int = 8) -> list[dict]:
    rows: list[dict] = []
    for seed in seeds:
        scenario = build_scenario(net, seed=seed, n_orders=orders, n_vehicles=vehicles)
        metrics = DispatcherAgent(net, scenario["vehicles"], scenario["orders"]).plan()["metrics"]
        rows.append({
            "seed": seed,
            "km": metrics["total_km"],
            "min": metrics["total_min"],
            "late": metrics["late_count"],
            "late_min": metrics["late_minutes"],
            "on_time": metrics["on_time_rate"],
            "violations": metrics["violations"],
            "blocked": metrics["blocked"],
            "over": metrics["over_capacity_routes"],
        })
    return rows


def routing_aggregate(net: Network, seeds: list[int], orders: int = 48, vehicles: int = 8) -> dict[str, dict]:
    """6 chiến lược xếp tuyến trên cùng phân công Hungarian, tổng hợp qua nhiều seed."""
    result: dict[str, dict] = {}
    samples = {
        key: {"km": [], "late": [], "on_time": [], "late_min": []}
        for key, _label in ROUTING_LABELS
    }
    for seed in seeds:
        scenario = build_scenario(net, seed=seed, n_orders=orders, n_vehicles=vehicles)
        assignment = STRATEGIES["hungarian"](net, scenario["orders"], scenario["vehicles"])
        for key, _label in ROUTING_LABELS:
            routes = plan_routes(net, scenario["vehicles"], assignment, strategy=key, start_min=BASE_MINUTE)
            summary = summarize(routes)
            samples[key]["km"].append(summary["total_km"])
            samples[key]["late"].append(summary["late_count"])
            samples[key]["late_min"].append(summary["late_minutes"])
            samples[key]["on_time"].append(summary["on_time_rate"])
    for key, label in ROUTING_LABELS:
        item = samples[key]
        result[key] = {
            "label": label,
            "km": _agg(item["km"]),
            "late": _agg(item["late"]),
            "late_min": _agg(item["late_min"]),
            "on_time": _agg(item["on_time"]),
        }
    return result


def rounds_sensitivity(net: Network, seeds: list[int], rounds_list: tuple[int, ...] = (0, 1, 2, 4, 6)) -> list[dict]:
    rows: list[dict] = []
    for rounds in rounds_list:
        km: list[float] = []
        late: list[float] = []
        violations: list[float] = []
        blocked: list[float] = []
        for seed in seeds:
            scenario = build_scenario(net, seed=seed, n_orders=48, n_vehicles=8)
            agent = DispatcherAgent(net, scenario["vehicles"], scenario["orders"], max_rounds=rounds)
            metrics = agent.plan()["metrics"]
            km.append(metrics["total_km"])
            late.append(metrics["late_count"])
            violations.append(metrics["violations"])
            blocked.append(metrics["blocked"])
        rows.append({
            "rounds": rounds,
            "km": statistics.fmean(km),
            "late": statistics.fmean(late),
            "violations": statistics.fmean(violations),
            "blocked": statistics.fmean(blocked),
        })
    return rows


def radius_sensitivity(net: Network, seeds: list[int], radii: tuple[float, ...] = (2.0, 3.0, 4.5, 6.0, 8.0)) -> list[dict]:
    """Vá tạm hai hàm tính vùng ùn tắc để thay đổi bán kính (mặc định hard-code 4,5 km)."""
    original_congestion = agent_module.congestion_edges
    original_hubs = agent_module.hubs_within
    rows: list[dict] = []
    try:
        for radius in radii:
            agent_module.congestion_edges = (
                lambda net_, radius_km=radius, _orig=original_congestion: _orig(net_, radius_km=radius)
            )
            agent_module.hubs_within = (
                lambda net_, radius_km=radius, _orig=original_hubs: _orig(net_, radius_km=radius)
            )
            km: list[float] = []
            late: list[float] = []
            violations: list[float] = []
            extra_km: list[float] = []
            detour_legs: list[float] = []
            for seed in seeds:
                scenario = build_scenario(net, seed=seed, n_orders=48, n_vehicles=8)
                agent = DispatcherAgent(net, scenario["vehicles"], scenario["orders"])
                agent.plan()
                result = agent.handle_incident("congestion")
                metrics = result["metrics"]
                km.append(metrics["total_km"])
                late.append(metrics["late_count"])
                violations.append(metrics["violations"])
                summary = agent.view.summary() if agent.view else {"extra_km": 0.0, "detour_legs": 0}
                extra_km.append(summary["extra_km"])
                detour_legs.append(summary["detour_legs"])
            rows.append({
                "radius": radius,
                "km": statistics.fmean(km),
                "late": statistics.fmean(late),
                "violations": statistics.fmean(violations),
                "extra_km": statistics.fmean(extra_km),
                "detour_legs": statistics.fmean(detour_legs),
            })
    finally:
        agent_module.congestion_edges = original_congestion
        agent_module.hubs_within = original_hubs
    return rows


def write_report(
    rows: list[dict],
    routing: dict[str, dict],
    rounds: list[dict],
    radius: list[dict],
    path: Path,
) -> Path:
    def stat(key: str) -> dict:
        return _agg([row[key] for row in rows])

    km = stat("km")
    total_min = stat("min")
    late = stat("late")
    on_time = stat("on_time")
    violations = stat("violations")
    blocked = stat("blocked")
    over = stat("over")

    random_km = routing["random"]["km"]["mean"]
    nn_km = routing["nearest"]["km"]["mean"]
    two_opt_km = routing["two_opt"]["km"]["mean"]
    deadline = routing["deadline"]

    lines = [
        "# Độ bền vững và độ nhạy của bộ điều phối",
        "",
        "Sinh tự động bằng `python -m backend.dispatch.robustness --report` (seed cố định nên",
        "tái lập được từng con số).",
        "",
        f"## 1. {len(rows)} seed trên cùng cấu hình (48 đơn, 8 xe)",
        "",
        "| Chỉ số | Trung bình | Độ lệch chuẩn | Nhỏ nhất | Lớn nhất |",
        "|---|---:|---:|---:|---:|",
        f"| Tổng quãng đường (km) | {km['mean']:.1f} | {km['std']:.2f} | {km['min']:.1f} | {km['max']:.1f} |",
        f"| Tổng thời gian (phút) | {total_min['mean']:.1f} | {total_min['std']:.2f} | "
        f"{total_min['min']:.1f} | {total_min['max']:.1f} |",
        f"| Số đơn trễ | {late['mean']:.2f} | {late['std']:.2f} | {late['min']:.0f} | {late['max']:.0f} |",
        f"| Đúng giờ (%) | {on_time['mean']:.1f} | {on_time['std']:.2f} | "
        f"{on_time['min']:.1f} | {on_time['max']:.1f} |",
        f"| Vi phạm luật | {violations['mean']:.2f} | {violations['std']:.2f} | "
        f"{violations['min']:.0f} | {violations['max']:.0f} |",
        f"| Vi phạm mức chặn | {blocked['mean']:.2f} | {blocked['std']:.2f} | "
        f"{blocked['min']:.0f} | {blocked['max']:.0f} |",
        f"| Tuyến quá tải | {over['mean']:.2f} | {over['std']:.2f} | {over['min']:.0f} | {over['max']:.0f} |",
        "",
        "Khoảng biến thiên giữa các seed cho thấy một kịch bản đơn lẻ không đủ đại diện: báo cáo",
        "chính nên dùng trung bình ± độ lệch chuẩn thay vì một con số của seed 7.",
        "",
        "## 2. So sánh 6 chiến lược xếp tuyến trên cùng bộ seed",
        "",
        "Cùng phân công Hungarian, chỉ đổi cách sắp thứ tự giao.",
        "",
        "| Chiến lược | Quãng đường TB (km) | Độ lệch | Đơn trễ TB | Đúng giờ TB (%) |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, _label in ROUTING_LABELS:
        item = routing[key]
        lines.append(
            f"| {item['label']} | {item['km']['mean']:.1f} | {item['km']['std']:.2f} | "
            f"{item['late']['mean']:.2f} | {item['on_time']['mean']:.1f} |"
        )
    lines += [
        "",
        "Kết luận (ổn định trên toàn bộ seed, không phụ thuộc một lần chạy):",
        "",
        f"- So với thứ tự nhập đơn, NN + 2-opt giảm **{(1 - two_opt_km / random_km) * 100:.1f}%** "
        f"quãng đường; so với Nearest Neighbor thuần giảm **{(1 - two_opt_km / nn_km) * 100:.1f}%**.",
        f"- Chiến lược mặc định `deadline` chấp nhận thêm **{(deadline['km']['mean'] / two_opt_km - 1) * 100:.1f}%** "
        f"quãng đường để kéo số đơn trễ trung bình từ {routing['two_opt']['late']['mean']:.2f} xuống "
        f"{deadline['late']['mean']:.2f} và đúng giờ từ {routing['two_opt']['on_time']['mean']:.1f}% lên "
        f"{deadline['on_time']['mean']:.1f}% — đúng mục tiêu ưu tiên cam kết với khách.",
        "",
        "## 3. Độ nhạy số vòng sửa vi phạm (`max_rounds`)",
        "",
        f"Trung bình trên {len(SENSITIVITY_SEEDS)} seed:",
        "",
        "| max_rounds | Quãng đường (km) | Đơn trễ | Vi phạm | Vi phạm mức chặn |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in rounds:
        lines.append(
            f"| {row['rounds']} | {row['km']:.1f} | {row['late']:.2f} | "
            f"{row['violations']:.2f} | {row['blocked']:.2f} |"
        )
    base = next(row for row in rounds if row["rounds"] == 4)
    more = next(row for row in rounds if row["rounds"] == 6)
    lines += [
        "",
        f"Từ 4 lên 6 vòng chỉ đổi {abs(more['km'] - base['km']):.1f} km và "
        f"{abs(more['violations'] - base['violations']):.2f} vi phạm — vòng sửa đã hội tụ;",
        "đây là căn cứ để chọn mặc định 4.",
        "",
        f"## 4. Độ nhạy bán kính vùng ùn tắc (kịch bản kẹt xe, trung bình {len(RADIUS_SEEDS)} seed)",
        "",
        "| Bán kính (km) | Quãng đường sau sự cố (km) | Đơn trễ | Vi phạm | Quãng đường đi vòng do A* (km) | Số chặng đi vòng |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in radius:
        lines.append(
            f"| {row['radius']:.1f} | {row['km']:.1f} | {row['late']:.2f} | {row['violations']:.2f} | "
            f"{row['extra_km']:.1f} | {row['detour_legs']:.1f} |"
        )
    lines += [
        "",
        "Bán kính càng lớn càng nhiều chặng bị chặn và A* phải đi vòng, quãng đường tăng tương ứng.",
        "Bảng này là căn cứ chọn 4,5 km cho kịch bản mặc định: đủ lớn để A* thực sự tìm đường vòng,",
        "đủ nhỏ để kế hoạch vẫn khả thi trong ca 4 giờ.",
        "",
        "## Cách chạy lại",
        "",
        "```powershell",
        "python -m backend.dispatch.robustness --report",
        "```",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Độ bền vững và độ nhạy của bộ điều phối")
    parser.add_argument("--report", action="store_true", help="ghi docs/ket-qua-do-ben.md")
    parser.add_argument("--seeds", type=int, default=30, help="số seed cho phần 1–2")
    args = parser.parse_args()

    net = load_network()
    seeds = list(range(1, args.seeds + 1))
    rows = seed_rows(net, seeds)
    routing = routing_aggregate(net, seeds)
    rounds = rounds_sensitivity(net, SENSITIVITY_SEEDS)
    radius = radius_sensitivity(net, RADIUS_SEEDS)

    print(f"== {len(rows)} seed ==")
    for key in ("km", "late", "on_time", "violations"):
        agg = _agg([row[key] for row in rows])
        print(f"{key:<12}{agg['mean']:>9.2f} ± {agg['std']:.2f}")
    print("\n== chiến lược xếp tuyến ==")
    for key, _label in ROUTING_LABELS:
        item = routing[key]
        print(f"{item['label']:<28}{item['km']['mean']:>8.1f} km ± {item['km']['std']:.2f} "
              f"• trễ {item['late']['mean']:.2f} • đúng giờ {item['on_time']['mean']:.1f}%")
    print("\n== max_rounds ==")
    for row in rounds:
        print(f"{row['rounds']:>2} vòng • {row['km']:.1f} km • trễ {row['late']:.2f} • vi phạm {row['violations']:.2f}")
    print("\n== bán kính ùn tắc ==")
    for row in radius:
        print(f"{row['radius']:.1f} km • {row['km']:.1f} km • trễ {row['late']:.2f} • vòng {row['extra_km']:.1f} km")

    if args.report:
        target = write_report(rows, routing, rounds, radius, ROOT / "docs" / "ket-qua-do-ben.md")
        print(f"\n[report] ghi {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
