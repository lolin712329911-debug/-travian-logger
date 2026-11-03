#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/server_profile.py（cm-13）
版本：v0.2（A2a-2a 跟進 parsed.py v0.3）
用途：ServerProfile（C11）的建立、時間換算、倍速換算與頁面核對（D-18）。純函式。
依賴：cm-01（models）、cm-09（parsed）；標準庫 zoneinfo（只讀系統時區資料庫，不連網）。
部署狀態：未部署（GA 前不 live）。

公開介面
  profile_from_dict(d, *, tribes=None) → ServerProfile（缺必填鍵、型別或格式錯誤丟 ValidationError）
  to_utc(server_dt, profile, *, fold=0) → aware UTC datetime
  from_utc(dt, profile) → aware datetime（伺服器時區）
  scale_speed(value, profile, *, divide=False)
  verify_against_page(profile, facts, *, tribe_keys_by_id=None) → list[Problem]

已知缺口（✗，交接區塊有列）
  1. tribe 合法值（TRIBES 鍵）來自 cm-06（尚未存在），所以 profile_from_dict 以 tribes 參數接收，
     沒給就略過該檢查；config_repo／app 呼叫時要傳 tribe_data.TRIBES。非預設種族的「未驗證」啟動警告
     需要比對種族字串，依 §4.1 規則 6 放在 tribe_data／config 層，不在本檔。
  2. scale_speed 套用在哪些量（產量乘、時間除…）屬於 cm-12（game_rules）；本檔只提供換算方法。
  3. verify_against_page 的 hard／soft 分級與核對項目是依 cm-13 卡片與 C11 文字做的草案；
     D-18 全文不在本切片內，PageFacts 欄位語意待 A2b 定案後再調。
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, List, Mapping, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import models
from .models import ServerProfile, ValidationError
from .parsed import PageFacts

# 預設值與 models 共用同一組常數，只在這裡組成 dict
PROFILE_DEFAULTS = {
    "game": models.DEFAULT_GAME,
    "speed": models.DEFAULT_SPEED,
    "map_half": models.DEFAULT_MAP_HALF,
    "protection_days": None,
    "version": None,
    "locale": models.DEFAULT_LOCALE,
}


class ServerTimeError(ValueError):
    """時間換算失敗（不存在的時間、未知時區、缺時區）。訊息不含伺服器資料。"""


# ---------------------------------------------------------------- 建立
def profile_from_dict(d: Mapping[str, Any], *, tribes=None) -> ServerProfile:
    """從 dict 建立 ServerProfile。

    - 缺的選填鍵（game／speed／map_half／protection_days／version／locale）補 C11 預設；
      已存在但值是 None 的不補（speed=None 會被擋）。
    - server_id、base_url、tribe、start_utc、server_tz 缺少＝ValidationError(rule=required)。
    - 未知鍵＝ValidationError(rule=unknown_field)：打錯鍵名不能靜默吃掉（例如 spped 變成預設倍速）。
    - tribes（TRIBES 的鍵集合）有給才檢查 tribe。
    """
    if not isinstance(d, Mapping):
        raise ValidationError("ServerProfile", "", None, "type")
    merged = dict(PROFILE_DEFAULTS)
    merged.update(d)
    ctx = {"strict": True}
    if tribes is not None:
        ctx["tribes"] = tribes
    return ServerProfile.from_dict(merged, ctx)


# ---------------------------------------------------------------- 時間
@lru_cache(maxsize=8)
def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ServerTimeError("未知或無法載入的時區") from None


def to_utc(server_dt: datetime, profile: ServerProfile, *, fold: int = 0) -> datetime:
    """頁面上的伺服器時間 → aware UTC datetime。

    - aware 輸入：直接轉 UTC（profile 不參與）。
    - naive 輸入：視為 profile.server_tz 的當地時間。
      夏令時間重複的那一小時（秋季回撥）有歧義，以 fold 指定（0＝第一次、1＝第二次，預設 0）；
      不存在的那一小時（春季跳進）丟 ServerTimeError，不猜。
    """
    if not isinstance(server_dt, datetime):
        raise ServerTimeError("需要 datetime")
    if fold not in (0, 1):
        raise ServerTimeError("fold 只能是 0 或 1")
    if server_dt.tzinfo is not None and server_dt.utcoffset() is not None:
        return server_dt.astimezone(timezone.utc)
    zone = _zone(profile.server_tz)
    local = server_dt.replace(tzinfo=zone, fold=fold)
    utc = local.astimezone(timezone.utc)
    if utc.astimezone(zone).replace(tzinfo=None) != server_dt:
        raise ServerTimeError("該當地時間在此時區不存在（夏令時間跳過）")
    return utc


def from_utc(dt: datetime, profile: ServerProfile) -> datetime:
    """aware datetime → 伺服器時區的 aware datetime。naive 一律拒絕（不得猜時區）。"""
    if not isinstance(dt, datetime):
        raise ServerTimeError("需要 datetime")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ServerTimeError("不接受 naive datetime（缺時區）")
    return dt.astimezone(_zone(profile.server_tz))


# ---------------------------------------------------------------- 倍速
Number = Union[int, float]


def scale_speed(value: Number, profile: ServerProfile, *, divide: bool = False) -> Number:
    """以 profile.speed 換算：預設乘（基準 1x 的產量、速度 → 本服數值），divide=True 除（時間縮短類）。

    整數乘整數回整數；除法回 float（呼叫端自行決定取整方式）。哪些量該乘或除見 cm-12（✗）。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("value 需為數字")
    speed = profile.speed
    if isinstance(speed, bool) or not isinstance(speed, int) or speed < 1:
        raise ValueError("profile.speed 需為 int ≥ 1")
    return value / speed if divide else value * speed


# ---------------------------------------------------------------- 頁面核對（D-18）
@dataclass(frozen=True)
class Problem:
    severity: str               # hard（不得繼續）／soft（警告）
    key: str                    # 對應 profile 欄位名
    expected: Optional[str]
    actual: Optional[str]

    def __post_init__(self):
        if self.severity not in ("hard", "soft"):
            raise ValueError("severity 只能是 hard 或 soft")


def _norm_lang(text: str) -> str:
    return text.strip().lower().replace("_", "-")


def verify_against_page(profile: ServerProfile, facts: PageFacts, *,
                        tribe_keys_by_id: Optional[Mapping[int, str]] = None) -> List[Problem]:
    """把 profile 與頁面事實比對，回傳問題清單（空＝全部相符）。純函式，不丟例外。

    頁面讀不到（facts 欄位為 None）不算相符：回報 soft 問題，不靜默略過。
      server_tz   頁面時區名稱不同＝hard（時間換算會錯）；讀不到＝soft
      locale      與 <html lang> 不同（忽略大小寫與 _／-）＝soft（C11：啟動警告）；讀不到＝soft
      version     profile.version 有填才比對 gpack，不同或讀不到＝soft
      tribe       有給 tribe_keys_by_id（tribeId→種族鍵）才比對，不同＝hard；讀不到＝soft
      map_half    villages（viewData.villageList）任一村的 |x| 或 |y| 超出 map_half＝hard（D-18 v0.30，
                  每個超出的村各回報一筆）；villages 為 None／空、或某村座標讀不到＝soft（不靜默略過）
    """
    out: List[Problem] = []

    if facts.tz_name is None:
        out.append(Problem("soft", "server_tz", profile.server_tz, None))
    elif facts.tz_name != profile.server_tz:
        out.append(Problem("hard", "server_tz", profile.server_tz, facts.tz_name))

    if facts.lang is None:
        out.append(Problem("soft", "locale", profile.locale, None))
    elif _norm_lang(facts.lang) != _norm_lang(profile.locale):
        out.append(Problem("soft", "locale", profile.locale, facts.lang))

    if profile.version is not None:
        if facts.gpack is None:
            out.append(Problem("soft", "version", profile.version, None))
        elif facts.gpack != profile.version:
            out.append(Problem("soft", "version", profile.version, facts.gpack))

    if tribe_keys_by_id is not None:
        if facts.tribe_id is None:
            out.append(Problem("soft", "tribe", profile.tribe, None))
        else:
            actual = tribe_keys_by_id.get(facts.tribe_id)
            if actual != profile.tribe:
                out.append(Problem("hard", "tribe", profile.tribe,
                                   actual if actual is not None else f"tribeId={facts.tribe_id}"))

    villages = facts.villages
    if not villages:
        out.append(Problem("soft", "map_half", f"|座標|<={profile.map_half}", None))
    else:
        unreadable = False
        for v in villages:
            if v.x is None or v.y is None:
                unreadable = True
            elif abs(v.x) > profile.map_half or abs(v.y) > profile.map_half:
                out.append(Problem("hard", "map_half", f"|座標|<={profile.map_half}",
                                   f"({v.x}|{v.y})"))
        if unreadable:
            out.append(Problem("soft", "map_half", f"|座標|<={profile.map_half}", None))

    return out
