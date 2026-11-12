import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from unittest import mock

from travian_bot.infra import notify as N


def _run(*a, **k):
    buf = io.StringIO()
    with mock.patch.object(N, "_clock", return_value=datetime(2026, 11, 12, 8, 5, 3)):
        with redirect_stdout(buf):
            N.notify(*a, **k)
    return buf.getvalue()


class TestNotify(unittest.TestCase):
    def test_info_format_same_as_old(self):
        self.assertEqual(_run("hello"), "[08:05:03] hello\n")      # 舊版：[HH:MM:SS] msg

    def test_warn_error_tags(self):
        self.assertEqual(_run("x", "warn"), "[08:05:03] [WARN] x\n")
        self.assertEqual(_run("x", level="error"), "[08:05:03] [ERROR] x\n")

    def test_unknown_level_rejected(self):
        with self.assertRaises(ValueError):
            _run("x", "debug")

    def test_message_is_redacted(self):
        out = _run("失敗 Cookie: PHPSESSID=abcdef123456; other=zzzzzzzz")
        self.assertNotIn("abcdef123456", out)
        self.assertIn("[REDACTED]", out)

    def test_non_string_message(self):
        self.assertEqual(_run(123), "[08:05:03] 123\n")


if __name__ == "__main__":
    unittest.main()
