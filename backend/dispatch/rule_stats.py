"""Thống kê cơ sở luật: luật nào kích hoạt, bao nhiêu lần, trên kịch bản nào.

Chạy:

    python -m backend.dispatch.rule_stats            # in ra màn hình
    python -m backend.dispatch.rule_stats --report   # ghi docs/ket-qua-luat.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .agent import DispatcherAgent
from .network import load_network
from .rules import RULES
from .scenario import build_scenario

ROOT = Path(__file__).resolve().parents[2]
SEEDS = (7, 11, 23)
ORDERS = 48


def collect(net) -> list[dict]:
    counts: dict[str, int] = {rule.id: 0 for rule in RULES}
    remaining: dict[str, int] = {rule.id: 0 for rule in RULES}
    plans: list[dict] = []
    for seed in SEEDS:
        scenario = build_scenario(net, seed=seed, n_orders=ORDERS, n_vehicles=8)
        agent = DispatcherAgent(net, scenario["vehicles"], scenario["orders"])
        result = agent.plan()
        for violation in result.get("violations_initial", result["violations"]):
            counts[violation["rule_id"]] = counts.get(violation["rule_id"], 0) + 1
        for violation in result["violations"]:
            remaining[violation["rule_id"]] = remaining.get(violation["rule_id"], 0) + 1
        plans.append({
            "seed": seed,
            "km": result["metrics"]["total_km"],
            "late": result["metrics"]["late_count"],
            "initial": len(result.get("violations_initial", [])),
            "violations": len(result["violations"]),
        })

    rows = []
    for rule in sorted(RULES, key=lambda r: r.priority):
        rows.append({
            "id": rule.id,
            "title": rule.title,
            "level": rule.level,
            "action": rule.action,
            "fired": counts.get(rule.id, 0),
            "left": remaining.get(rule.id, 0),
            "per_plan": round(counts.get(rule.id, 0) / len(SEEDS), 2),
            "clause": rule.clause,
        })
    return rows, plans


def render(rows: list[dict], plans: list[dict]) -> str:
    label = {"chan": "chặn", "canh_bao": "cảnh báo", "uu_tien": "ưu tiên"}
    lines = [
        "# Kết quả đối chiếu cơ sở luật",
        "",
        f"Ba kịch bản seed {', '.join(str(s) for s in SEEDS)} · {ORDERS} đơn · 8 xe. "
        "Số liệu sinh bằng `python -m backend.dispatch.rule_stats --report`.",
        "",
        "| Luật | Nội dung | Mức | Hành động | Vòng đầu | Sau khi sửa |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['title']} | {label.get(row['level'], row['level'])} | "
            f"{row['action'] or '—'} | {row['fired']} | {row['left']} |"
        )
    lines += ["", "## Kết quả điều phối của ba ca", "",
              "| Seed | Quãng đường (km) | Đơn trễ | Vi phạm vòng đầu | Còn lại sau khi sửa |",
              "|---|---|---|---|---|"]
    for plan in plans:
        lines.append(f"| {plan['seed']} | {plan['km']:.1f} | {plan['late']} | {plan['initial']} | {plan['violations']} |")
    lines += [
        "",
        "## Cách đọc",
        "",
        "- Luật mức **chặn** (R01, R02, R03, R08, R12) buộc tác tử phải sửa kế hoạch trước khi "
        "chốt; nếu không sửa được thì đơn bị đánh dấu chuyển người điều phối. Cột \"sau khi sửa\" "
        "của các luật này phải bằng 0 mới coi là kế hoạch hợp lệ.",
        "- Luật mức **cảnh báo** (R04, R05, R06, R07, R09, R10, R11) không chặn kế hoạch, chỉ "
        "nhắc tài xế hoặc điều phối viên xử lý thêm. Số của nhóm này có thể *tăng* sau khi sửa, "
        "vì đổi xe làm thay đổi tuyến nên có thêm đơn rơi vào ngưỡng — đây là hiện tượng thật, "
        "không phải lỗi đếm.",
        "- Vì vậy chỉ số đáng báo cáo là **số vi phạm mức chặn còn lại sau khi sửa**, không phải "
        "tổng số vi phạm.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Thống kê cơ sở luật")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    net = load_network()
    rows, plans = collect(net)

    print(f"{'luật':<5}{'mức':<10}{'kích hoạt':>10}  nội dung")
    for row in rows:
        print(f"{row['id']:<5}{row['level']:<10}{row['fired']:>10}  {row['title']}")

    if args.report:
        target = ROOT / "docs" / "ket-qua-luat.md"
        target.write_text(render(rows, plans), encoding="utf-8")
        print(f"\n[report] ghi {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
