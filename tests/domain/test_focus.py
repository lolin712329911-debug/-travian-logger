"""dm-04 focus 測試：與舊 hero_focus.decide_focus 的 600 組離線輸出逐案比對＋個別規則。"""
import json
import os
import unittest
from types import SimpleNamespace as NS

from travian_bot.common.decisions import FOCUS_NAMES, FocusDecision
from travian_bot.common.parsed import HeroFocus
from travian_bot.domain.focus import FocusSettings, decide_focus, hero_bonus

GOLDEN = os.path.join(os.path.dirname(__file__), "..", "golden", "domain", "focus.cases.json")
BIG = 10 ** 9


def _load():
    with open(GOLDEN, encoding="utf-8") as f:
        return json.load(f)


def snap(cost=None, stock=(0, 0, 0, 0), prod=(500, 500, 500, 500), cap_wh=BIG, cap_gr=BIG):
    tgt = NS(cost=tuple(cost)) if cost is not None else None
    return NS(stock=tuple(stock), prod=tuple(prod), cap_wh=cap_wh, cap_gr=cap_gr, next_target=tgt)


F = HeroFocus(0, (336, 1120, 1120, 1120, 1120))


class TestGolden(unittest.TestCase):
    def test_matches_old_function(self):
        cases = _load()
        self.assertEqual(len(cases), 600)
        n_switch = 0
        for i, c in enumerate(cases):
            s = FocusSettings(min_hours=c["settings"]["min_hours"], switch_ratio=c["settings"]["switch_ratio"],
                              crop_floor=c["settings"]["crop_floor"], back_to_balanced=c["settings"]["back_to_balanced"])
            d = decide_focus(snap(c["cost"], c["stock"], c["prod"]), HeroFocus(c["current"], tuple(c["types"])),
                             s, c["hours"])
            kind, t = c["expected"]
            with self.subTest(i=i):
                self.assertIsInstance(d, FocusDecision)
                self.assertEqual(d.act, kind == "switch")
                self.assertEqual(d.focus, FOCUS_NAMES[t] if kind == "switch" else None)
                self.assertTrue(d.reason)
            n_switch += d.act
        self.assertGreater(n_switch, 100)       # golden 有足夠的切換案例，不是全部 keep


class TestRules(unittest.TestCase):
    def test_hero_bonus(self):
        t = (336, 1120, 1120, 1120, 1120)
        self.assertEqual([hero_bonus(0, t, r) for r in range(1, 5)], [336] * 4)
        self.assertEqual([hero_bonus(2, t, r) for r in range(1, 5)], [0, 1120, 0, 0])

    def test_unreadable_focus_keeps(self):
        d = decide_focus(snap((1000, 0, 0, 0)), None)
        self.assertFalse(d.act)
        self.assertIsNone(d.focus)

    def test_recent_change_keeps(self):
        d = decide_focus(snap((5000, 0, 0, 0)), F, FocusSettings(min_hours=1.0), 0.5)
        self.assertFalse(d.act)
        self.assertIn("0.5h", d.reason)

    def test_unknown_hours_does_not_block(self):
        d = decide_focus(snap((5000, 0, 0, 0)), F, FocusSettings(), None)
        self.assertTrue(d.act)
        self.assertEqual(d.focus, "wood")

    def test_single_gap_switches_to_that_resource(self):
        d = decide_focus(snap((5000, 0, 0, 0), stock=(0, 0, 0, 0)), F)
        self.assertEqual((d.act, d.focus), (True, "wood"))

    def test_no_target_goes_back_to_balanced(self):
        d = decide_focus(snap(None), HeroFocus(1, F.types))
        self.assertEqual((d.act, d.focus), (True, "balanced"))

    def test_no_target_stays_if_already_balanced_or_disabled(self):
        self.assertFalse(decide_focus(snap(None), F).act)
        self.assertFalse(decide_focus(snap(None), HeroFocus(1, F.types), FocusSettings(back_to_balanced=False)).act)

    def test_affordable_target_is_no_gap(self):
        d = decide_focus(snap((100, 100, 100, 100), stock=(100, 100, 100, 100)), HeroFocus(3, F.types))
        self.assertEqual((d.act, d.focus), (True, "balanced"))

    def test_crop_floor_blocks_switch_that_starves(self):
        # 目前加成是穀（+1120，穀淨產量 1100 已含）；切到木會讓穀變 -20 ≤ 0，所以木被排除，改選平均
        d = decide_focus(snap((5000, 0, 0, 0), prod=(100, 100, 100, 1100)), HeroFocus(4, F.types))
        self.assertEqual((d.act, d.focus), (True, "balanced"))
        d2 = decide_focus(snap((5000, 0, 0, 0), prod=(100, 100, 100, 1100)), HeroFocus(4, F.types),
                          FocusSettings(crop_floor=-100.0))       # 下限放寬後木可選
        self.assertEqual((d2.act, d2.focus), (True, "wood"))

    def test_crop_floor_is_strict(self):
        # 切到木後穀淨產量剛好 0（＝下限）→ 不可選（要 > 下限）；改選平均
        d = decide_focus(snap((5000, 0, 0, 0), prod=(100, 100, 100, 1120)), HeroFocus(4, F.types))
        self.assertEqual((d.act, d.focus), (True, "balanced"))

    def test_zero_production_candidate_is_skipped_not_divided(self):
        # 目前平均：木產量 336 全是英雄加成，切到磚／鐵／穀單押後木產量為 0 → 該候選補齊時間無限，不可除以零
        d = decide_focus(snap((5000, 0, 0, 0), prod=(336, 500, 500, 500)), F)
        self.assertEqual((d.act, d.focus), (True, "wood"))

    def test_ratio_keeps_when_only_slightly_faster(self):
        # 平均 336 vs 木 1120：差距大會切；把 ratio 拉到 10 就不切
        s = snap((3000, 0, 0, 0))
        self.assertTrue(decide_focus(s, F, FocusSettings(switch_ratio=1.3)).act)
        self.assertFalse(decide_focus(s, F, FocusSettings(switch_ratio=10.0)).act)

    def test_cost_over_capacity_keeps(self):
        d = decide_focus(snap((5000, 0, 0, 0), cap_wh=4000), F)
        self.assertFalse(d.act)
        self.assertIn("倉容", d.reason)

    def test_over_capacity_only_checked_for_gap_resources(self):
        # 磚成本超過倉容但庫存已足夠（沒有缺口）→ 不擋；木有缺口且在倉容內 → 照常切木
        d = decide_focus(snap((5000, 9000, 0, 0), stock=(0, 9000, 0, 0), cap_wh=10000), F)
        self.assertEqual((d.act, d.focus), (True, "wood"))

    def test_crop_gap_uses_granary_capacity(self):
        d = decide_focus(snap((0, 0, 0, 5000), cap_wh=10 ** 6, cap_gr=4000), F)
        self.assertFalse(d.act)

    def test_decision_is_frozen_and_snapshot_untouched(self):
        s = snap((5000, 0, 0, 0))
        before = (s.stock, s.prod)
        d = decide_focus(s, F)
        self.assertEqual((s.stock, s.prod), before)
        with self.assertRaises(Exception):
            d.act = False


if __name__ == "__main__":
    unittest.main()
