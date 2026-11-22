"""API của DuDu — bốn module thuật toán phơi ra cho giao diện gọi.

Mọi endpoint đều kiểm tra dữ liệu vào bằng Pydantic trước khi chạy thuật toán:
- số đơn / số xe / seed có biên rõ ràng (chặn một request làm treo máy chủ),
- tên chiến lược chia đơn & xếp tuyến phải nằm trong danh sách cho phép,
- mã xe / mã nút trong sự cố phải tồn tại.

Phần nặng được cache có giới hạn: kịch bản theo (seed, số đơn, số xe) và kế hoạch "trước
sự cố" theo cùng bộ ba + chiến lược, nên bấm sự cố liên tiếp không phải tính lại từ đầu.
"""

from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
from contextlib import asynccontextmanager
from collections import OrderedDict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .dispatch.agent import DispatcherAgent
from .dispatch.evaluate import compare_routing, compare_strategies
from .dispatch.history import get as history_get
from .dispatch.history import recent as history_recent
from .dispatch.history import save as history_save
from .dispatch.import_orders import parse_orders_csv
from .dispatch.network import load_network
from .dispatch.routing import BASE_MINUTE, clock_label
from .dispatch.rules import RULES
from .dispatch.scenario import build_scenario, build_vehicles

logger = logging.getLogger("dudu.api")

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
GEOMETRY_CACHE = ROOT / "data" / "processed" / "geometry.json"
ETA_MODEL_FILE = ROOT / "ml" / "models" / "eta_rf.joblib"
ETA_METRICS_FILE = ROOT / "ml" / "models" / "eta_metrics.json"
SAMPLE_ORDERS_CSV = ROOT / "data" / "samples" / "don-hang-mau.csv"

# Biên dữ liệu vào — dùng chung cho mọi endpoint để không chỗ nào lỏng hơn chỗ khác.
ORDERS_MIN, ORDERS_MAX = 8, 200
VEHICLES_MIN, VEHICLES_MAX = 2, 8
SEED_MIN, SEED_MAX = 1, 9_999
SCENARIO_CACHE_SIZE = 64
BEFORE_CACHE_SIZE = 64
STARTED_AT = time.time()

AssignmentName = Literal["hungarian", "greedy", "savings", "random"]
RoutingName = Literal["deadline", "nearest", "two_opt", "random", "savings", "savings_2opt"]
IncidentKind = Literal["breakdown", "congestion", "depot_closed", "truck_ban"]
EtaSource = Literal["osrm", "ml"]


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    seed: int = Field(7, ge=SEED_MIN, le=SEED_MAX)
    orders: int = Field(48, ge=ORDERS_MIN, le=ORDERS_MAX)
    vehicles: int = Field(8, ge=VEHICLES_MIN, le=VEHICLES_MAX)
    assignment: AssignmentName = "hungarian"
    routing: RoutingName = "deadline"
    eta: EtaSource = "osrm"


class IncidentRequest(PlanRequest):
    kind: IncidentKind = "breakdown"
    vehicle_id: str | None = Field(None, max_length=64)
    hub_id: str | None = Field(None, max_length=64)
    # /api/incident trước đây nhận đủ bộ ba seed/orders/vehicles như plan
    orders: int = Field(48, ge=ORDERS_MIN, le=ORDERS_MAX)
    vehicles: int = Field(8, ge=VEHICLES_MIN, le=VEHICLES_MAX)


class ImportPlanRequest(BaseModel):
    """Kế hoạch từ danh sách đơn nhập tay (CSV dạng chuỗi, tối đa 200 dòng)."""

    model_config = ConfigDict(extra="ignore")

    csv: str = Field(min_length=1, max_length=200_000)
    seed: int = Field(7, ge=SEED_MIN, le=SEED_MAX)
    vehicles: int = Field(8, ge=VEHICLES_MIN, le=VEHICLES_MAX)
    assignment: AssignmentName = "hungarian"
    routing: RoutingName = "deadline"
    eta: EtaSource = "osrm"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Nạp sẵn mô hình ETA ở luồng nền để request đầu tiên không bị chậm."""
    threading.Thread(target=eta_model, name="eta-warmup", daemon=True).start()
    yield


app = FastAPI(title="DuDu Dispatch API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

net = load_network()
_scenarios: OrderedDict[tuple[int, int, int], dict] = OrderedDict()
_before_metrics: OrderedDict[tuple[int, int, int, str, str], dict] = OrderedDict()
_eta_model = None
_locks = {
    "scenario": threading.Lock(),
    "eta": threading.Lock(),
    "before": threading.Lock(),
    "geometry": threading.Lock(),
}



def eta_model():
    """Nạp mô hình ETA một lần (có khoá); thiếu mô hình thì trả None, hệ thống vẫn chạy."""
    global _eta_model
    if _eta_model is not None:
        return _eta_model or None
    with _locks["eta"]:
        if _eta_model is None:
            try:
                import sys

                if str(ROOT) not in sys.path:
                    sys.path.insert(0, str(ROOT))
                from ml.eta_model import EtaModel

                _eta_model = EtaModel.load() or False
            except Exception:  # noqa: BLE001 — thiếu model không được làm sập API
                logger.warning("Không nạp được mô hình ETA, dùng OSRM", exc_info=True)
                _eta_model = False
    return _eta_model or None


def eta_available() -> bool:
    """Có mô hình trên đĩa không — kiểm tra không cần nạp (health phải trả lời tức thì)."""
    if _eta_model is not None:
        return bool(_eta_model)
    return ETA_MODEL_FILE.exists() and ETA_METRICS_FILE.exists()


def _scenario(seed: int, orders: int, vehicles: int) -> dict:
    key = (seed, orders, vehicles)
    with _locks["scenario"]:
        if key in _scenarios:
            _scenarios.move_to_end(key)
            return _scenarios[key]
        data = build_scenario(net, seed=seed, n_orders=orders, n_vehicles=vehicles)
        _scenarios[key] = data
        while len(_scenarios) > SCENARIO_CACHE_SIZE:
            _scenarios.popitem(last=False)
        return data


def _copy_scenario(data: dict) -> tuple[list[dict], list[dict]]:
    """Thuật toán có thể sắp xếp/tiêu thụ danh sách — luôn đưa bản sao, giữ cache nguyên vẹn."""
    return [dict(v) for v in data["vehicles"]], [dict(o) for o in data["orders"]]


def _baseline_metrics(data: dict, assignment: str, routing: str) -> dict:
    key = (data["seed"], len(data["orders"]), len(data["vehicles"]), assignment, routing)
    with _locks["before"]:
        if key in _before_metrics:
            _before_metrics.move_to_end(key)
            return _before_metrics[key]
        vehicles, orders = _copy_scenario(data)
        metrics = DispatcherAgent(
            net,
            vehicles,
            orders,
            assignment_strategy=assignment,
            routing_strategy=routing,
        ).plan()["metrics"]
        _before_metrics[key] = metrics
        while len(_before_metrics) > BEFORE_CACHE_SIZE:
            _before_metrics.popitem(last=False)
        return metrics


def _validation_error(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Không trả stack trace ra ngoài; log lại để người phát triển đọc."""
    logger.exception("Lỗi không xử lý ở %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Lỗi nội bộ máy chủ", "type": type(exc).__name__, "path": request.url.path},
    )


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": app.version,
        "hubs": len(net.order),
        "rules": len(RULES),
        "eta_model": eta_available(),
        "eta_loaded": _eta_model is not None,
        "uptime_s": round(time.time() - STARTED_AT, 1),
        "limits": {
            "orders": [ORDERS_MIN, ORDERS_MAX],
            "vehicles": [VEHICLES_MIN, VEHICLES_MAX],
            "seed": [SEED_MIN, SEED_MAX],
        },
    }


@app.get("/api/hubs")
def hubs() -> dict:
    return {
        "hubs": [
            {"id": h.id, "name": h.name, "kind": h.kind, "district": h.district, "lat": h.lat, "lon": h.lon}
            for h in net.hubs.values()
        ],
        "bounds": {
            "min_lat": min(h.lat for h in net.hubs.values()),
            "max_lat": max(h.lat for h in net.hubs.values()),
            "min_lon": min(h.lon for h in net.hubs.values()),
            "max_lon": max(h.lon for h in net.hubs.values()),
        },
    }


@app.get("/api/scenario")
def scenario(
    seed: int = Query(7, ge=SEED_MIN, le=SEED_MAX),
    orders: int = Query(48, ge=ORDERS_MIN, le=ORDERS_MAX),
    vehicles: int = Query(8, ge=VEHICLES_MIN, le=VEHICLES_MAX),
) -> dict:
    data = _scenario(seed, orders, vehicles)
    return {**data, "start_label": clock_label(BASE_MINUTE)}


@app.post("/api/plan")
def plan(payload: PlanRequest | None = None) -> dict:
    request = payload or PlanRequest()
    data = _scenario(request.seed, request.orders, request.vehicles)
    vehicles, orders = _copy_scenario(data)
    model = eta_model() if request.eta == "ml" else None
    result = DispatcherAgent(
        net,
        vehicles,
        orders,
        assignment_strategy=request.assignment,
        routing_strategy=request.routing,
        eta_model=model,
    ).plan()
    result["seed"] = request.seed
    result["start_label"] = clock_label(BASE_MINUTE)
    result["warnings"] = []
    if request.eta == "ml" and model is None:
        result["warnings"].append(
            "Chưa có mô hình ETA trên máy này — kế hoạch đang tính theo OSRM free-flow. "
            "Chạy python ml/train_eta.py để bật hiệu chỉnh ùn tắc."
        )
    result["history_id"] = history_save("plan", request.model_dump(), result)
    # kèm dữ liệu nguồn để UI khôi phục kế hoạch từ lịch sử vẫn có đủ chi tiết đơn/xe
    result["orders"] = orders
    result["vehicles"] = vehicles
    return result


@app.post("/api/plan/import")
def plan_import(payload: ImportPlanRequest) -> dict:
    """Lập kế hoạch từ CSV: kiểm tra từng dòng, bỏ dòng lỗi kèm cảnh báo."""
    try:
        parsed = parse_orders_csv(payload.csv, net, seed=payload.seed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"CSV không hợp lệ: {exc}") from exc

    vehicles = build_vehicles(random.Random(payload.seed), payload.vehicles)
    model = eta_model() if payload.eta == "ml" else None
    result = DispatcherAgent(
        net,
        [vehicle.as_dict() for vehicle in vehicles],
        parsed["orders"],
        assignment_strategy=payload.assignment,
        routing_strategy=payload.routing,
        eta_model=model,
    ).plan()
    result["seed"] = payload.seed
    result["start_label"] = clock_label(BASE_MINUTE)
    result["warnings"] = []
    if payload.eta == "ml" and model is None:
        result["warnings"].append(
            "Chưa có mô hình ETA trên máy này — kế hoạch đang tính theo OSRM free-flow."
        )
    result["import"] = {"count": parsed["count"], "warnings": parsed["warnings"]}
    result["orders"] = parsed["orders"]
    result["vehicles"] = [vehicle.as_dict() for vehicle in vehicles]
    result["history_id"] = history_save(
        "import", {"seed": payload.seed, "vehicles": payload.vehicles, "rows": parsed["count"]}, result
    )
    return result


@app.get("/api/orders/template")
def orders_template():
    """Tải file CSV mẫu để người dùng điền đơn."""
    if not SAMPLE_ORDERS_CSV.exists():
        raise HTTPException(status_code=404, detail="chưa có file mẫu")
    return FileResponse(
        SAMPLE_ORDERS_CSV,
        media_type="text/csv; charset=utf-8",
        filename="don-hang-mau.csv",
    )


@app.get("/api/history")
def history_list(limit: int = Query(20, ge=1, le=100)) -> dict:
    return {"items": history_recent(limit)}


@app.get("/api/history/{plan_id}")
def history_detail(plan_id: int) -> dict:
    record = history_get(plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="không có bản ghi lịch sử này")
    return record


@app.get("/api/eta/info")
def eta_info() -> dict:
    model = eta_model()
    if model is None:
        return {"available": False, "hint": "chạy python ml/train_eta.py để có mô hình"}
    return {**model.as_dict(), "hour_multiplier": model.multiplier}


@app.get("/api/eta/predict")
def eta_predict(
    distance_km: float = Query(..., gt=0, le=60),
    hour: int = Query(8, ge=0, le=23),
    weekday: int = Query(2, ge=0, le=6),
) -> dict:
    model = eta_model()
    if model is None:
        raise HTTPException(503, "chưa có mô hình ETA")
    native = model.predict_native(distance_km, hour, weekday)
    return {
        "distance_km": distance_km,
        "hour": hour,
        "weekday": weekday,
        "eta_native_min": round(native, 1),
        "hour_factor": model.hour_factor(hour),
        "note": "eta_native_min theo miền dữ liệu huấn luyện (taxi đô thị); thời gian TP.HCM "
                "lấy từ OSRM nhân hour_factor.",
    }


@app.post("/api/incident")
def incident(payload: IncidentRequest) -> dict:
    """Gây sự cố rồi để tác tử xử lý; trả về số liệu trước và sau để so sánh."""
    data = _scenario(payload.seed, payload.orders, payload.vehicles)
    vehicle_ids = {vehicle["id"] for vehicle in data["vehicles"]}
    vehicle_id = payload.vehicle_id
    hub_id = payload.hub_id

    if payload.kind in ("breakdown", "truck_ban"):
        if not vehicle_id:
            raise _validation_error(
                f"Sự cố {payload.kind} cần vehicle_id. Các xe hiện có: {', '.join(sorted(vehicle_ids))}"
            )
        if vehicle_id not in vehicle_ids:
            raise _validation_error(f"vehicle_id '{vehicle_id}' không có trong kịch bản. Chọn một trong: {', '.join(sorted(vehicle_ids))}")

    if hub_id is not None and hub_id not in net.hubs:
        raise _validation_error(f"hub_id '{hub_id}' không tồn tại trong mạng 16 nút.")

    if payload.kind == "depot_closed" and not hub_id:
        counts: dict[str, int] = {}
        for vehicle in data["vehicles"]:
            counts[vehicle["start_hub"]] = counts.get(vehicle["start_hub"], 0) + 1
        hub_id = max(counts, key=counts.get)

    before = _baseline_metrics(data, payload.assignment, payload.routing)
    vehicles, orders = _copy_scenario(data)
    result = DispatcherAgent(
        net,
        vehicles,
        orders,
        assignment_strategy=payload.assignment,
        routing_strategy=payload.routing,
    ).handle_incident(payload.kind, vehicle_id, hub_id)
    record = {
        "before": before,
        "incident": {"kind": payload.kind, "vehicle_id": vehicle_id, "hub_id": hub_id},
        "orders": data["orders"],
        "vehicles": data["vehicles"],
        **result,
    }
    record["history_id"] = history_save("incident", payload.model_dump(), record)
    return record


@app.get("/api/compare")
def compare(
    seed: int = Query(7, ge=SEED_MIN, le=SEED_MAX),
    orders: int = Query(48, ge=ORDERS_MIN, le=ORDERS_MAX),
    vehicles: int = Query(8, ge=VEHICLES_MIN, le=VEHICLES_MAX),
) -> dict:
    data = _scenario(seed, orders, vehicles)
    return {
        "assignment": compare_strategies(net, data),
        "routing": compare_routing(net, data),
    }


@app.get("/api/rules")
def rules() -> dict:
    return {
        "rules": [
            {"id": r.id, "title": r.title, "clause": r.clause, "level": r.level, "priority": r.priority}
            for r in RULES
        ]
    }


@app.get("/api/geometry")
def geometry(a: str, b: str) -> dict:
    """Đường đi thật giữa hai nút để vẽ tuyến. Có cache trên đĩa, chỉ gọi OSRM một lần."""
    if a not in net.hubs or b not in net.hubs:
        raise HTTPException(404, "nút không tồn tại")
    key = f"{a}->{b}"
    with _locks["geometry"]:
        cache: dict = {}
        if GEOMETRY_CACHE.exists():
            try:
                cache = json.loads(GEOMETRY_CACHE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("File cache hình học hỏng, tạo lại từ đầu")
                cache = {}
        if key in cache:
            return cache[key]
        try:
            from data.build_matrix import leg_geometry

            hub_a, hub_b = net.hub(a), net.hub(b)
            payload = leg_geometry((hub_a.lat, hub_a.lon), (hub_b.lat, hub_b.lon))
        except Exception as exc:  # noqa: BLE001 — OSRM công cộng có thể chặn / mất mạng
            logger.warning("Không lấy được hình học %s: %s", key, exc)
            raise HTTPException(502, "không lấy được đường đi từ OSRM, thử lại sau") from exc
        cache[key] = payload
        GEOMETRY_CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = GEOMETRY_CACHE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, GEOMETRY_CACHE)
        return payload


@app.get("/")
def index():
    page = WEB_DIR / "index.html"
    if not page.exists():
        return {"message": "Giao diện đang được dựng, API đã sẵn sàng tại /docs"}
    return FileResponse(page)


if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")


