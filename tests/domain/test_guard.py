import unittest

from travian_bot.common.decisions import BuildDecision, BuildTarget
from travian_bot.domain import guard as G
from tests.domain.fixtures import snapshot

TYPES = [336, 1120, 1120, 1120, 1120]
HID = (2000,) * 4


def run(stock, prod, cur, att=0, **kw):
    return G.decide_guard(snapshot(stock, prod, 4000, 3100, HID, att), cur, TYPES, **kw)


class DecideGuardTest(unittest.TestCase):
    def test_overflow_switches_away_from_full_resource(self):
        d = run((3900, 500, 500, 500), (1420, 100, 100, 200), 1)       # 木快滿、目前押木
        self.assertEqual((d.act, d.focus, d.exposure), (True, 2, "incoming"))
        self.assertIn("溢出", d.reason)

    def test_demand_first_when_gap_needs_current_resource(self):
        d = run((3900, 500, 500, 500), (1420, 100, 100, 200), 1, gaps={1: 3000})
        self.assertEqual((d.act, d.focus), (False, None))

    def test_nothing_at_risk(self):
        d = run((500,) * 4, (100,) * 4, 0)
        self.assertEqual((d.act, d.focus), (False, None))
        self.assertIn("不會溢出", d.reason)

    def test_exposure_counts_only_with_attack_or_always(self):
        stock, prod = (500, 3000, 500, 500), (100,) * 4
        self.assertEqual(run(stock, prod, 0, att=1).focus, 4)
        self.assertFalse(run(stock, prod, 0, att=0).act)
        self.assertFalse(run(stock, prod, 0, att=None).act)
        d = run(stock, prod, 0, att=0, exposure_mode="always")
        self.assertEqual((d.act, d.focus, d.exposure), (True, 4, "always"))

    def test_unreadable_focus_does_nothing(self):
        for cur, types in ((None, TYPES), (1, None), (1, [])):
            d = G.decide_guard(snapshot(), cur, types)
            self.assertEqual((d.act, d.focus), (False, None))

    def test_crop_floor_excludes_candidates(self):
        # 同樣木快溢出、押木：穀淨產量 200 時切磚；穀 −100 時磚／鐵（穀仍 −100）被排除，改切穀
        self.assertEqual(run((3900, 500, 500, 500), (1420, 100, 100, 200), 1).focus, 2)
        d = run((3900, 500, 500, 500), (1420, 100, 100, -100), 1)
        self.assertEqual((d.act, d.focus), (True, 4))

    def test_bad_exposure_mode(self):
        with self.assertRaises(ValueError):
            run((500,) * 4, (100,) * 4, 0, exposure_mode="off")

    def test_default_capacity_when_unread(self):
        s = snapshot((3900, 500, 500, 500), (1420, 100, 100, 200), 0, 0, HID)
        self.assertEqual(G.decide_guard(s, 1, TYPES).focus, 2)       # 用 4000／3100 的舊預設，結果與讀得到時相同

    def test_ready_in_h_keeps_demand_first(self):
        d = run((3900, 500, 500, 500), (1420, 100, 100, 200), 1, gaps={}, ready_in_h=2.0)
        self.assertEqual((d.act, d.focus), (True, 2))                 # 目標現在就付得起：所有候選一樣快，只看評分


    def test_long_construction_wait_makes_every_candidate_equally_fast(self):
        # 同樣有「缺木 3000」的缺口：馬上要買時保木（不動）；施工還要 100 小時時所有候選一樣慢，只剩評分決定 → 切磚
        stock, prod = (3900, 500, 500, 500), (1420, 100, 100, 200)
        self.assertFalse(run(stock, prod, 1, gaps={1: 3000}, ready_in_h=0.0).act)
        d = run(stock, prod, 1, gaps={1: 3000}, ready_in_h=100.0)
        self.assertEqual((d.act, d.focus), (True, 2))


class ScoreTest(unittest.TestCase):
    def test_overflow_and_exposure(self):
        s = snapshot((3900, 500, 500, 500), (1420, 100, 100, 200), 4000, 3100, HID)
        self.assertEqual(G.overflow({1: 3900, 2: 0, 3: 0, 4: 0}, {1: 1420, 2: 0, 3: 0, 4: 0}, 1.25,
                                    {1: 4000, 2: 4000, 3: 4000, 4: 3100})[1], 1675)
        score, w, e = G.score_stock(s)
        self.assertEqual((w, e, score), (1675, 2000, 1675 + 0.5 * 2000))

    def test_exposure_ignores_overflow_part(self):
        e = G.exposure({1: 3900, 2: 0, 3: 0, 4: 0}, {1: 1420, 2: 0, 3: 0, 4: 0}, 1.25, {r: 2000 for r in (1, 2, 3, 4)},
                       {1: 4000, 2: 4000, 3: 4000, 4: 3100})
        self.assertEqual(e[1], 2000)                  # min(4000, 5675) − 2000


class GapsTest(unittest.TestCase):
    t = BuildTarget(1, 1, "伐木場", 2, (500, 100, 100, 100), 0)

    def test_wait_resources(self):
        d = BuildDecision("wait_resources", self.t, "x", wait_s=60)
        self.assertEqual(G.gaps_from_decision(d, (200, 500, 500, 500), 1.5), ({1: 300}, 1.5))

    def test_exact_stock_is_not_a_gap(self):
        d = BuildDecision("wait_resources", self.t, "x")
        self.assertEqual(G.gaps_from_decision(d, (500, 100, 100, 100), 0)[0], {})

    def test_build_has_no_gaps(self):
        d = BuildDecision("build", self.t, "x")
        self.assertEqual(G.gaps_from_decision(d, (1000,) * 4, -3), ({}, 0.0))

    def test_other_kinds_are_none(self):
        for k in ("wait_queue", "storage_too_small", "plan_stuck", "no_free_slot", "done", "need_facts", "no_affordable"):
            self.assertIsNone(G.gaps_from_decision(BuildDecision(k, None, "x"), (0,) * 4, 0))


if __name__ == "__main__":
    unittest.main()
