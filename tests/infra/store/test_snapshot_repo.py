import unittest

from travian_bot.common.parsed import BuildCondition, BuildingSlot, BuildOption, QueueItem, ResField
from travian_bot.infra.store import snapshot_repo as S

try:
    from .fakes import FakeSheet, FakeWS, patch_gspread
except ImportError:  # 直接以檔案執行時
    from fakes import FakeSheet, FakeWS, patch_gspread

T0, T1, T2 = "2026-11-14T08:00:00Z", "2026-11-14T08:30:00Z", "2026-11-15T09:00:00Z"
_p = None


def setUpModule():
    global _p
    _p = patch_gspread()
    _p.start()


def tearDownModule():
    _p.stop()


def F(aid, gid=4, level=9, cost=(1, 2, 3, 4), secs=100, uc=False):
    return ResField(aid, gid, level, cost, secs, uc, None)


def B(aid, gid=None, level=0, name=None, uc=False):
    return BuildingSlot(aid, gid, level, name, uc)


def O(gid, met=True, cost=(10, 20, 30, 40), secs=60, conds=None):
    c = conds if conds is not None else ([] if met else [BuildCondition(22, "研究院", 10, False, 9, False)])
    return BuildOption(gid, f"b{gid}", cost, secs if met else None, met, None, False, None, None, tuple(c))


def snap(**kw):
    d = dict(ts_utc=T0, server_time="8:07:51", village_name="v", population=420, loyalty_pct=100, gold=100,
             silver=6625, stock=(1, 2, 3, 4), prod=(5, 6, 7, 8), free_crop=1403, hero_health_pct=53,
             hero_exp_pct=62, hero_adventures=12, queue=(QueueItem(14776, "泥坑 等級 10"),), plus_hours=None,
             protection_hours=None, attacks=0, attack_eta_min=None)
    d.update(kw)
    return S.SnapshotLogRow(**d)


def tab(sh, name):
    return sh.tabs[name].get_all_values()


def kinds(sh):
    return [r[1] for r in tab(sh, "Changes")[1:]]


class TestSheet1(unittest.TestCase):
    def test_new_sheet_header_and_row(self):
        sh = FakeSheet()
        S.append_snapshot(sh, 7, snap())
        v = tab(sh, "Sheet1")
        self.assertEqual(tuple(v[0]), S.SHEET1_HEADER)
        r = v[1]
        self.assertEqual(r[0], T0)
        self.assertEqual(r[7:15], ["1", "5", "2", "6", "3", "7", "4", "8"])     # 存量、產量交錯（舊欄序）
        self.assertEqual(r[19], '[{"info":"泥坑 等級 10","remaining_s":14776}]')
        self.assertEqual(r[20:24], ["", "", "0", ""])                              # None＝空白、0 照寫
        self.assertEqual(r[24], "7")

    def test_second_append_no_second_header(self):
        sh = FakeSheet()
        S.append_snapshot(sh, 7, snap())
        S.append_snapshot(sh, 7, snap(ts_utc=T1))
        v = tab(sh, "Sheet1")
        self.assertEqual(len(v), 3)
        self.assertEqual(v[2][0], T1)

    def test_old_24col_header_gets_did(self):
        sh = FakeSheet({"Sheet1": FakeWS("Sheet1", rows=[list(S._SHEET1_V1), ["old"] * 24], col_count=26)})
        S.append_snapshot(sh, 1, snap())
        v = tab(sh, "Sheet1")
        self.assertEqual(tuple(v[0]), S.SHEET1_HEADER)
        self.assertEqual(v[1][0], "old")
        self.assertEqual(len(v), 3)

    def test_foreign_header_refused(self):
        sh = FakeSheet({"Sheet1": FakeWS("Sheet1", rows=[["a", "b"]])})
        with self.assertRaises(S.SnapshotTableError):
            S.append_snapshot(sh, 1, snap())
        self.assertEqual(tab(sh, "Sheet1"), [["a", "b"]])

    def test_empty_queue_and_none_resources(self):
        sh = FakeSheet()
        S.append_snapshot(sh, 1, snap(queue=(), stock=None, prod=None))
        r = tab(sh, "Sheet1")[1]
        self.assertEqual(r[19], "")
        self.assertEqual(r[7:15], [""] * 8)

    def test_bad_did_and_bad_time(self):
        with self.assertRaises(ValueError):
            S.append_snapshot(FakeSheet(), 0, snap())
        with self.assertRaises(Exception):
            S.append_snapshot(FakeSheet(), 1, snap(ts_utc="2026-11-14 8:07:51"))


class TestFields(unittest.TestCase):
    def test_init_then_no_write_when_same(self):
        sh = FakeSheet()
        r = S.write_structure(sh, 1, now=T0, fields=[F(2), F(1, level=10)], names={4: "農場"})
        v = tab(sh, "Fields")
        self.assertEqual(tuple(v[0]), S.FIELDS_HEADER)
        self.assertEqual(v[1][:5], ["1", "4", "農場", "10", "FALSE"])
        self.assertEqual(v[1][5:10], ["1", "2", "3", "4", "100"])
        self.assertEqual(v[1][10:], [T0, "1"])
        self.assertEqual(r.initialized, ("Fields",))
        self.assertEqual(kinds(sh), ["initialized"])
        n = sh.tabs["Fields"].n_calls("update")
        r2 = S.write_structure(sh, 1, now=T1, fields=[F(2), F(1, level=10)], names={4: "農場"})
        self.assertEqual(sh.tabs["Fields"].n_calls("update"), n)
        self.assertEqual(r2.wrote, ())
        self.assertEqual(kinds(sh), ["initialized"])
        self.assertEqual(tab(sh, "Fields")[1][10], T0)

    def test_level_and_build_started(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, fields=[F(1), F(2)])
        S.write_structure(sh, 1, now=T1, fields=[F(1, uc=True), F(2, level=10)])
        v = tab(sh, "Changes")
        self.assertEqual([r[1] for r in v[2:]], ["field_level", "field_build_started"] if v[2][2] == "field:2" else ["field_build_started", "field_level"])
        by = {r[1]: r for r in v[2:]}
        self.assertEqual((by["field_level"][2], by["field_level"][5], by["field_level"][6]), ("field:2", "9", "10"))
        self.assertEqual((by["field_build_started"][2], by["field_build_started"][5], by["field_build_started"][6]), ("field:1", "9", "10"))
        f = {r[0]: r for r in tab(sh, "Fields")[1:]}
        self.assertEqual(f["1"][10], T1)
        self.assertEqual(f["2"][10], T1)

    def test_type_change_and_removed(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, fields=[F(1), F(2)])
        S.write_structure(sh, 1, now=T1, fields=[F(1, gid=1)])
        self.assertEqual(sorted(kinds(sh)[1:]), ["field_removed", "field_type_changed"])
        self.assertEqual(len(tab(sh, "Fields")), 2)

    def test_cost_carry_forward_same_level_only(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, fields=[F(1, cost=(7, 8, 9, 10), secs=555)])
        S.write_structure(sh, 1, now=T1, fields=[F(1, cost=None, secs=None, uc=True)])
        r = tab(sh, "Fields")[1]
        self.assertEqual(r[5:10], ["7", "8", "9", "10", "555"])
        self.assertEqual(r[4], "TRUE")
        S.write_structure(sh, 1, now=T2, fields=[F(1, level=10, cost=None, secs=None)])
        self.assertEqual(tab(sh, "Fields")[1][5:10], [""] * 5)          # 等級變了不沿用

    def test_two_villages_isolated(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, fields=[F(1), F(2)])
        r = S.write_structure(sh, 2, now=T0, fields=[F(1, level=3)])
        self.assertEqual(r.initialized, ("Fields",))
        self.assertEqual(kinds(sh), ["initialized", "initialized"])
        S.write_structure(sh, 2, now=T1, fields=[F(1, level=4)])
        v = tab(sh, "Fields")[1:]
        self.assertEqual([(x[0], x[3], x[-1]) for x in v], [("1", "9", "1"), ("2", "9", "1"), ("1", "4", "2")])

    def test_empty_input_skips(self):
        sh = FakeSheet()
        r = S.write_structure(sh, 1, now=T0, fields=[], buildings=None)
        self.assertEqual((r.wrote, r.changes), ((), ()))
        self.assertEqual(sh.tabs, {})

    def test_legacy_header_rebuilt(self):
        old = [["位置(slot)", "類型", "等級"], ["1", "農場", "9"], ["2", "農場", "9"], ["3", "農場", "9"]]
        sh = FakeSheet({"Fields": FakeWS("Fields", rows=old)})
        S.write_structure(sh, 1, now=T0, fields=[F(1)])
        v = tab(sh, "Fields")
        self.assertEqual(tuple(v[0]), S.FIELDS_HEADER)
        self.assertEqual(len(v), 2)

    def test_duplicate_aid_rejected(self):
        with self.assertRaises(ValueError):
            S.write_structure(FakeSheet(), 1, now=T0, fields=[F(1), F(1)])


class TestBuildings(unittest.TestCase):
    def test_empty_slot_blank_gid(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, buildings=[B(19, 26, 10, "皇宮"), B(25)])
        v = tab(sh, "Buildings")
        self.assertEqual(v[1][:5], ["19", "26", "皇宮", "10", "FALSE"])
        self.assertEqual(v[2][:5], ["25", "", "", "0", "FALSE"])

    def test_events(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, buildings=[B(25), B(26, 15, 20, "x"), B(27, 13, 5, "y"), B(28, 22, 9, "z")])
        r = S.write_structure(sh, 1, now=T1, buildings=[B(25, 17, 0, "市場", uc=True), B(26), B(27, 20, 5, "馬廄"),
                                                         B(28, 22, 9, "z", uc=True)])
        self.assertTrue(r.buildings_changed)
        got = {x[2]: x for x in tab(sh, "Changes")[2:]}
        self.assertEqual(got["building:25"][1], "building_built")
        self.assertEqual(got["building:25"][8 - 1], "under_construction")
        self.assertEqual(got["building:26"][1], "building_removed")
        self.assertEqual((got["building:27"][1], got["building:27"][5], got["building:27"][6]), ("building_changed", "13", "20"))
        self.assertEqual((got["building:28"][1], got["building:28"][5], got["building:28"][6]), ("building_build_started", "9", "10"))

    def test_level_up_and_unchanged_flag(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, buildings=[B(34, 20, 9, "x")])
        r = S.write_structure(sh, 1, now=T1, buildings=[B(34, 20, 10, "x")])
        self.assertEqual(kinds(sh)[-1], "building_level")
        r2 = S.write_structure(sh, 1, now=T2, buildings=[B(34, 20, 10, "x")])
        self.assertFalse(r2.buildings_changed)
        self.assertTrue(r.buildings_changed)


class TestBuildable(unittest.TestCase):
    def test_init_columns(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, buildable=[O(24, met=False), O(23)])
        v = tab(sh, "Buildable")
        self.assertEqual(tuple(v[0]), S.BUILDABLE_HEADER)
        self.assertEqual(v[1][:9], ["23", "b23", "10", "20", "30", "40", "60", "TRUE", ""])
        self.assertEqual(v[2][7], "FALSE")
        self.assertEqual(v[2][8], '[{"current":9,"forbidden":false,"gid":22,"level":10,"name":"研究院"}]')
        self.assertEqual(v[2][9:], [T0, T0, "1"])
        self.assertEqual(v[2][6], "")          # 不能蓋時沒有工期

    def test_refresh_updates_checked_only(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, buildable=[O(23)])
        r = S.write_structure(sh, 1, now=T1, buildable=[O(23)])
        row = tab(sh, "Buildable")[1]
        self.assertEqual((row[9], row[10]), (T0, T1))
        self.assertEqual(r.wrote, ("Buildable",))
        self.assertEqual(kinds(sh), ["initialized"])

    def test_prereq_flip_and_add_remove(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, buildable=[O(24, met=False), O(25), O(26, met=False)])
        S.write_structure(sh, 1, now=T1, buildable=[O(24), O(26, met=False), O(27)])
        ch = {(r[1], r[3]): r for r in tab(sh, "Changes")[2:]}
        self.assertIn(("prereq_met", "24"), ch)
        self.assertIn(("buildable_removed", "25"), ch)
        self.assertIn(("buildable_added", "27"), ch)
        self.assertEqual(len(ch), 3)

    def test_unmet_text_change_not_logged(self):
        sh = FakeSheet()
        a = O(24, conds=[BuildCondition(22, "研究院", 10, False, 8, False)])
        b = O(24, conds=[BuildCondition(22, "研究院", 10, False, 9, False)])
        S.write_structure(sh, 1, now=T0, buildable=[a])
        S.write_structure(sh, 1, now=T1, buildable=[b])
        self.assertEqual(kinds(sh), ["initialized"])
        self.assertIn('"current":9', tab(sh, "Buildable")[1][8])

    def test_prereq_unmet_note(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, buildable=[O(24)])
        S.write_structure(sh, 1, now=T1, buildable=[O(24, met=False)])
        r = tab(sh, "Changes")[-1]
        self.assertEqual((r[1], r[5], r[6]), ("prereq_unmet", "TRUE", "FALSE"))
        self.assertIn("研究院", r[7])

    def test_buildable_due(self):
        sh = FakeSheet()
        self.assertTrue(S.buildable_due(sh, 1, now=T0))
        S.write_structure(sh, 1, now=T0, buildable=[O(23)])
        self.assertFalse(S.buildable_due(sh, 1, now=T1))
        self.assertTrue(S.buildable_due(sh, 1, now=T2))              # 超過 24 小時
        self.assertTrue(S.buildable_due(sh, 2, now=T1))              # 另一個村沒資料
        sh.tabs["Buildable"].rows[1][10] = "garbage"
        self.assertTrue(S.buildable_due(sh, 1, now=T1))              # 讀不到有效時間

    def test_cost_none_blank(self):
        sh = FakeSheet()
        o = BuildOption(23, "x", None, None, False, None, False, None, None, ())
        S.write_structure(sh, 1, now=T0, buildable=[o])
        self.assertEqual(tab(sh, "Buildable")[1][2:7], [""] * 5)


class TestChangesTab(unittest.TestCase):
    def test_foreign_changes_header_refused_and_state_still_written(self):
        sh = FakeSheet({"Changes": FakeWS("Changes", rows=[["時間(UTC)", "類別"], ["x", "y"]])})
        with self.assertRaises(S.SnapshotTableError):
            S.write_structure(sh, 1, now=T0, fields=[F(1)])
        self.assertEqual(tab(sh, "Changes"), [["時間(UTC)", "類別"], ["x", "y"]])
        self.assertEqual(len(tab(sh, "Fields")), 2)

    def test_earlier_changes_kept_when_later_step_fails(self):
        sh = FakeSheet()
        S.write_structure(sh, 1, now=T0, fields=[F(1)])
        S.write_structure(sh, 1, now=T0, buildings=[B(34, 20, 9, "x")])
        ws = sh.tabs["Buildings"]
        ws.fail_on = {"update": RuntimeError("boom")}
        with self.assertRaises(RuntimeError):
            S.write_structure(sh, 1, now=T1, fields=[F(1, level=10)], buildings=[B(34, 20, 10, "x")])
        self.assertEqual(kinds(sh)[-1], "field_level")

    def test_row_layout_and_did(self):
        sh = FakeSheet()
        S.write_structure(sh, 5, now=T0, fields=[F(1)])
        S.write_structure(sh, 5, now=T1, fields=[F(1, level=10)])
        v = tab(sh, "Changes")
        self.assertEqual(tuple(v[0]), S.CHANGES_HEADER)
        self.assertEqual(v[2], [T1, "field_level", "field:1", "4", "", "9", "10", "", "5"])


if __name__ == "__main__":
    unittest.main()
