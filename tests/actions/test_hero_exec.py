# -*- coding: utf-8 -*-
"""tests/actions/test_hero_exec.py（ac-05）v0.1（A5a）。
解析函式（parse_hero_status／parse_adventures）用 mock 換成固定回傳，只測本層的核對與流程；解析本身在 tests/parsers。"""
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from tests.fakes_a5a import BASE, FakePage, FakeResp, make_gateway
from travian_bot.actions import hero_exec as HE
from travian_bot.common.modes import Mode
from travian_bot.common.parsed import Adventure, HeroState
from travian_bot.common.schema import ParseError
from travian_bot.infra.gateway import GatewayError

PATH = "/hero/adventures"


def hero(**kw):
    base = dict(status=None, at_home=True, health_pct=100, exp_pct=10, adventures_count=2, regenerating=False,
                home_did=7, in_village_did=None, adventure_no=None, arrival_in_s=None, arrival_at=None,
                difficulty_bonus=False, duration_bonus=False)
    base.update(kw)
    return HeroState(**base)


def adv(number=11, distance=4.2, place="grassland", difficulty=1, duration_s=600, icon="normal", clickable=True):
    return Adventure(number=number, distance=distance, place=place, difficulty=difficulty, hard=(difficulty == 0),
                     duration_s=duration_s, x=None, y=None, icon=icon, clickable=clickable)


WANT = adv()
GOING = hero(status=50, at_home=False, adventure_no=11, arrival_in_s=540)


def setup(hero_seq, advs, page=None):
    gw, page, router = make_gateway(pages={PATH: "<html>adv</html>"}, routes={("GET", PATH): [FakeResp(200, "raw")]},
                                    page=page)
    side = list(hero_seq)
    p1 = mock.patch.object(HE, "parse_hero_status", side_effect=side)
    p2 = mock.patch.object(HE, "parse_adventures", return_value=advs)
    return gw, page, router, p1, p2


def click(want=WANT, hero_seq=None, advs=None, mode=Mode.LIVE, page=None):
    gw, page, router, p1, p2 = setup(hero_seq if hero_seq is not None else [hero(), GOING],
                                     advs if advs is not None else (adv(10, place="lake"), WANT), page)
    with p1 as ph, p2:
        r = HE.click_adventure(gw, want, mode)
    return r, page, router, gw, ph


class ReadHeroTest(unittest.TestCase):
    def test_uses_raw_http_not_browser(self):
        gw, page, router = make_gateway(pages={PATH: "x"}, routes={("GET", PATH): [FakeResp(200, "raw")]})
        with mock.patch.object(HE, "parse_hero_status", return_value="H") as p:
            self.assertEqual(HE.read_hero(gw), "H")
        p.assert_called_once_with("raw")
        self.assertEqual(page.visited, [])                  # 沒開瀏覽器
        self.assertEqual(router.seq(), [("GET", PATH)])


class ModeTest(unittest.TestCase):
    def test_off_no_requests(self):
        r, page, router, gw, _ = click(mode=Mode.OFF)
        self.assertEqual((r.result, r.requests_used, page.visited, router.calls, page.clicks), ("skipped", 0, [], [], []))

    def test_unknown_mode_is_off(self):
        for bad in ("on", None, 2):
            r, page, *_ = click(mode=bad)
            self.assertEqual((r.result, page.visited, page.clicks), ("skipped", [], []), repr(bad))

    def test_dry_checks_but_does_not_click(self):
        r, page, router, gw, _ = click(mode=Mode.DRY)
        self.assertEqual((r.result, r.verified), ("dry", None))
        self.assertEqual((page.clicks, len(page.visited), router.calls), ([], 1, []))
        self.assertEqual(r.requests_used, 1)
        self.assertIn("第 2 列", r.detail)


class PreClickChecksTest(unittest.TestCase):
    def assert_not_clicked(self, r, result="skipped"):
        self.assertEqual(r.result, result)
        self.assertEqual(r.verified, None)

    def test_reread_failure_failed_no_click(self):
        gw, page, router, p1, p2 = setup([], ())
        with mock.patch.object(HE, "parse_hero_status", side_effect=ParseError("hero", "壞")), p2:
            r = HE.click_adventure(gw, WANT, Mode.LIVE)
        self.assert_not_clicked(r, "failed")
        self.assertEqual(page.clicks, [])

    def test_page_error_failed_no_click(self):
        page = FakePage({PATH: GatewayError("down")})
        gw, page, router, p1, p2 = setup([], (), page)
        with p1, p2:
            r = HE.click_adventure(gw, WANT, Mode.LIVE)
        self.assert_not_clicked(r, "failed")
        self.assertEqual(page.clicks, [])

    def test_adventures_parse_error_failed(self):
        gw, page, router, p1, p2 = setup([hero()], ())
        with p1, mock.patch.object(HE, "parse_adventures", side_effect=ParseError("hero", "表格與 JSON 不一致")):
            r = HE.click_adventure(gw, WANT, Mode.LIVE)
        self.assert_not_clicked(r, "failed")
        self.assertEqual(page.clicks, [])

    def test_hero_not_home_skipped(self):
        for name, h in {"at_home False": hero(at_home=False), "at_home None": hero(at_home=None),
                        "adventure_no": hero(adventure_no=3), "arrival_in_s": hero(arrival_in_s=30)}.items():
            with self.subTest(name):
                r, page, *_ = click(hero_seq=[h])
                self.assert_not_clicked(r)
                self.assertEqual(page.clicks, [])

    def test_difficulty_bonus_skipped(self):
        r, page, *_ = click(hero_seq=[hero(difficulty_bonus=True)])
        self.assert_not_clicked(r)
        self.assertEqual(page.clicks, [])

    def test_adventure_gone_skipped(self):
        r, page, *_ = click(advs=(adv(10), adv(12)))
        self.assert_not_clicked(r)
        self.assertIn("清單", r.detail)
        self.assertEqual(page.clicks, [])

    def test_row_changed_skipped(self):
        changed = {"distance": adv(distance=4.3), "place": adv(place="lake"), "difficulty": adv(difficulty=2),
                   "duration": adv(duration_s=601), "icon": adv(icon="hard")}
        for name, a in changed.items():
            with self.subTest(name):
                r, page, *_ = click(advs=(a,))
                self.assert_not_clicked(r)
                self.assertIn("不同", r.detail)
                self.assertEqual(page.clicks, [])

    def test_icon_none_on_either_side_is_not_a_difference(self):
        for a, w in ((adv(icon=None), WANT), (adv(icon="normal"), adv(icon=None))):
            r, page, *_ = click(want=w, advs=(a,), mode=Mode.DRY)
            self.assertEqual(r.result, "dry")

    def test_tiny_distance_float_noise_is_same(self):
        r, *_ = click(advs=(adv(distance=4.2 + 1e-12),), mode=Mode.DRY)
        self.assertEqual(r.result, "dry")

    def test_not_clickable_skipped(self):
        for c in (False, None):
            with self.subTest(c):
                r, page, *_ = click(advs=(adv(clickable=c),))
                self.assert_not_clicked(r)
                self.assertEqual(page.clicks, [])


class LiveTest(unittest.TestCase):
    def test_click_selector_uses_row_position(self):
        r, page, router, gw, _ = click(advs=(adv(10, place="lake"), adv(12, place="lake"), WANT))
        self.assertEqual(page.clicks, [("table.adventureList tbody tr:nth-child(3) td.button button", 0)])
        self.assertEqual((r.result, r.verified), ("ok", True))

    def test_ok_flow_and_counts(self):
        r, page, router, gw, ph = click()
        self.assertEqual(page.clicks, [("table.adventureList tbody tr:nth-child(2) td.button button", 0)])
        self.assertEqual(r.requests_used, 3)                 # 渲染頁、點擊、重讀
        self.assertEqual(r.requests_used, gw.request_count())
        self.assertEqual(ph.call_count, 2)
        self.assertIn("540", r.detail)

    def test_ok_without_eta(self):
        r, *_ = click(hero_seq=[hero(), hero(status=50, at_home=False, adventure_no=11)])
        self.assertEqual((r.result, r.verified), ("ok", True))
        self.assertNotIn("抵達", r.detail)

    def test_click_error_failed_no_reread_no_retry(self):
        page = FakePage(click_error=RuntimeError("x"))
        r, page, router, gw, ph = click(page=page)
        self.assertEqual((r.result, r.verified), ("failed", None))
        self.assertEqual(len(page.clicks), 1)
        self.assertEqual((ph.call_count, router.calls), (1, []))   # 沒有點擊後重讀
        self.assertIn("不重試", r.detail)

    def test_reread_error_failed_unverified(self):
        r, page, *_ = click(hero_seq=[hero(), GatewayError("boom")])
        self.assertEqual((r.result, r.verified), ("failed", None))
        self.assertEqual(len(page.clicks), 1)

    def test_not_departed_failed_verified_false(self):
        cases = {"仍在家": hero(status=None), "status 不是 50": hero(status=9, at_home=False, adventure_no=11),
                 "編號不同": hero(status=50, at_home=False, adventure_no=99)}
        for name, h in cases.items():
            with self.subTest(name):
                r, page, *_ = click(hero_seq=[hero(), h])
                self.assertEqual((r.result, r.verified), ("failed", False))
                self.assertEqual(len(page.clicks), 1)


if __name__ == "__main__":
    unittest.main()
