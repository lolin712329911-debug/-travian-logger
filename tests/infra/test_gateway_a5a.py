# -*- coding: utf-8 -*-
"""tests/infra/test_gateway_a5a.py（if-02 v0.2 追加）v0.1（A5a）：Response.headers、Gateway.base_url、Gateway.click。
既有行為（A4a）的測試不動。"""
import unittest
from types import SimpleNamespace as NS

from tests.fakes_a5a import BASE, FakePage, FakeResp, make_gateway
from travian_bot.infra.gateway import Gateway, GatewayError, GatewayLimits, Response

P = "/hero/adventures"


def loaded(**kw):
    """已經 get 過一頁（page.url 有值）的 gateway。"""
    gw, page, router = make_gateway(pages={P: "<html>x</html>"}, **kw)
    gw.get("hero/adventures")
    return gw, page, router


class ResponseHeadersTest(unittest.TestCase):
    def test_default_is_empty_dict(self):
        self.assertEqual(Response(200, True, "x").headers, {})
        self.assertIsNot(Response(200, True, "x").headers, Response(200, True, "y").headers)

    def test_keys_are_lowercased(self):
        gw, _, _ = make_gateway(routes={("PUT", "/a"): [FakeResp(204, "", {"X-Nonce": "abc", "Content-Type": "t"})]})
        r = gw.request("PUT", "/a")
        self.assertEqual(r.headers, {"x-nonce": "abc", "content-type": "t"})
        self.assertEqual((r.status, r.ok), (204, True))

    def test_values_are_strings(self):
        gw, _, _ = make_gateway(routes={("GET", "/a"): [FakeResp(200, "x", {"X-N": 5})]})
        self.assertEqual(gw.request("GET", "/a").headers, {"x-n": "5"})

    def test_missing_or_none_headers_become_empty(self):
        bare = NS(status=200, ok=True, text=lambda: "x")
        for resp in (bare, FakeResp(200, "x", None)):
            gw, _, _ = make_gateway(routes={("GET", "/a"): [resp]})
            if isinstance(resp, FakeResp):
                resp.headers = None
            self.assertEqual(gw.request("GET", "/a").headers, {})

    def test_request_headers_are_sent_not_overwritten_by_response_headers(self):
        # 回歸：實作曾把回應標頭的變數蓋掉外層的請求標頭
        gw, _, router = make_gateway(routes={("POST", "/a"): [FakeResp(200, "x", {"X-Resp": "1"})]})
        r = gw.request("POST", "/a", headers={"x-req": "2"}, data="{}")
        self.assertEqual(router.calls[0]["headers"], {"x-req": "2"})
        self.assertEqual(r.headers, {"x-resp": "1"})

    def test_get_also_returns_headers(self):
        gw, _, _ = make_gateway(routes={("GET", "/a"): [FakeResp(200, "x", {"A": "b"})]})
        self.assertEqual(gw.request("GET", "/a").headers, {"a": "b"})

    def test_cookie_and_authorization_still_refused(self):
        gw, _, router = make_gateway(routes={("GET", "/a"): [FakeResp()]})
        for k in ("Cookie", "authorization"):
            with self.assertRaises(ValueError):
                gw.request("GET", "/a", headers={k: "x"})
        self.assertEqual(router.calls, [])

    def test_post_is_not_retried_even_when_get_retries_set(self):
        gw, _, router = make_gateway(routes={("POST", "/a"): [OSError("net")]},
                                     limits=GatewayLimits(get_retries=2))
        with self.assertRaises(GatewayError) as cm:
            gw.request("POST", "/a?checksum=secret", data="{}")
        self.assertEqual((len(router.calls), gw.request_count()), (1, 1))
        self.assertNotIn("secret", str(cm.exception))

    def test_get_is_still_retried(self):
        gw, _, router = make_gateway(routes={("GET", "/a"): [OSError("net"), FakeResp(200, "ok")]},
                                     limits=GatewayLimits(get_retries=1))
        self.assertEqual(gw.request("GET", "/a").text, "ok")
        self.assertEqual(gw.request_count(), 2)


class BaseUrlTest(unittest.TestCase):
    def test_base_url_without_trailing_slash(self):
        gw, _, _ = make_gateway(base=BASE + "/")
        self.assertEqual(gw.base_url, BASE)

    def test_base_url_is_read_only(self):
        gw, _, _ = make_gateway()
        with self.assertRaises(AttributeError):
            gw.base_url = "https://evil.example"


class ClickTest(unittest.TestCase):
    def test_clicks_nth_element_then_waits(self):
        gw, page, _ = loaded()
        n = gw.request_count()
        gw.click("table tr td button", index=2, settle_ms=500)
        self.assertEqual((page.clicks, page.waits), ([("table tr td button", 2)], [500]))
        self.assertEqual(gw.request_count(), n + 1)

    def test_defaults(self):
        gw, page, _ = loaded()
        gw.click("button")
        self.assertEqual((page.clicks, page.waits), ([("button", 0)], [3000]))

    def test_settle_zero_does_not_wait(self):
        gw, page, _ = loaded()
        gw.click("button", settle_ms=0)
        self.assertEqual((len(page.clicks), page.waits), (1, []))

    def test_unsafe_current_page_is_not_clicked(self):
        gw, page, _ = loaded()
        n = gw.request_count()
        for url in ("https://evil.example/x", "http://ts1.example.com/x", ""):
            page.url = url
            with self.assertRaises(GatewayError):
                gw.click("button")
        self.assertEqual((page.clicks, gw.request_count()), ([], n))

    def test_click_before_any_page_is_refused(self):
        gw, page, _ = make_gateway()
        with self.assertRaises(GatewayError):
            gw.click("button")
        self.assertEqual(page.clicks, [])

    def test_click_failure_is_gateway_error_without_detail_and_not_retried(self):
        page = FakePage({P: "x"}, click_error=RuntimeError("secret-token-123"))
        gw, page, _ = make_gateway(page=page, limits=GatewayLimits(get_retries=3))
        gw.get("hero/adventures")
        n = gw.request_count()
        with self.assertRaises(GatewayError) as cm:
            gw.click("button")
        self.assertEqual(len(page.clicks), 1)
        self.assertEqual(gw.request_count(), n + 1)
        self.assertIn("RuntimeError", str(cm.exception))
        self.assertNotIn("secret-token-123", str(cm.exception))

    def test_invalid_arguments_raise_before_touching_the_page(self):
        gw, page, _ = loaded()
        n = gw.request_count()
        bad = [dict(selector=""), dict(selector="  "), dict(selector=None), dict(selector=5),
               dict(selector="b", index=-1), dict(selector="b", index=True), dict(selector="b", index=1.5),
               dict(selector="b", settle_ms=-1), dict(selector="b", settle_ms=True), dict(selector="b", settle_ms="3")]
        for kw in bad:
            with self.subTest(kw):
                with self.assertRaises(ValueError):
                    gw.click(kw.pop("selector"), **kw)
        self.assertEqual((page.clicks, page.waits, gw.request_count()), ([], [], n))

    def test_click_honours_wait_limits(self):
        sleeps = []
        gw, page, _ = loaded(limits=GatewayLimits(wait_min_s=1, wait_max_s=2),
                             sleep=sleeps.append, uniform=lambda a, b: 1.5)
        sleeps.clear()
        gw.click("button")
        self.assertEqual(sleeps, [1.5])


if __name__ == "__main__":
    unittest.main()
