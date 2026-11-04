#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/common/test_server_profile.py（cm-13）v0.2（A2a-2a 跟進 PageFacts 欄位）"""
import dataclasses
import unittest
from datetime import datetime, timedelta, timezone

from travian_bot.common import server_profile as sp
from travian_bot.common.models import ServerProfile, ValidationError
from travian_bot.common.parsed import PageFacts, PageVillage
from travian_bot.common.server_profile import (
    Problem, ServerTimeError, from_utc, profile_from_dict, scale_speed, to_utc, verify_against_page)

BASE = {"server_id": "example-s1", "base_url": "https://example.invalid", "tribe": "gaul",
        "start_utc": "2026-11-02T08:15:30Z", "server_tz": "Europe/London"}


def prof(**over):
    return profile_from_dict(dict(BASE, **over))


_VILLAGE_DEFAULTS = {"did": 101, "name": "村", "x": 0, "y": 0}


def village(x=0, y=0, **over):
    """依 PageVillage 實際欄位建立（只填 did／name／x／y；其他欄位若為必填請在 over 補）。"""
    vals = dict(_VILLAGE_DEFAULTS, x=x, y=y, **over)
    names = {f.name for f in dataclasses.fields(PageVillage)}
    return PageVillage(**{k: v for k, v in vals.items() if k in names})


def facts(**over):
    d = dict(tz_name="Europe/London", tz_offset_s=0, lang="zh-TW", gpack="678.2", tribe_id=3,
             server_ts=1793607330, villages=(village(0, 0),))   # 1793607330 = 2026-11-02T08:15:30Z
    d.update(over)
    return PageFacts(**d)


def blank_facts():
    return PageFacts(*([None] * len(dataclasses.fields(PageFacts))))


class TestProfileFromDict(unittest.TestCase):
    def test_defaults_filled(self):
        p = prof()
        self.assertEqual((p.game, p.speed, p.map_half, p.locale), ("legends", 1, 200, "zh-TW"))
        self.assertIsNone(p.protection_days)
        self.assertIsNone(p.version)

    def test_explicit_values_kept(self):
        p = prof(speed=3, map_half=400, protection_days=5, version="678.2", locale="en-US")
        self.assertEqual((p.speed, p.map_half, p.protection_days, p.version, p.locale),
                         (3, 400, 5, "678.2", "en-US"))

    def test_missing_required_keys(self):
        for key in ("server_id", "base_url", "tribe", "start_utc", "server_tz"):
            with self.subTest(key=key):
                d = dict(BASE)
                del d[key]
                with self.assertRaises(ValidationError) as cm:
                    profile_from_dict(d)
                self.assertTrue(any(e.field == key and e.rule == "required" for e in cm.exception.all))

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValidationError) as cm:
            profile_from_dict(dict(BASE, spped=2))
        self.assertTrue(any(e.rule == "unknown_field" for e in cm.exception.all))

    def test_none_for_defaulted_key_is_not_silently_defaulted(self):
        with self.assertRaises(ValidationError):
            profile_from_dict(dict(BASE, speed=None))

    def test_bad_values(self):
        cases = [("base_url", "https://u:p@example.invalid", "credentials_in_url"),
                 ("base_url", "http://example.invalid", "pattern"),
                 ("server_tz", "Taipei", "pattern"),
                 ("speed", 0, "min"),
                 ("start_utc", "2026-11-02 08:15:30", "utc_format")]
        for key, val, rule in cases:
            with self.subTest(key=key, rule=rule):
                with self.assertRaises(ValidationError) as cm:
                    prof(**{key: val})
                self.assertTrue(any(e.field == key and e.rule == rule for e in cm.exception.all))

    def test_tribes_check_only_when_given(self):
        prof(tribe="anything")                                  # 沒給 tribes：略過
        with self.assertRaises(ValidationError) as cm:
            profile_from_dict(dict(BASE, tribe="nobody"), tribes={"gaul"})
        self.assertTrue(any(e.rule == "unknown_tribe" for e in cm.exception.all))
        self.assertEqual(profile_from_dict(BASE, tribes={"gaul"}).tribe, "gaul")

    def test_not_a_mapping(self):
        with self.assertRaises(ValidationError):
            profile_from_dict(["x"])

    def test_defaults_match_dataclass(self):
        p = ServerProfile(**BASE)
        self.assertEqual(prof(), p)

    def test_roundtrip(self):
        p = prof(speed=2, version="678.2")
        self.assertEqual(profile_from_dict(p.to_dict()), p)


class TestTime(unittest.TestCase):
    def test_summer_and_winter_london(self):
        p = prof()
        self.assertEqual(to_utc(datetime(2026, 7, 1, 12, 0), p),
                         datetime(2026, 7, 1, 11, 0, tzinfo=timezone.utc))
        self.assertEqual(to_utc(datetime(2026, 12, 1, 12, 0), p),
                         datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc))

    def test_result_is_aware_utc(self):
        out = to_utc(datetime(2026, 7, 1, 12, 0), prof())
        self.assertEqual(out.utcoffset(), timedelta(0))
        self.assertIs(out.tzinfo, timezone.utc)

    def test_utc_zone(self):
        p = prof(server_tz="UTC")
        self.assertEqual(to_utc(datetime(2026, 7, 1, 12, 0), p),
                         datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc))

    def test_other_zone_without_dst(self):
        p = prof(server_tz="Asia/Taipei")
        self.assertEqual(to_utc(datetime(2026, 7, 1, 12, 0), p),
                         datetime(2026, 7, 1, 4, 0, tzinfo=timezone.utc))

    def test_ambiguous_hour_uses_fold(self):
        p = prof()          # 2026-10-25 02:00 BST → 01:00 GMT，01:30 出現兩次
        t = datetime(2026, 10, 25, 1, 30)
        self.assertEqual(to_utc(t, p), datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc))
        self.assertEqual(to_utc(t, p, fold=1), datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc))

    def test_nonexistent_hour_rejected(self):
        with self.assertRaises(ServerTimeError):
            to_utc(datetime(2026, 3, 29, 1, 30), prof())    # 01:00 → 02:00 跳過

    def test_bad_fold_and_type(self):
        with self.assertRaises(ServerTimeError):
            to_utc(datetime(2026, 7, 1), prof(), fold=2)
        with self.assertRaises(ServerTimeError):
            to_utc("2026-07-01", prof())

    def test_aware_input_passthrough(self):
        tz8 = timezone(timedelta(hours=8))
        self.assertEqual(to_utc(datetime(2026, 7, 1, 12, 0, tzinfo=tz8), prof()),
                         datetime(2026, 7, 1, 4, 0, tzinfo=timezone.utc))

    def test_unknown_zone_name(self):
        bad = ServerProfile(**dict(BASE, server_tz="Nowhere/Land"))
        with self.assertRaises(ServerTimeError):
            to_utc(datetime(2026, 7, 1), bad)
        with self.assertRaises(ServerTimeError):
            from_utc(datetime(2026, 7, 1, tzinfo=timezone.utc), bad)

    def test_from_utc_and_roundtrip(self):
        p = prof()
        u = datetime(2026, 7, 1, 11, 0, tzinfo=timezone.utc)
        local = from_utc(u, p)
        self.assertEqual((local.hour, local.utcoffset()), (12, timedelta(hours=1)))
        self.assertEqual(to_utc(local.replace(tzinfo=None), p), u)

    def test_from_utc_rejects_naive(self):
        with self.assertRaises(ServerTimeError):
            from_utc(datetime(2026, 7, 1), prof())


class TestScaleSpeed(unittest.TestCase):
    def test_multiply_int_stays_int(self):
        out = scale_speed(10, prof(speed=3))
        self.assertEqual(out, 30)
        self.assertIsInstance(out, int)

    def test_divide(self):
        self.assertEqual(scale_speed(90, prof(speed=3), divide=True), 30.0)

    def test_speed_one_is_identity(self):
        self.assertEqual(scale_speed(7, prof()), 7)

    def test_rejects_bad_input(self):
        with self.assertRaises(TypeError):
            scale_speed(True, prof())
        with self.assertRaises(TypeError):
            scale_speed("5", prof())
        bad = ServerProfile(**dict(BASE, speed=0))
        with self.assertRaises(ValueError):
            scale_speed(5, bad)


class TestVerifyAgainstPage(unittest.TestCase):
    def keys(self, problems):
        return [(p.severity, p.key) for p in problems]

    def test_all_match(self):
        self.assertEqual(verify_against_page(prof(), facts()), [])

    def test_tz_mismatch_is_hard(self):
        out = verify_against_page(prof(), facts(tz_name="Asia/Taipei"))
        self.assertEqual(out, [Problem("hard", "server_tz", "Europe/London", "Asia/Taipei")])

    def test_locale_mismatch_is_soft_and_normalized(self):
        self.assertEqual(verify_against_page(prof(), facts(lang="zh_tw")), [])
        out = verify_against_page(prof(), facts(lang="en"))
        self.assertEqual(self.keys(out), [("soft", "locale")])

    def test_version_only_checked_when_profile_has_it(self):
        self.assertEqual(verify_against_page(prof(), facts(gpack="999")), [])
        p = prof(version="678.2")
        self.assertEqual(verify_against_page(p, facts()), [])
        self.assertEqual(self.keys(verify_against_page(p, facts(gpack="679.0"))), [("soft", "version")])
        self.assertEqual(self.keys(verify_against_page(p, facts(gpack=None))), [("soft", "version")])

    def test_tribe_checked_only_with_mapping(self):
        self.assertEqual(verify_against_page(prof(), facts(tribe_id=1)), [])
        ids = {3: "gaul", 1: "roman"}
        self.assertEqual(verify_against_page(prof(), facts(tribe_id=3), tribe_keys_by_id=ids), [])
        out = verify_against_page(prof(), facts(tribe_id=1), tribe_keys_by_id=ids)
        self.assertEqual(out, [Problem("hard", "tribe", "gaul", "roman")])
        out = verify_against_page(prof(), facts(tribe_id=9), tribe_keys_by_id=ids)
        self.assertEqual(out[0].actual, "tribeId=9")
        out = verify_against_page(prof(), facts(tribe_id=None), tribe_keys_by_id=ids)
        self.assertEqual(self.keys(out), [("soft", "tribe")])

    def test_coordinates_out_of_map(self):
        out = verify_against_page(prof(), facts(villages=(village(201, 0), village(0, -250))))
        self.assertEqual(out, [Problem("hard", "map_half", "|座標|<=200", "(201|0)"),
                               Problem("hard", "map_half", "|座標|<=200", "(0|-250)")])
        self.assertEqual(verify_against_page(prof(), facts(villages=(village(200, -200),))), [])

    def test_any_village_out_of_map_is_caught(self):
        vs = (village(0, 0), village(-25, -85), village(0, 201, did=102))
        out = verify_against_page(prof(), facts(villages=vs))
        self.assertEqual(out, [Problem("hard", "map_half", "|座標|<=200", "(0|201)")])

    def test_map_half_follows_profile(self):
        vs = (village(300, 0),)
        self.assertEqual(self.keys(verify_against_page(prof(), facts(villages=vs))), [("hard", "map_half")])
        self.assertEqual(verify_against_page(prof(map_half=400), facts(villages=vs)), [])

    def test_villages_unreadable_is_soft(self):
        for vs in (None, ()):
            with self.subTest(villages=vs):
                out = verify_against_page(prof(), facts(villages=vs))
                self.assertEqual(out, [Problem("soft", "map_half", "|座標|<=200", None)])

    def test_unreadable_facts_are_reported_not_ignored(self):
        out = verify_against_page(prof(), blank_facts())
        self.assertEqual(self.keys(out), [("soft", "server_tz"), ("soft", "locale"), ("soft", "map_half")])

    def test_problem_severity_validated(self):
        with self.assertRaises(ValueError):
            Problem("fatal", "x", None, None)

    def test_defaults_shared_with_models(self):
        self.assertEqual(sp.PROFILE_DEFAULTS["map_half"], 200)


if __name__ == "__main__":
    unittest.main()
