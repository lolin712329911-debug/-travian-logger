"""decisions.py v0.5（A3c）：HideCandidate／HideDecision／LockDecision。既有 test_decisions 不動。"""
import dataclasses
import unittest

from travian_bot.common import decisions as D


class A3cDecisions(unittest.TestCase):
    def test_hide_candidate_old_construction_still_works(self):
        c = D.HideCandidate(1, 2, "wood25", 3.0, True)
        self.assertEqual((c.map_id, c.one_way_s, c.back_ts, c.covered, c.missed), (None, None, None, (), ()))

    def test_hide_candidate_field_order_appended_at_tail(self):
        names = [f.name for f in dataclasses.fields(D.HideCandidate)]
        self.assertEqual(names, ["x", "y", "kind", "distance", "safe", "map_id", "one_way_s", "back_ts", "covered", "missed"])

    def test_hide_decision_defaults_and_order(self):
        d = D.HideDecision(False, None, (), "x")
        self.assertEqual((d.kind, d.code, d.units, d.scope, d.full), ("", "", (), (), False))
        self.assertEqual([f.name for f in dataclasses.fields(D.HideDecision)],
                         ["act", "chosen", "candidates", "reason", "kind", "code", "units", "scope", "full"])

    def test_lock_decision(self):
        d = D.LockDecision("ok", "r")
        self.assertFalse(d.record)
        self.assertEqual([f.name for f in dataclasses.fields(D.LockDecision)], ["kind", "reason", "record"])

    def test_all_frozen(self):
        for cls in (D.HideCandidate, D.HideDecision, D.LockDecision):
            self.assertTrue(cls.__dataclass_params__.frozen, cls)
            self.assertIn(cls.__name__, D.__all__)

    def test_value_domains(self):
        self.assertEqual(D.HIDE_KINDS, ("skip", "wait", "go"))
        self.assertEqual(D.HIDE_CODES, ("ok", "no_units", "unknown_speed", "weak", "no_future", "too_far", "too_close", "no_oasis"))
        self.assertEqual(D.LOCK_KINDS, ("ok", "skip"))
        for name in ("HIDE_KINDS", "HIDE_CODES", "LOCK_KINDS"):
            self.assertNotIn(name, D.__all__)           # tuple 不進 __all__（既有 test_decisions 的規則）

    def test_all_only_frozen_dataclasses_except_build_kinds(self):
        for n in D.__all__:
            o = getattr(D, n)
            if n == "BUILD_KINDS":
                continue
            self.assertTrue(dataclasses.is_dataclass(o) and o.__dataclass_params__.frozen, n)


if __name__ == "__main__":
    unittest.main()
