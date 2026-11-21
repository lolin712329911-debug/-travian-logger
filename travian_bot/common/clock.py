#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/clock.py（cm-05）
版本：v0.1（A1b）
用途：取得現在時間、把頁面上的伺服器時刻轉成 UTC、計算距離某個 UTC 時間點還有幾秒。
      內部一律 UTC；伺服器本地時間只在 resolve_clock_time 內經 ServerProfile 轉換。
依賴：cm-13（server_profile）、cm-10（serialize，解析 UTC 字串）。
部署狀態：未部署（GA 前不 live）。

公開介面
  utc_now()                              → aware UTC datetime
  secs_until(ts_utc, now_utc=None)       → int ≥ 0（距 ts_utc 還有幾秒，向上取整，已過＝0）
  resolve_clock_time(text, now_utc, profile) → aware UTC datetime
      頁面上只有時刻（'HH:MM' 或 'HH:MM:SS'，伺服器本地時鐘）沒有日期時，
      回傳「不早於 now_utc 的下一個該時刻」。

來源：舊 runner.py 的 _now（✓）、dispatch.py 的 parse_time（✓，語意搬到 resolve_clock_time，
      時區改由 ServerProfile 決定，不再用全域 SERVER_TZ）。
不保留：舊 runner.in_quiet_hours 與環境變數 QUIET_UTC（使用者決定不需要安靜時段，v0.28 A1b）。
與舊版差異：
  1. utc_now 回 datetime；舊 _now 回 '%F %T' 字串。字串格式一律經 serialize.to_utc_str（Z 結尾）。
  2. resolve_clock_time 以「秒精度」比較：now_utc 的微秒先捨去（舊版 base 也是 microsecond=0）。
  3. 當地時間在夏令時間「跳過的那一小時」不存在 → ServerTimeError（不猜）；
     「重複的那一小時」取第一次（fold=0）。
"""
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import serialize
from .server_profile import ServerProfile, ServerTimeError, from_utc, to_utc

__all__ = ["ServerTimeError", "utc_now", "secs_until", "resolve_clock_time"]

_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def utc_now() -> datetime:
    """現在時間，aware UTC。"""
    return datetime.now(timezone.utc)


def _aware_utc(dt: datetime, what: str) -> datetime:
    if not isinstance(dt, datetime):
        raise ServerTimeError(f"{what} 需要 datetime")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ServerTimeError(f"{what} 不接受 naive datetime（缺時區）")
    return dt.astimezone(timezone.utc)


def secs_until(ts_utc, now_utc: Optional[datetime] = None) -> int:
    """距離 ts_utc 還有幾秒（整數，向上取整；已過＝0）。

    ts_utc 是 'YYYY-MM-DDTHH:MM:SSZ' 字串（§6.1）或 aware datetime。
    now_utc 省略時用 utc_now()（測試請傳入）。格式不合法丟 serialize.SerializeError。
    """
    if isinstance(ts_utc, datetime):
        target = _aware_utc(ts_utc, "ts_utc")
    else:
        target = serialize.parse_utc(ts_utc)
    now = utc_now() if now_utc is None else _aware_utc(now_utc, "now_utc")
    remaining = (target - now).total_seconds()
    return max(0, int(math.ceil(remaining)))


def resolve_clock_time(text: str, now_utc: datetime, profile: ServerProfile) -> datetime:
    """伺服器本地時鐘的 'HH:MM' 或 'HH:MM:SS' → 不早於 now_utc 的下一個該時刻（aware UTC）。

    例：伺服器 23:50，頁面寫 00:10 → 回傳明天的 00:10（換成 UTC）。
    與 now_utc 同一秒也算「現在」（不進位到明天），與舊 parse_time 一致。
    """
    if not isinstance(text, str):
        raise ServerTimeError("時刻需為字串")
    m = _CLOCK_RE.match(text.strip())
    if not m:
        raise ServerTimeError("時刻格式需為 HH:MM 或 HH:MM:SS")
    hh, mm = int(m.group(1)), int(m.group(2))
    ss = int(m.group(3)) if m.group(3) is not None else 0
    if hh > 23 or mm > 59 or ss > 59:
        raise ServerTimeError("時刻數值不合法")
    now = _aware_utc(now_utc, "now_utc").replace(microsecond=0)
    local_today = from_utc(now, profile).date()
    naive = datetime(local_today.year, local_today.month, local_today.day, hh, mm, ss)
    candidate = to_utc(naive, profile)
    if candidate < now:
        candidate = to_utc(naive + timedelta(days=1), profile)
    return candidate
