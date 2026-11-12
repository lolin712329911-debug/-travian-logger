import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from travian_bot.infra.session import Session, SessionLost, parse_cookie_header

PROFILE = SimpleNamespace(server_id="s2-test", base_url="https://ts1.example.invalid/")
NOW = datetime(2026, 11, 12, 8, 15, 30, 999999, tzinfo=timezone.utc)
COOKIE_VALUE = "SECRETVALUE123456"


class FakeContext:
    def __init__(self, storage_state=None):
        self.init_state, self.cookies_added, self.closed = storage_state, None, False
        self.pages = 0
        self.state = {"cookies": [{"name": "sid", "value": COOKIE_VALUE, "domain": "ts1.example.invalid",
                                   "path": "/", "expires": -1}],
                      "origins": [{"origin": "https://ts1.example.invalid", "localStorage": []}]}

    def add_cookies(self, c):
        self.cookies_added = c

    def new_page(self):
        self.pages += 1
        return SimpleNamespace(id=self.pages)

    def storage_state(self):
        return self.state

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self):
        self.contexts, self.closed = [], 0

    def new_context(self, storage_state=None):
        c = FakeContext(storage_state)
        self.contexts.append(c)
        return c

    def close(self):
        self.closed += 1


class FakePlaywright:
    def __init__(self):
        self.browser = FakeBrowser()
        self.chromium = SimpleNamespace(launch=self._launch)
        self.launched = 0

    def _launch(self, headless=True):
        self.launched += 1
        assert headless is True
        return self.browser


def cache_text(server_id="s2-test", version=1, cookies=None, **extra):
    d = {"schema_version": version, "saved_utc": "2026-11-01T00:00:00Z", "server_id": server_id,
         "cookies": [{"name": "sid", "value": "old", "domain": "d", "path": "/", "expires": -1}]
         if cookies is None else cookies}
    d.update(extra)
    return json.dumps(d)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "travian_session.json"
        self.logs = []
        self.pw = FakePlaywright()

    def launch(self, seed=None):
        return Session.launch(self.pw, PROFILE, self.path, seed, log=self.logs.append, now_fn=lambda: NOW)


class TestLaunch(Base):
    def test_cache_used_first(self):
        self.path.write_text(cache_text(origins=[{"origin": "o"}]), encoding="utf-8")
        s = self.launch(seed="a=1")
        self.assertTrue(s.used_cache)
        ctx = self.pw.browser.contexts[0]
        self.assertEqual(ctx.init_state["cookies"][0]["value"], "old")
        self.assertEqual(ctx.init_state["origins"], [{"origin": "o"}])
        self.assertIsNone(ctx.cookies_added)
        self.assertIs(s.context, ctx)
        self.assertEqual(s.page.id, 1)

    def test_seed_when_no_cache(self):
        s = self.launch(seed="a=1; b=2")
        self.assertFalse(s.used_cache)
        self.assertEqual(self.pw.browser.contexts[0].cookies_added,
                         [{"name": "a", "value": "1", "url": "https://ts1.example.invalid"},
                          {"name": "b", "value": "2", "url": "https://ts1.example.invalid"}])

    def test_neither_raises_before_browser_launch(self):
        with self.assertRaises(SessionLost):
            self.launch(seed=None)
        with self.assertRaises(SessionLost):
            self.launch(seed="   ")
        self.assertEqual(self.pw.launched, 0)

    def test_bad_seed_closes_browser(self):
        with self.assertRaises(SessionLost):
            self.launch(seed="garbage-without-equals")
        self.assertEqual(self.pw.browser.closed, 1)

    def test_server_id_mismatch_discards_whole_cache(self):
        self.path.write_text(cache_text(server_id="other"), encoding="utf-8")
        s = self.launch(seed="a=1")
        self.assertFalse(s.used_cache)
        self.assertFalse(self.path.exists())
        with self.assertRaises(SessionLost):          # 沒種子就不能退回舊服的 cache
            self.path.write_text(cache_text(server_id="other"), encoding="utf-8")
            self.launch(seed=None)

    def test_bad_cache_variants_ignored(self):
        bad = ["not json", "[]", json.dumps({"server_id": "s2-test", "cookies": []}),
               cache_text(version=2), cache_text(version=True), cache_text(cookies=[]),
               cache_text(cookies=["x"]), cache_text(cookies=[{"name": "a"}]),
               cache_text(origins="no")]
        for text in bad:
            self.path.write_text(text, encoding="utf-8")
            s = self.launch(seed="a=1")
            self.assertFalse(s.used_cache, text)

    def test_logs_never_contain_cookie_values(self):
        self.path.write_text(cache_text(version=9), encoding="utf-8")
        self.launch(seed=f"sid={COOKIE_VALUE}")
        self.assertNotIn(COOKIE_VALUE, "\n".join(self.logs))

    def test_repr_hides_seed(self):
        s = self.launch(seed=f"sid={COOKIE_VALUE}")
        self.assertNotIn(COOKIE_VALUE, repr(s))


class TestRecover(Base):
    def test_recover_rebuilds_from_seed_and_drops_cache(self):
        self.path.write_text(cache_text(), encoding="utf-8")
        s = self.launch(seed="a=1")
        old_ctx, old_page = s.context, s.page
        self.assertTrue(s.can_recover)
        s.recover()
        self.assertTrue(old_ctx.closed)
        self.assertFalse(self.path.exists())
        self.assertIsNot(s.context, old_ctx)
        self.assertIsNot(s.page, old_page)
        self.assertFalse(s.used_cache)
        self.assertEqual(s.context.cookies_added[0]["name"], "a")

    def test_recover_without_seed_or_from_seed_session_raises(self):
        self.path.write_text(cache_text(), encoding="utf-8")
        s = self.launch(seed=None)
        self.assertFalse(s.can_recover)
        with self.assertRaises(SessionLost):
            s.recover()
        self.assertTrue(self.path.exists())          # 失敗時不動 cache
        self.path.unlink()
        s2 = self.launch(seed="a=1")
        self.assertFalse(s2.can_recover)
        with self.assertRaises(SessionLost):
            s2.recover()

    def test_recover_after_close_raises(self):
        self.path.write_text(cache_text(), encoding="utf-8")
        s = self.launch(seed="a=1")
        s.close()
        with self.assertRaises(SessionLost):
            s.recover()


class TestSaveState(Base):
    def test_contract_format(self):
        s = self.launch(seed="a=1")
        s.save_state()
        text = self.path.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        data = json.loads(text)
        self.assertEqual(list(data), sorted(data))     # 鍵排序
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["saved_utc"], "2026-11-12T08:15:30Z")   # 秒精度、Z
        self.assertEqual(data["server_id"], "s2-test")
        self.assertEqual(data["cookies"][0]["name"], "sid")
        self.assertEqual(data["origins"][0]["origin"], "https://ts1.example.invalid")
        self.assertFalse(Path(str(self.path) + ".tmp").exists())

    def test_save_then_launch_roundtrip(self):
        s = self.launch(seed="a=1")
        s.save_state()
        s2 = self.launch(seed=None)
        self.assertTrue(s2.used_cache)
        self.assertEqual(self.pw.browser.contexts[-1].init_state["cookies"][0]["value"], COOKIE_VALUE)

    def test_save_overwrites_atomically(self):
        self.path.write_text("old", encoding="utf-8")
        s = self.launch(seed="a=1")
        s.save_state()
        self.assertIn("schema_version", self.path.read_text(encoding="utf-8"))

    @unittest.skipIf(os.name == "nt", "POSIX 權限")
    def test_file_mode_600(self):
        s = self.launch(seed="a=1")
        s.save_state()
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)


class TestMisc(Base):
    def test_is_village_html(self):
        self.assertTrue(Session.is_village_html('<div id="stockBar">'))
        self.assertFalse(Session.is_village_html("<html>login</html>"))
        self.assertFalse(Session.is_village_html(None))

    def test_close_idempotent_and_context_manager(self):
        with self.launch(seed="a=1") as s:
            pass
        s.close()
        self.assertEqual(self.pw.browser.closed, 1)

    def test_parse_cookie_header_golden_vs_old(self):
        # 期望值取自舊 travian_ci_run.parse_cookie_header 的離線輸出
        u = "https://h.example"
        c = lambda n, v: {"name": n, "value": v, "url": u}
        cases = {
            "a=1; b=2": [c("a", "1"), c("b", "2")],
            "  a = 1 ;b=2;; ;": [c("a", "1"), c("b", "2")],
            "x=a=b; y=": [c("x", "a=b"), c("y", "")],
            "noequals; k=v": [c("k", "v")],
            "": [], ";": [], "k=v;": [c("k", "v")],
        }
        for header, expected in cases.items():
            self.assertEqual(parse_cookie_header(header, u), expected, header)


if __name__ == "__main__":
    unittest.main()
