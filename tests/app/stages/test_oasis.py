# -*- coding: utf-8 -*-
"""ap-16 oasis stage（A6a2b）。actions.oasis_exec.scan 在 stage 模組層級換成假的；StageIO 的 oasis_* 換成記錄用的假函式。"""
import dataclasses
import unittest
from datetime import timedelta
from unittest import mock

from travian_bot.app import stage_base as SB
from travian_bot.app.stages import _util as U
from travian_bot.common import geo
from travian_bot.app.stages import oasis as OA
from travian_bot.actions.oasis_exec import OasisExecError
from travian_bot.common.models import HideContext, VillageSnapshot
from travian_bot.common.modes import Mode
from travian_bot.common.parsed import BlockOasis
from travian_bot.infra.gateway import GatewayError
from travian_bot.infra.store.oasis_repo import CenterInfo, OasisTableError

from ..fakes import NOW, NOW_S, FakeGateway, make_rc, make_vc


def bo(x, y, taken=False, bonuses=((0, 25),), animals=()):
    return BlockOasis(x=x, y=y, taken=taken, bonuses=tuple(bonuses), animals=tuple(animals), owner=None)


SCANNED = (bo(10, 0), bo(3, 0, bonuses=((0, 25), (3, 25))), bo(5, 5, taken=True), bo(1, 1, animals=((31, 4),)),
           bo(-4, 2, bonuses=((2, 50),)))


def stamp(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def snap(incoming=0):
    return VillageSnapshot(did=101, ts_utc=NOW_S, stock=(0, 0, 0, 0), prod=(0, 0, 0, 0), cap_wh=1, cap_gr=1, hidden=None,
                           queue_free_in_s=0, queue_slots_used=0, next_target=None, merchants=None, incoming_res=(),
                           outgoing_res=(), incoming_attacks=incoming, units_home=None, units_away=None)


class Env:
    """rc＋可設定的 Oases IO。centers＝list_centers 的回傳；stored＝load 的回傳。"""

    def __init__(self, centers=(), stored=(), save_exc=None, dry_flag=False):
        self.rc, self.rec = make_rc(gateway=FakeGateway(), dry_flag=dry_flag)
        self.saved, self.loaded = [], []
        self.vc = make_vc(modes={"oasis": "live"})

        def save(sh, center, oases, *, now):
            if save_exc:
                raise save_exc
            self.saved.append((center, list(oases), now))
            return len(oases)

        def load(sh, center):
            self.loaded.append(center)
            return list(stored)
        self.rc.io = dataclasses.replace(self.rc.io, oasis_centers=lambda sh: list(centers), oasis_load=load,
                                         oasis_save=save)

    def run(self, snapshot, mode=Mode.LIVE, scan_result=SCANNED, scan_exc=None):
        scan = mock.Mock(return_value=scan_result, side_effect=scan_exc)
        with mock.patch.object(OA, "scan", scan):
            res = OA.run(self.rc, self.vc, snapshot, mode)
        return res, scan

    def ctx(self):
        return U.hide_context_of(self.rc, self.vc)


class PureTest(unittest.TestCase):
    def test_kind_of(self):
        self.assertEqual(OA.kind_of(((0, 25),)), "wood25")
        self.assertEqual(OA.kind_of(((0, 25), (3, 25))), "wood25_crop25")
        self.assertEqual(OA.kind_of(()), "oasis")
        self.assertLessEqual(len(OA.kind_of(((0, 25), (1, 25), (2, 25), (3, 25)))), 20)

    def test_to_hide_oases_filters_sorts_and_blocks(self):
        free, blocked = OA.to_hide_oases(SCANNED, (0, 0), 200)
        self.assertEqual([(o.x, o.y) for o in free], [(3, 0), (-4, 2), (10, 0)])      # 距離 3、4.47、10
        self.assertEqual([o.kind for o in free], ["wood25_crop25", "iron50", "wood25"])
        self.assertTrue(all(o.safe is None for o in free))
        self.assertEqual(blocked, tuple(sorted((geo.map_id(5, 5, 200), geo.map_id(1, 1, 200)))))   # (5|5) 被佔領、(1|1) 有動物

    def test_stage_metadata(self):
        s = OA.STAGE
        self.assertEqual((s.name, s.scope, s.mode_key, s.order), ("oasis", "village", "oasis", 5))


class IncomingTest(unittest.TestCase):
    def test_incoming_with_data_loads_without_scanning_or_row(self):
        e = Env(centers=[CenterInfo(0, 0, stamp(40), 5)], stored=SCANNED)       # 很舊也照用
        res, scan = e.run(snap(1))
        scan.assert_not_called()
        self.assertEqual((res.status, res.actions), ("ok", []))
        self.assertEqual(e.loaded, [(0, 0)])
        self.assertEqual([(o.x, o.y) for o in e.ctx().oases], [(3, 0), (-4, 2), (10, 0)])
        self.assertEqual(e.saved, [])

    def test_incoming_unknown_counts_as_incoming(self):
        e = Env(centers=[CenterInfo(0, 0, stamp(1), 5)], stored=SCANNED)
        res, scan = e.run(snap(None))
        scan.assert_not_called()
        self.assertTrue(e.ctx().oases)

    def test_incoming_without_data_writes_skipped_row_and_does_not_scan(self):
        e = Env(centers=[CenterInfo(7, 7, stamp(1), 5)])                          # 別的中心
        res, scan = e.run(snap(1))
        scan.assert_not_called()
        self.assertEqual([r.result for r in res.actions], ["skipped"])
        self.assertIn("沒有綠洲資料", res.actions[0].detail)
        self.assertEqual(e.loaded, [])
        self.assertEqual(e.ctx().oases, ())                                        # 維持 vc 原本的（空）


class ScanTest(unittest.TestCase):
    def test_fresh_data_does_nothing(self):
        e = Env(centers=[CenterInfo(0, 0, stamp(3), 5)], stored=SCANNED)
        res, scan = e.run(snap(0))
        scan.assert_not_called()
        self.assertEqual((res.status, res.actions), ("skipped", []))
        self.assertEqual(e.loaded, [])

    def test_stale_data_scans_saves_and_applies(self):
        e = Env(centers=[CenterInfo(0, 0, stamp(13), 5)])
        res, scan = e.run(snap(0))
        self.assertEqual(scan.call_args[0][1], (0, 0))
        self.assertEqual(scan.call_args[0][2], 15)
        self.assertEqual(scan.call_args[1]["map_half"], 200)
        self.assertEqual(scan.call_args[1]["max_requests"], 30)
        self.assertEqual(e.saved[0][0], (0, 0))
        self.assertEqual(e.saved[0][2], NOW_S)
        row = res.actions[0]
        self.assertEqual((res.status, row.action, row.mode, row.result), ("ok", "綠洲掃描", "live", "ok"))
        self.assertEqual(row.validate(), [])
        self.assertIn("太舊", row.detail)
        self.assertEqual(len(e.ctx().oases), 3)
        self.assertEqual(e.ctx().home_x, 0)

    def test_no_data_scans(self):
        e = Env(centers=[])
        res, scan = e.run(snap(0))
        self.assertTrue(scan.called)
        self.assertIn("沒有資料", res.actions[0].detail)

    def test_unreadable_time_scans(self):
        e = Env(centers=[CenterInfo(0, 0, "垃圾", 5)])
        _res, scan = e.run(snap(0))
        self.assertTrue(scan.called)

    def test_empty_center_scans(self):
        e = Env(centers=[CenterInfo(0, 0, stamp(1), 0)])
        _res, scan = e.run(snap(0))
        self.assertTrue(scan.called)

    def test_dry_mode_scans_and_saves_but_row_is_dry(self):
        e = Env(centers=[])
        res, _scan = e.run(snap(0), mode=Mode.DRY)
        self.assertEqual((res.actions[0].mode, res.actions[0].result), ("dry", "dry"))
        self.assertEqual(len(e.saved), 1)

    def test_empty_scan_is_failed_and_does_not_save(self):
        e = Env(centers=[])
        res, _scan = e.run(snap(0), scan_result=())
        self.assertEqual((res.status, res.actions[0].result), ("failed", "failed"))
        self.assertEqual(e.saved, [])
        self.assertEqual(e.ctx().oases, ())

    def test_scan_errors_are_failed_rows(self):
        for exc in (OasisExecError("x"), GatewayError("x"), ValueError("x")):
            e = Env(centers=[])
            res, _scan = e.run(snap(0), scan_exc=exc)
            self.assertEqual((res.status, res.actions[0].result), ("failed", "failed"), exc)
            self.assertTrue(e.rec.notes)

    def test_load_error_is_failed_row(self):
        e = Env(centers=[CenterInfo(0, 0, stamp(1), 5)])
        e.rc.io = dataclasses.replace(e.rc.io, oasis_load=mock.Mock(side_effect=OasisTableError("壞列")))
        res, _scan = e.run(snap(1))
        self.assertEqual((res.status, res.actions[0].result), ("failed", "failed"))

    def test_save_failure_warns_but_still_applies(self):
        e = Env(centers=[], save_exc=RuntimeError("quota"))
        res, _scan = e.run(snap(0))
        self.assertEqual(res.actions[0].result, "ok")
        self.assertIn("寫 Oases 失敗", res.actions[0].detail)
        self.assertTrue(any("Oases" in w for w in e.rc.warnings))
        self.assertEqual(len(e.ctx().oases), 3)

    def test_missing_io_is_skipped(self):
        e = Env()
        e.rc.io = dataclasses.replace(e.rc.io, oasis_centers=None)
        res, scan = e.run(snap(0))
        self.assertEqual(res.status, "skipped")
        scan.assert_not_called()

    def test_request_count_in_detail_and_context_keeps_tribe(self):
        e = Env(centers=[])
        scan = mock.Mock(side_effect=lambda gw, *a, **k: (gw.tick(requests=6), SCANNED)[1])
        with mock.patch.object(OA, "scan", scan):
            res = OA.run(e.rc, e.vc, snap(0), Mode.LIVE)
        self.assertIn("請求 6", res.actions[0].detail)
        self.assertEqual(e.ctx().tribe, e.vc.hide_context.tribe)


class ViaRunStageTest(unittest.TestCase):
    def test_off_skips(self):
        e = Env(centers=[])
        e.vc = make_vc(modes={"oasis": "off"})
        with mock.patch.object(OA, "scan") as scan:
            res = SB.run_stage(OA.STAGE, e.rc, e.vc, snap(0))
        self.assertEqual(res.status, "skipped")
        scan.assert_not_called()

    def test_dry_run_env_lowers_live_to_dry_row(self):
        e = Env(centers=[], dry_flag=True)
        with mock.patch.object(OA, "scan", return_value=SCANNED):
            SB.run_stage(OA.STAGE, e.rc, e.vc, snap(0))
        rows = e.rec.of("log_actions")[0][1][1]
        self.assertEqual([(r.mode, r.result) for r in rows], [("dry", "dry")])


class HandoffTest(unittest.TestCase):
    def test_context_is_used_by_hide(self):
        from travian_bot.app.stages import hide as HI
        e = Env(centers=[])
        e.run(snap(0))
        self.assertIsInstance(U.hide_context_of(e.rc, e.vc), HideContext)
        self.assertEqual(len(U.hide_context_of(e.rc, e.vc).oases), 3)
        self.assertEqual(e.vc.hide_context.oases, ())                              # vc 本身沒被改
        self.assertTrue(callable(HI.run))


if __name__ == "__main__":
    unittest.main()
