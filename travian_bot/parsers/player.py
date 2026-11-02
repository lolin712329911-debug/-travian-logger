#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/parsers/player.py（ps-04）
版本：v0.1（A2a-1）
用途：頁面內嵌 viewData 的 ownPlayer → PlayerInfo（種族 id、Plus、文化點、村莊名額）。
      純函式：HTML 進、資料出，不碰網路、不碰 Sheet。
依賴：cm-09（parsed）、cm-11（schema，ParseError）。
部署狀態：未部署（GA 前不 live）。

來源：舊 travian_pages.py v2.38 的 parse_player_info（✓ 已讀，沿用＋小改）。
輸入頁面不限：dorf1、dorf2 皆含 viewData（舊服樣本 S1a／S1b ✓）。
Plus 沿用舊設計（v0.33）：人工在遊戲內開關，頁面顯示有開（isActive＝true）就用，系統不購買。

與舊版的差異：
  1. 回傳 PlayerInfo（舊為 dict）；文化點與名額拆成 cp_*、village_slots_* 欄位。
  2. 整段讀不到（沒有 viewData、ownPlayer 不是物件）丟 ParseError，不回 None（A2a-1 決定：
     避免呼叫端把「沒讀到」當成「沒開 Plus」而繼續）；個別欄位讀不到仍是 None。
  3. tribe_id 排除 bool（舊碼 isinstance(True, int) 為真）；數字欄位接受整數值的 float 與純數字字串。
  4. 文化點與名額五欄同進同出：任一缺漏或不是整數，五欄全部 None（沿用舊行為）。

viewData 讀取函式 `_view_data` 與 village_list.py、（A2a-2）village.py 各有一份私有複本
（check_arch 禁止 parsers 互相 import）；tests/parsers/test_viewdata_helpers.py 用同一批案例
對每份複本都跑一遍。ParseError 的訊息只放頁面名稱與原因，不放頁面內容。
"""
import json
import re
from typing import Any, Optional

from ..common.parsed import PlayerInfo
from ..common.schema import ParseError

__all__ = ["parse_player_info"]

_PAGE = "player"
_VIEWDATA_RE = re.compile(r"viewData\s*:\s*")
_INT_TEXT_RE = re.compile(r"-?\d+")


def _view_data(html: Any) -> Optional[dict]:
    """頁內 `viewData: {…}` → dict。找不到、不是 JSON、不是物件回 None；有多處時取第一個可解析的物件。"""
    if not isinstance(html, str):
        return None
    decoder = json.JSONDecoder()
    for m in _VIEWDATA_RE.finditer(html):
        try:
            obj, _ = decoder.raw_decode(html, m.end())
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _as_int(v: Any) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and _INT_TEXT_RE.fullmatch(v.strip()):
        return int(v.strip())
    return None


def _dig(d: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def parse_player_info(html: str) -> PlayerInfo:
    """viewData.ownPlayer → PlayerInfo。整段讀不到丟 ParseError；個別欄位讀不到為 None。"""
    data = _view_data(html)
    if data is None:
        raise ParseError(_PAGE, "viewData 找不到或不是 JSON 物件")
    p = data.get("ownPlayer")
    if not isinstance(p, dict):
        raise ParseError(_PAGE, "viewData.ownPlayer 不存在或不是物件")

    plus = _dig(p, "goldFeatures", "travianPlus", "isActive")
    cp = p.get("culturalPointsOverview")
    cp_vals = [None] * 5
    if isinstance(cp, dict):
        vals = [_as_int(cp.get(k)) for k in (
            "cpProducedForNextSlot", "cpNeededForNextSlot", "cpProductionTotal",
            "usedSlots", "maxControllableVillages")]
        if all(v is not None for v in vals):
            cp_vals = vals
    return PlayerInfo(
        tribe_id=_as_int(p.get("tribeId")),
        plus_active=plus if isinstance(plus, bool) else None,
        cp_have=cp_vals[0], cp_need=cp_vals[1], cp_per_day=cp_vals[2],
        village_slots_used=cp_vals[3], village_slots_max=cp_vals[4])
