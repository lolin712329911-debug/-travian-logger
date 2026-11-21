#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cm-06 tribe_data 的測試（A1b）＋種族煙霧測試：每個登記的種族都走一遍公開介面。"""
import dataclasses
import json
import unittest
from pathlib import Path

from travian_bot.common import tribe_data as td
from travian_bot.common.schema import ValidationError


GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "common" / "tribe_data"


def _golden(name):
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


class GoldenAgainstOldDispatchTest(unittest.TestCase):
    """golden＝舊 dispatch.py v1.8 的離線輸出（舊鍵 gauls→gaul、t1→u1 對應後比對）。"""

    def test_resolve_tribe(self):
        for c in _golden("resolve_tribe.expected.json")["cases"]:
            with self.subTest(case=c):
                self.assertEqual(td.resolve_tribe(c["input"]), c["expected"])

    def test_tribe_from_state(self):
        for c in _golden("resolve_tribe.expected.json")["state_cases"]:
            with self.subTest(case=c):
                self.assertEqual(td.tribe_from_state(c["rows"]), c["expected"])

    def test_unit_tables_match_old(self):
        old = _golden("units.expected.json")["tribes"]
        self.assertEqual(set(old), set(td.TRIBES))
        for key, units in old.items():
            spec = td.get_tribe(key)
            for t, (speed, attack, carry) in units.items():
                u = spec.unit("u" + t[1:])
                with self.subTest(tribe=key, unit=t):
                    self.assertEqual((u.speed, u.attack, u.carry), (speed, attack, carry))


class RegistryTest(unittest.TestCase):
    def test_registered_keys(self):
        self.assertEqual(sorted(td.TRIBES), ["egyptian", "gaul", "roman", "teuton"])

    def test_registry_is_read_only(self):
        with self.assertRaises(TypeError):
            td.TRIBES["hun"] = None      # type: ignore[index]

    def test_specs_are_frozen(self):
        spec = td.get_tribe("gaul")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.cranny_factor = 5       # type: ignore[misc]

    def test_get_tribe_unknown(self):
        for bad in ("nobody", "hun", "", None, 3):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError) as cm:
                    td.get_tribe(bad)
                self.assertEqual(cm.exception.rule, "unknown_tribe")

    def test_nothing_is_marked_verified_yet(self):
        # 開服後用 S8／遊戲內頁核對才能改 True（A0b）
        self.assertTrue(all(not s.verified for s in td.TRIBES.values()))


class SmokePerTribeTest(unittest.TestCase):
    """種族煙霧測試：每個種族的結構一致、查詢函式不炸。"""

    def test_each_tribe(self):
        for key, spec in td.TRIBES.items():
            with self.subTest(tribe=key):
                self.assertEqual(spec.key, key)
                self.assertIn(spec.queue_mode, ("single", "parallel"))
                self.assertGreaterEqual(spec.base_queue_slots, 1)
                self.assertEqual(spec.base_queue_slots == 2, spec.queue_mode == "parallel")
                self.assertGreaterEqual(td.cranny_factor(spec), 1)
                keys = [u.key for u in spec.units]
                self.assertEqual(len(keys), len(set(keys)))
                for u in spec.units:
                    self.assertRegex(u.key, r"^u([1-9]|10)$")
                    for v in (u.speed, u.attack, u.carry):
                        self.assertTrue(v is None or (isinstance(v, int) and v >= 0))
                self.assertEqual(spec.settler_unit, "u10")
                self.assertEqual(spec.chief_unit, "u9")
                self.assertEqual(td.resolve_tribe(spec.name), key)
                self.assertEqual(td.resolve_tribe(key), key)
                self.assertEqual(td.tribe_keys_by_id()[spec.tribe_id], key)
                if spec.merchant_capacity is None:
                    with self.assertRaises(td.TribeDataError):
                        td.merchant_info(spec, 1)
                else:
                    cap, speed = td.merchant_info(spec, 1)
                    self.assertGreater(cap, 0)
                    self.assertGreater(speed, 0)

    def test_gaul_has_ten_units_with_speeds(self):
        spec = td.get_tribe("gaul")
        self.assertEqual([u.key for u in spec.units], ["u%d" % i for i in range(1, 11)])
        self.assertTrue(all(u.speed is not None for u in spec.units))


class GaulValuesTest(unittest.TestCase):
    """舊 dispatch.TRIBES['gauls'] 的 t1～t6（速度、攻擊、載重）搬過來要一致。"""
    OLD = {"t1": (7, 15, 35), "t2": (6, 65, 45), "t3": (17, 0, 0), "t4": (19, 90, 75),
           "t5": (16, 45, 35), "t6": (13, 140, 65)}

    def test_old_table_preserved(self):
        spec = td.get_tribe("gaul")
        for old_key, (speed, attack, carry) in self.OLD.items():
            u = spec.unit("u" + old_key[1:])
            with self.subTest(unit=old_key):
                self.assertEqual((u.speed, u.attack, u.carry), (speed, attack, carry))

    def test_merchant_cranny_trap(self):
        spec = td.get_tribe("gaul")
        self.assertEqual(td.merchant_info(spec, 1), (750, 24))
        self.assertEqual(td.cranny_factor(spec), 2)
        self.assertEqual((spec.wall_gid, spec.trap_gid), (33, 36))

    def test_merchant_speed_server_is_refused_until_verified(self):
        # 官方倍速表只說明部隊速度（x3 乘 2，不是 3），沒有說明商人 → 不猜
        for speed in (2, 3, 5, 10):
            with self.subTest(speed=speed):
                with self.assertRaises(td.TribeDataError):
                    td.merchant_info(td.get_tribe("gaul"), speed)

    def test_merchant_bad_speed(self):
        spec = td.get_tribe("gaul")
        for bad in (0, -1, 1.5, True, None):
            with self.subTest(bad=bad):
                with self.assertRaises(td.TribeDataError):
                    td.merchant_info(spec, bad)

    def test_other_tribes_merchants(self):
        self.assertEqual(td.merchant_info(td.get_tribe("roman"), 1), (500, 16))
        self.assertEqual(td.merchant_info(td.get_tribe("teuton"), 1), (1000, 12))

    def test_queue(self):
        self.assertEqual(td.get_tribe("roman").base_queue_slots, 2)     # 舊 runner：羅馬 2、其他 1
        self.assertEqual(td.get_tribe("gaul").base_queue_slots, 1)


class ResolveTest(unittest.TestCase):
    CASES = {
        "高盧": "gaul", "高卢": "gaul", "高盧人": "gaul", " Gauls ": "gaul", "GAUL": "gaul",
        "羅馬": "roman", "罗马": "roman", "romans": "roman",
        "條頓": "teuton", "条顿": "teuton", "日耳曼": "teuton", "Teutons": "teuton",
        "埃及": "egyptian", "埃及人": "egyptian", "egyptians": "egyptian",
    }

    def test_aliases(self):
        for text, key in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(td.resolve_tribe(text), key)

    def test_unknown(self):
        for text in ("匈奴", "hun", "維京", "", "   ", None, 0, "abc"):
            with self.subTest(text=text):
                self.assertIsNone(td.resolve_tribe(text))


class FromStateTest(unittest.TestCase):
    def test_found(self):
        rows = [["plus_active", "TRUE", ""], ["tribe", " 高盧 ", "說明"], ["cp_have", "10"]]
        self.assertEqual(td.tribe_from_state(rows), "gaul")

    def test_missing_or_unknown(self):
        self.assertIsNone(td.tribe_from_state([["cp_have", "10"]]))
        self.assertIsNone(td.tribe_from_state([["tribe"]]))
        self.assertIsNone(td.tribe_from_state([["tribe", "匈奴"]]))
        self.assertIsNone(td.tribe_from_state([]))
        self.assertIsNone(td.tribe_from_state(None))
        self.assertIsNone(td.tribe_from_state(5))            # 不可迭代也不拋例外
        self.assertIsNone(td.tribe_from_state([None, []]))


class GlobalUnitIdTest(unittest.TestCase):
    def test_gaul(self):
        spec = td.get_tribe("gaul")
        self.assertEqual(td.global_unit_id(spec, "u1"), 21)
        self.assertEqual(td.global_unit_id(spec, "u10"), 30)

    def test_unknown_base_and_bad_key(self):
        self.assertIsNone(td.global_unit_id(td.get_tribe("roman"), "u1"))
        for bad in ("u0", "u11", "hero", "1", "", None):
            with self.subTest(bad=bad):
                with self.assertRaises(td.TribeDataError):
                    td.global_unit_id(td.get_tribe("gaul"), bad)


class TribeIdTest(unittest.TestCase):
    def test_ids_from_old_const(self):
        self.assertEqual(td.tribe_keys_by_id(), {1: "roman", 2: "teuton", 3: "gaul", 6: "egyptian", 7: "hun"})

    def test_returns_copy(self):
        d = td.tribe_keys_by_id()
        d[1] = "x"
        self.assertEqual(td.tribe_keys_by_id()[1], "roman")


if __name__ == "__main__":
    unittest.main()
