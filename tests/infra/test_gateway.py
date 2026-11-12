import unittest
from types import SimpleNamespace

from travian_bot.infra.gateway import (Gateway, GatewayError, GatewayLimits, Response, safe_url)

BASE = "https://ts1.example.invalid"


class FakeResp:
    def __init__(self, text="", status=200, ok=True):
        self._t, self.status, self.ok = text, status, ok

    def text(self):
        return self._t


class FakeRequest:
    def __init__(self, owner):
        self.o = owner

    def get(self, url):
        self.o.calls.append(("raw_get", url))
        return self.o.next("raw_get")

    def fetch(self, url, **kw):
        self.o.calls.append(("fetch", url, kw))
        return self.o.next("fetch")


class FakeWorld:
    """page＋context 的假物件；script 是依序回傳（Exception 實例＝丟出）。"""

    def __init__(self, page_html="<html/>", script=None):
        self.calls, self.page_html, self.script = [], page_html, list(script or [])
        self.page = SimpleNamespace(goto=self._goto, content=lambda: self.page_html)
        self.context = SimpleNamespace(request=FakeRequest(self))

    def _goto(self, url, wait_until=None):
        self.calls.append(("goto", url, wait_until))
        if self.script and isinstance(self.script[0], Exception) and self.script[0].__class__.__name__ == "GotoBoom":
            raise self.script.pop(0)

    def next(self, kind):
        item = self.script.pop(0) if self.script else FakeResp("raw")
        if isinstance(item, Exception):
            raise item
        return item


class GotoBoom(Exception):
    pass


def make(world, limits=None, **kw):
    prof = SimpleNamespace(base_url=BASE + "/")
    return Gateway(world, prof, limits, **kw)


class TestSafeUrl(unittest.TestCase):
    def test_accepts(self):
        for u in ("/dorf1.php", "/dorf1.php?id=3&gid=4", BASE + "/build.php?id=1", BASE.upper().replace("HTTPS", "https")):
            self.assertTrue(safe_url(u, BASE), u)

    def test_rejects(self):
        bad = ["", None, 5, "dorf1.php", "//evil.example/x", "http://ts1.example.invalid/x",
               "https://evil.example/x", "https://ts1.example.invalid@evil.example/",
               "https://user:pw@ts1.example.invalid/", "/a/../b", "/a b", "/a\nb", "/a\\b",
               "https://ts1.example.invalid.evil.example/", "javascript:alert(1)"]
        for u in bad:
            self.assertFalse(safe_url(u, BASE), repr(u))


class TestGet(unittest.TestCase):
    def test_default_renders_with_browser(self):
        w = FakeWorld("<html>X</html>")
        g = make(w)
        self.assertEqual(g.get("dorf1.php"), "<html>X</html>")
        self.assertEqual(w.calls, [("goto", BASE + "/dorf1.php", "networkidle")])
        self.assertEqual(g.request_count(), 1)

    def test_leading_slash_and_double_slash_stay_on_base(self):
        w = FakeWorld()
        make(w).get("//evil.example/x")
        self.assertEqual(w.calls[0][1], BASE + "/evil.example/x")

    def test_raw_uses_http_not_browser(self):
        w = FakeWorld(script=[FakeResp("RAW")])
        g = make(w)
        self.assertEqual(g.get("dorf1.php", raw=True), "RAW")
        self.assertEqual(w.calls, [("raw_get", BASE + "/dorf1.php")])

    def test_raw_if_true_refetches_raw(self):
        w = FakeWorld("<rendered/>", script=[FakeResp("<original/>")])
        g = make(w)
        seen = []
        out = g.get("dorf1.php", raw_if=lambda h: seen.append(h) or True)
        self.assertEqual(out, "<original/>")
        self.assertEqual(seen, ["<rendered/>"])
        self.assertEqual(g.request_count(), 2)

    def test_raw_if_false_keeps_rendered(self):
        w = FakeWorld("<rendered/>")
        g = make(w)
        self.assertEqual(g.get("dorf1.php", raw_if=lambda h: False), "<rendered/>")
        self.assertEqual(g.request_count(), 1)

    def test_did_ignored(self):
        w = FakeWorld()
        make(w).get("dorf1.php", did=123)
        self.assertEqual(w.calls[0][1], BASE + "/dorf1.php")

    def test_unsafe_path_rejected_and_not_sent(self):
        w = FakeWorld()
        for p in ("https://evil.example/x", "http://ts1.example.invalid/x", "/a/../b", "", "  "):
            with self.assertRaises(GatewayError):
                make(w).get(p)
        self.assertEqual(w.calls, [])

    def test_error_message_has_no_query(self):
        w = FakeWorld(script=[ConnectionError("x")])
        with self.assertRaises(GatewayError) as cm:
            make(w).get("dorf1.php?checksum=deadbeef&id=1", raw=True)
        self.assertNotIn("deadbeef", str(cm.exception))
        self.assertIn("/dorf1.php", str(cm.exception))

    def test_session_replacement_is_followed(self):
        w1, w2 = FakeWorld("<one/>"), FakeWorld("<two/>")
        holder = SimpleNamespace(page=w1.page, context=w1.context)
        g = Gateway(holder, SimpleNamespace(base_url=BASE))
        self.assertEqual(g.get("dorf1.php"), "<one/>")
        holder.page, holder.context = w2.page, w2.context      # 模擬 recover()
        self.assertEqual(g.get("dorf1.php"), "<two/>")


class TestRetryAndWait(unittest.TestCase):
    def test_default_limits_no_retry_no_sleep(self):
        slept = []
        w = FakeWorld(script=[ConnectionError("a"), FakeResp("ok")])
        g = make(w, sleep=slept.append)
        with self.assertRaises(GatewayError):
            g.get("x.php", raw=True)
        self.assertEqual(g.request_count(), 1)
        self.assertEqual(slept, [])

    def test_get_retries_transport_errors(self):
        slept = []
        w = FakeWorld(script=[ConnectionError("a"), ConnectionError("b"), FakeResp("ok")])
        g = make(w, GatewayLimits(get_retries=2, retry_wait_s=1.5), sleep=slept.append)
        self.assertEqual(g.get("x.php", raw=True), "ok")
        self.assertEqual(g.request_count(), 3)
        self.assertEqual(slept, [1.5, 1.5])

    def test_retries_exhausted(self):
        w = FakeWorld(script=[ConnectionError("a")] * 3)
        g = make(w, GatewayLimits(get_retries=1), sleep=lambda s: None)
        with self.assertRaises(GatewayError):
            g.get("x.php", raw=True)
        self.assertEqual(g.request_count(), 2)

    def test_random_wait_before_each_request(self):
        slept, asked = [], []
        w = FakeWorld(script=[FakeResp("a"), FakeResp("b")])
        g = make(w, GatewayLimits(wait_min_s=1, wait_max_s=3), sleep=slept.append,
                 uniform=lambda lo, hi: asked.append((lo, hi)) or 2.0)
        g.get("a.php", raw=True)
        g.get("b.php", raw=True)
        self.assertEqual(asked, [(1, 3), (1, 3)])
        self.assertEqual(slept, [2.0, 2.0])

    def test_limits_validation(self):
        for kw in ({"wait_min_s": -1}, {"wait_min_s": 2, "wait_max_s": 1}, {"get_retries": -1},
                   {"get_retries": True}, {"retry_wait_s": "x"}):
            with self.assertRaises(ValueError):
                GatewayLimits(**kw)

    def test_elapsed(self):
        t = [100.0]
        g = make(FakeWorld(), clock=lambda: t[0])
        t[0] = 107.5
        self.assertEqual(g.elapsed(), 7.5)


class TestSubmitAndRequest(unittest.TestCase):
    def test_submit_goto_and_safe(self):
        w = FakeWorld()
        g = make(w)
        g.submit("/dorf1.php?id=1&gid=4&action=build&checksum=abc123")
        self.assertEqual(w.calls[0][0], "goto")
        self.assertEqual(g.request_count(), 1)
        with self.assertRaises(GatewayError):
            g.submit("https://evil.example/x")
        self.assertEqual(len(w.calls), 1)

    def test_submit_never_retried(self):
        w = FakeWorld(script=[GotoBoom("x")])
        g = make(w, GatewayLimits(get_retries=5), sleep=lambda s: None)
        with self.assertRaises(GatewayError):
            g.submit("/dorf1.php")
        self.assertEqual(len(w.calls), 1)

    def test_request_post_returns_response_no_retry(self):
        w = FakeWorld(script=[FakeResp("body", 500, False)])
        g = make(w, GatewayLimits(get_retries=3))
        r = g.request("post", "/api/x", headers={"X-A": "1"}, data={"k": "v"})
        self.assertEqual(r, Response(500, False, "body"))
        self.assertEqual(w.calls[0][2], {"method": "POST", "headers": {"X-A": "1"}, "data": {"k": "v"}})

    def test_request_post_transport_error_not_resent(self):
        w = FakeWorld(script=[ConnectionError("x"), FakeResp("ok")])
        g = make(w, GatewayLimits(get_retries=3), sleep=lambda s: None)
        with self.assertRaises(GatewayError):
            g.request("POST", "/api/x", data="d")
        self.assertEqual(g.request_count(), 1)

    def test_request_get_retries(self):
        w = FakeWorld(script=[ConnectionError("x"), FakeResp("ok")])
        g = make(w, GatewayLimits(get_retries=1), sleep=lambda s: None)
        self.assertEqual(g.request("GET", "/api/x").text, "ok")
        self.assertEqual(g.request_count(), 2)

    def test_request_rejects_bad_method_and_cookie_header(self):
        g = make(FakeWorld())
        with self.assertRaises(ValueError):
            g.request("PATCH", "/x")
        with self.assertRaises(ValueError):
            g.request("POST", "/x", headers={"Cookie": "a=b"})
        with self.assertRaises(ValueError):
            g.request("POST", "/x", headers={"authorization": "Bearer x"})


if __name__ == "__main__":
    unittest.main()
