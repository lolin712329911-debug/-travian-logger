"""test_check_contracts.py  v0.1 (A1a-3)：check_contracts 的測試。
用真實的 travian_bot.common（A1a-1／2）驗證「現況乾淨」，再用被改壞的規格／範例驗證每條規則真的會報。"""
import contextlib
import copy
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CC = _load("check_contracts")
from travian_bot.common import models, schema   # noqa: E402


def rules(findings):
    return sorted({f.rule for f in findings})


def run_examples(specs=None, examples=None):
    return CC.check_examples(specs or schema.CONTRACT_SPECS, models.CONTRACT_CLASSES,
                             examples or schema.contract_examples(), models, schema.validate)


class RealRepoClean(unittest.TestCase):
    def test_specs_match_classes(self):
        self.assertEqual([f.text() for f in CC.check_specs_vs_classes(
            schema.CONTRACT_SPECS, models.CONTRACT_CLASSES)], [])

    def test_examples_and_roundtrips(self):
        self.assertEqual([f.text() for f in run_examples()], [])

    def test_every_contract_has_examples(self):
        ex = schema.contract_examples()
        self.assertEqual(sorted(ex), sorted(schema.CONTRACT_SPECS))

    def test_generated_files_are_current(self):
        folder = os.path.join(_ROOT, "tests", "contracts")
        want = CC.build_example_files(schema.contract_examples())
        for fn, text in want.items():
            with open(os.path.join(folder, fn), encoding="utf-8", newline="") as fh:
                self.assertEqual(fh.read(), text, fn)

    def test_files_reload_and_behave(self):
        folder = os.path.join(_ROOT, "tests", "contracts")
        for name in schema.CONTRACT_SPECS:
            for kind in ("valid", "invalid"):
                with open(os.path.join(folder, f"{name}.{kind}.json"), encoding="utf-8") as fh:
                    doc = json.load(fh)
                self.assertEqual((doc["schema_version"], doc["contract"], doc["kind"]), (1, name, kind))
                for c in CC.load_cases(doc):
                    errs = schema.validate(name, c["data"], c["ctx"] or None)
                    if kind == "valid":
                        self.assertEqual(errs, [], (name, c))
                    else:
                        self.assertIn((c["field"], c["rule"]), {(e.field, e.rule) for e in errs}, (name, c))


class SpecMutations(unittest.TestCase):
    def specs(self):
        return copy.deepcopy(schema.CONTRACT_SPECS)

    def check(self, specs):
        return CC.check_specs_vs_classes(specs, models.CONTRACT_CLASSES)

    def test_missing_field_in_spec(self):
        s = self.specs()
        del s["VillageRef"]["fields"]["active"]
        self.assertIn("SPEC_FIELDS", rules(self.check(s)))

    def test_extra_field_in_spec(self):
        s = self.specs()
        s["VillageRef"]["fields"]["zzz"] = {"t": "int", "min": 0, "max": None, "null": False, "coord": False}
        self.assertIn("SPEC_FIELDS", rules(self.check(s)))

    def test_nullable_mismatch(self):
        s = self.specs()
        s["VillageRef"]["fields"]["did"]["null"] = True
        s["VillageRef"]["fields"]["is_capital"]["null"] = False
        res = [f for f in self.check(s) if f.rule == "SPEC_NULLABLE"]
        self.assertEqual({f.where for f in res}, {"VillageRef.did", "VillageRef.is_capital"})

    def test_kind_mismatch(self):
        s = self.specs()
        s["VillageRef"]["fields"]["name"] = {"t": "int", "min": 0, "max": None, "null": False, "coord": False}
        s["BuildTarget"]["fields"]["cost"] = {"t": "int", "min": 0, "max": None, "null": False, "coord": False}
        s["VillageSnapshot"]["fields"]["next_target"] = {"t": "struct", "name": "Merchants", "null": True}
        s["PlanVerdict"]["fields"]["rejected"] = {"t": "list", "item": {"t": "struct", "name": "Oasis", "null": False},
                                                  "null": False}
        res = {f.where for f in self.check(s) if f.rule == "SPEC_KIND"}
        self.assertEqual(res, {"VillageRef.name", "BuildTarget.cost", "VillageSnapshot.next_target",
                               "PlanVerdict.rejected"})

    def test_no_class_and_no_spec(self):
        s = self.specs()
        s["Ghost"] = {"fields": {}, "rules": []}
        del s["Oasis"]
        r = {(f.rule, f.where) for f in self.check(s)}
        self.assertIn(("NO_CLASS", "Ghost"), r)
        self.assertIn(("NO_SPEC", "Oasis"), r)

    def test_table_contract_needs_no_class(self):
        self.assertNotIn(("NO_CLASS", "VillageSettingsTable"),
                         {(f.rule, f.where) for f in self.check(self.specs())})


class ExampleMutations(unittest.TestCase):
    def ex(self):
        return copy.deepcopy(schema.contract_examples())

    def test_coverage(self):
        e = self.ex()
        e["Oasis"]["invalid"] = []
        del e["Merchants"]
        self.assertEqual(rules(run_examples(examples=e)), ["EXAMPLE_COVERAGE"])

    def test_valid_rejected(self):
        e = self.ex()
        e["VillageRef"]["valid"][0]["data"]["did"] = 0
        self.assertIn("VALID_REJECTED", rules(run_examples(examples=e)))

    def test_invalid_passed_and_wrong_rule(self):
        e = self.ex()
        e["VillageRef"]["invalid"][0]["rule"] = "enum"          # 實際錯誤是 min
        e["Oasis"]["invalid"][0]["data"] = e["Oasis"]["valid"][0]["data"]   # 其實合規
        res = [f for f in run_examples(examples=e) if f.rule == "INVALID_PASSED"]
        self.assertEqual({f.where for f in res}, {"VillageRef.invalid[0]", "Oasis.invalid[0]"})

    def test_roundtrip_dict_detects_changed_data(self):
        e = self.ex()
        e["PlanVerdict"]["valid"][0]["data"]["extra_unknown"] = 1      # schema 容許未知欄位，但 to_dict 不會帶出
        self.assertIn("ROUNDTRIP_DICT", rules(run_examples(examples=e)))

    def test_roundtrip_row_detects_lossy_row(self):
        class Lossy(models.ActionRow):
            pass
        orig = models.CONTRACT_CLASSES["ActionRow"]

        def bad_from_row(cls, cells, ctx=None):
            obj = orig.from_row(cells, ctx)
            return orig.from_dict(dict(obj.to_dict(), detail="changed"), ctx)
        Lossy.from_row = classmethod(bad_from_row)
        classes = dict(models.CONTRACT_CLASSES, ActionRow=Lossy)
        res = CC.check_examples(schema.CONTRACT_SPECS, classes, schema.contract_examples(), models, schema.validate)
        self.assertIn("ROUNDTRIP_ROW", rules(res))


class FileChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ex = schema.contract_examples()

    def test_write_then_clean(self):
        self.assertEqual(rules(CC.check_files(self.tmp, self.ex)), ["FILE_MISSING"])
        self.assertEqual(CC.check_files(self.tmp, self.ex, write=True), [])
        folder = os.path.join(self.tmp, "tests", "contracts")
        self.assertEqual(len(os.listdir(folder)), 2 * len(schema.CONTRACT_SPECS))
        with open(os.path.join(folder, "VillageRef.valid.json"), "rb") as fh:
            raw = fh.read()
        self.assertTrue(raw.endswith(b"\n") and b"\r" not in raw)

    def test_hand_edit_extra_and_missing(self):
        CC.check_files(self.tmp, self.ex, write=True)
        folder = os.path.join(self.tmp, "tests", "contracts")
        with open(os.path.join(folder, "Oasis.valid.json"), "a", encoding="utf-8") as fh:
            fh.write(" ")
        with open(os.path.join(folder, "Nope.valid.json"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        os.remove(os.path.join(folder, "Merchants.invalid.json"))
        got = {(f.rule, os.path.basename(f.where)) for f in CC.check_files(self.tmp, self.ex)}
        self.assertEqual(got, {("FILE_STALE", "Oasis.valid.json"), ("FILE_EXTRA", "Nope.valid.json"),
                               ("FILE_MISSING", "Merchants.invalid.json")})

    def test_write_removes_stale_extra_files(self):
        CC.check_files(self.tmp, self.ex, write=True)
        extra = os.path.join(self.tmp, "tests", "contracts", "Nope.invalid.json")
        with open(extra, "w", encoding="utf-8") as fh:
            fh.write("{}")
        self.assertEqual(CC.check_files(self.tmp, self.ex, write=True), [])
        self.assertFalse(os.path.exists(extra))

    def test_set_ctx_roundtrip(self):
        doc = json.loads(CC.build_example_files(self.ex)["ServerProfile.valid.json"])
        self.assertEqual(doc["cases"][0]["ctx"], {"tribes": ["gaul"]})
        self.assertEqual(CC.load_cases(doc)[0]["ctx"], {"tribes": {"gaul"}})


def run_main(argv):
    """執行 CC.main 並吞掉 stdout／stderr，回傳 (exit 碼, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = CC.main(argv)
    return code, out.getvalue(), err.getvalue()


class Cli(unittest.TestCase):
    def test_exit_codes(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        code, out, err = run_main(["--root", tmp])                 # 沒有範例檔
        self.assertEqual(code, 1)
        self.assertEqual(out.count("VIOLATION｜FILE_MISSING｜"), 2 * len(schema.CONTRACT_SPECS))
        self.assertIn("失敗", err)
        code, out, err = run_main(["--root", tmp, "--write"])
        self.assertEqual((code, out), (0, ""))
        code, out, err = run_main(["--root", tmp])
        self.assertEqual((code, out), (0, ""))
        self.assertIn("通過", err)
        code, out, err = run_main(["--bogus"])
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments", err)


if __name__ == "__main__":
    unittest.main()
