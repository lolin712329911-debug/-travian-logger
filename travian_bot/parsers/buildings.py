#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/parsers/buildings.py（ps-03）
版本：v0.1.1（GA-fix3：find_upgrade_url 認新版「按鈕＋JS POST」的升級按鈕，回傳 click:build:<aid>:<gid>）｜v0.1（A2a-2b）
用途：建築頁解析（HTML 進、結構出；不碰網路、不碰 Sheet、無全域可變狀態）：
  parse_building_cost(html)  → UpgradeCost     既有建築頁（build.php?id=<aid>）的升級成本／工期／缺資源資訊
  parse_build_options(html)  → tuple[BuildOption, ...]  空地建造頁（build.php?id=<空地>，body #build.gid0）
  find_upgrade_url(html)     → str | None      單一建築頁上通過白名單的綠色興建／升級按鈕網址
依賴：cm-03（constants.BIDI）、cm-09（parsed）、cm-11（schema.ParseError）；第三方：beautifulsoup4。
部署狀態：未部署（GA 前不 live）。

與舊 travian_pages.py v2.38 的差異（五條判定見交接區塊）：
  沿用：只讀 `upgradeBuilding` 區塊（避開研究院頁各兵種研究成本）、成本只認 r1Big～r4Big、千分位與雙向控制字元清除、
        section1 才是正常工期、網址白名單（多任何參數如 &buildmaster、&as= 一律不算，避免花金幣）。
  修改：①前置條件的等級與目前等級改取數字，不比對「等級」「目前等級」字樣（去中文字面）
        ②`exceeds_storage` → `exchange_disabled`（只描述事實，不推測原因；沒有按鈕＝None）
        ③新增 `afford_in_s`（`errorMessage` 內 `span.timer` 的 value）
        ④回傳結構化 dataclass；讀不到的值用 None（工期不再用 0）；解析失敗丟 ParseError，不回傳空 list／預設值
        ⑤綠色按鈕改認「`button.green`＋onclick 網址通過白名單」，不再要求 class 含 `build`：S10 的興建按鈕 class 是
          `green new`（✓），舊選擇器 `green.build` 在 S10 一個都選不到；`contractLink`／disabled 的按鈕沒有網址，自然排除
        ⑥拿掉 print 警告與 `_rejected_seen` 全域集合（純解析層）；找不到升級區塊時不再退回掃整頁（那是研究院誤判的來源）
  搬走：`_safe_build_url` 的警告職責與 `fetch_build_options`（需要 get）不在本層，歸 infra/gateway 與 actions。
"""
import re
from typing import Optional, Tuple

from bs4 import BeautifulSoup

from ..common.constants import BIDI
from ..common.parsed import BuildCondition, BuildOption, UpgradeCost
from ..common.schema import ParseError

__all__ = ["parse_building_cost", "parse_build_options", "find_upgrade_url"]

_PAGE = "buildings"

# 「興建／擴建」按鈕的網址只認這一種格式（✓ S10：/dorf2.php?id=21&gid=23&action=build&checksum=4cdfae）。
# 金幣（&buildmaster）、看廣告（&as=）、其他多餘參數一律不算。
_BUILD_URL_RE = re.compile(r"/dorf[12]\.php\?id=\d+&gid=\d+&action=build&checksum=[0-9a-fA-F]+")
# v0.1.1：新版頁面的升級按鈕沒有網址，onclick 是無參數的 build_<token>()，真正動作在頁面 script：
#   function build_<token>(token = undefined, masterBuilder = false) { Travian.Promises.post('building/build/<aid>', {..., buildingId: <gid>, ...}) }
# 只認「呼叫端不帶任何參數」（masterBuilder 預設 false，不花金幣）；函式簽名的 masterBuilder 預設不是 false 就不認。
_CLICK_ONCLICK_RE = re.compile(r"\s*(build_\w+)\(\s*\)\s*;?\s*return\s+false\s*;?\s*")
_BUILD_FN_RE = re.compile(
    r"function\s+(build_\w+)\s*\(([^)]*)\)\s*\{\s*Travian\.Promises\.post\(\s*'building/build/(\d+)'\s*,\s*\{([^}]*)\}", re.S)
_BUILDING_ID_RE = re.compile(r"buildingId\s*:\s*(\d+)")
_MASTER_FALSE_RE = re.compile(r"masterBuilder\s*=\s*false")
_HREF_RE = re.compile(r"location\.href\s*=\s*'([^']+)'")
_RES_CLASS_RE = re.compile(r"\br([1-4])Big\b")
_OPEN_BUILDING_RE = re.compile(r"open\(\s*'building'\s*,\s*(\d+)")
_HMS_RE = re.compile(r"(\d+):(\d{2}):(\d{2})")


def _soup(html: str) -> BeautifulSoup:
    if not isinstance(html, str) or not html.strip():
        raise ParseError(_PAGE, "empty html")
    return BeautifulSoup(html, "html.parser")


def _text(el) -> str:
    return BIDI.sub("", el.get_text("", strip=True)) if el is not None else ""


def _digits(s: str) -> Optional[int]:
    """'‭3,220‬' → 3220；沒有數字 → None。"""
    d = re.sub(r"\D", "", BIDI.sub("", s or ""))
    return int(d) if d else None


def _first_int(s: str) -> Optional[int]:
    """文字中第一段數字（不理會周圍的語言字樣）：'等級 3' → 3；'目前等級: ‭0‬' → 0。"""
    m = re.search(r"\d+", BIDI.sub("", s or ""))
    return int(m.group(0)) if m else None


def _seconds(s: str) -> Optional[int]:
    m = _HMS_RE.search(s or "")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None


def _safe_url(onclick: str) -> Optional[str]:
    m = _HREF_RE.search(onclick or "")
    if not m:
        return None
    u = m.group(1)                      # BeautifulSoup 已把 &amp; 還原
    return u if _BUILD_URL_RE.fullmatch(u) else None


def _cost(scope) -> Optional[Tuple[int, int, int, int]]:
    """scope 內的 r1Big～r4Big（木磚鐵穀）；四種都讀到才回，否則 None。cropConsumptionBig 不匹配。"""
    found = {}
    for i in scope.find_all("i"):
        m = _RES_CLASS_RE.search(" ".join(i.get("class", [])))
        v = i.find_next_sibling("span")
        n = _digits(_text(v)) if v is not None else None
        if m and n is not None:
            found[int(m.group(1))] = n
    return tuple(found[k] for k in (1, 2, 3, 4)) if set(found) == {1, 2, 3, 4} else None


def _build_time(scope) -> Optional[int]:
    """section1（一般工期）；section2（看廣告加速）的工期較短，不能拿來用。"""
    d = scope.select_one("div.upgradeButtonsContainer div.section1 .duration span.value")
    return _seconds(_text(d)) if d is not None else None


def _click_token(btn, soup) -> Optional[str]:
    """新版升級按鈕 → 'click:build:<aid>:<gid>'（aid、gid 取自頁面 script 的 POST 內容，供呼叫端核對）；不符安全條件回 None。"""
    m = _CLICK_ONCLICK_RE.fullmatch(btn.get("onclick", "") or "")
    if not m:
        return None
    fname = m.group(1)
    for sc in soup.find_all("script"):
        text = sc.string or sc.get_text()
        if not text or fname not in text:
            continue
        for fm in _BUILD_FN_RE.finditer(text):
            if fm.group(1) != fname:
                continue
            bid = _BUILDING_ID_RE.search(fm.group(4))
            if bid is None or not _MASTER_FALSE_RE.search(fm.group(2)):
                return None
            return f"click:build:{int(fm.group(3))}:{int(bid.group(1))}"
    return None


def _green_url(scope, soup=None) -> Optional[str]:
    box = scope.select_one("div.upgradeButtonsContainer")
    if box is None:
        return None
    for b in box.select("button.green"):
        if "disabled" in b.get("class", []):
            continue
        u = _safe_url(b.get("onclick", ""))
        if u:
            return u
        if soup is not None:                    # v0.1.1：新版按鈕（只有 find_upgrade_url 傳 soup）
            tok = _click_token(b, soup)
            if tok:
                return tok
    return None


def _blocked(scope):
    """(resource_short, exchange_disabled, afford_in_s)：都取自 `div.upgradeBlocked`。"""
    blk = scope.select_one("div.upgradeBlocked")
    if blk is None:
        return False, None, None
    ex = blk.select_one("button.exchange")
    t = blk.select_one("div.errorMessage span.timer")
    afford = _first_int(t.get("value", "")) if t is not None else None
    return ex is not None, (("disabled" in ex.get("class", [])) if ex is not None else None), afford


def _conditions(scope) -> Tuple[BuildCondition, ...]:
    box = scope.select_one("div.upgradeButtonsContainer")
    out = []
    if box is None:
        return ()
    for c in box.select("span.buildingCondition"):
        a = c.find("a")
        om = _OPEN_BUILDING_RE.search(a.get("onclick", "")) if a is not None else None
        lvl_el = next(iter(c.find_all("span", recursive=False)), None)
        out.append(BuildCondition(
            gid=int(om.group(1)) if om else None,
            name=_text(a) or None,
            level=_first_int(_text(lvl_el)) if lvl_el is not None else None,
            met="error" not in c.get("class", []),
            current=_first_int(lvl_el.get("title", "")) if lvl_el is not None else None,
            forbidden=bool(a is not None and a.find("span", style=re.compile("line-through"))),
        ))
    return tuple(out)


# ---------------------------------------------------------------- 公開函式
def parse_building_cost(html: str) -> UpgradeCost:
    """既有建築頁的升級成本。只讀 `div.upgradeBuilding`（退一步只認 `#contract`）；兩者都沒有，或成本不足四格，
    丟 ParseError（舊版回 ([], 0)；研究院、兵營等頁的各兵種成本不是升級成本，不能當它）。"""
    soup = _soup(html)
    scope = soup.select_one("div.upgradeBuilding") or soup.select_one("#contract")
    if scope is None:
        raise ParseError(_PAGE, "no upgradeBuilding block")
    cost = _cost(scope)
    if cost is None:
        raise ParseError(_PAGE, "upgrade cost is not 4 resources")
    short, disabled, afford = _blocked(scope)
    return UpgradeCost(cost=cost, build_time_s=_build_time(scope), resource_short=short,
                       exchange_disabled=disabled, afford_in_s=afford)


def parse_build_options(html: str) -> Tuple[BuildOption, ...]:
    """空地建造頁上每一棟建築一筆（頁面順序）。不是建築頁（沒有 `#build`）丟 ParseError；
    是建築頁但沒有任何建築（該分頁全蓋過了）回空 tuple。"""
    soup = _soup(html)
    if soup.select_one("#build") is None:
        raise ParseError(_PAGE, "no #build container")
    out = []
    for w in soup.select('div.buildingWrapper[id^="contract_building"]'):
        m = re.fullmatch(r"contract_building(\d+)", w.get("id", ""))
        if not m:
            continue
        scope = w.select_one("div.upgradeBuilding") or w
        name = _text(w.select_one("div.build_desc h2"))
        name = re.sub(r"^\d+\s*[.．]\s*", "", name) or None      # 「12. 山洞」的序號前綴只是顯示（✗ 只見於 S10 一處）
        url = _green_url(scope)
        short, disabled, afford = _blocked(scope)
        out.append(BuildOption(
            gid=int(m.group(1)), name=name, cost=_cost(scope), build_time_s=_build_time(scope),
            buildable=url is not None, url=url, resource_short=short, exchange_disabled=disabled,
            afford_in_s=afford, conditions=_conditions(scope)))
    return tuple(out)


def find_upgrade_url(html: str) -> Optional[str]:
    """單一建築頁上綠色興建／升級按鈕的網址（通過白名單才回）；新版頁面沒有網址，回 'click:build:<aid>:<gid>'（v0.1.1）；沒有（佇列滿、資源不足、已滿級）＝None。
    頁面有多個 `upgradeBuilding`（空地建造頁 gid0）丟 ParseError：該頁要用 parse_build_options，
    不能拿第一個按鈕當「這棟建築的網址」。紫色加速、金幣、disabled 的按鈕一律不碰。"""
    soup = _soup(html)
    blocks = soup.select("div.upgradeBuilding")
    if len(blocks) > 1:
        raise ParseError(_PAGE, "multiple upgradeBuilding blocks (gid0 page?)")
    return _green_url(blocks[0], soup) if blocks else None
