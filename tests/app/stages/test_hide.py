# -*- coding: utf-8 -*-
"""ap-15 hide stage（A6a2b）。domain（hide_plan／hide_decide）用真的；actions（send_troops／verify_oasis）與 parse_overview 在 stage 模組層級換成假的。"""
import dataclasses
import unittest
from unittest import mock

from travian_bot.app import stage_base as SB
from travian_bot.app.stages import _util as U
from travian_bot.app.stages import hide as HI
from travian_bot.common.decisions import ExecResult
from travian_bot.common.models import HideContext, Oasis, VillageSnapshot
from travian_bot.common.modes import Mode
from travian_bot.common.parsed import RallyMovement, RallyOverview
from travian_bot.common.schema import ParseError
from travian_bot.infra.gateway import GatewayError

from ..fakes import NOW_S, FakeGateway, make_rc, make_vc

PATH = "build.php?gid=16&tt=1"
T0 = 100000


def mv(kind, arrive, units=None, hostile=None):
    return RallyMovement(kinds=(kind,), hostile=kind in ("inRaid", "inAttack") if hostile is None else hostile,
                         own_home=False, arrive_ts=arrive, units=units or {}, role_did=1, head_did=2, link_did=1,
                         recall_id=None, section="", headline="")


def ov(arrivals=(T0 + 1800,), home=None, extra=(), ts=T0):
    moves = tuple(mv("inRaid", a, {"u1": None}) for a in arrivals) + tuple(extra)
    return RallyOverview(server_ts=ts, movements=moves, units_home={"u1": 50} if home is None else home,
                         units_away=None, incoming_attacks=len(arrivals))


def ctx(oases=((3, 0), (10, 0))):
    return HideContext(home_x=0, home_y=0, oases=tuple(Oasis(x, y, "wood25", None) for x, y in oases), blocked=(),
                       tribe="gaul")


def vc_with(oases=((3, 0), (10, 0)), modes=None, did=101):
    vc = make_vc(did=did, modes=modes if modes is not None else {"hide": "live"})
    return dataclasses.replace(vc, hide_context=ctx(oases))


def snap(incoming=1):
    return VillageSnapshot(did=101, ts_utc=NOW_S, stock=(0, 0, 0, 0), prod=(0, 0, 0, 0), cap_wh=1, cap_gr=1, hidden=None,
                           queue_free_in_s=0, queue_slots_used=0, next_target=None, merchants=None, incoming_res=(),
                           outgoing_res=(), incoming_attacks=incoming, units_home=None, units_away=None)


def rc_for(pages=None, cfg=None, dry_flag=False, fail=None):
    gw = FakeGateway(pages={PATH: "<html/>", **(pages or {})}, fail=fail)
    return make_rc(gateway=gw, cfg=cfg if cfg is not None else {"main_did": 101}, dry_flag=dry_flag)


def go(rc, vc, overview, mode=Mode.LIVE, exec_result=None, s=None):
    seq = overview if isinstance(overview, list) else [overview]
    send = mock.Mock(return_value=exec_result)
    verify = mock.Mock()
    with mock.patch.object(HI, "parse_overview", side_effect=seq), mock.patch.object(HI, "send_troops", send), \
            mock.patch.object(HI, "verify_oasis", verify):
        res = HI.run(rc, vc, s or snap(), mode)
    return res, send, verify


OK = ExecResult("ok", "已送出 (3|0)", 5, True)
DRY = ExecResult("dry", "確認頁核對通過，未送出", 3, None)


class PreconditionTest(unittest.TestCase):
    def test_precondition(self):
        rc, _ = rc_for()
        vc = vc_with()
        self.assertFalse(HI.precondition(rc, vc, None))
        self.assertFalse(HI.precondition(rc, None, snap()))
        self.assertFalse(HI.precondition(rc, vc, snap(0)))          # 確定沒有來襲
        self.assertTrue(HI.precondition(rc, vc, snap(2)))
        self.assertTrue(HI.precondition(rc, vc, snap(None)))        # 未知＝仍讀概況

    def test_stage_metadata(self):
        s = HI.STAGE
        self.assertEqual((s.name, s.scope, s.mode_key, s.order), ("hide", "village", "hide", 10))


class RunTest(unittest.TestCase):
    def test_no_hostile_is_silent(self):
        rc, _ = rc_for()
        res, send, _v = go(rc, vc_with(), ov(arrivals=()))
        self.assertEqual((res.status, res.actions), ("skipped", []))
        send.assert_not_called()

    def test_go_dry_sends_decision_and_row_is_dry(self):
        rc, _ = rc_for()
        res, send, _verify = go(rc, vc_with(), ov(), Mode.DRY, DRY)
        row = res.actions[0]
        self.assertEqual((res.status, row.action, row.mode, row.result, row.did), ("ok", "躲兵", "dry", "dry", 101))
        self.assertEqual(row.validate(), [])
        dec = send.call_args[0][2]
        self.assertTrue(dec.act)
        self.assertEqual((dec.chosen.x, dec.chosen.y, dec.units), (3, 0, (("u1", 50),)))
        self.assertIs(send.call_args[0][3], Mode.DRY)
        self.assertEqual(send.call_args[1]["map_half"], 200)
        with mock.patch.object(HI, "verify_oasis") as vo:           # verify 注入：map_half、locale 由 stage 補上
            send.call_args[1]["verify"]("gw", "cand")
        vo.assert_called_once_with("gw", "cand", map_half=200, locale="zh-TW")
        self.assertEqual(res.snapshot_updates, {})
        self.assertIn("go:ok", row.detail)
        self.assertIn("結果=確認頁核對通過", row.detail)

    def test_dry_mode_never_writes_ok_even_if_exec_says_ok(self):
        rc, _ = rc_for()
        res, _s, _v = go(rc, vc_with(), ov(), Mode.DRY, OK)                   # C5：mode=dry 時 result 不可為 ok
        self.assertEqual(res.actions[0].result, "dry")
        self.assertEqual(res.actions[0].validate(), [])

    def test_live_ok_updates_units_home_and_notifies(self):
        rc, rec = rc_for()
        res, _s, _v = go(rc, vc_with(), ov(home={"u1": 50, "hero": 1}), Mode.LIVE, OK)
        self.assertEqual((res.status, res.actions[0].result), ("ok", "ok"))
        self.assertEqual(res.snapshot_updates, {"units_home": {"hero": 1}})
        self.assertTrue(any("躲兵" in n for n in rec.notes))

    def test_live_failed_is_failed_and_notifies(self):
        rc, rec = rc_for()
        res, _s, _v = go(rc, vc_with(), ov(), Mode.LIVE, ExecResult("failed", "送出後概況沒看到出擊", 4, False))
        self.assertEqual((res.status, res.actions[0].result), ("failed", "failed"))
        self.assertIn("沒看到出擊", res.note)
        self.assertTrue(any("人工確認" in n for n in rec.notes))

    def test_exec_skipped_is_skipped_row_ok_status(self):
        rc, _ = rc_for()
        res, _s, _v = go(rc, vc_with(), ov(), Mode.LIVE, ExecResult("skipped", "候選全部未通過", 2, None))
        self.assertEqual((res.status, res.actions[0].result), ("ok", "skipped"))

    def test_weak_skips_without_sending(self):
        rc, _ = rc_for()
        res, send, _v = go(rc, vc_with(), ov(home={"u1": 1}))       # 攻擊力 40 > 20，要更弱
        self.assertTrue(send.called)                                  # 40 > 20 → 會派
        rc, _ = rc_for(cfg={"main_did": 101, "hide_min_attack": 100})
        res, send, _v = go(rc, vc_with(), ov(home={"u1": 1}))
        send.assert_not_called()
        self.assertEqual(res.actions[0].result, "skipped")
        self.assertIn("weak", res.actions[0].detail)

    def test_too_far_is_deferred(self):
        rc, _ = rc_for()
        res, send, _v = go(rc, vc_with(), ov(arrivals=(T0 + 3 * 3600,)))
        send.assert_not_called()
        self.assertEqual(res.actions[0].result, "deferred")
        self.assertIn("too_far", res.actions[0].detail)

    def test_no_oases_skips_and_says_so(self):
        rc, _ = rc_for()
        res, send, _v = go(rc, vc_with(oases=()), ov())
        send.assert_not_called()
        self.assertEqual(res.actions[0].result, "skipped")
        self.assertIn("no_oasis", res.actions[0].detail)
        self.assertIn("綠洲=0", res.actions[0].detail)

    def test_uses_context_from_oasis_stage(self):
        rc, _ = rc_for()
        vc = vc_with(oases=())
        U.set_hide_context(rc, vc.did, ctx(((5, 0),)))
        _res, send, _v = go(rc, vc, ov())
        self.assertEqual((send.call_args[0][2].chosen.x, send.call_args[0][2].chosen.y), (5, 0))

    def test_cfg_values_reach_domain(self):
        rc, _ = rc_for(cfg={"main_did": 101, "hide_min_attack": 5000})
        res, send, _v = go(rc, vc_with(), ov())
        send.assert_not_called()
        self.assertIn("門檻>5000", res.actions[0].detail)

    def test_read_failure_is_failed_row(self):
        rc, rec = rc_for(fail={PATH: GatewayError("x")})
        with mock.patch.object(HI, "send_troops") as send:
            res = HI.run(rc, vc_with(), snap(), Mode.LIVE)
        send.assert_not_called()
        self.assertEqual((res.status, res.actions[0].result), ("failed", "failed"))
        self.assertTrue(rec.notes)

    def test_parse_failure_is_failed_row(self):
        rc, _ = rc_for()
        with mock.patch.object(HI, "parse_overview", side_effect=ParseError("rally", "x")):
            res = HI.run(rc, vc_with(), snap(), Mode.LIVE)
        self.assertEqual(res.status, "failed")


class WindowTest(unittest.TestCase):
    def window_ov(self, back_in=60, next_in=1200):
        ret = mv("inReturn", T0 + back_in, {"u1": 50}, hostile=False)
        return ov(arrivals=(T0 + next_in,), home={}, extra=(ret,))

    def test_waits_for_return_then_rereads_and_sends(self):
        rc, _ = rc_for()
        slept = []
        rc.io = dataclasses.replace(rc.io, sleep=slept.append)
        second = ov(arrivals=(T0 + 1200,), home={"u1": 50}, ts=T0 + 64)
        res, send, _v = go(rc, vc_with(), [self.window_ov(), second], Mode.LIVE, OK)
        self.assertEqual(slept, [63])                                 # 60＋緩衝 3，gateway 耗時 0
        self.assertTrue(send.called)
        self.assertIn("等待=63s", res.actions[0].detail)
        self.assertIn("窗口=", res.actions[0].detail)

    def test_weak_units_also_wait_for_return(self):
        rc, _ = rc_for(cfg={"main_did": 101, "hide_min_attack": 100})        # 在家只有 1 個 u1（攻擊力 40）→ weak
        slept = []
        rc.io = dataclasses.replace(rc.io, sleep=slept.append)
        first = dataclasses.replace(self.window_ov(), units_home={"u1": 1})
        second = ov(arrivals=(T0 + 1200,), home={"u1": 51}, ts=T0 + 64)       # 歸來後 51×40＝2040 > 100
        _res, send, _v = go(rc, vc_with(), [first, second], Mode.LIVE, OK)
        self.assertEqual(slept, [63])
        self.assertTrue(send.called)

    def test_does_not_wait_for_other_skip_codes(self):
        rc, _ = rc_for()
        slept = []
        rc.io = dataclasses.replace(rc.io, sleep=slept.append)
        far = dataclasses.replace(self.window_ov(), units_home={"u1": 50})   # 有兵、可派 → 不是 no_units／weak
        go(rc, vc_with(oases=()), far)                                        # no_oasis
        self.assertEqual(slept, [])

    def test_does_not_wait_beyond_cap(self):
        rc, _ = rc_for(cfg={"main_did": 101, "hide_wait_max_s": 30})
        slept = []
        rc.io = dataclasses.replace(rc.io, sleep=slept.append)
        res, send, _v = go(rc, vc_with(), self.window_ov())
        self.assertEqual(slept, [])
        send.assert_not_called()
        self.assertIn("有歸來窗口但沒等", res.actions[0].detail)

    def test_does_not_wait_when_gap_too_short(self):
        rc, _ = rc_for()
        slept = []
        rc.io = dataclasses.replace(rc.io, sleep=slept.append)
        res, _send, _v = go(rc, vc_with(), self.window_ov(back_in=60, next_in=120))
        self.assertEqual(slept, [])
        self.assertIn("空檔不夠", res.actions[0].detail)

    def test_wait_zero_disables_waiting(self):
        rc, _ = rc_for(cfg={"main_did": 101, "hide_wait_max_s": 0})
        slept = []
        rc.io = dataclasses.replace(rc.io, sleep=slept.append)
        go(rc, vc_with(), self.window_ov())
        self.assertEqual(slept, [])

    def test_wait_time_is_reduced_by_read_elapsed(self):
        rc, _ = rc_for()
        slept = []
        rc.io = dataclasses.replace(rc.io, sleep=slept.append)

        class Slow(FakeGateway):
            def elapsed(self_inner):
                self_inner._calls = getattr(self_inner, "_calls", 0) + 1
                return 0.0 if self_inner._calls == 1 else 10.0       # 讀頁後過了 10 秒
        rc.gateway = Slow(pages={PATH: "<html/>"})
        second = ov(arrivals=(T0 + 1200,), home={"u1": 50}, ts=T0 + 64)
        go(rc, vc_with(), [self.window_ov(), second], Mode.LIVE, OK)
        self.assertEqual(slept, [53])

    def test_reread_failure_after_wait(self):
        rc, _ = rc_for()
        rc.io = dataclasses.replace(rc.io, sleep=lambda s: None)
        with mock.patch.object(HI, "parse_overview", side_effect=[self.window_ov(), ParseError("rally", "x")]):
            res = HI.run(rc, vc_with(), snap(), Mode.LIVE)
        self.assertEqual(res.status, "failed")


class ViaRunStageTest(unittest.TestCase):
    def run_stage(self, dry_flag, hide_mode="live"):
        rc, rec = rc_for(dry_flag=dry_flag)
        vc = vc_with(modes={"hide": hide_mode})
        with mock.patch.object(HI, "parse_overview", return_value=ov()), \
                mock.patch.object(HI, "send_troops", return_value=DRY) as send:
            res = SB.run_stage(HI.STAGE, rc, vc, snap())
        return res, rec, send

    def test_live_is_lowered_to_dry_by_dry_run_env(self):
        res, rec, send = self.run_stage(dry_flag=True)
        self.assertIs(send.call_args[0][3], Mode.DRY)
        self.assertEqual([r.mode for r in rec.of("log_actions")[0][1][1]], ["dry"])

    def test_off_does_nothing(self):
        res, rec, send = self.run_stage(dry_flag=False, hide_mode="off")
        self.assertEqual(res.status, "skipped")
        send.assert_not_called()
        self.assertEqual(rec.of("log_actions"), [])

    def test_no_incoming_skips_by_precondition(self):
        rc, rec = rc_for()
        with mock.patch.object(HI, "send_troops") as send:
            res = SB.run_stage(HI.STAGE, rc, vc_with(), snap(0))
        self.assertEqual(res.status, "skipped")
        self.assertEqual(rc.gateway.calls, [])                       # 沒有來襲不抓任何頁
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
