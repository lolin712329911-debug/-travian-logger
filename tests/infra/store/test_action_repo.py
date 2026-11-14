import unittest
from datetime import datetime, timezone

from travian_bot.common.models import ActionRow, ValidationError
from travian_bot.infra.store import action_repo as R
from .fakes import FakeSheet, FakeWS, patch_gspread

_p = patch_gspread()


def setUpModule():
    _p.start()


def tearDownModule():
    _p.stop()


H = list(R.ACTIONS_HEADER)
NOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)


def row(**kw):
    d = dict(ts_utc="2026-11-14T08:15:30Z", action="upgrade", aid=3, gid=1, level=4, cost="10,20,30,40",
             mode="live", result="ok", detail="", did=101)
    d.update(kw)
    return ActionRow(**d)


class TestLog(unittest.TestCase):
    def test_new_tab_gets_header_then_one_append_raw(self):
        sh = FakeSheet()
        n = R.log_actions(sh, [row(), row(aid=None, gid=None, level=None, cost=None, mode="dry", result="dry")])
        ws = sh.tabs["Actions"]
        self.assertEqual(n, 2)
        self.assertEqual(ws.rows[0], H)
        self.assertEqual(ws.rows[1], ["2026-11-14T08:15:30Z", "upgrade", "3", "1", "4", "10,20,30,40", "live", "ok", "", "101"])
        self.assertEqual(ws.rows[2][2:6], ["", "", "", ""])         # 空值留空，不寫 0
        self.assertEqual(ws.n_calls("append_rows"), 1)
        self.assertEqual(ws.last_append[1], "RAW")

    def test_existing_header_ok_appends_only(self):
        ws = FakeWS("Actions", rows=[H])
        R.log_action(FakeSheet({"Actions": ws}), row())
        self.assertEqual(ws.n_calls("update"), 0)
        self.assertEqual(len(ws.rows), 2)

    def test_empty_list_touches_nothing(self):
        sh = FakeSheet()
        self.assertEqual(R.log_actions(sh, []), 0)
        self.assertEqual(sh.worksheet_calls, 0)

    def test_wrong_header_raises_and_does_not_modify(self):
        ws = FakeWS("Actions", rows=[["時間(UTC)", "動作", "slot"]])
        with self.assertRaises(ValueError):
            R.log_action(FakeSheet({"Actions": ws}), row())
        self.assertEqual(ws.rows, [["時間(UTC)", "動作", "slot"]])

    def test_one_invalid_row_means_nothing_written_not_even_the_tab(self):
        sh = FakeSheet()
        with self.assertRaises(ValidationError):
            R.log_actions(sh, [row(), row(mode="dry", result="ok")])   # C5：dry 的 result 不可為 ok
        self.assertEqual(sh.tabs, {})

    def test_detail_redacted_and_clipped(self):
        sh = FakeSheet()
        R.log_action(sh, row(detail="Cookie: abc123456789; x=yyyyyyyy " + "字" * 400))
        d = sh.tabs["Actions"].rows[1][8]
        self.assertNotIn("abc123456789", d)
        self.assertLessEqual(len(d), R.DETAIL_MAX)

    def test_non_action_row_rejected(self):
        with self.assertRaises(TypeError):
            R.log_actions(FakeSheet(), [["a"]])

    def test_write_error_propagates(self):
        ws = FakeWS("Actions", rows=[H], fail_on={"append_rows": RuntimeError("x")})
        with self.assertRaises(RuntimeError):
            R.log_action(FakeSheet({"Actions": ws}), row())


class TestLastAge(unittest.TestCase):
    def sheet(self, extra):
        rows = [H] + extra
        return FakeSheet({"Actions": FakeWS("Actions", rows=rows)})

    def mk(self, ts, action="boost", result="ok", did="101"):
        return [ts, action, "", "", "", "", "live", result, "", did]

    def test_latest_match_age_in_hours(self):
        sh = self.sheet([self.mk("2026-11-14T06:00:00Z"), self.mk("2026-11-14T09:30:00Z"),
                         self.mk("2026-11-14T11:00:00Z", result="skipped")])
        self.assertAlmostEqual(R.last_action_age_hours(sh, "boost", now=NOW), 2.5)

    def test_one_request_only(self):
        sh = self.sheet([self.mk("2026-11-14T09:30:00Z")])
        R.last_action_age_hours(sh, "boost", now=NOW)
        ws = sh.tabs["Actions"]
        self.assertEqual((ws.n_calls("batch_get"), ws.n_calls("get_all_values")), (1, 0))

    def test_did_filter(self):
        sh = self.sheet([self.mk("2026-11-14T06:00:00Z", did="101"), self.mk("2026-11-14T11:00:00Z", did="202")])
        self.assertAlmostEqual(R.last_action_age_hours(sh, "boost", 101, now=NOW), 6.0)
        self.assertAlmostEqual(R.last_action_age_hours(sh, "boost", None, now=NOW), 1.0)
        self.assertIsNone(R.last_action_age_hours(sh, "boost", 303, now=NOW))

    def test_none_when_no_such_row_or_no_tab(self):
        self.assertIsNone(R.last_action_age_hours(self.sheet([self.mk("2026-11-14T06:00:00Z", action="x")]), "boost", now=NOW))
        self.assertIsNone(R.last_action_age_hours(FakeSheet(), "boost", now=NOW))

    def test_other_result_value(self):
        sh = self.sheet([self.mk("2026-11-14T06:00:00Z", result="dry")])
        self.assertIsNone(R.last_action_age_hours(sh, "boost", now=NOW))
        self.assertAlmostEqual(R.last_action_age_hours(sh, "boost", result="dry", now=NOW), 6.0)

    def test_unparseable_time_is_conservative_zero_with_warning(self):
        sh = self.sheet([self.mk("11/14/2026 06:00:00")])
        msgs = []
        self.assertEqual(R.last_action_age_hours(sh, "boost", now=NOW, warn=msgs.append), 0.0)
        self.assertEqual(len(msgs), 1)

    def test_read_failure_is_conservative_zero_with_warning(self):
        ws = FakeWS("Actions", rows=[H], fail_on={"batch_get": RuntimeError("SECRETXYZ")})
        msgs = []
        self.assertEqual(R.last_action_age_hours(FakeSheet({"Actions": ws}), "boost", now=NOW, warn=msgs.append), 0.0)
        self.assertEqual(len(msgs), 1)
        self.assertNotIn("SECRETXYZ", msgs[0])

    def test_future_timestamp_is_not_negative(self):
        sh = self.sheet([self.mk("2026-11-14T13:00:00Z")])
        self.assertEqual(R.last_action_age_hours(sh, "boost", now=NOW), 0.0)

    def test_header_row_never_matches(self):
        sh = FakeSheet({"Actions": FakeWS("Actions", rows=[H])})
        self.assertIsNone(R.last_action_age_hours(sh, "action", result="result", now=NOW))


if __name__ == "__main__":
    unittest.main()
