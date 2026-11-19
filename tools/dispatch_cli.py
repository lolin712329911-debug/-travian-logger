#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/dispatch_cli.py
版本：v0.1（A3c）
用途：離線躲兵計畫與推薦（原 dispatch.py 的 main；不連遊戲、不讀 Sheet）。用 domain/hide_plan 的同一套算法。
      不在 bot 執行路徑上。
執行（在 repo 根目錄）：
  python tools/dispatch_cli.py -a 10:36:43 -a 11:21:33 --unit u1 --now 09:43:44 --home=-196,172 \\
      --oasis=-200,171,wood25 --oasis=198,173,iron25,safe
  python tools/dispatch_cli.py -a 10:36:43 -s 7 --home 0,0 --oases-json oases.json --json

座標有負數時，選項與值要用 `=` 連在一起（--home=-196,172、--oasis=-200,171,wood25），否則 argparse 會把它當成選項（舊 CLI 同）。
時間一律是「伺服器本地時刻」的 HH:MM[:SS]，只在檔內換成當天的秒數（早於現在＝隔天），不涉及時區；
--now 省略時用 --tz（IANA，預設 UTC）的現在時間。

參數
  -a/--arrival      來襲到達時間（可重複，必填）
  -s/--speed        部隊速度（格／時，基礎值）；與 --unit 擇一
  --unit            兵種鍵 u1～u6（可重複，多個取最慢；速度取自 --tribe 的表）
  --tribe           種族鍵（預設 gaul；須為 tribe_data 的鍵）
  --server-speed    伺服器速度倍率（預設 1；簡單相乘，倍速服未驗證，見 hide_plan 說明）
  --margin          安全緩衝秒數（預設 30）
  --map-half        地圖半邊長（預設 200）
  --home X,Y        我的村莊座標（必填）
  --oasis X,Y,KIND[,safe]   候選綠洲（可重複；有 safe 字樣＝已驗證）
  --oases-json F    綠洲清單 JSON 檔：[{"x":…,"y":…,"kind":"wood25","safe":true}, …]（可與 --oasis 併用）
  --now / --tz      現在的伺服器時刻／時區
  --include-unverified   推薦時也接受未驗證的綠洲
  --json            輸出 JSON（serialize.dumps_stable）
exit：0＝有推薦；1＝算得出來但沒有任何綠洲能一趟撐過全部；2＝用法或輸入錯誤。
舊版差異：舊版候選來自全域 OASES（執行時由 Sheet 載入，單獨跑 CLI 時是空的），新版改由 --oasis／--oases-json 提供。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from travian_bot.common import geo, serialize, tribe_data          # noqa: E402
from travian_bot.common.models import HideContext, Oasis            # noqa: E402
from travian_bot.domain import hide_plan as HP                      # noqa: E402

DAY = 86400


def _hms(text: str) -> int:
    """HH:MM[:SS] → 當天秒數。"""
    parts = text.strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise ValueError(f"時間格式需為 HH:MM[:SS]：{text!r}")
    h, m, s = (int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) == 3 else 0)
    if h > 23 or m > 59 or s > 59:
        raise ValueError(f"時間超出範圍：{text!r}")
    return h * 3600 + m * 60 + s


def _clock(sec: int) -> str:
    return geo.fmt_duration(sec % DAY)


def _xy(text: str) -> Tuple[int, int]:
    x, y = (int(v.replace("\u2212", "-")) for v in text.split(","))
    return x, y


def _parse_oasis(text: str) -> Oasis:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) not in (3, 4) or (len(parts) == 4 and parts[3] != "safe"):
        raise ValueError(f"--oasis 格式需為 X,Y,KIND[,safe]：{text!r}")
    x, y = _xy(f"{parts[0]},{parts[1]}")
    return Oasis(x, y, parts[2], True if len(parts) == 4 else None)


def _load_oases_json(path: str) -> List[Oasis]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("--oases-json 頂層需為 list")
    out = []
    for o in data:
        safe = o.get("safe")
        if safe is not None and not isinstance(safe, bool):
            raise ValueError("oases-json 的 safe 需為 true／false／null")
        out.append(Oasis(int(o["x"]), int(o["y"]), str(o.get("kind", "")), safe))
    return out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="離線躲兵計畫與推薦（A3c）")
    ap.add_argument("-a", "--arrival", action="append", required=True, help="來襲到達時間 HH:MM[:SS]（可重複）")
    ap.add_argument("-s", "--speed", type=float, help="部隊速度（格／時，基礎值）；與 --unit 擇一")
    ap.add_argument("--unit", action="append", help="兵種鍵 u1～u6（可重複；多個取最慢）")
    ap.add_argument("--tribe", default="gaul", help="種族鍵（預設 gaul）")
    ap.add_argument("--server-speed", type=float, default=1.0)
    ap.add_argument("--margin", type=int, default=30)
    ap.add_argument("--map-half", type=int, default=200)
    ap.add_argument("--home", help="我的村莊座標 X,Y（必填）")
    ap.add_argument("--oasis", action="append", default=[], help="候選綠洲 X,Y,KIND[,safe]（可重複）")
    ap.add_argument("--oases-json", help="綠洲清單 JSON 檔")
    ap.add_argument("--now", help="現在伺服器時刻 HH:MM[:SS]")
    ap.add_argument("--tz", default="UTC", help="--now 省略時用的 IANA 時區（預設 UTC）")
    ap.add_argument("--include-unverified", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    return ap


def _now_seconds(args) -> int:
    if args.now:
        return _hms(args.now)
    if args.tz == "UTC":
        t = datetime.now(timezone.utc)
    else:
        from zoneinfo import ZoneInfo
        t = datetime.now(ZoneInfo(args.tz))
    return t.hour * 3600 + t.minute * 60 + t.second


def run(argv: Optional[List[str]] = None, out=None) -> int:
    out = out or sys.stdout
    ap = build_parser()
    args = ap.parse_args(argv)
    if not args.home:
        ap.error("請用 --home X,Y 指定村莊座標")
    if args.speed is None and not args.unit:
        ap.error("請用 -s 指定速度，或用 --unit 指定兵種")
    try:
        home = _xy(args.home)
        oases = [_parse_oasis(t) for t in args.oasis]
        if args.oases_json:
            oases += _load_oases_json(args.oases_json)
        spec = tribe_data.get_tribe(args.tribe)
        speeds = HP.unit_speeds(spec.key)
        if args.unit:
            bad = [u for u in args.unit if u not in speeds]
            if bad:
                ap.error(f"種族 {args.tribe} 的表沒有 {','.join(bad)}；可用：{','.join(sorted(speeds)) or '（空）'}，或改用 -s")
            base_speed = min(speeds[u] for u in args.unit)
        else:
            base_speed = args.speed
        geo.map_id(home[0], home[1], args.map_half)                # 家座標要在地圖內
        now = _now_seconds(args)
        arrivals = sorted(t + DAY if t < now else t for t in (_hms(a) for a in args.arrival))
        speed = base_speed * args.server_speed
        ctx = HideContext(home_x=home[0], home_y=home[1], oases=tuple(oases), blocked=(), tribe=spec.key)
        rows = HP.plan_at_speed(ctx, speed, now, arrivals, map_half=args.map_half, margin=args.margin)
    except (ValueError, KeyError, OSError, TypeError) as e:        # geo.GeoError、ValidationError 都是 ValueError
        print(f"輸入錯誤：{e}", file=sys.stderr)
        return 2
    best = HP.recommend(rows, args.include_unverified)
    first, last = arrivals[0], arrivals[-1]

    if args.as_json:
        row = lambda c: dict(x=c.x, y=c.y, kind=c.kind, distance=round(c.distance, 2), safe=c.safe, map_id=c.map_id,
                             one_way_s=c.one_way_s, back_ts=c.back_ts, covered=list(c.covered), missed=list(c.missed))
        out.write(serialize.dumps_stable(dict(
            now_s=now, arrivals_s=arrivals, speed=speed, margin=args.margin, rows=[row(c) for c in rows],
            recommend=None if best is None else row(best),
            earliest_send_s=None if best is None else last + args.margin - best.one_way_s * 2)))
        return 0 if best else 1

    p = lambda s="": print(s, file=out)
    p(f"現在：{_clock(now)}　來襲：{', '.join(_clock(a) for a in arrivals)}　速度：{speed:g} 格/時　緩衝：{args.margin}s\n")
    p(f"{'座標':<11}{'加成':<14}{'距離':>6}  {'單程':>8}  {'回家':>9}  {'撐過':>5}  判定")
    for c in rows:
        tag = "" if c.safe else "（未驗證）"
        verdict = ("OK 撐過全部" + tag) if not c.missed else ("缺 " + ",".join(_clock(a) for a in c.missed) + "；回家後再發" + tag)
        p(f"({c.x}|{c.y})".ljust(11) + (c.kind or "").ljust(14)
          + f"{c.distance:>6.2f}  {geo.fmt_duration(c.one_way_s):>8}  {_clock(c.back_ts):>9}  "
          + f"{len(c.covered)}/{len(arrivals)}".rjust(5) + f"  {verdict}")
    p()
    if now >= first:
        p("⚠ 第一波已經到達或同時到達，請確認時間是否正確。")
    if best is None:
        p("沒有任何綠洲能一趟撐過最後一波；可改「回家後再發第二趟」（看上表『缺』欄的時間），或用其他方式避難。")
        return 1
    p(f"建議：({best.x}|{best.y}) {best.kind}，距離 {best.distance:.2f}（map id {best.map_id}）")
    p(f"  現在發兵 → 到達 {_clock(now + best.one_way_s)}，回家 {_clock(best.back_ts)}（最後一波 {_clock(last)} 之後）")
    p(f"  發兵時間要晚於 {_clock(last + args.margin - best.one_way_s * 2)}（否則太早回家），且務必在第一波 {_clock(first)} 之前發出。")
    p(f"  預填網址：/build.php?gid=16&tt=2&eventType=4&targetMapId={best.map_id}")
    p("\n提醒：發兵前一刻再確認該綠洲「未佔領、無動物」（清單是快照）；英雄不要帶。")
    return 0


if __name__ == "__main__":
    sys.exit(run())
