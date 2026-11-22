"""Kiểm thử từng luật trong cơ sở tri thức R01–R12 và cơ chế ưu tiên của engine.

Mỗi luật có một ca dương (kích hoạt đúng) và một ca âm (sự kiện trung tính không kích hoạt);
thêm các ca kiểm tra thứ tự ưu tiên và việc dừng suy diễn sau luật mức "chặn".
"""

from __future__ import annotations

import unittest

from backend.dispatch.rules import Facts, RULES, RuleEngine

ENGINE = RuleEngine()


def make_facts(**overrides) -> Facts:
    order = {
        "id": "DD-1001",
        "goods": "thuong",
        "goods_label": "Hàng thường",
        "volume_l": 10.0,
        "weight_kg": 2.0,
        "cod": 0,
        "priority": "thuong",
        "priority_label": "Thường",
        "promised_min": 120,
    }
    vehicle = {
        "id": "XE-01",
        "kind": "xe_may",
        "label": "Xe máy",
        "driver": "Nguyễn Văn A",
        "plate": "51A-123.45",
        "capacity_kg": 30.0,
        "capacity_l": 45.0,
    }
    base = {
        "order": order,
        "vehicle": vehicle,
        "arrive_min": 8 * 60 + 30,
        "district": "Quận 1",
        "stop_index": 0,
        "stop_count": 1,
    }
    for key, value in overrides.items():
        if key == "order":
            order.update(value)
        elif key == "vehicle":
            vehicle.update(value)
        else:
            base[key] = value
    return Facts(**base)


def fired_ids(facts: Facts) -> list[str]:
    return [verdict.rule_id for verdict in ENGINE.evaluate(facts)]


class TestRuleCatalogue(unittest.TestCase):
    def test_twelve_unique_rules(self) -> None:
        self.assertEqual(len(RULES), 12)
        self.assertEqual(len({rule.id for rule in RULES}), 12)
        self.assertEqual({rule.id for rule in RULES}, {f"R{index:02d}" for index in range(1, 13)})

    def test_every_rule_has_clause_and_level(self) -> None:
        for rule in RULES:
            self.assertIn("NẾU", rule.clause, rule.id)
            self.assertIn(rule.level, {"chan", "canh_bao", "uu_tien"}, rule.id)
            self.assertTrue(rule.title.strip(), rule.id)


class TestEachRuleFires(unittest.TestCase):
    """Mỗi luật phải kích hoạt đúng ca dương của nó."""

    def assert_rule(self, rule_id: str, facts: Facts) -> None:
        self.assertIn(rule_id, fired_ids(facts))

    def test_r01_fresh_goods_over_two_hours(self) -> None:
        self.assert_rule("R01", make_facts(order={"goods": "tuoi_song"}, arrive_min=8 * 60 + 121))

    def test_r02_truck_ban_hours(self) -> None:
        self.assert_rule("R02", make_facts(vehicle={"kind": "xe_tai"}, district="Quận 3", arrive_min=7 * 60))

    def test_r03_bulky_on_motorcycle(self) -> None:
        self.assert_rule("R03", make_facts(order={"volume_l": 60.0}, vehicle={"kind": "xe_may"}))

    def test_r04_large_cod(self) -> None:
        self.assert_rule("R04", make_facts(order={"cod": 6_000_000}))

    def test_r05_express_late(self) -> None:
        self.assert_rule(
            "R05",
            make_facts(order={"priority": "hoa_toc", "promised_min": 60}, arrive_min=8 * 60 + 80),
        )

    def test_r06_too_many_stops(self) -> None:
        self.assert_rule("R06", make_facts(vehicle={"kind": "xe_may"}, stop_count=13, stop_index=12))

    def test_r07_fragile_on_motorcycle_with_long_route(self) -> None:
        self.assert_rule("R07", make_facts(order={"goods": "de_vo"}, vehicle={"kind": "xe_may"}, stop_count=7))

    def test_r08_over_capacity(self) -> None:
        self.assert_rule("R08", make_facts(vehicle={"_load_kg": 40.0, "capacity_kg": 30.0}))

    def test_r09_high_value_electronics(self) -> None:
        self.assert_rule("R09", make_facts(order={"goods": "dien_tu", "cod": 2_000_000}))

    def test_r10_route_over_four_hours(self) -> None:
        self.assert_rule("R10", make_facts(stop_index=0, stop_count=1, arrive_min=8 * 60 + 250))

    def test_r11_outer_district_after_rush(self) -> None:
        self.assert_rule("R11", make_facts(district="Nhà Bè", arrive_min=17 * 60 + 30))

    def test_r12_heavy_parcel_on_motorcycle(self) -> None:
        self.assert_rule("R12", make_facts(order={"weight_kg": 9.0}, vehicle={"kind": "xe_may"}))


class TestNeutralFacts(unittest.TestCase):
    def test_neutral_order_triggers_nothing(self) -> None:
        self.assertEqual(fired_ids(make_facts()), [])

    def test_fresh_goods_within_window_not_blocked(self) -> None:
        self.assertEqual(fired_ids(make_facts(order={"goods": "tuoi_song"}, arrive_min=8 * 60 + 100)), [])

    def test_truck_outside_ban_hours_not_blocked(self) -> None:
        self.assertEqual(fired_ids(make_facts(vehicle={"kind": "xe_tai"}, district="Quận 1", arrive_min=10 * 60)), [])

    def test_light_parcel_on_motorcycle_not_blocked(self) -> None:
        self.assertEqual(fired_ids(make_facts(order={"weight_kg": 3.0}, vehicle={"kind": "xe_may"})), [])


class TestInferenceControl(unittest.TestCase):
    def test_blocking_rule_stops_inference(self) -> None:
        # R08 (ưu tiên 0, mức chặn) phải đứng trước R12 (ưu tiên 11) và R03 (ưu tiên 3)
        facts = make_facts(
            order={"weight_kg": 12.0, "volume_l": 60.0},
            vehicle={"_load_kg": 40.0, "capacity_kg": 30.0, "kind": "xe_may"},
        )
        ids = fired_ids(facts)
        self.assertEqual(ids[0], "R08")
        self.assertNotIn("R12", ids)
        self.assertNotIn("R03", ids)

    def test_warnings_can_stack_but_stop_after_first_block(self) -> None:
        # Hoả tốc trễ (R05) + COD lớn (R04) đều là cảnh báo → hiện cả hai
        facts = make_facts(order={"priority": "hoa_toc", "promised_min": 60, "cod": 6_000_000}, arrive_min=8 * 60 + 80)
        ids = fired_ids(facts)
        self.assertIn("R04", ids)
        self.assertIn("R05", ids)

    def test_verdict_carries_context_for_explanation(self) -> None:
        facts = make_facts(order={"cod": 6_000_000, "id": "DD-9999"})
        verdict = next(item for item in ENGINE.evaluate(facts) if item.rule_id == "R04")
        self.assertEqual(verdict.order_id, "DD-9999")
        self.assertTrue(verdict.detail.strip())
        self.assertEqual(verdict.level, "canh_bao")


if __name__ == "__main__":
    unittest.main()
