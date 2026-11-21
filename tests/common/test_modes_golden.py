"""tests/common/test_modes_golden.py — cm-04 與舊 runner.py 的離線比對（A1a-1 補，v0.1）

下面兩個函式是舊 runner.py v2.36 的 `_guard_mode`／`_fill_mode` 原文（只改成接受單一值，
邏輯不變），僅供本測試當對照；新程式碼不得 import 舊 runner。
"""
import unittest

from travian_bot.common.modes import Mode, parse_mode


def old_guard_mode(raw) -> str:
    m = str(raw).strip().lower()
    return m if m in ("dry", "incoming", "always") else "off"


def old_fill_mode(raw) -> str:
    m = str(raw).strip().lower()
    return m if m in ("dry", "on") else "off"


SAMPLES = ["off", "dry", "on", "live", "incoming", "always", "OFF", " Dry ", "ON", "", "  ",
           None, "garbage", "1", "true", 1, True]


class GoldenAgreementTest(unittest.TestCase):
    def test_agree_on_off_dry_blank_and_garbage(self):
        """舊值落在 off／dry／空白／亂值時，新舊結果一致（空白在舊版也是 off）。"""
        for raw in SAMPLES:
            for old_fn in (old_guard_mode, old_fill_mode):
                old = old_fn(raw)
                if old in ("off", "dry"):
                    # 舊版把 'live'、1、True 之類當 off；新版對「看得懂的 live」會給 LIVE，下面另測
                    if isinstance(raw, str) and raw.strip().lower() == "live":
                        continue
                    self.assertEqual(parse_mode(raw).value, old, f"{old_fn.__name__}({raw!r})")


class KnownDivergenceTest(unittest.TestCase):
    """新舊詞彙不同之處。這些是『已知差異』，不是 bug；處置待使用者決定（見交接區塊）。"""

    def test_fill_in_on_is_live_in_new_vocabulary(self):
        self.assertEqual(old_fill_mode("on"), "on")
        self.assertIs(parse_mode("on"), Mode.OFF)       # 新版不認 on；邊界（config_repo）要把 on 轉成 live
        self.assertIs(parse_mode("live"), Mode.LIVE)

    def test_guard_incoming_always_have_no_new_equivalent(self):
        for v in ("incoming", "always"):
            self.assertEqual(old_guard_mode(v), v)
            self.assertIs(parse_mode(v), Mode.OFF)      # 新版視為不合法→off；語意要另外承接

    def test_old_live_was_off(self):
        self.assertEqual(old_guard_mode("live"), "off")
        self.assertEqual(old_fill_mode("live"), "off")


if __name__ == "__main__":
    unittest.main()
