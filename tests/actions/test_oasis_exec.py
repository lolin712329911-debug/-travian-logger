# -*- coding: utf-8 -*-
"""ac-07 oasis_exec 測試。區塊 JSON 與 tile-details HTML 都是依 ps-08／ps-09 的選擇器合成的資料（非真實樣本 ✗）。"""
import ast
import json
import os
import unittest

from travian_bot.actions import oasis_exec as OE
from travian_bot.actions.oasis_exec import OasisExecError, fetch_block, scan, verify_oasis
from travian_bot.common.geo import map_id
from travian_bot.common.models import Oasis
from travian_bot.common.schema import ParseError
from travian_bot.infra.gateway import GatewayError, Response

HALF = 200


# ---------------------------------------------------------------- 合成資料
def block(cx, cy, oases=(), w=11, h=9):
    """以 (cx, cy) 為中心的 w×h 區塊；oases＝{(x, y): (taken, animals)}。"""
    tiles = []
    for yy in range(cy + h // 2, cy - h // 2 - 1, -1):
        for xx in range(cx - w // 2, cx + w // 2 + 1):
            tiles.append({"position": {"x": xx, "y": yy}, "title": "森林", "text": ""})
    for t in tiles:
        k = (t["position"]["x"], t["position"]["y"])
        if k in oases:
            taken, animals = oases[k]
            t["title"] = "{k.bt}" if taken else "{k.fo}"
            t["text"] = "{a:r1} {a.r1} 25%"
            if animals:
                t["text"] += " {k.animals} " + "".join(
                    '<i class="unit u%d"></i><span class="value ">%d</span>' % (u, n) for u, n in animals)
    return {"tiles": tiles}


def tile_html(x, y, *, occupied=False, animals=(), mid=None, with_table=True, oasis=True):
    mid = map_id(x, y, HALF) if mid is None else mid
    title = "已被佔領的綠州" if occupied else "未被佔領的綠州"
    rows = "".join('<tr><td><img class="unit u%d"></td><td class="val">%d</td></tr>' % (u, n) for u, n in animals)
    table = ('<div id="map_details"><table id="troop_info"><tbody>%s</tbody></table></div>'
             % (rows or "<tr><td>無</td></tr>")) if with_table else ""
    village = '<div id="village_info"><a href="/profile/7">X</a></div>' if occupied else ""
    return ('<div id="tileDetails" class="%s oasis-3"><h1 class="titleInHeader">%s (%d|%d)</h1>'
            '<a data-centermap="1" href="/karte.php?x=%d&y=%d&targetMapId=%d">c</a>%s%s'
            '<table id="distribution"><tr><td><i class="r1"></i></td><td class="val">25%%</td></tr></table></div>'
            % ("oasis" if oasis else "village", title, x, y, x, y, mid, table, village))


class FakeGW:
    base_url = "https://example.invalid"

    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def request(self, method, path, *, headers=None, data=None):
        self.calls.append((method, path, headers, data))
        r = self.handler(method, path, headers, data)
        if isinstance(r, Exception):
            raise r
        return r


def ok(obj):
    return Response(200, True, obj if isinstance(obj, str) else json.dumps(obj))


# ---------------------------------------------------------------- fetch_block
class FetchBlock(unittest.TestCase):
    def test_request_shape(self):
        gw = FakeGW(lambda *a: ok({"tiles": []}))
        self.assertEqual(fetch_block(gw, 3, -4, map_half=HALF), {"tiles": []})
        m, path, hdr, data = gw.calls[0]
        self.assertEqual((m, path), ("POST", "/api/v1/map/position"))
        self.assertEqual(data, {"data": {"x": 3, "y": -4, "zoomLevel": 1, "ignorePositions": []}})
        self.assertEqual(hdr["X-Requested-With"], "XMLHttpRequest")
        self.assertEqual(hdr["Referer"], "https://example.invalid/karte.php")

    def test_wraps_and_zoom(self):
        gw = FakeGW(lambda *a: ok({"tiles": []}))
        fetch_block(gw, 201, -201, map_half=HALF, zoom=2)
        d = gw.calls[0][3]["data"]
        self.assertEqual((d["x"], d["y"], d["zoomLevel"]), (-200, 200, 2))

    def test_http_error(self):
        for body in ("", '{"tiles": []}'):         # 即使本文是合法 JSON，非 2xx 也不能用
            with self.assertRaises(OasisExecError):
                fetch_block(FakeGW(lambda *a, b=body: Response(500, False, b)), 0, 0, map_half=HALF)

    def test_not_json_and_not_object(self):
        for body in ("<html>", "[1]", '"x"'):
            with self.assertRaises(OasisExecError):
                fetch_block(FakeGW(lambda *a, b=body: Response(200, True, b)), 0, 0, map_half=HALF)

    def test_gateway_error_propagates(self):
        with self.assertRaises(GatewayError):
            fetch_block(FakeGW(lambda *a: GatewayError("x")), 0, 0, map_half=HALF)

    def test_bad_args(self):
        gw = FakeGW(lambda *a: ok({}))
        for kw in (dict(x="0", y=0, map_half=HALF), dict(x=0, y=0, map_half=0),
                   dict(x=0, y=0, map_half=HALF, zoom=0), dict(x=True, y=0, map_half=HALF)):
            with self.assertRaises(ValueError):
                fetch_block(gw, **kw)
        self.assertEqual(gw.calls, [])


# ---------------------------------------------------------------- scan
WORLD = {(0, 0): (False, ()), (4, 3): (False, ((31, 5),)), (-9, 2): (True, ()), (12, 5): (False, ())}


def world_fetch(log):
    def f(gw, x, y, *, map_half, zoom):
        log.append((x, y))
        return block(x, y, WORLD)
    return f


class Scan(unittest.TestCase):
    def run_scan(self, radius, **kw):
        log, slept = [], []
        res = scan(None, (0, 0), radius, map_half=HALF, sleep=slept.append, fetch=world_fetch(log), **kw)
        return res, log, slept

    def test_center_first_and_request_count(self):
        res, log, slept = self.run_scan(5)
        self.assertEqual(len(log), 9)               # 11×9 區塊：步距 10×8，radius 5 → 3×3
        self.assertEqual(log[0], (0, 0))
        self.assertEqual(len(slept), 8)
        self.assertTrue(all(s == 0.5 for s in slept))

    def test_requests_ordered_nearest_first(self):
        _, log, _ = self.run_scan(15)
        d = [abs(x) + abs(y) for x, y in log]
        self.assertEqual(d, sorted(d))

    def test_overlap_deduped(self):
        world = {(5, 0): (False, ()), (0, 4): (False, ())}      # 在相鄰區塊的重疊列／欄上
        res = scan(None, (0, 0), 15, map_half=HALF, sleep=lambda s: None,
                   fetch=lambda gw, x, y, *, map_half, zoom: block(x, y, world))
        self.assertEqual(sorted((o.x, o.y) for o in res), [(0, 4), (5, 0)])

    def test_first_block_not_refetched(self):
        gw_log = []
        gw = FakeGW(lambda m, p, h, d: ok(block(d["data"]["x"], d["data"]["y"], WORLD)))
        scan(gw, (0, 0), 5, map_half=HALF, sleep=gw_log.append)
        self.assertEqual(len(gw.calls), 9)
        self.assertEqual(gw.calls[0][3]["data"]["x"], 0)

    def test_dedup_and_contents(self):
        res, _, _ = self.run_scan(15)
        got = {(o.x, o.y): o for o in res}
        self.assertEqual(len(res), len(got))        # 重疊格子只出現一次
        self.assertEqual(set(got), set(WORLD))
        self.assertEqual(got[(4, 3)].animals, ((31, 5),))
        self.assertTrue(got[(-9, 2)].taken)
        self.assertFalse(got[(0, 0)].taken)
        self.assertEqual(got[(0, 0)].bonuses, ((0, 25),))

    def test_max_requests_exceeded(self):
        log = []
        with self.assertRaises(OasisExecError):
            scan(None, (0, 0), 15, map_half=HALF, max_requests=24, sleep=lambda s: None, fetch=world_fetch(log))
        self.assertEqual(len(log), 1)               # 只有量範圍那一次

    def test_exactly_max_requests_ok(self):
        res, log, _ = self.run_scan(15, max_requests=25)
        self.assertEqual(len(log), 25)

    def test_span_too_small(self):
        for w, h in ((2, 9), (11, 2), (0, 0)):
            grid = {"tiles": [{"position": {"x": i, "y": j}, "title": "森林", "text": ""}
                              for i in range(w) for j in range(h)]}
            fetch = lambda gw, x, y, *, map_half, zoom, g=grid: g
            with self.assertRaises(OasisExecError):
                scan(None, (0, 0), 5, map_half=HALF, max_requests=10000, sleep=lambda s: None, fetch=fetch)

    def test_malformed_tiles(self):
        for data in ({}, {"tiles": "x"}, {"tiles": [1]}, {"tiles": [{"position": {"x": "a"}}]}):
            with self.assertRaises(OasisExecError):
                scan(None, (0, 0), 5, map_half=HALF, sleep=lambda s: None, fetch=lambda *a, **k: data)

    def test_parse_error_propagates(self):
        bad = block(0, 0, ())
        bad["tiles"][0] = {"position": {"x": 0, "y": 0}, "title": "?", "text": "{a:r1} {a.r1} 25%"}   # 分不出佔領
        with self.assertRaises(ParseError):
            scan(None, (0, 0), 5, map_half=HALF, sleep=lambda s: None, fetch=lambda *a, **k: bad)

    def test_bad_args(self):
        base = dict(map_half=HALF, sleep=lambda s: None, fetch=world_fetch([]))
        for center, radius, extra in (((0,), 5, {}), (("0", 0), 5, {}), ((0, 0), 0, {}), ((0, 0), 5, {"max_requests": 0}),
                                      ((0, 0), 5, {"map_half": 0})):
            kw = dict(base, **extra)
            with self.assertRaises(ValueError):
                scan(None, center, radius, **kw)

    def test_wraps_far_centers(self):
        log = []
        scan(None, (198, 0), 5, map_half=HALF, sleep=lambda s: None, fetch=world_fetch(log))
        self.assertIn((208, 0), log)                # scan 不環繞；環繞在 fetch_block 做
        gw = FakeGW(lambda m, p, h, d: ok({"tiles": []}))
        fetch_block(gw, 208, 0, map_half=HALF)
        self.assertEqual(gw.calls[0][3]["data"]["x"], -193)


# ---------------------------------------------------------------- verify_oasis
def tile_gw(html):
    return FakeGW(lambda m, p, h, d: ok({"html": html}))


class VerifyOasis(unittest.TestCase):
    def test_safe(self):
        gw = tile_gw(tile_html(3, -4))
        info = verify_oasis(gw, Oasis(x=3, y=-4, kind="wood25", safe=None), map_half=HALF)
        self.assertTrue(info.safe)
        self.assertEqual((info.x, info.y, info.map_id), (3, -4, map_id(3, -4, HALF)))
        m, path, hdr, data = gw.calls[0]
        self.assertEqual((m, path, data), ("POST", "/api/v1/map/tile-details", {"x": 3, "y": -4}))

    def test_animals_not_safe(self):
        info = verify_oasis(tile_gw(tile_html(3, -4, animals=((31, 5),))), Oasis(3, -4, "w", None), map_half=HALF)
        self.assertFalse(info.safe)
        self.assertEqual(info.animals, {31: 5})

    def test_occupied_not_safe(self):
        info = verify_oasis(tile_gw(tile_html(3, -4, occupied=True, with_table=False)), Oasis(3, -4, "w", None),
                            map_half=HALF)
        self.assertFalse(info.safe)

    def test_unknown_animals_not_safe(self):
        info = verify_oasis(tile_gw(tile_html(3, -4, with_table=False)), Oasis(3, -4, "w", None), map_half=HALF)
        self.assertIsNone(info.animals)
        self.assertFalse(info.safe)

    def test_coord_mismatch(self):
        with self.assertRaises(OasisExecError):
            verify_oasis(tile_gw(tile_html(5, -4)), Oasis(3, -4, "w", None), map_half=HALF)

    def test_coord_mismatch_even_if_map_id_matches_request(self):
        with self.assertRaises(OasisExecError):     # map_id 對得上要求的格子，但頁面座標是別格
            verify_oasis(tile_gw(tile_html(5, -4, mid=map_id(3, -4, HALF))), Oasis(3, -4, "w", None), map_half=HALF)

    def test_map_id_mismatch(self):
        with self.assertRaises(OasisExecError):
            verify_oasis(tile_gw(tile_html(3, -4, mid=map_id(3, -4, HALF) + 1)), Oasis(3, -4, "w", None), map_half=HALF)

    def test_map_half_changes_expected_id(self):
        with self.assertRaises(OasisExecError):     # 頁面是 half=200 的 id，用 half=100 核對必須不符
            verify_oasis(tile_gw(tile_html(3, -4)), Oasis(3, -4, "w", None), map_half=100)

    def test_http_error_and_bad_body(self):
        with self.assertRaises(OasisExecError):     # 非 2xx 即使本文是好的也不用
            verify_oasis(FakeGW(lambda *a: Response(403, False, json.dumps({"html": tile_html(3, -4)}))),
                         Oasis(3, -4, "w", None), map_half=HALF)
        for body in ("<html>", '{"x": 1}', '{"html": 5}', "[]"):
            with self.assertRaises(OasisExecError):
                verify_oasis(FakeGW(lambda *a, b=body: Response(200, True, b)), Oasis(3, -4, "w", None), map_half=HALF)

    def test_parse_error_and_gateway_error_propagate(self):
        with self.assertRaises(ParseError):
            verify_oasis(tile_gw(tile_html(3, -4, oasis=False)), Oasis(3, -4, "w", None), map_half=HALF)
        with self.assertRaises(GatewayError):
            verify_oasis(FakeGW(lambda *a: GatewayError("x")), Oasis(3, -4, "w", None), map_half=HALF)

    def test_bad_target(self):
        for bad in (None, (1, 2), object()):
            with self.assertRaises(ValueError):
                verify_oasis(tile_gw(""), bad, map_half=HALF)
        with self.assertRaises(ValueError):
            verify_oasis(tile_gw(""), Oasis(3, -4, "w", None), map_half=0)


# ---------------------------------------------------------------- 分層（§4.1：actions 可依賴 common／parsers／infra）
class Layers(unittest.TestCase):
    def test_imports(self):
        here = os.path.dirname(OE.__file__)
        for name in ("oasis_exec.py", "village_switch.py"):
            with open(os.path.join(here, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for n in ast.walk(tree):
                mods = []
                if isinstance(n, ast.ImportFrom):
                    mods = [("." * n.level) + (n.module or "")]
                elif isinstance(n, ast.Import):
                    mods = [a.name for a in n.names]
                for m in mods:
                    for bad in ("domain", "app", "dispatch", "oasis_store", "hide_troops", "playwright", "gspread", "os", "environ"):
                        self.assertNotIn(bad, m.split("."), f"{name} 不該 import {m}")
                    self.assertFalse(m.startswith(".") and m.split(".")[-1] in {"hide_exec", "hero_exec", "build_exec"},
                                     f"{name} 不可依賴其他 actions：{m}")


if __name__ == "__main__":
    unittest.main()
