import unittest
from types import SimpleNamespace as NS
from unittest import mock

from travian_bot.actions import build_exec as BE
from travian_bot.common.models import BuildTarget, ServerProfile
from travian_bot.common.modes import Mode
from travian_bot.infra.gateway import Gateway, GatewayError

BASE = "https://ts1.example.com"
COST = (100, 200, 300, 400)
CHECKSUM = "abc123"


def cost_html(cost=COST):
    return "".join(f'<i class="r{i + 1}Big"></i><span>{c}</span>' for i, c in enumerate(cost))


def button(url, cls="textButtonV1 green build"):
    return f'<button class="{cls}" onclick="location.href=\'{url}\'">ok</button>'


def build_page(url=None, cost=COST, extra_buttons=""):
    btn = button(url) if url else ""
    return ('<div class="upgradeBuilding">' + cost_html(cost) +
            '<div class="upgradeButtonsContainer"><div class="section1"><div class="duration">'
            '<span class="value">0:05:00</span></div>' + btn + extra_buttons + '</div></div></div>')


def gid0_page(options):
    """options: [(gid, url or None, cost)]"""
    ws = ""
    for gid, url, cost in options:
        ws += (f'<div class="buildingWrapper" id="contract_building{gid}"><div class="build_desc"><h2>b{gid}</h2></div>'
               + build_page(url, cost) + '</div>')
    return f'<div id="build" class="gid0">{ws}</div>'


class FakePage:
    def __init__(self, pages):
        self.pages, self.submitted, self.visited, self.cur = pages, [], [], ""

    def goto(self, url, wait_until=None):
        self.visited.append(url)
        v = self.pages.get(url[len(BASE):], "")
        if isinstance(v, Exception):
            raise v
        if "action=build" in url:
            self.submitted.append(url)
        self.cur = url

    def content(self):
        return self.pages[self.cur[len(BASE):]]


def make(pages):
    page = FakePage(pages)
    gw = Gateway(NS(context=NS(), page=page), ServerProfile(BASE))
    return gw, page


def d1(stock, queue):
    return NS(stock=stock, queue=tuple(range(queue)))


def target(aid=3, gid=1, cost=COST):
    return BuildTarget(aid=aid, gid=gid, name="Woodcutter", to_level=2, cost=cost, ready_in_s=0)


UP = f"/dorf1.php?id=3&gid=1&action=build&checksum={CHECKSUM}"


def pages_ok(url=UP, cost=COST):
    return {"/build.php?id=3": build_page(url, cost), "/dorf1.php": "d1"}


class SubmitUpgradeTest(unittest.TestCase):
    def run_live(self, pages, before, after, t=None, mode=Mode.LIVE):
        gw, page = make(pages)
        with mock.patch.object(BE, "parse_dorf1", side_effect=[before, after]):
            r = BE.submit_upgrade(gw, 1, t or target(), mode)
        return r, page, gw

    # ---- mode
    def test_off_no_requests(self):
        gw, page = make(pages_ok())
        r = BE.submit_upgrade(gw, 1, target(), Mode.OFF)
        self.assertEqual((r.result, r.requests_used, page.visited), ("skipped", 0, []))

    def test_unknown_mode_is_off(self):
        gw, page = make(pages_ok())
        for bad in ("on", "LIVE!", None, 1):
            self.assertEqual(BE.submit_upgrade(gw, 1, target(), bad).result, "skipped")
        self.assertEqual(page.visited, [])

    def test_mode_accepts_plain_string(self):
        gw, page = make(pages_ok())
        self.assertEqual(BE.submit_upgrade(gw, 1, target(), "dry").result, "dry")

    # ---- dry
    def test_dry_does_not_submit_and_is_not_ok(self):
        gw, page = make(pages_ok())
        r = BE.submit_upgrade(gw, 1, target(), Mode.DRY)
        self.assertEqual(r.result, "dry")
        self.assertIsNone(r.verified)
        self.assertEqual(page.submitted, [])
        self.assertEqual(r.requests_used, 1)

    # ---- live 成功
    def test_live_ok_by_queue(self):
        r, page, _ = self.run_live(pages_ok(), d1((1000,) * 4, 0), d1((1000,) * 4, 1))
        self.assertEqual((r.result, r.verified), ("ok", True))
        self.assertEqual(page.submitted, [BASE + UP])

    def test_live_ok_by_stock_drop(self):
        r, _, _ = self.run_live(pages_ok(), d1((1000,) * 4, 1), d1((1, 1, 1, 1), 1))
        self.assertEqual((r.result, r.verified), ("ok", True))

    def test_requests_used_counts_all(self):
        r, _, gw = self.run_live(pages_ok(), d1((1000,) * 4, 0), d1((1000,) * 4, 1))
        self.assertEqual(r.requests_used, gw.request_count())
        self.assertEqual(r.requests_used, 4)   # 建築頁、dorf1、submit、dorf1

    # ---- live 失敗
    def test_live_no_change_is_failed_not_retried(self):
        r, page, _ = self.run_live(pages_ok(), d1((1000,) * 4, 1), d1((1000,) * 4, 1))
        self.assertEqual((r.result, r.verified), ("failed", False))
        self.assertEqual(len(page.submitted), 1)

    def test_small_stock_drop_is_not_enough(self):
        # 庫存只少成本合計的一半以下（可能只是產量與別的消耗）→ 不算
        half = sum(COST) // 2
        r, _, _ = self.run_live(pages_ok(), d1((1000, 0, 0, 0), 1), d1((1000 - half, 0, 0, 0), 1))
        self.assertEqual(r.result, "failed")

    def test_submit_error_failed_unverified_no_reread(self):
        pages = pages_ok()
        pages[UP] = GatewayError("x")
        gw, page = make(pages)
        with mock.patch.object(BE, "parse_dorf1", side_effect=[d1((1,) * 4, 0)]) as p:
            r = BE.submit_upgrade(gw, 1, target(), Mode.LIVE)
        self.assertEqual((r.result, r.verified), ("failed", None))
        self.assertEqual(p.call_count, 1)             # 沒有送出後重讀
        self.assertIn("不重送", r.detail)

    def test_reread_error_after_submit(self):
        gw, page = make(pages_ok())
        with mock.patch.object(BE, "parse_dorf1", side_effect=[d1((1,) * 4, 0), GatewayError("boom")]):
            r = BE.submit_upgrade(gw, 1, target(), Mode.LIVE)
        self.assertEqual((r.result, r.verified), ("failed", None))
        self.assertEqual(len(page.submitted), 1)

    def test_baseline_error_means_not_sent(self):
        gw, page = make(pages_ok())
        with mock.patch.object(BE, "parse_dorf1", side_effect=GatewayError("boom")):
            r = BE.submit_upgrade(gw, 1, target(), Mode.LIVE)
        self.assertEqual(r.result, "failed")
        self.assertEqual(page.submitted, [])

    def test_build_page_read_error(self):
        gw, page = make({"/build.php?id=3": GatewayError("down")})
        r = BE.submit_upgrade(gw, 1, target(), Mode.LIVE)
        self.assertEqual(r.result, "failed")
        self.assertEqual(page.submitted, [])

    def test_unparseable_build_page(self):
        gw, page = make({"/build.php?id=3": "<html>nothing</html>"})
        self.assertEqual(BE.submit_upgrade(gw, 1, target(), Mode.LIVE).result, "skipped")

    # ---- 核對
    def test_no_button_skipped(self):
        gw, page = make({"/build.php?id=3": build_page(None)})
        r = BE.submit_upgrade(gw, 1, target(), Mode.LIVE)
        self.assertEqual(r.result, "skipped")
        self.assertEqual(page.submitted, [])

    def test_disabled_button_skipped(self):
        html = build_page(None, extra_buttons=button(UP, "textButtonV1 green build disabled"))
        gw, page = make({"/build.php?id=3": html})
        self.assertEqual(BE.submit_upgrade(gw, 1, target(), Mode.LIVE).result, "skipped")

    def test_cost_mismatch_skipped(self):
        gw, page = make(pages_ok(cost=(100, 200, 300, 401)))
        r = BE.submit_upgrade(gw, 1, target(), Mode.LIVE)
        self.assertEqual(r.result, "skipped")
        self.assertEqual(page.submitted, [])

    def test_gold_and_ad_urls_never_sent(self):
        for bad in (UP + "&buildmaster=1", UP + "&as=1", UP.replace("action=build", "action=finish")):
            gw, page = make({"/build.php?id=3": build_page(bad)})
            r = BE.submit_upgrade(gw, 1, target(), Mode.LIVE)
            self.assertEqual(r.result, "skipped", bad)       # parsers 白名單就擋下
            self.assertEqual(page.submitted, [])

    def test_action_layer_rechecks_url(self):
        # parsers 若被放行了不對的網址，本層仍然擋：id／gid 必須等於 target、完整相符
        for bad in (UP.replace("id=3", "id=4"), UP.replace("gid=1", "gid=2"), UP + "&buildmaster=1",
                    "https://evil.example/dorf1.php?id=3&gid=1&action=build&checksum=aa"):
            gw, page = make(pages_ok())
            with mock.patch.object(BE, "find_upgrade_url", return_value=bad), \
                 mock.patch.object(BE, "parse_building_cost", return_value=NS(cost=COST)):
                r = BE.submit_upgrade(gw, 1, target(), Mode.LIVE)
            self.assertEqual(r.result, "failed", bad)
            self.assertEqual(page.submitted, [])

    def test_detail_has_no_checksum_or_url(self):
        for mode in (Mode.DRY, Mode.LIVE):
            gw, page = make(pages_ok())
            with mock.patch.object(BE, "parse_dorf1", side_effect=[d1((1000,) * 4, 0), d1((1000,) * 4, 1)]):
                r = BE.submit_upgrade(gw, 1, target(), mode)
            self.assertNotIn(CHECKSUM, r.detail)
            self.assertNotIn("checksum", r.detail)

    # ---- 空地（gid0）
    def test_empty_slot_uses_options(self):
        url = f"/dorf2.php?id=21&gid=23&action=build&checksum={CHECKSUM}"
        pages = {"/build.php?id=21": gid0_page([(10, f"/dorf2.php?id=21&gid=10&action=build&checksum=ff", (1, 1, 1, 1)),
                                                 (23, url, COST)]), "/dorf1.php": "d1"}
        t = target(aid=21, gid=23)
        r, page, _ = self.run_live(pages, d1((1000,) * 4, 0), d1((1000,) * 4, 1), t)
        self.assertEqual(r.result, "ok")
        self.assertEqual(page.submitted, [BASE + url])        # 送的是 gid 23 的，不是第一個

    def test_empty_slot_missing_gid(self):
        pages = {"/build.php?id=21": gid0_page([(10, "/dorf2.php?id=21&gid=10&action=build&checksum=ff", COST)])}
        gw, page = make(pages)
        r = BE.submit_upgrade(gw, 1, target(aid=21, gid=23), Mode.LIVE)
        self.assertEqual(r.result, "skipped")
        self.assertEqual(page.submitted, [])

    def test_empty_slot_not_buildable(self):
        pages = {"/build.php?id=21": gid0_page([(23, None, COST)])}
        gw, page = make(pages)
        self.assertEqual(BE.submit_upgrade(gw, 1, target(aid=21, gid=23), Mode.LIVE).result, "skipped")

    def test_empty_slot_cost_mismatch(self):
        url = f"/dorf2.php?id=21&gid=23&action=build&checksum={CHECKSUM}"
        pages = {"/build.php?id=21": gid0_page([(23, url, (9, 9, 9, 9))])}
        gw, page = make(pages)
        r = BE.submit_upgrade(gw, 1, target(aid=21, gid=23), Mode.LIVE)
        self.assertEqual(r.result, "skipped")
        self.assertEqual(page.submitted, [])


if __name__ == "__main__":
    unittest.main()
