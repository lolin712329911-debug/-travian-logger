"""tests/common/test_schema.py — cm-11（v0.1，A1a-1）

契約測試：合規範例通過、不合規範例被擋且指到正確欄位與規則。
"""
import unittest

from travian_bot.common import schema as SC

SPEC_CONTRACTS = {f"C{i}" for i in range(1, 13)}


class ExamplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = SC.contract_examples()

    def test_every_contract_has_examples(self):
        self.assertEqual(set(self.examples), set(SC.CONTRACT_SPECS))
        for name, ex in self.examples.items():
            self.assertTrue(ex["valid"], f"{name} 缺合規範例")
            self.assertGreaterEqual(len(ex["invalid"]), 2, f"{name} 不合規範例太少")

    def test_valid_examples_pass(self):
        for name, ex in self.examples.items():
            for i, case in enumerate(ex["valid"]):
                errs = SC.validate(name, case["data"], case["ctx"])
                self.assertEqual([str(e) for e in errs], [], f"{name} valid[{i}]")

    def test_invalid_examples_are_caught_at_right_field(self):
        for name, ex in self.examples.items():
            for i, case in enumerate(ex["invalid"]):
                errs = SC.validate(name, case["data"], case["ctx"])
                got = {(e.field, e.rule) for e in errs}
                self.assertIn((case["field"], case["rule"]), got, f"{name} invalid[{i}] 實得 {sorted(got)}")

    def test_examples_do_not_mutate_each_other(self):
        a = SC.contract_examples()
        b = SC.contract_examples()
        self.assertEqual(a, b)
        a["BuildTarget"]["valid"][0]["data"]["cost"][0] = 999
        self.assertNotEqual(SC.contract_examples()["BuildTarget"]["valid"][0]["data"]["cost"][0], 999)


class CoverageTest(unittest.TestCase):
    def test_c1_to_c12_present(self):
        names = set(SC.CONTRACT_SPECS)
        for required in ("VillageRef", "VillageSnapshot", "TransferPlan", "TroopMovePlan", "ActionRow",
                         "VillageSettingsRow", "MarketConfig", "VillageLock", "VillageContext",
                         "StageResult", "ServerProfile", "PlanVerdict"):
            self.assertIn(required, names)
        for sub in ("BuildTarget", "Merchants", "Transit", "Oasis", "BuildSettings", "HideContext"):
            self.assertIn(sub, names)

    def test_c5_has_ten_columns_in_order(self):
        cols = list(SC.CONTRACT_SPECS["ActionRow"]["fields"])
        self.assertEqual(cols, ["ts_utc", "action", "aid", "gid", "level", "cost", "mode", "result",
                                "detail", "did"])

    def test_c6_column_order(self):
        cols = list(SC.CONTRACT_SPECS["VillageSettingsRow"]["fields"])
        self.assertEqual(cols, ["did", "name", "enabled", "role", "is_capital", "queue_slots", "build_order",
                                "hide_mode", "guard_mode", "fill_mode", "priority", "note"])

    def test_c11_has_locale_and_no_wuid(self):
        fields = SC.CONTRACT_SPECS["ServerProfile"]["fields"]
        self.assertIn("locale", fields)
        self.assertNotIn("wuid", fields)   # D-21 未同意前不加


class EngineBehaviourTest(unittest.TestCase):
    def setUp(self):
        self.ex = SC.contract_examples()
        self.snap = self.ex["VillageSnapshot"]["valid"][0]["data"]

    def test_bool_is_not_int(self):
        data = dict(self.snap, cap_wh=True)
        self.assertIn(("cap_wh", "type"), {(e.field, e.rule) for e in SC.validate("VillageSnapshot", data)})

    def test_float_is_not_int(self):
        data = dict(self.snap, cap_wh=800.0)
        self.assertIn(("cap_wh", "type"), {(e.field, e.rule) for e in SC.validate("VillageSnapshot", data)})

    def test_prod_may_be_negative_stock_may_not(self):
        self.assertEqual(SC.validate("VillageSnapshot", dict(self.snap, prod=[-1, -2, -3, -4])), [])
        errs = SC.validate("VillageSnapshot", dict(self.snap, stock=[-1, 0, 0, 0]))
        self.assertEqual([(e.field, e.rule) for e in errs], [("stock[0]", "min")])

    def test_nullable_missing_ok_required_missing_error(self):
        data = dict(self.snap)
        del data["merchants"]
        self.assertEqual(SC.validate("VillageSnapshot", data), [])
        del data["did"]
        self.assertIn(("did", "required"), {(e.field, e.rule) for e in SC.validate("VillageSnapshot", data)})

    def test_null_for_required_is_error(self):
        errs = SC.validate("VillageSnapshot", dict(self.snap, did=None))
        self.assertIn(("did", "required"), {(e.field, e.rule) for e in errs})

    def test_sentinel_not_allowed_for_null(self):
        base = self.ex["VillageSettingsRow"]["valid"][0]["data"]
        for s in ("-", "none", "None", "null"):
            errs = SC.validate("VillageSettingsRow", dict(base, build_order=s))
            self.assertIn(("build_order", "no_sentinel"), {(e.field, e.rule) for e in errs}, s)

    def test_strict_unknown_fields(self):
        data = dict(self.snap, future_field=1)
        self.assertEqual(SC.validate("VillageSnapshot", data), [])
        errs = SC.validate("VillageSnapshot", data, {"strict": True})
        self.assertEqual([(e.field, e.rule) for e in errs], [("future_field", "unknown_field")])

    def test_non_dict_input(self):
        errs = SC.validate("BuildTarget", [1, 2])
        self.assertEqual([(e.field, e.rule) for e in errs], [("", "type")])

    def test_unknown_contract_is_programming_error(self):
        with self.assertRaises(KeyError):
            SC.validate("Nope", {})

    def test_errors_do_not_leak_values(self):
        secret = "COOKIE-SECRET-VALUE-123"
        prof = dict(self.ex["ServerProfile"]["valid"][0]["data"], base_url="https://" + secret + "@x.invalid")
        errs = SC.validate("ServerProfile", prof)
        self.assertTrue(errs)
        for e in errs:
            self.assertNotIn(secret, str(e))
            self.assertNotIn(secret, repr(e.args))

    def test_ensure_valid(self):
        ok = self.ex["BuildTarget"]["valid"][0]["data"]
        self.assertIsNone(SC.ensure_valid("BuildTarget", ok))
        bad = dict(ok, aid=0, gid=0)
        with self.assertRaises(SC.ValidationError) as cm:
            SC.ensure_valid("BuildTarget", bad)
        self.assertEqual(len(cm.exception.all), 2)

    def test_rules_skipped_when_field_errors_exist(self):
        # free 型別錯時不應再跑 free<=total 規則（避免 TypeError）
        errs = SC.validate("Merchants", {"free": "x", "total": 1, "capacity_each": 1})
        self.assertEqual([(e.field, e.rule) for e in errs], [("free", "type")])

    def test_hold_rule_semantics(self):
        v = self.ex["PlanVerdict"]
        hold = v["valid"][1]["data"]
        # 後面的步驟被拒但還沒輪到：proceed
        later = dict(hold, verdict="proceed", next_seq=2)
        self.assertEqual(SC.validate("PlanVerdict", later), [])

    def test_parse_error(self):
        e = SC.ParseError("dorf1", "找不到資源列")
        self.assertEqual(str(e), "dorf1: 找不到資源列")
        self.assertEqual((e.page, e.reason), ("dorf1", "找不到資源列"))


if __name__ == "__main__":
    unittest.main()
