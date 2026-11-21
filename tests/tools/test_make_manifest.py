"""test_make_manifest.py  v0.1：make_manifest 的測試（合成的卡片表，不依賴真實主檔）。"""
import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MM = _load("make_manifest")

SLICE = """# 範例切片
**本版：v9.9｜切片：X**
一句話：共 3 個模組。

| ID | 檔 | 內容規劃 | 依賴 | 舊源→處置 | WP |
|---|---|---|---|---|---|
| cm-01 | `common/models.py` | 結構 | cm-03 | 無；**新寫** | A1a-2 〔測試備註：x〕 |
| cm-03 | `common/constants.py` | 常數 | — | 舊檔；**沿用** | A1a-1 |
| ps-01 | `parsers/village.py` | 解析 | cm-01、cm-03 | 舊檔；**拆** | A2a／B1 |
"""

FULL = """## 4. 架構
| cm-99 | `common/not_in_section.py` | x | — | x | X | x |
### 4.2 檔案卡片
#### common
| ID | 檔 | 內容 | 依賴 | 舊源→處置 | WP | 測試 |
|---|---|---|---|---|---|---|
| cm-03 | `common/constants.py` | 常數 | — | 舊檔；**沿用** | A1a-1 | `tests/common/test_constants.py` |
| cm-01 | `common/models.py` | 結構 | `common/constants` | 無；**新寫** | A1a-2 | `tests/common/test_models.py`（備註） |
| ps-01 | `parsers/village.py` | 解析 | `common/models`、`common/constants.py` | **拆**成兩半 | A2a | `tests/parsers/test_village.py` |
#### tools/、tests/、其他
| ac-99 | `actions/not_in_section.py` | x | — | x | X | x |
共 3 個模組
"""


def quiet(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = MM.main(argv)
    return code, err.getvalue()


class ParseTests(unittest.TestCase):
    def test_slice_six_columns(self):
        cards, stated, ver = MM.parse_cards(SLICE)
        self.assertEqual((stated, ver, [c["id"] for c in cards]), (3, "v9.9", ["cm-01", "cm-03", "ps-01"]))
        c = {x["id"]: x for x in cards}
        self.assertEqual(c["cm-01"]["deps"], ["cm-03"])
        self.assertEqual(c["cm-01"]["wp"], "A1a-2")                       # 〔測試備註〕被去掉
        self.assertEqual((c["cm-01"]["disp"], c["cm-03"]["disp"], c["ps-01"]["disp"]), ("新寫", "沿用", "拆"))
        self.assertEqual(c["ps-01"]["wp"], "A2a／B1")
        self.assertEqual(c["cm-03"]["deps"], [])

    def test_full_seven_columns_path_deps_and_section_limit(self):
        cards, stated, _ = MM.parse_cards(FULL)
        self.assertEqual([c["id"] for c in cards], ["cm-01", "cm-03", "ps-01"])    # cm-99／ac-99 在範圍外
        c = {x["id"]: x for x in cards}
        self.assertEqual(c["cm-01"]["deps"], ["cm-03"])
        self.assertEqual(c["ps-01"]["deps"], ["cm-01", "cm-03"])
        self.assertEqual(stated, 3)

    def test_errors(self):
        with self.assertRaises(MM.SourceError):
            MM.parse_cards("沒有表")
        with self.assertRaises(MM.SourceError):
            MM.parse_cards(SLICE.replace("| A1a-1 |", "| A1a-1 | 多一欄 | 又一欄 |"))
        with self.assertRaises(MM.SourceError):                           # 路徑依賴對不到
            MM.parse_cards(FULL.replace("`common/constants` ", "`common/nope` "))
        dup = SLICE + "| cm-03 | `common/constants.py` | 不同內容 | — | 舊檔；**沿用** | A1a-1 |\n"
        with self.assertRaises(MM.SourceError):
            MM.parse_cards(dup)
        same = SLICE + "| cm-03 | `common/constants.py` | 常數 | — | 舊檔；**沿用** | A1a-1 |\n"
        self.assertEqual(len(MM.parse_cards(same)[0]), 3)                 # 完全相同的重複列可容忍


class BuildTests(unittest.TestCase):
    def test_build_and_load(self):
        text, n = MM.build(SLICE, "s.md")
        self.assertEqual(n, 3)
        ns = {}
        exec(compile(text, "arch_manifest.py", "exec"), ns)
        self.assertEqual(ns["EXPECTED_COUNT"], 3)
        self.assertEqual(ns["SOURCE"], "s.md v9.9 §4.2")
        self.assertEqual(len(ns["MANIFEST"]), 3)

    def test_count_mismatch(self):
        with self.assertRaises(MM.SourceError):
            MM.build(SLICE.replace("共 3 個模組", "共 5 個模組"), "s.md")

    def test_rejects_bad_dependency_direction_and_cycle(self):
        bad = SLICE.replace("| cm-03 | `common/constants.py` | 常數 | — |", "| cm-03 | `common/constants.py` | 常數 | ps-01 |")
        with self.assertRaises(MM.SourceError) as cm:
            MM.build(bad, "s.md")
        self.assertIn("MANIFEST", str(cm.exception))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = os.path.join(self.tmp, "s.md")
        self.out = os.path.join(self.tmp, "arch_manifest.py")
        with open(self.src, "w", encoding="utf-8") as fh:
            fh.write(SLICE)

    def test_write_then_check(self):
        self.assertEqual(quiet([self.src, "-o", self.out])[0], 0)
        code, err = quiet([self.src, "-o", self.out, "--check"])
        self.assertEqual(code, 0)
        self.assertIn("一致", err)

    def test_check_detects_drift_but_ignores_label(self):
        quiet([self.src, "-o", self.out])
        with open(self.out, encoding="utf-8") as fh:
            text = fh.read()
        with open(self.out, "w", encoding="utf-8") as fh:
            fh.write(text.replace("A1a-2", "A9"))
        self.assertEqual(quiet([self.src, "-o", self.out, "--check"])[0], 1)
        with open(self.out, "w", encoding="utf-8") as fh:
            fh.write(text.replace("s.md v9.9", "other.md v1.0"))
        self.assertEqual(quiet([self.src, "-o", self.out, "--check"])[0], 0)

    def test_bad_source_writes_nothing(self):
        with open(self.src, "w", encoding="utf-8") as fh:
            fh.write(SLICE.replace("共 3 個模組", "共 4 個模組"))
        code, err = quiet([self.src, "-o", self.out])
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(self.out))
        self.assertIn("ERROR｜", err)

    def test_usage_errors(self):
        self.assertEqual(quiet([os.path.join(self.tmp, "nope.md")])[0], 2)
        self.assertEqual(quiet(["--bogus"])[0], 2)


if __name__ == "__main__":
    unittest.main()
