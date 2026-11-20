# -*- coding: utf-8 -*-
"""ac-01 village_switch 測試（假 Gateway；dorf1 片段為合成資料，非真實樣本 ✗）。"""
import unittest

from travian_bot.actions.village_switch import assert_active, switch_to
from travian_bot.common.constants import PATH_DORF1
from travian_bot.infra.gateway import GatewayError


class FakeGW:
    def __init__(self, html=None, exc=None):
        self.html, self.exc, self.gets, self.requests = html, exc, [], 0

    def get(self, path, **kw):
        self.gets.append((path, kw))
        if self.exc:
            raise self.exc
        return self.html

    def request(self, *a, **k):
        self.requests += 1
        raise AssertionError("不該送 request")


def page(did=101, x=1, y=2):
    return 'var a = {viewData: {"ownPlayer": {"village": {"id": %d, "x": %d, "y": %d}}}};' % (did, x, y)


class SwitchTo(unittest.TestCase):
    def test_noop_skipped_no_requests(self):
        gw = FakeGW()
        r = switch_to(gw, 101)
        self.assertEqual((r.result, r.requests_used, r.verified), ("skipped", 0, None))
        self.assertEqual(gw.gets, [])
        self.assertEqual(gw.requests, 0)

    def test_bad_did(self):
        for bad in (0, -1, "101", None, True, 1.5):
            with self.assertRaises(ValueError):
                switch_to(FakeGW(), bad)


class AssertActive(unittest.TestCase):
    def test_match(self):
        gw = FakeGW(page(101))
        self.assertIs(assert_active(gw, 101), True)
        self.assertEqual(gw.gets, [(PATH_DORF1, {"raw": True})])

    def test_mismatch(self):
        self.assertIs(assert_active(FakeGW(page(102)), 101), False)

    def test_unreadable_page_is_false(self):
        self.assertIs(assert_active(FakeGW("<html>沒有 viewData</html>"), 101), False)

    def test_out_of_map_is_false(self):
        self.assertIs(assert_active(FakeGW(page(101, 500, 0)), 101, map_half=200), False)
        self.assertIs(assert_active(FakeGW(page(101, 150, 0)), 101, map_half=200), True)

    def test_gateway_error_propagates(self):
        with self.assertRaises(GatewayError):
            assert_active(FakeGW(exc=GatewayError("x")), 101)

    def test_bad_did(self):
        with self.assertRaises(ValueError):
            assert_active(FakeGW(page()), 0)


if __name__ == "__main__":
    unittest.main()
