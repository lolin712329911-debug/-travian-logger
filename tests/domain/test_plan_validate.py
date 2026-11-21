import unittest

from travian_bot.common.decisions import BuildFacts, FactsNeed
from travian_bot.domain import plan_validate as V
from tests.domain.fixtures import cond, dorf1, dorf2, fields, option

NOFACTS = BuildFacts()


def verdict(text, d1=None, facts=NOFACTS, cap=False):
    return V.validate_order(V.parse_build_order(text), d1 or dorf1(), facts, cap, 7, "2026-11-11T00:00:00Z")


class ParseTest(unittest.TestCase):
    def test_formats(self):
        r = V.parse_build_order("res:2, 15：3\n資源田:4;10:5")
        self.assertEqual([(s.seq, s.key, s.level) for s in r], [(1, "res", 2), (2, 15, 3), (3, "res", 4), (4, 10, 5)])

    def test_garbage_is_kept_not_raised(self):
        r = V.parse_build_order("res:2,abc,15:")
        self.assertEqual([(s.key, s.level) for s in r], [("res", 2), ("abc", None), ("15:", None)])

    def test_empty(self):
        self.assertEqual(V.parse_build_order(None), ())
        self.assertEqual(V.parse_build_order("  "), ())


class CheckStepTest(unittest.TestCase):
    def rule(self, key, level, cap=False):
        v = V.check_step(V.RawStep(3, key, level), cap)
        return None if v.ok else v.rule

    def test_bad_format(self):
        for k, lv in (("abc", None), (0, 1), (-1, 1), (True, 1), (15, 0), (15, True), (15, 2.5), (None, 1), ("res", "2")):
            self.assertEqual(self.rule(k, lv), "bad_format", (k, lv))

    def test_unknown_building(self):
        self.assertEqual(self.rule(999, 1), "unknown_building")
        self.assertEqual(self.rule(12, 1), "unknown_building")         # 12 不在 GID_NAMES

    def test_level_caps(self):
        self.assertEqual(self.rule("res", 11), "level_over_cap")
        self.assertEqual(self.rule(1, 11), "level_over_cap")
        self.assertIsNone(self.rule("res", 11, cap=True))              # 首都沒有可靠上限資料：不拒
        self.assertEqual(self.rule(15, 21), "level_over_cap")
        self.assertIsNone(self.rule(15, 20))
        self.assertIsNone(self.rule("res", 10))

    def test_reason_mentions_step(self):
        self.assertIn("第 3 步", V.check_step(V.RawStep(3, 999, 1), False).reason)

    def test_usable_order_filters_and_keeps_order(self):
        raw = V.parse_build_order("res:2,999:1,15:3,res:11")
        self.assertEqual(V.usable_order(raw, False), [("res", 2), (15, 3)])


class ValidateOrderTest(unittest.TestCase):
    def test_missing_order_holds(self):
        for raw in (None, ()):
            v = V.validate_order(raw, dorf1(), NOFACTS, False, 7, "t")
            self.assertEqual((v.verdict, v.next_seq, [(r.seq, r.rule) for r in v.rejected]), ("hold", None, [(1, "missing_order")]))

    def test_proceed_points_at_first_unachieved_step(self):
        d1 = dorf1(flds=fields(levels={a: 2 for a in range(1, 19)}))
        v = verdict("res:2,res:3,res:4", d1)
        self.assertEqual((v.verdict, v.next_seq, v.did, v.checked_utc, v.rejected), ("proceed", 2, 7, "2026-11-11T00:00:00Z", ()))

    def test_all_done_points_at_last_step(self):
        v = verdict("res:1,res:1", dorf1())
        self.assertEqual((v.verdict, v.next_seq), ("proceed", 2))

    def test_rejected_next_step_holds(self):
        v = verdict("res:11,res:2")
        self.assertEqual((v.verdict, v.next_seq, [(r.seq, r.rule) for r in v.rejected]), ("hold", 1, [(1, "level_over_cap")]))

    def test_rejected_later_step_is_recorded_but_does_not_hold(self):
        v = verdict("res:2,999:1,x")
        self.assertEqual((v.verdict, v.next_seq), ("proceed", 1))
        self.assertEqual([(r.seq, r.rule) for r in v.rejected], [(2, "unknown_building"), (3, "bad_format")])

    def test_rejected_step_behind_achieved_ones_holds_when_it_becomes_next(self):
        d1 = dorf1(flds=fields(levels={a: 2 for a in range(1, 19)}))
        v = verdict("res:2,999:1", d1)
        self.assertEqual((v.verdict, v.next_seq), ("hold", 2))

    def test_building_step_without_dorf2_still_proceeds_but_needs_facts(self):
        raw = V.parse_build_order("15:3")
        self.assertEqual(V.validation_need(raw, dorf1(), NOFACTS, False), FactsNeed("dorf2"))
        self.assertEqual(verdict("15:3").verdict, "proceed")           # ④ 略過

    def test_existing_building_achieved_or_upgrade(self):
        facts = BuildFacts(dorf2({25: (15, 3)}))
        v = verdict("15:3,15:5", facts=facts)
        self.assertEqual((v.verdict, v.next_seq), ("proceed", 2))

    def test_new_building_prereq(self):
        market = option(17, buildable=False, conds=[cond(15, 3)])
        facts = BuildFacts(dorf2(), options={19: (market,)})
        v = verdict("17:1", facts=facts)
        self.assertEqual((v.verdict, v.next_seq, [(r.seq, r.rule) for r in v.rejected]), ("hold", 1, [(1, "prereq_unmet")]))
        self.assertIn("3 級", v.rejected[0].reason)
        ok = BuildFacts(dorf2(), options={19: (option(17),)})
        self.assertEqual(verdict("17:1", facts=ok).verdict, "proceed")

    def test_prereq_met_condition_is_fine(self):
        met = option(17, buildable=False, conds=[cond(15, 3, met=True)])
        self.assertEqual(verdict("17:1", facts=BuildFacts(dorf2(), options={19: (met,)})).verdict, "proceed")

    def test_forbidden_condition(self):
        pal = option(26, buildable=False, conds=[cond(25, 1, forbidden=True)])
        v = verdict("26:1", facts=BuildFacts(dorf2(), options={19: (pal,)}))
        self.assertEqual((v.verdict, v.rejected[0].rule), ("hold", "prereq_unmet"))
        self.assertIn("擋住", v.rejected[0].reason)

    def test_building_not_in_option_list_is_left_to_planner(self):
        v = verdict("22:1", facts=BuildFacts(dorf2(), options={19: (option(18),)}))
        self.assertEqual(v.verdict, "proceed")

    def test_prereq_only_checked_for_next_step(self):
        market = option(17, buildable=False, conds=[cond(15, 3)])
        facts = BuildFacts(dorf2(), options={19: (market,)})
        v = verdict("res:2,17:1", facts=facts)
        self.assertEqual((v.verdict, v.next_seq, v.rejected), ("proceed", 1, ()))

    def test_reason_truncated_to_200(self):
        long = "x" * 300
        v = V.validate_order((V.RawStep(1, long, None),), dorf1(), NOFACTS, False, 1, "t")
        self.assertLessEqual(len(v.rejected[0].reason), 200)


class ValidationNeedTest(unittest.TestCase):
    def test_sequence(self):
        raw = V.parse_build_order("17:1")
        self.assertEqual(V.validation_need(raw, dorf1(), NOFACTS, False), FactsNeed("dorf2"))
        f1 = BuildFacts(dorf2())
        self.assertEqual(V.validation_need(raw, dorf1(), f1, False), FactsNeed("build_options", 19))
        f2 = BuildFacts(dorf2(), options={19: ()})
        self.assertIsNone(V.validation_need(raw, dorf1(), f2, False))

    def test_no_need_for_fields_existing_or_empty(self):
        self.assertIsNone(V.validation_need(V.parse_build_order("res:2"), dorf1(), NOFACTS, False))
        self.assertIsNone(V.validation_need(V.parse_build_order("15:5"), dorf1(), BuildFacts(dorf2({25: (15, 1)})), False))
        self.assertIsNone(V.validation_need(None, dorf1(), NOFACTS, False))


if __name__ == "__main__":
    unittest.main()
