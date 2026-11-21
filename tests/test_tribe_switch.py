"""對 TRIBES 每個種族（＋假 ServerProfile＋樣本快照）跑每個 domain 規劃函式：不得出錯、不得寫死高盧（A3a 起；之後每個 domain WP 都加入）。"""
import os
import re
import unittest

from travian_bot.common.decisions import BuildFacts
from travian_bot.common.models import BuildSettings, ServerProfile
from travian_bot.common.tribe_data import TRIBES
from travian_bot.domain import build_planner as B, fill_in as F, guard as G, plan_validate as V
from tests.domain.fixtures import dorf1, dorf2, fields, option, snapshot, uc

DOMAIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "travian_bot", "domain")


def settings_for(spec):
    """和 config_schema.settings_from_config 相同：queue_slots 留空＝種族基準條數。"""
    return BuildSettings(target_level=10, queue_slots=spec.base_queue_slots)


class TribeSwitchTest(unittest.TestCase):
    def test_every_domain_function_runs_for_every_tribe(self):
        facts = BuildFacts(dorf2({25: (15, 1)}), {25: uc((100, 100, 100, 100))}, {19: (option(18), option(17))})
        order = [("res", 2), (15, 3), (18, 1)]
        for key, spec in TRIBES.items():
            with self.subTest(tribe=key):
                prof = ServerProfile("s1", "https://ts1.example", key, "2026-11-01T00:00:00Z", "Asia/Taipei")
                self.assertEqual(prof.tribe, key)
                st, snap = settings_for(spec), snapshot(hidden=(2000,) * 4, attacks=1)
                d1 = dorf1()
                for is_capital in (False, True):
                    self.assertEqual(B.plan(d1, st, is_capital).kind, "build")
                    self.assertIn(B.plan_with_order(order, d1, facts, st, is_capital).kind, ("build", "wait_resources"))
                    main, cands = B.fill_in_candidates(order, d1, facts, st, is_capital)
                    F.pick_fill_in(main.target, cands, snap, [], st.queue_slots) if main.target else None
                    B.next_target(order, d1, facts, st, is_capital)
                raw = V.parse_build_order("res:2,15:3,18:1")
                self.assertEqual(V.validate_order(raw, d1, facts, False, 1, "t").verdict, "proceed")
                g = G.decide_guard(snap, 0, [336, 1120, 1120, 1120, 1120], exposure_mode="always")
                self.assertIn(g.act, (True, False))

    def test_queue_length_comes_from_tribe_data_not_a_constant(self):
        """羅馬基準 2 條、其他 1 條：佇列已有一項時，羅馬還能排、其他種族要等。"""
        busy = dorf1(queue=(900,))
        for key, spec in TRIBES.items():
            kind = B.plan(busy, settings_for(spec), False).kind
            self.assertEqual(kind, "build" if spec.base_queue_slots >= 2 else "wait_queue", key)

    def test_no_hardcoded_tribe_in_domain_sources(self):
        names = [n for spec in TRIBES.values() for n in (spec.key, spec.name)]
        names += ["高卢", "条顿", "日耳曼", "gauls", "romans", "teutons", "egyptians"]
        pat = re.compile("|".join(re.escape(n) for n in names), re.I)
        for fn in sorted(os.listdir(DOMAIN_DIR)):
            if fn.endswith(".py"):
                with open(os.path.join(DOMAIN_DIR, fn), encoding="utf-8") as fh:
                    code = [ln for ln in fh.read().splitlines() if not ln.lstrip().startswith("#")]
                self.assertIsNone(pat.search("\n".join(code)), fn)


if __name__ == "__main__":
    unittest.main()
