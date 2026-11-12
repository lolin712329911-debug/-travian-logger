import unittest

from travian_bot.common.decisions import BuildFacts
from travian_bot.common.models import BuildSettings
from travian_bot.domain import build_planner as B
from tests.domain.fixtures import cond, dorf1, dorf2, fields, option, uc

S = BuildSettings(target_level=3, queue_slots=1)


def run(fn, order, d1, truth, st=S, cap=False, **kw):
    """模擬 stage 的 need_facts 迴圈：缺什麼就從 truth（dorf2, upgrade_costs, options）補，最多 12 次。"""
    d2, ucs, opts = truth
    facts, calls = BuildFacts(), []
    for _ in range(12):
        r = fn(order, d1, facts, st, cap, **kw)
        d = r[0] if isinstance(r, tuple) else r
        if d.kind != "need_facts":
            return r, calls
        n = d.need
        calls.append((n.kind, n.aid))
        if n.kind == "dorf2":
            facts = BuildFacts(d2, facts.upgrade_costs, facts.options)
        elif n.kind == "upgrade_cost":
            facts = BuildFacts(facts.dorf2, {**facts.upgrade_costs, n.aid: ucs[n.aid]}, facts.options)
        else:
            facts = BuildFacts(facts.dorf2, facts.upgrade_costs, {**facts.options, n.aid: opts.get(n.aid, ())})
    raise AssertionError("need_facts 迴圈不收斂")


NO = (dorf2(), {}, {})


class PlanTest(unittest.TestCase):
    def test_roi_picks_cheapest_per_gain(self):
        # 等級 1→2：每小時 +4；等級 2→3：+6。成本相同時，等級 2 的田（花費÷新增產量較小）先升
        d1 = dorf1(flds=fields(levels={5: 2}))
        d = B.plan(d1, S, False)
        self.assertEqual((d.kind, d.target.aid, d.target.to_level), ("build", 5, 3))

    def test_wait_queue(self):
        d = B.plan(dorf1(queue=(900,)), S, False)
        self.assertEqual((d.kind, d.wait_s, d.target), ("wait_queue", 905, None))

    def test_wait_resources_seconds(self):
        # 缺 100−10＝90 木，產量 100/h → 3240 秒 ＋30
        d = B.plan(dorf1(stock=(10, 1000, 1000, 1000), flds=fields(levels={1: 2})), S, False)
        self.assertEqual((d.kind, d.target.aid, d.wait_s, d.target.ready_in_s), ("wait_resources", 1, 3270, 3270))

    def test_low_free_crop_prefers_crop_field(self):
        d = B.plan(dorf1(free_crop=4, flds=fields(levels={1: 2})), S, False)
        self.assertEqual(d.target.gid, 4)

    def test_need_storage_and_done(self):
        big = {1: (5000, 100, 100, 100)}
        d = B.plan(dorf1(flds=fields(levels={a: 3 for a in range(1, 19) if a != 1}, costs=big)), S, False)
        self.assertEqual((d.kind, d.target.aid), ("storage_too_small", 1))
        d = B.plan(dorf1(flds=fields(levels={a: 3 for a in range(1, 19)})), S, False)
        self.assertEqual(d.kind, "done")

    def test_capital_cap(self):
        s = BuildSettings(target_level=12, queue_slots=1)
        lv = {a: 10 for a in range(1, 19)}
        self.assertEqual(B.plan(dorf1(flds=fields(levels=lv)), s, False).kind, "done")      # 非首都封頂 10
        self.assertEqual(B.plan(dorf1(flds=fields(levels=lv)), s, True).kind, "build")      # 首都沒有上限資料

    def test_affordable_only_and_extra_and_touched(self):
        d1 = dorf1(stock=(50, 50, 50, 50))
        self.assertEqual(B.plan(d1, S, False, affordable_only=True).kind, "no_affordable")
        ex = [B.UpgradeCandidate(25, 10, 3, (40, 40, 40, 40), 500)]
        d = B.plan(d1, S, False, extra=ex, affordable_only=True)
        self.assertEqual((d.kind, d.target.aid, d.target.to_level), ("build", 25, 4))
        every = set(range(1, 19))
        self.assertEqual(B.plan(dorf1(), S, False, touched=every).kind, "done")


class PlanWithOrderTest(unittest.TestCase):
    def test_res_goal_needs_no_pages(self):
        r, calls = run(B.plan_with_order, [("res", 2)], dorf1(), NO)
        self.assertEqual((r.kind, calls), ("build", []))
        self.assertEqual(r.target.to_level, 2)

    def test_upgrade_existing_building_asks_cost_page_then_builds(self):
        truth = (dorf2({25: (15, 1)}), {25: uc((300, 200, 100, 50), 4000)}, {})
        r, calls = run(B.plan_with_order, [(15, 3)], dorf1(), truth)
        self.assertEqual(calls, [("dorf2", None), ("upgrade_cost", 25)])
        self.assertEqual((r.kind, r.target.aid, r.target.gid, r.target.to_level, r.build_time_s),
                         ("build", 25, 15, 2, 4000))

    def test_building_cost_unreadable_blocks_unless_queue(self):
        truth = (dorf2({25: (15, 1)}), {25: None}, {})
        self.assertEqual(run(B.plan_with_order, [(15, 3)], dorf1(), truth)[0].kind, "plan_stuck")
        self.assertEqual(run(B.plan_with_order, [(15, 3)], dorf1(queue=(100,)), truth, st=BuildSettings(3, 2))[0].kind,
                         "wait_queue")

    def test_new_building_with_prereq_builds_prereq_first(self):
        market = option(17, buildable=False, conds=[cond(15, 3)])
        truth = (dorf2({25: (15, 1)}), {25: uc((100, 100, 100, 100))}, {19: (market,)})
        r, calls = run(B.plan_with_order, [(17, 1)], dorf1(), truth)
        self.assertEqual(calls, [("dorf2", None), ("build_options", 19), ("upgrade_cost", 25)])
        self.assertEqual((r.kind, r.target.aid, r.target.gid), ("build", 25, 15))

    def test_new_building_buildable_and_forbidden_and_missing(self):
        truth = (dorf2(), {}, {19: (option(18),)})
        r, _ = run(B.plan_with_order, [(18, 1)], dorf1(), truth)
        self.assertEqual((r.kind, r.target.aid, r.target.to_level), ("build", 19, 1))
        forb = option(26, buildable=False, conds=[cond(25, 1, forbidden=True)])
        r, _ = run(B.plan_with_order, [(26, 1)], dorf1(), (dorf2(), {}, {19: (forb,)}))
        self.assertEqual(r.kind, "plan_stuck")
        r, _ = run(B.plan_with_order, [(22, 1)], dorf1(), (dorf2(), {}, {19: (option(18),)}))
        self.assertEqual(r.kind, "plan_stuck")

    def test_no_free_slot(self):
        full = dorf2({a: (11, 1) for a in range(19, 39)})
        r, calls = run(B.plan_with_order, [(18, 1)], dorf1(), (full, {}, {}))
        self.assertEqual((r.kind, calls), ("no_free_slot", [("dorf2", None)]))

    def test_storage_fix_upgrades_warehouse_first(self):
        big = {1: (5000, 100, 100, 100)}
        d1 = dorf1(flds=fields(levels={a: 3 for a in range(2, 19)}, costs=big))
        truth = (dorf2({25: (10, 5)}), {25: uc((200, 200, 200, 100))}, {})
        r, _ = run(B.plan_with_order, [("res", 3)], d1, truth)
        self.assertEqual((r.kind, r.target.gid, r.target.to_level), ("build", 10, 6))

    def test_touched_empty_slot_waits_instead_of_building_twice(self):
        # 本輪剛送出新建築、dorf2 還沒反映（乾跑就是這樣）：不要重複蓋
        truth = (dorf2(), {}, {19: (option(18),)})
        r, _ = run(B.plan_with_order, [(18, 1)], dorf1(), truth, touched={19})
        self.assertEqual((r.kind, r.wait_s), ("wait_queue", 600))

    def test_done_and_queue(self):
        lv = {a: 3 for a in range(1, 19)}
        r, _ = run(B.plan_with_order, [("res", 3)], dorf1(flds=fields(levels=lv)), NO)
        self.assertEqual(r.kind, "done")
        r, _ = run(B.plan_with_order, [("res", 4)], dorf1(queue=(120,)), NO)
        self.assertEqual((r.kind, r.wait_s), ("wait_queue", 125))

    def test_field_under_construction_waits(self):
        lv = {a: 5 for a in range(1, 19)}
        d1 = dorf1(flds=fields(levels=lv, building=set(range(1, 19))))
        r, _ = run(B.plan_with_order, [("res", 6)], d1, NO, st=BuildSettings(3, 2))
        self.assertEqual((r.kind, r.wait_s), ("wait_queue", 600))      # 讀不到佇列秒數：舊碼預設 600

    def test_res_goal_capped_for_non_capital(self):
        lv = {a: 10 for a in range(1, 19)}
        r, _ = run(B.plan_with_order, [("res", 12)], dorf1(flds=fields(levels=lv)), NO)
        self.assertEqual(r.kind, "done")
        r, _ = run(B.plan_with_order, [("res", 12)], dorf1(flds=fields(levels=lv)), NO, cap=True)
        self.assertEqual(r.kind, "build")


class PlanWithOrderMoreTest(unittest.TestCase):
    def test_low_free_crop_prefers_crop_field_in_res_goal(self):
        d1 = dorf1(free_crop=4, flds=fields(levels={1: 2}))          # aid 1（木）較划算，但穀產出太低
        r, _ = run(B.plan_with_order, [("res", 3)], d1, NO)
        self.assertEqual((r.kind, r.target.gid), ("build", 4))

    def test_storage_fix_gives_up_when_warehouse_is_max(self):
        big = {1: (5000, 100, 100, 100)}
        d1 = dorf1(flds=fields(levels={a: 3 for a in range(2, 19)}, costs=big))
        r, _ = run(B.plan_with_order, [("res", 3)], d1, (dorf2({25: (10, 20)}), {}, {}))
        self.assertEqual(r.kind, "plan_stuck")
        self.assertIn("已滿級", r.reason)

    def test_storage_fix_unreadable_cost_and_no_warehouse(self):
        big = {1: (5000, 100, 100, 100)}
        d1 = dorf1(flds=fields(levels={a: 3 for a in range(2, 19)}, costs=big))
        r, _ = run(B.plan_with_order, [("res", 3)], d1, (dorf2(), {}, {19: (option(10),)}))
        self.assertEqual((r.kind, r.target.gid, r.target.to_level), ("build", 10, 1))     # 沒有倉庫：先蓋一棟


class RoiOrderTest(unittest.TestCase):
    def test_field_without_roi_data_ranks_after_fields_with_data(self):
        # 等級 10→11 沒有產量表（Legends 沒有 11 級資料）：即使更便宜也排在有 ROI 資料的田後面
        lv = {a: 10 for a in range(1, 19)}
        lv[2] = 1
        d1 = dorf1(flds=fields(levels=lv, costs={1: (10, 10, 10, 10), 2: (300, 300, 300, 300)}))
        d = B.plan(d1, BuildSettings(target_level=11, queue_slots=1), True)
        self.assertEqual(d.target.aid, 2)


class FillInCandidatesTest(unittest.TestCase):
    def test_lists_affordable_later_goals(self):
        # 主目標 res:2：aid 1 缺資源；後面 15:1 付得起
        costs = {a: (2000, 2000, 2000, 2000) for a in range(1, 19)}
        d1 = dorf1(stock=(100, 100, 100, 100), flds=fields(costs=costs))
        truth = (dorf2({25: (15, 0)}), {25: uc((50, 50, 50, 50), 700)}, {})
        (main, cands), _ = run(B.fill_in_candidates, [("res", 2), (15, 1)], d1, truth)
        self.assertEqual(main.kind, "wait_resources")
        self.assertEqual([(c.target.aid, c.target.gid, c.build_time_s) for c in cands], [(25, 15, 700)])

    def test_no_candidates_when_main_not_waiting(self):
        (main, cands), _ = run(B.fill_in_candidates, [("res", 2)], dorf1(), NO)
        self.assertEqual((main.kind, cands), ("build", []))

    def test_next_target_ignores_queue(self):
        d1 = dorf1(queue=(300,), stock=(10, 1000, 1000, 1000))
        d = B.next_target([("res", 2)], d1, BuildFacts(), S, False)
        self.assertEqual(d.kind, "wait_resources")
        self.assertEqual(B.plan_with_order([("res", 2)], d1, BuildFacts(), S, False).kind, "wait_queue")


if __name__ == "__main__":
    unittest.main()
