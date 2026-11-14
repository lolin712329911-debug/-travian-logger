import sys
import types
import unittest
from unittest import mock

from travian_bot.infra.store import gsheets as G


class FakeAPIError(Exception):
    def __init__(self, code):
        super().__init__("api error")
        self.code = code


class FakeWS:
    def __init__(self, errors=()):
        self.errors, self.calls = list(errors), []

    def _maybe(self):
        if self.errors:
            e = self.errors.pop(0)
            if e is not None:
                raise e

    def append_rows(self, data, value_input_option=None):
        self.calls.append(("append", data, value_input_option))
        self._maybe()

    def update(self, range_name=None, values=None, value_input_option=None):
        self.calls.append(("update", range_name, values, value_input_option))
        self._maybe()


class TestBatchWrite(unittest.TestCase):
    def test_append_single_request_raw_by_default(self):
        ws = FakeWS()
        n = G.batch_write(ws, [["a", 1], ("b", 2.5)])
        self.assertEqual(n, 2)
        self.assertEqual(ws.calls, [("append", [["a", 1], ["b", 2.5]], "RAW")])

    def test_update_with_start(self):
        ws = FakeWS()
        G.batch_write(ws, [["x"]], start="B7", value_input="USER_ENTERED")
        self.assertEqual(ws.calls, [("update", "B7", [["x"]], "USER_ENTERED")])

    def test_empty_rows_no_call(self):
        ws = FakeWS()
        self.assertEqual(G.batch_write(ws, []), 0)
        self.assertEqual(ws.calls, [])

    def test_quota_retried_then_ok(self):
        ws, slept = FakeWS([FakeAPIError(429), FakeAPIError(429), None]), []
        n = G.batch_write(ws, [["a"]], sleep=slept.append)
        self.assertEqual(n, 1)
        self.assertEqual(len(ws.calls), 3)
        self.assertEqual(slept, [10.0, 30.0])

    def test_quota_retries_exhausted_raises(self):
        ws = FakeWS([FakeAPIError(429)] * 10)
        with self.assertRaises(FakeAPIError):
            G.batch_write(ws, [["a"]], backoff_s=(1, 2), sleep=lambda s: None)
        self.assertEqual(len(ws.calls), 3)             # 1 次 + 2 次重試

    def test_other_errors_not_resent(self):
        for err in (FakeAPIError(500), FakeAPIError(403), ConnectionError("x"), RuntimeError("y")):
            ws = FakeWS([err, None])
            with self.assertRaises(type(err)):
                G.batch_write(ws, [["a"]], sleep=lambda s: None)
            self.assertEqual(len(ws.calls), 1, repr(err))     # 可能已寫入，不重送

    def test_response_status_code_fallback(self):
        e = RuntimeError("x")
        e.response = types.SimpleNamespace(status_code=429)
        ws = FakeWS([e, None])
        G.batch_write(ws, [["a"]], sleep=lambda s: None)
        self.assertEqual(len(ws.calls), 2)

    def test_validation(self):
        ws = FakeWS()
        for kw in ({"value_input": "raw"}, {"start": "5A"}, {"start": "a1"}, {"start": ""}, {"start": 3}):
            with self.assertRaises(ValueError):
                G.batch_write(ws, [["a"]], **kw)
        for bad in ([[None]], [[True]], [[{"a": 1}]], [[b"x"]], [[["x"]]]):
            with self.assertRaises(ValueError):
                G.batch_write(ws, bad)
        self.assertEqual(ws.calls, [])


class TestConfigured(unittest.TestCase):
    def test_is_configured(self):
        self.assertTrue(G.is_configured("{}", "abc"))
        for a, b in ((None, "x"), ("{}", None), ("", "x"), ("{}", " "), (1, "x")):
            self.assertFalse(G.is_configured(a, b))

    def test_open_sheet(self):
        client = mock.Mock()
        G.open_sheet(client, " sid ")
        client.open_by_key.assert_called_once_with("sid")
        for bad in (None, "", "  "):
            with self.assertRaises(RuntimeError):
                G.open_sheet(client, bad)


class TestCredentialsAndWorksheet(unittest.TestCase):
    def _fake_modules(self):
        gspread = types.ModuleType("gspread")
        gspread.authorize = mock.Mock(return_value="CLIENT")
        exc = types.ModuleType("gspread.exceptions")

        class WorksheetNotFound(Exception):
            pass
        exc.WorksheetNotFound = WorksheetNotFound
        gspread.exceptions = exc
        google = types.ModuleType("google")
        oauth2 = types.ModuleType("google.oauth2")
        sa = types.ModuleType("google.oauth2.service_account")
        sa.Credentials = mock.Mock()
        sa.Credentials.from_service_account_info = mock.Mock(return_value="CREDS")
        return {"gspread": gspread, "gspread.exceptions": exc, "google": google,
                "google.oauth2": oauth2, "google.oauth2.service_account": sa}, gspread, sa, WorksheetNotFound

    def test_get_credentials(self):
        mods, gspread, sa, _ = self._fake_modules()
        with mock.patch.dict(sys.modules, mods):
            self.assertEqual(G.get_credentials('{"client_email": "a@b"}'), "CLIENT")
        sa.Credentials.from_service_account_info.assert_called_once_with(
            {"client_email": "a@b"}, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        gspread.authorize.assert_called_once_with("CREDS")

    def test_get_credentials_bad_input_message_has_no_content(self):
        for bad in (None, "", "  ", "not json SECRETXYZ", "[1]", "123"):
            with self.assertRaises(RuntimeError) as cm:
                G.get_credentials(bad)
            self.assertNotIn("SECRETXYZ", str(cm.exception))

    def test_has_worksheet(self):
        mods, _, _, NotFound = self._fake_modules()
        sh = mock.Mock()
        with mock.patch.dict(sys.modules, mods):
            self.assertTrue(G.has_worksheet(sh, "Config"))
            sh.worksheet.side_effect = NotFound()
            self.assertFalse(G.has_worksheet(sh, "Nope"))
            sh.worksheet.side_effect = PermissionError("x")      # 其他錯誤不當成「沒有」
            with self.assertRaises(PermissionError):
                G.has_worksheet(sh, "Config")

    def test_gspread_not_imported_at_module_import(self):
        # 模組最上層不得 import gspread／google（CI 的 import 步驟沒裝）
        import ast
        tree = ast.parse(open(G.__file__, encoding="utf-8").read())
        top = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                top += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                top.append(node.module or "")
        self.assertFalse([m for m in top if m.split(".")[0] in ("gspread", "google")], top)


class TestWorksheetHelpers(unittest.TestCase):
    """v0.2（A4b-1）追加：get_worksheet／ensure_worksheet。"""

    def _mods(self):
        exc = types.ModuleType("gspread.exceptions")

        class WorksheetNotFound(Exception):
            pass
        exc.WorksheetNotFound = WorksheetNotFound
        g = types.ModuleType("gspread")
        g.exceptions = exc
        return {"gspread": g, "gspread.exceptions": exc}, WorksheetNotFound

    def test_get_worksheet_found_missing_and_other_errors(self):
        mods, NotFound = self._mods()
        sh = mock.Mock()
        sh.worksheet.return_value = "WS"
        with mock.patch.dict(sys.modules, mods):
            self.assertEqual(G.get_worksheet(sh, "Config"), "WS")
            sh.worksheet.side_effect = NotFound()
            self.assertIsNone(G.get_worksheet(sh, "Nope"))
            sh.worksheet.side_effect = PermissionError("x")
            with self.assertRaises(PermissionError):
                G.get_worksheet(sh, "Config")
            self.assertEqual(sh.worksheet.call_count, 3)          # 每次只有一次請求

    def test_ensure_worksheet_existing_and_created(self):
        mods, NotFound = self._mods()
        sh = mock.Mock()
        sh.worksheet.return_value = "WS"
        with mock.patch.dict(sys.modules, mods):
            self.assertEqual(G.ensure_worksheet(sh, "A"), ("WS", False))
            sh.add_worksheet.assert_not_called()
            sh.worksheet.side_effect = NotFound()
            sh.add_worksheet.return_value = "NEW"
            self.assertEqual(G.ensure_worksheet(sh, "B", rows=5, cols=3), ("NEW", True))
            sh.add_worksheet.assert_called_once_with(title="B", rows=5, cols=3)


if __name__ == "__main__":
    unittest.main()
