"""Cơ sở tri thức dạng luật IF–THEN cho vận hành giao hàng nội thành.

Mỗi luật gồm: điều kiện (when), kết luận (verdict), mức độ (mức chặn / cảnh báo / ưu tiên)
và một câu giải thích có số liệu cụ thể. Engine chạy theo thứ tự ưu tiên, ghi lại đầy đủ
chuỗi suy diễn để màn hình "Giải trình" hiển thị lại được.

Đây là phần "logic – suy diễn" của học phần: không dùng mô hình học máy, chỉ luật và
suy diễn tiến trên tập sự kiện (facts) của từng điểm giao.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

INNER_DISTRICTS = {"Quận 1", "Quận 3", "Quận 5", "Quận 10"}
OUTER_DISTRICTS = {"Nhà Bè", "Hóc Môn", "Bình Chánh", "Quận 7", "TP. Thủ Đức"}
TRUCK_BAN_HOURS = [(6 * 60, 9 * 60), (16 * 60, 20 * 60)]


@dataclass
class Facts:
    """Sự kiện của một điểm giao tại thời điểm lập kế hoạch."""
    order: dict
    vehicle: dict
    arrive_min: float          # phút kể từ 00:00
    district: str
    stop_index: int
    stop_count: int


@dataclass
class Verdict:
    rule_id: str
    title: str
    clause: str
    level: str                 # chan | canh_bao | uu_tien
    detail: str
    action: str = ""           # chuyen_xe | doi_gio | danh_dau | ""
    order_id: str = ""


@dataclass
class Rule:
    id: str
    title: str
    clause: str
    level: str
    action: str
    priority: int
    when: Callable[[Facts], bool]
    detail: Callable[[Facts], str]


def _clock(minutes: float) -> str:
    hour = int(minutes // 60) % 24
    minute = int(minutes % 60)
    return f"{hour:02d}:{minute:02d}"


RULES: list[Rule] = [
    Rule(
        id="R01",
        title="Hàng tươi sống quá 2 giờ",
        clause="NẾU hàng tươi sống VÀ thời gian tới điểm giao > 120 phút THÌ chặn kế hoạch",
        level="chan",
        action="danh_dau",
        priority=1,
        when=lambda f: f.order["goods"] == "tuoi_song" and _minutes_from_start(f.arrive_min) > 120,
        detail=lambda f: f"tới nơi lúc {_clock(f.arrive_min)}, đã {int(_minutes_from_start(f.arrive_min))} phút kể từ 08:00",
    ),
    Rule(
        id="R02",
        title="Xe tải vào nội thành giờ cấm",
        clause="NẾU xe tải VÀ giờ giao thuộc 06:00–09:00 hoặc 16:00–20:00 VÀ quận nội thành THÌ không cho giao",
        level="chan",
        action="chuyen_xe",
        priority=2,
        when=lambda f: f.vehicle["kind"] == "xe_tai"
        and f.district in INNER_DISTRICTS
        and any(start <= f.arrive_min <= end for start, end in TRUCK_BAN_HOURS),
        detail=lambda f: f"{f.vehicle['label']} tới {f.district} lúc {_clock(f.arrive_min)} — trong khung giờ cấm tải",
    ),
    Rule(
        id="R03",
        title="Hàng cồng kềnh không đi xe máy",
        clause="NẾU thể tích > 50 L VÀ xe là xe máy THÌ đổi sang xe tải",
        level="chan",
        action="chuyen_xe",
        priority=3,
        when=lambda f: f.order["volume_l"] > 50 and f.vehicle["kind"] == "xe_may",
        detail=lambda f: f"kiện {f.order['volume_l']:.0f} L vượt thùng {f.vehicle['label']}",
    ),
    Rule(
        id="R04",
        title="Thu hộ tiền mặt lớn",
        clause="NẾU tiền thu hộ > 5.000.000đ THÌ bắt buộc giao tận tay, không để hòm",
        level="canh_bao",
        action="danh_dau",
        priority=4,
        when=lambda f: f.order["cod"] > 5_000_000,
        detail=lambda f: f"thu hộ {f.order['cod']:,}đ".replace(",", "."),
    ),
    Rule(
        id="R05",
        title="Đơn hoả tốc trễ cam kết",
        clause="NẾU đơn hoả tốc VÀ trễ quá 15 phút THÌ báo khách trước giờ hẹn",
        level="canh_bao",
        action="danh_dau",
        priority=5,
        when=lambda f: f.order["priority"] == "hoa_toc" and f.arrive_min - 8 * 60 > f.order["promised_min"] + 15,
        detail=lambda f: f"tới {_clock(f.arrive_min)}, cam kết {f.order['promised_min']} phút",
    ),
    Rule(
        id="R06",
        title="Tài xế quá nhiều điểm trong ca",
        clause="NẾU số điểm của tuyến vượt định mức của loại xe (xe máy 12, xe tải 20) THÌ cảnh báo quá tải lao động",
        level="canh_bao",
        action="danh_dau",
        priority=6,
        when=lambda f: f.stop_count > (20 if f.vehicle["kind"] == "xe_tai" else 12) and f.stop_index == f.stop_count - 1,
        detail=lambda f: f"{f.vehicle['driver']} phải giao {f.stop_count} điểm trong một ca",
    ),
    Rule(
        id="R07",
        title="Hàng dễ vỡ trên xe máy",
        clause="NẾU hàng dễ vỡ VÀ xe máy VÀ tuyến có trên 6 điểm THÌ yêu cầu đóng gói chống sốc",
        level="canh_bao",
        action="danh_dau",
        priority=7,
        when=lambda f: f.order["goods"] == "de_vo" and f.vehicle["kind"] == "xe_may" and f.stop_count > 6,
        detail=lambda f: f"tuyến {f.stop_count} điểm, thùng xe máy không cố định được kiện",
    ),
    Rule(
        id="R08",
        title="Trọng tải vượt sức chứa",
        clause="NẾU tổng tải tuyến vượt 100% sức chứa xe THÌ không xuất phát",
        level="chan",
        action="chuyen_xe",
        priority=0,
        when=lambda f: f.vehicle.get("_load_kg", 0) > f.vehicle["capacity_kg"] * 1.001
        or f.vehicle.get("_load_l", 0) > f.vehicle["capacity_l"] * 1.001,
        detail=lambda f: f"tuyến {f.vehicle.get('_load_kg', 0):.0f} kg / {f.vehicle['capacity_kg']:.0f} kg",
    ),
    Rule(
        id="R09",
        title="Hàng điện tử giá trị cao",
        clause="NẾU hàng điện tử VÀ tiền thu hộ từ 2 triệu THÌ buộc giao tận tay và ký nhận",
        level="canh_bao",
        action="danh_dau",
        priority=8,
        when=lambda f: f.order["goods"] == "dien_tu" and f.order["cod"] >= 2_000_000,
        detail=lambda f: f"{f.order['goods_label']} thu hộ {f.order['cod']:,}đ".replace(",", "."),
    ),
    Rule(
        id="R10",
        title="Tuyến dài quá 4 giờ liên tục",
        clause="NẾU tuyến kéo dài quá 240 phút THÌ phải nghỉ 15 phút trước điểm cuối",
        level="canh_bao",
        action="danh_dau",
        priority=9,
        when=lambda f: f.stop_index == f.stop_count - 1 and f.arrive_min - 8 * 60 > 240,
        detail=lambda f: f"{f.vehicle['driver']} chạy liên tục {int(f.arrive_min - 8 * 60)} phút",
    ),
    Rule(
        id="R11",
        title="Ngoại thành sau giờ tan tầm",
        clause="NẾU điểm giao ở huyện ngoại thành VÀ tới sau 17:00 THÌ hẹn giao sáng hôm sau",
        level="canh_bao",
        action="doi_gio",
        priority=10,
        when=lambda f: f.district in OUTER_DISTRICTS and f.arrive_min >= 17 * 60,
        detail=lambda f: f"{f.district} lúc {_clock(f.arrive_min)} — đường về kẹt, tài xế khó kịp chuyến tiếp",
    ),
    Rule(
        id="R12",
        title="Kiện nặng không đi xe máy",
        clause="NẾU một kiện nặng trên 8 kg VÀ xe là xe máy THÌ chặn, đổi sang xe tải nhỏ",
        level="chan",
        action="chuyen_xe",
        priority=11,
        when=lambda f: f.vehicle["kind"] == "xe_may" and f.order["weight_kg"] > 8.0,
        detail=lambda f: f"kiện {f.order['weight_kg']:.1f} kg, thùng xe máy chỉ chở được kiện nhẹ",
    ),
]


def _minutes_from_start(arrive_min: float) -> float:
    return arrive_min - 8 * 60


class RuleEngine:
    """Suy diễn tiến: duyệt luật theo ưu tiên, dừng ở luật chặn đầu tiên của mỗi đơn."""

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules = sorted(rules or RULES, key=lambda r: r.priority)

    def evaluate(self, facts: Facts) -> list[Verdict]:
        verdicts: list[Verdict] = []
        blocked = False
        for rule in self.rules:
            if blocked:
                break
            try:
                fired = rule.when(facts)
            except KeyError:
                continue
            if not fired:
                continue
            verdicts.append(Verdict(
                rule_id=rule.id,
                title=rule.title,
                clause=rule.clause,
                level=rule.level,
                detail=rule.detail(facts),
                action=rule.action,
                order_id=facts.order["id"],
            ))
            if rule.level == "chan":
                blocked = True
        return verdicts

    def check_routes(
        self,
        net,
        routes,
        vehicles_by_id: dict[str, dict],
        orders_by_id: dict[str, dict],
    ) -> list[dict]:
        """Chạy toàn bộ tuyến, trả về danh sách vi phạm (kèm ngữ cảnh để sửa)."""
        violations: list[dict] = []
        for route in routes:
            vehicle = dict(vehicles_by_id[route.vehicle_id])
            vehicle["_load_kg"] = route.load_kg
            vehicle["_load_l"] = route.load_l
            for index, stop in enumerate(route.stops):
                order = orders_by_id.get(stop.order_id)
                if order is None:
                    continue
                facts = Facts(
                    order=order,
                    vehicle=vehicle,
                    arrive_min=stop.arrive_min,
                    district=net.hub(order["dest_hub"]).district,
                    stop_index=index,
                    stop_count=len(route.stops),
                )
                for verdict in self.evaluate(facts):
                    violations.append({
                        "rule_id": verdict.rule_id,
                        "title": verdict.title,
                        "clause": verdict.clause,
                        "level": verdict.level,
                        "detail": verdict.detail,
                        "action": verdict.action,
                        "order_id": verdict.order_id,
                        "vehicle_id": vehicle["id"],
                        "clock": _clock(stop.arrive_min),
                    })
        return violations
