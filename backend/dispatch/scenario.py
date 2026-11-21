"""Sinh kịch bản vận hành: đội xe và lô đơn hàng trong một ca.

Toàn bộ dùng random có seed để mọi người (và giảng viên) tái lập được đúng kết quả.
Tên cửa hàng/đường lấy theo bối cảnh TP.HCM để kịch bản đọc lên thấy thật, không
phải "Order 1, Order 2".
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

from .network import Network

GOODS = [
    # (mã, nhãn hiển thị, khối lượng kg, thể tích L)
    ("tuoi_song", "Hàng tươi sống", 3.0, 8.0),
    ("dien_tu", "Điện tử", 1.2, 6.0),
    ("de_vo", "Dễ vỡ", 2.0, 12.0),
    ("thuong", "Hàng thường", 2.5, 10.0),
    ("cong_kenh", "Hàng cồng kềnh", 12.0, 60.0),
]

PRIORITIES = [
    ("hoa_toc", "Hoả tốc", 90),      # phút, cam kết giao
    ("tieu_chuan", "Tiêu chuẩn", 240),
    ("tiet_kiem", "Tiết kiệm", 480),
]

SHOPS = [
    ("Tạp hoá Cô Bảy", "0903 118 2xx"),
    ("Điện thoại Minh Khang", "0918 442 7xx"),
    ("Tiệm bánh Hồng Ngọc", "0932 771 0xx"),
    ("Nhà thuốc An Tâm", "0909 336 5xx"),
    ("Cà phê Bệt Sài Gòn", "0977 210 8xx"),
    ("Shop quần áo 79", "0968 554 3xx"),
    ("Vựa trái cây Út Hậu", "0913 887 6xx"),
    ("Điện máy Chợ Lớn", "0907 665 1xx"),
    ("Nhà sách Trí Tuệ", "0938 004 9xx"),
    ("Mắt kính Sài Gòn", "0912 447 2xx"),
    ("Bánh mì Huỳnh Hoa", "0908 331 7xx"),
    ("Trà sữa Nhà Làm", "0989 112 4xx"),
    ("Thiết bị văn phòng Tín Phát", "0919 556 0xx"),
    ("Gạo ST25 Cô Út", "0937 220 5xx"),
    ("Phụ tùng xe máy Thanh Niên", "0902 774 6xx"),
    ("Đồ chơi trẻ em Bảo Ngọc", "0965 883 1xx"),
]

STREETS = {
    "q1": ["Lý Tự Trọng", "Nguyễn Trãi", "Cách Mạng Tháng 8", "Pasteur"],
    "q3": ["Võ Văn Tần", "Nguyễn Thị Minh Khai", "Kỳ Đồng", "Bàn Cờ"],
    "q5": ["Trần Hưng Đạo", "Nguyễn Trãi", "Hải Thượng Lãn Ông", "Châu Văn Liêm"],
    "q10": ["Tô Hiến Thành", "Sư Vạn Hạnh", "Nguyễn Tri Phương", "Lý Thường Kiệt"],
    "go-vap": ["Quang Trung", "Nguyễn Oanh", "Phan Văn Trị", "Lê Đức Thọ"],
    "thu-duc": ["Võ Văn Ngân", "Đặng Văn Bi", "Tô Ngọc Vân", "Kha Vạn Cân"],
    "nha-be": ["Huỳnh Tấn Phát", "Nguyễn Hữu Thọ", "Đào Sư Tích", "Lê Văn Lương"],
    "q7": ["Nguyễn Thị Thập", "Huỳnh Tấn Phát", "Nguyễn Văn Linh", "Lê Văn Thiêm"],
    "binh-thanh": ["Xô Viết Nghệ Tĩnh", "Điện Biên Phủ", "Nơ Trang Long", "Phan Đăng Lưu"],
    "tan-phu": ["Tân Kỳ Tân Quý", "Luỹ Bán Bích", "Hoà Bình", "Thoại Ngọc Hầu"],
    "tan-binh": ["Cộng Hoà", "Trường Chinh", "Bạch Đằng", "Út Tịch"],
    "binh-dien": ["Quốc lộ 1A", "Nguyễn Văn Linh", "Trần Đại Nghĩa"],
    "hoc-mon": ["Quốc lộ 22", "Nguyễn Ảnh Thủ", "Tô Ký"],
    "tsn": ["Hồng Hà", "Bạch Đằng", "Trường Sơn"],
    "cat-lai": ["Nguyễn Thị Định", "Đồng Văn Cống", "Võ Chí Công"],
    "song-than": ["Quốc lộ 1K", "Nguyễn Thị Minh Khai"],
}

DEPOTS = ["cat-lai", "song-than", "tan-binh", "q7"]


@dataclass
class Vehicle:
    id: str
    plate: str
    driver: str
    kind: str                    # xe_may | xe_tai_nho | xe_tai
    label: str
    capacity_kg: float
    capacity_l: float
    start_hub: str
    shift_start: str = "07:30"
    speed_factor: float = 1.0    # hệ số nhân thời gian OSRM (xe máy chen chúc hơn)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Order:
    id: str
    code: str
    shop: str
    phone: str
    address: str
    dest_hub: str                # nút mạng dùng để định tuyến
    lat: float                   # vị trí thật (lệch nhẹ so với nút) để hiển thị
    lon: float
    weight_kg: float
    volume_l: float
    goods: str
    goods_label: str
    cod: int
    priority: str
    priority_label: str
    promised_min: int
    created_at: str
    service_min: float = 5.0

    def as_dict(self) -> dict:
        return asdict(self)


VEHICLE_PRESETS = [
    ("xe_may", "Xe máy", 30.0, 45.0, 1.18),
    ("xe_may", "Xe máy", 30.0, 45.0, 1.12),
    ("xe_may", "Xe máy", 30.0, 45.0, 1.15),
    ("xe_may", "Xe máy", 30.0, 45.0, 1.10),
    ("xe_tai_nho", "Xe tải nhỏ 500kg", 500.0, 1500.0, 1.05),
    ("xe_tai_nho", "Xe tải nhỏ 500kg", 500.0, 1500.0, 1.05),
    ("xe_tai", "Xe tải 1.5 tấn", 1500.0, 6000.0, 1.0),
    ("xe_tai", "Xe tải 1.5 tấn", 1500.0, 6000.0, 1.0),
]

DRIVERS = [
    "Trần Văn Hùng", "Nguyễn Minh Tuấn", "Lê Thị Kim Oanh", "Phạm Quốc Bảo",
    "Võ Thành Đạt", "Huỳnh Ngọc Sơn", "Đặng Văn Lâm", "Bùi Thanh Phong",
]


def _plate(rng: random.Random) -> str:
    letter = rng.choice("ABCDEFGH")
    return f"51{letter}-{rng.randint(100, 999)}.{rng.randint(10, 99)}"


def build_vehicles(rng: random.Random, count: int = 8) -> list[Vehicle]:
    presets = VEHICLE_PRESETS[:count]
    vehicles: list[Vehicle] = []
    for i, (kind, label, cap_kg, cap_l, factor) in enumerate(presets, start=1):
        vehicles.append(
            Vehicle(
                id=f"XE-{i:02d}",
                plate=_plate(rng),
                driver=DRIVERS[(i - 1) % len(DRIVERS)],
                kind=kind,
                label=label,
                capacity_kg=cap_kg,
                capacity_l=cap_l,
                start_hub=rng.choice(DEPOTS) if kind == "xe_tai" else rng.choice(["q1", "q3", "q10", "binh-thanh", "tan-binh"]),
                speed_factor=factor,
            )
        )
    return vehicles


def build_orders(net: Network, rng: random.Random, count: int, start: datetime) -> list[Order]:
    """Sinh đơn: 60% rơi vào các bưu cục nội thành, 40% rải ra ngoại thành cho đa dạng."""
    inner = ["q1", "q3", "q5", "q10", "go-vap", "binh-thanh", "tan-phu", "thu-duc"]
    outer = ["nha-be", "q7", "hoc-mon", "binh-dien"]
    orders: list[Order] = []
    for i in range(1, count + 1):
        hub_id = rng.choice(inner) if rng.random() < 0.6 else rng.choice(outer)
        hub = net.hub(hub_id)
        # Lệch ngẫu nhiên ~0.3–1.1 km quanh nút để điểm giao không trùng nhau trên bản đồ
        radius = rng.uniform(0.003, 0.010)
        angle = rng.uniform(0, 2 * math.pi)
        lat = hub.lat + radius * math.sin(angle)
        lon = hub.lon + radius * math.cos(angle) / math.cos(math.radians(hub.lat))

        goods, goods_label, w, v = rng.choice(GOODS)
        priority, priority_label, promised = rng.choices(PRIORITIES, weights=[0.22, 0.6, 0.18])[0]
        shop, phone = rng.choice(SHOPS)
        street = rng.choice(STREETS.get(hub_id, ["Quốc lộ 1A"]))
        created = start + timedelta(minutes=rng.randint(-25, 55))

        weight = round(w * rng.uniform(0.6, 1.9), 1)
        volume = round(v * rng.uniform(0.7, 1.6), 1)
        cod = 0 if rng.random() < 0.35 else rng.choice([89_000, 145_000, 249_000, 380_000, 520_000, 1_250_000, 2_900_000, 6_400_000])
        # Hàng tươi sống phải tới tay người nhận trong 2 giờ, hạn giao thực tế bị siết lại
        promised_effective = min(promised, 110) if goods == "tuoi_song" else promised

        orders.append(
            Order(
                id=f"DD{1000 + i}",
                code=f"DD-{start:%d%m}-{1000 + i}",
                shop=shop,
                phone=phone,
                address=f"{rng.randint(12, 480)} {street}, {hub.district}",
                dest_hub=hub_id,
                lat=round(lat, 6),
                lon=round(lon, 6),
                weight_kg=weight,
                volume_l=volume,
                goods=goods,
                goods_label=goods_label,
                cod=cod,
                priority=priority,
                priority_label=priority_label,
                promised_min=promised_effective,
                created_at=created.strftime("%H:%M"),
                service_min=round(rng.uniform(3.0, 7.0), 1),
            )
        )
    return orders


def build_scenario(net: Network, seed: int = 7, n_orders: int = 48, n_vehicles: int = 8) -> dict:
    rng = random.Random(seed)
    start = datetime.strptime("2026-11-21 08:00", "%Y-%m-%d %H:%M")
    vehicles = build_vehicles(rng, n_vehicles)
    orders = build_orders(net, rng, n_orders, start)
    return {
        "seed": seed,
        "started_at": start.strftime("%Y-%m-%dT%H:%M"),
        "vehicles": [v.as_dict() for v in vehicles],
        "orders": [o.as_dict() for o in orders],
    }
