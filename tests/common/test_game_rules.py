#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cm-12 game_rules 的測試（A1b）。"""
import unittest

from travian_bot.common import game_rules as gr
from travian_bot.common.schema import ValidationError
from travian_bot.common.server_profile import profile_from_dict


def _profile(speed=1, protection=None):
    return profile_from_dict({"server_id": "s1", "base_url": "https://ts1.example.com", "tribe": "gaul",
                              "start_utc": "2026-11-02T08:15:30Z", "server_tz": "UTC", "speed": speed,
                              "protection_days": protection})


class CpRequiredTest(unittest.TestCase):
    def test_anchors_from_official_table(self):
        p1 = _profile(1)
        self.assertEqual(gr.cp_required(1, p1), 0)
        self.assertEqual(gr.cp_required(2, p1), 2000)
        self.assertEqual(gr.cp_required(3, p1), 8000)
        self.assertEqual(gr.cp_required(10, p1), 251000)
        self.assertEqual(gr.cp_required(20, p1), 1397000)
        self.assertEqual(gr.cp_required(50, p1), 12347000)
        self.assertEqual(gr.cp_required(2, _profile(2)), 800)
        self.assertEqual(gr.cp_required(2, _profile(3)), 500)
        self.assertEqual(gr.cp_required(2, _profile(5)), 300)
        self.assertEqual(gr.cp_required(2, _profile(10)), 200)
        self.assertEqual(gr.cp_required(21, _profile(3)), 524000)

    def test_tables_are_complete_and_increasing(self):
        for speed in gr.CP_TABLE_SPEEDS:
            p = _profile(speed)
            values = [gr.cp_required(n, p) for n in range(1, 51)]
            with self.subTest(speed=speed):
                self.assertEqual(values[0], 0)
                self.assertTrue(all(b > a for a, b in zip(values, values[1:])))

    def test_x10_is_one_tenth_of_x1(self):
        # 官方表的內部一致性：抄錯任何一格都會被抓到
        p1, p10 = _profile(1), _profile(10)
        for n in range(1, 51):
            with self.subTest(n=n):
                self.assertEqual(gr.cp_required(n, p1), gr.cp_required(n, p10) * 10)

    def test_unsupported_speed_is_rejected_not_interpolated(self):
        for speed in (4, 6, 8, 100):
            with self.subTest(speed=speed):
                with self.assertRaises(ValidationError) as cm:
                    gr.cp_required(2, _profile(speed))
                self.assertEqual(cm.exception.rule, "unsupported_speed")

    def test_village_count_range(self):
        for bad in (0, -1, 51, 2.5, True, None, "2"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError) as cm:
                    gr.cp_required(bad, _profile(1))
                self.assertEqual(cm.exception.rule, "range")


class FieldCapTest(unittest.TestCase):
    def test_caps(self):
        self.assertEqual(gr.resource_field_cap(False), 10)
        self.assertEqual(gr.MAX_NON_CAPITAL_FIELD_LEVEL, 10)
        self.assertIsNone(gr.resource_field_cap(True))     # 首都沒有可靠資料，不當成無限

    def test_type(self):
        for bad in (0, 1, None, "no"):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    gr.resource_field_cap(bad)


class SettleTest(unittest.TestCase):
    def test_requirements(self):
        r = gr.settle_requirements()
        self.assertEqual(r.settlers, 3)
        self.assertEqual(r.cost_each, (750, 750, 750, 750))
        self.assertEqual(r.cp_checked_at, ("send", "arrive"))
        by_gid = {s.gid: s for s in r.slot_sources}
        self.assertEqual((by_gid[25].slots, by_gid[26].slots, by_gid[44].slots), (2, 3, 3))   # ✓ 官方「Expansion Slots」
        self.assertEqual(by_gid[25].levels, (10, 20))
        self.assertEqual(by_gid[26].levels, (10, 15, 20))
        self.assertEqual(by_gid[44].levels, ())
        self.assertTrue(all(not s.levels_verified for s in r.slot_sources))
        self.assertTrue(all(len(s.levels) in (0, s.slots) or s.gid == 26 for s in r.slot_sources))


class ProtectionTest(unittest.TestCase):
    def test_explicit_value_wins(self):
        self.assertEqual(gr.default_protection_days(_profile(protection=7)), 7)
        self.assertEqual(gr.default_protection_days(_profile(speed=10, protection=0)), 0)

    def test_official_base_days_when_blank(self):
        self.assertEqual([gr.default_protection_days(_profile(s)) for s in (1, 2, 3, 5, 10)], [5, 3, 3, 2, 1])

    def test_unknown_speed_is_none(self):
        self.assertIsNone(gr.default_protection_days(_profile(4)))
        self.assertEqual(gr.default_protection_days(_profile(4, protection=2)), 2)


class SpeedRulesTest(unittest.TestCase):
    def test_official_factors(self):
        got = {s: gr.speed_rules(_profile(s)) for s in gr.CP_TABLE_SPEEDS}
        self.assertEqual([got[s].production_factor for s in (1, 2, 3, 5, 10)], [1, 2, 3, 5, 10])
        self.assertEqual([got[s].build_divisor for s in (1, 2, 3, 5, 10)], [1, 2, 3, 5, 10])
        self.assertEqual([got[s].train_divisor for s in (1, 2, 3, 5, 10)], [1, 2, 3, 5, 10])
        self.assertEqual([got[s].start_cp for s in (1, 2, 3, 5, 10)], [500, 250, 167, 100, 50])
        self.assertEqual([got[s].protection_extension_days for s in (1, 2, 3, 5, 10)], [3, 3, 3, 2, 1])

    def test_troop_speed_factor_is_not_the_server_speed(self):
        self.assertEqual([gr.speed_rules(_profile(s)).troop_speed_factor for s in (1, 2, 3, 5, 10)], [1, 2, 2, 2, 4])

    def test_covers_exactly_the_cp_table_speeds(self):
        self.assertEqual(tuple(sorted(gr._SPEED_RULES)), gr.CP_TABLE_SPEEDS)

    def test_unsupported_speed(self):
        for speed in (4, 6, 100):
            with self.subTest(speed=speed):
                with self.assertRaises(ValidationError) as cm:
                    gr.speed_rules(_profile(speed))
                self.assertEqual(cm.exception.rule, "unsupported_speed")

    def test_start_cp_matches_second_village_order_of_magnitude(self):
        for s in gr.CP_TABLE_SPEEDS:
            self.assertLess(gr.speed_rules(_profile(s)).start_cp, gr.cp_required(2, _profile(s)))


class ProductionTableTest(unittest.TestCase):
    def test_marked_unverified_data_only(self):
        self.assertEqual(gr.RESOURCE_FIELD_PRODUCTION_1X[10], 200)
        self.assertEqual(gr.RESOURCE_FIELD_PRODUCTION_1X[9], 145)
        self.assertFalse(hasattr(gr, "field_production"))


if __name__ == "__main__":
    unittest.main()
