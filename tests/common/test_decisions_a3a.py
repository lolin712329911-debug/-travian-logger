"""cm-02 v0.2（A3a）新增部分的測試。原有的 test_decisions.py 不動（它釘住 BUILD_KINDS 的 7 個舊標籤與 __all__ 內容）。"""
import dataclasses
import unittest

from travian_bot.common import decisions as D
from travian_bot.common.decisions import (BUILD_DECISION_KINDS, BUILD_EXTRA_KINDS, BUILD_KINDS, FACTS_KINDS,
                                          BuildDecision, BuildFacts, FactsNeed, FillCandidate, GuardDecision)
from travian_bot.common.models import BuildTarget


class KindsTest(unittest.TestCase):
    def test_kinds_layout(self):
        self.assertEqual(len(BUILD_KINDS), 7)
        self.assertEqual(BUILD_EXTRA_KINDS, ("no_affordable", "need_facts"))
        self.assertEqual(BUILD_DECISION_KINDS, BUILD_KINDS + BUILD_EXTRA_KINDS)
        self.assertEqual(len(set(BUILD_DECISION_KINDS)), 9)
        self.assertEqual(FACTS_KINDS, ("dorf2", "upgrade_cost", "build_options"))

    def test_new_tuples_stay_out_of_all(self):
        for n in ("BUILD_EXTRA_KINDS", "BUILD_DECISION_KINDS", "FACTS_KINDS"):
            self.assertNotIn(n, D.__all__)
        for n in ("FactsNeed", "BuildFacts", "FillCandidate"):
            self.assertIn(n, D.__all__)
            self.assertTrue(dataclasses.is_dataclass(getattr(D, n)))


class StructTest(unittest.TestCase):
    def test_build_decision_defaults(self):
        d = BuildDecision("done", None, "x")
        self.assertEqual((d.wait_s, d.build_time_s, d.need), (None, None, None))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            d.kind = "build"

    def test_need_and_candidate_are_frozen(self):
        n = FactsNeed("upgrade_cost", 25)
        self.assertEqual((n.kind, n.aid, FactsNeed("dorf2").aid), ("upgrade_cost", 25, None))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            n.aid = 1
        t = BuildTarget(1, 1, "伐木場", 2, (1, 1, 1, 1), 0)
        self.assertEqual(FillCandidate(t, 600).build_time_s, 600)

    def test_build_facts_defaults_and_copies_input(self):
        f = BuildFacts()
        self.assertEqual((f.dorf2, f.upgrade_costs, f.options), (None, {}, {}))
        src = {25: None}
        g = BuildFacts(None, src)
        src[26] = None
        self.assertEqual(list(g.upgrade_costs), [25])          # 不受呼叫端之後修改影響
        with self.assertRaises(dataclasses.FrozenInstanceError):
            g.dorf2 = 1

    def test_guard_decision_focus(self):
        self.assertIsNone(GuardDecision(False, "x").focus)
        self.assertEqual(GuardDecision(True, "x", "always", 2).focus, 2)


if __name__ == "__main__":
    unittest.main()
