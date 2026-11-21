# -*- coding: utf-8 -*-
"""ap-05 observe（A6a1）：用真實樣本（S10b dorf1／S10a dorf2／S10a build 頁，S1a／S1b）＋假 gateway、假 Sheet。"""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from travian_bot.app import observe as O
from travian_bot.common import serialize
from travian_bot.common.models import VillageSnapshot
from travian_bot.common.parsed import PlayerInfo
from travian_bot.common.schema import ParseError
from travian_bot.infra.gateway import GatewayError
from travian_bot.infra.session import SessionLost
from travian_bot.parsers.village import parse_dorf1, parse_dorf2, parse_page_facts

from .fakes import NOW, NOW_S, FakeGateway, FakeSession, Recorder, make_rc, make_vc, sample

GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "golden" / "app" / "formatting"
                     / "old_runner.expected.json").read_text(encoding="utf-8"))
D1 = sample("S10b", "dorf1", "20261104")
D2 = sample("S10a", "dorf2", "20261104")        # 空地：aid 20、21
BUILD = sample("S10a", "build_gid0", "20261104")
PAGES = {"dorf1.php": D1, "dorf2.php": D2, **{f"build.php?id=20&category={c}": BUILD for c in (1, 2, 3)}}


def setup(pages=None, session=None, recorder=None, queue_slots=2, gateway=None):
    gw = gateway or FakeGateway(PAGES if pages is None else pages)
    rc, rec = make_rc(gateway=gw, session=session, recorder=recorder)
    return rc, rec, gw, make_vc(queue_slots=queue_slots)


class SnapshotTest(unittest.TestCase):
    def test_snapshot_fields(self):
        rc, _rec, _gw, vc = setup(queue_slots=3)
        snap = O.observe_village(rc, vc)
        d1 = parse_dorf1(D1)
        self.assertIsInstance(snap, VillageSnapshot)
        self.assertEqual(snap.validate(), [])
        self.assertEqual((snap.did, snap.ts_utc), (101, NOW_S))
        self.assertEqual((snap.stock, snap.prod), (d1.stock, d1.prod))
        self.assertEqual((snap.cap_wh, snap.cap_gr), (d1.cap_wh, d1.cap_gr))
        self.assertIsNone(snap.hidden)                                   # D-32
        self.assertEqual(snap.queue_slots_used, len(d1.queue))
        self.assertEqual(snap.queue_free_in_s, 0)                        # 3 格只用 2 格
        self.assertEqual((snap.next_target, snap.merchants, snap.units_home, snap.units_away), (None,) * 4)
        self.assertEqual((snap.incoming_res, snap.outgoing_res), ((), ()))
        self.assertEqual(snap.incoming_attacks, d1.incoming_attacks)

    def test_full_queue_uses_min_remaining(self):
        rc, _rec, _gw, vc = setup(queue_slots=2)
        snap = O.observe_village(rc, vc)
        self.assertEqual(snap.queue_free_in_s, min(q.remaining_s for q in parse_dorf1(D1).queue))
        self.assertGreater(snap.queue_free_in_s, 0)

    def test_hero_updated_on_success(self):
        rc, _rec, _gw, vc = setup()
        O.observe_village(rc, vc)
        self.assertEqual((rc.hero.health_pct, rc.hero.exp_pct), (49, 69))
        self.assertTrue(rc.hero.at_home)

    def test_hero_failure_only_warns_and_keeps_old(self):
        rc, _rec, _gw, vc = setup()
        from travian_bot.parsers.hero import parse_hero_status
        old = parse_hero_status(D1)
        rc.hero = old
        with mock.patch.object(O, "parse_hero_status", side_effect=ParseError("hero", "x")):
            snap = O.observe_village(rc, vc)
        self.assertIsNotNone(snap)
        self.assertIs(rc.hero, old)
        self.assertEqual(len(rc.warnings), 1)

    def test_each_page_fetched_once_and_cached(self):
        rc, _rec, gw, vc = setup()
        O.observe_village(rc, vc)
        O.observe_player(rc)
        self.assertEqual(gw.calls.count("dorf1.php"), 1)
        self.assertEqual(gw.calls.count("dorf2.php"), 1)


class SessionAndErrorsTest(unittest.TestCase):
    def test_login_page_with_recover_retries_once(self):
        sess = FakeSession(recoverable=True)
        rc, _rec, gw, vc = setup(pages={**PAGES, "dorf1.php": ["<html>login</html>", "<html>login</html>", D1]}, session=sess)
        snap = O.observe_village(rc, vc)     # 瀏覽器版與 raw_if 的純 HTTP 備援都是登入頁，才輪到 recover
        self.assertEqual(sess.recovered, 1)
        self.assertEqual(snap.did, 101)

    def test_login_page_without_recover_raises_session_lost(self):
        sess = FakeSession(recoverable=False)
        rc, _rec, _gw, vc = setup(pages={**PAGES, "dorf1.php": "<html>login</html>"}, session=sess)
        with self.assertRaises(SessionLost):
            O.observe_village(rc, vc)
        self.assertEqual(sess.recovered, 0)

    def test_still_login_after_recover_raises(self):
        sess = FakeSession(recoverable=True)
        rc, _rec, _gw, vc = setup(pages={**PAGES, "dorf1.php": "<html>login</html>"}, session=sess)
        with self.assertRaises(SessionLost):
            O.observe_village(rc, vc)
        self.assertEqual(sess.recovered, 1)

    def test_gateway_errors_propagate(self):
        for path in ("dorf1.php", "dorf2.php"):
            rc, _rec, _gw, vc = setup(gateway=FakeGateway(PAGES, fail={path: GatewayError("fail")}))
            with self.assertRaises(GatewayError):
                O.observe_village(rc, vc)

    def test_parse_errors_propagate(self):
        rc, _rec, _gw, vc = setup(pages={**PAGES, "dorf1.php": '<html><div id="stockBar"></div></html>'})
        with self.assertRaises(ParseError):
            O.observe_village(rc, vc)
        rc, _rec, _gw, vc = setup(pages={**PAGES, "dorf2.php": "<html></html>"})
        with self.assertRaises(ParseError):
            O.observe_village(rc, vc)

    def test_nothing_written_when_page_step_fails(self):
        rc, rec, _gw, vc = setup(pages={**PAGES, "dorf2.php": "<html></html>"})
        with self.assertRaises(ParseError):
            O.observe_village(rc, vc)
        self.assertEqual(rec.names(), [])


class SheetWritesTest(unittest.TestCase):
    def test_sheet1_row_and_structure_and_buildable(self):
        rc, rec, gw, vc = setup()
        O.observe_village(rc, vc)
        self.assertEqual(rec.names(), ["append_snapshot", "write_structure", "buildable_due", "write_structure"])
        (_n, a, _k), = rec.of("append_snapshot")
        self.assertEqual(a[1], 101)
        self.assertEqual(a[2].village_name, "測試村")
        s1, s2 = (c[2] for c in rec.of("write_structure"))
        self.assertEqual(set(s1), {"now", "fields", "buildings", "names"})
        self.assertEqual(len(s1["fields"]), 18)
        self.assertEqual(s1["now"], NOW_S)
        self.assertEqual(set(s2), {"now", "buildable", "names"})
        self.assertTrue(s2["buildable"])
        self.assertEqual([c for c in gw.calls if c.startswith("build.php")],
                         [f"build.php?id=20&category={c}" for c in (1, 2, 3)])

    def test_buildable_skipped_when_not_due_and_unchanged(self):
        rc, rec, gw, vc = setup(recorder=Recorder(buildable_due=False, structure_changed=False))
        O.observe_village(rc, vc)
        self.assertEqual(len(rec.of("write_structure")), 1)
        self.assertFalse([c for c in gw.calls if c.startswith("build.php")])

    def test_buildable_fetched_when_buildings_changed(self):
        rc, rec, _gw, vc = setup(recorder=Recorder(buildable_due=False, structure_changed=True))
        O.observe_village(rc, vc)
        self.assertEqual(len(rec.of("write_structure")), 2)

    def test_no_free_slot_skips_buildable(self):
        with mock.patch.object(O, "_first_free_aid", return_value=None):
            rc, rec, _gw, vc = setup()
            O.observe_village(rc, vc)
        self.assertEqual(len(rec.of("write_structure")), 1)
        self.assertEqual(rec.of("buildable_due"), [])

    def test_sheet_failures_only_warn(self):
        for failing in ("append_snapshot", "write_structure"):
            rc, rec, _gw, vc = setup(recorder=Recorder(fail={failing: RuntimeError("sheet down")}))
            snap = O.observe_village(rc, vc)
            self.assertEqual(snap.did, 101)
            self.assertTrue(rc.warnings, failing)
            self.assertTrue(all("不影響升級" in w for w in rc.warnings))

    def test_append_failure_does_not_stop_structure(self):
        rc, rec, _gw, vc = setup(recorder=Recorder(fail={"append_snapshot": RuntimeError("x")}))
        O.observe_village(rc, vc)
        self.assertTrue(rec.of("write_structure"))

    def test_buildable_page_failure_only_warns(self):
        gw = FakeGateway(PAGES, fail={"build.php?id=20&category=2": GatewayError("x")})
        rc, rec, _gw, vc = setup(gateway=gw)
        snap = O.observe_village(rc, vc)
        self.assertEqual(snap.did, 101)
        self.assertTrue(rc.warnings)

    def test_first_free_aid_ignores_wall_and_rally_slots(self):
        d2 = parse_dorf2(sample("S12a", "dorf2", "20261031"))
        self.assertEqual(O._first_free_aid(d2), 19)
        self.assertIsNone(O._first_free_aid(type(d2)(tuple(s for s in d2.slots if s.aid > 38))))


class FetchBuildOptionsTest(unittest.TestCase):
    def test_three_categories_dedup_by_gid_keeping_order(self):
        rc, _rec, gw, _vc = setup()
        opts = O.fetch_build_options(rc, 20)
        self.assertIsInstance(opts, tuple)
        gids = [o.gid for o in opts]
        self.assertEqual(len(gids), len(set(gids)))
        self.assertTrue(gids)
        self.assertEqual(gw.calls, [f"build.php?id=20&category={c}" for c in (1, 2, 3)])
        self.assertFalse(hasattr(opts[0], "category"))


class PlayerTest(unittest.TestCase):
    def test_observe_player_uses_cached_dorf1(self):
        rc, _rec, gw, _vc = setup()
        rc.pages["dorf1.php"] = D1
        info = O.observe_player(rc)
        self.assertEqual(info.tribe_id, 3)
        self.assertEqual(gw.calls, [])

    def test_observe_player_fetches_dorf1_when_missing(self):
        rc, _rec, gw, _vc = setup()
        O.observe_player(rc)
        self.assertEqual(gw.calls, ["dorf1.php"])

    def test_parse_error_falls_back_to_dorf2(self):
        rc, _rec, gw, _vc = setup(pages={"dorf1.php": "<html></html>", "dorf2.php": D2})
        info = O.observe_player(rc)
        self.assertIsNotNone(info)
        self.assertEqual(gw.calls, ["dorf1.php", "dorf2.php"])

    def test_both_fail_raises(self):
        rc, _rec, _gw, _vc = setup(pages={"dorf1.php": "<html></html>", "dorf2.php": "<html></html>"})
        with self.assertRaises(ParseError):
            O.observe_player(rc)

    def test_write_player_state_ok_and_failure(self):
        rc, rec, _gw, vc = setup()
        info = O.observe_player(rc)
        snap = O.observe_village(rc, vc)
        self.assertTrue(O.write_player_state(rc, vc, info, snap, 2))
        (_n, a, _k), = rec.of("write_state")
        self.assertEqual((a[1], a[3]), (101, NOW_S))
        self.assertIn("queue_slots", [r[0] for r in a[2]])
        rc2, rec2, _g, vc2 = setup(recorder=Recorder(fail={"write_state": RuntimeError("x")}))
        self.assertFalse(O.write_player_state(rc2, vc2, info, None, 1))
        self.assertEqual(len(rc2.warnings), 1)


# ---------------------------------------------------------------- 純函式
class PureFunctionsTest(unittest.TestCase):
    def test_hours_and_eta(self):
        self.assertEqual(O.hours_1dp(5400), 1.5)
        self.assertEqual(O.hours_1dp(3599), 1.0)
        self.assertIsNone(O.hours_1dp(None))
        for secs, want in ((None, None), (0, 0), (59, 0), (60, 1), (119, 1), (3600, 60)):
            self.assertEqual(O.attack_eta_minutes(secs), want, secs)

    def test_row_matches_old_sheet1_for_shared_columns(self):
        for old in GOLDEN["sheet1_old"]:
            html = sample(old["sample"], "dorf1", "20261031")
            d1 = parse_dorf1(html)
            row = O.build_snapshot_row(now=NOW, village_name="v", dorf1=d1, facts=parse_page_facts(html),
                                       hero=__import__("travian_bot.parsers.hero", fromlist=["x"]).parse_hero_status(html))
            self.assertEqual(list(row.stock), old["stock"])
            self.assertEqual(list(row.prod[:3]), old["prod"][:3])
            self.assertEqual(row.free_crop, old["free_crop"])
            self.assertEqual((row.hero_health_pct, row.hero_exp_pct, row.hero_adventures),
                             (old["hero_health_pct"], old["hero_exp_pct"], old["hero_adventures"]))
            # D-34：這四欄 A6a1 一律空白（舊版有值）
            self.assertEqual((row.population, row.loyalty_pct, row.gold, row.silver), (None,) * 4)
            self.assertIsNotNone(old["population"])

    def test_known_difference_crop_production(self):
        """舊版記 stockBar 標題值，新版記 dorf1 的 l4（淨產量）。S1a 舊 298、新 196；S1b 舊 460、新 382。"""
        for old, new in zip(GOLDEN["sheet1_old"], (196, 382)):
            d1 = parse_dorf1(sample(old["sample"], "dorf1", "20261031"))
            self.assertEqual(d1.prod[3], new)
            self.assertNotEqual(old["prod"][3], new)

    def test_row_fields(self):
        html = sample("S1a", "dorf1", "20261031")
        d1 = parse_dorf1(html)
        facts = parse_page_facts(html)
        row = O.build_snapshot_row(now=NOW, village_name="v", dorf1=d1, facts=facts, hero=None)
        self.assertEqual(row.ts_utc, NOW_S)
        self.assertEqual(row.server_time, serialize.to_utc_str(datetime.fromtimestamp(facts.server_ts, timezone.utc)))
        self.assertEqual((row.hero_health_pct, row.hero_exp_pct, row.hero_adventures), (None,) * 3)
        self.assertEqual(row.queue, d1.queue)
        self.assertEqual((row.plus_hours, row.protection_hours), (None, None))
        self.assertEqual(row.attacks, d1.incoming_attacks)
        self.assertIsNone(O.build_snapshot_row(now=NOW, village_name="v", dorf1=d1, facts=None, hero=None).server_time)

    def test_row_converts_seconds(self):
        import dataclasses
        d1 = dataclasses.replace(parse_dorf1(D1), plus_s=5400, protection_s=7200, attack_eta_s=125, incoming_attacks=2)
        row = O.build_snapshot_row(now=NOW, village_name="v", dorf1=d1, facts=None, hero=None)
        self.assertEqual((row.plus_hours, row.protection_hours, row.attacks, row.attack_eta_min), (1.5, 2.0, 2, 2))

    def test_row_is_writable_by_snapshot_repo(self):
        from travian_bot.infra.store import snapshot_repo
        d1 = parse_dorf1(D1)
        row = O.build_snapshot_row(now=NOW, village_name="v", dorf1=d1, facts=parse_page_facts(D1), hero=None)
        cells = snapshot_repo.sheet1_cells(row, 101)
        self.assertEqual(len(cells), len(snapshot_repo.SHEET1_HEADER))


def _snap(cap):
    if cap is None:
        return None
    return VillageSnapshot(1, NOW_S, (0, 0, 0, 0), (0, 0, 0, 0), cap[0], cap[3], None, 0, 0, None, None, (), (), 0, None, None)


def _info(d):
    if d is None:
        return None
    cp = d.get("cp") or {}
    return PlayerInfo(tribe_id=d["tribe_id"], plus_active=d["plus_active"], cp_have=cp.get("have"), cp_need=cp.get("need"),
                      cp_per_day=cp.get("per_day"), village_slots_used=cp.get("used"), village_slots_max=cp.get("max"))


class StateRowsGoldenTest(unittest.TestCase):
    def test_matches_old_build_state_rows(self):
        for c in GOLDEN["state_rows"]:
            rows = O.build_state_rows(_info(c["info"]), _snap(c["cap"]), c["queue_slots"])
            norm = [[k, ("TRUE" if v else "FALSE") if isinstance(v, bool) else v, n] for k, v, n in rows]
            self.assertEqual(norm, c["rows"], c["case"])

    def test_plus_active_is_bool_and_state_repo_writes_true_false(self):
        from travian_bot.infra.store import state_repo
        rows = O.build_state_rows(_info({"tribe_id": 3, "plus_active": True, "cp": None}), None, 1)
        self.assertIs(dict((k, v) for k, v, _ in rows)["plus_active"], True)
        cells = state_repo.build_rows(101, rows, NOW_S)
        self.assertIn("TRUE", [c for r in cells for c in r])

    def test_keys_are_in_state_repo_account_or_village_sets(self):
        rows = O.build_state_rows(_info(GOLDEN["state_rows"][0]["info"]), _snap([6300] * 4), 2)
        from travian_bot.infra.store import state_repo
        self.assertTrue(state_repo.build_rows(101, rows, NOW_S))


class CpSummaryGoldenTest(unittest.TestCase):
    def test_matches_old(self):
        for c in GOLDEN["cp_summary"]:
            info = _info({"tribe_id": 3, "plus_active": True, "cp": c["cp"]})
            self.assertEqual(O.cp_summary(info), c["text"], c["case"])

    def test_unreadable_returns_none(self):
        self.assertIsNone(O.cp_summary(None))
        self.assertIsNone(O.cp_summary(_info({"tribe_id": 3, "plus_active": True, "cp": None})))


if __name__ == "__main__":
    unittest.main()
