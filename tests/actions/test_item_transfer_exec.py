# -*- coding: utf-8 -*-
"""tests/actions/test_item_transfer_exec.py（ac-03）v0.1（A5a）。
替身：tests/fakes_a5a（Router 依 (方法, 路徑) 回應）。解析用真的 ps-05 parse_transfer_state。"""
import json
import unittest

from tests.fakes_a5a import BASE, FakeResp, make_gateway
from travian_bot.actions import item_transfer_exec as IT
from travian_bot.common.decisions import ItemTransferDecision, TransferLine
from travian_bot.common.modes import Mode
from travian_bot.common.schema import ParseError
from travian_bot.infra.gateway import GatewayError

GQL = ("POST", IT.GRAPHQL_PATH)
PUT = ("PUT", IT.USE_ITEM_PATH)
POST = ("POST", IT.USE_ITEM_PATH)
INV = {0: (11, 1000), 1: (12, 1000), 2: (13, 1000), 3: (14, 1000)}   # 資源索引 → (庫存物件 id, 數量)


def state_json(stock=(0, 0, 0, 0), inv=INV, village_id=7, wh=10000, gr=10000):
    items = [{"id": i, "amount": a, "typeId": 145 + r} for r, (i, a) in inv.items()]
    return json.dumps({"data": {"ownPlayer": {
        "hero": {"inventory": items},
        "village": {"id": village_id, "resources": {
            "lumberStock": stock[0], "clayStock": stock[1], "ironStock": stock[2], "cropStock": stock[3],
            "maxStorageCapacity": wh, "maxCropStorageCapacity": gr}}}}})


def gql(stock=(0, 0, 0, 0), inv=INV):
    return FakeResp(200, state_json(stock, inv))


def item_of(call):
    return json.loads(call["data"])["itemId"]


def put_ok(call):
    return FakeResp(204, "", {"X-Nonce": "nonce-%d" % item_of(call)})       # 大寫鍵：Gateway 要轉小寫


def post_ok(call):
    want = "nonce-%d" % item_of(call)
    return FakeResp(200, "{}") if (call["headers"] or {}).get("x-nonce") == want else FakeResp(403, "bad nonce")


def dec(lines=((0, 11, 500),), village_id=7, targets=(500, 0, 0, 0), act=True, reason="缺口"):
    return ItemTransferDecision(act, reason, tuple(TransferLine(*ln) for ln in lines), village_id, targets)


def routes_ok(before=(0, 0, 0, 0), after=(500, 0, 0, 0)):
    return {GQL: [gql(before), gql(after)], PUT: [put_ok], POST: [post_ok]}


def run(decision=None, routes=None, mode=Mode.LIVE):
    gw, page, router = make_gateway(routes=routes if routes is not None else routes_ok())
    r = IT.execute_item_transfer(gw, decision or dec(), mode)
    return r, router, gw


TWO = dict(lines=((0, 11, 500), (3, 14, 300)), targets=(500, 0, 0, 300))


class ModeTest(unittest.TestCase):
    def test_off_no_requests(self):
        r, router, _ = run(mode=Mode.OFF)
        self.assertEqual((r.result, r.requests_used, router.calls), ("skipped", 0, []))

    def test_unknown_mode_is_off(self):
        for bad in ("on", "LIVE!", None, 1, ""):
            r, router, _ = run(mode=bad)
            self.assertEqual((r.result, router.calls), ("skipped", []), repr(bad))

    def test_plain_string_modes(self):
        r, router, _ = run(mode="dry")
        self.assertEqual(r.result, "dry")
        r, router, _ = run(mode=" LIVE ")
        self.assertEqual(r.result, "ok")

    def test_act_false_skipped_no_requests(self):
        r, router, _ = run(ItemTransferDecision(False, "不需要"))
        self.assertEqual((r.result, r.requests_used, router.calls), ("skipped", 0, []))
        self.assertIn("不需要", r.detail)

    def test_dry_sends_nothing(self):
        r, router, _ = run(dec(**TWO), mode=Mode.DRY)
        self.assertEqual((r.result, r.verified, r.requests_used, router.calls), ("dry", None, 0, []))
        self.assertIn("lumber 500", r.detail)
        self.assertIn("crop 300", r.detail)


class ValidationTest(unittest.TestCase):
    def test_invalid_decisions_failed_and_nothing_sent(self):
        good = dec()
        cases = {
            "lines 空": ItemTransferDecision(True, "x", (), 7, (1, 1, 1, 1)),
            "village None": dec(village_id=None),
            "village 0": dec(village_id=0),
            "village bool": dec(village_id=True),
            "targets None": dec(targets=None),
            "targets list": dec(targets=[500, 0, 0, 0]),
            "targets 3 個": dec(targets=(1, 2, 3)),
            "targets 負數": dec(targets=(500, -1, 0, 0)),
            "targets bool": dec(targets=(True, 0, 0, 0)),
            "resource 4": dec(lines=((4, 11, 5),)),
            "resource -1": dec(lines=((-1, 11, 5),)),
            "resource bool": dec(lines=((True, 11, 5),)),
            "item_id 0": dec(lines=((0, 0, 5),)),
            "amount 0": dec(lines=((0, 11, 0),)),
            "amount bool": dec(lines=((0, 11, True),)),
            "amount 負數": dec(lines=((0, 11, -5),)),
            "resource 重複": dec(lines=((0, 11, 5), (0, 12, 5))),
            "item_id 重複": dec(lines=((0, 11, 5), (1, 11, 5))),
        }
        self.assertIsNone(IT._check(good))
        for name, d in cases.items():
            with self.subTest(name):
                r, router, _ = run(d)
                self.assertEqual(r.result, "failed")
                self.assertEqual((r.requests_used, router.calls), (0, []))
                self.assertIn("未送出", r.detail)


class LiveOkTest(unittest.TestCase):
    def test_order_all_put_then_all_post(self):
        r, router, _ = run(dec(**TWO), routes_ok(after=(500, 0, 0, 300)))
        self.assertEqual((r.result, r.verified), ("ok", True))
        self.assertEqual(router.seq(), [GQL, PUT, PUT, POST, POST, GQL])
        self.assertEqual(router.unexpected, [])

    def test_each_post_carries_its_own_items_nonce(self):
        r, router, _ = run(dec(**TWO), routes_ok(after=(500, 0, 0, 300)))
        posts = router.of("POST", IT.USE_ITEM_PATH)
        self.assertEqual([(item_of(c), c["headers"]["x-nonce"]) for c in posts],
                         [(11, "nonce-11"), (14, "nonce-14")])
        self.assertEqual(r.result, "ok")          # post_ok 在 nonce 對不上時回 403

    def test_put_has_no_nonce_header(self):
        _, router, _ = run()
        self.assertNotIn("x-nonce", router.of("PUT")[0]["headers"])

    def test_put_and_post_payload_identical(self):
        _, router, _ = run(dec(**TWO), routes_ok(after=(500, 0, 0, 300)))
        puts, posts = router.of("PUT"), router.of("POST", IT.USE_ITEM_PATH)
        self.assertEqual([c["data"] for c in puts], [c["data"] for c in posts])
        self.assertEqual(json.loads(puts[0]["data"]),
                         {"action": "inventory", "itemId": 11, "amount": 500, "villageId": 7})
        self.assertEqual(json.loads(puts[1]["data"]),
                         {"action": "inventory", "itemId": 14, "amount": 300, "villageId": 7})

    def test_headers_origin_referer_and_no_cookie(self):
        _, router, _ = run()
        h = router.of("PUT")[0]["headers"]
        self.assertEqual((h["origin"], h["referer"]), (BASE, BASE + "/dorf1.php"))
        self.assertTrue(h["content-type"].startswith("application/json"))
        self.assertFalse({k.lower() for k in h} & {"cookie", "authorization"})

    def test_graphql_body_is_valid_json_with_state_query(self):
        _, router, _ = run()
        body = json.loads(router.of("POST", IT.GRAPHQL_PATH)[0]["data"])
        self.assertEqual(body, {"query": IT.STATE_QUERY})

    def test_requests_used_counts_all(self):
        r, router, gw = run()
        self.assertEqual(r.requests_used, 4)                 # graphql、PUT、POST、graphql
        self.assertEqual(r.requests_used, gw.request_count())
        r, router, gw = run(dec(**TWO), routes_ok(after=(500, 0, 0, 300)))
        self.assertEqual(r.requests_used, 6)

    def test_exact_target_is_enough(self):
        r, _, _ = run(routes=routes_ok(after=(500, 0, 0, 0)))
        self.assertEqual((r.result, r.verified), ("ok", True))

    def test_only_resources_in_lines_are_checked(self):
        d = dec(targets=(500, 9999, 9999, 9999))            # 其他資源的目標高，但不在 lines 裡
        r, _, _ = run(d, routes_ok(after=(500, 0, 0, 0)))
        self.assertEqual((r.result, r.verified), ("ok", True))

    def test_detail_has_before_after_and_no_nonce(self):
        r, _, _ = run()
        self.assertIn("0→500", r.detail)
        self.assertIn("庫存", r.detail)
        self.assertNotIn("nonce-11", r.detail)

    def test_baseline_failure_does_not_block(self):
        routes = routes_ok()
        routes[GQL] = [FakeResp(500, "x"), gql((500, 0, 0, 0))]
        r, router, _ = run(routes=routes)
        self.assertEqual((r.result, r.verified), ("ok", True))
        self.assertIn("?→500", r.detail)
        self.assertEqual(len(router.of("PUT")), 1)


class LiveFailTest(unittest.TestCase):
    def uses(self, router):
        return [(c["method"]) for c in router.calls if c["path"] == IT.USE_ITEM_PATH]

    def test_short_after_is_failed_verified_false_no_retry(self):
        r, router, _ = run(routes=routes_ok(after=(499, 0, 0, 0)))
        self.assertEqual((r.result, r.verified), ("failed", False))
        self.assertEqual(self.uses(router), ["PUT", "POST"])
        self.assertIn("不足", r.detail)

    def test_reread_failure_is_unverified(self):
        routes = routes_ok()
        routes[GQL] = [gql(), FakeResp(500, "x")]
        r, router, _ = run(routes=routes)
        self.assertEqual((r.result, r.verified), ("failed", None))
        self.assertIn("無法驗證", r.detail)
        self.assertEqual(self.uses(router), ["PUT", "POST"])

    def test_reread_unparseable_is_unverified(self):
        routes = routes_ok()
        routes[GQL] = [gql(), FakeResp(200, "<html>")]
        r, _, _ = run(routes=routes)
        self.assertEqual((r.result, r.verified), ("failed", None))

    def test_put_http_error_stops_before_post(self):
        routes = routes_ok()
        routes[PUT] = [FakeResp(500, "boom")]
        r, router, _ = run(dec(**TWO), routes)
        self.assertEqual((r.result, r.verified), ("failed", None))
        self.assertEqual(self.uses(router), ["PUT"])          # 第二個 PUT 與所有 POST 都沒送
        self.assertIn("HTTP 500", r.detail)

    def test_put_without_nonce_stops_before_post(self):
        routes = routes_ok()
        routes[PUT] = [FakeResp(204, "", {})]
        r, router, _ = run(dec(**TWO), routes)
        self.assertEqual(r.result, "failed")
        self.assertEqual(self.uses(router), ["PUT"])          # 第一個 PUT 沒給 nonce 就停，不送第二個 PUT
        self.assertIn("回應標頭沒有 x-nonce", r.detail)

    def test_put_transport_error_stops(self):
        routes = routes_ok()
        routes[PUT] = [OSError("net")]
        r, router, _ = run(routes=routes)
        self.assertEqual(r.result, "failed")
        self.assertEqual(self.uses(router), ["PUT"])

    def test_second_put_failure_sends_no_post(self):
        routes = routes_ok()
        routes[PUT] = [put_ok, FakeResp(429, "slow")]
        r, router, _ = run(dec(**TWO), routes)
        self.assertEqual(r.result, "failed")
        self.assertEqual(self.uses(router), ["PUT", "PUT"])

    def test_post_error_stops_remaining_posts(self):
        routes = routes_ok()
        routes[POST] = [FakeResp(500, "boom")]
        r, router, _ = run(dec(**TWO), routes)
        self.assertEqual(r.result, "failed")
        self.assertEqual(self.uses(router), ["PUT", "PUT", "POST"])   # 只送了第一個 POST，不重試、不送第二個
        self.assertIn("HTTP 500", r.detail)

    def test_post_transport_error_stops(self):
        routes = routes_ok()
        routes[POST] = [OSError("net")]
        r, router, _ = run(routes=routes)
        self.assertEqual(r.result, "failed")
        self.assertEqual(self.uses(router), ["PUT", "POST"])

    def test_failure_details_never_contain_nonce(self):
        routes = routes_ok()
        routes[POST] = [FakeResp(500, "boom")]
        r, _, _ = run(routes=routes)
        self.assertNotIn("nonce-11", r.detail)


class ReadStateTest(unittest.TestCase):
    def test_reads_graphql(self):
        gw, _, router = make_gateway(routes={GQL: [gql((1, 2, 3, 4))]})
        st = IT.read_transfer_state(gw)
        self.assertEqual((st.village_id, st.stock, st.capacity), (7, (1, 2, 3, 4), (10000,) * 4))
        self.assertEqual(st.inventory[0].id, 11)
        self.assertEqual(router.seq(), [GQL])

    def test_http_error_raises_gateway_error(self):
        gw, _, _ = make_gateway(routes={GQL: [FakeResp(503, "x")]})
        with self.assertRaises(GatewayError):
            IT.read_transfer_state(gw)

    def test_bad_body_raises_parse_error(self):
        gw, _, _ = make_gateway(routes={GQL: [FakeResp(200, "{}")]})
        with self.assertRaises(ParseError):
            IT.read_transfer_state(gw)


if __name__ == "__main__":
    unittest.main()
