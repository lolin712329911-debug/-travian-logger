import unittest

from travian_bot.common import config_schema as CS
from travian_bot.infra.store import config_repo as R
from .fakes import FakeSheet, FakeWS, patch_gspread

_p = patch_gspread()


def setUpModule():
    _p.start()


def tearDownModule():
    _p.stop()


class TestParse(unittest.TestCase):
    def test_keys_lowercased_header_skipped_last_wins(self):
        vals = [["key", "value", "note"], [" Enabled ", " TRUE ", "x"], ["", "orphan"], ["build_order"], ["enabled", "FALSE"]]
        self.assertEqual(R.parse_rows(vals), {"enabled": "FALSE", "build_order": ""})

    def test_missing_rows_follow_schema_order_and_cells(self):
        rows = R.missing_rows({"enabled"})
        self.assertEqual([r[0] for r in rows], [k for k in CS.ORDER if k != "enabled"])
        by = {r[0]: r for r in rows}
        self.assertEqual(by["schema_version"][1], 1)
        self.assertEqual(by["hero_skip_on_incoming"][1], "TRUE")
        self.assertEqual(by["server_id"][1], "")                 # 必填鍵沒有預設：空白，不編造
        self.assertEqual(by["hero_focus_min_hours"][1], 1.0)
        self.assertTrue(all(isinstance(r[2], str) and "\n" not in r[2] for r in rows))


class TestLoad(unittest.TestCase):
    def test_missing_tab_is_created_with_header_and_all_keys(self):
        sh = FakeSheet()
        raw = R.load_config(sh)
        ws = sh.tabs["Config"]
        self.assertEqual(ws.rows[0], ["key", "value", "note"])
        self.assertEqual(len(ws.rows), 1 + len(CS.ORDER))
        self.assertEqual(ws.last_update[0], "A1")
        self.assertEqual(ws.last_update[2], "RAW")
        self.assertEqual(raw["enabled"], "TRUE")
        self.assertEqual(raw["schema_version"], "1")
        self.assertEqual(set(raw), set(CS.ORDER))

    def test_existing_values_untouched_only_missing_appended_no_header_added(self):
        ws = FakeWS("Config", rows=[["enabled", "FALSE", "mine"], ["build_order", "res:9,26:10"]])
        sh = FakeSheet({"Config": ws})
        raw = R.load_config(sh)
        self.assertEqual(ws.rows[0], ["enabled", "FALSE", "mine"])
        self.assertEqual(ws.rows[1][:2], ["build_order", "res:9,26:10"])
        self.assertEqual(ws.last_update[0], "A3")
        self.assertEqual(len(ws.rows), 2 + len(CS.ORDER) - 2)
        self.assertEqual((raw["enabled"], raw["build_order"]), ("FALSE", "res:9,26:10"))

    def test_nothing_missing_means_no_write(self):
        ws = FakeWS("Config", rows=[[k, "", ""] for k in CS.ORDER])
        R.load_config(FakeSheet({"Config": ws}))
        self.assertEqual(ws.n_calls("update"), 0)
        self.assertEqual(ws.n_calls("append_rows"), 0)

    def test_ensure_false_does_not_write(self):
        sh = FakeSheet({"Config": FakeWS("Config", rows=[["enabled", "TRUE"]])})
        R.load_config(sh, ensure=False)
        self.assertEqual(sh.tabs["Config"].n_calls("update"), 0)

    def test_grows_sheet_when_short(self):
        ws = FakeWS("Config", rows=[["enabled", "TRUE"]], row_count=5, col_count=2)
        R.load_config(FakeSheet({"Config": ws}))
        self.assertGreaterEqual(ws.row_count, 1 + len(CS.ORDER) - 1)
        self.assertGreaterEqual(ws.col_count, 3)

    def test_write_failure_propagates(self):
        ws = FakeWS("Config", rows=[["enabled", "TRUE"]], fail_on={"update": RuntimeError("boom")})
        with self.assertRaises(RuntimeError):
            R.load_config(FakeSheet({"Config": ws}))

    def test_normalized_reports_required_keys_empty(self):
        cfg, problems = R.load_normalized(FakeSheet())
        errs = {p.key for p in problems if p.severity == "error"}
        self.assertTrue({"server_id", "server_base_url", "server_tz", "server_start_utc"} <= errs)
        self.assertIs(cfg["enabled"], True)


class TestDisable(unittest.TestCase):
    def _sheet(self, rows):
        ws = FakeWS("Config", rows=rows)
        return FakeSheet({"Config": ws}), ws

    def test_account_sets_false_and_note_keeps_other_cells(self):
        sh, ws = self._sheet([["target_level", "10", "n"], ["enabled", "TRUE", "old note"]])
        self.assertTrue(R.disable(sh, "account", None, "session 失效"))
        self.assertEqual(ws.rows[1][:2], ["enabled", "FALSE"])
        self.assertIn("自動停用：session 失效", ws.rows[1][2])
        self.assertEqual(ws.rows[0], ["target_level", "10", "n"])
        self.assertEqual(ws.last_update[0], "B2")

    def test_account_reason_is_redacted_and_clipped(self):
        sh, ws = self._sheet([["enabled", "TRUE"]])
        R.disable(sh, "account", None, "Cookie: abc123456789; sid=zzzzzzzz " + "字" * 500)
        self.assertNotIn("abc123456789", ws.rows[0][2])
        self.assertLessEqual(len(ws.rows[0][2]), R.NOTE_MAX)

    def test_account_missing_row_is_appended(self):
        sh, ws = self._sheet([["target_level", "10"]])
        R.disable(sh, "account", None, "x")
        self.assertEqual(ws.rows[1][:2], ["enabled", "FALSE"])

    def test_account_missing_tab_creates_it(self):
        sh = FakeSheet()
        R.disable(sh, "account", None, "x")
        ws = sh.tabs["Config"]
        self.assertEqual(ws.rows[0], ["key", "value", "note"])
        self.assertEqual(ws.rows[1][:2], ["enabled", "FALSE"])

    def test_village_scope_without_villages_tab_returns_false_and_does_not_touch_config(self):
        sh, ws = self._sheet([["enabled", "TRUE"]])
        self.assertFalse(R.disable(sh, "village", 7, "x"))
        self.assertEqual(ws.rows[0][:2], ["enabled", "TRUE"])
        self.assertEqual(ws.n_calls("update"), 0)

    def test_village_scope_disables_only_that_village(self):
        from travian_bot.infra.store import village_repo as V
        vil = FakeWS("Villages", rows=[list(V.VILLAGES_HEADER),
                                       ["1", "A", "TRUE", "resource", "FALSE", "1", "", "", "", "", "100", ""],
                                       ["2", "B", "TRUE", "resource", "FALSE", "1", "", "", "", "", "100", "mine"]])
        cfg = FakeWS("Config", rows=[["enabled", "TRUE"]])
        sh = FakeSheet({"Villages": vil, "Config": cfg})
        self.assertTrue(R.disable(sh, "village", 2, "掉線"))
        self.assertEqual([r[2] for r in vil.rows[1:]], ["TRUE", "FALSE"])
        self.assertTrue(vil.rows[2][11].startswith("掉線"))
        self.assertIn("mine", vil.rows[2][11])
        self.assertEqual(cfg.rows[0][:2], ["enabled", "TRUE"])

    def test_bad_arguments(self):
        sh = FakeSheet()
        for args in (("nope", None, "x"), ("account", None, ""), ("account", None, "  "),
                     ("village", None, "x"), ("village", 0, "x"), ("village", True, "x")):
            with self.assertRaises(ValueError, msg=repr(args)):
                R.disable(sh, *args)

    def test_write_failure_is_raised_not_swallowed(self):
        ws = FakeWS("Config", rows=[["enabled", "TRUE"]], fail_on={"update": RuntimeError("x")})
        with self.assertRaises(RuntimeError):
            R.disable(FakeSheet({"Config": ws}), "account", None, "x")


if __name__ == "__main__":
    unittest.main()
