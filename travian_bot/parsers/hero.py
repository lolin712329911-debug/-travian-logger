#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/parsers/hero.py（ps-05）
版本：v0.1（A2b）
用途：英雄狀態（HUD＋冒險頁 JSON 合併）與冒險清單（JSON，已渲染表格時逐列核對）的解析。
      純函式：HTML 進、資料出，不碰網路、不碰 Sheet。
依賴：cm-09（parsed）、cm-03（constants，BIDI）、cm-11（schema，ParseError）。
部署狀態：未部署（GA 前不 live）。

公開介面
  parse_hero_status(html) → HeroState
      HUD（`#topBarHero`，任何頁都有）與冒險頁 `viewData` 的英雄 JSON 合併；讀不到的欄位為 None；
      HUD 與 JSON 都找不到 → ParseError。
  parse_adventures(html)  → tuple[Adventure, ...]
      讀冒險頁 `viewData` 的 JSON（原始 HTML 即可，不需瀏覽器渲染）；頁面已渲染出 `table.adventureList` 時逐列核對
      地點、距離、秒數並補 icon／clickable，不一致 → ParseError；沒有表格＝這兩欄為 None；JSON 找不到 → ParseError。

來源：舊 travian_hero.py hero-v1.4（✓ 已讀）的 parse_hero_hud、parse_hero_json、parse_adventure_rows、rows_match_json；
      §5.1 判定：輸入輸出對得上卡片、無全域狀態、依賴合規、有樣本可做 golden、格式符合 §6，五條皆成立 → 套用（沿用＋修改）。
有意的修改（golden 以新行為為準）：
  1. HUD 與 JSON 合併成一個 HeroState（舊為 HeroHud＋HeroState 兩個）；dataclass 移到 cm-09。
  2. 舊檔 try／except 匯入 travian_const 與備援字元表 → 改用 cm-03 的 BIDI（正規表示式），不留備援。
  3. 時間欄位 `*_s`、讀不到 None、解析失敗丟 ParseError（舊：回 None 或回預設值）。
  4. 難度：difficulty＝JSON 整數，hard＝（difficulty＝0）（§10 v0.43）；狀態碼原樣保留，意義用 cm-03 HERO_STATUS。
  5. 距離不再 `.3g` 取整，保留 JSON 原值；與表格核對時容許 0.15（頁面顯示四捨五入到 2 位或 3 位有效數字）。
  6. 解析器改用 html.parser（不需 lxml）；JSON 取法改成 `viewData:` 後第一個可解析的 JSON 物件（舊用貪婪 regex 連到 `activePerspective`）。
  7. 補 arrival_at（epoch 秒）與 HUD 的經驗百分比、冒險數；冒險去程（status 50）的 `adventure` 與回程（status 9）的 `arrivalAt` 皆有樣本。
**移出**：parse_hero_inventory（舊檔沒有、無樣本）→ 留給 SAMP／item_transfer；plan_adventure（決策）→ 歸 domain（dm-06）。
樣本：S18a／S18b（Asia 8 返回中，原始頁）、S18c（Intl 11 去冒險，原始頁）、S18d（Asia 8 渲染後 `#heroAdventure` DOM 片段）、
      集結點概況與表單頁的 HUD（英雄在家、返回、出發）。

viewData 讀取函式 `_view_data` 是私有複本（check_arch 禁止 parsers 互相 import）。ParseError 的訊息只放頁面名稱與原因，
不放頁面內容。
"""
import html as _html
import json
import re
from typing import Any, List, Optional, Tuple

from bs4 import BeautifulSoup

from ..common.constants import BIDI
from ..common.parsed import Adventure, HeroState
from ..common.schema import ParseError

__all__ = ["parse_hero_status", "parse_adventures"]

_PAGE = "hero"
_VIEWDATA_RE = re.compile(r"viewData\s*:\s*")
_PCT_RE = re.compile(r"(\d+)\s*%")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_DUR_RE = re.compile(r"(\d+):(\d{2}):(\d{2})")
_DIST_TOLERANCE = 0.15          # 頁面距離與 JSON 原值的容許誤差（舊 hero-v1.4 同值）


# ---------------------------------------------------------------- 共用小工具
def _need_str(html: Any) -> str:
    if not isinstance(html, str) or not html.strip():
        raise ParseError(_PAGE, "輸入不是字串或是空的")
    return html


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


def _int_or_none(v: Any) -> Optional[int]:
    return v if _is_int(v) else None


def _bool_or_none(v: Any) -> Optional[bool]:
    return v if isinstance(v, bool) else None


def _clean(s: str) -> str:
    return BIDI.sub("", s).strip()


def _unescape_twice(s: str) -> str:
    # 經驗標題是雙重跳脫（&amp;#x202d;），體力是單重；多做一次無害
    return _html.unescape(_html.unescape(s))


def _hero_json(data: Optional[dict]) -> Optional[dict]:
    """viewData 裡的英雄物件。冒險頁是 data.ownPlayer.hero；其他頁若直接有 ownPlayer.hero 也認；找不到回 None。"""
    if not isinstance(data, dict):
        return None
    for root in (data.get("data"), data):
        own = root.get("ownPlayer") if isinstance(root, dict) else None
        hero = own.get("hero") if isinstance(own, dict) else None
        if isinstance(hero, dict):
            return hero
    return None


# ---------------------------------------------------------------- HUD
def _hud_pct(soup: BeautifulSoup, selector: str) -> Optional[int]:
    el = soup.select_one(selector)
    if el is None:
        return None
    m = _PCT_RE.search(_clean(_unescape_twice(el.get_text())))   # 經驗標題含「經驗 97%||還需要…」，只取第一個百分比
    return int(m.group(1)) if m else None


def _hud(soup: BeautifulSoup) -> dict:
    out = {"at_home": None, "health_pct": None, "exp_pct": None, "adventures_count": None}
    out["health_pct"] = _hud_pct(soup, "#topBarHero svg.health path.title > title")
    out["exp_pct"] = _hud_pct(soup, "#topBarHero svg.experience path.title > title")
    c = soup.select_one("#topBarHero a.adventure .content")
    if c is not None:
        m = re.search(r"\d+", _clean(c.get_text()))
        if m:
            out["adventures_count"] = int(m.group(0))
    # 圖示只能分在家／在外；去程與返回要看 JSON 的 status
    if soup.select_one("#topBarHero .heroStatus i.heroHome"):
        out["at_home"] = True
    elif soup.select_one("#topBarHero .heroStatus i.heroRunning"):
        out["at_home"] = False
    return out


def _village_id(v: Any) -> Optional[int]:
    """status.inVillage：整數、或帶 id 的物件；null／其他＝None（在家樣本未見，✗）。"""
    if isinstance(v, dict):
        return _int_or_none(v.get("id"))
    return _int_or_none(v)


# ---------------------------------------------------------------- 公開：英雄狀態
def parse_hero_status(html: str) -> HeroState:
    html = _need_str(html)
    soup = BeautifulSoup(html, "html.parser")
    has_hud = soup.select_one("#topBarHero") is not None
    hero = _hero_json(_view_data(html))
    if not has_hud and hero is None:
        raise ParseError(_PAGE, "找不到英雄 HUD 與英雄 JSON")

    hud = _hud(soup) if has_hud else {"at_home": None, "health_pct": None, "exp_pct": None, "adventures_count": None}
    vals = {"status": None, "regenerating": None, "home_did": None, "in_village_did": None, "adventure_no": None,
            "arrival_in_s": None, "arrival_at": None, "difficulty_bonus": None, "duration_bonus": None}
    if hero is not None:
        st = hero.get("status")
        if not isinstance(st, dict) or not _is_int(st.get("status")):
            raise ParseError(_PAGE, "英雄 JSON 沒有 status.status")
        adv = st.get("adventure")
        home = hero.get("homeVillage")
        vals.update(
            status=st["status"],
            regenerating=_bool_or_none(hero.get("isRegenerating")),
            home_did=_int_or_none(home.get("id")) if isinstance(home, dict) else None,
            in_village_did=_village_id(st.get("inVillage")),
            adventure_no=_int_or_none(adv.get("number")) if isinstance(adv, dict) else None,
            arrival_in_s=_int_or_none(st.get("arrivalIn")),
            arrival_at=_int_or_none(st.get("arrivalAt")),
            difficulty_bonus=_bool_or_none(hero.get("adventureDifficultyBonus")),
            duration_bonus=("adventureDurationBonus" in hero and hero["adventureDurationBonus"] is not None),
        )
    return HeroState(**hud, **vals)


# ---------------------------------------------------------------- 公開：冒險清單
def _adventures_json(html: str) -> Tuple[dict, ...]:
    hero = _hero_json(_view_data(html))
    if hero is None:
        raise ParseError(_PAGE, "找不到冒險頁的英雄 JSON")
    raw = hero.get("adventures")
    if not isinstance(raw, list):
        raise ParseError(_PAGE, "英雄 JSON 沒有 adventures 清單")
    return tuple(raw)


def _row_distance(td: Any) -> Optional[float]:
    if td is None:
        return None
    m = _NUM_RE.search(_clean(td.get_text()))
    return float(m.group(0)) if m else None


def _row_duration(el: Any) -> Optional[int]:
    if el is None:
        return None
    m = _DUR_RE.search(_clean(el.get_text()))
    if not m:
        return None
    h, mi, s = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s


def _table_rows(html: str) -> Optional[List[dict]]:
    """渲染後的 `table.adventureList` → 每列的事實；沒有表格回 None。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.adventureList")
    if table is None:
        return None
    rows = []
    for tr in table.select("tbody tr"):
        img = tr.select_one("td.place img")
        classes = tuple(img.get("class", [])) if img is not None else ()
        icon_el = tr.select_one("td.difficulty i")
        icon = None
        if icon_el is not None:
            cl = icon_el.get("class", [])
            icon = "hard" if "difficulty_hard" in cl else ("normal" if "difficulty_normal" in cl else None)
        btn = tr.select_one("td.button button")
        rows.append({
            "classes": classes,
            "distance": _row_distance(tr.select_one("td.distance")),
            "duration": _row_duration(tr.select_one("td.duration div.duration")),
            "icon": icon,
            "clickable": bool(btn is not None and "disabled" not in btn.get("class", [])),
        })
    return rows


def parse_adventures(html: str) -> Tuple[Adventure, ...]:
    html = _need_str(html)
    raw = _adventures_json(html)
    items = []
    for i, a in enumerate(raw):
        if not isinstance(a, dict):
            raise ParseError(_PAGE, f"第 {i + 1} 筆冒險不是物件")
        dist = a.get("distance")
        if not (_is_int(a.get("number")) and isinstance(a.get("place"), str) and _is_int(a.get("difficulty"))
                and _is_int(a.get("travelingDuration")) and isinstance(dist, (int, float)) and not isinstance(dist, bool)):
            raise ParseError(_PAGE, f"第 {i + 1} 筆冒險缺少必要欄位或型別不符")
        items.append(a)

    rows = _table_rows(html)
    if rows is not None:
        if len(rows) != len(items):
            raise ParseError(_PAGE, "表格列數與 JSON 筆數不一致")
        for i, (r, a) in enumerate(zip(rows, items)):
            if a["place"] not in r["classes"]:          # 地點以 JSON 為準：表格圖片 class 要含 JSON 的地點（新地形也能對上）
                raise ParseError(_PAGE, f"第 {i + 1} 列的地點與 JSON 不一致")
            if r["distance"] is None or abs(r["distance"] - float(a["distance"])) > _DIST_TOLERANCE:
                raise ParseError(_PAGE, f"第 {i + 1} 列的距離與 JSON 不一致")
            if r["duration"] != a["travelingDuration"]:
                raise ParseError(_PAGE, f"第 {i + 1} 列的秒數與 JSON 不一致")

    out = []
    for i, a in enumerate(items):
        out.append(Adventure(
            number=a["number"], distance=float(a["distance"]), place=a["place"], difficulty=a["difficulty"],
            hard=(a["difficulty"] == 0), duration_s=a["travelingDuration"],
            x=_int_or_none(a.get("x")), y=_int_or_none(a.get("y")),
            icon=rows[i]["icon"] if rows is not None else None,
            clickable=rows[i]["clickable"] if rows is not None else None,
        ))
    return tuple(out)
