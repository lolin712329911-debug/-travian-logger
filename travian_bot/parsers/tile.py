#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/parsers/tile.py（ps-09）
版本：v0.1（A2b）
用途：綠洲格詳情（`/api/v1/map/tile-details` 回傳 JSON 的 `html` 欄，根節點 `div#tileDetails`）的解析。
      純函式：HTML 進、資料出，不連遊戲、不連 Sheet。
依賴：cm-09（parsed）、cm-11（schema，ParseError）。不依賴 cm-03、cm-07：座標與地圖格編號只取自網址、數字用 `\\d` 取，
      不需清 BIDI；座標與 map_id 是否一致（geo.map_id 公式）由呼叫端核對。
部署狀態：未部署（GA 前不 live）。

公開介面
  parse_tile_details(html, locale="zh-TW") → TileSafety
      事實欄位＋保守的 `safe`。只收綠洲格；座標讀不到、不是綠洲格、`occupied` 與標題核對不符 → ParseError。

來源：舊 oasis_check.py v0.2（✓ 已讀）的 parse_tile_details、is_safe。**重新規劃**（§5.1(d) 成立，樣本 S15a～c 三份）：
  1. 舊碼靠中文字面（「未被佔領」「已被佔領」「加成」「軍隊：」「持有人：」「無」）→ 全部改結構選擇器；
     只剩兩處中文：佔領事件的時間文字（只存原文）與 zh-TW 標題核對（locale 不是 zh-TW 則略過）。
  2. is_safe 與 recent_occupy_warning 不進 parser：`safe` 只看「未佔領且動物表存在且為空」；近期佔領的判斷（靠「今天／昨天」字樣）
     留給 domain，這裡只保留 `occupy_events` 原文。
  3. 舊碼用 `\\d` 與標題座標；改取「中心地圖」連結 `a[data-centermap]` 的 x／y 與 `targetMapId`（沒有才取模擬連結的 `kid`）。
  4. 陷阱：同頁有兩個 `id="troop_info"`（動物表與報告分頁表，後者 class 含 `rep`），用 class 區分；
     已佔領格沒有動物表＝animals 為 None（未知），不等於「沒有動物」（`{}`）。
樣本：S15a `map_NN`（未佔領、動物表「無」）、S15b `map_NY`（未佔領、3 種動物）、S15c `map_YN`（已佔領、無動物表）。
      ✗ 三份都是同一個種族語系（舊服 zh-TW）；佔領事件時間的格式只見「今天, HH:MM」「昨天, HH:MM」「2 日前, HH:MM」「DD.MM.YY, HH:MM」；
      ✗ 已佔領格其他欄位（例如 `#village_info` 缺公會）只依選擇器容錯，沒有樣本。
ParseError 的訊息只放頁面名稱與原因，不放頁面內容。
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from ..common.parsed import TileSafety
from ..common.schema import ParseError

__all__ = ["parse_tile_details"]

_PAGE = "tile"
_TITLE_TAKEN = "已被佔領"          # zh-TW 標題；「未被佔領」不含這四字
_TITLE_FREE = "未被佔領"
_X_RE = re.compile(r"[?&]x=(-?\d+)")
_Y_RE = re.compile(r"[?&]y=(-?\d+)")
_TARGET_RE = re.compile(r"[?&]targetMapId=(\d+)")
_KID_RE = re.compile(r"[?&]kid=(\d+)")
_NUM_RE = re.compile(r"\d+")
_DIST_RE = re.compile(r"\s*(\d+(?:\.\d+)?)")


def _need_str(html: Any) -> str:
    if not isinstance(html, str) or not html.strip():
        raise ParseError(_PAGE, "輸入不是字串或是空的")
    return html


def _int_in(pattern: "re.Pattern[str]", text: str) -> Optional[int]:
    m = pattern.search(text)
    return int(m.group(1)) if m else None


def _class_n(el: Any, prefix: str) -> Optional[int]:
    """class 清單中 `<prefix>N`（oasis-7、r2、u35）的 N；沒有回 None。prefix 後的連字號依樣本：oasis-7、r2、u35。"""
    for c in el.get("class", []):
        m = re.fullmatch(rf"{re.escape(prefix)}-?(\d+)", c)
        if m:
            return int(m.group(1))
    return None


def _flat(el: Any) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip()


def _coords_and_map_id(root: Any) -> Tuple[int, int, int]:
    center = root.select_one("a[data-centermap]")
    href = center.get("href", "") if center is not None else ""
    x, y = _int_in(_X_RE, href), _int_in(_Y_RE, href)
    if x is None or y is None:
        raise ParseError(_PAGE, "讀不到座標（沒有「中心地圖」連結或連結沒有 x／y）")
    map_id = None
    for a in root.select("a[href]"):
        map_id = _int_in(_TARGET_RE, a["href"])
        if map_id is not None:
            break
    if map_id is None:                               # 沒有任何 targetMapId 才取模擬連結的 kid
        for a in root.select("a[href]"):
            map_id = _int_in(_KID_RE, a["href"])
            if map_id is not None:
                break
    if map_id is None:
        raise ParseError(_PAGE, "讀不到地圖格編號（沒有 targetMapId 也沒有模擬連結的 kid）")
    return x, y, map_id


def _owner(root: Any) -> Tuple[Optional[int], Optional[int], Optional[Tuple[int, int]]]:
    info = root.select_one("#village_info")
    if info is None:
        return None, None, None
    uid = alliance = None
    village = None
    for a in info.select("a[href]"):
        href = a["href"]
        if uid is None:
            m = re.match(r"^/profile/(\d+)", href)
            if m:
                uid = int(m.group(1))
                continue
        if alliance is None:
            m = re.match(r"^/alliance/(\d+)", href)
            if m:
                alliance = int(m.group(1))
                continue
        if village is None and "karte.php" in href:
            x, y = _int_in(_X_RE, href), _int_in(_Y_RE, href)
            if x is not None and y is not None:
                village = (x, y)
    return uid, alliance, village


def _animals(root: Any) -> Optional[Dict[int, int]]:
    """`#map_details` 下 class 不含 `rep` 的 table#troop_info：有表＝單位 id→數量（沒有 img.unit＝{}）；沒有該表＝None。"""
    table = None
    for t in root.select("#map_details table#troop_info"):
        if "rep" not in t.get("class", []):
            table = t
            break
    if table is None:
        return None
    out: Dict[int, int] = {}
    for img in table.select("img.unit"):
        uid = _class_n(img, "u")
        tr = img.find_parent("tr")
        val = tr.select_one("td.val") if tr is not None else None
        m = _NUM_RE.search(val.get_text()) if val is not None else None
        if uid is None or m is None:
            raise ParseError(_PAGE, "動物列讀不出單位或數量")
        out[uid] = out.get(uid, 0) + int(m.group(0))
    return out


def _bonuses(root: Any) -> Tuple[Tuple[int, int], ...]:
    out = []
    for tr in root.select("#distribution tr"):
        icon = tr.select_one("i")
        val = tr.select_one("td.val")
        n = _class_n(icon, "r") if icon is not None else None
        m = _NUM_RE.search(val.get_text()) if val is not None else None
        if n is None or m is None:
            continue
        if not 1 <= n <= 4:
            raise ParseError(_PAGE, "加成的資源編號不在 1～4")
        out.append((n - 1, int(m.group(0))))
    return tuple(out)


def _distance(root: Any) -> Optional[float]:
    td = root.select_one("#distance td.bold")
    if td is None:
        return None
    m = _DIST_RE.match(td.get_text())
    return float(m.group(1)) if m else None


def parse_tile_details(html: str, locale: str = "zh-TW") -> TileSafety:
    html = _need_str(html)
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#tileDetails")
    if root is None:
        raise ParseError(_PAGE, "找不到 #tileDetails")
    if "oasis" not in root.get("class", []):
        raise ParseError(_PAGE, "不是綠洲格（根節點沒有 oasis class）")

    x, y, map_id = _coords_and_map_id(root)
    occupied = root.select_one("#village_info") is not None
    if locale == "zh-TW":
        h1 = root.select_one("h1.titleInHeader")
        title = _flat(h1) if h1 is not None else ""
        # 先看「未被佔領」再看「已被佔領」；兩者都沒有＝無法核對 → ParseError
        if _TITLE_FREE in title:
            title_occupied = False
        elif _TITLE_TAKEN in title:
            title_occupied = True
        else:
            raise ParseError(_PAGE, "標題沒有佔領狀態字樣，無法核對")
        if title_occupied != occupied:
            raise ParseError(_PAGE, "標題的佔領狀態與頁面內容不一致")

    uid, alliance, village = _owner(root) if occupied else (None, None, None)
    animals = _animals(root)
    events: List[str] = [_flat(td) for td in root.select("#surrounding_info td")]
    return TileSafety(
        x=x, y=y, map_id=map_id, occupied=occupied,
        owner_uid=uid, alliance_id=alliance, owner_village=village,
        animals=animals, bonuses=_bonuses(root), distance=_distance(root),
        oasis_type=_class_n(root, "oasis"), occupy_events=tuple(events),
        safe=(not occupied and animals == {}),
    )
