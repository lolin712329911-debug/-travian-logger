# -*- coding: utf-8 -*-
"""A6a1：契約 C-v0.7（D-32）C2 VillageSnapshot.hidden 可為 null。"""
import copy
import json
import unittest
from pathlib import Path

from travian_bot.common import schema
from travian_bot.common.models import ValidationError, VillageSnapshot

VALID = json.loads((Path(__file__).resolve().parents[1] / "contracts" / "VillageSnapshot.valid.json")
                   .read_text(encoding="utf-8"))["cases"]


class HiddenNullTest(unittest.TestCase):
    def base(self):
        return copy.deepcopy(VALID[0]["data"])

    def test_null_is_valid_and_round_trips(self):
        d = self.base()
        d["hidden"] = None
        self.assertEqual(schema.validate("VillageSnapshot", d), [])
        obj = VillageSnapshot.from_dict(d)
        self.assertIsNone(obj.hidden)
        self.assertIsNone(obj.to_dict()["hidden"])

    def test_missing_key_is_treated_like_null(self):
        d = self.base()
        del d["hidden"]
        self.assertEqual(schema.validate("VillageSnapshot", d), [])

    def test_values_still_checked(self):
        d = self.base()
        d["hidden"] = [0, 0, 0, -1]
        errs = schema.validate("VillageSnapshot", d)
        self.assertEqual([(e.field, e.rule) for e in errs], [("hidden[3]", "min")])
        d["hidden"] = [0, 0, 0]
        self.assertEqual(schema.validate("VillageSnapshot", d)[0].rule, "res4_length")

    def test_valid_example_with_null_is_published(self):
        self.assertTrue(any(c["data"].get("hidden", 0) is None for c in VALID))

    def test_tuple_conversion_keeps_non_null(self):
        self.assertEqual(VillageSnapshot.from_dict(self.base()).hidden, (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
