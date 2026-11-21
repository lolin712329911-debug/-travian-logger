# -*- coding: utf-8 -*-
"""ap-01 main：merge_settings 失敗＝hold＋通知（假物件，無網路、不需 playwright）。"""
import unittest
from unittest import mock

from travian_bot.app import main as m
from travian_bot.common.models import ValidationError


class BuildContexts(unittest.TestCase):
    def _call(self, side_effect=None, return_value=None):
        with mock.patch.object(m.village_repo, "load_villages", return_value=[]), \
                mock.patch.object(m.config_schema, "merge_settings",
                                  side_effect=side_effect, return_value=return_value) as ms, \
                mock.patch.object(m, "notify") as nt, mock.patch.object(m, "_say"):
            out = m._build_contexts({"a": 1}, object(), ["ref"])
        return out, ms, nt

    def test_success_passes_args_and_returns_list(self):
        out, ms, nt = self._call(return_value=["ctx"])
        self.assertEqual(out, ["ctx"])
        ms.assert_called_once_with({"a": 1}, [], ["ref"])
        nt.assert_not_called()

    def test_validation_error_is_hold_and_notifies(self):
        out, _, nt = self._call(side_effect=ValidationError("VillageContext", "main_did", None, "main_did_not_found"))
        self.assertIsNone(out)
        nt.assert_called_once()

    def test_not_implemented_is_hold_and_notifies(self):
        out, _, nt = self._call(side_effect=NotImplementedError("多村"))
        self.assertIsNone(out)
        nt.assert_called_once()

    def test_other_exceptions_not_swallowed(self):
        with self.assertRaises(RuntimeError):
            self._call(side_effect=RuntimeError("x"))


if __name__ == "__main__":
    unittest.main()
