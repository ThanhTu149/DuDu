"""Tác tử điều phối: vòng lặp nhận biết — quyết định — hành động.

Đây là phần "tác tử" của học phần. Tác tử không chỉ chạy thuật toán một lần rồi thôi:
nó nhìn lại kế hoạch vừa lập, đối chiếu với cơ sở luật, tự sửa những chỗ vi phạm, rồi
lập lại tuyến — lặp tới khi hết vi phạm hoặc hết số vòng cho phép. Mỗi vòng được ghi vào
`steps` để màn hình giải trình hiển thị lại toàn bộ quá trình ra quyết định.

Ngoài ra tác tử còn xử lý sự cố: một xe hỏng giữa ca thì đơn của xe đó được chia lại cho
các xe còn lại và toàn bộ tuyến được lập lại.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .assignment import STRATEGIES, _load, repair_capacity
from .network import Network
from .routing import BASE_MINUTE, plan_routes, summarize
from .rules import RuleEngine


@dataclass
class Step:
    index: int
    stage: str          # perceive | decide | act | verify
    title: str
    detail: str
    ms: int = 0         # mili-giây kể từ lúc bắt đầu lập kế hoạch

    def as_dict(self) -> dict:
        return {"index": self.index, "stage": self.stage, "title": self.title,
                "detail": self.detail, "ms": self.ms}


class DispatcherAgent:
    def __init__(
        self,
        net: Network,
        vehicles: list[dict],
        orders: list[dict],
        assignment_strategy: str = "hungarian",
        routing_strategy: str = "deadline",
        max_rounds: int = 4,
        eta_model=None,
    ) -> None:
        self.net = net
        self.vehicles = [dict(v) for v in vehicles]
        self.orders = [dict(o) for o in orders]
        self.assignment_strategy = assignment_strategy
        self.routing_strategy = routing_strategy
        self.max_rounds = max_rounds
        self.eta_model = eta_model
        self.time_multiplier = 1.0
        self.rules = RuleEngine()
        self.steps: list[Step] = []
        self._t0: float | None = None

    # -- tiện ích -------------------------------------------------------
    def _log(self, stage: str, title: str, detail: str) -> None:
        elapsed = int((time.perf_counter() - self._t0) * 1000) if self._t0 else 0
        self.steps.append(Step(len(self.steps) + 1, stage, title, detail, elapsed))

    def _orders_by_id(self) -> dict[str, dict]:
        return {o["id"]: o for o in self.orders}

    def _vehicles_by_id(self) -> dict[str, dict]:
        return {v["id"]: v for v in self.vehicles}

    def _plan(self, assignment: dict[str, list[dict]]):
        routes = plan_routes(self.net, self.vehicles, assignment, strategy=self.routing_strategy, start_min=BASE_MINUTE, eta_model=self.eta_model, time_multiplier=self.time_multiplier)
        assignment, moves = repair_capacity(assignment, self.vehicles)
        if moves:
            routes = plan_routes(self.net, self.vehicles, assignment, strategy=self.routing_strategy, start_min=BASE_MINUTE, eta_model=self.eta_model, time_multiplier=self.time_multiplier)
        return assignment, routes, moves

    # -- chu trình chính -------------------------------------------------
    def plan(self) -> dict:
        self.steps.clear()
        self._t0 = time.perf_counter()
        self._log("perceive", "Nhận lô đơn",
                  f"{len(self.orders)} đơn, {len(self.vehicles)} xe, ca bắt đầu 08:00. "
                  f"Tổng khối lượng {sum(o['weight_kg'] for o in self.orders):.0f} kg.")

        assign_fn = STRATEGIES[self.assignment_strategy]
        assignment = assign_fn(self.net, self.orders, self.vehicles)
        self._log("decide", f"Chia đơn bằng {self.assignment_strategy}",
                  f"{sum(1 for v in assignment.values() if v)} xe có đơn, "
                  f"tải lớn nhất {max((_load(v)[0] for v in assignment.values()), default=0):.0f} kg.")

        assignment, routes, moves = self._plan(assignment)
        if moves:
            self._log("act", "Sửa lô vượt tải", f"chuyển {moves} đơn sang xe còn chỗ.")

        violations = self.rules.check_routes(self.net, routes, self._vehicles_by_id(), self._orders_by_id())
        initial_violations = list(violations)
        self._log("verify", "Đối chiếu cơ sở luật",
                  f"{len(violations)} vi phạm" if violations else "không có vi phạm.")

        for round_index in range(1, self.max_rounds + 1):
            actionable = [v for v in violations if v["action"] == "chuyen_xe" and v["level"] == "chan"]
            if not actionable:
                break
            moved = self._apply_moves(assignment, actionable)
            if not moved:
                self._log("act", f"Vòng {round_index}: không thể sửa tự động",
                          f"{len(actionable)} vi phạm cần người điều phối xử lý (đánh dấu lại).")
                break
            self._log("act", f"Vòng {round_index}: đổi xe cho đơn vi phạm", f"đã chuyển {moved} đơn.")
            assignment, routes, _ = self._plan(assignment)
            violations = self.rules.check_routes(self.net, routes, self._vehicles_by_id(), self._orders_by_id())
            self._log("verify", f"Vòng {round_index}: kiểm tra lại",
                      f"còn {len(violations)} vi phạm." if violations else "đã sạch vi phạm.")

        metrics = summarize(routes)
        metrics["violations"] = len(violations)
        metrics["blocked"] = sum(1 for v in violations if v["level"] == "chan")
        self._log("verify", "Chốt kế hoạch",
                  f"{metrics['orders']} điểm giao, {metrics['total_km']:.0f} km, "
                  f"{metrics['late_count']} đơn trễ, {metrics['violations']} vi phạm.")

        return {
            "routes": [r.as_dict() for r in routes],
            "metrics": metrics,
            "violations": violations,
            "violations_initial": initial_violations,
            "steps": [s.as_dict() for s in self.steps],
            "strategy": {"assignment": self.assignment_strategy, "routing": self.routing_strategy, "eta": "ml" if self.eta_model else "osrm"},
        }

    # -- các hành động sửa lỗi -------------------------------------------
    def _apply_moves(self, assignment: dict[str, list[dict]], violations: list[dict]) -> int:
        """Chuyển đơn vi phạm sang xe khác còn đủ sức chứa. Trả về số đơn đã chuyển."""
        by_id = self._orders_by_id()
        vehicles_by_id = self._vehicles_by_id()
        moved = 0
        seen: set[str] = set()
        for violation in violations:
            order_id = violation["order_id"]
            if order_id in seen:
                continue
            seen.add(order_id)
            order = by_id.get(order_id)
            if order is None:
                continue

            source_id = next((vid for vid, items in assignment.items() if any(o["id"] == order_id for o in items)), None)
            if source_id is None:
                continue

            loads = {vid: _load(items) for vid, items in assignment.items()}
            candidates = [
                v for v in self.vehicles
                if v["id"] != source_id
                and loads[v["id"]][0] + order["weight_kg"] <= v["capacity_kg"]
                and loads[v["id"]][1] + order["volume_l"] <= v["capacity_l"]
                and not self._would_repeat(v, order)
            ]
            if not candidates:
                continue
            target = min(candidates, key=lambda v: self.net.dur(v["start_hub"], order["dest_hub"]))
            assignment[source_id] = [o for o in assignment[source_id] if o["id"] != order_id]
            assignment[target["id"]].append(order)
            moved += 1
        return moved

    def _would_repeat(self, vehicle: dict, order: dict) -> bool:
        """Tránh đẩy đơn sang một xe cũng vi phạm đúng luật đó."""
        if order["volume_l"] > 50 and vehicle["kind"] == "xe_may":
            return True
        if order["weight_kg"] > 8 and vehicle["kind"] == "xe_may":
            return True
        if vehicle["kind"] == "xe_tai" and self.net.hub(order["dest_hub"]).district in {
            "Quận 1", "Quận 3", "Quận 5", "Quận 10"
        } and BASE_MINUTE <= 9 * 60:
            return True
        return False

    # -- sự cố ------------------------------------------------------------
    def handle_incident(self, kind: str, vehicle_id: str | None = None, hub_id: str | None = None) -> dict:
        """Xử lý sự cố: xe hỏng / kẹt xe diện rộng / kho đóng.

        Cả ba đều dẫn tới cùng một phản ứng của tác tử: nhận biết sự kiện, chia lại đơn theo
        năng lực còn lại, lập lại tuyến và kiểm tra luật.
        """
        if kind == "truck_ban":
            self._log("perceive", "Sự cố: xe tải bị chặn", f"xe {vehicle_id} không được vào nội thành.")
            return self._replan_after_removal()

        if kind == "congestion":
            self.time_multiplier = 1.4
            self._log("perceive", "Sự cố: kẹt xe diện rộng",
                      "toàn bộ thời gian di chuyển tăng 40%, quãng đường không đổi.")
            return self._replan_after_removal()

        if kind == "depot_closed" and hub_id:
            closed = self.net.hub(hub_id).name if hub_id in self.net.hubs else hub_id
            alternatives = [v["start_hub"] for v in self.vehicles if v["start_hub"] != hub_id]
            fallback = alternatives[0] if alternatives else hub_id
            affected = [v for v in self.vehicles if v["start_hub"] == hub_id]
            if not affected:
                self._log("perceive", "Sự cố: kho đóng", f"{closed} không có xe nào xuất phát từ đây.")
                return self._replan_after_removal()
            self._log("perceive", "Sự cố: kho đóng",
                      f"{closed} ngừng nhận hàng, {len(affected)} xe chuyển sang xuất phát tại "
                      f"{self.net.hub(fallback).name}.")
            self.vehicles = [
                {**v, "start_hub": fallback} if v["start_hub"] == hub_id else v for v in self.vehicles
            ]
            return self._replan_after_removal()

        if kind == "breakdown" and vehicle_id:
            broken = next((v for v in self.vehicles if v["id"] == vehicle_id), None)
            if broken is None:
                return self._replan_after_removal()
            self._log("perceive", "Sự cố: xe hỏng",
                      f"{broken['label']} {broken['plate']} ({broken['driver']}) dừng hoạt động.")
            self.vehicles = [v for v in self.vehicles if v["id"] != vehicle_id]
            return self._replan_after_removal()

        return self._replan_after_removal()

    def _replan_after_removal(self) -> dict:
        """Chia lại đơn theo năng lực còn lại rồi lập lại toàn bộ tuyến."""
        self._t0 = time.perf_counter()
        assign_fn = STRATEGIES[self.assignment_strategy]
        assignment = assign_fn(self.net, self.orders, self.vehicles)
        assignment, routes, moves = self._plan(assignment)
        self._log("act", "Chia lại toàn bộ đơn",
                  f"{len(self.vehicles)} xe còn lại nhận {len(self.orders)} đơn.")
        violations = self.rules.check_routes(self.net, routes, self._vehicles_by_id(), self._orders_by_id())
        metrics = summarize(routes)
        metrics["violations"] = len(violations)
        metrics["blocked"] = sum(1 for v in violations if v["level"] == "chan")
        self._log("verify", "Kế hoạch sau sự cố",
                  f"{metrics['total_km']:.0f} km, {metrics['late_count']} đơn trễ, {len(violations)} vi phạm.")
        return {
            "routes": [r.as_dict() for r in routes],
            "metrics": metrics,
            "violations": violations,
            "steps": [s.as_dict() for s in self.steps],
            "strategy": {"assignment": self.assignment_strategy, "routing": self.routing_strategy, "eta": "ml" if self.eta_model else "osrm"},
        }



