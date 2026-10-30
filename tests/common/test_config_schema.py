#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cm-08 config_schema 的測試（A1b）。舊預設值取自 sheets_writer.py v2.36 的 _default_cfg（✓ 已讀）。"""
import unittest

from travian_bot.common import config_schema as cs
from travian_bot.common.models import VillageContext, VillageRef, VillageSettingsRow
from travian_bot.common.schema import ValidationError

REQUIRED = {"server_id": "s1", "server_base_url": "https://ts1.example.com",
            "server_tz": "Europe/London", "server_start_utc": "2026-11-02T08:15:30Z"}

# 舊 _default_cfg 中「鍵名與預設都不變」的部分
OLD_UNCHANGED = {
    "enabled": True, "queue_slots": None, "max_builds": 2, "target_building_level": 0,
    "is_capital": False, "hero_min_health": 45, "hero_allowed": "normal", "hero_skip_on_incoming": True,
    "hero_transfer_min": 20000, "hero_transfer_max_gap": 1000, "hero_transfer_eta_min": 45,
    "hero_hard_min_health": 60, "hero_guard_hidden": 2000, "fill_in_slack_min": 0,
    "hide_min_attack": 20, "hide_wait_max_s": 180,
}
LOCK3 = {"main_did": "3", "main_did_set_utc": "2026-11-02T09:00:00Z"}
RETIRED = ("home_x", "home_y", "map_size", "village_id", "hero_adventure", "hero_transfer_mode",
           "hero_focus_mode", "hero_guard_mode", "fill_in_mode")


def _rules(problems, key):
    return {(p.severity, p.rule) for p in problems if p.key == key}


class RegistryTest(unittest.TestCase):
    def test_consistent(self):
        self.assertEqual(len(cs.ORDER), len(set(cs.ORDER)))
        self.assertEqual(set(cs.ORDER), set(cs.DEFAULTS))
        self.assertEqual(set(cs.ORDER), set(cs.NOTES))
        self.assertTrue(all(cs.NOTES[k].strip() for k in cs.ORDER))
        self.assertEqual(cs.ORDER[0], "schema_version")

    def test_old_defaults_preserved(self):
        for key, value in OLD_UNCHANGED.items():
            with self.subTest(key=key):
                self.assertEqual(cs.DEFAULTS[key], value)

    def test_documented_default_changes(self):
        self.assertEqual(cs.DEFAULTS["target_level"], 10)          # 舊 2，已決定改 10
        self.assertEqual(cs.DEFAULTS["hero_focus_min_hours"], 1.0)  # 舊 int 1 → float
        self.assertEqual(cs.DEFAULTS["hide_mode"], "off")           # 舊 observe
        self.assertIsNone(cs.DEFAULTS["build_order"])               # 舊 ""，§6.1 空值用 None

    def test_retired_and_quiet_keys_not_registered(self):
        for key in RETIRED:
            self.assertNotIn(key, cs.DEFAULTS)
        self.assertFalse([k for k in cs.ORDER if "quiet" in k])

    def test_all_modes_default_off(self):
        self.assertEqual(len(cs.MODE_KEYS), 8)                      # focus_mode 不是 mode 鍵（off／auto，A6a2）
        self.assertTrue(all(cs.DEFAULTS[k] == "off" for k in cs.MODE_KEYS))
        self.assertEqual(set(cs.MODE_TO_CTX), set(cs.MODE_KEYS))
        self.assertEqual(cs.DEFAULTS["focus_mode"], "off")

    def test_section_6_4_keys_present(self):
        for key in ("tribe", "server_id", "server_base_url", "server_tz", "server_start_utc", "server_speed",
                    "server_map_half", "server_protection_days", "server_locale", "main_did", "main_did_set_utc",
                    "hide_mode", "guard_mode", "fill_mode", "guard_exposure", "transfer_mode", "focus_mode",
                    "oasis_mode", "hero_mode", "market_mode", "troop_mode", "market_max_per_ship",
                    "market_min_ship", "market_reserve_hours", "market_target_fill_pct",
                    "market_max_ships_per_run", "schema_version"):
            self.assertIn(key, cs.DEFAULTS)
        self.assertEqual(cs.DEFAULTS["server_speed"], 1)
        self.assertEqual(cs.DEFAULTS["server_map_half"], 200)
        self.assertEqual(cs.DEFAULTS["server_locale"], "zh-TW")
        self.assertEqual(cs.DEFAULTS["tribe"], "gaul")
        self.assertEqual(cs.DEFAULTS["guard_exposure"], "incoming")
        self.assertEqual(cs.REQUIRED_KEYS, ("server_id", "server_base_url", "server_tz", "server_start_utc"))


class NormalizeTest(unittest.TestCase):
    def test_empty_gives_defaults_and_required_errors(self):
        cfg, problems = cs.normalize_cfg({})
        self.assertEqual({k: v for k, v in cfg.items() if v is not None}, {k: v for k, v in cs.DEFAULTS.items() if v is not None})
        self.assertEqual({p.key for p in problems if p.severity == "error"}, set(cs.REQUIRED_KEYS))

    def test_keys_case_and_whitespace(self):
        cfg, problems = cs.normalize_cfg({" Max_Builds ": " 5 ", **REQUIRED})
        self.assertEqual(cfg["max_builds"], 5)
        self.assertEqual(problems, [])

    def test_blank_cell_uses_default(self):
        cfg, problems = cs.normalize_cfg({"max_builds": "  ", "queue_slots": "", "target_level": None, **REQUIRED})
        self.assertEqual((cfg["max_builds"], cfg["queue_slots"], cfg["target_level"]), (2, None, 10))
        self.assertEqual(problems, [])

    def test_unregistered_warns_and_is_dropped(self):
        cfg, problems = cs.normalize_cfg({"quiet_utc": "17,23", "home_x": "-28", **REQUIRED})
        self.assertNotIn("quiet_utc", cfg)
        self.assertNotIn("home_x", cfg)
        self.assertEqual({(p.key, p.severity, p.rule) for p in problems},
                         {("quiet_utc", "warn", "unregistered"), ("home_x", "warn", "legacy_key")})

    def test_bad_types_use_default_and_report(self):
        cfg, problems = cs.normalize_cfg({"max_builds": "abc", "hero_min_health": "150", "hero_skip_on_incoming": "maybe",
                                          "hero_focus_min_hours": "x", "queue_slots": "7",
                                          "hero_transfer_min": "20,000", "guard_exposure": "sometimes", **REQUIRED})
        self.assertEqual(cfg["max_builds"], 2)
        self.assertEqual(cfg["hero_min_health"], 45)
        self.assertIs(cfg["hero_skip_on_incoming"], True)
        self.assertEqual(cfg["hero_focus_min_hours"], 1.0)
        self.assertIsNone(cfg["queue_slots"])
        self.assertEqual(cfg["hero_transfer_min"], 20000)
        self.assertEqual(cfg["guard_exposure"], "incoming")
        for key, rule in (("max_builds", "type"), ("hero_min_health", "range"), ("hero_skip_on_incoming", "type"),
                          ("queue_slots", "range"), ("hero_transfer_min", "type"), ("guard_exposure", "enum")):
            self.assertEqual(_rules(problems, key), {("warn", rule)}, key)

    def test_messages_never_contain_values(self):
        secret = "SeCrEt-Value-123"
        _, problems = cs.normalize_cfg({"max_builds": secret, "hide_mode": secret, "enabled": secret,
                                        "server_speed": secret, secret: "x", **REQUIRED})
        for p in problems:
            self.assertNotIn(secret, p.message)
            self.assertNotIn(secret, p.rule)

    def test_bool_strictness(self):
        for text, expected in (("TRUE", True), ("false", False), ("1", True), ("0", False), (True, True)):
            with self.subTest(text=text):
                cfg, _ = cs.normalize_cfg({"is_capital": text, **REQUIRED})
                self.assertIs(cfg["is_capital"], expected)
        for text in ("yes", "是", "否", "on"):
            with self.subTest(text=text):
                cfg, problems = cs.normalize_cfg({"is_capital": text, **REQUIRED})
                self.assertIs(cfg["is_capital"], False)
                self.assertEqual(_rules(problems, "is_capital"), {("warn", "type")})

    def test_enabled_typo_means_stop(self):
        cfg, problems = cs.normalize_cfg({"enabled": "FASLE", **REQUIRED})
        self.assertIs(cfg["enabled"], False)
        self.assertEqual(_rules(problems, "enabled"), {("error", "type")})
        cfg, problems = cs.normalize_cfg({"enabled": "", **REQUIRED})      # 空白＝預設 TRUE（不是看不懂）
        self.assertIs(cfg["enabled"], True)
        self.assertEqual(problems, [])

    def test_modes(self):
        cfg, problems = cs.normalize_cfg({"hide_mode": " DRY ", "fill_mode": "live", "guard_mode": "on",
                                          "hero_mode": "observe", "market_mode": 5, **REQUIRED})
        self.assertEqual((cfg["hide_mode"], cfg["fill_mode"]), ("dry", "live"))
        for key in ("guard_mode", "hero_mode", "market_mode"):
            self.assertEqual(cfg[key], "off", key)
            self.assertEqual(_rules(problems, key), {("warn", "mode")}, key)
        self.assertEqual(_rules(problems, "hide_mode"), set())

    def test_hero_allowed(self):
        for text, expected in (("normal", "normal"), ("Hard, normal", "normal,hard"), ("hard", "hard"),
                               ("normal,normal", "normal")):
            with self.subTest(text=text):
                cfg, problems = cs.normalize_cfg({"hero_allowed": text, **REQUIRED})
                self.assertEqual(cfg["hero_allowed"], expected)
                self.assertEqual(problems, [])
        cfg, problems = cs.normalize_cfg({"hero_allowed": "easy", **REQUIRED})
        self.assertEqual(cfg["hero_allowed"], "normal")
        self.assertEqual(_rules(problems, "hero_allowed"), {("warn", "enum")})

    def test_strict_keys_do_not_fall_back(self):
        cfg, problems = cs.normalize_cfg({**REQUIRED, "server_speed": "fast", "server_map_half": "0",
                                          "server_start_utc": "2026-11-02"})
        for key in ("server_speed", "server_map_half", "server_start_utc"):
            self.assertIsNone(cfg[key], key)
            self.assertTrue(any(s == "error" for s, _ in _rules(problems, key)), key)

    def test_tribe(self):
        cfg, problems = cs.normalize_cfg({"tribe": " Roman ", **REQUIRED})
        self.assertEqual(cfg["tribe"], "roman")
        self.assertEqual(_rules(problems, "tribe"), {("warn", "unverified_tribe")})
        cfg, problems = cs.normalize_cfg({"tribe": "nobody", **REQUIRED})
        self.assertEqual(_rules(problems, "tribe"), {("error", "unknown_tribe")})
        cfg, problems = cs.normalize_cfg({**REQUIRED})
        self.assertEqual((cfg["tribe"], _rules(problems, "tribe")), ("gaul", set()))

    def test_level_over_cap(self):
        _, problems = cs.normalize_cfg({"target_level": "12", **REQUIRED})
        self.assertEqual(_rules(problems, "target_level"), {("error", "level_over_cap")})
        _, problems = cs.normalize_cfg({"target_level": "12", "is_capital": "TRUE", **REQUIRED})
        self.assertEqual(_rules(problems, "target_level"), set())

    def test_idempotent_on_typed_cfg(self):
        cfg, _ = cs.normalize_cfg({**REQUIRED, "max_builds": "3", "hide_mode": "dry"})
        again, problems = cs.normalize_cfg(cfg)
        self.assertEqual(again, cfg)
        self.assertEqual(problems, [])

    def test_rejects_non_mapping(self):
        with self.assertRaises(ValidationError):
            cs.normalize_cfg([("a", 1)])


class ValidateAndProfileTest(unittest.TestCase):
    def test_validate_ok(self):
        self.assertEqual(cs.validate_cfg(REQUIRED), [])

    def test_validate_catches_profile_rules(self):
        problems = cs.validate_cfg({**REQUIRED, "server_base_url": "http://ts1.example.com"})
        self.assertTrue(any(p.key == "server_base_url" and p.severity == "error" for p in problems))
        problems = cs.validate_cfg({**REQUIRED, "server_tz": "Taipei"})
        self.assertTrue(any(p.key == "server_tz" and p.severity == "error" for p in problems))

    def test_profile_from_cfg(self):
        p = cs.profile_from_cfg({**REQUIRED, "server_speed": "3", "server_protection_days": "5"})
        self.assertEqual((p.server_id, p.base_url, p.tribe, p.speed, p.map_half, p.protection_days, p.locale),
                         ("s1", "https://ts1.example.com", "gaul", 3, 200, 5, "zh-TW"))
        self.assertEqual(p.server_tz, "Europe/London")
        self.assertIsNone(cs.profile_from_cfg(REQUIRED).protection_days)

    def test_profile_missing_required_raises(self):
        for key in cs.REQUIRED_KEYS:
            cfg = dict(REQUIRED)
            del cfg[key]
            with self.subTest(missing=key):
                with self.assertRaises(ValidationError):
                    cs.profile_from_cfg(cfg)

    def test_profile_never_falls_back_to_default_speed(self):
        with self.assertRaises(ValidationError):
            cs.profile_from_cfg({**REQUIRED, "server_speed": "fast"})
        with self.assertRaises(ValidationError):
            cs.profile_from_cfg({**REQUIRED, "server_speed": "0"})

    def test_profile_unknown_tribe_raises(self):
        with self.assertRaises(ValidationError):
            cs.profile_from_cfg({**REQUIRED, "tribe": "nobody"})

    def test_profile_ignores_non_profile_warnings(self):
        p = cs.profile_from_cfg({**REQUIRED, "max_builds": "abc", "hide_mode": "observe"})
        self.assertEqual(p.speed, 1)


def _ref(did=11, active=True, is_capital=None):
    return VillageRef(did=did, name="Village %d" % did, x=-28, y=-72, is_capital=is_capital, active=active)


class MergeSettingsTest(unittest.TestCase):
    def test_single_village_defaults(self):
        [ctx] = cs.merge_settings(REQUIRED, None, [_ref()])
        self.assertIsInstance(ctx, VillageContext)
        self.assertEqual((ctx.did, ctx.x, ctx.y, ctx.is_capital, ctx.role, ctx.enabled, ctx.priority),
                         (11, -28, -72, False, "resource", True, 100))
        self.assertEqual((ctx.build_settings.target_level, ctx.build_settings.queue_slots,
                          ctx.build_settings.build_order), (10, 1, None))
        self.assertEqual(ctx.modes, {**{k: "off" for k in cs.MODE_TO_CTX.values()}, "focus": "off"})
        self.assertEqual((ctx.hide_context.home_x, ctx.hide_context.home_y, ctx.hide_context.oases,
                          ctx.hide_context.blocked, ctx.hide_context.tribe), (-28, -72, (), (), "gaul"))
        self.assertEqual(ctx.validate({"tribe": "gaul"}), [])

    def test_empty_village_rows_means_single_mode(self):
        self.assertEqual(len(cs.merge_settings(REQUIRED, [], [_ref()])), 1)

    def test_modes_are_mapped(self):
        cfg = {**REQUIRED, "hide_mode": "dry", "guard_mode": "live", "fill_mode": "dry", "transfer_mode": "dry",
               "focus_mode": "auto", "oasis_mode": "dry", "hero_mode": "live", "market_mode": "dry", "troop_mode": "live"}
        [ctx] = cs.merge_settings(cfg, None, [_ref()])
        # focus 的值域待 A6a2，目前固定 off（即使 Config 寫 auto）
        self.assertEqual(ctx.modes, {"fill_in": "dry", "guard": "live", "item_transfer": "dry", "focus": "off",
                                     "hide": "dry", "oasis": "dry", "hero": "live", "market": "dry", "troops": "live"})

    def test_settings_and_capital(self):
        cfg = {**REQUIRED, "is_capital": "TRUE", "target_level": "15", "queue_slots": "2", "build_order": "res:2,15:3"}
        [ctx] = cs.merge_settings(cfg, None, [_ref()])
        self.assertEqual((ctx.is_capital, ctx.role), (True, "capital"))
        self.assertEqual((ctx.build_settings.target_level, ctx.build_settings.queue_slots,
                          ctx.build_settings.build_order), (15, 2, "res:2,15:3"))

    def test_queue_default_comes_from_tribe(self):
        [ctx] = cs.merge_settings({**REQUIRED, "tribe": "roman"}, None, [_ref()])
        self.assertEqual(ctx.build_settings.queue_slots, 2)
        [ctx] = cs.merge_settings({**REQUIRED, "tribe": "roman", "queue_slots": "1"}, None, [_ref()])
        self.assertEqual(ctx.build_settings.queue_slots, 1)
        self.assertEqual(ctx.hide_context.tribe, "roman")

    def test_global_stop_disables_context(self):
        [ctx] = cs.merge_settings({**REQUIRED, "enabled": "FALSE"}, None, [_ref()])
        self.assertFalse(ctx.enabled)

    def test_over_cap_raises(self):
        with self.assertRaises(ValidationError) as cm:
            cs.merge_settings({**REQUIRED, "target_level": "11"}, None, [_ref()])
        self.assertEqual(cm.exception.rule, "level_over_cap")

    def test_unknown_tribe_raises(self):
        with self.assertRaises(ValidationError):
            cs.merge_settings({**REQUIRED, "tribe": "nobody"}, None, [_ref()])

    def test_village_selection(self):
        refs = [_ref(1, active=False), _ref(2, active=True), _ref(3, active=False)]
        self.assertEqual(cs.merge_settings(REQUIRED, None, refs)[0].did, 2)
        self.assertEqual(cs.merge_settings({**REQUIRED, **LOCK3}, None, refs)[0].did, 3)
        self.assertEqual(cs.merge_settings(REQUIRED, None, [_ref(5, active=False)])[0].did, 5)

    def test_village_selection_errors(self):
        for refs, cfg_extra, rule in (
                ([], {}, "no_village"),
                ([_ref(1), _ref(2)], {}, "ambiguous_village"),
                ([_ref(1, active=False), _ref(2, active=False)], {}, "ambiguous_village"),
                ([_ref(1)], {"main_did": "9", "main_did_set_utc": "2026-11-02T09:00:00Z"}, "main_did_not_found")):
            with self.subTest(rule=rule):
                with self.assertRaises(ValidationError) as cm:
                    cs.merge_settings({**REQUIRED, **cfg_extra}, None, refs)
                self.assertEqual(cm.exception.rule, rule)

    def test_multi_village_rows_not_yet_supported(self):
        row = VillageSettingsRow(did=11, name="v")
        with self.assertRaises(NotImplementedError):
            cs.merge_settings(REQUIRED, [row], [_ref()])


class MergedBehaviorTest(unittest.TestCase):
    """A1b 合併時補的行為（原兩份實作各有一部分）。"""

    def test_tribe_aliases_are_read_leniently(self):
        for text, key in (("高盧", "gaul"), ("GAUL", "gaul"), (" Gauls ", "gaul"), ("romans", "roman"), ("条顿", "teuton")):
            with self.subTest(text=text):
                cfg, problems = cs.normalize_cfg({**REQUIRED, "tribe": text})
                self.assertEqual(cfg["tribe"], key)
                self.assertEqual(profile_tribe(text), key)

    def test_unknown_tribe_still_rejected(self):
        for text in ("hun", "viking", "nobody"):
            with self.subTest(text=text):
                _, problems = cs.normalize_cfg({**REQUIRED, "tribe": text})
                self.assertEqual(_rules(problems, "tribe"), {("error", "unknown_tribe")})
                with self.assertRaises(ValidationError):
                    cs.profile_from_cfg({**REQUIRED, "tribe": text})

    def test_non_default_tribe_warns(self):
        _, problems = cs.normalize_cfg({**REQUIRED, "tribe": "roman"})
        self.assertEqual(_rules(problems, "tribe"), {("warn", "unverified_tribe")})

    def test_lock_must_be_complete(self):
        for extra in ({"main_did": "3"}, {"main_did_set_utc": "2026-11-02T09:00:00Z"}):
            with self.subTest(extra=extra):
                _, problems = cs.normalize_cfg({**REQUIRED, **extra})
                self.assertEqual(_rules(problems, "main_did_set_utc"), {("error", "lock_incomplete")})
                with self.assertRaises(ValidationError) as cm:
                    cs.merge_settings({**REQUIRED, **extra}, None, [_ref()])
                self.assertEqual(cm.exception.rule, "lock_incomplete")
        _, problems = cs.normalize_cfg({**REQUIRED, **LOCK3})
        self.assertEqual(problems, [])

    def test_newer_schema_is_refused_everywhere(self):
        cfg = {**REQUIRED, "schema_version": "2"}
        self.assertIn(("error", "schema_too_new"), _rules(cs.validate_cfg(cfg), "schema_version"))
        with self.assertRaises(ValidationError) as cm:
            cs.profile_from_cfg(cfg)
        self.assertEqual(cm.exception.rule, "schema_too_new")
        with self.assertRaises(ValidationError):
            cs.merge_settings(cfg, None, [_ref()])

    def test_legacy_keys_hint_and_are_not_applied(self):
        old = {"hero_adventure": "TRUE", "hero_transfer_mode": "always", "hero_focus_mode": "auto",
               "hero_guard_mode": "always", "fill_in_mode": "live", "map_size": "401", "village_id": "5",
               "home_x": "1", "home_y": "2"}
        self.assertEqual(set(old), set(cs.LEGACY_KEY_MAP))
        cfg, problems = cs.normalize_cfg({**REQUIRED, **old})
        self.assertEqual({(p.key, p.severity, p.rule) for p in problems}, {(k, "warn", "legacy_key") for k in old})
        by_key = {p.key: p.message for p in problems}
        self.assertIn("fill_mode", by_key["fill_in_mode"])
        self.assertIn("server_map_half", by_key["map_size"])
        self.assertIn("main_did", by_key["village_id"])
        self.assertIn("不再使用", by_key["home_x"])
        # 舊值不會被偷偷套用到新鍵
        self.assertEqual((cfg["fill_mode"], cfg["guard_mode"], cfg["hero_mode"], cfg["transfer_mode"]),
                         ("off", "off", "off", "off"))
        self.assertEqual((cfg["focus_mode"], cfg["server_map_half"], cfg["main_did"]), ("off", 200, None))

    def test_every_old_key_is_registered_or_mapped(self):
        old_keys = ("enabled", "target_level", "queue_slots", "is_capital", "max_builds", "target_building_level",
                    "build_order", "hero_adventure", "hero_min_health", "hero_allowed", "hero_skip_on_incoming",
                    "hero_transfer_mode", "hero_transfer_min", "hero_transfer_max_gap", "hero_transfer_eta_min",
                    "hero_focus_mode", "hero_focus_min_hours", "hero_hard_min_health", "hero_guard_mode",
                    "hero_guard_hidden", "fill_in_mode", "fill_in_slack_min", "hide_mode", "hide_min_attack",
                    "hide_wait_max_s", "home_x", "home_y", "map_size", "village_id")
        for k in old_keys:
            self.assertTrue(k in cs.DEFAULTS or k in cs.LEGACY_KEY_MAP, k)

    def test_focus_mode_is_off_or_auto(self):
        cfg, problems = cs.normalize_cfg({**REQUIRED, "focus_mode": "Auto"})
        self.assertEqual((cfg["focus_mode"], problems), ("auto", []))
        for bad in ("live", "dry", "yes", 1):
            with self.subTest(bad=bad):
                cfg, problems = cs.normalize_cfg({**REQUIRED, "focus_mode": bad})
                self.assertEqual(cfg["focus_mode"], "off")
                self.assertEqual(_rules(problems, "focus_mode"), {("warn", "enum")})

    def test_capital_comes_from_config_not_page(self):
        [ctx] = cs.merge_settings(REQUIRED, None, [_ref_cap(True)])
        self.assertFalse(ctx.is_capital)
        [ctx] = cs.merge_settings({**REQUIRED, "is_capital": "TRUE"}, None, [_ref_cap(False)])
        self.assertTrue(ctx.is_capital)

    def test_capital_blank_is_false_not_true(self):
        cfg, _ = cs.normalize_cfg({**REQUIRED, "is_capital": ""})
        self.assertIs(cfg["is_capital"], False)

    def test_hero_focus_hours_is_float(self):
        cfg, problems = cs.normalize_cfg({**REQUIRED, "hero_focus_min_hours": "1.5"})
        self.assertEqual((cfg["hero_focus_min_hours"], problems), (1.5, []))

    def test_secret_like_values_never_echoed(self):
        secret = "SUPERSECRET-123"
        _, problems = cs.normalize_cfg({**REQUIRED, "hide_mode": secret, "server_speed": secret, "tribe": secret,
                                        secret: "x"})
        for p in problems:
            self.assertNotIn(secret, p.message + p.rule)


def profile_tribe(text):
    return cs.profile_from_cfg({**REQUIRED, "tribe": text}).tribe


def _ref_cap(is_capital):
    return VillageRef(did=11, name="v", x=-28, y=-72, is_capital=is_capital, active=True)


if __name__ == "__main__":
    unittest.main()
