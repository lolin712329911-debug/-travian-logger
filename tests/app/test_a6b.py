# -*- coding: utf-8 -*-
"""A6b：village_cycle／orchestrator 的單元測試（全用假物件，無網路）。"""
import unittest
from dataclasses import dataclass
from types import SimpleNamespace as NS
from unittest import mock

from travian_bot.app import orchestrator, village_cycle as vcy
from travian_bot.common.modes import Mode


@dataclass
class _Snap:
    did: int
    stock: tuple = (0, 0, 0, 0)
    ok: bool = True

    def ensure_valid(self):
        if not self.ok:
            raise ValueError("bad")


def _rc(cfg=None):
    from datetime import datetime, timezone
    rows = []
    io = NS(now=lambda: datetime(2026, 11, 21, tzinfo=timezone.utc), log_actions=lambda sh, r: rows.append(list(r)))
    return NS(cfg=cfg if cfg is not None else {}, io=io, sh=object(), dry_flag=True, gateway=object(),
              profile=NS(map_half=200), warnings=[], warn=lambda m: None, rows=rows)


def _vc():
    return NS(did=7, enabled=True, priority=100, build_settings=NS(queue_slots=1))


class OrderVillages(unittest.TestCase):
    def test_priority_then_did_and_enabled_only(self):
        vs = [NS(did=3, priority=50, enabled=True), NS(did=2, priority=50, enabled=True),
              NS(did=1, priority=10, enabled=False), NS(did=9, priority=5, enabled=True)]
        self.assertEqual([v.did for v in orchestrator.order_villages(vs)], [9, 2, 3])


class ApplyUpdates(unittest.TestCase):
    def test_apply_and_reject(self):
        s = _Snap(did=1)
        self.assertEqual(vcy.apply_updates(s, {"stock": (1, 2, 3, 4)}).stock, (1, 2, 3, 4))
        self.assertIs(vcy.apply_updates(s, {}), s)
        with self.assertRaises(ValueError):
            vcy.apply_updates(s, {"nope": 1})
        with self.assertRaises(ValueError):
            vcy.apply_updates(s, {"did": 2})
        with self.assertRaises(ValueError):
            vcy.apply_updates(s, {"ok": False})


class Cycle(unittest.TestCase):
    def test_entry_assert_fail_skips_whole_village(self):
        rc = _rc()
        with mock.patch.object(vcy, "village_switch") as sw, mock.patch.object(vcy, "observe") as ob:
            sw.assert_active.return_value = False
            run = vcy.run_village_cycle(rc, _vc())
        self.assertIsNotNone(run.skipped_reason)
        self.assertEqual(run.results[0].status, "skipped")
        ob.observe_village.assert_not_called()
        self.assertEqual(len(rc.rows), 1)          # 只寫一列「村莊跳過」，沒有 disable

    def test_lock_skip(self):
        rc = _rc({"main_did": 1})
        with mock.patch.object(vcy, "village_switch") as sw, mock.patch.object(vcy, "village_lock") as lk, \
                mock.patch.object(vcy, "observe") as ob, mock.patch.object(vcy, "_lock_from_cfg"):
            sw.assert_active.return_value = True
            lk.decide_lock.return_value = NS(kind="skip", reason="main_did 不符", record=False)
            run = vcy.run_village_cycle(rc, _vc())
        self.assertEqual(run.skipped_reason, "main_did 不符")
        ob.observe_village.assert_not_called()

    def test_lock_record_calls_writer_before_observe(self):
        rc, calls = _rc(), []
        with mock.patch.object(vcy, "village_switch") as sw, mock.patch.object(vcy, "village_lock") as lk, \
                mock.patch.object(vcy, "observe") as ob, mock.patch.object(vcy, "registry") as rg, \
                mock.patch.object(vcy, "_lock_from_cfg", return_value=NS(main_did=None)):
            sw.assert_active.return_value = True
            lk.decide_lock.return_value = NS(kind="ok", reason="", record=True)
            lk.record_main.return_value = "LOCK"
            ob.observe_village.side_effect = lambda rc_, vc_: calls.append("observe") or _Snap(did=7)
            ob.observe_player.return_value = None
            ob.cp_summary.return_value = None
            rg.village_stages.return_value = []
            vcy.run_village_cycle(rc, _vc(), record_lock=lambda r, l: calls.append(("lock", l)))
        self.assertEqual(calls, [("lock", "LOCK"), "observe"])

    def test_write_stage_rechecked_and_rest_skipped_when_village_changes(self):
        rc = _rc()
        st = [NS(name="a", mode_key=None), NS(name="b", mode_key=None), NS(name="c", mode_key="hide")]
        ran = []
        with mock.patch.object(vcy, "village_switch") as sw, mock.patch.object(vcy, "village_lock") as lk, \
                mock.patch.object(vcy, "observe") as ob, mock.patch.object(vcy, "registry") as rg, \
                mock.patch.object(vcy, "stage_mode", return_value=Mode.LIVE), \
                mock.patch.object(vcy, "_lock_from_cfg", return_value=NS(main_did=7)), \
                mock.patch.object(vcy, "run_stage",
                                  side_effect=lambda s, *a: ran.append(s.name) or NS(status="ok", snapshot_updates={})):
            sw.assert_active.side_effect = [True, True, False]      # 進村、a 前、b 前
            lk.decide_lock.return_value = NS(kind="ok", reason="", record=False)
            ob.observe_village.return_value = _Snap(did=7)
            ob.observe_player.return_value = None
            ob.cp_summary.return_value = None
            rg.village_stages.return_value = st
            run = vcy.run_village_cycle(rc, _vc())
        self.assertEqual(ran, ["a"])
        self.assertEqual([r.status for r in run.results], ["ok", "skipped", "skipped"])
        self.assertEqual(len(rc.rows), 1)

    def test_snapshot_updates_applied_between_stages(self):
        rc, seen = _rc(), []
        st = [NS(name="a", mode_key=None), NS(name="b", mode_key=None)]

        def fake_run(s, rc_, vc_, snap):
            seen.append(snap.stock)
            return NS(status="ok", snapshot_updates={"stock": (9, 9, 9, 9)} if s.name == "a" else {})
        with mock.patch.object(vcy, "village_switch") as sw, mock.patch.object(vcy, "village_lock") as lk, \
                mock.patch.object(vcy, "observe") as ob, mock.patch.object(vcy, "registry") as rg, \
                mock.patch.object(vcy, "stage_mode", return_value=Mode.DRY), \
                mock.patch.object(vcy, "_lock_from_cfg", return_value=NS(main_did=7)), \
                mock.patch.object(vcy, "run_stage", side_effect=fake_run):
            sw.assert_active.return_value = True
            lk.decide_lock.return_value = NS(kind="ok", reason="", record=False)
            ob.observe_village.return_value = _Snap(did=7)
            ob.observe_player.return_value = None
            ob.cp_summary.return_value = None
            rg.village_stages.return_value = st
            run = vcy.run_village_cycle(rc, _vc())
        self.assertEqual(seen, [(0, 0, 0, 0), (9, 9, 9, 9)])
        self.assertEqual(run.snapshot.stock, (9, 9, 9, 9))


class Run(unittest.TestCase):
    def _rc(self):
        rc = _rc()
        rc.gateway = NS(request_count=lambda: 0, elapsed=lambda: 0.0)
        return rc

    def test_village_exception_isolated_and_reported(self):
        rc = self._rc()
        with mock.patch.object(orchestrator.village_cycle, "run_village_cycle", side_effect=RuntimeError("x")), \
                mock.patch.object(orchestrator, "registry") as rg:
            rg.account_stages.return_value = []
            rep = orchestrator.run(rc, [NS(did=7)], [_vc()])
        self.assertTrue(rep.failed)
        self.assertEqual(len(rep.errors), 1)

    def test_session_lost_propagates(self):
        from travian_bot.infra.session import SessionLost
        rc = self._rc()
        with mock.patch.object(orchestrator.village_cycle, "run_village_cycle", side_effect=SessionLost("x")):
            with self.assertRaises(SessionLost):
                orchestrator.run(rc, [NS(did=7)], [_vc()])

    def test_failed_stage_makes_report_failed(self):
        rc = self._rc()
        run_ = vcy.VillageRun(did=7, snapshot=_Snap(did=7), results=[NS(status="failed")])
        with mock.patch.object(orchestrator.village_cycle, "run_village_cycle", return_value=run_), \
                mock.patch.object(orchestrator, "registry") as rg:
            rg.account_stages.return_value = []
            self.assertTrue(orchestrator.run(rc, [NS(did=7)], [_vc()]).failed)


if __name__ == "__main__":
    unittest.main()
