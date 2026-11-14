import unittest

from travian_bot.infra.store import plan_repo as R
from .fakes import FakeSheet, FakeWS, patch_gspread

_p = patch_gspread()


def setUpModule():
    _p.start()


def tearDownModule():
    _p.stop()


def sheet(rows):
    return FakeSheet({"Config": FakeWS("Config", rows=rows)})


class TestLoad(unittest.TestCase):
    def test_reads_config_string(self):
        raw = R.load_build_order(sheet([["enabled", "TRUE"], ["build_order", " res:9,26:10,20:10 "]]), 101)
        self.assertEqual(raw, R.RawBuildOrder("res:9,26:10,20:10", "config"))

    def test_blank_missing_or_no_tab_is_none(self):
        self.assertIsNone(R.load_build_order(sheet([["build_order", "  "]]), 1))
        self.assertIsNone(R.load_build_order(sheet([["enabled", "TRUE"]]), 1))
        self.assertIsNone(R.load_build_order(FakeSheet(), 1))

    def test_does_not_read_the_build_order_tab_or_write_anything(self):
        ws = FakeWS("Config", rows=[["build_order", "res:2"]])
        other = FakeWS("build_order", rows=[["run_id", "key", "level"], ["x", "res", "9"]])
        sh = FakeSheet({"Config": ws, "build_order": other})
        self.assertEqual(R.load_build_order(sh, 1).text, "res:2")
        self.assertEqual(other.calls, [])
        self.assertEqual(ws.n_calls("update") + ws.n_calls("append_rows"), 0)

    def test_every_call_rereads_no_cache(self):
        sh = sheet([["build_order", "res:2"]])
        R.load_build_order(sh, 1)
        sh.tabs["Config"].rows[0][1] = "res:3"
        self.assertEqual(R.load_build_order(sh, 1).text, "res:3")

    def test_raw_config_shortcut_makes_no_sheet_request(self):
        sh = FakeSheet()
        self.assertEqual(R.load_build_order(sh, 1, raw_config={"build_order": "res:2"}).text, "res:2")
        self.assertIsNone(R.load_build_order(sh, 1, raw_config={"build_order": ""}))
        self.assertEqual(sh.worksheet_calls, 0)

    def test_read_error_is_not_none(self):
        ws = FakeWS("Config", rows=[["build_order", "res:2"]], fail_on={"get_all_values": RuntimeError("x")})
        with self.assertRaises(RuntimeError):
            R.load_build_order(FakeSheet({"Config": ws}), 1)

    def test_bad_did(self):
        for d in (0, True, "1", None):
            with self.assertRaises(ValueError):
                R.load_build_order(FakeSheet(), d)


if __name__ == "__main__":
    unittest.main()
