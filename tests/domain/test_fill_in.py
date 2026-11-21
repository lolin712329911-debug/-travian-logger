import unittest

from travian_bot.common.decisions import FillCandidate
from travian_bot.common.models import BuildTarget
from travian_bot.domain import fill_in as F
from tests.domain.fixtures import snapshot

STOCK, PROD = (1000,) * 4, (100,) * 4


class StartHoursTest(unittest.TestCase):
    def test_hours_and_inf(self):
        self.assertEqual(F.start_hours(STOCK, PROD, (1500,) * 4), 5.0)
        self.assertEqual(F.start_hours(STOCK, PROD, (900,) * 4), 0.0)
        self.assertEqual(F.start_hours(STOCK, (100, 100, 100, 0), (1000, 1000, 1000, 1500)), F.INF)

    def test_hidden_caps_stock_per_resource(self):
        self.assertEqual(F.start_hours(STOCK, PROD, (1500,) * 4, hidden=(200, 200, 200, 200)), 13.0)
        self.assertEqual(F.start_hours(STOCK, PROD, (1500,) * 4, hidden=(1000, 1000, 1000, 0)), 15.0)

    def test_queue_free_hours(self):
        self.assertEqual(F.queue_free_hours([], 1, 1800), 0.5)            # 1 格：F 自己佔滿
        self.assertEqual(F.queue_free_hours([3600], 2, 7200), 1.0)
        self.assertEqual(F.queue_free_hours([3600], 3, 7200), 0.0)        # 還有空位


class ShouldFillTest(unittest.TestCase):
    def test_slows_main_goal_is_rejected(self):
        c = F.should_fill(STOCK, PROD, (1500,) * 4, (100,) * 4, 1800, [], 1)
        self.assertFalse(c.ok)
        self.assertEqual((c.t0, c.t1, c.tq), (5.0, 6.0, 0.5))
        self.assertIn("會拖慢主目標", c.why)

    def test_slack_allows(self):
        self.assertTrue(F.should_fill(STOCK, PROD, (1500,) * 4, (100,) * 4, 1800, [], 1, slack_h=1.0).ok)

    def test_not_affordable(self):
        c = F.should_fill(STOCK, PROD, (1500,) * 4, (1100, 0, 0, 0), 600, [], 1)
        self.assertEqual((c.ok, c.why), (False, "插隊項目現在付不起"))

    def test_attack_relaxation(self):
        args = (STOCK, PROD, (1500,) * 4, (100,) * 4, 1800, [], 1)
        self.assertFalse(F.should_fill(*args, hidden=(200,) * 4, attacks=0).ok)
        r = F.should_fill(*args, hidden=(200,) * 4, attacks=1)               # 不知道 ETA：放寬
        self.assertTrue(r.ok and r.relaxed)
        self.assertEqual((r.t0, r.t1), (13.0, 13.0))
        self.assertFalse(F.should_fill(*args, hidden=(200,) * 4, attacks=1, attack_eta_s=20 * 3600).relaxed)
        self.assertFalse(F.should_fill(*args, hidden=(200,) * 4, attacks=None).relaxed)   # 未知＝沒有

    def test_queue_blocks_even_when_resources_fine(self):
        a = (STOCK, PROD, (500,) * 4, (100,) * 4, 7200, [3600])
        self.assertFalse(F.should_fill(*a, 2).ok)          # 2 格：F 佔滿後要等 1 小時才有空位 > 0
        self.assertTrue(F.should_fill(*a, 3).ok)

    def test_zero_production_cannot_judge(self):
        c = F.should_fill(STOCK, (0, 0, 0, 0), (1500,) * 4, (100,) * 4, 600, [], 1)
        self.assertFalse(c.ok)
        self.assertIn("產量 ≤ 0", c.why)


def cand(aid, cost, secs):
    return FillCandidate(BuildTarget(aid, 15, "村莊大樓", 2, cost, 0), secs)


class PickFillInTest(unittest.TestCase):
    main = BuildTarget(1, 1, "伐木場", 2, (1500,) * 4, 3000)

    def test_picks_first_that_passes(self):
        cs = [cand(25, (100,) * 4, 1800), cand(26, (100,) * 4, 60)]
        d = F.pick_fill_in(self.main, cs, snapshot(), [], 1, slack_h=0.0)
        self.assertEqual((d.act, d.target), (False, None))
        d = F.pick_fill_in(self.main, cs, snapshot(), [], 1, slack_h=1.0)
        self.assertEqual((d.act, d.target.aid), (True, 25))

    def test_unknown_build_time_is_skipped(self):
        d = F.pick_fill_in(self.main, [cand(25, (100,) * 4, None)], snapshot(), [], 1, slack_h=9)
        self.assertEqual((d.act, d.target), (False, None))
        self.assertIn("工期未知", d.reason)

    def test_empty(self):
        self.assertFalse(F.pick_fill_in(self.main, [], snapshot(), [], 1).act)

    def test_snapshot_attack_and_hidden_are_used(self):
        s = snapshot(hidden=(200,) * 4, attacks=2)
        d = F.pick_fill_in(self.main, [cand(25, (100,) * 4, 1800)], s, [], 1)
        self.assertTrue(d.act)
        self.assertIn("來襲放寬", d.reason)


if __name__ == "__main__":
    unittest.main()
