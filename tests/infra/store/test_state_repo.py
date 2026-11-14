import unittest

from travian_bot.infra.store import state_repo as R
from .fakes import FakeSheet, FakeWS, patch_gspread

_p = patch_gspread()


def setUpModule():
    _p.start()


def tearDownModule():
    _p.stop()


H = list(R.STATE_HEADER)
T1, T2 = "2026-11-14T08:00:00Z", "2026-11-14T09:00:00Z"
ACC = [("tribe", "gaul", "種族"), ("plus_active", True, "Plus"), ("cp_have", 1200, "文化點")]
VIL = [("queue_slots", 1, "佇列"), ("cap_wood", 8000, "木倉")]


class TestBuild(unittest.TestCase):
    def test_account_keys_have_blank_did(self):
        rows = R.build_rows(101, ACC + VIL, T1)
        self.assertEqual([r[4] for r in rows], ["", "", "", 101, 101])
        self.assertEqual(rows[1][1], "TRUE")
        self.assertEqual(rows[0][3], T1)

    def test_none_value_is_skipped_not_listed(self):
        rows = R.build_rows(1, [("cp_have", None, "x"), ("queue_slots", 1, "y")], T1)
        self.assertEqual([r[0] for r in rows], ["queue_slots"])

    def test_bad_input(self):
        for args in ((0, VIL, T1), (1, [("", 1, "")], T1), (1, [("a b", 1, "")], T1),
                     (1, [("a", 1, ""), ("a", 2, "")], T1), (1, [("a", [1], "")], T1), (1, VIL, "2026-11-14 08:00:00")):
            with self.assertRaises(ValueError, msg=repr(args)):
                R.build_rows(*args)


class TestWrite(unittest.TestCase):
    def test_first_write_creates_tab_with_header(self):
        sh = FakeSheet()
        n = R.write_state(sh, 101, ACC + VIL, T1)
        ws = sh.tabs["state"]
        self.assertEqual(n, 5)
        self.assertEqual(ws.rows[0], H)
        self.assertEqual(ws.rows[1][:5], ["tribe", "gaul", "種族", T1, ""])
        self.assertEqual(ws.rows[4][:2], ["queue_slots", "1"])
        self.assertEqual(ws.last_update[2], "RAW")
        self.assertEqual(ws.n_calls("update"), 1)

    def test_other_village_kept_this_village_replaced(self):
        sh = FakeSheet()
        R.write_state(sh, 101, ACC + VIL, T1)
        R.write_state(sh, 202, VIL, T1)
        R.write_state(sh, 101, [("queue_slots", 2, "佇列")], T2)          # 101 換成更短的一組
        ws = sh.tabs["state"]
        body = [(r[0], r[1], r[3], r[4]) for r in ws.rows[1:] if r[0]]
        self.assertIn(("queue_slots", "2", T2, "101"), body)
        self.assertNotIn(("cap_wood", "8000", T1, "101"), body)          # 101 舊的 cap_wood 沒了
        self.assertIn(("cap_wood", "8000", T1, "202"), body)             # 202 不受影響
        self.assertIn(("tribe", "gaul", T1, ""), body)                   # 沒給帳號級鍵 → 帳號級舊列保留（舊時間）
        self.assertEqual([r[0] for r in ws.rows[1:] if r[0]].count("queue_slots"), 2)

    def test_account_rows_replaced_when_given(self):
        sh = FakeSheet()
        R.write_state(sh, 101, ACC, T1)
        R.write_state(sh, 101, [("cp_have", 1500, "文化點")], T2)
        ws = sh.tabs["state"]
        body = [(r[0], r[1], r[3]) for r in ws.rows[1:] if r[0]]
        self.assertEqual(body, [("cp_have", "1500", T2)])

    def test_order_account_first_then_villages_ascending(self):
        sh = FakeSheet()
        R.write_state(sh, 202, VIL, T1)
        R.write_state(sh, 101, ACC + VIL, T1)
        dids = [r[4] for r in sh.tabs["state"].rows[1:] if r[0]]
        self.assertEqual(dids, ["", "", "", "101", "101", "202", "202"])

    def test_shrink_blanks_the_tail_in_the_same_request(self):
        sh = FakeSheet()
        R.write_state(sh, 101, ACC + VIL, T1)               # 1 表頭＋5 列
        ws = sh.tabs["state"]
        ws.calls.clear()
        R.write_state(sh, 101, ACC + [("queue_slots", 1, "x")], T2)     # 1 表頭＋4 列 → 尾端多 1 列要蓋掉
        self.assertEqual((ws.n_calls("update"), ws.n_calls("append_rows")), (1, 0))
        self.assertEqual([r[0] for r in ws.rows[1:5]], ["tribe", "plus_active", "cp_have", "queue_slots"])
        self.assertEqual(ws.rows[5], [""] * 5)
        self.assertEqual(len(ws.get_all_values()), 5)

    def test_old_four_column_header_is_rebuilt(self):
        ws = FakeWS("state", rows=[["項目(key)", "值", "說明", "更新時間(UTC)"], ["cp_have", "5", "x", "2026-10-01"],
                                   ["a", "b", "c", "d"], ["e", "f", "g", "h"]])
        R.write_state(FakeSheet({"state": ws}), 101, VIL, T1)
        self.assertEqual(ws.rows[0], H)
        self.assertEqual([r[0] for r in ws.rows[1:] if r[0]], ["queue_slots", "cap_wood"])

    def test_write_failure_propagates_and_nothing_cleared_first(self):
        sh = FakeSheet()
        R.write_state(sh, 101, VIL, T1)
        ws = sh.tabs["state"]
        ws.fail_on = {"update": RuntimeError("x")}
        with self.assertRaises(RuntimeError):
            R.write_state(sh, 202, VIL, T2)
        self.assertNotIn("clear", ws.calls)
        self.assertEqual(ws.rows[1][0], "queue_slots")

    def test_note_redacted(self):
        sh = FakeSheet()
        R.write_state(sh, 1, [("queue_slots", 1, "token=abcdef123456")], T1)
        self.assertNotIn("abcdef123456", sh.tabs["state"].rows[1][2])


if __name__ == "__main__":
    unittest.main()
