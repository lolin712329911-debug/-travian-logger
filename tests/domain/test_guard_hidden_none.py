"""A6a1（D-32／C-v0.7）：C2 hidden 為 None（山洞容量未知）時，dm-03 guard 不當掉，且不把未知當 0。"""
import unittest

from travian_bot.domain import guard as G
from tests.domain.fixtures import snapshot

TYPES = [336, 1120, 1120, 1120, 1120]


class HiddenNoneTest(unittest.TestCase):
    def test_exposure_is_zero_when_hidden_unknown(self):
        s = snapshot((3000, 3000, 3000, 3000), (100, 100, 100, 100), 4000, 3100, attacks=2)
        s_none = type(s)(**{**s.__dict__, "hidden": None})
        score_none, waste_none, expo_none = G.score_stock(s_none, lambda_exposure=1.0)
        self.assertEqual(expo_none, 0.0)
        self.assertEqual(score_none, waste_none)
        _, _, expo_zero = G.score_stock(snapshot((3000,) * 4, (100,) * 4, 4000, 3100, hidden=(0, 0, 0, 0), attacks=2),
                                        lambda_exposure=1.0)
        self.assertGreater(expo_zero, 0.0)          # hidden=0 會把全部算成暴露；None 不是 0

    def test_decide_guard_runs_with_none(self):
        s = snapshot((3900, 500, 500, 500), (1420, 100, 100, 200), 4000, 3100, attacks=2)
        s = type(s)(**{**s.__dict__, "hidden": None})
        d = G.decide_guard(s, 1, TYPES)
        self.assertTrue(d.act)                      # 溢出仍然會被處理
        self.assertIn("溢出", d.reason)

    def test_no_overflow_no_action_when_hidden_unknown(self):
        s = snapshot((100, 100, 100, 100), (10, 10, 10, 10), 4000, 3100, attacks=3)
        s = type(s)(**{**s.__dict__, "hidden": None})
        self.assertFalse(G.decide_guard(s, 1, TYPES, exposure_mode="always").act)


if __name__ == "__main__":
    unittest.main()
