# -*- coding: utf-8 -*-
"""A6a2 stages（ap-11 item_transfer、ap-12 focus、ap-13 fill_in、ap-14 guard、ap-17 hero）與 registry 登記。
只測 stage 這一層：domain／actions／parsers 在 stage 模組層級換成假的（它們各有自己的測試）。
未實測（寫的時候沒有整個 repo 可以跑）。"""
import dataclasses
import unittest
from types import SimpleNamespace
from unittest import mock

from travian_bot.app import registry as REG
from travian_bot.app.stages import _util as U
from travian_bot.app.stages import fill_in as FI
from travian_bot.app.stages import focus as FO
from travian_bot.app.stages import guard as GU
from travian_bot.app.stages import hero as HE
from travian_bot.app.stages import item_transfer as IT
from travian_bot.common.decisions import (BuildDecision, ExecResult, FillCandidate, FillInDecision, FocusDecision,
                                          GuardDecision)
from travian_bot.common.models import BuildTarget, VillageSnapshot
from travian_bot.common.modes import Mode
from travian_bot.common.parsed import Adventure, HeroFocus, HeroState, TransferItem, TransferState
from travian_bot.infra.gateway import GatewayError

from .fakes import NOW_S, FakeGateway, make_rc, make_vc

HOME_HTML = '<div id="stockBar"></div>'
TYPES = (336, 1120, 1120, 1120, 1120)


def target(cost=(1000, 1000, 1000, 1000), ready=3600, aid=5, gid=1, to_level=3):
    return BuildTarget(aid=aid, gid=gid, name="伐木場", to_level=to_level, cost=cost, ready_in_s=ready)


def snap(**kw):
    base = dict(did=101, ts_utc=NOW_S, stock=(500, 500, 500, 500), prod=(100, 100, 100, 100), cap_wh=4000, cap_gr=4000,
                hidden=(2000, 2000, 2000, 2000), queue_free_in_s=0, queue_slots_used=0, next_target=target(),
                merchants=None, incoming_res=(), outgoing_res=(), incoming_attacks=0, units_home=None, units_away=None)
    base.update(kw)
    return VillageSnapshot(**base)


def rc_for(pages=None, cfg=None, dry_flag=False, **kw):
    gw = FakeGateway(pages={"dorf1.php": HOME_HTML, **(pages or {})})
    return make_rc(gateway=gw, cfg=cfg if cfg is not None else {"main_did": 101}, dry_flag=dry_flag, **kw)


def with_age(rc, value):
    return dataclasses.replace(rc.io, last_action_age_hours=lambda sh, action, did=None, **k: value)


def rows_of(res):
    return res.actions


# ---------------------------------------------------------------- _util
class UtilTest(unittest.TestCase):
    def test_hero_here(self):
        rc, _ = rc_for()
        vc = make_vc()
        self.assertTrue(U.hero_here(rc, vc))                                   # 讀不到英雄、main_did 相符
        rc.hero = HeroState(100, True, 90, 0, 0, False, 999, None, None, None, None, False, False)
        self.assertFalse(U.hero_here(rc, vc))                                  # 英雄的家在別村
        rc.hero = dataclasses.replace(rc.hero, in_village_did=101)
        self.assertTrue(U.hero_here(rc, vc))                                   # in_village_did 優先
        rc2, _ = rc_for(cfg={"main_did": 202})
        self.assertFalse(U.hero_here(rc2, vc))                                 # 讀不到英雄、main_did 不同
        rc3, _ = rc_for(cfg={})
        self.assertTrue(U.hero_here(rc3, vc))                                  # 都不知道＝當作在這裡

    def test_notes_are_per_village(self):
        rc, _ = rc_for()
        U.set_note(rc, 101, "built")
        self.assertTrue(U.has_note(rc, 101, "built"))
        self.assertFalse(U.has_note(rc, 102, "built"))
        self.assertFalse(U.has_note(rc, 101, "focus_acted"))

    def test_make_row_is_valid_c5(self):
        rc, _ = rc_for()
        row = U.make_row(rc, 101, U.ACTION_FOCUS, Mode.LIVE, "ok", "x" * 500, target())
        self.assertEqual(row.validate(), [])
        self.assertEqual((row.aid, row.gid, row.level, row.cost), (5, 1, 2, "1000,1000,1000,1000"))
        self.assertLessEqual(len(row.detail), 300)

    def test_run_with_facts_fetches_then_returns(self):
        rc, _ = rc_for()
        calls = []

        def step(facts):
            calls.append(dict(facts.options))
            from travian_bot.common.decisions import FactsNeed
            return "done", (None if 25 in facts.options else FactsNeed("build_options", 25))
        with mock.patch.object(U, "parse_build_options", return_value=()), \
                mock.patch.object(rc.gateway, "pages", {**rc.gateway.pages, "build.php?id=25": "<html/>"}):
            value, facts = U.run_with_facts(rc, step)
        self.assertEqual(value, "done")
        self.assertEqual(len(calls), 2)
        self.assertEqual(facts.options[25], ())

    def test_run_with_facts_gives_up(self):
        rc, _ = rc_for(pages={"dorf2.php": "<html/>"})
        from travian_bot.common.decisions import FactsNeed
        with mock.patch.object(U, "parse_dorf2", return_value=SimpleNamespace(slots=())):
            with self.assertRaises(RuntimeError):
                U.run_with_facts(rc, lambda f: (None, FactsNeed("dorf2")))


# ---------------------------------------------------------------- focus（ap-12）
class FocusStageTest(unittest.TestCase):
    def setUp(self):
        self.vc = make_vc(modes={"focus": "live"})

    def test_precondition(self):
        rc, _ = rc_for()
        self.assertTrue(FO.precondition(rc, self.vc, snap()))
        self.assertFalse(FO.precondition(rc, self.vc, None))
        self.assertFalse(FO.precondition(rc, self.vc, snap(next_target=None)))
        self.assertFalse(FO.precondition(rc, self.vc, snap(next_target=target(ready=0))))     # 付得起
        self.assertFalse(FO.precondition(rc, self.vc, snap(queue_slots_used=1)))              # 佇列滿
        U.set_note(rc, 101, "built")
        self.assertFalse(FO.precondition(rc, self.vc, snap()))                                # 本輪已有建城動作

    def _run(self, decision, exec_result=None, age=None, read_exc=None, rc=None):
        self.rec = None
        if rc is None:
            rc, self.rec = rc_for()
        rc.io = with_age(rc, age)
        read = mock.Mock(side_effect=read_exc) if read_exc else mock.Mock(return_value=HeroFocus(0, TYPES))
        with mock.patch.object(FO, "read_focus", read), \
                mock.patch.object(FO, "decide_focus", return_value=decision) as dec, \
                mock.patch.object(FO, "set_focus", return_value=exec_result) as setf, \
                mock.patch.object(FO, "parse_dorf1", return_value=SimpleNamespace(prod=(100, 100, 100, 1220))):
            res = FO.run(rc, self.vc, snap(), Mode.LIVE)
        return rc, res, dec, setf

    def test_keep_writes_skipped_row_and_does_not_mark(self):
        rc, res, _dec, setf = self._run(FocusDecision(False, None, "沒有更快的選項"))
        self.assertEqual((res.status, [r.result for r in rows_of(res)]), ("ok", ["skipped"]))
        self.assertIn("沒有更快的選項", rows_of(res)[0].detail)
        setf.assert_not_called()
        self.assertFalse(U.has_note(rc, 101, "focus_acted"))

    def test_settings_and_age_are_passed_to_domain(self):
        rc, _ = rc_for(cfg={"main_did": 101, "hero_focus_min_hours": 2.5})
        _rc, _res, dec, _ = self._run(FocusDecision(False, None, "x"), age=0.7, rc=rc)
        args = dec.call_args[0]
        self.assertEqual(args[2].min_hours, 2.5)
        self.assertFalse(args[2].back_to_balanced)          # 舊 runner 傳 back_to_balanced=False
        self.assertEqual(args[3], 0.7)

    def test_switch_ok_updates_prod_marks_and_notifies(self):
        rc, res, _dec, setf = self._run(FocusDecision(True, "crop", "改穀"),
                                        ExecResult("ok", "已改成 crop 並驗證", 3, True))
        self.assertEqual((res.status, [r.result for r in rows_of(res)]), ("ok", ["ok"]))
        self.assertEqual(res.snapshot_updates, {"prod": (100, 100, 100, 1220)})
        self.assertTrue(U.has_note(rc, 101, "focus_acted"))
        self.assertTrue(any("crop" in n for n in self.rec.notes))

    def test_switch_failed_is_failed_and_still_marks(self):
        rc, res, *_ = self._run(FocusDecision(True, "crop", "改穀"), ExecResult("failed", "HTTP 500", 1, False))
        self.assertEqual(res.status, "failed")
        self.assertTrue(res.note)
        self.assertTrue(U.has_note(rc, 101, "focus_acted"))

    def test_dry_switch_marks_too(self):
        rc, res, *_ = self._run(FocusDecision(True, "wood", "改木"), ExecResult("dry", "會改成 wood", 0, None))
        self.assertEqual([r.result for r in rows_of(res)], ["dry"])
        self.assertEqual(res.snapshot_updates, {})
        self.assertTrue(U.has_note(rc, 101, "focus_acted"))

    def test_read_failure_is_failed_and_marks(self):
        rc, res, _dec, setf = self._run(None, read_exc=GatewayError("boom"))
        self.assertEqual(res.status, "failed")
        self.assertEqual([r.result for r in rows_of(res)], ["failed"])
        self.assertTrue(U.has_note(rc, 101, "focus_acted"))
        setf.assert_not_called()

    def test_stage_registration_fields(self):
        self.assertEqual((FO.STAGE.name, FO.STAGE.scope, FO.STAGE.mode_key, FO.STAGE.order),
                         ("focus", "village", "focus", 40))


# ---------------------------------------------------------------- item_transfer（ap-11）
def tstate(stock=(0, 0, 0, 0), inv=30000):
    return TransferState(village_id=101, stock=stock, capacity=(4000, 4000, 4000, 4000),
                         inventory=tuple(TransferItem(10 + i, inv) for i in range(4)))


class ItemTransferStageTest(unittest.TestCase):
    def setUp(self):
        self.vc = make_vc(modes={"item_transfer": "live"})
        self.snap = snap(next_target=target(cost=(500, 200, 0, 0)), incoming_attacks=1)

    def _run(self, state=None, exec_result=None, eta=600, attacks=1, read_exc=None, mode=Mode.LIVE):
        rc, _ = rc_for()
        s = dataclasses.replace(self.snap, incoming_attacks=attacks)
        read = mock.Mock(side_effect=read_exc) if read_exc else mock.Mock(return_value=state or tstate())
        with mock.patch.object(IT, "read_transfer_state", read), \
                mock.patch.object(IT, "execute_item_transfer", return_value=exec_result) as ex, \
                mock.patch.object(IT, "parse_dorf1", return_value=SimpleNamespace(attack_eta_s=eta)):
            res = IT.run(rc, self.vc, s, mode)
        return rc, res, read, ex

    def test_precondition(self):
        rc, _ = rc_for()
        self.assertTrue(IT.precondition(rc, self.vc, self.snap))
        self.assertFalse(IT.precondition(rc, self.vc, snap(next_target=target(ready=0))))
        self.assertFalse(IT.precondition(rc, self.vc, snap(queue_slots_used=1)))

    def test_no_incoming_skips_without_reading_state_or_writing_row(self):
        rc, res, read, ex = self._run(attacks=0)
        self.assertEqual((res.status, res.actions), ("skipped", []))
        read.assert_not_called()
        ex.assert_not_called()

    def test_eta_too_far_skips(self):
        _rc, res, read, _ex = self._run(eta=3 * 3600)
        self.assertEqual(res.status, "skipped")
        read.assert_not_called()

    def test_transfer_ok_updates_snapshot_and_drops_cached_dorf1(self):
        rc, res, _read, ex = self._run(exec_result=ExecResult("ok", "已轉移並驗證", 6, True))
        self.assertEqual((res.status, [r.result for r in rows_of(res)]), ("ok", ["ok"]))
        self.assertEqual(res.snapshot_updates["stock"], (1000, 700, 500, 500))     # snap.stock (500×4) ＋ 轉入 (500, 200, 0, 0)
        self.assertEqual(res.snapshot_updates["next_target"].ready_in_s, 0)
        self.assertNotIn("dorf1.php", rc.pages)
        dec = ex.call_args[0][1]
        self.assertTrue(dec.act)
        self.assertEqual({ln.resource: ln.amount for ln in dec.lines}, {0: 500, 1: 200})

    def test_gap_too_big_writes_skipped_row_and_does_not_execute(self):
        rc, _ = rc_for()                      # 缺口 6000 > 1000
        big = dataclasses.replace(self.snap, next_target=target(cost=(3000, 3000, 0, 0)))
        with mock.patch.object(IT, "read_transfer_state", return_value=tstate()), \
                mock.patch.object(IT, "execute_item_transfer") as ex2, \
                mock.patch.object(IT, "parse_dorf1", return_value=SimpleNamespace(attack_eta_s=600)):
            res = IT.run(rc, self.vc, big, Mode.LIVE)
        self.assertEqual([r.result for r in rows_of(res)], ["skipped"])
        self.assertIn("gap_too_big", rows_of(res)[0].detail)
        ex2.assert_not_called()

    def test_read_failure_is_failed_not_raised(self):
        _rc, res, _read, ex = self._run(read_exc=GatewayError("graphql"))
        self.assertEqual(res.status, "failed")
        ex.assert_not_called()

    def test_failed_transfer_is_failed(self):
        _rc, res, *_ = self._run(exec_result=ExecResult("failed", "轉移後村莊仍不足", 6, False))
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.snapshot_updates, {})


# ---------------------------------------------------------------- fill_in（ap-13）
class FillInStageTest(unittest.TestCase):
    def setUp(self):
        self.main = target(cost=(3000, 3000, 3000, 3000), ready=7200, aid=6, to_level=4)
        self.f = target(cost=(100, 100, 100, 100), ready=0, aid=7, to_level=2)
        self.vc = make_vc(modes={"fill_in": "live"})
        self.vc = dataclasses.replace(self.vc, build_settings=dataclasses.replace(self.vc.build_settings, build_order="res:5"))
        self.snap = snap(next_target=self.main)

    def _run(self, *, verdict="proceed", pick=None, exec_result=None, mode=Mode.LIVE, vc=None,
             main_kind="wait_resources"):
        rc, _ = rc_for()
        main_dec = BuildDecision(main_kind, self.main, "")
        pick = pick or FillInDecision(False, None, "都會拖慢主目標")
        d1 = SimpleNamespace(queue=(), attack_eta_s=None)
        with mock.patch.object(FI, "parse_dorf1", return_value=d1), \
                mock.patch.object(FI, "validation_need", return_value=None), \
                mock.patch.object(FI, "validate_order", return_value=SimpleNamespace(verdict=verdict)), \
                mock.patch.object(FI, "fill_in_candidates", return_value=(main_dec, [FillCandidate(self.f, 600)])), \
                mock.patch.object(FI, "pick_fill_in", return_value=pick), \
                mock.patch.object(FI, "submit_upgrade", return_value=exec_result) as sub:
            res = FI.run(rc, vc or self.vc, self.snap, mode)
        return rc, res, sub

    def test_precondition(self):
        rc, _ = rc_for()
        self.assertTrue(FI.precondition(rc, self.vc, self.snap))
        self.assertFalse(FI.precondition(rc, make_vc(), self.snap))                     # 沒有 build_order
        self.assertFalse(FI.precondition(rc, self.vc, snap(next_target=target(ready=0))))
        self.assertFalse(FI.precondition(rc, self.vc, snap(queue_slots_used=1, next_target=self.main)))

    def test_hold_does_not_fill(self):
        _rc, res, sub = self._run(verdict="hold")
        self.assertEqual((res.status, res.actions), ("skipped", []))
        sub.assert_not_called()

    def test_main_not_waiting_resources_skips(self):
        _rc, res, sub = self._run(main_kind="wait_queue")
        self.assertEqual(res.status, "skipped")
        sub.assert_not_called()

    def test_live_no_fill_writes_nothing(self):
        _rc, res, sub = self._run(mode=Mode.LIVE)
        self.assertEqual((res.status, res.actions), ("ok", []))
        sub.assert_not_called()

    def test_dry_no_fill_writes_a_row_each_round(self):
        _rc, res, _sub = self._run(mode=Mode.DRY)
        self.assertEqual([r.result for r in rows_of(res)], ["skipped"])

    def test_fill_ok_updates_snapshot_marks_built_and_drops_dorf1(self):
        rc, res, sub = self._run(pick=FillInDecision(True, self.f, "主目標不變慢"),
                                 exec_result=ExecResult("ok", "已送出並驗證", 5, True))
        self.assertEqual((res.status, [r.result for r in rows_of(res)]), ("ok", ["ok"]))
        self.assertEqual(res.snapshot_updates, {"stock": (400, 400, 400, 400), "queue_slots_used": 1})
        self.assertTrue(U.has_note(rc, 101, "built"))
        self.assertNotIn("dorf1.php", rc.pages)
        self.assertEqual(sub.call_args[0][2], self.f)
        self.assertEqual((rows_of(res)[0].aid, rows_of(res)[0].action), (7, U.ACTION_FILL_IN))

    def test_fill_failed_is_failed(self):
        rc, res, _ = self._run(pick=FillInDecision(True, self.f, "x"), exec_result=ExecResult("failed", "沒扣資源", 5, False))
        self.assertEqual(res.status, "failed")
        self.assertFalse(U.has_note(rc, 101, "built"))

    def test_config_dry_fill_does_not_mark_built(self):
        vc = dataclasses.replace(self.vc, modes={"fill_in": "dry"})
        rc, _res, _ = self._run(pick=FillInDecision(True, self.f, "x"), exec_result=ExecResult("dry", "會送出", 3, None),
                                mode=Mode.DRY, vc=vc)
        self.assertFalse(U.has_note(rc, 101, "built"))          # 舊 fill_mode＝dry：action 不變

    def test_env_dry_with_live_config_marks_built(self):
        rc, _res, _ = self._run(pick=FillInDecision(True, self.f, "x"), exec_result=ExecResult("dry", "會送出", 3, None),
                                mode=Mode.DRY)                    # DRY_RUN 把 live 降成 dry，但設定是 live
        self.assertTrue(U.has_note(rc, 101, "built"))


# ---------------------------------------------------------------- guard（ap-14）
class GuardStageTest(unittest.TestCase):
    def setUp(self):
        self.vc = make_vc(modes={"guard": "live", "focus": "live"})

    def test_precondition_wait_res_or_wait_queue(self):
        rc, _ = rc_for()
        self.assertTrue(GU.precondition(rc, self.vc, snap()))                                    # wait_res
        self.assertTrue(GU.precondition(rc, self.vc, snap(queue_slots_used=1)))                  # wait_queue
        self.assertFalse(GU.precondition(rc, self.vc, snap(next_target=target(ready=0))))        # 付得起、佇列空
        self.assertFalse(GU.precondition(rc, self.vc, snap(next_target=None)))

    def test_precondition_skips_after_focus_or_build(self):
        rc, _ = rc_for()
        U.set_note(rc, 101, "focus_acted")
        self.assertFalse(GU.precondition(rc, self.vc, snap()))
        rc2, _ = rc_for()
        U.set_note(rc2, 101, "built")
        self.assertFalse(GU.precondition(rc2, self.vc, snap()))

    def test_precondition_live_guard_needs_focus_on_but_dry_does_not(self):
        rc, _ = rc_for()
        self.assertFalse(GU.precondition(rc, make_vc(modes={"guard": "live", "focus": "off"}), snap()))
        self.assertTrue(GU.precondition(rc, make_vc(modes={"guard": "dry", "focus": "off"}), snap()))

    def _run(self, decision, exec_result=None, mode=Mode.LIVE, s=None, cfg=None, read_exc=None, next_gaps=None):
        rc, _ = rc_for(cfg=cfg)
        read = mock.Mock(side_effect=read_exc) if read_exc else mock.Mock(return_value=HeroFocus(0, TYPES))
        with mock.patch.object(GU, "read_focus", read), \
                mock.patch.object(GU, "decide_guard", return_value=decision) as dec, \
                mock.patch.object(GU, "set_focus", return_value=exec_result) as setf, \
                mock.patch.object(GU, "_next_gaps", return_value=next_gaps) as ng:
            res = GU.run(rc, self.vc, s or snap(), mode)
        return rc, res, dec, setf, ng

    def test_no_act_live_writes_nothing_dry_writes_row(self):
        _rc, res, *_ = self._run(GuardDecision(False, "不會溢出"), mode=Mode.LIVE)
        self.assertEqual((res.status, res.actions), ("ok", []))
        _rc, res, *_ = self._run(GuardDecision(False, "不會溢出"), mode=Mode.DRY)
        self.assertEqual([r.result for r in rows_of(res)], ["skipped"])

    def test_dry_uses_always_exposure_live_uses_config(self):
        _rc, _res, dec, *_ = self._run(GuardDecision(False, "x"), mode=Mode.DRY, cfg={"main_did": 101, "guard_exposure": "incoming"})
        self.assertEqual(dec.call_args.kwargs["exposure_mode"], "always")
        _rc, _res, dec, *_ = self._run(GuardDecision(False, "x"), mode=Mode.LIVE, cfg={"main_did": 101, "guard_exposure": "incoming"})
        self.assertEqual(dec.call_args.kwargs["exposure_mode"], "incoming")

    def test_wait_res_passes_gap_of_next_target(self):
        _rc, _res, dec, *_ = self._run(GuardDecision(False, "x"))
        self.assertEqual(dec.call_args.kwargs["gaps"], {1: 500, 2: 500, 3: 500, 4: 500})

    def test_switch_calls_set_focus_with_name_and_updates_prod(self):
        _rc, res, _dec, setf, _ng = self._run(GuardDecision(True, "改穀", "incoming", 4),
                                              ExecResult("ok", "已改成 crop 並驗證", 3, True))
        sent = setf.call_args[0][1]
        self.assertEqual((sent.act, sent.focus), (True, "crop"))
        self.assertEqual(res.snapshot_updates, {"prod": (100 - 336, 100 - 336, 100 - 336, 100 - 336 + 1120)})
        self.assertEqual((res.status, rows_of(res)[0].action), ("ok", U.ACTION_GUARD))

    def test_queue_busy_switch_looks_up_next_target_gaps_and_decides_again(self):
        first, second = GuardDecision(True, "先想切", "incoming", 1), GuardDecision(False, "補不齊，不切")
        rc, _ = rc_for()
        with mock.patch.object(GU, "read_focus", return_value=HeroFocus(0, TYPES)), \
                mock.patch.object(GU, "decide_guard", side_effect=[first, second]) as dec, \
                mock.patch.object(GU, "set_focus") as setf, \
                mock.patch.object(GU, "_next_gaps", return_value=({1: 300}, 0.5, "｜下一目標…")) as ng:
            res = GU.run(rc, self.vc, snap(queue_slots_used=1, queue_free_in_s=1800), Mode.LIVE)
        ng.assert_called_once()
        self.assertEqual(dec.call_count, 2)
        self.assertEqual(dec.call_args_list[1].kwargs["gaps"], {1: 300})
        self.assertEqual(dec.call_args_list[1].kwargs["ready_in_h"], 0.5)
        setf.assert_not_called()
        self.assertEqual(res.actions, [])

    def test_queue_busy_next_target_unavailable_falls_back_to_no_gaps(self):
        _rc, res, dec, setf, _ng = self._run(GuardDecision(True, "切", "incoming", 1), ExecResult("dry", "會改", 0, None),
                                             mode=Mode.DRY, s=snap(queue_slots_used=1), next_gaps=None)
        self.assertEqual(dec.call_count, 1)                        # 查不到下一目標：不重新決策
        self.assertIn("算不出來", rows_of(res)[0].detail)
        setf.assert_called_once()

    def test_failed_switch_is_failed(self):
        _rc, res, *_ = self._run(GuardDecision(True, "切", "incoming", 1), ExecResult("failed", "HTTP 500", 1, False))
        self.assertEqual(res.status, "failed")

    def test_read_failure(self):
        _rc, res, _d, setf, _ng = self._run(None, read_exc=GatewayError("x"))
        self.assertEqual(res.status, "failed")
        setf.assert_not_called()


# ---------------------------------------------------------------- hero（ap-17）
def hero_state(**kw):
    base = dict(status=100, at_home=True, health_pct=90, exp_pct=0, adventures_count=3, regenerating=False,
                home_did=101, in_village_did=None, adventure_no=None, arrival_in_s=None, arrival_at=None,
                difficulty_bonus=False, duration_bonus=False)
    base.update(kw)
    return HeroState(**base)


ADV = Adventure(number=7, distance=10.0, place="grassland", difficulty=1, hard=False, duration_s=600, x=None, y=None,
                icon="normal", clickable=True)


class HeroStageTest(unittest.TestCase):
    def _run(self, hero=None, advs=(ADV,), exec_result=None, cfg=None, incoming=0, read_exc=None, mode=Mode.LIVE,
             html=HOME_HTML):
        rc, _ = rc_for(pages={"dorf1.php": html, "hero/adventures": "<html/>"}, cfg=cfg)
        read = mock.Mock(side_effect=read_exc) if read_exc else mock.Mock(return_value=hero or hero_state())
        with mock.patch.object(HE, "read_hero", read), \
                mock.patch.object(HE, "parse_adventures", return_value=advs), \
                mock.patch.object(HE, "parse_dorf1", return_value=SimpleNamespace(incoming_attacks=incoming)), \
                mock.patch.object(HE, "click_adventure", return_value=exec_result) as click:
            res = HE.run(rc, None, None, mode)
        return rc, res, click

    def test_stage_is_account_level(self):
        self.assertEqual((HE.STAGE.scope, HE.STAGE.mode_key), ("account", "hero"))

    def test_no_main_did_is_skipped(self):
        _rc, res, click = self._run(cfg={})
        self.assertEqual((res.status, res.actions), ("skipped", []))
        click.assert_not_called()

    def test_not_a_village_page_is_skipped(self):
        _rc, res, click = self._run(html="<html>login</html>")
        self.assertEqual(res.status, "skipped")
        click.assert_not_called()

    def test_going_or_returning_is_quiet(self):
        for status in (50, 9):
            rc, res, click = self._run(hero=hero_state(status=status, at_home=False, adventure_no=7, arrival_in_s=300))
            self.assertEqual((res.status, res.actions), ("ok", []), status)
            click.assert_not_called()
            self.assertEqual(rc.hero.status, status)                 # rc.hero 有更新

    def test_not_home_other_status_writes_skipped_row_without_fetching_adventures(self):
        rc, res, _click = self._run(hero=hero_state(status=None, at_home=False))
        self.assertEqual([r.result for r in rows_of(res)], ["skipped"])
        self.assertNotIn("hero/adventures", rc.pages)

    def test_low_health_writes_skipped_row(self):
        _rc, res, click = self._run(hero=hero_state(health_pct=30))
        self.assertEqual([r.result for r in rows_of(res)], ["skipped"])
        self.assertIn("體力", rows_of(res)[0].detail)
        click.assert_not_called()

    def test_incoming_blocks_when_configured(self):
        _rc, res, click = self._run(incoming=2)
        self.assertEqual([r.result for r in rows_of(res)], ["skipped"])
        click.assert_not_called()
        _rc, res, click = self._run(incoming=2, cfg={"main_did": 101, "hero_skip_on_incoming": False},
                                    exec_result=ExecResult("ok", "已確認出發", 4, True))
        click.assert_called_once()

    def test_go_ok(self):
        rc, res, click = self._run(exec_result=ExecResult("ok", "已確認出發", 4, True))
        self.assertEqual((res.status, [r.result for r in rows_of(res)]), ("ok", ["ok"]))
        self.assertEqual(click.call_args[0][1].number, 7)
        self.assertEqual(rows_of(res)[0].action, U.ACTION_HERO)
        self.assertEqual(rows_of(res)[0].did, 101)

    def test_go_failed(self):
        _rc, res, _ = self._run(exec_result=ExecResult("failed", "沒看到出發", 4, False))
        self.assertEqual(res.status, "failed")

    def test_read_failure_is_failed_row(self):
        _rc, res, click = self._run(read_exc=GatewayError("x"))
        self.assertEqual(res.status, "failed")
        click.assert_not_called()


# ---------------------------------------------------------------- registry
class RegistryTest(unittest.TestCase):
    def test_a6a2_stages_are_registered_and_valid(self):
        REG.validate_stages(REG.STAGES)
        names = {s.name for s in REG.STAGES}
        self.assertTrue({"build", "item_transfer", "fill_in", "focus", "guard", "hero"} <= names)

    def test_order_matches_old_runner(self):
        order = [s.name for s in REG.village_stages()]
        self.assertLess(order.index("item_transfer"), order.index("fill_in"))
        self.assertLess(order.index("fill_in"), order.index("build"))
        self.assertLess(order.index("build"), order.index("focus"))
        self.assertLess(order.index("focus"), order.index("guard"))     # 使用者定案：focus 先、guard 後
        self.assertEqual([s.name for s in REG.account_stages()].count("hero"), 1)


if __name__ == "__main__":
    unittest.main()
