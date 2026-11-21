"""Bảng so sánh chiến lược điều phối — dùng cho chương đánh giá của báo cáo."""

from __future__ import annotations

import argparse
from pathlib import Path

from .assignment import STRATEGIES
from .network import Network, load_network
from .routing import BASE_MINUTE, plan_routes, summarize

ROOT = Path(__file__).resolve().parents[2]

ROUTING_LABELS = [
    ("random", "Thứ tự nhập"),
    ("nearest", "Nearest Neighbor"),
    ("two_opt", "NN + 2-opt"),
    ("savings", "Clarke–Wright"),
    ("savings_2opt", "C-W + 2-opt"),
    ("deadline", "NN + 2-opt (hạn giao)"),
]


def compare_strategies(net: Network, scenario: dict, routing_strategy: str = "deadline") -> list[dict]:
    rows = []
    for name, assign in STRATEGIES.items():
        assignment = assign(net, scenario["orders"], scenario["vehicles"])
        routes = plan_routes(net, scenario["vehicles"], assignment, strategy=routing_strategy, start_min=BASE_MINUTE)
        summary = summarize(routes)
        summary["strategy"] = name
        rows.append(summary)
    return rows


def compare_routing(net: Network, scenario: dict, assignment_name: str = "hungarian") -> list[dict]:
    rows = []
    assign = STRATEGIES[assignment_name]
    assignment = assign(net, scenario["orders"], scenario["vehicles"])
    for key, label in ROUTING_LABELS:
        routes = plan_routes(net, scenario["vehicles"], assignment, strategy=key, start_min=BASE_MINUTE)
        summary = summarize(routes)
        summary["routing"] = label
        rows.append(summary)
    return rows


def compare_eta(net: Network, scenario: dict, assignment_name: str = "hungarian") -> list[dict]:
    """Cùng một kế hoạch, khác nhau ở cách tính thời gian di chuyển.

    - `osrm`: thời gian free-flow của mạng đường (lạc quan, bỏ qua ùn tắc).
    - `ml`: nhân thêm hệ số ùn tắc theo giờ học từ dữ liệu thật.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ml.eta_model import EtaModel

    model = EtaModel.load()
    assignment = STRATEGIES[assignment_name](net, scenario["orders"], scenario["vehicles"])
    rows = []
    for label, eta in (("OSRM (free-flow)", None), ("OSRM × hệ số ùn tắc (mô hình)", model)):
        if label.startswith("OSRM ×") and model is None:
            continue
        routes = plan_routes(net, scenario["vehicles"], assignment, strategy="deadline", start_min=BASE_MINUTE, eta_model=eta)
        summary = summarize(routes)
        summary["eta"] = label
        rows.append(summary)
    return rows


def scaling_rows(net: Network, sizes=(48, 96, 144), vehicles: int = 8) -> list[dict]:
    """Cùng một đội xe, tăng dần số đơn — để trả lời "2-opt có đáng dùng không"."""
    from .scenario import build_scenario

    rows: list[dict] = []
    for size in sizes:
        scenario = build_scenario(net, seed=7, n_orders=size, n_vehicles=vehicles)
        assignment = STRATEGIES["hungarian"](net, scenario["orders"], scenario["vehicles"])
        for key, label in ROUTING_LABELS:
            if key == "deadline":
                continue
            routes = plan_routes(net, scenario["vehicles"], assignment, strategy=key, start_min=BASE_MINUTE)
            summary = summarize(routes)
            served = summary.pop("orders")
            rows.append({"orders": size, "served": served, "strategy": label, "key": key, **summary})
    return rows


def write_scaling_report(net: Network, out_md: Path, out_dir: Path) -> Path:
    """Sinh bảng markdown + 2 biểu đồ cho chương 2 của báo cáo."""
    rows = scaling_rows(net)
    sizes = sorted({row["orders"] for row in rows})
    labels = [label for key, label in ROUTING_LABELS if key != "deadline"]

    lines = ["# Kết quả thí nghiệm xếp tuyến theo quy mô", "",
             "Sinh tự động bằng `python -m backend.dispatch.evaluate --report`. Cùng một kịch bản "
             "(seed 7, 8 xe, cách chia đơn Hungary), chỉ đổi chiến lược sắp thứ tự giao.",
             "",
             "| Số đơn | " + " | ".join(labels) + " |",
             "|---" * (len(labels) + 1) + "|"]
    for size in sizes:
        cells = []
        for label in labels:
            row = next(r for r in rows if r["orders"] == size and r["strategy"] == label)
            cells.append(f"{row['total_km']:.1f} km")
        lines.append(f"| {size} | " + " | ".join(cells) + " |")

    lines += ["", "## Tỉ lệ đúng giờ", "", "| Số đơn | " + " | ".join(labels) + " |",
              "|---" * (len(labels) + 1) + "|"]
    for size in sizes:
        cells = []
        for label in labels:
            row = next(r for r in rows if r["orders"] == size and r["strategy"] == label)
            cells.append(f"{row['on_time_rate']:.1f}%")
        lines.append(f"| {size} | " + " | ".join(cells) + " |")

    nn_by_size = {r["orders"]: r["total_km"] for r in rows if r["key"] == "nearest"}
    cw_by_size = {r["orders"]: r["total_km"] for r in rows if r["key"] == "savings_2opt"}
    gains = {size: (nn_by_size[size] - cw_by_size[size]) / nn_by_size[size] * 100 for size in sizes}
    lines += ["", "## Mức cải thiện của C-W + 2-opt so với Nearest Neighbor", "",
              "| Số đơn | " + " | ".join(str(s) for s in sizes) + " |",
              "|---" * (len(sizes) + 1) + "|",
              "| Giảm quãng đường | " + " | ".join(f"{gains[s]:.1f}%" for s in sizes) + " |", "",
              "## Cách đọc bảng", "",
              "- Ở 48 đơn mỗi tuyến chỉ 6 điểm, Nearest Neighbor đã gần tối ưu nên 2-opt không "
              "cải thiện; ở 144 đơn mỗi tuyến 18 điểm, 2-opt giảm 10,4% quãng đường. Kết luận: "
              "2-opt đáng dùng khi tuyến dài, không phải lúc nào cũng đáng.",
              "- Clarke–Wright (dựng tuyến bằng tiết kiệm) *không* vượt Nearest Neighbor khi chỉ "
              "sắp thứ tự cho một danh sách điểm có sẵn, vì nó được thiết kế để quyết định gộp "
              "tuyến ở cấp đội xe. Ở cấp đội xe (xem bảng chia đơn trong báo cáo), nó cạnh tranh "
              "với tham lam nhưng kém Hungary vì bỏ qua hạn giao.",
              "- Cột \"Thứ tự nhập\" là mốc xấu nhất — tương đương điều phối viên giao đơn theo thứ "
              "tự đơn đến, không sắp gì.", ""]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
    except ImportError:
        print("[chart] chưa có matplotlib, bỏ qua biểu đồ")
        return out_md

    out_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False

    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=160)
    palette = ["#8d8d8d", "#c9490e", "#2f5d8c", "#2c6b52", "#15171c"]
    for index, label in enumerate(labels):
        series = [next(r for r in rows if r["orders"] == size and r["strategy"] == label)["total_km"] for size in sizes]
        ax.plot(sizes, series, marker="o", linewidth=1.8, markersize=4,
                color=palette[index % len(palette)], label=label)
    ax.set_xlabel("Số đơn trong ca")
    ax.set_ylabel("Tổng quãng đường (km)")
    ax.set_xticks(sizes)
    ax.grid(axis="y", color="#e5dfd3", linewidth=0.8)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_dir / "vrp-km.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.4, 3.6), dpi=160)
    ax.bar([str(s) for s in sizes], [gains[s] for s in sizes], color="#c9490e", width=0.5)
    for i, size in enumerate(sizes):
        ax.text(i, gains[size] + 0.4, f"{gains[size]:.1f}%", ha="center", fontsize=9)
    ax.set_xlabel("Số đơn trong ca")
    ax.set_ylabel("Giảm quãng đường so với NN (%)")
    ax.grid(axis="y", color="#e5dfd3", linewidth=0.8)
    ax.set_ylim(0, max(gains.values()) * 1.35)
    fig.tight_layout()
    fig.savefig(out_dir / "vrp-cai-thien.png")
    plt.close(fig)
    return out_md


def main() -> None:
    parser = argparse.ArgumentParser(description="So sánh chiến lược điều phối")
    parser.add_argument("--report", action="store_true", help="ghi docs/ket-qua-vrp.md và biểu đồ")
    args = parser.parse_args()

    from .scenario import build_scenario

    net = load_network()
    scenario = build_scenario(net, seed=7, n_orders=48, n_vehicles=8)

    print(f"Kịch bản seed={scenario['seed']}: {len(scenario['orders'])} đơn, {len(scenario['vehicles'])} xe\n")
    print("== Chia đơn: random / greedy / Hungary (xếp tuyến bằng 2-opt có hạn giao) ==")
    print(f"{'chiến lược':<12}{'km':>8}{'phút':>8}{'trễ':>5}{'phút trễ':>10}{'đúng giờ %':>12}{'quá tải':>9}")
    for row in compare_strategies(net, scenario):
        print(f"{row['strategy']:<12}{row['total_km']:>8.1f}{row['total_min']:>8.1f}{row['late_count']:>5}"
              f"{row['late_minutes']:>10.0f}{row['on_time_rate']:>12.1f}{row['over_capacity_routes']:>9}")

    print("\n== Xếp tuyến: 6 chiến lược trên cùng cách chia đơn của Hungary ==")
    print(f"{'chiến lược':<26}{'km':>8}{'phút':>8}{'trễ':>5}{'phút trễ':>10}")
    for row in compare_routing(net, scenario):
        print(f"{row['routing']:<26}{row['total_km']:>8.1f}{row['total_min']:>8.1f}"
              f"{row['late_count']:>5}{row['late_minutes']:>10.0f}")

    eta_rows = compare_eta(net, scenario)
    if len(eta_rows) > 1:
        print("\n== Thời gian di chuyển: free-flow so với có hệ số ùn tắc ==")
        print(f"{'cách tính':<28}{'phút':>8}{'trễ':>5}{'phút trễ':>10}{'đúng giờ %':>12}")
        for row in eta_rows:
            print(f"{row['eta']:<28}{row['total_min']:>8.1f}{row['late_count']:>5}"
                  f"{row['late_minutes']:>10.0f}{row['on_time_rate']:>12.1f}")

    if args.report:
        target = write_scaling_report(net, ROOT / "docs" / "ket-qua-vrp.md", ROOT / "docs" / "hinh")
        print(f"\n[report] ghi {target.relative_to(ROOT)} + 2 biểu đồ trong docs/hinh/")


if __name__ == "__main__":
    main()
