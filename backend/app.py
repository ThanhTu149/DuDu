"""API của DuDu — bốn module thuật toán phơi ra cho giao diện gọi."""

from __future__ import annotations

import json
import random
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .dispatch.agent import DispatcherAgent
from .dispatch.evaluate import compare_routing, compare_strategies
from .dispatch.network import load_network
from .dispatch.routing import BASE_MINUTE, clock_label
from .dispatch.rules import RULES
from .dispatch.scenario import build_scenario

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
GEOMETRY_CACHE = ROOT / "data" / "processed" / "geometry.json"

app = FastAPI(title="DuDu Dispatch API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

net = load_network()
_scenarios: dict[tuple[int, int, int], dict] = {}
_eta_model = None


def eta_model():
    """Nạp mô hình ETA một lần; nếu chưa huấn luyện thì trả None (hệ thống vẫn chạy)."""
    global _eta_model
    if _eta_model is None:
        try:
            import sys

            sys.path.insert(0, str(ROOT))
            from ml.eta_model import EtaModel

            _eta_model = EtaModel.load() or False
        except Exception:  # noqa: BLE001 — thiếu model không được làm sập API
            _eta_model = False
    return _eta_model or None


def _scenario(seed: int, orders: int, vehicles: int) -> dict:
    key = (seed, orders, vehicles)
    if key not in _scenarios:
        _scenarios[key] = build_scenario(net, seed=seed, n_orders=orders, n_vehicles=vehicles)
    return _scenarios[key]


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "hubs": len(net.order), "rules": len(RULES)}


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
def scenario(seed: int = 7, orders: int = Query(48, ge=8, le=200), vehicles: int = Query(8, ge=2, le=8)) -> dict:
    data = _scenario(seed, orders, vehicles)
    return {**data, "start_label": clock_label(BASE_MINUTE)}


@app.post("/api/plan")
def plan(payload: dict | None = None) -> dict:
    payload = payload or {}
    seed = int(payload.get("seed", 7))
    orders = int(payload.get("orders", 48))
    vehicles = int(payload.get("vehicles", 8))
    data = _scenario(seed, orders, vehicles)
    agent = DispatcherAgent(
        net,
        data["vehicles"],
        data["orders"],
        assignment_strategy=payload.get("assignment", "hungarian"),
        routing_strategy=payload.get("routing", "deadline"),
        eta_model=eta_model() if payload.get("eta", "osrm") == "ml" else None,
    )
    result = agent.plan()
    result["seed"] = seed
    result["start_label"] = clock_label(BASE_MINUTE)
    return result


@app.get("/api/eta/info")
def eta_info() -> dict:
    model = eta_model()
    if model is None:
        return {"available": False, "hint": "chạy python ml/train_eta.py để có mô hình"}
    return {**model.as_dict(), "hour_multiplier": model.multiplier}


@app.get("/api/eta/predict")
def eta_predict(distance_km: float = Query(..., gt=0, le=60), hour: int = Query(8, ge=0, le=23), weekday: int = Query(2, ge=0, le=6)) -> dict:
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
def incident(payload: dict) -> dict:
    """Gây sự cố rồi để tác tử xử lý; trả về số liệu trước và sau để so sánh."""
    kind = payload.get("kind", "breakdown")
    vehicle_id = payload.get("vehicle_id")
    hub_id = payload.get("hub_id")
    seed = int(payload.get("seed", 7))
    data = _scenario(seed, int(payload.get("orders", 48)), int(payload.get("vehicles", 8)))
    options = {
        "assignment_strategy": payload.get("assignment", "hungarian"),
        "routing_strategy": payload.get("routing", "deadline"),
    }

    if kind == "depot_closed" and not hub_id:
        counts: dict[str, int] = {}
        for vehicle in data["vehicles"]:
            counts[vehicle["start_hub"]] = counts.get(vehicle["start_hub"], 0) + 1
        hub_id = max(counts, key=counts.get)

    before = DispatcherAgent(net, data["vehicles"], data["orders"], **options).plan()["metrics"]

    agent = DispatcherAgent(net, data["vehicles"], data["orders"], **options)
    result = agent.handle_incident(kind, vehicle_id, hub_id)
    return {
        "before": before,
        "incident": {"kind": kind, "vehicle_id": vehicle_id, "hub_id": hub_id},
        **result,
    }


@app.get("/api/compare")
def compare(seed: int = 7, orders: int = Query(48, ge=8, le=200), vehicles: int = Query(8, ge=2, le=8)) -> dict:
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
    cache: dict = json.loads(GEOMETRY_CACHE.read_text(encoding="utf-8")) if GEOMETRY_CACHE.exists() else {}
    key = f"{a}->{b}"
    if key not in cache:
        from data.build_matrix import leg_geometry

        hub_a, hub_b = net.hub(a), net.hub(b)
        cache[key] = leg_geometry((hub_a.lat, hub_a.lon), (hub_b.lat, hub_b.lon))
        GEOMETRY_CACHE.parent.mkdir(parents=True, exist_ok=True)
        GEOMETRY_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache[key]


@app.get("/")
def index():
    page = WEB_DIR / "index.html"
    if not page.exists():
        return {"message": "Giao diện đang được dựng, API đã sẵn sàng tại /docs"}
    return FileResponse(page)


if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")
