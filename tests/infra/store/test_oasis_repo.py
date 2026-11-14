import unittest

from travian_bot.common.parsed import BlockOasis
from travian_bot.infra.store import oasis_repo as R

try:
    from .fakes import FakeSheet, FakeWS, patch_gspread
except ImportError:
    from fakes import FakeSheet, FakeWS, patch_gspread

T0, T1 = "2026-11-14T03:08:24Z", "2026-11-14T15:00:00Z"
_p = None


def setUpModule():
    global _p
    _p = patch_gspread()
    _p.start()


def tearDownModule():
    _p.stop()


def O(x, y, taken=False, bonuses=((3, 25),), animals=(), owner=None):
    return BlockOasis(x, y, taken, tuple(bonuses), tuple(animals), owner)


A = (-25, -85)
B = (10, 20)


class TestOasisRepo(unittest.TestCase):
    def test_save_load_roundtrip(self):
        sh = FakeSheet()
        a = [O(-50, -92, animals=((31, 16), (32, 17))), O(-50, -95, True, ((3, 25),), (), "Deja Vu"),
             O(-50, -88, bonuses=((0, 25), (3, 25))), O(-49, -97, bonuses=())]
        self.assertEqual(R.save(sh, A, a, now=T0), 4)
        v = sh.tabs["Oases"].get_all_values()
        self.assertEqual(tuple(v[0]), R.OASES_HEADER)
        self.assertEqual(v[1], ["-50", "-95", "TRUE", "[[3,25]]", "", "Deja Vu", T0, "-25", "-85"])
        self.assertEqual(R.load(sh, A), sorted(a, key=lambda o: (o.x, o.y)))

    def test_save_replaces_only_that_center(self):
        sh = FakeSheet()
        R.save(sh, A, [O(1, 1), O(2, 2), O(3, 3)], now=T0)
        R.save(sh, B, [O(5, 5)], now=T0)
        R.save(sh, A, [O(2, 2, True, owner="n")], now=T1)
        self.assertEqual([(o.x, o.y) for o in R.load(sh, A)], [(2, 2)])
        self.assertEqual([(o.x, o.y) for o in R.load(sh, B)], [(5, 5)])
        self.assertEqual(len(sh.tabs["Oases"].get_all_values()), 3)        # 表頭＋2 列，尾端舊列已清空

    def test_list_centers(self):
        sh = FakeSheet()
        self.assertEqual(R.list_centers(sh), [])
        R.save(sh, B, [O(5, 5)], now=T0)
        R.save(sh, A, [O(1, 1), O(2, 2)], now=T1)
        self.assertEqual(R.list_centers(sh), [R.CenterInfo(-25, -85, T1, 2), R.CenterInfo(10, 20, T0, 1)])

    def test_load_empty_cases(self):
        sh = FakeSheet()
        self.assertEqual(R.load(sh, A), [])
        R.save(sh, B, [O(5, 5)], now=T0)
        self.assertEqual(R.load(sh, A), [])

    def test_empty_oases_refused(self):
        sh = FakeSheet()
        R.save(sh, A, [O(1, 1)], now=T0)
        with self.assertRaises(ValueError):
            R.save(sh, A, [], now=T1)
        self.assertEqual(len(R.load(sh, A)), 1)

    def test_validation(self):
        sh = FakeSheet()
        for bad in [(1,), (1, "2"), (True, 2), "ab", None]:
            with self.assertRaises(ValueError):
                R.save(sh, bad, [O(1, 1)], now=T0)
        with self.assertRaises(ValueError):
            R.save(sh, A, [O(1, 1), O(1, 1)], now=T0)
        with self.assertRaises(Exception):
            R.save(sh, A, [O(1, 1)], now="2026-11-14 03:08:24")

    def test_legacy_header_treated_as_empty(self):
        legacy = [["x", "y", "kind", "加成", "動物(json)", "佔領者", "更新時間(UTC)", "中心x", "中心y"],
                  ["-50", "-95", "taken_oasis", "穀 25%", "[]", "Deja Vu", "2026-11-14 03:08:24", "-25", "-85"]]
        sh = FakeSheet({"Oases": FakeWS("Oases", rows=legacy)})
        self.assertEqual(R.load(sh, A), [])
        self.assertEqual(R.list_centers(sh), [])
        R.save(sh, A, [O(1, 1)], now=T0)
        v = sh.tabs["Oases"].get_all_values()
        self.assertEqual(len(v), 2)
        self.assertEqual(tuple(v[0]), R.OASES_HEADER)

    def test_bad_row_raises(self):
        sh = FakeSheet()
        R.save(sh, A, [O(1, 1)], now=T0)
        sh.tabs["Oases"].rows[1][3] = "not json"
        with self.assertRaises(R.OasisTableError):
            R.load(sh, A)
        sh.tabs["Oases"].rows[1][3] = "[[1,2,3]]"
        with self.assertRaises(R.OasisTableError):
            R.load(sh, A)

    def test_unreadable_center_rows_preserved(self):
        sh = FakeSheet()
        R.save(sh, A, [O(1, 1)], now=T0)
        sh.tabs["Oases"].rows.append(["9", "9", "TRUE", "", "", "", T0, "", ""])
        R.save(sh, A, [O(2, 2)], now=T1)
        self.assertEqual(len(sh.tabs["Oases"].get_all_values()), 3)


if __name__ == "__main__":
    unittest.main()
