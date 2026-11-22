"""Nhập đơn hàng từ CSV do người dùng cung cấp.

Mục đích: web không chỉ chạy kịch bản sinh theo seed mà còn nhận được danh sách đơn thật
(tối đa 200 dòng) từ file CSV. Dữ liệu được kiểm tra từng dòng; dòng lỗi bị bỏ qua kèm cảnh
báo chứ không làm hỏng cả lần nhập.

Cột bắt buộc (chấp nhận cả tiêu đề tiếng Việt có/không dấu và tiếng Anh):

| Cột | Bí danh | Ý nghĩa |
|---|---|---|
| `diem_giao` | `dest_hub`, `diem_den`, `hub` | mã nút giao (q1, q3, q10, binh-thanh, …) hoặc đúng tên nút |
| `khoi_luong_kg` | `weight_kg`, `khoi_luong` | khối lượng kiện, 0,1–2000 kg |
| `the_tich_l` | `volume_l`, `the_tich` | thể tích kiện, 0,5–10000 L |

Cột tuỳ chọn: `ma_don`, `hang_hoa` (tuoi_song/dien_tu/de_vo/thuong/cong_kenh), `cod`,
`uu_tien` (hoa_toc/tieu_chuan/tiet_kiem), `hen_giao_phut`, `dich_vu_phut`, `dia_chi`,
`cua_hang`, `dien_thoai`.

File mẫu: `data/samples/don-hang-mau.csv`.
"""

from __future__ import annotations

import csv
import io
import math
import random

from .network import Network
from .scenario import GOODS, PRIORITIES, SHOPS, STREETS

MAX_IMPORT_ROWS = 200
GOODS_LABELS = {code: label for code, label, _, _ in GOODS}
PRIORITY_PROMISED = {code: promised for code, _, promised in PRIORITIES}
PRIORITY_LABELS = {code: label for code, label, _ in PRIORITIES}

HEADER_ALIASES = {
    "diem_giao": {"diem_giao", "diem den", "diem_den", "dest_hub", "hub", "diem"},
    "khoi_luong_kg": {"khoi_luong_kg", "khoi luong", "khoi_luong", "weight_kg", "weight", "kg"},
    "the_tich_l": {"the_tich_l", "the tich", "the_tich", "volume_l", "volume", "lit"},
    "ma_don": {"ma_don", "ma don", "order_id", "id", "ma"},
    "hang_hoa": {"hang_hoa", "hang hoa", "goods", "loai_hang"},
    "cod": {"cod", "thu_ho", "tien_thu_ho"},
    "uu_tien": {"uu_tien", "uu tien", "priority", "loai_don"},
    "hen_giao_phut": {"hen_giao_phut", "hen giao", "promised_min", "sla_phut"},
    "dich_vu_phut": {"dich_vu_phut", "dich vu", "service_min", "phut_phuc_vu"},
    "dia_chi": {"dia_chi", "dia chi", "address"},
    "cua_hang": {"cua_hang", "cua hang", "shop"},
    "dien_thoai": {"dien_thoai", "dien thoai", "phone", "sdt"},
}

# Chuẩn hoá tiêu đề: bỏ khoảng trắng/gạch dưới, đưa về dạng không dấu để so khớp dễ.
STRIP_CHARS = str.maketrans({"_": " ", "-": " ", ".": " "})


def _normalize_header(raw: str) -> str:
    return " ".join(raw.strip().lower().translate(STRIP_CHARS).split())


def _header_map(fieldnames: list[str] | None) -> dict[str, str]:
    """Ánh xạ tên cột chuẩn → tên cột thực tế trong file."""
    actual = {_normalize_header(name): name for name in (fieldnames or []) if name}
    result: dict[str, str] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        normalized_aliases = {_normalize_header(alias) for alias in aliases}
        for alias in normalized_aliases:
            if alias in actual:
                result[canonical] = actual[alias]
                break
    return result


def _hub_lookup(net: Network) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for hub in net.hubs.values():
        lookup[hub.id.lower()] = hub.id
        lookup[hub.name.strip().lower()] = hub.id
    return lookup


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(raw: str | None) -> int | None:
    value = _to_float(raw)
    return int(value) if value is not None and value >= 0 else None


def parse_orders_csv(text: str, net: Network, seed: int = 7) -> dict:
    """Đọc CSV và trả về {"orders": [...], "warnings": [...], "count": int}.

    Ném ValueError nếu không đọc được tiêu đề, thiếu cột bắt buộc, hoặc không có dòng hợp lệ.
    """
    if not text or not text.strip():
        raise ValueError("file CSV rỗng")
    if len(text) > 200_000:
        raise ValueError("file CSV quá lớn (giới hạn 200 KB)")

    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    mapping = _header_map(reader.fieldnames)
    missing = [key for key in ("diem_giao", "khoi_luong_kg", "the_tich_l") if key not in mapping]
    if missing:
        raise ValueError(
            "thiếu cột bắt buộc: " + ", ".join(missing)
            + " (xem file mẫu /api/orders/template)"
        )

    hubs = _hub_lookup(net)
    orders: list[dict] = []
    warnings: list[str] = []
    used_ids: set[str] = set()
    index = 0

    for line_number, row in enumerate(reader, start=2):
        if index >= MAX_IMPORT_ROWS:
            warnings.append(f"chỉ nhận tối đa {MAX_IMPORT_ROWS} đơn — các dòng sau bị bỏ qua")
            break
        raw_hub = str(row.get(mapping["diem_giao"], "") or "").strip()
        weight = _to_float(row.get(mapping["khoi_luong_kg"]))
        volume = _to_float(row.get(mapping["the_tich_l"]))

        hub_id = hubs.get(raw_hub.lower())
        if not hub_id:
            warnings.append(f"dòng {line_number}: điểm giao '{raw_hub}' không có trong mạng 16 nút — bỏ qua")
            continue
        if weight is None or not (0.1 <= weight <= 2000):
            warnings.append(f"dòng {line_number}: khối lượng phải trong 0,1–2000 kg — bỏ qua")
            continue
        if volume is None or not (0.5 <= volume <= 10000):
            warnings.append(f"dòng {line_number}: thể tích phải trong 0,5–10000 L — bỏ qua")
            continue

        goods = str(row.get(mapping.get("hang_hoa", ""), "") or "").strip().lower() or "thuong"
        if goods not in GOODS_LABELS:
            warnings.append(f"dòng {line_number}: hàng hoá '{goods}' không hợp lệ, dùng 'thuong'")
            goods = "thuong"

        priority = str(row.get(mapping.get("uu_tien", ""), "") or "").strip().lower() or "tieu_chuan"
        if priority not in PRIORITY_LABELS:
            warnings.append(f"dòng {line_number}: ưu tiên '{priority}' không hợp lệ, dùng 'tieu_chuan'")
            priority = "tieu_chuan"

        promised = _to_int(row.get(mapping.get("hen_giao_phut", "")))
        if promised is None or not (15 <= promised <= 720):
            promised = PRIORITY_PROMISED[priority]
        service = _to_float(row.get(mapping.get("dich_vu_phut", "")))
        if service is None or not (1 <= service <= 60):
            service = 5.0
        cod = _to_int(row.get(mapping.get("cod", ""))) or 0
        cod = min(cod, 1_000_000_000)

        raw_id = str(row.get(mapping.get("ma_don", ""), "") or "").strip()
        order_id = raw_id[:32] if raw_id else f"DD-IMPORT-{index + 1:03d}"
        while order_id in used_ids:
            order_id = f"{order_id}-{index + 1}"
        used_ids.add(order_id)

        hub = net.hub(hub_id)
        rng = random.Random(f"{seed}:{line_number}:{order_id}")
        radius = rng.uniform(0.003, 0.010)
        angle = rng.uniform(0, 2 * math.pi)
        lat = hub.lat + radius * math.sin(angle)
        lon = hub.lon + radius * math.cos(angle) / math.cos(math.radians(hub.lat))
        shop, phone = rng.choice(SHOPS)
        street = rng.choice(STREETS.get(hub_id, ["Quốc lộ 1A"]))
        address = str(row.get(mapping.get("dia_chi", ""), "") or "").strip()
        if not address:
            address = f"{rng.randint(12, 480)} {street}, {hub.district}"

        orders.append({
            "id": order_id,
            "code": order_id if order_id.startswith("DD-") else f"DD-{order_id}",
            "shop": str(row.get(mapping.get("cua_hang", ""), "") or "").strip() or shop,
            "phone": str(row.get(mapping.get("dien_thoai", ""), "") or "").strip() or phone,
            "address": address,
            "dest_hub": hub_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "weight_kg": round(weight, 1),
            "volume_l": round(volume, 1),
            "goods": goods,
            "goods_label": GOODS_LABELS[goods],
            "cod": cod,
            "priority": priority,
            "priority_label": PRIORITY_LABELS[priority],
            "promised_min": promised,
            "created_at": "08:00",
            "service_min": round(service, 1),
        })
        index += 1

    if not orders:
        raise ValueError("không có dòng hợp lệ nào — kiểm tra lại cột điểm giao/khối lượng/thể tích")
    return {"orders": orders, "warnings": warnings[:20], "count": len(orders)}
