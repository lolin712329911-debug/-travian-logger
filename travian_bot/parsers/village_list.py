#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/parsers/village_list.py（ps-02）
版本：v0.1（A2a-1）
用途：目前選中的村莊（did、座標）、家的座標、頁面上全部村莊的清單。純函式：HTML 進、資料出。
依賴：cm-01（models，VillageRef）、cm-03（constants，BIDI）、cm-11（schema，ParseError）。
部署狀態：未部署（GA 前不 live）。

公開介面
  parse_active_village(html, map_half=None) → did（int）或 None
  resolve_home(html, map_half=None)         → (x, y) 或 None
  parse_village_list(html, map_half=None)   → list[VillageRef]；讀不到或前後矛盾丟 ParseError
  map_half 有給時，座標超出 ±map_half 視為讀不到（active／home 回 None；list 丟 ParseError）；
  沒給就略過範圍檢查（不猜預設，同 schema 的 ctx 慣例）。

來源：舊 travian_pages.py v2.38 的 parse_active_village、resolve_home（✓ 已讀，沿用＋小改）；
      parse_village_list 新寫（樣本 S1a／S1b ✓）。
與舊版的差異：
  1. 兩處來源（viewData.ownPlayer.village 與側欄 div.listEntry.village.active）交叉核對的規則不變：
     座標或 did 不一致回 None，不猜。舊的 map_size（401）參數改為 map_half（D-18）。
  2. resolve_home 照卡片只回 (x, y)｜None；舊版的 Config 備用（cfg_home）與說明字串移到呼叫端
     （A5b hide_exec），parsers 不認識 Config（A2a-1 決定）。
  3. 側欄座標文字的方向控制字元改用 constants.BIDI 清除，另清 U+200E／U+200F（BIDI 沒涵蓋）。
parse_village_list：
  - 清單取自 viewData.ownPlayer.villageList（id、name、x、y）；作用中的村取自 ownPlayer.village.id。
  - is_capital 一律 None（頁面沒有首都標記；C1 允許）。
  - 與側欄交叉核對（A2a-1 決定）：did 集合、座標、作用中的村任何一項不一致丟 ParseError；
    頁面沒有側欄（找不到 div.listEntry.village）時只用 viewData，不算不一致。
  - 回傳前以 VillageRef.validate 驗證（§6 邊界驗證），不合格丟 ParseError。
ParseError 的訊息只放頁面名稱與原因，不放頁面內容（村名、座標、帳號）。
viewData 讀取函式 `_view_data` 是私有複本，見 player.py 說明。
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from ..common.constants import BIDI
from ..common.models import VillageRef
from ..common.schema import ParseError

__all__ = ["parse_active_village", "resolve_home", "parse_village_list"]

_PAGE = "village_list"
_VIEWDATA_RE = re.compile(r"viewData\s*:\s*")
_COORD_RE = re.compile(r"\(\s*(-?\d+)\s*\|\s*(-?\d+)\s*\)")
# 頁面座標格式 (−196|172)：負號是 U+2212；數字外面包方向控制字元（constants.BIDI 沒涵蓋 U+200E／U+200F）
_STRIP_MARKS = dict.fromkeys(map(ord, "\u200e\u200f"), None)


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


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _coords_from_text(text: str) -> Optional[Tuple[int, int]]:
    t = BIDI.sub("", text).translate(_STRIP_MARKS).replace("\u2212", "-")
    m = _COORD_RE.search(t)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _sidebar_entries(html: Any) -> List[Dict[str, Any]]:
    """側欄每個村莊一列：did、座標、是否作用中。讀不到的欄位為 None。"""
    if not isinstance(html, str):
        return []
    out = []
    for el in BeautifulSoup(html, "html.parser").select("div.listEntry.village"):
        did = el.get("data-did")
        grid = el.select_one(".coordinatesGrid")
        out.append({
            "did": int(did) if isinstance(did, str) and did.isdigit() else None,
            "xy": _coords_from_text(grid.get_text("", strip=True)) if grid is not None else None,
            "active": "active" in (el.get("class") or []),
        })
    return out


def _village_from_viewdata(html: Any) -> Optional[Dict[str, Any]]:
    data = _view_data(html)
    own = data.get("ownPlayer") if data else None
    v = own.get("village") if isinstance(own, dict) else None
    if not isinstance(v, dict):
        return None
    x, y = v.get("x"), v.get("y")
    if not _is_int(x) or not _is_int(y):
        return None
    vid = v.get("id")
    return {"id": vid if _is_int(vid) else None, "x": x, "y": y}


def _village_from_sidebar(html: Any) -> Optional[Dict[str, Any]]:
    for e in _sidebar_entries(html):
        if e["active"] and e["xy"] is not None:
            return {"id": e["did"], "x": e["xy"][0], "y": e["xy"][1]}
    return None


def _active_village(html: Any, map_half: Optional[int]) -> Optional[Dict[str, Any]]:
    """目前選中的村莊 → dict(id, x, y, source)；讀不到、兩處不一致、座標超出地圖一律 None（不猜）。
    source：'viewData+sidebar'（兩處一致）／'viewData'／'sidebar'（只有一處讀到）。"""
    a, b = _village_from_viewdata(html), _village_from_sidebar(html)
    if a and b and (a["x"], a["y"]) != (b["x"], b["y"]):
        return None
    if a and b and a["id"] and b["id"] and a["id"] != b["id"]:
        return None
    v, src = (a, "viewData") if a else (b, "sidebar") if b else (None, None)
    if v is None:
        return None
    if a and b:
        src = "viewData+sidebar"
    if map_half is not None and not (-map_half <= v["x"] <= map_half and -map_half <= v["y"] <= map_half):
        return None
    return {"id": v["id"] or (b or {}).get("id"), "x": v["x"], "y": v["y"], "source": src}


def parse_active_village(html: str, map_half: Optional[int] = None) -> Optional[int]:
    """目前選中的村莊 did；讀不到、兩處來源不一致、座標超出 ±map_half 回 None。"""
    v = _active_village(html, map_half)
    return v["id"] if v else None


def resolve_home(html: str, map_half: Optional[int] = None) -> Optional[Tuple[int, int]]:
    """目前選中村莊的座標 (x, y)；讀不到、兩處不一致、超出 ±map_half 回 None。
    Config 備用（home_x／home_y）由呼叫端處理，這裡不認識 Config。"""
    v = _active_village(html, map_half)
    return (v["x"], v["y"]) if v else None


def _cross_check_sidebar(html: Any, items: List[Tuple[int, str, int, int]], active_did: int) -> None:
    entries = _sidebar_entries(html)
    if not entries:
        return                      # 頁面沒有側欄：只能用 viewData，不算不一致
    side: Dict[int, Dict[str, Any]] = {}
    for e in entries:
        if e["did"] is None or e["did"] in side:
            raise ParseError(_PAGE, "側欄的村莊 did 讀不到或重複")
        side[e["did"]] = e
    if set(side) != {did for did, _, _, _ in items}:
        raise ParseError(_PAGE, "側欄的村莊與 viewData.villageList 不一致")
    for did, _, x, y in items:
        xy = side[did]["xy"]
        if xy is not None and xy != (x, y):
            raise ParseError(_PAGE, "側欄座標與 viewData.villageList 不一致")
    active = [e["did"] for e in entries if e["active"]]
    if active and active != [active_did]:
        raise ParseError(_PAGE, "側欄作用中的村與 viewData 不一致")


def parse_village_list(html: str, map_half: Optional[int] = None) -> List[VillageRef]:
    """頁面上全部村莊 → list[VillageRef]（順序同 viewData.villageList；恰有一個 active）。
    is_capital 一律 None。讀不到、欄位不合法、與側欄矛盾、不符 C1 契約都丟 ParseError。"""
    data = _view_data(html)
    if data is None:
        raise ParseError(_PAGE, "viewData 找不到或不是 JSON 物件")
    own = data.get("ownPlayer")
    if not isinstance(own, dict):
        raise ParseError(_PAGE, "viewData.ownPlayer 不存在或不是物件")
    raw = own.get("villageList")
    if not isinstance(raw, list) or not raw:
        raise ParseError(_PAGE, "villageList 不存在、不是清單或是空的")
    cur = own.get("village")
    active_did = cur.get("id") if isinstance(cur, dict) else None
    if not _is_int(active_did):
        raise ParseError(_PAGE, "ownPlayer.village.id 讀不到")

    items: List[Tuple[int, str, int, int]] = []
    seen = set()
    for i, it in enumerate(raw, 1):
        if not isinstance(it, dict):
            raise ParseError(_PAGE, f"villageList 第 {i} 項不是物件")
        did, name, x, y = it.get("id"), it.get("name"), it.get("x"), it.get("y")
        if not (_is_int(did) and isinstance(name, str) and name.strip() and _is_int(x) and _is_int(y)):
            raise ParseError(_PAGE, f"villageList 第 {i} 項欄位缺漏或型別不合法")
        if did in seen:
            raise ParseError(_PAGE, f"villageList 第 {i} 項的 did 重複")
        seen.add(did)
        items.append((did, name.strip(), x, y))
    if active_did not in seen:
        raise ParseError(_PAGE, "目前的村不在 villageList 內")
    _cross_check_sidebar(html, items, active_did)

    ctx = {"map_half": map_half} if map_half is not None else None
    refs = []
    for i, (did, name, x, y) in enumerate(items, 1):
        ref = VillageRef(did=did, name=name, x=x, y=y, is_capital=None, active=(did == active_did))
        errors = ref.validate(ctx)
        if errors:
            raise ParseError(_PAGE, f"villageList 第 {i} 項不符合 VillageRef 契約：{errors[0]}")
        refs.append(ref)
    return refs
