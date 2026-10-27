#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/common/test_models.py（cm-01）v0.1（A1a-2）
把 schema.contract_examples()（§6.2 合規／不合規範例）轉成 models 的測試，另測 to_row／from_row 往返。"""
import dataclasses
import re
import unittest
from pathlib import Path

from travian_bot.common import models, schema, serialize
from travian_bot.common.models import (
    ACTION_COLUMNS, CONTRACT_CLASSES, VILLAGE_COLUMNS, ActionRow, BuildSettings, HideContext,
    MarketConfig, ServerProfile, StageResult, VillageContext, VillageSettingsRow, VillageSnapshot,
    clip_text, to_plain, validate_village_table)

EX = schema.contract_examples()
TABLE = "VillageSettingsTable"
CLASS_NAMES = [n for n in schema.CONTRACT_NAMES if n != TABLE]


def _has(errs, field, rule):
    return any(e.field == field and e.rule == rule for e in errs)


class TestCoverage(unittest.TestCase):
    def test_every_contract_has_a_class(self):
        self.assertEqual(set(CONTRACT_CLASSES), set(CLASS_NAMES))

    def test_every_class_fields_match_spec(self):
        for name in CLASS_NAMES:
            with self.subTest(name):
                cls = CONTRACT_CLASSES[name]
                self.assertEqual({f.name for f in dataclasses.fields(cls)},
                                 set(schema.CONTRACT_SPECS[name]["fields"]))


class TestExamples(unittest.TestCase):
    def test_valid_examples_roundtrip(self):
        for name in CLASS_NAMES:
            cls = CONTRACT_CLASSES[name]
            for i, ex in enumerate(EX[name]["valid"]):
                with self.subTest(name=name, i=i):
                    obj = cls.from_dict(ex["data"], ex["ctx"])
                    self.assertEqual(obj.validate(ex["ctx"]), [])
                    self.assertEqual(obj.to_dict(), ex["data"])
                    self.assertEqual(cls.from_dict(obj.to_dict(), ex["ctx"]), obj)

    def test_invalid_examples_rejected_with_field_and_rule(self):
        for name in CLASS_NAMES:
            cls = CONTRACT_CLASSES[name]
            for i, ex in enumerate(EX[name]["invalid"]):
                with self.subTest(name=name, i=i, field=ex["field"], rule=ex["rule"]):
                    with self.assertRaises(models.ValidationError) as cm:
                        cls.from_dict(ex["data"], ex["ctx"])
                    self.assertTrue(_has(cm.exception.all, ex["field"], ex["rule"]))

    def test_validate_on_constructed_object_points_to_field(self):
        # 物件可以先建（不自動驗證），validate() 再指出錯誤
        ex = EX["ActionRow"]["valid"][0]["data"]
        row = ActionRow(**dict(ex, mode="dry", result="ok"))
        self.assertTrue(_has(row.validate(), "result", "dry_result_ok"))
        with self.assertRaises(models.ValidationError):
            row.ensure_valid()

    def test_from_dict_check_false_skips_validation(self):
        obj = models.Oasis.from_dict({"x": "bad", "y": 1, "kind": "k", "safe": None}, check=False)
        self.assertEqual(obj.x, "bad")
        with self.assertRaises(models.ValidationError):
            models.Oasis.from_dict("not a dict", check=False)

    def test_village_table_rules(self):
        for ex in EX[TABLE]["valid"]:
            rows = [VillageSettingsRow.from_dict(r) for r in ex["data"]]
            self.assertEqual(validate_village_table(rows), [])
        for ex in EX[TABLE]["invalid"]:
            if not isinstance(ex["data"], list):
                continue
            with self.subTest(field=ex["field"], rule=ex["rule"]):
                rows = [VillageSettingsRow.from_dict(r) for r in ex["data"]]
                self.assertTrue(_has(validate_village_table(rows), ex["field"], ex["rule"]))


class TestStructure(unittest.TestCase):
    def test_nested_types_and_tuples(self):
        data = EX["VillageContext"]["valid"][0]["data"]
        ctx = VillageContext.from_dict(data, {"tribe": "gaul"})
        self.assertIsInstance(ctx.build_settings, BuildSettings)
        self.assertIsInstance(ctx.hide_context, HideContext)
        self.assertIsInstance(ctx.hide_context.oases, tuple)
        self.assertIsInstance(ctx.hide_context.oases[0], models.Oasis)
        snap = VillageSnapshot.from_dict(EX["VillageSnapshot"]["valid"][0]["data"])
        self.assertEqual(snap.stock, (500, 500, 500, 500))
        self.assertIsInstance(snap.next_target, models.BuildTarget)
        self.assertIsInstance(snap.incoming_res[0], models.Transit)
        self.assertIsNone(snap.merchants)

    def test_frozen(self):
        snap = VillageSnapshot.from_dict(EX["VillageSnapshot"]["valid"][0]["data"])
        with self.assertRaises(dataclasses.FrozenInstanceError):
            snap.did = 2

    def test_stage_result_is_mutable_and_defaults_are_not_shared(self):
        a, b = StageResult(status="ok"), StageResult(status="ok")
        a.actions.append(ActionRow.from_dict(EX["ActionRow"]["valid"][0]["data"]))
        a.snapshot_updates["stock"] = [1, 2, 3, 4]
        self.assertEqual(b.actions, [])
        self.assertEqual(b.snapshot_updates, {})
        self.assertEqual(StageResult.from_dict(a.to_dict()), a)

    def test_to_plain_converts_tuples_and_enums(self):
        import enum

        class E(enum.Enum):
            A = "a"
        self.assertEqual(to_plain({"k": (1, E.A)}), {"k": [1, "a"]})

    def test_market_config_defaults_valid(self):
        self.assertEqual(MarketConfig().validate(), [])

    def test_server_profile_has_no_tribe_default(self):
        with self.assertRaises(TypeError):
            ServerProfile(server_id="s", base_url="https://example.invalid",
                          start_utc="2026-11-02T08:15:30Z", server_tz="UTC")

    def test_build_settings_target_level_has_no_default(self):
        with self.assertRaises(TypeError):
            BuildSettings()


class TestActionRowSheet(unittest.TestCase):
    def setUp(self):
        self.row = ActionRow(
            ts_utc="2026-11-02T08:15:30Z", action="升級", aid=5, gid=1, level=3,
            cost="100,80,60,40", mode="live", result="ok", detail="成功", did=101)

    def test_columns(self):
        self.assertEqual(len(ACTION_COLUMNS), 10)
        self.assertEqual(ACTION_COLUMNS[0], "ts_utc")
        self.assertEqual(ACTION_COLUMNS[-1], "did")

    def test_roundtrip(self):
        cells = self.row.to_row()
        self.assertEqual(len(cells), 10)
        self.assertEqual(cells[5], "100,80,60,40")
        self.assertEqual(ActionRow.from_row(cells), self.row)

    def test_roundtrip_with_nulls_and_empty_detail(self):
        row = ActionRow(ts_utc="2026-11-02T08:15:30Z", action="調度資源", aid=None, gid=None,
                        level=None, cost=None, mode="dry", result="dry", detail="", did=101)
        cells = row.to_row()
        self.assertEqual(cells[2:6], ["", "", "", ""])
        self.assertEqual(ActionRow.from_row(cells), row)

    def test_from_row_accepts_sheet_float_and_short_or_long_rows(self):
        cells = self.row.to_row()
        cells[9] = 101.0                                  # Sheet API 常回 float
        self.assertEqual(ActionRow.from_row(cells), self.row)
        self.assertEqual(ActionRow.from_row(cells + ["未來追加欄"]), self.row)

    def test_from_row_blank_required_is_error(self):
        cells = self.row.to_row()
        cells[9] = ""
        with self.assertRaises(models.ValidationError) as cm:
            ActionRow.from_row(cells)
        self.assertTrue(_has(cm.exception.all, "did", "required"))

    def test_from_row_bad_cell_points_to_field(self):
        cells = self.row.to_row()
        cells[2] = "5.5"
        with self.assertRaises(models.ValidationError) as cm:
            ActionRow.from_row(cells)
        self.assertEqual((cm.exception.field, cm.exception.rule), ("aid", "cell_format"))

    def test_to_row_refuses_invalid(self):
        bad = dataclasses.replace(self.row, mode="dry")   # dry 不可搭配 result=ok
        with self.assertRaises(models.ValidationError):
            bad.to_row()
        too_long = dataclasses.replace(self.row, detail="x" * 301)
        with self.assertRaises(models.ValidationError):
            too_long.to_row()

    def test_clip_text_then_to_row(self):
        row = dataclasses.replace(self.row, detail=clip_text("字" * 500, 300))
        self.assertEqual(len(row.detail), 300)
        self.assertTrue(row.detail.endswith(serialize.TRUNC_MARK))
        self.assertEqual(ActionRow.from_row(row.to_row()), row)

    def test_cost_res(self):
        self.assertEqual(self.row.cost_res, [100, 80, 60, 40])
        self.assertIsNone(dataclasses.replace(self.row, cost=None).cost_res)


class TestVillageRowSheet(unittest.TestCase):
    def test_columns(self):
        self.assertEqual(len(VILLAGE_COLUMNS), 12)
        self.assertEqual(VILLAGE_COLUMNS[:3], ("did", "name", "enabled"))

    def test_roundtrip_full(self):
        row = VillageSettingsRow(did=102, name="二村", enabled=False, role="capital", is_capital=True,
                                 queue_slots=2, build_order="seq1", hide_mode="dry", guard_mode="off",
                                 fill_mode="live", priority=5, note="備註")
        cells = row.to_row()
        self.assertEqual(cells[2], "FALSE")
        self.assertEqual(cells[4], "TRUE")
        self.assertEqual(VillageSettingsRow.from_row(cells), row)

    def test_roundtrip_defaults(self):
        row = VillageSettingsRow(did=101, name="主村")
        cells = row.to_row()
        self.assertEqual(cells[6:10], ["", "", "", ""])
        self.assertEqual(VillageSettingsRow.from_row(cells), row)

    def test_blank_cells_use_c6_defaults(self):
        row = VillageSettingsRow.from_row([101, "主村"])      # 其餘欄被 Sheet 截掉
        self.assertEqual((row.enabled, row.role, row.is_capital, row.queue_slots, row.priority),
                         (True, "resource", False, 1, 100))
        self.assertIsNone(row.hide_mode)

    def test_blank_did_or_name_is_error(self):
        for cells in (["", "主村"], [101, ""]):
            with self.assertRaises(models.ValidationError):
                VillageSettingsRow.from_row(cells)

    def test_bool_synonyms_read_but_write_strict(self):
        row = VillageSettingsRow.from_row([101, "主村", "false", "military", "0", 1, "", "", "", "", 100, ""])
        self.assertFalse(row.enabled)
        self.assertFalse(row.is_capital)
        self.assertEqual(row.to_row()[2], "FALSE")

    def test_bad_values_rejected(self):
        with self.assertRaises(models.ValidationError) as cm:
            VillageSettingsRow.from_row([101, "主村", "yes"])
        self.assertEqual((cm.exception.field, cm.exception.rule), ("enabled", "cell_format"))
        with self.assertRaises(models.ValidationError) as cm:
            VillageSettingsRow.from_row([101, "主村", "TRUE", "boss"])
        self.assertTrue(_has(cm.exception.all, "role", "enum"))
        with self.assertRaises(models.ValidationError) as cm:
            VillageSettingsRow.from_row([101, "主村", "TRUE", "resource", "FALSE", 1, "", "maybe"])
        self.assertTrue(_has(cm.exception.all, "hide_mode", "enum"))


class TestSourceRules(unittest.TestCase):
    """§4.1 規則的簡易自查（正式檢查在 A1a-3 的 check_arch）。"""
    FILES = ("models", "decisions", "parsed", "server_profile")
    FORBIDDEN = (r"\bstrftime\b", r"\bisoformat\b", r"json\.dump", r"json\.load", r"\bgspread\b",
                 r"\bos\.environ\b", r"\bimport os\b", r"\brequests\b", r"\bplaywright\b",
                 r"['\"](gaul|roman|teuton)['\"]")

    def test_no_forbidden_constructs(self):
        base = Path(models.__file__).parent
        for fn in self.FILES:
            src = (base / f"{fn}.py").read_text(encoding="utf-8")
            code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
            for pat in self.FORBIDDEN:
                with self.subTest(file=fn, pattern=pat):
                    self.assertIsNone(re.search(pat, code))

    def test_imports_only_common(self):
        base = Path(models.__file__).parent
        for fn in self.FILES:
            src = (base / f"{fn}.py").read_text(encoding="utf-8")
            for m in re.finditer(r"^\s*(?:from|import)\s+([\w.]+)", src, re.M):
                mod = m.group(1)
                if mod.startswith("."):
                    continue
                self.assertFalse(mod.startswith(("travian_bot.domain", "travian_bot.parsers",
                                                 "travian_bot.infra", "travian_bot.actions",
                                                 "travian_bot.app")), (fn, mod))


if __name__ == "__main__":
    unittest.main()
