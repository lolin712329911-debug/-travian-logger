import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr

from tools import dispatch_cli as CLI

BASE = ["-a", "10:36:43", "-a", "11:21:33", "--unit", "u2", "--now", "09:43:44", "--home=-196,172",
        "--oasis=-200,171,wood25,safe", "--oasis=198,173,iron25", "--oasis=-190,180,crop50,safe", "--oasis=-150,100,wood25,safe"]

# 舊 dispatch.py v1.8 main 的輸出（同輸入，離線執行）；唯一差異：單程欄位補零（0:41:14 → 00:41:14）
OLD_OUTPUT = """現在：09:43:44　來襲：10:36:43, 11:21:33　速度：6 格/時　緩衝：30s

座標         加成                距離        單程         回家     撐過  判定
(-200|171) wood25          4.12  00:41:14   11:06:12    1/2  缺 11:21:33；回家後再發
(198|173)  iron25          7.07  01:10:43   12:05:10    2/2  OK 撐過全部（未驗證）
(-190|180) crop50         10.00  01:40:00   13:03:44    2/2  OK 撐過全部
(-150|100) wood25         85.44  14:14:24   14:12:32    2/2  OK 撐過全部

建議：(-190|180) crop50，距離 10.00（map id 8031）
  現在發兵 → 到達 11:23:44，回家 13:03:44（最後一波 11:21:33 之後）
  發兵時間要晚於 08:02:03（否則太早回家），且務必在第一波 10:36:43 之前發出。
  預填網址：/build.php?gid=16&tt=2&eventType=4&targetMapId=8031

提醒：發兵前一刻再確認該綠洲「未佔領、無動物」（清單是快照）；英雄不要帶。
"""


def run(argv):
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stderr(err):
        try:
            rc = CLI.run(argv, out=out)
        except SystemExit as e:                 # argparse 的用法錯誤
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


class Cli(unittest.TestCase):
    def test_matches_old_output(self):
        rc, out, _ = run(BASE)
        self.assertEqual(rc, 0)
        self.assertEqual(out.rstrip("\n"), OLD_OUTPUT.rstrip("\n"))

    def test_include_unverified_changes_recommendation(self):
        rc, out, _ = run(BASE + ["--include-unverified"])
        self.assertEqual(rc, 0)
        self.assertIn("建議：(198|173)", out)

    def test_speed_option_equals_unit(self):
        a = run([x for x in BASE if x not in ("--unit", "u2")] + ["-s", "6"])
        self.assertEqual(a[1].rstrip("\n"), OLD_OUTPUT.rstrip("\n"))

    def test_no_recommendation_exit_1(self):
        rc, out, _ = run(["-a", "12:00:00", "-s", "6", "--now", "09:59:00", "--home=0,0", "--oasis=1,0,wood25,safe"])   # 回家 10:19，撐不到 12:00
        self.assertEqual(rc, 1)
        self.assertIn("沒有任何綠洲能一趟撐過", out)
        self.assertIn("第一波已經到達", run(["-a", "10:00:00", "-s", "6", "--now", "10:00:00", "--home=0,0"])[1])

    def test_arrival_before_now_is_next_day(self):
        rc, out, _ = run(["-a", "00:30:00", "-s", "6", "--now", "23:50:00", "--home=0,0", "--oasis=3,4,wood25,safe"])
        self.assertEqual(rc, 0)                         # 隔天 00:30；5 格÷6×3600＝3000 秒單程，回家 01:30 > 00:30
        self.assertIn("來襲：00:30:00", out)
        self.assertIn("1/1", out)                       # 隔天的來襲要被撐過（沒換成隔天就會變 0/1）

    def test_json_output(self):
        rc, out, _ = run(BASE + ["--json"])
        self.assertEqual(rc, 0)
        d = json.loads(out)
        self.assertEqual(d["recommend"]["map_id"], 8031)
        self.assertEqual(len(d["rows"]), 4)
        self.assertEqual(d["earliest_send_s"], (11 * 3600 + 21 * 60 + 33) + 30 - 2 * 6000)   # 最後一波＋緩衝－2×單程（08:02:03）
        self.assertTrue(out.endswith("\n"))

    def test_json_no_recommendation_exit_1(self):
        rc, out, _ = run(["-a", "12:00:00", "-s", "6", "--now", "09:59:00", "--home=0,0", "--oasis=1,0,wood25,safe", "--json"])
        self.assertEqual(rc, 1)
        self.assertIsNone(json.loads(out)["recommend"])

    def test_oases_json_file(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "o.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump([{"x": 3, "y": 4, "kind": "wood25", "safe": True}], f)
            rc, out, _ = run(["-a", "11:00:00", "-s", "6", "--now", "10:00:00", "--home=0,0", "--oases-json", p])
        self.assertEqual(rc, 0)
        self.assertIn("(3|4)", out)

    def test_input_errors_exit_2(self):
        cases = [
            ["-a", "10:00:00", "-s", "6", "--home=0,0", "--now", "25:00:00"],               # 時間超出範圍
            ["-a", "10:xx", "-s", "6", "--home=0,0", "--now", "09:00:00"],                  # 時間格式
            ["-a", "10:00:00", "-s", "6", "--home=999,0", "--now", "09:00:00"],             # 家超出地圖
            ["-a", "10:00:00", "-s", "6", "--home=0,0", "--now", "09:00:00", "--oasis=1,2"],  # 綠洲格式
            ["-a", "10:00:00", "-s", "6", "--home=0,0", "--now", "09:00:00", "--tribe", "nope"],
            ["-a", "10:00:00", "-s", "6", "--home=0,0", "--now", "09:00:00", "--oases-json", "/no/such/file.json"],
            ["-a", "10:00:00", "-s", "0", "--home=0,0", "--now", "09:00:00", "--oasis=1,1,k"],  # 速度 0
            ["-a", "10:00:00", "-s", "6", "--home=0,0", "--now", "09:00:00", "--oasis=201,0,k"],  # 綠洲超出地圖
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                self.assertEqual(run(argv)[0], 2)

    def test_usage_errors_exit_2(self):
        self.assertEqual(run(["-a", "10:00:00", "-s", "6"])[0], 2)                           # 沒有 --home
        self.assertEqual(run(["-a", "10:00:00", "--home=0,0"])[0], 2)                        # 沒有速度也沒有兵種
        self.assertEqual(run(["-a", "10:00:00", "--home=0,0", "--unit", "u7"])[0], 2)        # 攻城器不在表內
        self.assertEqual(run(["--home=0,0", "-s", "6"])[0], 2)                               # 沒有來襲時間


if __name__ == "__main__":
    unittest.main()
