"""tests/common/test_modes.py — cm-04（v0.1，A1a-1）"""
import unittest

from travian_bot.common.modes import (Mode, effective_mode, parse_dry_run_flag,
                                       parse_mode, parse_mode_checked)


class ParseModeTest(unittest.TestCase):
    def test_valid_values(self):
        self.assertIs(parse_mode("off"), Mode.OFF)
        self.assertIs(parse_mode(" DRY "), Mode.DRY)
        self.assertIs(parse_mode("Live"), Mode.LIVE)
        self.assertIs(parse_mode(Mode.LIVE), Mode.LIVE)

    def test_blank_uses_default(self):
        self.assertIs(parse_mode("", Mode.DRY), Mode.DRY)
        self.assertIs(parse_mode("   ", Mode.DRY), Mode.DRY)
        self.assertIs(parse_mode(None, Mode.LIVE), Mode.LIVE)
        self.assertEqual(parse_mode_checked("", Mode.DRY), (Mode.DRY, None))

    def test_invalid_is_off_and_reported(self):
        for bad in ("yes", "1", "liv", 1, True, ["live"]):
            mode, problem = parse_mode_checked(bad, Mode.LIVE)
            self.assertIs(mode, Mode.OFF, bad)
            self.assertTrue(problem, bad)

    def test_problem_text_does_not_echo_value(self):
        _, problem = parse_mode_checked("SECRET-COOKIE-abc123", Mode.OFF)
        self.assertNotIn("SECRET", problem)


class EffectiveModeTest(unittest.TestCase):
    def test_flag_downgrades_live_only(self):
        self.assertIs(effective_mode(Mode.LIVE, True), Mode.DRY)
        self.assertIs(effective_mode(Mode.DRY, True), Mode.DRY)
        self.assertIs(effective_mode(Mode.OFF, True), Mode.OFF)

    def test_no_flag_keeps_mode(self):
        for m in Mode:
            self.assertIs(effective_mode(m, False), m)

    def test_flag_must_be_bool(self):
        for bad in ("0", "1", 0, 1, None):
            with self.assertRaises(TypeError):
                effective_mode(Mode.LIVE, bad)


class DryRunFlagTest(unittest.TestCase):
    def test_only_explicit_false_disables(self):
        for raw in ("0", "false", "FALSE", " no ", "off"):
            self.assertFalse(parse_dry_run_flag(raw), raw)

    def test_everything_else_is_dry(self):
        for raw in (None, "", "  ", "1", "true", "yes", "garbage"):
            self.assertTrue(parse_dry_run_flag(raw), raw)


if __name__ == "__main__":
    unittest.main()
