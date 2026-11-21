# -*- coding: utf-8 -*-
"""tests/actions/test_focus_exec.py（ac-04）v0.1（A5a）。解析用真的 ps-05。"""
import json
import unittest

from tests.fakes_a5a import BASE, FakeResp, make_gateway
from travian_bot.actions import focus_exec as FE
from travian_bot.common.decisions import FOCUS_NAMES, FocusDecision
from travian_bot.common.modes import Mode
from travian_bot.common.schema import ParseError
from travian_bot.infra.gateway import GatewayError

SCREEN = ("GET", FE.SCREEN_PATH)
SET = ("POST", FE.ATTR_PATH)


def screen(cur):
    return FakeResp(200, json.dumps({"hero": {"productionType": cur, "productionTypes": [336, 1120, 1120, 1120, 1120]}}))


def posted(n):
    return FakeResp(200, json.dumps({"productionType": n, "other": 1}))


def dec(focus="wood", act=True, reason="缺木"):
    return FocusDecision(act, focus, reason)


def run(decision=None, routes=None, mode=Mode.LIVE):
    gw, _, router = make_gateway(routes=routes if routes is not None else {SET: [posted(1)], SCREEN: [screen(1)]})
    return FE.set_focus(gw, decision or dec(), mode), router, gw


class ReadFocusTest(unittest.TestCase):
    def test_reads_attributes(self):
        gw, _, router = make_gateway(routes={SCREEN: [screen(3)]})
        f = FE.read_focus(gw)
        self.assertEqual((f.current, f.types), (3, (336, 1120, 1120, 1120, 1120)))
        h = router.calls[0]["headers"]
        self.assertEqual((h["origin"], h["referer"]), (BASE, BASE + "/hero/attributes"))

    def test_http_error_raises_gateway_error(self):
        gw, _, _ = make_gateway(routes={SCREEN: [FakeResp(500, "x")]})
        with self.assertRaises(GatewayError):
            FE.read_focus(gw)

    def test_bad_body_raises_parse_error(self):
        gw, _, _ = make_gateway(routes={SCREEN: [FakeResp(200, "{}")]})
        with self.assertRaises(ParseError):
            FE.read_focus(gw)


class SetFocusGuardTest(unittest.TestCase):
    def test_off_no_requests(self):
        r, router, _ = run(mode=Mode.OFF)
        self.assertEqual((r.result, r.requests_used, router.calls), ("skipped", 0, []))

    def test_unknown_mode_is_off(self):
        for bad in ("on", None, 3, "LIVE!"):
            r, router, _ = run(mode=bad)
            self.assertEqual((r.result, router.calls), ("skipped", []), repr(bad))

    def test_act_false_skipped(self):
        r, router, _ = run(FocusDecision(False, None, "不用切"))
        self.assertEqual((r.result, router.calls), ("skipped", []))
        self.assertIn("不用切", r.detail)

    def test_invalid_focus_failed_not_sent(self):
        for bad in (None, "", "gold", "WOOD", 1, "wood "):
            with self.subTest(bad):
                r, router, _ = run(dec(focus=bad))
                self.assertEqual((r.result, r.requests_used, router.calls), ("failed", 0, []))

    def test_dry_sends_nothing(self):
        r, router, _ = run(mode=Mode.DRY)
        self.assertEqual((r.result, r.verified, r.requests_used, router.calls), ("dry", None, 0, []))
        self.assertIn("wood", r.detail)
        self.assertIn("resource=1", r.detail)


class SetFocusLiveTest(unittest.TestCase):
    def test_each_name_maps_to_its_code(self):
        for code, name in enumerate(FOCUS_NAMES):
            with self.subTest(name):
                r, router, _ = run(dec(name), {SET: [posted(code)], SCREEN: [screen(code)]})
                self.assertEqual((r.result, r.verified), ("ok", True))
                self.assertEqual(json.loads(router.of("POST")[0]["data"]), {"resource": code})

    def test_flow_post_then_reread_and_counts(self):
        r, router, gw = run()
        self.assertEqual(router.seq(), [SET, SCREEN])
        self.assertEqual((r.requests_used, gw.request_count()), (2, 2))
        self.assertEqual(router.unexpected, [])

    def test_post_headers(self):
        _, router, _ = run()
        h = router.of("POST")[0]["headers"]
        self.assertEqual((h["origin"], h["referer"]), (BASE, BASE + "/hero/attributes"))
        self.assertFalse({k.lower() for k in h} & {"cookie", "authorization", "x-nonce"})

    def test_post_http_error_no_reread_no_retry(self):
        r, router, _ = run(routes={SET: [FakeResp(500, "boom")], SCREEN: [screen(1)]})
        self.assertEqual((r.result, r.verified), ("failed", None))
        self.assertEqual(router.seq(), [SET])
        self.assertIn("HTTP 500", r.detail)

    def test_post_transport_error_no_retry(self):
        r, router, _ = run(routes={SET: [OSError("net")], SCREEN: [screen(1)]})
        self.assertEqual((r.result, r.verified), ("failed", None))
        self.assertEqual(router.seq(), [SET])
        self.assertIn("不重送", r.detail)

    def test_unparseable_response_failed(self):
        r, router, _ = run(routes={SET: [FakeResp(200, "<html>")], SCREEN: [screen(1)]})
        self.assertEqual((r.result, r.verified), ("failed", None))
        self.assertEqual(router.seq(), [SET])

    def test_response_mismatch_failed_verified_false_no_reread(self):
        r, router, _ = run(routes={SET: [posted(2)], SCREEN: [screen(1)]})
        self.assertEqual((r.result, r.verified), ("failed", False))
        self.assertEqual(router.seq(), [SET])

    def test_reread_mismatch_failed_verified_false(self):
        r, router, _ = run(routes={SET: [posted(1)], SCREEN: [screen(0)]})
        self.assertEqual((r.result, r.verified), ("failed", False))
        self.assertEqual(router.seq(), [SET, SCREEN])

    def test_reread_error_is_ok_but_unverified(self):
        for resp in (FakeResp(500, "x"), FakeResp(200, "{}"), OSError("net")):
            with self.subTest(repr(resp)):
                r, _, _ = run(routes={SET: [posted(1)], SCREEN: [resp]})
                self.assertEqual((r.result, r.verified), ("ok", None))
                self.assertIn("未驗證", r.detail)


if __name__ == "__main__":
    unittest.main()
