#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/geo.py（cm-07）
版本：v0.1（A1b）
用途：地圖幾何與持續時間的純函式。地圖大小一律由呼叫端以 map_half（C11 server_map_half）傳入，
      不寫死 200，不碰全域變數。
依賴：無（只用標準庫）。
部署狀態：未部署（GA 前不 live）。

公開介面
  wrap_delta(a, b, map_half)        一維環繞距離
  distance(a, b, map_half)          兩點 (x, y) 環繞後的直線距離
  map_id(x, y, map_half)            格子 id（派遣預填網址的 targetMapId）
  travel_seconds(dist, speed)       距離（格）÷ 速度（格／時，已含倍速）→ 整數秒（四捨五入）
  parse_duration(text)              'H:MM:SS' → 整數秒（小時可超過 24）
  fmt_duration(seconds)             整數秒 → 'HH:MM:SS'

來源：舊 dispatch.py v1.8（✓ 已讀）的 wrap_delta、distance、map_id、plan() 裡的單程秒數算式。
與舊版的差異（交接區塊有列）：
  1. 全域 MAP_SIZE 改成 map_half 參數（舊 MAP_SIZE＝2×map_half＋1）。
  2. map_id 對超出 ±map_half 的座標丟 GeoError（舊版不檢查，由 configure 在別處擋）。
  3. 舊 parse_time(s, base)／fmt(datetime) 處理的是「伺服器本地時刻」，不是持續時間；
     時刻解析改放 clock.resolve_clock_time（要用 ServerProfile 轉 UTC）。本檔只處理持續時間。
"""
import math
import re
from typing import Sequence

__all__ = ["GeoError", "wrap_delta", "distance", "map_id", "travel_seconds",
           "parse_duration", "fmt_duration"]


class GeoError(ValueError):
    """參數不合法（map_half、座標範圍、速度、持續時間格式）。訊息不含呼叫端資料。"""


def _check_half(map_half) -> int:
    if isinstance(map_half, bool) or not isinstance(map_half, int) or map_half < 1:
        raise GeoError("map_half 需為 int ≥ 1")
    return map_half


def _size(map_half) -> int:
    return 2 * _check_half(map_half) + 1


def wrap_delta(a, b, map_half: int):
    """一維環繞距離：座標範圍 -map_half..map_half，寬 2*map_half+1。"""
    size = _size(map_half)
    d = abs(a - b)
    return min(d, size - d)


def distance(a: Sequence, b: Sequence, map_half: int) -> float:
    """環繞後的直線距離。a、b 是 (x, y)。"""
    return math.hypot(wrap_delta(a[0], b[0], map_half), wrap_delta(a[1], b[1], map_half))


def map_id(x: int, y: int, map_half: int) -> int:
    """格子 id（targetMapId）。座標需在 ±map_half 內，否則 GeoError。"""
    half = _check_half(map_half)
    for v in (x, y):
        if isinstance(v, bool) or not isinstance(v, int):
            raise GeoError("座標需為 int")
        if abs(v) > half:
            raise GeoError("座標超出地圖範圍")
    return (half - y) * (2 * half + 1) + (x + half) + 1


def travel_seconds(dist: float, speed: float) -> int:
    """單程秒數＝round(距離 ÷ 速度 × 3600)。speed 是格／時，呼叫端已乘過伺服器倍速。"""
    for v in (dist, speed):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
            raise GeoError("dist、speed 需為數字")
    if dist < 0:
        raise GeoError("dist 不可為負")
    if speed <= 0:
        raise GeoError("speed 需 > 0")
    return int(round(dist / speed * 3600))


_DUR_RE = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)$")


def parse_duration(text: str) -> int:
    """'H:MM:SS'（小時不限位數、可超過 24；分、秒兩位且 00～59）→ 整數秒。其他格式 GeoError。"""
    if not isinstance(text, str):
        raise GeoError("持續時間需為字串")
    m = _DUR_RE.match(text.strip())
    if not m:
        raise GeoError("持續時間格式需為 H:MM:SS")
    h, mi, s = (int(g) for g in m.groups())
    return h * 3600 + mi * 60 + s


def fmt_duration(seconds: int) -> str:
    """整數秒 → 'HH:MM:SS'（小時至少兩位，超過 99 就多幾位）。"""
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 0:
        raise GeoError("秒數需為 int ≥ 0")
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
