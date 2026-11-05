#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/common/test_parsed.py（cm-09）v0.3（A2a-2b 加建築頁結構）：草案結構的基本性質與舊 Field／State／Slot 邊界約定。"""
import dataclasses
import unittest

from travian_bot.common import models, parsed
from travian_bot.common.parsed import (
    BuildCondition, BuildingSlot, BuildOption, Dorf1, Dorf2, MarketState, PageFacts, QueueItem, ResField,
    UpgradeCost)


class TestParsed(unittest.TestCase):
    def test_oasis_is_the_models_one(self):
        self.assertIs(parsed.Oasis, models.Oasis)

    def test_all_exported_are_frozen_dataclasses(self):
        for name in parsed.__all__:
            obj = getattr(parsed, name)
            with self.subTest(name):
                self.assertTrue(dataclasses.is_dataclass(obj))
                self.assertTrue(obj.__dataclass_params__.frozen)

    def test_dorf1_unknowns_are_none_not_zero(self):
        f = ResField(aid=1, gid=1, level=0, cost=(10, 20, 30, 40), build_time_s=None,
                     under_construction=None, url=None)
        d = Dorf1(stock=(1, 2, 3, 4), prod=(1, 1, 1, -1), cap_wh=800, cap_gr=800, free_crop=5,
                  fields=(f,), queue=(QueueItem(106, "農場 等級 1"),), incoming_attacks=None,
                  attack_eta_s=None, movements=(), protection_s=None, plus_s=None)
        plain = models.to_plain(d)
        self.assertIsNone(plain["incoming_attacks"])      # 未知 ≠ 0（舊 State.attacks=0 的歧義）
        self.assertIsNone(plain["fields"][0]["url"])      # 舊 url="" → None
        self.assertEqual(plain["queue"], [{"remaining_s": 106, "info": "農場 等級 1"}])
        self.assertEqual(plain["fields"][0]["cost"], [10, 20, 30, 40])

    def test_empty_slot_has_gid_none(self):
        s = BuildingSlot(aid=25, gid=None, level=0, name=None, under_construction=None)
        self.assertIsNone(models.to_plain(Dorf2(slots=(s,)))["slots"][0]["gid"])

    def test_market_state_reuses_models(self):
        m = MarketState(merchants=models.Merchants(2, 3, 500), incoming=(), outgoing=())
        self.assertEqual(models.to_plain(m)["merchants"]["capacity_each"], 500)
        self.assertIsNone(MarketState(None, (), ()).merchants)

    def test_page_facts_all_optional(self):
        n = len(dataclasses.fields(PageFacts))
        f = PageFacts(*([None] * n))
        self.assertTrue(all(v is None for v in models.to_plain(f).values()))
        self.assertEqual(
            [x.name for x in dataclasses.fields(PageFacts)],
            ["tz_name", "tz_offset_s", "lang", "gpack", "tribe_id", "server_ts", "villages"])

    def test_build_option_unknowns_are_none_not_zero(self):
        c = BuildCondition(gid=25, name="行宮", level=None, met=True, current=None, forbidden=True)
        o = BuildOption(gid=26, name="皇宮", cost=None, build_time_s=None, buildable=False, url=None,
                        resource_short=False, exchange_disabled=None, afford_in_s=None, conditions=(c,))
        plain = models.to_plain(o)
        self.assertIsNone(plain["build_time_s"])          # 舊 secs=0 → None
        self.assertIsNone(plain["exchange_disabled"])     # 沒有「交換資源」按鈕 ≠ 沒 disabled
        self.assertIsNone(plain["conditions"][0]["level"])
        self.assertTrue(plain["conditions"][0]["forbidden"])

    def test_build_option_fields_renamed(self):
        names = [f.name for f in dataclasses.fields(BuildOption)]
        self.assertIn("exchange_disabled", names)
        self.assertIn("afford_in_s", names)
        self.assertNotIn("exceeds_storage", names)
        self.assertNotIn("secs", names)

    def test_upgrade_cost_plain(self):
        u = UpgradeCost(cost=(1, 2, 3, 4), build_time_s=60, resource_short=True, exchange_disabled=True,
                        afford_in_s=10)
        self.assertEqual(models.to_plain(u)["cost"], [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
