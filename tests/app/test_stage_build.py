# -*- coding: utf-8 -*-
"""ap-10 build stage（A6a2）。domain／actions／parsers／plan_repo 在 stage 模組層級換成假的。
未實測（寫的時候沒有整個 repo 可以跑）。"""
import dataclasses
import unittest
from types import SimpleNamespace
from unittest import mock

from travian_bot.app.stages import _util as U
from travian_bot.app.stages import build as B
from travian_bot.common.decisions import BuildDecision, ExecResult
from travian_bot.common.models import BuildTarget, PlanRejection, PlanVerdict, VillageSnapshot
from travian_bot.common.modes import Mode
from travian_bot.domain.build_planner import UpgradeCandidate
from travian_bot.infra.store.plan_repo import RawBuildOrder

from .fakes import NOW_S, FakeGateway, make_rc, make_vc

HOME_HTML = '<div id="stockBar"></div>'


def tgt(aid=5, gid=1, level=3, cost=(100, 100, 100, 100), ready=0):
    return BuildTarget(aid=aid, gid=gid, name="伐木場", to_level=level, cost=cost, ready_in_s=ready)


def snap():
    return VillageSnapshot(did=101, ts_utc=NOW_S, stock=(500, 500, 500, 500), prod=(100, 100, 100, 100), cap_wh=4000,
                           cap_gr=4000, hidden=(2000,) * 4, queue_free_in_s=0, queue_slots_used=0, next_target=None,
                           merchants=None, incoming_res=(), outgoing_res=(), incoming_attacks=0, units_home=None,
                           units_away=None)


def d1(cap_wh=4000, cap_gr=4000, queue=()):
    return SimpleNamespace(stock=(500, 500, 500, 500), prod=(100, 100, 100, 100), cap_wh=cap_wh, cap_gr=cap_gr,
                           free_crop=50, fields=(), queue=tuple(queue), incoming_attacks=0)


class Env:
    """一次測試的環境：rc、錄下的 state 寫入與通知。"""

    def __init__(self, prev_status=None, cfg=None, order_text=None):
        self.rc, self.rec = make_rc(gateway=FakeGateway(pages={"dorf1.php": HOME_HTML}),
                                    cfg=cfg if cfg is not None else {"main_did": 101, "max_builds": 2}, dry_flag=False)
        self.upserts = []
        self.rc.io = dataclasses.replace(
            self.rc.io, read_state=lambda sh, did, keys: ({} if prev_status is None else {"plan_status": prev_status}),
            upsert_state=lambda sh, did, rows, ts: self.upserts.append(rows) or len(rows))
        self.vc = make_vc(modes={})
        self.order_text = order_text

    def state(self):
        return {k: v for k, v, _n in self.upserts[-1]} if self.upserts else None


def run_build(env, *, raw=None, load_exc=None, verdict=None, plan_seq=(), order_seq=(), exec_seq=(),
              mode=Mode.LIVE, storage_cands=None, dorf1=None):
    load = mock.Mock(side_effect=load_exc) if load_exc else mock.Mock(return_value=raw)
    with mock.patch.object(B.plan_repo, "load_build_order", load), \
            mock.patch.object(B, "parse_dorf1", return_value=dorf1 or d1()), \
            mock.patch.object(B, "validation_need", return_value=None), \
            mock.patch.object(B, "validate_order", return_value=verdict), \
            mock.patch.object(B, "plan", side_effect=list(plan_seq)) as plan, \
            mock.patch.object(B, "plan_with_order", side_effect=list(order_seq)) as pwo, \
            mock.patch.object(B, "_storage_candidates", return_value=storage_cands or []) as sc, \
            mock.patch.object(B, "submit_upgrade", side_effect=list(exec_seq)) as sub:
        try:
            res = B.run(env.rc, env.vc, snap(), mode)
            exc = None
        except Exception as e:  # noqa: BLE001
            res, exc = None, e
    return SimpleNamespace(res=res, exc=exc, plan=plan, pwo=pwo, sub=sub, sc=sc, load=load)


OK = ExecResult("ok", "已送出並驗證", 5, True)


class BuildStageTest(unittest.TestCase):
    def test_stage_registration_fields(self):
        self.assertEqual((B.STAGE.name, B.STAGE.scope, B.STAGE.mode_key, B.STAGE.order),
                         ("build", "village", None, 30))

    def test_max_builds_zero_is_skipped(self):
        env = Env(cfg={"main_did": 101, "max_builds": 0})
        r = run_build(env)
        self.assertEqual(r.res.status, "skipped")
        r.load.assert_not_called()

    # --- 沒有計畫：舊流程
    def test_blank_build_order_uses_legacy_plan_and_says_so(self):
        env = Env()
        r = run_build(env, raw=None, plan_seq=[BuildDecision("build", tgt(), "x", build_time_s=60),
                                               BuildDecision("wait_resources", tgt(aid=6, cost=(9000, 0, 0, 0), ready=900), "x", wait_s=900)],
                      exec_seq=[OK])
        self.assertEqual(r.res.status, "ok")
        self.assertEqual(r.plan.call_count, 2)
        r.pwo.assert_not_called()
        acts = [(a.action, a.result) for a in r.res.actions]
        self.assertEqual(acts, [("升級", "ok"), ("建城等待", "skipped")])
        self.assertIn("無 build_order，走舊流程", r.res.actions[0].detail)
        self.assertTrue(U.has_note(env.rc, 101, "built"))
        self.assertEqual(r.res.snapshot_updates["next_target"].ready_in_s, 900)
        self.assertEqual(env.state()["plan_status"], "none")
        self.assertEqual(env.state()["plan_needs_refill"], False)

    def test_read_failure_does_not_fall_back_to_legacy(self):
        env = Env()
        r = run_build(env, load_exc=RuntimeError("sheet down"))
        self.assertIsInstance(r.exc, RuntimeError)
        r.plan.assert_not_called()
        r.sub.assert_not_called()
        self.assertEqual(env.upserts, [])

    # --- hold
    def test_hold_writes_one_row_and_nothing_else(self):
        env = Env()
        verdict = PlanVerdict(101, NOW_S, "hold", 1, (PlanRejection(1, "bad_format", "看不懂"),))
        r = run_build(env, raw=RawBuildOrder("bad", "config"), verdict=verdict)
        self.assertEqual([(a.action, a.result) for a in r.res.actions], [(B.ACTION_PLAN_HOLD, "skipped")])
        self.assertIn("bad_format", r.res.actions[0].detail)
        r.plan.assert_not_called()          # 不走成長清單、不退回舊流程
        r.pwo.assert_not_called()
        r.sub.assert_not_called()
        self.assertEqual(env.upserts, [])    # hold 不寫 plan_*
        self.assertEqual(len(env.rec.notes), 1)

    # --- 有計畫
    def test_plan_active_builds_and_marks_active(self):
        env = Env()
        verdict = PlanVerdict(101, NOW_S, "proceed", 1, ())
        r = run_build(env, raw=RawBuildOrder("res:5", "config"), verdict=verdict,
                      order_seq=[BuildDecision("build", tgt(), "x", build_time_s=60),
                                 BuildDecision("wait_queue", None, "x", wait_s=60)], exec_seq=[OK])
        self.assertEqual(env.state()["plan_status"], "active")
        self.assertEqual(r.res.actions[0].action, "升級")
        self.assertNotIn("走舊流程", r.res.actions[0].detail)

    def test_plan_done_goes_to_growth_tier_1_and_still_acts(self):
        env = Env()
        verdict = PlanVerdict(101, NOW_S, "proceed", 1, ())
        r = run_build(env, raw=RawBuildOrder("res:5", "config"), verdict=verdict,
                      order_seq=[BuildDecision("done", None, ""), BuildDecision("done", None, "")],
                      plan_seq=[BuildDecision("build", tgt(), "x", build_time_s=60),
                                BuildDecision("wait_queue", None, "x", wait_s=60)], exec_seq=[OK])
        self.assertEqual(r.sub.call_count, 1)
        self.assertIn("計畫已達成，成長清單第 1 層", r.res.actions[0].detail)
        self.assertEqual(env.state()["plan_status"], "exhausted")
        self.assertEqual(env.state()["plan_needs_refill"], True)
        self.assertTrue(any("計畫已用完" in n for n in env.rec.notes))

    def test_growth_tier_1_empty_is_idle_and_notifies_once(self):
        verdict = PlanVerdict(101, NOW_S, "proceed", 1, ())
        env = Env(prev_status=None)
        r = run_build(env, raw=RawBuildOrder("res:5", "config"), verdict=verdict,
                      order_seq=[BuildDecision("done", None, "")], plan_seq=[BuildDecision("done", None, "")])
        r.sub.assert_not_called()
        self.assertEqual(env.state()["plan_status"], "idle")
        self.assertEqual(env.state()["plan_needs_refill"], True)
        self.assertEqual(len(env.rec.notes), 1)
        env2 = Env(prev_status="idle")                         # 前值已是 idle：不再通知
        run_build(env2, raw=RawBuildOrder("res:5", "config"), verdict=verdict,
                  order_seq=[BuildDecision("done", None, "")], plan_seq=[BuildDecision("done", None, "")])
        self.assertEqual(env2.rec.notes, [])

    # --- need_storage
    def test_storage_too_small_upgrades_warehouse_for_wood_clay_iron(self):
        env = Env()
        big = tgt(aid=8, cost=(5000, 100, 100, 100))
        wh = UpgradeCandidate(25, 10, 5, (100, 100, 100, 0), 120, False)
        r = run_build(env, raw=None, plan_seq=[BuildDecision("storage_too_small", big, ""),
                                               BuildDecision("wait_queue", None, "x", wait_s=60)],
                      exec_seq=[OK], storage_cands=[wh])
        sent = r.sub.call_args[0][2]
        self.assertEqual((sent.aid, sent.gid, sent.to_level), (25, 10, 6))
        self.assertEqual(r.sc.call_args[0][2], (10,))

    def test_storage_too_small_upgrades_granary_for_crop(self):
        env = Env()
        big = tgt(aid=8, cost=(100, 100, 100, 5000))
        gr = UpgradeCandidate(26, 11, 3, (100, 100, 100, 0), 120, False)
        r = run_build(env, raw=None, plan_seq=[BuildDecision("storage_too_small", big, ""),
                                               BuildDecision("wait_queue", None, "x", wait_s=60)],
                      exec_seq=[OK], storage_cands=[gr])
        self.assertEqual(r.sub.call_args[0][2].gid, 11)
        self.assertEqual(r.sc.call_args[0][2], (11,))

    def test_storage_too_small_without_storage_building_is_stuck_not_build(self):
        env = Env()
        big = tgt(aid=8, cost=(5000, 100, 100, 100))
        r = run_build(env, raw=None, plan_seq=[BuildDecision("storage_too_small", big, "")], storage_cands=[])
        r.sub.assert_not_called()
        self.assertEqual([a.action for a in r.res.actions], [B.ACTION_PLAN_STUCK])
        self.assertIn("找不到可升級的倉庫", r.res.actions[0].detail)
        self.assertEqual(len(env.rec.notes), 1)               # 卡住要通知（最近一列超過 6 小時或沒有才通知）

    def test_affordable_only_alternative_when_attacked_and_transfer_on(self):
        env = Env()
        env.vc = make_vc(modes={"item_transfer": "live"})
        wait = BuildDecision("wait_resources", tgt(aid=6, cost=(9000, 0, 0, 0), ready=900), "x", wait_s=900)
        cheap = BuildDecision("build", tgt(aid=7), "付得起", build_time_s=60)
        under_attack = d1()
        under_attack.incoming_attacks = 1
        r = run_build(env, raw=None, dorf1=under_attack, plan_seq=[wait, cheap, BuildDecision("wait_queue", None, "x", wait_s=60)],
                      exec_seq=[OK])
        self.assertTrue(r.plan.call_args_list[1].kwargs["affordable_only"])
        self.assertEqual(r.sub.call_args[0][2].aid, 7)
        self.assertIn("改做付得起的項目", r.res.actions[0].detail)

    def test_no_affordable_alternative_when_transfer_off_or_no_attack(self):
        wait = BuildDecision("wait_resources", tgt(aid=6, cost=(9000, 0, 0, 0), ready=900), "x", wait_s=900)
        env = Env()                                            # item_transfer 沒開
        under_attack = d1()
        under_attack.incoming_attacks = 1
        r = run_build(env, raw=None, dorf1=under_attack, plan_seq=[wait])
        self.assertEqual(r.plan.call_count, 1)
        env2 = Env()
        env2.vc = make_vc(modes={"item_transfer": "live"})
        r2 = run_build(env2, raw=None, dorf1=d1(), plan_seq=[wait])           # 沒有來襲（incoming_attacks＝0）
        self.assertEqual(r2.plan.call_count, 1)

    # --- 迴圈與乾跑
    def test_stops_after_max_builds(self):
        env = Env(cfg={"main_did": 101, "max_builds": 1})
        r = run_build(env, raw=None, plan_seq=[BuildDecision("build", tgt(), "x", build_time_s=60)], exec_seq=[OK])
        self.assertEqual(r.sub.call_count, 1)
        self.assertEqual([a.action for a in r.res.actions], ["升級"])

    def test_failed_build_stops_and_reports_failed(self):
        env = Env()
        r = run_build(env, raw=None, plan_seq=[BuildDecision("build", tgt(), "x", build_time_s=60)],
                      exec_seq=[ExecResult("failed", "沒扣資源", 5, False)])
        self.assertEqual((r.res.status, r.sub.call_count), ("failed", 1))
        self.assertEqual(r.res.snapshot_updates, {})

    def test_dry_simulates_queue_and_touched_and_makes_no_snapshot_update(self):
        env = Env()
        r = run_build(env, raw=None, mode=Mode.DRY,
                      plan_seq=[BuildDecision("build", tgt(aid=5), "x", build_time_s=60),
                                BuildDecision("wait_queue", None, "x", wait_s=60)],
                      exec_seq=[ExecResult("dry", "會送出", 3, None)])
        second = r.plan.call_args_list[1].kwargs
        self.assertEqual(second["touched"], {5})
        self.assertEqual(second["queue_secs"], [60])
        self.assertEqual(r.res.snapshot_updates, {})
        self.assertTrue(U.has_note(env.rc, 101, "built"))
        self.assertEqual([a.result for a in r.res.actions], ["dry", "skipped"])

    def test_state_write_failure_only_warns(self):
        env = Env()
        env.rc.io = dataclasses.replace(env.rc.io, upsert_state=mock.Mock(side_effect=RuntimeError("x")))
        r = run_build(env, raw=None, plan_seq=[BuildDecision("wait_queue", None, "x", wait_s=60)])
        self.assertEqual(r.res.status, "ok")
        self.assertTrue(any("plan_*" in w for w in env.rc.warnings))


class HelpersTest(unittest.TestCase):
    def test_remaining_counts_unmet_steps(self):
        f = lambda aid, gid, lv: SimpleNamespace(aid=aid, gid=gid, level=lv)
        d = SimpleNamespace(fields=(f(1, 1, 9), f(2, 2, 10), f(3, 3, 10), f(4, 4, 10)))
        dorf2 = SimpleNamespace(slots=(SimpleNamespace(aid=20, gid=15, level=3),))
        self.assertEqual(B._remaining([("res", 10), (15, 5)], d, dorf2, False), 2)     # 伐木場 9<10、村莊大樓 3<5
        self.assertEqual(B._remaining([("res", 9), (15, 3)], d, dorf2, False), 0)
        self.assertEqual(B._remaining([(15, 3)], d, None, False), 1)                   # 沒有 dorf2：建築步驟算未達成

    def test_ready_seconds(self):
        self.assertEqual(B._ready_s((100, 100, 100, 100), d1()), 0)
        self.assertEqual(B._ready_s((700, 100, 100, 100), d1()), int(200 / 100 * 3600) + 30)


if __name__ == "__main__":
    unittest.main()
