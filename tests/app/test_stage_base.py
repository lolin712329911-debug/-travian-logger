# -*- coding: utf-8 -*-
"""ap-03 stage_base（A6a1）：stage_mode、run_stage 的 5 條規則與各種例外。"""
import unittest

from travian_bot.app import stage_base as SB
from travian_bot.common.models import ActionRow, StageResult, ValidationError
from travian_bot.common.modes import Mode
from travian_bot.common.schema import ParseError
from travian_bot.infra.gateway import GatewayError
from travian_bot.infra.session import SessionLost

from .fakes import NOW_S, FakeGateway, Recorder, make_rc, make_vc


def row(result="ok", mode="live", did=101, action="測試", detail=""):
    return ActionRow(ts_utc=NOW_S, action=action, aid=None, gid=None, level=None, cost=None, mode=mode,
                     result=result, detail=detail, did=did)


def stage(run=None, pre=None, mode_key="guard", scope="village", name="t", order=1):
    calls = {"pre": 0, "run": 0}

    def _pre(rc, vc, snap):
        calls["pre"] += 1
        return True if pre is None else pre(rc, vc, snap) if callable(pre) else pre

    def _run(rc, vc, snap, mode):
        calls["run"] += 1
        return run(rc, vc, snap, mode) if run else StageResult(status="ok")

    s = SB.Stage(name=name, scope=scope, mode_key=mode_key, order=order, precondition=_pre, run=_run)
    return s, calls


class StageModeTest(unittest.TestCase):
    def test_no_mode_key_is_live_but_dry_flag_lowers_it(self):
        s, _ = stage(mode_key=None)
        self.assertIs(SB.stage_mode(s, make_vc(), False), Mode.LIVE)
        self.assertIs(SB.stage_mode(s, make_vc(), True), Mode.DRY)

    def test_village_modes_and_dry_flag(self):
        s, _ = stage()
        for raw, flag, want in (("live", False, Mode.LIVE), ("live", True, Mode.DRY), ("dry", False, Mode.DRY),
                                ("off", False, Mode.OFF), ("off", True, Mode.OFF)):
            self.assertIs(SB.stage_mode(s, make_vc(modes={"guard": raw}), flag), want, (raw, flag))

    def test_invalid_mode_is_off_and_warns_when_rc_given(self):
        s, _ = stage()
        rc, _r = make_rc()
        self.assertIs(SB.stage_mode(s, make_vc(modes={"guard": "maybe"}), False, rc=rc), Mode.OFF)
        self.assertEqual(len(rc.warnings), 1)
        self.assertNotIn("maybe", rc.warnings[0])        # 問題說明不含原值
        self.assertIs(SB.stage_mode(s, make_vc(modes={"guard": "maybe"}), False), Mode.OFF)   # 沒 rc 也不當掉

    def test_missing_mode_is_off_without_warning(self):
        s, _ = stage()
        rc, _r = make_rc()
        self.assertIs(SB.stage_mode(s, make_vc(modes={}), False, rc=rc), Mode.OFF)
        self.assertEqual(rc.warnings, [])

    def test_account_stage_reads_rc_modes(self):
        s, _ = stage(mode_key="market", scope="account")
        rc, _r = make_rc(modes={"market": "live"}, dry_flag=False)
        self.assertIs(SB.stage_mode(s, None, False, rc=rc), Mode.LIVE)
        rc2, _r2 = make_rc(modes={}, dry_flag=False)
        self.assertIs(SB.stage_mode(s, None, False, rc=rc2), Mode.OFF)


class RunStageTest(unittest.TestCase):
    def setUp(self):
        self.vc = make_vc(modes={"guard": "live"})

    def test_off_does_not_run_and_writes_nothing(self):
        s, calls = stage()
        rc, rec = make_rc(dry_flag=False)
        res = SB.run_stage(s, rc, make_vc(modes={"guard": "off"}), None)
        self.assertEqual(res.status, "skipped")
        self.assertEqual(calls, {"pre": 0, "run": 0})
        self.assertEqual(rec.of("log_actions"), [])

    def test_false_precondition_is_skipped_and_writes_nothing(self):
        s, calls = stage(pre=False)
        rc, rec = make_rc(dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(res.status, "skipped")
        self.assertEqual((calls["pre"], calls["run"]), (1, 0))
        self.assertEqual(rec.of("log_actions"), [])

    def test_ok_result_passes_through_and_actions_are_written_once(self):
        rows = [row(), row(result="skipped", detail="第二列")]
        s, _ = stage(run=lambda rc, vc, snap, mode: StageResult(status="ok", actions=list(rows),
                                                                snapshot_updates={"queue_slots_used": 1}))
        rc, rec = make_rc(dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.snapshot_updates, {"queue_slots_used": 1})
        calls = rec.of("log_actions")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1][1], rows)

    def test_stage_receives_effective_mode(self):
        seen = []
        s, _ = stage(run=lambda rc, vc, snap, mode: (seen.append(mode), StageResult(status="ok"))[1])
        rc, _rec = make_rc(dry_flag=True)
        SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(seen, [Mode.DRY])

    def test_requests_and_elapsed_are_gateway_deltas(self):
        gw = FakeGateway()
        gw.tick(requests=7, seconds=10.0)           # 之前已用的
        s, _ = stage(run=lambda rc, vc, snap, mode: (gw.tick(requests=3, seconds=2.5), StageResult(status="ok"))[1])
        rc, _rec = make_rc(gateway=gw, dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(res.requests_used, 3)
        self.assertAlmostEqual(res.elapsed_s, 2.5)

    def test_exceptions_become_failed_with_one_failed_row(self):
        excs = [ParseError("dorf1", "讀不到"), GatewayError("請求失敗 /dorf1.php"), SessionLost("登入失效"),
                ValidationError("StageResult", "status", "x", "enum"), RuntimeError("boom")]
        for exc in excs:
            def run(rc, vc, snap, mode, exc=exc):
                raise exc
            s, _ = stage(run=run)
            rc, rec = make_rc(dry_flag=False)
            res = SB.run_stage(s, rc, self.vc, None)
            self.assertEqual(res.status, "failed", type(exc).__name__)
            self.assertTrue(res.note)
            self.assertLessEqual(len(res.note), 200)
            self.assertIn(type(exc).__name__, res.note)
            logged = rec.of("log_actions")
            self.assertEqual(len(logged), 1)
            (r,) = logged[0][1][1]
            self.assertEqual((r.result, r.did, r.mode, r.action), ("failed", 101, "live", "t"))
            self.assertIn(type(exc).__name__, r.detail)
            self.assertLessEqual(len(r.detail), 300)
            self.assertEqual(r.validate(), [])

    def test_exception_text_is_redacted_and_truncated(self):
        def run(rc, vc, snap, mode):
            raise RuntimeError("Cookie: sessionid=TOPSECRET " + "x" * 500)
        s, _ = stage(run=run)
        rc, rec = make_rc(dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertNotIn("TOPSECRET", res.note)
        self.assertNotIn("TOPSECRET", rec.of("log_actions")[0][1][1][0].detail)
        self.assertLessEqual(len(res.note), 200)

    def test_precondition_exception_is_also_failed(self):
        def boom(rc, vc, snap):
            raise ParseError("x", "y")
        s, calls = stage(pre=boom)
        rc, _rec = make_rc(dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(res.status, "failed")
        self.assertEqual(calls["run"], 0)

    def test_log_actions_failure_only_warns(self):
        s, _ = stage(run=lambda rc, vc, snap, mode: StageResult(status="ok", actions=[row()]))
        rc, rec = make_rc(recorder=Recorder(fail={"log_actions": RuntimeError("sheet down")}), dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(res.status, "ok")
        self.assertEqual(len(rc.warnings), 1)
        self.assertIn("RuntimeError", rc.warnings[0])

    def test_log_actions_failure_on_failed_stage_keeps_failed(self):
        def run(rc, vc, snap, mode):
            raise RuntimeError("x")
        s, _ = stage(run=run)
        rc, _rec = make_rc(recorder=Recorder(fail={"log_actions": RuntimeError("sheet down")}), dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(res.status, "failed")
        self.assertTrue(rc.warnings)

    def test_stage_failed_without_failed_row_gets_one(self):
        s, _ = stage(run=lambda rc, vc, snap, mode: StageResult(status="failed", note="按鈕不見了"))
        rc, rec = make_rc(dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(res.status, "failed")
        (r,) = rec.of("log_actions")[0][1][1]
        self.assertEqual(r.result, "failed")
        self.assertIn("按鈕不見了", r.detail)

    def test_stage_failed_with_empty_note_gets_default_note(self):
        s, _ = stage(run=lambda rc, vc, snap, mode: StageResult(status="failed"))
        rc, _rec = make_rc(dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(res.status, "failed")
        self.assertTrue(res.note)

    def test_non_stage_result_return_is_failed(self):
        s, _ = stage(run=lambda rc, vc, snap, mode: {"status": "ok"})
        rc, _rec = make_rc(dry_flag=False)
        self.assertEqual(SB.run_stage(s, rc, self.vc, None).status, "failed")

    def test_invalid_stage_result_is_failed(self):
        bad = row(result="ok", mode="dry")           # C5：mode=dry 時 result 不可為 ok
        s, _ = stage(run=lambda rc, vc, snap, mode: StageResult(status="ok", actions=[bad]))
        rc, rec = make_rc(dry_flag=False)
        res = SB.run_stage(s, rc, self.vc, None)
        self.assertEqual(res.status, "failed")
        self.assertIn("ValidationError", res.note)
        (r,) = rec.of("log_actions")[0][1][1]
        self.assertEqual(r.result, "failed")

    def test_account_stage_uses_main_did(self):
        def run(rc, vc, snap, mode):
            raise RuntimeError("x")
        s, _ = stage(run=run, mode_key="market", scope="account")
        rc, rec = make_rc(cfg={"main_did": 202}, modes={"market": "live"}, dry_flag=False)
        res = SB.run_stage(s, rc, None, None)
        self.assertEqual(res.status, "failed")
        self.assertEqual(rec.of("log_actions")[0][1][1][0].did, 202)

    def test_account_stage_without_main_did_cannot_log_only_warns(self):
        def run(rc, vc, snap, mode):
            raise RuntimeError("x")
        s, _ = stage(run=run, mode_key="market", scope="account")
        rc, rec = make_rc(cfg={}, modes={"market": "live"}, dry_flag=False)
        res = SB.run_stage(s, rc, None, None)
        self.assertEqual(res.status, "failed")
        self.assertEqual(rec.of("log_actions"), [])
        self.assertTrue(rc.warnings)

    def test_never_raises_even_if_stage_and_log_both_fail(self):
        def run(rc, vc, snap, mode):
            raise KeyError("x")
        s, _ = stage(run=run)
        rc, _rec = make_rc(recorder=Recorder(fail={"log_actions": RuntimeError("x")}), dry_flag=False)
        self.assertEqual(SB.run_stage(s, rc, self.vc, None).status, "failed")


if __name__ == "__main__":
    unittest.main()
