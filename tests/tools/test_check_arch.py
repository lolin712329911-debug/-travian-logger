"""test_check_arch.py  v0.1.1 (A1a-3)：check_arch 的測試，用暫存的合成目錄樹，不依賴真實 repo。"""
import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "tools")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_TOOLS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CA = _load("check_arch")
MANIFEST, EXPECTED = CA.load_manifest(os.path.join(_TOOLS, "arch_manifest.py"))
BY_PATH = {c["path"]: c for c in MANIFEST}


def run_main(argv):
    """執行 CA.main 並吞掉 stdout／stderr（測試時不讓日誌出現假的 VIOLATION／usage），回傳 (exit 碼, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = CA.main(argv)
    return code, out.getvalue(), err.getvalue()


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "travian_bot"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def put(self, rel, text="X = 1\n", top="travian_bot"):
        full = os.path.join(self.root, top, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_checks(self, **kw):
        findings, n = CA.run_checks(self.root, MANIFEST, EXPECTED, **kw)
        return findings

    def rules(self, **kw):
        return sorted({(f.kind, f.rule) for f in self.run_checks(**kw)})

    def has(self, rule, path=None, kind="VIOLATION", **kw):
        return any(f.rule == rule and f.kind == kind and (path is None or path in f.path)
                   for f in self.run_checks(**kw))


class ManifestTests(unittest.TestCase):
    def test_real_manifest_is_clean(self):
        self.assertEqual(len(MANIFEST), 74)
        self.assertEqual([f.text() for f in CA.check_manifest(MANIFEST, EXPECTED)], [])

    def test_bad_manifest_detected(self):
        bad = [dict(c) for c in MANIFEST]
        bad[0]["deps"] = ["ps-01"]                      # actions → parsers 合法，改成不合法的
        bad[bad.index(next(c for c in bad if c["id"] == "ps-01"))]["deps"] = ["ps-02"]   # parsers→parsers
        res = CA.check_manifest(bad, EXPECTED)
        self.assertTrue(any("ps-01→ps-02" in f.detail for f in res))
        dup = bad + [dict(bad[1])]
        self.assertTrue(any("重複" in f.detail for f in CA.check_manifest(dup, EXPECTED)))
        self.assertTrue(any("卡片數" in f.detail for f in CA.check_manifest(bad[:-1], EXPECTED)))

    def test_pair_allowed_table(self):
        ok = [("app/main.py", "domain/guard.py"), ("actions/build_exec.py", "infra/gateway.py"),
              ("actions/build_exec.py", "parsers/village.py"), ("infra/store/oasis_repo.py", "infra/store/gsheets.py"),
              ("common/geo.py", "common/constants.py"), ("app/stages/build.py", "app/stage_base.py")]
        no = [("domain/guard.py", "parsers/village.py"), ("parsers/village.py", "parsers/buildings.py"),
              ("actions/hide_exec.py", "actions/build_exec.py"), ("actions/build_exec.py", "domain/guard.py"),
              ("infra/gateway.py", "infra/session.py"), ("infra/store/gsheets.py", "parsers/village.py"),
              ("common/geo.py", "infra/gateway.py"), ("domain/guard.py", "domain/focus.py")]
        for a, b in ok:
            self.assertTrue(CA.pair_allowed(a, b), (a, b))
        for a, b in no:
            self.assertFalse(CA.pair_allowed(a, b), (a, b))


class TreeTests(TreeCase):
    def test_clean_tree_passes(self):
        self.put("common/constants.py")
        self.put("common/models.py", "from travian_bot.common import constants\nfrom .constants import X\n")
        self.put("parsers/village.py", "from travian_bot.common.models import X\n")
        self.put("app/main.py", "from travian_bot.parsers import village\nimport os\nos.environ.get('A')\n")
        findings = [f for f in self.run_checks() if f.kind == "VIOLATION"]
        self.assertEqual([f.text() for f in findings], [])

    def test_unregistered(self):
        self.put("common/mystery.py")
        self.assertTrue(self.has("UNREGISTERED", "common/mystery.py"))

    def test_init_files_not_registered(self):
        self.put("common/__init__.py", "")
        self.assertFalse(self.has("UNREGISTERED"))

    def test_missing_file_only_for_expected_wp(self):
        self.put("common/constants.py")
        self.assertFalse(self.has("MISSING_FILE"))
        self.assertTrue(self.has("MISSING_FILE", "common/modes.py", expect_wp=["A1a-1"]))
        self.assertFalse(self.has("MISSING_FILE", "common/constants.py", expect_wp=["A1a-1"]))
        self.assertFalse(self.has("MISSING_FILE", "common/geo.py", expect_wp=["A1a-1"]))   # cm-07 屬 A1b

    def test_layer_dep_violations(self):
        self.put("common/models.py")
        self.put("parsers/village.py", "from travian_bot.parsers import buildings\n")
        self.put("parsers/buildings.py")
        self.put("domain/guard.py", "from travian_bot.parsers.village import X\n")
        self.put("common/geo.py", "from travian_bot.infra import gateway\n")
        self.put("infra/gateway.py")
        self.put("infra/session.py", "from travian_bot.infra.gateway import X\n")
        for path in ("parsers/village.py", "domain/guard.py", "common/geo.py", "infra/session.py"):
            self.assertTrue(self.has("LAYER_DEP", path), path)

    def test_relative_import_resolved(self):
        self.put("common/models.py")
        self.put("domain/guard.py", "from ..parsers import village\n")
        self.put("parsers/village.py")
        self.assertTrue(self.has("LAYER_DEP", "domain/guard.py"))

    def test_cycle(self):
        self.put("common/constants.py", "from travian_bot.common import modes\n")
        self.put("common/modes.py", "from travian_bot.common import constants\n")
        self.assertTrue(self.has("CYCLE"))

    def test_pure_layer_io_and_env(self):
        self.put("common/clock.py", "import requests\nimport os\nx = os.environ['A']\nfrom os import getenv\n")
        self.put("domain/guard.py", "from urllib import request\nimport playwright\n")
        self.assertTrue(self.has("PURE_LAYER_IO", "common/clock.py"))
        self.assertTrue(self.has("PURE_LAYER_IO", "domain/guard.py"))
        self.assertEqual(sum(1 for f in self.run_checks() if f.rule == "ENV_IN_COMMON"), 2)

    def test_env_allowed_outside_common_and_io_allowed_in_infra(self):
        self.put("infra/gateway.py", "import requests\nimport os\nos.getenv('A')\n")
        self.assertFalse(self.has("PURE_LAYER_IO"))
        self.assertFalse(self.has("ENV_IN_COMMON"))

    def test_old_root_import(self):
        self.put("travian_agent.py", "A = 1\n", top="")
        self.put("runner.py", "B = 1\n", top="")
        self.put("common/models.py", "import runner\nfrom travian_agent import A\n")
        self.assertEqual(sum(1 for f in self.run_checks() if f.rule == "OLD_ROOT_IMPORT"), 2)

    def test_tribe_string(self):
        self.put("domain/guard.py", 'def f(t):\n    """docstring mentions gaul"""\n    return t == "gaul"\n')
        self.put("common/tribe_data.py", 'DEFAULT = "gaul"\n')
        self.put("common/config_schema.py", 'T = "gaul"\n')
        self.put("common/schema.py", 'T = "Roman"\n')
        hits = [f for f in self.run_checks() if f.rule == "TRIBE_STRING"]
        self.assertEqual([f.path for f in hits], ["travian_bot/domain/guard.py"])
        self.assertEqual(hits[0].line, 3)

    def test_tribe_string_all_playable_tribes(self):
        for i, name in enumerate(["gaul", "roman", "teuton", "egyptian", "hun", "spartan", "viking",
                                  "Spartans", "VIKING", "huns"]):
            self.put("domain/guard.py", 'def f(t):\n    return t == "%s"\n' % name)
            hits = [f for f in self.run_checks() if f.rule == "TRIBE_STRING"]
            self.assertEqual(len(hits), 1, name)
        # 不是種族名的相似字不誤報
        self.put("domain/guard.py", 'X = "hundred spartanburg vikingr romance"\n')
        self.assertEqual([f for f in self.run_checks() if f.rule == "TRIBE_STRING"], [])
        # 允許位置（tribe_data／config_schema／schema）不報
        self.put("domain/guard.py", "X = 1\n")
        for rel in ("common/tribe_data.py", "common/config_schema.py", "common/schema.py"):
            self.put(rel, 'T = "spartan"\nU = "viking"\n')
        self.assertEqual([f for f in self.run_checks() if f.rule == "TRIBE_STRING"], [])

    def test_format_exit(self):
        code = ("import json\nimport json as j\nfrom json import dumps as d\n"
                "def f(dt, o):\n    a = dt.strftime('%Y')\n    b = dt.isoformat()\n"
                "    c = json.dumps(o)\n    e = j.dumps(o)\n    return d(o)\n")
        self.put("app/formatting.py", code)
        self.put("common/serialize.py", code)
        hits = [f for f in self.run_checks() if f.rule == "FORMAT_EXIT"]
        self.assertTrue(hits and all("app/formatting.py" in f.path for f in hits))
        self.assertGreaterEqual(len(hits), 6)

    def test_json_loads_and_other_dumps_ok(self):
        self.put("app/formatting.py", "import json\nx = json.loads('1')\ndef dumps(): pass\ndumps()\n")
        self.assertFalse(self.has("FORMAT_EXIT"))

    def test_gspread_exit(self):
        self.put("infra/store/gsheets.py", "import gspread\n")
        self.put("infra/store/config_repo.py", "import gspread\n")
        self.put("common/models.py", "import gspread\n")
        hits = {f.path for f in self.run_checks() if f.rule == "GSPREAD_EXIT"}
        self.assertEqual(hits, {"travian_bot/infra/store/config_repo.py", "travian_bot/common/models.py"})

    def test_undeclared_dep_warn_and_strict(self):
        self.put("common/constants.py")
        self.put("common/geo.py", "from travian_bot.common import constants\n")   # cm-07 依賴欄是「—」
        self.assertTrue(self.has("UNDECLARED_DEP", kind="WARN"))
        self.assertFalse(self.has("UNDECLARED_DEP", kind="VIOLATION"))
        self.assertTrue(self.has("UNDECLARED_DEP", kind="VIOLATION", strict=True))

    def test_syntax_error_reported(self):
        self.put("common/constants.py", "def (:\n")
        self.assertTrue(self.has("PARSE", "common/constants.py"))

    def test_output_format_and_exit_codes(self):
        self.put("common/mystery.py")
        f = [x for x in self.run_checks() if x.rule == "UNREGISTERED"][0]
        self.assertTrue(f.text().startswith("VIOLATION｜UNREGISTERED｜travian_bot/common/mystery.py｜"))
        code, out, err = run_main(["--root", self.root])
        self.assertEqual(code, 1)
        self.assertIn("VIOLATION｜UNREGISTERED｜", out)
        self.assertIn("失敗", err)
        os.remove(os.path.join(self.root, "travian_bot/common/mystery.py"))
        code, out, err = run_main(["--root", self.root])
        self.assertEqual((code, out), (0, ""))
        self.assertIn("通過", err)
        code, out, err = run_main(["--root", os.path.join(self.root, "nope")])
        self.assertEqual(code, 2)
        self.assertIn("ERROR｜", err)
        code, out, err = run_main(["--bogus"])
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments", err)


if __name__ == "__main__":
    unittest.main()
