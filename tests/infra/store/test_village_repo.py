import unittest

from travian_bot.infra.store import village_repo as V
from .fakes import FakeSheet, FakeWS, patch_gspread

_p = patch_gspread()


def setUpModule():
    _p.start()


def tearDownModule():
    _p.stop()


H = list(V.VILLAGES_HEADER)


def sheet(rows):
    ws = FakeWS("Villages", rows=rows)
    return FakeSheet({"Villages": ws}), ws


class TestLoad(unittest.TestCase):
    def test_no_tab_is_single_village_mode(self):
        self.assertEqual(V.load_villages(FakeSheet()), [])

    def test_empty_or_header_only(self):
        self.assertEqual(V.load_villages(sheet([])[0]), [])
        self.assertEqual(V.load_villages(sheet([H])[0]), [])

    def test_rows_with_blank_defaults(self):
        sh, _ = sheet([H, ["101", "主村", "", "", "", "", "res:9", "", "dry", "", "", ""], ["", "", ""],
                       ["102", "二村", "FALSE", "capital", "TRUE", "2", "", "live", "", "", "50", "首都"]])
        a, b = V.load_villages(sh)
        self.assertEqual((a.did, a.enabled, a.role, a.is_capital, a.queue_slots, a.priority),
                         (101, True, "resource", False, 1, 100))
        self.assertEqual((a.build_order, a.guard_mode, a.hide_mode), ("res:9", "dry", None))
        self.assertEqual((b.did, b.enabled, b.is_capital, b.queue_slots, b.priority, b.note),
                         (102, False, True, 2, 50, "首都"))

    def test_bad_cell_names_row_and_field_but_not_value(self):
        sh, _ = sheet([H, ["101", "A", "yes-SECRET", "", "", "", "", "", "", "", "", ""]])
        with self.assertRaises(V.VillageTableError) as cm:
            V.load_villages(sh)
        self.assertIn("第 2 列", str(cm.exception))
        self.assertNotIn("SECRET", str(cm.exception))

    def test_table_rules_duplicate_did_and_two_capitals(self):
        dup, _ = sheet([H, ["1", "A", "", "", "", "", "", "", "", "", "", ""], ["1", "B", "", "", "", "", "", "", "", "", "", ""]])
        with self.assertRaises(V.VillageTableError):
            V.load_villages(dup)
        two, _ = sheet([H, ["1", "A", "", "capital", "TRUE", "", "", "", "", "", "", ""],
                        ["2", "B", "", "capital", "TRUE", "", "", "", "", "", "", ""]])
        with self.assertRaises(V.VillageTableError):
            V.load_villages(two)

    def test_wrong_header_is_error_and_nothing_written(self):
        sh, ws = sheet([["did", "name"], ["1", "A"]])
        with self.assertRaises(V.VillageTableError):
            V.load_villages(sh)
        self.assertEqual(ws.n_calls("update") + ws.n_calls("append_rows"), 0)

    def test_header_with_extra_trailing_column_is_accepted(self):
        sh, _ = sheet([H + ["extra"], ["1", "A", "", "", "", "", "", "", "", "", "", "", "x"]])
        self.assertEqual(len(V.load_villages(sh)), 1)


class TestSetEnabled(unittest.TestCase):
    def rows(self):
        return [H, ["1", "A", "TRUE", "resource", "FALSE", "1", "", "", "", "", "100", ""],
                ["2", "B", "TRUE", "resource", "FALSE", "1", "", "", "", "", "100", "舊備註"]]

    def test_only_target_row_changes(self):
        sh, ws = sheet(self.rows())
        self.assertTrue(V.set_enabled(sh, 2, False))
        self.assertEqual([r[2] for r in ws.rows[1:]], ["TRUE", "FALSE"])
        self.assertEqual(ws.rows[2][11], "舊備註")             # 沒給 note 不動
        self.assertEqual(ws.last_update, ("C3", [["FALSE"]], "RAW"))

    def test_note_goes_first_redacted_and_clipped(self):
        sh, ws = sheet(self.rows())
        V.set_enabled(sh, 2, False, note="token=abcdef123456 " + "字" * 400)
        note = ws.rows[2][11]
        self.assertNotIn("abcdef123456", note)
        self.assertLessEqual(len(note), V.NOTE_MAX)
        self.assertTrue(note.startswith("token=[REDACTED]"))

    def test_unknown_did_or_no_tab_returns_false(self):
        sh, ws = sheet(self.rows())
        self.assertFalse(V.set_enabled(sh, 9, False))
        self.assertEqual(ws.n_calls("update"), 0)
        self.assertFalse(V.set_enabled(FakeSheet(), 1, False))

    def test_enable_true_and_validation(self):
        sh, ws = sheet(self.rows())
        ws.rows[1][2] = "FALSE"
        V.set_enabled(sh, 1, True)
        self.assertEqual(ws.rows[1][2], "TRUE")
        for args in ((0, True), (True, True), (1, "x")):
            with self.assertRaises(ValueError):
                V.set_enabled(sh, *args)

    def test_wrong_header_is_error(self):
        sh, _ = sheet([["a", "b"], ["1", "x"]])
        with self.assertRaises(V.VillageTableError):
            V.set_enabled(sh, 1, False)


if __name__ == "__main__":
    unittest.main()
