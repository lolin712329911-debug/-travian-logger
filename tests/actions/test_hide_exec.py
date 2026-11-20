# -*- coding: utf-8 -*-
"""ac-06 hide_exec 測試。確認頁／概況頁是依 S17d／S6d 的結構合成的（非真實樣本 ✗）；
第三步表單與 S17d 真實確認頁的逐欄比對在交接區塊記錄（離線一次性核對，不進 repo：樣本含 token）。"""
import ast
import os
import unittest
from urllib.parse import parse_qsl

from travian_bot.actions import hide_exec as HE
from travian_bot.actions.hide_exec import confirm_matches, confirm_ok, recent_occupy, send_troops
from travian_bot.common.decisions import HideCandidate, HideDecision
from travian_bot.common.geo import map_id
from travian_bot.common.parsed import TileSafety
from travian_bot.common.schema import ParseError
from travian_bot.infra.gateway import GatewayError, Response
from travian_bot.parsers.rally import parse_send_confirm

HALF, DID, PAGE_TS, TRIP = 200, 65222, 1_000_000, 600
SECRET = "CKSUM-SECRET-123"
SCOPE = (PAGE_TS + 500, PAGE_TS + 1000)
UNITS = (("u1", 5), ("u3", 2))


# ---------------------------------------------------------------- 合成頁面
def confirm_html(x, y, *, did=DID, page_ts=PAGE_TS, trip=TRIP, units=None, hero=0, event=4, scout="", cat1="", cat2=""):
    u = {f"t{i}": 0 for i in range(1, 12)}
    u.update(units or {"t1": 5, "t3": 2})
    u["t11"] = hero
    hid = "".join(f'<input type="hidden" name="troops[0][{k}]" value="{v}" />' for k, v in u.items())
    return (f'<div><form method="post" action="/build.php?gid=16&tt=2" id="troopSendForm">'
            f'<input type="hidden" name="action" value="troopsSend/{did}/{page_ts}" />'
            f'<input type="hidden" name="eventType" value="{event}" /><input type="hidden" name="villagename" value="" />'
            f'<input type="hidden" name="x" value="{x}" /><input type="hidden" name="y" value="{y}" />'
            f'<input type="hidden" name="redeployHero" value=""/><input type="hidden" name="checksum" value="" />{hid}'
            f'<input type="hidden" name="troops[0][scoutTarget]" value="{scout}" />'
            f'<input type="hidden" name="troops[0][catapultTarget1]" value="{cat1}" />'
            f'<input type="hidden" name="troops[0][catapultTarget2]" value="{cat2}" />'
            f'<input type="hidden" name="troops[0][villageId]" value="{did}" /></form>'
            f'<table><tr><td class="troopHeadline"><span>x</span></td></tr></table>'
            f'<span id="at" class="timer" value="{page_ts + trip}"></span>'
            f'<button type="button" id="confirmSendTroops" onclick="this.disabled = true; '
            f"document.querySelector('#troopSendForm input[name=checksum]').value='{SECRET}'; "
            f'document.getElementById(\'troopSendForm\').submit(); return false;">ok</button></div>')


def overview_html(raid_map_ids=(), ts=PAGE_TS + 60):
    cells = "".join('<td class="unit">0</td>' for _ in range(11))
    tables = "".join(
        f'<h4 class="spacer">出擊軍團</h4><table class="troop_details outRaid"><thead><tr>'
        f'<td class="role"><a href="/karte.php?d=1">v</a></td>'
        f'<td class="troopHeadline"><a href="/karte.php?d={mid}">o</a></td></tr></thead>'
        f'<tbody class="infos"><tr><td><span class="timer" value="300"></span></td></tr></tbody>'
        f'<tbody class="units last"><tr>{cells}</tr></tbody></table>' for mid in raid_map_ids)
    return (f'<script>Travian.Game.timestamp = {ts};</script>'
            f'<div class="rallyPointOverviewContainer">{tables}</div>')


def tile(x, y, *, safe=True, events=()):
    return TileSafety(x=x, y=y, map_id=map_id(x, y, HALF), occupied=not safe, owner_uid=None, alliance_id=None,
                      owner_village=None, animals={} if safe else None, bonuses=(), distance=5.0, oasis_type=3,
                      occupy_events=tuple(events), safe=safe)


class FakeGW:
    def __init__(self, *, confirm=None, step3=None, overview=None, get_exc=None):
        self.confirm = confirm or (lambda f: Response(200, True, confirm_html(f["x"], f["y"])))
        self.step3 = step3 or (lambda f: Response(200, True, "<html>ok</html>"))
        self.overview = overview if overview is not None else (lambda: overview_html([map_id(3, -4, HALF)]))
        self.get_exc, self.n, self.posts, self.gets = get_exc, 0, [], []

    def request_count(self):
        return self.n

    def request(self, method, path, *, headers=None, data=None):
        self.n += 1
        assert method == "POST" and path == HE.SEND_PATH, (method, path)
        fields = dict(parse_qsl(data, keep_blank_values=True))
        self.posts.append((headers, data, fields))
        r = self.step3(fields) if "checksum" in fields else self.confirm(fields)
        if isinstance(r, Exception):
            raise r
        return r

    def get(self, path, **kw):
        self.n += 1
        self.gets.append((path, kw))
        if self.get_exc:
            raise self.get_exc
        return self.overview()

    # 第一步／第三步分開看
    def step1(self):
        return [p for p in self.posts if "checksum" not in p[2]]

    def step3_posts(self):
        return [p for p in self.posts if "checksum" in p[2]]


def cands(*pos):
    return tuple(HideCandidate(x, y, "wood25", 5.0, None, map_id=map_id(x, y, HALF)) for x, y in pos)


def decision(*pos, units=UNITS, scope=SCOPE, full=False, act=True, kind="go"):
    cs = cands(*(pos or ((3, -4),)))
    return HideDecision(act=act, chosen=cs[0] if cs else None, candidates=cs, reason="r", kind=kind, code="ok",
                        units=units, scope=scope, full=full)


def safe_all(gw, cand):
    return tile(cand.x, cand.y)


def run(gw, dec, mode="live", verify=safe_all, **kw):
    return send_troops(gw, DID, dec, mode, map_half=HALF, verify=verify, **kw)


# ---------------------------------------------------------------- 前置
class Guards(unittest.TestCase):
    def test_off_and_unknown_mode(self):
        for mode in ("off", "OFF", "bogus", None):
            gw = FakeGW()
            r = run(gw, decision(), mode)
            self.assertEqual((r.result, r.requests_used), ("skipped", 0))
            self.assertEqual(gw.n, 0)

    def test_not_a_go_decision(self):
        for dec in (decision(act=False), decision(kind="wait"), decision(kind=""),
                    HideDecision(True, None, (), "r", kind="go", units=UNITS, scope=SCOPE)):
            gw = FakeGW()
            self.assertEqual(run(gw, dec).result, "skipped")
            self.assertEqual(gw.n, 0)

    def test_bad_units_or_scope_fail_without_requests(self):
        bad_units = [(), (("hero", 1),), (("u1", 0),), (("u11", 1),), (("u1", 1), ("u1", 2)), (("u1", True),), (("u1", "5"),)]
        for u in bad_units:
            gw = FakeGW()
            r = run(gw, decision(units=u))
            self.assertEqual(r.result, "failed", u)
            self.assertEqual(gw.n, 0)
        gw = FakeGW()
        self.assertEqual(run(gw, decision(scope=())).result, "failed")
        self.assertEqual(run(gw, decision(scope=(1.5,))).result, "failed")
        self.assertEqual(gw.n, 0)

    def test_bad_did_or_map_half(self):
        gw = FakeGW()
        self.assertEqual(send_troops(gw, 0, decision(), "live", map_half=HALF, verify=safe_all).result, "failed")
        self.assertEqual(send_troops(gw, DID, decision(), "live", map_half=0, verify=safe_all).result, "failed")
        self.assertEqual(gw.n, 0)


# ---------------------------------------------------------------- 主流程
class Flow(unittest.TestCase):
    def test_dry_stops_at_confirm_page(self):
        gw = FakeGW()
        r = run(gw, decision(), "dry")
        self.assertEqual(r.result, "dry")
        self.assertIsNone(r.verified)
        self.assertEqual(len(gw.step1()), 1)
        self.assertEqual(gw.step3_posts(), [])
        self.assertEqual(gw.gets, [])
        self.assertEqual(r.requests_used, 1)

    def test_live_happy_path(self):
        gw = FakeGW()
        r = run(gw, decision(), "live")
        self.assertEqual((r.result, r.verified, r.requests_used), ("ok", True, 3))
        h, body, f1 = gw.step1()[0]
        self.assertEqual(h["Content-Type"], "application/x-www-form-urlencoded")
        self.assertEqual(f1, {"troop[t1]": "5", "troop[t3]": "2", "villagename": "", "x": "3", "y": "-4",
                              "eventType": "4", "ok": "ok"})
        _, body3, f3 = gw.step3_posts()[0]
        self.assertEqual(f3["checksum"], SECRET)
        self.assertEqual(f3["action"], f"troopsSend/{DID}/{PAGE_TS}")
        self.assertEqual((f3["troops[0][t1]"], f3["troops[0][t3]"], f3["troops[0][t11]"]), ("5", "2", "0"))
        self.assertEqual(f3["troops[0][villageId]"], str(DID))
        self.assertEqual(gw.gets, [(HE.OVERVIEW_PATH, {"raw": True})])
        self.assertNotIn(SECRET, r.detail)

    def test_step3_body_equals_confirm_form_fields(self):
        """第三步欄位＝確認頁 form 的 hidden 欄位（含順序），checksum 取自按鈕 onclick。"""
        conf = parse_send_confirm(confirm_html(3, -4))
        got = parse_qsl(HE._step3_body(conf), keep_blank_values=True)
        names = [k for k, _ in got]
        self.assertEqual(names[:7], ["action", "eventType", "villagename", "x", "y", "redeployHero", "checksum"])
        self.assertEqual(names[7:18], [f"troops[0][t{i}]" for i in range(1, 12)])
        self.assertEqual(names[18:], ["troops[0][scoutTarget]", "troops[0][catapultTarget1]",
                                      "troops[0][catapultTarget2]", "troops[0][villageId]"])
        self.assertEqual(len(got), 22)

    def test_live_no_raid_in_overview_is_failed(self):
        gw = FakeGW(overview=lambda: overview_html([]))
        r = run(gw, decision())
        self.assertEqual((r.result, r.verified), ("failed", False))
        self.assertEqual(len(gw.step3_posts()), 1)           # 不重送

    def test_live_overview_other_target_is_failed(self):
        gw = FakeGW(overview=lambda: overview_html([map_id(9, 9, HALF)]))
        self.assertEqual(run(gw, decision()).result, "failed")

    def test_overview_reread_fails_is_unknown(self):
        for exc in (GatewayError("x"),):
            gw = FakeGW(get_exc=exc)
            r = run(gw, decision())
            self.assertEqual((r.result, r.verified), ("failed", None))
            self.assertIn("結果不明", r.detail)
            self.assertEqual(len(gw.step3_posts()), 1)
        gw = FakeGW(overview=lambda: "<html>不是概況</html>")
        self.assertEqual(run(gw, decision()).verified, None)

    def test_step3_error_but_overview_shows_raid_is_ok(self):
        gw = FakeGW(step3=lambda f: GatewayError("POST /build.php 失敗：TimeoutError"))
        r = run(gw, decision())
        self.assertEqual((r.result, r.verified), ("ok", True))
        self.assertEqual(len(gw.step3_posts()), 1)

    def test_step3_http_error_and_no_raid_mentions_it(self):
        gw = FakeGW(step3=lambda f: Response(500, False, ""), overview=lambda: overview_html([]))
        r = run(gw, decision())
        self.assertEqual(r.result, "failed")
        self.assertIn("HTTP 500", r.detail)

    def test_token_never_in_any_detail(self):
        for gw, mode in ((FakeGW(), "live"), (FakeGW(overview=lambda: overview_html([])), "live"), (FakeGW(), "dry"),
                         (FakeGW(get_exc=GatewayError("x")), "live")):
            self.assertNotIn(SECRET, run(gw, decision(), mode).detail)

    def test_detail_length_cap(self):
        gw = FakeGW()
        r = run(gw, decision(*[(i, 0) for i in range(1, 13)]), "live", verify=lambda g, c: tile(c.x, c.y, safe=False))
        self.assertLessEqual(len(r.detail), 300)


# ---------------------------------------------------------------- 候選篩選
class Candidates(unittest.TestCase):
    def test_unsafe_then_next(self):
        def verify(gw, c):
            return tile(c.x, c.y, safe=(c.x != 3))
        gw = FakeGW(overview=lambda: overview_html([map_id(5, 6, HALF)]))
        r = run(gw, decision((3, -4), (5, 6)), verify=verify)
        self.assertEqual(r.result, "ok")
        self.assertEqual((gw.step1()[0][2]["x"], gw.step1()[0][2]["y"]), ("5", "6"))

    def test_recent_occupy_skipped(self):
        def verify(gw, c):
            return tile(c.x, c.y, events=("昨天, 15:39",) if c.x == 3 else ("2 日前, 19:28", "03.11.26, 07:35"))
        gw = FakeGW(overview=lambda: overview_html([map_id(5, 6, HALF)]))
        r = run(gw, decision((3, -4), (5, 6)), verify=verify)
        self.assertEqual(r.result, "ok")
        self.assertEqual(gw.step1()[0][2]["x"], "5")

    def test_verify_exceptions_skip_candidate(self):
        for exc in (GatewayError("x"), ParseError("tile", "r"), RuntimeError("OasisExecError"), ValueError("v")):
            def verify(gw, c, exc=exc):
                if c.x == 3:
                    raise exc
                return tile(c.x, c.y)
            gw = FakeGW(overview=lambda: overview_html([map_id(5, 6, HALF)]))
            self.assertEqual(run(gw, decision((3, -4), (5, 6)), verify=verify).result, "ok", exc)

    def test_all_fail_is_skipped_with_no_step1(self):
        gw = FakeGW()
        r = run(gw, decision((3, -4), (5, 6)), verify=lambda g, c: tile(c.x, c.y, safe=False))
        self.assertEqual(r.result, "skipped")
        self.assertEqual(gw.n, 0)

    def test_candidate_map_id_mismatch_skipped(self):
        bad = HideCandidate(3, -4, "k", 1.0, None, map_id=1)
        good = cands((5, 6))[0]
        dec = HideDecision(True, bad, (bad, good), "r", kind="go", code="ok", units=UNITS, scope=SCOPE)
        gw = FakeGW(overview=lambda: overview_html([map_id(5, 6, HALF)]))
        self.assertEqual(run(gw, dec).result, "ok")
        self.assertEqual(gw.step1()[0][2]["x"], "5")

    def test_candidate_without_map_id_is_computed(self):
        c = HideCandidate(3, -4, "k", 1.0, None)
        dec = HideDecision(True, c, (c,), "r", kind="go", code="ok", units=UNITS, scope=SCOPE)
        self.assertEqual(run(FakeGW(), dec).result, "ok")

    def test_max_confirm_and_max_checks(self):
        gw = FakeGW(confirm=lambda f: Response(500, False, ""))
        r = run(gw, decision((1, 0), (2, 0), (3, 0), (4, 0)), max_confirm=2)
        self.assertEqual(len(gw.step1()), 2)
        self.assertEqual(r.result, "skipped")
        seen = []
        gw = FakeGW()
        run(gw, decision((1, 0), (2, 0), (3, 0)), verify=lambda g, c: (seen.append(c.x), tile(c.x, c.y, safe=False))[1],
            max_checks=2)
        self.assertEqual(seen, [1, 2])
        self.assertEqual(gw.n, 0)

    def test_unsafe_checks_do_not_use_confirm_quota(self):
        def verify(gw, c):
            return tile(c.x, c.y, safe=(c.x == 4))
        gw = FakeGW(overview=lambda: overview_html([map_id(4, 0, HALF)]))
        self.assertEqual(run(gw, decision((1, 0), (2, 0), (3, 0), (4, 0)), verify=verify, max_confirm=1).result, "ok")


# ---------------------------------------------------------------- 第一步／確認頁
class Confirm(unittest.TestCase):
    def reject(self, factory):
        gw = FakeGW(confirm=factory)
        r = run(gw, decision())
        self.assertEqual(r.result, "skipped", r.detail)
        self.assertEqual(gw.step3_posts(), [])
        return r

    def test_http_error_and_parse_error(self):
        self.reject(lambda f: Response(403, False, ""))
        self.reject(lambda f: Response(200, True, "<html>不是確認頁</html>"))
        self.reject(lambda f: GatewayError("x"))

    def test_hero_not_zero(self):
        self.reject(lambda f: Response(200, True, confirm_html(3, -4, hero=1)))

    def test_units_mismatch(self):
        self.reject(lambda f: Response(200, True, confirm_html(3, -4, units={"t1": 5, "t3": 3})))
        self.reject(lambda f: Response(200, True, confirm_html(3, -4, units={"t1": 5, "t3": 2, "t4": 1})))

    def test_target_mismatch(self):
        self.reject(lambda f: Response(200, True, confirm_html(4, -4)))
        self.reject(lambda f: Response(200, True, confirm_html(3, -5)))

    def test_event_type_must_be_raid(self):
        for ev in (3, 5):
            self.reject(lambda f, ev=ev: Response(200, True, confirm_html(3, -4, event=ev)))

    def test_wrong_village(self):
        self.reject(lambda f: Response(200, True, confirm_html(3, -4, did=DID + 1)))

    def test_scout_or_catapult_targets(self):
        for kw in ({"scout": "1"}, {"cat1": "7"}, {"cat2": "7"}):
            self.reject(lambda f, kw=kw: Response(200, True, confirm_html(3, -4, **kw)))

    def test_no_chinese_literal_dependency(self):
        """標題文字不影響判斷（舊版靠「掠奪」二字）。"""
        html = confirm_html(3, -4).replace("<span>x</span>", "<span>Raid Oasis</span>")
        self.assertEqual(run(FakeGW(confirm=lambda f: Response(200, True, html)), decision()).result, "ok")

    def test_late_and_trip_checks_via_flow(self):
        # 單程 4000：返回太晚沒問題，但送出時間（頁面＋45）已超過第一波 → 來不及
        self.reject(lambda f: Response(200, True, confirm_html(3, -4, page_ts=SCOPE[0] - 10)))
        # 單程 100：往返 200 秒，第一波（+500）在返回前就到 → 不派
        self.reject(lambda f: Response(200, True, confirm_html(3, -4, trip=100)))

    def test_full_requires_all_waves(self):
        # 單程 300：送出 PAGE+45、返回 PAGE+645；scope 第一波 +500 撐得過，第二波 +1000 撐不過 → n=1
        slow = lambda f: Response(200, True, confirm_html(3, -4, trip=300))
        gw = FakeGW(confirm=slow)
        self.assertEqual(run(gw, decision(full=True)).result, "skipped")
        self.assertEqual(gw.step3_posts(), [])
        gw = FakeGW(confirm=slow)
        r = run(gw, decision(full=False))
        self.assertEqual(r.result, "ok")
        self.assertIn("1/2", r.detail)

    def test_send_delay_and_margin_are_parameters(self):
        self.assertEqual(run(FakeGW(), decision(), send_delay_s=45).result, "ok")
        self.assertEqual(run(FakeGW(), decision(), send_delay_s=500).result, "skipped")   # 送出時第一波已到
        self.assertEqual(run(FakeGW(), decision(), margin=2000).result, "skipped")


# ---------------------------------------------------------------- 純函式
def conf(**kw):
    return parse_send_confirm(confirm_html(3, -4, **kw))


class Pure(unittest.TestCase):
    def test_confirm_ok_boundaries(self):
        c = conf()                                           # 頁面 PAGE_TS、單程 600、delay 45 → 送出 +45、返回 +1245
        self.assertEqual(confirm_ok(c, [PAGE_TS + 46], send_delay_s=45)[:2], (True, 1))
        self.assertFalse(confirm_ok(c, [PAGE_TS + 45], send_delay_s=45)[0])               # 送出＝第一波：不行
        self.assertTrue(confirm_ok(c, [PAGE_TS + 1214], margin=30)[0])                    # a < back-margin（1215）
        self.assertFalse(confirm_ok(c, [PAGE_TS + 1215], margin=30)[0])                   # a == back-margin：不行
        self.assertEqual(confirm_ok(c, [PAGE_TS + 500, PAGE_TS + 1214, PAGE_TS + 1215])[1], 2)
        self.assertEqual(confirm_ok(c, [PAGE_TS + 1214, PAGE_TS + 500])[1], 2)             # 不要求已排序
        self.assertFalse(confirm_ok(c, [])[0])

    def test_confirm_ok_zero_trip(self):
        c = parse_send_confirm(confirm_html(3, -4, trip=0).replace(f'value="{PAGE_TS}"', f'value="{PAGE_TS}"'))
        self.assertFalse(confirm_ok(c, SCOPE)[0])

    def test_confirm_matches_ok_and_each_failure(self):
        u = {"u1": 5, "u3": 2}
        self.assertEqual(confirm_matches(conf(), u, (3, -4), DID), (True, "ok"))
        self.assertFalse(confirm_matches(conf(), u, (3, -4), DID + 1)[0])
        self.assertFalse(confirm_matches(conf(hero=1), u, (3, -4), DID)[0])
        self.assertFalse(confirm_matches(conf(), {"u1": 5}, (3, -4), DID)[0])
        self.assertFalse(confirm_matches(conf(), u, (3, -5), DID)[0])
        self.assertFalse(confirm_matches(conf(event=5), u, (3, -4), DID)[0])

    def test_recent_occupy(self):
        self.assertTrue(recent_occupy(["昨天, 15:39"]))
        self.assertTrue(recent_occupy(["x", "5 分鐘前"]))
        self.assertFalse(recent_occupy(["2 日前, 19:28", "03.11.26, 07:35"]))      # S15a 的其餘兩筆
        self.assertFalse(recent_occupy([]))

    def test_short_caps_length(self):
        self.assertEqual(len(HE._short(["x" * 500])), 280)
        self.assertEqual(HE._short(["a", "b"]), "a；b")

    def test_unit_key_mapping(self):
        f = dict(parse_qsl(HE._step1_body({"u10": 1, "u2": 4}, (-7, 8)), keep_blank_values=True))
        self.assertEqual((f["troop[t10]"], f["troop[t2]"], f["x"], f["y"]), ("1", "4", "-7", "8"))


class Layers(unittest.TestCase):
    def test_imports(self):
        with open(HE.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for n in ast.walk(tree):
            mods = ([("." * n.level) + (n.module or "")] if isinstance(n, ast.ImportFrom)
                    else [a.name for a in n.names] if isinstance(n, ast.Import) else [])
            for m in mods:
                parts = m.split(".")
                for bad in ("domain", "app", "dispatch", "oasis_store", "hide_troops", "playwright", "gspread", "os",
                            "bs4", "oasis_exec", "hero_exec", "village_switch"):
                    self.assertNotIn(bad, parts, f"hide_exec 不該 import {m}")


if __name__ == "__main__":
    unittest.main()
