#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/parsers/village.py（ps-01）
版本：v0.1（A2a-2a）
用途：dorf1（資源田頁）與 dorf2（村莊中心）的解析，以及每頁都有的頁面事實（PageFacts，D-18）。
      純函式：HTML 進、資料出，不碰網路、不碰 Sheet。
依賴：cm-09（parsed）、cm-03（constants，BIDI）、cm-11（schema，ParseError）。
部署狀態：未部署（GA 前不 live）。

公開介面
  parse_dorf1(html)        → Dorf1（庫存、產量、容量、可用穀物、資源田、施工佇列、來襲、移動列、保護／Plus 秒數）
  parse_movements(html)    → list[dict]（dorf1 的 #movements 表格；沒有表格＝空 list）
  parse_dorf2(html)        → Dorf2（全部建築位）
  parse_dorf2_slots(html)  → tuple[BuildingSlot, ...]（同 Dorf2.slots）
  parse_page_facts(html)   → PageFacts（任何 Travian 頁面都可；讀不到的欄位為 None，不丟 ParseError）

來源：舊 travian_pages.py v2.38 的 parse_dorf1、parse_movements、parse_dorf2、parse_dorf2_slots（✓ 已讀，沿用＋修改）；
      parse_page_facts 新寫。樣本：舊服 Asia 8 的 S1a／S1b（dorf1）、S12a／S12b（dorf2）。

與舊版的差異（§5.1 判定：輸入輸出對得上卡片與 §6 契約、無全域狀態、依賴合規、有樣本可做 golden、格式符合 §6，
五條皆成立 → 套用；以下是有意的修改，golden 以新行為為準）：
  1. 回傳 parsed 的 dataclass（舊為 State／Field／Slot／dict）；list→tuple；cost→Res4（4 個整數的 tuple）。
  2. 讀不到就丟 ParseError，不回預設值（舊碼 var resources 缺漏時庫存全 0、資源田沒有等級時當 0）。
     丟 ParseError 的情況：var resources 或其中任一格缺漏、倉庫容量木磚鐵不等、資源田不是 18 個（aid 1～18、gid 1～4、
     有等級）、升級成本只有一部分、施工佇列某項沒有倒數秒數（不能少算佇列）、建築位不是 aid 19～40 各一個、
     重複 aid（城牆 top／bottom 除外）、有建築卻讀不到等級。
  3. incoming_attacks 改成「目前村」的來襲數，取自 viewData.ownPlayer.villageList 中作用中那筆：舊碼用
     `incomingAttacksAmount": 對整頁 regex 加總，而這個鍵在 villageList 每個村各有一筆，所以多村時會把其他村的
     來襲算進來（舊服樣本是 2 個村）。讀不到＝None（舊碼 0 同時代表「沒有」與「不知道」）。
  4. parse_movements：辨識 `hero_on_adventure` 為 kind `adventure`；其餘 class 原樣保留（舊碼只認 att／def／rai／rei
     加數字，其餘一律 'unknown'）；沒有 class 才是 'unknown'。
  5. parse_dorf2 回 Dorf2（全部建築位）；舊 parse_dorf2 回 {gid: (aid, level)} 且只含 BUILDING_GIDS，這個過濾移到
     使用端（stage／domain 從 slots 自己挑）。parse_dorf2_slots 以 aid 去重：城牆（aid 40）等級大於 0 時有 top／bottom
     兩個節點，取有 data-building-id 者（舊碼回 23 筆）。
  6. 施工佇列的顯示文字 info 只放「名稱 等級 N」，不含「剩 h:mm:ss」（剩餘秒數已在 remaining_s）；名稱讀不到＝None
     （舊為「（未知建築）」）。
  7. 沒有升級成本（已達最高等級）時 cost／build_time_s 為 None（舊為空 list／0）。
  8. 兩個 class `underConstruction` 旗標選擇器已驗證（dorf1 資源田用 S1b、dorf2 建築位用 S12a／S12b 對照施工佇列），回 bool。
還在的中文字面：`新手保護`（protection_s，舊碼沿用；頁面沒有結構選擇器，待 S9，v0.31）。其餘判斷都不依賴頁面語言。

viewData 讀取函式 `_view_data` 是私有複本（check_arch 禁止 parsers 互相 import；見 player.py 說明），
tests/parsers/test_viewdata_helpers.py 的 MODULES 含本檔。ParseError 的訊息只放頁面名稱與原因，不放頁面內容。
"""
import copy
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from ..common.constants import BIDI
from ..common.parsed import (
    BuildingSlot, Dorf1, Dorf2, PageFacts, PageVillage, QueueItem, ResField,
)
from ..common.schema import ParseError

__all__ = ["parse_dorf1", "parse_movements", "parse_dorf2", "parse_dorf2_slots", "parse_page_facts"]

_PAGE = "village"
_VIEWDATA_RE = re.compile(r"viewData\s*:\s*")
_RESOURCES_RE = re.compile(r"var\s+resources\s*=\s*\{(.*?)\}\s*;", re.S)
_LVAL_RE = re.compile(r'"l(\d)"\s*:\s*(-?\d+)')
_LEVEL_CLASS_RE = re.compile(r"\blevel(\d+)\b")
_TIP_COST_RE = re.compile(r'class="r(\d)Big"></i><span class="value ">(\d+)<')
_TIP_DUR_RE = re.compile(r'clock_medium"></i><span class="value ">(\d+):(\d{2}):(\d{2})<')
_LEAD_INT_RE = re.compile(r"\s*(\d+)")
_N_FIELDS = 18                                  # 資源田 aid 1～18
_SLOT_AIDS = frozenset(range(19, 41))           # 村莊中心 aid 19～40（含集結點 39、城牆 40）
_MOVEMENT_KINDS = {"att1": "attack", "def1": "reinforcement", "hero_on_adventure": "adventure"}


# ---------------------------------------------------------------- 共用小工具
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


def _need_str(html: Any) -> str:
    if not isinstance(html, str) or not html.strip():
        raise ParseError(_PAGE, "輸入不是字串或是空的")
    return html


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _attr_int(el: Any, name: str) -> Optional[int]:
    v = el.get(name)
    return int(v) if isinstance(v, str) and v.isdigit() else None


def _own_villages(data: Optional[dict]) -> Optional[List[dict]]:
    """viewData.ownPlayer.villageList 攤平成村莊 dict 的 list（清單裡的村莊群組 villages 會展開）；結構不對回 None。"""
    own = data.get("ownPlayer") if data else None
    raw = own.get("villageList") if isinstance(own, dict) else None
    if not isinstance(raw, list):
        return None
    out: List[dict] = []
    for it in raw:
        if not isinstance(it, dict):
            return None
        if isinstance(it.get("villages"), list):
            for sub in it["villages"]:
                if not isinstance(sub, dict):
                    return None
                out.append(sub)
        else:
            out.append(it)
    return out


# ---------------------------------------------------------------- dorf1
def _js_dict(block: str, key: str) -> Dict[int, int]:
    m = re.search(r"(?<![A-Za-z])" + key + r"\s*:\s*\{([^}]*)\}", block)
    return {int(i): int(v) for i, v in _LVAL_RE.findall(m.group(1))} if m else {}


def _res4(d: Dict[int, int], what: str) -> Tuple[int, int, int, int]:
    if not all(i in d for i in (1, 2, 3, 4)):
        raise ParseError(_PAGE, f"var resources.{what} 缺少 l1～l4")
    return (d[1], d[2], d[3], d[4])


def _parse_fields(soup: BeautifulSoup) -> Tuple[ResField, ...]:
    out: List[ResField] = []
    for a in soup.select("#resourceFieldContainer a.resourceField"):
        aid, gid = _attr_int(a, "data-aid"), _attr_int(a, "data-gid")
        classes = a.get("class") or []
        m = _LEVEL_CLASS_RE.search(" ".join(classes))
        if aid is None or gid is None or m is None:
            raise ParseError(_PAGE, "資源田缺少 aid／gid／等級")
        tip = a.get("title") or ""
        costs = _TIP_COST_RE.findall(tip)
        cost = None
        if costs:
            by_idx = sorted((int(i), int(v)) for i, v in costs)
            if [i for i, _ in by_idx] != [1, 2, 3, 4]:
                raise ParseError(_PAGE, f"資源田 {aid} 的升級成本不是完整的 4 項")
            cost = tuple(v for _, v in by_idx)
        dur = _TIP_DUR_RE.search(tip)
        out.append(ResField(
            aid=aid, gid=gid, level=int(m.group(1)), cost=cost,
            build_time_s=(int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + int(dur.group(3))) if dur else None,
            under_construction="underConstruction" in classes, url=None))
    aids = sorted(f.aid for f in out)
    if aids != list(range(1, _N_FIELDS + 1)) or any(f.gid not in (1, 2, 3, 4) for f in out):
        raise ParseError(_PAGE, "資源田不是 aid 1～18 各一個、gid 1～4")
    return tuple(sorted(out, key=lambda f: f.aid))


def _queue_info(li: Any) -> Optional[str]:
    n = li.select_one("div.name")
    if n is None:
        return None
    n = copy.copy(n)                            # 不動原本的 soup
    lvl = ""
    lv = n.select_one("span.lvl")
    if lv is not None:
        lvl = BIDI.sub("", lv.get_text(" ", strip=True))
        lv.extract()
    name = BIDI.sub("", n.get_text(" ", strip=True))
    return " ".join(x for x in (name, lvl) if x) or None


def _parse_queue(soup: BeautifulSoup) -> Tuple[QueueItem, ...]:
    out: List[QueueItem] = []
    for li in soup.select("div.buildingList li"):
        t = li.select_one("span.timer")
        v = t.get("value") if t is not None else None
        if not (isinstance(v, str) and v.isdigit()):
            raise ParseError(_PAGE, "施工佇列有一項讀不到倒數秒數")
        out.append(QueueItem(remaining_s=int(v), info=_queue_info(li)))
    return tuple(out)


def _movements(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    tbl = soup.find(id="movements")
    out: List[Dict[str, Any]] = []
    if tbl is None:
        return out
    for tr in tbl.find_all("tr"):
        img = tr.select_one("td.typ img")
        if img is None:
            continue
        classes = img.get("class") or []
        kind = next((_MOVEMENT_KINDS[c] for c in classes if c in _MOVEMENT_KINDS), None)
        if kind is None:
            kind = classes[0] if classes else "unknown"
        label = BIDI.sub("", (tr.select_one("div.mov") or tr).get_text(" ", strip=True))
        n = _LEAD_INT_RE.match(label)
        t = tr.select_one("span.timer")
        v = t.get("value") if t is not None else None
        out.append({"kind": kind, "count": int(n.group(1)) if n else None,
                    "seconds": int(v) if isinstance(v, str) and v.isdigit() else None, "label": label})
    return out


def parse_movements(html: str) -> List[Dict[str, Any]]:
    """dorf1 的 #movements 表格 → [{kind, count, seconds, label}, …]；沒有表格＝空 list。"""
    return _movements(_soup(_need_str(html)))


def _incoming_attacks(html: str) -> Optional[int]:
    """目前村的來襲數：viewData.ownPlayer.villageList 中 id＝ownPlayer.village.id 那筆的 incomingAttacksAmount。"""
    data = _view_data(html)
    own = data.get("ownPlayer") if data else None
    cur = own.get("village") if isinstance(own, dict) else None
    did = cur.get("id") if isinstance(cur, dict) else None
    villages = _own_villages(data)
    if not _is_int(did) or villages is None:
        return None
    for v in villages:
        if v.get("id") == did:
            n = v.get("incomingAttacksAmount")
            return n if _is_int(n) and n >= 0 else None
    return None


def _sidebar_timers(soup: BeautifulSoup) -> Tuple[Optional[int], Optional[int]]:
    """#sidebarBoxInfobox 的新手保護與 Plus 剩餘秒數（沒有該區塊或沒有倒數＝None）。
    ✗ 「新手保護」是中文字面，待 S9 找結構選擇器（v0.31）；Plus 字樣為拉丁字母。"""
    protection = plus = None
    for li in soup.select("#sidebarBoxInfobox li"):
        t = li.select_one("span.timer")
        v = t.get("value") if t is not None else None
        if not (isinstance(v, str) and v.isdigit()):
            continue
        txt = BIDI.sub("", li.get_text(" ", strip=True))
        if "新手保護" in txt:
            protection = int(v)
        elif "Plus" in txt:
            plus = int(v)
    return protection, plus


def parse_dorf1(html: str) -> Dorf1:
    """dorf1.php → Dorf1。讀不到必要欄位丟 ParseError；選填欄位（來襲、保護、Plus）讀不到為 None。"""
    html = _need_str(html)
    m = _RESOURCES_RE.search(html)
    if m is None:
        raise ParseError(_PAGE, "var resources 找不到")
    blk = m.group(1)
    prod, stock, cap = (_js_dict(blk, k) for k in ("production", "storage", "maxStorage"))
    stock4, prod4, cap4 = _res4(stock, "storage"), _res4(prod, "production"), _res4(cap, "maxStorage")
    if 5 not in prod:
        raise ParseError(_PAGE, "var resources.production 缺少 l5（可用穀物）")
    if not (cap4[0] == cap4[1] == cap4[2]):
        raise ParseError(_PAGE, "木磚鐵的倉庫容量不一致")

    soup = _soup(html)
    movements = _movements(soup)
    etas = [mv["seconds"] for mv in movements if mv["kind"] == "attack" and mv["seconds"] is not None]
    protection, plus = _sidebar_timers(soup)
    return Dorf1(
        stock=stock4, prod=prod4, cap_wh=cap4[0], cap_gr=cap4[3], free_crop=prod[5],
        fields=_parse_fields(soup), queue=_parse_queue(soup),
        incoming_attacks=_incoming_attacks(html), attack_eta_s=min(etas) if etas else None,
        movements=tuple(movements), protection_s=protection, plus_s=plus)


# ---------------------------------------------------------------- dorf2
def _slot_nodes(soup: BeautifulSoup) -> Dict[int, Any]:
    """aid → 建築位節點。同一個 aid 有兩個節點時只允許城牆的 top／bottom，取有 data-building-id 者。"""
    by_aid: Dict[int, Any] = {}
    for s in soup.select("#villageContent .buildingSlot"):
        aid, gid = _attr_int(s, "data-aid"), _attr_int(s, "data-gid")
        if aid is None or gid is None:
            raise ParseError(_PAGE, "建築位缺少 aid 或 gid")
        if aid in by_aid:
            old = by_aid[aid]
            c_old, c_new = set(old.get("class") or []), set(s.get("class") or [])
            if not ({"top", "bottom"} & c_old and {"top", "bottom"} & c_new):
                raise ParseError(_PAGE, f"建築位 aid {aid} 重複")
            if not old.get("data-building-id") and s.get("data-building-id"):
                by_aid[aid] = s
            continue
        by_aid[aid] = s
    return by_aid


def _to_slot(aid: int, s: Any) -> BuildingSlot:
    gid = _attr_int(s, "data-gid")
    a = s.select_one("a.level")
    cls = " ".join(s.get("class") or []) + " " + " ".join((a.get("class") or []) if a is not None else [])
    lv = a.get("data-level") if a is not None else None
    if isinstance(lv, str) and lv.isdigit():
        level = int(lv)
    elif gid == 0:
        level = 0
    else:
        raise ParseError(_PAGE, f"建築位 {aid} 有建築但讀不到等級")
    return BuildingSlot(aid=aid, gid=gid or None, level=level, name=s.get("data-name") or None,
                        under_construction="underConstruction" in cls)


def parse_dorf2_slots(html: str) -> Tuple[BuildingSlot, ...]:
    """dorf2.php → 全部建築位（aid 19～40 各一個，依 aid 排序）。"""
    by_aid = _slot_nodes(_soup(_need_str(html)))
    if set(by_aid) != _SLOT_AIDS:
        raise ParseError(_PAGE, "建築位不是 aid 19～40 各一個")
    return tuple(_to_slot(aid, by_aid[aid]) for aid in sorted(by_aid))


def parse_dorf2(html: str) -> Dorf2:
    """dorf2.php → Dorf2。"""
    return Dorf2(slots=parse_dorf2_slots(html))


# ---------------------------------------------------------------- 頁面事實（D-18）
_LANG_RE = re.compile(r"<html\b[^>]*?\blang\s*=\s*\"([^\"]*)\"", re.I | re.S)
_GPACK_RE = re.compile(r"/gpack/(\d[\d.]*)/")
_TZ_RE = re.compile(r"Travian\.Game\.timeZone\s*=\s*\"([^\"]*)\"")
_TZ_OFFSET_RE = re.compile(r"Travian\.Game\.timezoneOffsetToUTC\s*=\s*(-?\d+)\s*;")
_TS_RE = re.compile(r"Travian\.Game\.timestamp\s*=\s*(\d+)\s*;")


def _first_int(rx: "re.Pattern[str]", html: str) -> Optional[int]:
    m = rx.search(html)
    return int(m.group(1)) if m else None


def _first_str(rx: "re.Pattern[str]", html: str) -> Optional[str]:
    m = rx.search(html)
    return m.group(1) if m and m.group(1) else None


def _page_villages(data: Optional[dict]) -> Optional[Tuple[PageVillage, ...]]:
    villages = _own_villages(data)
    if not villages:
        return None
    out = []
    for v in villages:
        did, x, y = v.get("id"), v.get("x"), v.get("y")
        if not (_is_int(did) and _is_int(x) and _is_int(y)):
            return None
        out.append(PageVillage(did=did, x=x, y=y))
    return tuple(out)


def parse_page_facts(html: str) -> PageFacts:
    """任何 Travian 頁面都含的頁面事實。讀不到的欄位為 None（不丟 ParseError；輸入不是字串才丟）。
    不做任何比對或判斷；比對由 common/server_profile.verify_against_page 負責。"""
    if not isinstance(html, str):
        raise ParseError(_PAGE, "輸入不是字串")
    data = _view_data(html)
    own = data.get("ownPlayer") if data else None
    tribe = own.get("tribeId") if isinstance(own, dict) else None
    return PageFacts(
        tz_name=_first_str(_TZ_RE, html), tz_offset_s=_first_int(_TZ_OFFSET_RE, html),
        lang=_first_str(_LANG_RE, html), gpack=_first_str(_GPACK_RE, html),
        tribe_id=tribe if _is_int(tribe) else None, server_ts=_first_int(_TS_RE, html),
        villages=_page_villages(data))
