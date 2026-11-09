# -*- coding: utf-8 -*-
"""schema.py v0.2（A2b，契約 C-v0.6）：C2 VillageSnapshot 的 units_home／units_away 鍵格式改為 u1～u10 或 hero（D-21②）。
與 TroopMovePlan.units 的鍵格式一致；其餘契約不變（契約範例與 tools/check_contracts.py 的計數不受影響）。"""
import unittest

from travian_bot.common import schema


def _snap(**kw):
    base = dict(schema.contract_examples()["VillageSnapshot"]["valid"][0]["data"])
    base.update(kw)
    return base


def _pairs(errs):
    return {(e.field, e.rule) for e in errs}


class UnitsKeyFormat(unittest.TestCase):
    def test_valid_keys(self):
        for d in ({"u1": 10}, {"u1": 1, "u10": 2, "hero": 1}, {f"u{i}": 1 for i in range(1, 11)}, {}):
            with self.subTest(d=d):
                self.assertEqual(schema.validate("VillageSnapshot", _snap(units_home=d, units_away=d)), [])

    def test_none_still_allowed(self):
        self.assertEqual(schema.validate("VillageSnapshot", _snap(units_home=None, units_away=None)), [])

    def test_old_t_keys_rejected(self):
        for field in ("units_home", "units_away"):
            with self.subTest(field=field):
                errs = schema.validate("VillageSnapshot", _snap(**{field: {"t1": 5}}))
                self.assertIn((field, "key_pattern"), _pairs(errs))

    def test_bad_keys_rejected(self):
        for k in ("u0", "u11", "u01", "hero2", "U1", "t11", "", "u1 "):
            with self.subTest(k=k):
                errs = schema.validate("VillageSnapshot", _snap(units_home={k: 1}))
                self.assertIn(("units_home", "key_pattern"), _pairs(errs))

    def test_zero_count_still_rejected(self):
        errs = schema.validate("VillageSnapshot", _snap(units_home={"u1": 0}))
        self.assertIn(("units_home.u1", "min"), _pairs(errs))

    def test_same_format_as_troop_move_plan(self):
        self.assertEqual(schema.CONTRACT_SPECS["VillageSnapshot"]["fields"]["units_home"]["key_pattern"],
                         schema.CONTRACT_SPECS["TroopMovePlan"]["fields"]["units"]["key_pattern"])


if __name__ == "__main__":
    unittest.main()
