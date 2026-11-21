"""tests/common/test_serialize.py — cm-10（v0.1，A1a-1）"""
import json
import unittest
from datetime import datetime, timedelta, timezone

from travian_bot.common import serialize as S


class UtcTest(unittest.TestCase):
    def test_to_utc_str_converts_and_truncates(self):
        tz = timezone(timedelta(hours=8))
        dt = datetime(2026, 11, 2, 16, 15, 30, 999999, tzinfo=tz)
        self.assertEqual(S.to_utc_str(dt), "2026-11-02T08:15:30Z")

    def test_naive_rejected(self):
        with self.assertRaises(S.SerializeError):
            S.to_utc_str(datetime(2026, 11, 2, 8, 15, 30))

    def test_parse_roundtrip(self):
        s = "2026-11-02T08:15:30Z"
        dt = S.parse_utc(s)
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(S.to_utc_str(dt), s)
        self.assertEqual(S.parse_utc("  " + s + " "), dt)

    def test_parse_rejects_bad(self):
        for bad in ("2026-11-02 08:15:30", "2026-11-02T08:15:30", "2026-11-02T08:15:30+00:00",
                    "2026-13-02T08:15:30Z", "2026-02-30T08:15:30Z", "", None, 123):
            with self.assertRaises(S.SerializeError, msg=repr(bad)):
                S.parse_utc(bad)


class JsonTest(unittest.TestCase):
    def test_dumps_stable(self):
        text = S.dumps_stable({"b": 1, "a": "中文", "schema_version": 1})
        self.assertEqual(text, '{\n  "a": "中文",\n  "b": 1,\n  "schema_version": 1\n}\n')
        self.assertTrue(text.endswith("\n") and "\r" not in text and not text.startswith("﻿"))

    def test_dumps_stable_deterministic(self):
        self.assertEqual(S.dumps_stable({"x": 1, "y": 2}), S.dumps_stable({"y": 2, "x": 1}))

    def test_nan_rejected(self):
        with self.assertRaises(S.SerializeError):
            S.dumps_stable({"a": float("nan")})
        with self.assertRaises(S.SerializeError):
            S.dumps_compact({"a": object()})

    def test_dumps_compact(self):
        self.assertEqual(S.dumps_compact({"b": [1, 2], "a": None}), '{"a":null,"b":[1,2]}')
        with self.assertRaises(S.SerializeError):
            S.dumps_compact(["x" * 50], max_chars=10)

    def test_loads_checked_ok_and_bom(self):
        data = S.loads_checked('﻿{"schema_version": 1, "k": 2}', "X")
        self.assertEqual(data["k"], 2)

    def test_loads_checked_rejects(self):
        bad = ['not json', '[1]', '{}', '{"schema_version": "1"}', '{"schema_version": true}',
               '{"schema_version": 0}', '{"schema_version": 2}']
        for text in bad:
            with self.assertRaises(S.SerializeError, msg=text):
                S.loads_checked(text, "X")

    def test_loads_checked_newer_allowed_when_max_raised(self):
        self.assertEqual(S.loads_checked('{"schema_version": 2}', "X", max_version=2)["schema_version"], 2)

    def test_loads_checked_validator(self):
        ok = S.loads_checked('{"schema_version": 1}', "X", validator=lambda n, d: [])
        self.assertEqual(ok["schema_version"], 1)
        with self.assertRaises(S.SerializeError):
            S.loads_checked('{"schema_version": 1}', "X", validator=lambda n, d: ["bad field"])


class ResourceTest(unittest.TestCase):
    def test_cells_roundtrip(self):
        self.assertEqual(S.res_to_cells([1, 2, 3, 4]), [1, 2, 3, 4])
        d = S.res_to_cells([1, 2, 3, 4], "stock")
        self.assertEqual(list(d), ["stock_wood", "stock_clay", "stock_iron", "stock_crop"])
        self.assertEqual(S.cells_to_res(d, "stock"), [1, 2, 3, 4])
        self.assertEqual(S.cells_to_res(["1", 2.0, 3, "4"]), [1, 2, 3, 4])

    def test_bad_resources(self):
        for bad in ([1, 2, 3], [1, 2, 3, 4, 5], [1, 2, 3, 1.5], [1, 2, 3, True], "1234", None):
            with self.assertRaises(S.SerializeError, msg=repr(bad)):
                S.res_to_cells(bad)
        with self.assertRaises(S.SerializeError):
            S.cells_to_res(["1", "", "3", "4"])
        with self.assertRaises(S.SerializeError):
            S.cells_to_res({"stock_wood": 1}, "stock")

    def test_cost_str(self):
        self.assertEqual(S.res_to_cost_str([1, 2, 3, 4]), "1,2,3,4")
        self.assertEqual(S.cost_str_to_res("1,2,3,4"), [1, 2, 3, 4])
        for bad in ("1,2,3", "1, 2, 3, 4", "a,b,c,d", "1,2,3,-4"):
            with self.assertRaises(S.SerializeError, msg=bad):
                S.cost_str_to_res(bad)
        with self.assertRaises(S.SerializeError):
            S.res_to_cost_str([1, -2, 3, 4])


class CellTest(unittest.TestCase):
    def test_to_cell_basic(self):
        self.assertEqual(S.to_cell(12, "int"), 12)
        self.assertEqual(S.to_cell(True, "bool"), "TRUE")
        self.assertEqual(S.to_cell(False, "bool"), "FALSE")
        self.assertEqual(S.to_cell(None, "int"), "")
        self.assertEqual(S.to_cell(2.5, "float"), 2.5)
        self.assertEqual(S.to_cell({"b": 1, "a": 2}, "json"), '{"a":2,"b":1}')
        self.assertEqual(S.to_cell("2026-11-02T08:15:30Z", "utc"), "2026-11-02T08:15:30Z")
        dt = datetime(2026, 11, 2, 8, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(S.to_cell(dt, "utc"), "2026-11-02T08:15:30Z")

    def test_to_cell_strict(self):
        for value, typ in ((True, "int"), (1.5, "int"), ("1", "int"), (1, "bool"), ("x", "float"),
                           (float("nan"), "float"), (5, "str"), ("2026-11-02", "utc")):
            with self.assertRaises(S.SerializeError, msg=f"{value!r}/{typ}"):
                S.to_cell(value, typ)

    def test_str_newline_and_truncate(self):
        self.assertEqual(S.to_cell("a\nb\r\nc", "str"), "a b c")
        out = S.to_cell("x" * 20, "str", max_len=10)
        self.assertEqual(len(out), 10)
        self.assertTrue(out.endswith(S.TRUNC_MARK))
        self.assertEqual(S.to_cell("short", "str", max_len=10), "short")

    def test_from_cell_blank(self):
        for blank in (None, "", "   "):
            for typ in ("int", "float", "bool", "utc", "json"):
                self.assertIsNone(S.from_cell(blank, typ))
            self.assertIsNone(S.from_cell(blank, "str"))
            self.assertEqual(S.from_cell(blank, "str", nullable=False), "")

    def test_from_cell_values(self):
        self.assertEqual(S.from_cell(" 12 ", "int"), 12)
        self.assertEqual(S.from_cell(12.0, "int"), 12)
        self.assertEqual(S.from_cell("-3", "int"), -3)
        self.assertEqual(S.from_cell("2.5", "float"), 2.5)
        self.assertEqual(S.from_cell(" abc ", "str"), "abc")
        self.assertEqual(S.from_cell(123, "str"), "123")
        self.assertEqual(S.from_cell('{"a":1}', "json"), {"a": 1})
        self.assertEqual(S.from_cell("2026-11-02T08:15:30Z", "utc"), "2026-11-02T08:15:30Z")

    def test_from_cell_bool(self):
        for t in ("TRUE", "true", "1", True, 1):
            self.assertIs(S.from_cell(t, "bool"), True, t)
        for f in ("FALSE", "false", "0", False, 0):
            self.assertIs(S.from_cell(f, "bool"), False, f)
        for bad in ("yes", "True", "2", 2):
            with self.assertRaises(S.SerializeError, msg=repr(bad)):
                S.from_cell(bad, "bool")

    def test_from_cell_int_strict(self):
        for bad in ("1,000", "1.5", "1.0", 1.5, "abc", True):
            with self.assertRaises(S.SerializeError, msg=repr(bad)):
                S.from_cell(bad, "int")

    def test_roundtrip(self):
        cases = [(5, "int"), (True, "bool"), (False, "bool"), (2.5, "float"), ("文字", "str"),
                 ("2026-11-02T08:15:30Z", "utc"), ({"k": [1, 2]}, "json")]
        for value, typ in cases:
            self.assertEqual(S.from_cell(S.to_cell(value, typ), typ), value, typ)
        for typ in ("int", "bool", "float", "utc", "json", "str"):
            self.assertIsNone(S.from_cell(S.to_cell(None, typ), typ), typ)

    def test_unknown_type(self):
        with self.assertRaises(S.SerializeError):
            S.to_cell(1, "decimal")
        with self.assertRaises(S.SerializeError):
            S.from_cell(1, "decimal")


class RedactTest(unittest.TestCase):
    def assertGone(self, text, secret):
        out = S.redact(text)
        self.assertNotIn(secret, out, out)
        self.assertEqual(S.redact(out), out, "redact 必須冪等")

    def test_cookie_header(self):
        self.assertGone("GET / Cookie: T3E=abcdef123456; lowRes=0", "abcdef123456")
        self.assertGone("Set-Cookie: sess=TOPSECRET99; Path=/", "TOPSECRET99")

    def test_raw_cookie_string(self):
        self.assertGone("seed=T3E=abcdef123456; lowRes=zzzzzzzz9", "abcdef123456")

    def test_key_value_and_json(self):
        self.assertGone("password=hunter2hunter2", "hunter2")
        self.assertGone('{"token": "tok_ABCDEFG123"}', "tok_ABCDEFG123")
        self.assertGone('{"name": "T3E", "value": "cookieval12345"}', "cookieval12345")
        self.assertGone("TRAVIAN_SEED_COOKIE=abc123def456", "abc123def456")

    def test_bearer_and_jwt(self):
        self.assertGone("Authorization: Bearer abcdefghijklmnop", "abcdefghijklmnop")
        self.assertGone("id eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig_abc", "eyJzdWIi")

    def test_private_key(self):
        pem = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg\n-----END PRIVATE KEY-----"
        self.assertGone("k=" + pem, "MIIEvQIBADANBg")

    def test_ordinary_text_untouched(self):
        for text in ("升級 伐木場 3 級 成本 100,80,60,40", "dorf1.php?newdid=5", "2026-11-02T08:15:30Z INFO build 101 ok"):
            self.assertEqual(S.redact(text), text)

    def test_non_str(self):
        self.assertEqual(S.redact(None), "None")
        self.assertEqual(S.redact(123), "123")


class JsonRoundtripTest(unittest.TestCase):
    def test_file_roundtrip(self):
        obj = {"schema_version": 1, "cookies": [], "saved_utc": "2026-11-02T08:15:30Z", "名稱": "值"}
        self.assertEqual(S.loads_checked(S.dumps_stable(obj), "state"), obj)
        self.assertEqual(json.loads(S.dumps_stable(obj)), obj)


if __name__ == "__main__":
    unittest.main()
