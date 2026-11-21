#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/parsers/rally.py（ps-06）
版本：v0.1（A2b）
用途：集結點（gid 16）的解析：概況頁（移動表與本村在家兵力）與送兵第二步的確認頁。純函式：HTML 進、資料出，
      不碰網路、不碰 Sheet。
依賴：cm-09（parsed）、cm-03（constants，BIDI）、cm-11（schema，ParseError）。
部署狀態：未部署（GA 前不 live）。

公開介面
  parse_overview(html)      → RallyOverview（server_ts、movements、units_home、units_away＝None、incoming_attacks）
                              找不到 `Travian.Game.timestamp` 或沒有 `div.rallyPointOverviewContainer`（不是概況頁；確認頁也有
                              table.troop_details，所以不能只看表格）→ ParseError
  parse_troops_home(html)   → dict | None（本村在家部隊表；鍵 u1～u10／hero、零省略；有表即 dict、全 0＝{}；沒有該表＝None）
  parse_send_confirm(html)  → SendConfirm（確認頁；找不到關鍵欄位 → ParseError）
D1 擴充 parse_troops_away（本 WP 不做，units_away 固定 None）。

來源：舊 hide_troops.py（✓ 已讀）的 parse_overview、home_units、parse_confirm、Movement；§5.1 判定五條皆成立 → 套用（沿用＋修改）。
有意的修改（golden 以新行為為準）：
  1. 兵種鍵由 t1～t11 改 u1～u10＋hero（D-21②）；表的鍵一律依欄位順序（第 1～10 欄＝u1～u10、第 11 欄＝hero），
     不看圖示 class（圖示 class 隨種族不同，例 u21～u30、u51～u60；俘虜表是別的種族）。確認頁的 `troops[0][tN]` 依名稱對應。
  2. Movement → cm-09 RallyMovement；recall_url → recall_id（取自 `div.abort` 按鈕的 onclick，網址由 actions 組）；
     只輸出有種類 class 的表（本村在家、別村駐守本村、我方駐守他村、俘虜都不輸出）；到達時間欄位改名 arrive_ts。
  3. 舊版跨 parser 引用 oasis_check._text → 本檔自己的文字清理（cm-03 BIDI）；ValueError／None → ParseError。
  4. home_units 含 hero（舊版排除）；零省略；有表即 dict、沒有表＝None（舊版沒有表也回 {}）。
  5. parse_confirm 回 None → parse_send_confirm 丟 ParseError；補 checksum（hidden 是空的，值在確認鈕 onclick）、
     villagename、scout／catapult 目標、village_did（`troops[0][villageId]`，與 action 第二段交叉核對）。
  6. 類型只看 hidden `eventType`，不取標題文字判斷（標題只存 kind_text 供記錄）；舊版 confirm_matches 的「掠奪」字樣核對不搬。
  7. 敵方兵力欄顯示「?」→ 該鍵值 None（舊版 counts 的 None）；未知的其他文字 → ParseError。
**不搬**：decide、return_windows、confirm_matches、confirm_ok、attack_total（決策，歸 domain）；incoming_symbols（側欄各村來襲，
歸 ps-02 擴充）。

註：movements 不含無種類 class 的表，所以 RallyMovement.own_home 在 A2b 輸出中恆為 False（欄位依卡片保留）。
ParseError 的訊息只放頁面名稱與原因，不放頁面內容。確認頁的 checksum 是 token，呼叫端進 log／Sheet 前要 redact。
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from ..common.constants import BIDI
from ..common.parsed import RallyMovement, RallyOverview, SendConfirm
from ..common.schema import ParseError

__all__ = ["parse_overview", "parse_troops_home", "parse_send_confirm"]

_PAGE = "rally"
_TS_RE = re.compile(r"Travian\.Game\.timestamp\s*=\s*(\d+)")
_D_RE = re.compile(r"[?&]d=(\d+)")
_RECALL_RE = re.compile(r"recall=(\d+)")
_ACTION_RE = re.compile(r"^troopsSend/(\d+)/(\d+)$")
_CHECKSUM_RE = re.compile(r"name=checksum\]'\)\.value\s*=\s*'([^']+)'")
_UNIT_KEYS = tuple(f"u{i}" for i in range(1, 11)) + ("hero",)     # 第 1～10 欄、第 11 欄
_HOSTILE = frozenset({"inRaid", "inAttack"})


# ---------------------------------------------------------------- 共用小工具
def _need_str(html: Any) -> str:
    if not isinstance(html, str) or not html.strip():
        raise ParseError(_PAGE, "輸入不是字串或是空的")
    return html


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _text(el: Any) -> str:
    """元素文字：去 BIDI 控制字元、空白收成單一空格。"""
    if el is None:
        return ""
    return re.sub(r"\s+", " ", BIDI.sub("", el.get_text(" "))).strip()


def _d_of(el: Any) -> Optional[int]:
    if el is None:
        return None
    m = _D_RE.search(el.get("href", ""))
    return int(m.group(1)) if m else None


def _is_home_table(table: Any) -> bool:
    did = table.get("data-did")
    return bool(did) and did == table.get("data-ort")


def _units_of(table: Any) -> Dict[str, Optional[int]]:
    """一張 troop_details 表的兵力：`tbody.units.last` 那列的 11 個 td.unit，依欄位順序對應 u1～u10／hero。
    零省略；「?」＝None；其他文字 → ParseError。"""
    row = table.select_one("tbody.units.last tr")
    cells = row.select("td.unit") if row is not None else []
    if len(cells) != len(_UNIT_KEYS):
        raise ParseError(_PAGE, "兵力列不是 11 欄")
    out: Dict[str, Optional[int]] = {}
    for key, td in zip(_UNIT_KEYS, cells):
        t = _text(td)
        if t == "?":
            out[key] = None
        elif t.isdigit():
            if int(t) > 0:
                out[key] = int(t)
        else:
            raise ParseError(_PAGE, "兵力欄不是數字也不是「?」")
    return out


def _table_sections(soup: BeautifulSoup) -> List[Tuple[str, Any]]:
    """依頁面順序回傳 (所屬 h4.spacer 文字, table.troop_details)。"""
    out, section = [], ""
    for el in soup.select("h4.spacer, table.troop_details"):
        if el.name == "h4":
            section = _text(el)
        else:
            out.append((section, el))
    return out


def _home_units(tables: List[Tuple[str, Any]]) -> Optional[Dict[str, int]]:
    for _sec, table in tables:
        if _is_home_table(table):
            units = _units_of(table)
            return {k: v for k, v in units.items() if v is not None}
    return None


# ---------------------------------------------------------------- 概況頁
def parse_overview(html: str) -> RallyOverview:
    html = _need_str(html)
    m = _TS_RE.search(html)
    if not m:
        raise ParseError(_PAGE, "找不到 Travian.Game.timestamp")
    server_ts = int(m.group(1))
    soup = _soup(html)
    if soup.select_one("div.rallyPointOverviewContainer") is None:
        # 確認頁也有 table.troop_details，不能只靠表格判斷；概況頁（6 份樣本）都有這個容器，確認頁與表單頁都沒有
        raise ParseError(_PAGE, "不是集結點概況頁")
    tables = _table_sections(soup)

    moves = []
    for section, table in tables:
        kinds = tuple(c for c in table.get("class", []) if c != "troop_details")
        if not kinds:
            continue
        timer = table.select_one("tbody.infos span.timer[value]")
        value = timer.get("value", "") if timer is not None else ""
        abort = table.select_one("div.abort button[onclick*='recall=']")
        rm = _RECALL_RE.search(abort.get("onclick", "")) if abort is not None else None
        head = table.select_one("td.troopHeadline")
        role_did = _d_of(table.select_one("td.role a[href*='d=']"))
        head_did = _d_of(head.select_one("a[href*='d=']") if head is not None else None)
        moves.append(RallyMovement(
            kinds=kinds,
            hostile=any(k in _HOSTILE for k in kinds),
            own_home=_is_home_table(table),
            arrive_ts=server_ts + int(value) if value.isdigit() else None,
            units=_units_of(table),
            role_did=role_did,
            head_did=head_did,
            link_did=head_did if any(k.startswith("out") for k in kinds) else role_did,
            recall_id=int(rm.group(1)) if rm else None,
            section=section,
            headline=_text(head),
        ))
    return RallyOverview(
        server_ts=server_ts,
        movements=tuple(moves),
        units_home=_home_units(tables),
        units_away=None,
        incoming_attacks=sum(1 for mv in moves if mv.hostile),
    )


def parse_troops_home(html: str) -> Optional[Dict[str, int]]:
    """本村在家部隊表（data-did＝data-ort）。沒有該表＝None（不是 {}）；有表但全 0＝{}。不需要時間戳。"""
    html = _need_str(html)
    return _home_units(_table_sections(_soup(html)))


# ---------------------------------------------------------------- 確認頁
def _hidden(form: Any, name: str) -> Optional[str]:
    el = form.select_one(f'input[name="{name}"]')
    v = el.get("value") if el is not None else None
    return v if isinstance(v, str) else None


def _req_int(form: Any, name: str) -> int:
    v = _hidden(form, name)
    # 座標可為負號；頁面負號在 hidden 欄位裡是 ASCII '-'
    if v is None or not re.fullmatch(r"-?\d+", v.strip()):
        raise ParseError(_PAGE, f"確認頁的 {name} 缺漏或不是整數")
    return int(v)


def _opt_str(form: Any, name: str) -> Optional[str]:
    v = _hidden(form, name)
    return v if v else None


def parse_send_confirm(html: str) -> SendConfirm:
    html = _need_str(html)
    soup = _soup(html)
    form = soup.select_one("form#troopSendForm")
    if form is None:
        raise ParseError(_PAGE, "不是送兵確認頁（沒有 troopSendForm）")
    m = _ACTION_RE.match((_hidden(form, "action") or "").strip())
    if not m:
        raise ParseError(_PAGE, "確認頁的 action 不是 troopsSend/<did>/<ts>")
    action_did, page_ts = int(m.group(1)), int(m.group(2))

    at = soup.select_one("span#at[value]")
    at_v = at.get("value", "") if at is not None else ""
    if not at_v.isdigit():
        raise ParseError(_PAGE, "確認頁沒有 span#at 的預計到達時間")
    epoch = int(at_v)
    if epoch < page_ts:
        raise ParseError(_PAGE, "預計到達時間早於頁面時間（單程秒數為負）")

    button = soup.select_one("button#confirmSendTroops")
    cm = _CHECKSUM_RE.search(button.get("onclick", "")) if button is not None else None
    if not cm:
        raise ParseError(_PAGE, "確認頁沒有確認鈕或讀不到 checksum")

    vid = _hidden(form, "troops[0][villageId]")
    if vid is None:
        village_did = action_did
    elif vid.isdigit() and int(vid) == action_did:
        village_did = int(vid)
    else:
        raise ParseError(_PAGE, "villageId 與 action 的村莊編號不一致")

    units: Dict[str, int] = {}
    for i, key in enumerate(_UNIT_KEYS, start=1):
        units[key] = _req_int(form, f"troops[0][t{i}]")

    return SendConfirm(
        epoch=epoch,
        trip_s=epoch - page_ts,
        village_did=village_did,
        event_type=_req_int(form, "eventType"),
        x=_req_int(form, "x"),
        y=_req_int(form, "y"),
        villagename=_opt_str(form, "villagename"),
        checksum=cm.group(1),
        scout_target=_opt_str(form, "troops[0][scoutTarget]"),
        catapult_target1=_opt_str(form, "troops[0][catapultTarget1]"),
        catapult_target2=_opt_str(form, "troops[0][catapultTarget2]"),
        units=units,
        kind_text=_text(soup.select_one("td.troopHeadline")),
        has_confirm=True,
    )
