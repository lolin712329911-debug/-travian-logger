#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/actions/build_exec.py（ac-02）
版本：v0.1.2（GA-fix7：空地新蓋——依分頁抓建造頁、點按鈕的選擇器限定在該建築區塊）｜v0.1.1（GA-fix3：新版升級按鈕沒有網址，改點綠色按鈕；送出前的 dorf1 基準改在讀建築頁之前）｜v0.1（A5a）
用途：送出一次建築升級／興建並驗證：submit_upgrade(gw, did, target, mode) → ExecResult。
依賴：if-02（Gateway）、ps-01（parse_dorf1）、ps-03（建築頁解析）、cm-02（BuildTarget、ExecResult）、cm-04（Mode）、cm-11（ParseError，v0.1 補）。
部署狀態：未部署（GA 前不 live）。

流程（舊 runner.py run_build_cycle 的送出段，✓ 已讀；差異見下）
  off  → skipped，不發任何請求。
  其餘 → 讀 build.php?id=<aid> → 取升級網址與頁面成本 → 核對（網址、成本）→
  dry  → 回 dry（不送出）。
  live → 先讀 dorf1 當基準（v0.1.1：必須在讀建築頁「之前」，因為點擊要在建築頁上）→ 讀建築頁 → 核對 →
         送出（舊式網址 gw.submit；新版按鈕 gw.click，不重試）→ 重讀 dorf1：佇列變長，或庫存合計
         減少超過成本合計的一半 → ok（verified=True）；否則 failed（verified=False，不重試）。

安全規則（v0.68，§11.7-B）：
  只認升級／興建連結（`/dorf[12].php?id=<aid>&gid=<gid>&action=build&checksum=…`，id 與 gid 必須等於 target）；
  不得點「立即完成」、高級建築師、NPC 商人（耗金幣）。網址白名單在兩處：parsers（取網址時）與本檔（送出前再核對一次，
  只認完整相符，多任何參數如 &buildmaster、&as= 一律不送）。
  ExecResult.detail 不放網址（含 checksum），只放建築名稱與等級。

與舊碼的差異
  1. 舊碼的網址來自決策物件（Field.url，空地建造用）；BuildTarget 沒有網址，改在送出前讀建築頁取得：
     有建造清單的頁（空地，gid0）→ parse_build_options 取 gid 相符的那一筆的網址與成本；
     否則（既有建築）→ find_upgrade_url＋parse_building_cost。
  2. 新增「送出前核對成本」（頁面成本必須等於 target.cost）、核對網址的 id／gid。
  3. 舊碼用決策時的 st 當基準；本函式簽名沒有 st，送出前自己讀一次 dorf1（多 1 個請求）。
  4. 舊碼的隨機等待（2～6 秒等）不在這裡：等待由 GatewayLimits（B3 時間預算）負責。
  5. 舊碼「沒看到變化」時 return 1 讓整輪停止；本函式回 failed，是否停止由 stage 決定。
  6. 頁面一律用 Gateway.get 預設（瀏覽器渲染），與舊碼 get_html 一致。
"""
import re
from typing import Optional, Tuple

from ..common.decisions import BuildTarget, ExecResult
from ..common.modes import Mode
from ..common.schema import ParseError
from ..infra.gateway import Gateway, GatewayError
from ..parsers.buildings import find_upgrade_url, parse_build_options, parse_building_cost
from ..parsers.village import parse_dorf1

__all__ = ["submit_upgrade"]

# 只認這一種（與 parsers/buildings 同格式，但這裡要抓 id、gid 來核對；完整相符才算）
_UPGRADE_URL_RE = re.compile(r"/dorf[12]\.php\?id=(\d+)&gid=(\d+)&action=build&checksum=[0-9a-fA-F]+")
# v0.1.1：新版升級按鈕沒有網址（parsers 回 click:build:<aid>:<gid>），送出方式是點「正常工期」區的綠色按鈕。
# 紫色加速（.purple）、disabled、金幣大師建築師一律不碰；aid、gid 在送出前核對（來自頁面 script 的 POST 內容）。
_CLICK_TOKEN_RE = re.compile(r"click:build:(\d+):(\d+)")
_CLICK_SELECTOR = "div.upgradeBuilding div.upgradeButtonsContainer div.section1 button.green.build:not(.disabled)"
# v0.1.2（GA-fix7）：空地建造頁（gid0）一頁有多個 div.upgradeBuilding，按鈕 class 是 `green new`（不是 `green build`），
# 所以選擇器要限定在 #contract_building<gid> 內。aid、gid 仍由 _url_ok 核對過才會走到這裡。
_CLICK_SELECTOR_SLOT = "#contract_building{gid} div.upgradeButtonsContainer div.section1 button.green:not(.disabled)"
# 空地頁有三個分頁（1 基礎、2 軍事、3 資源）；一頁只列該分頁的建築。下表取自三張空地頁樣本（✓ 11-24，埃及人）；
# 沒列到的 gid 先用預設頁，找不到再逐頁試。純提示用，不影響安全核對。
_CATEGORY_HINT = {
    17: 1, 18: 1, 23: 1, 24: 1, 25: 1, 26: 1, 27: 1, 28: 1, 38: 1, 39: 1, 45: 1,
    13: 2, 14: 2, 20: 2, 21: 2, 22: 2, 46: 2,
    5: 3, 6: 3, 7: 3, 8: 3, 9: 3,
}
_CATEGORY_PATH = "build.php?id={aid}&category={cat}"     # ✗ 與 observe.fetch_build_options 用的網址是否一致待核對
_NOT_LISTED = "空地頁沒有 gid"
_DORF1 = "dorf1.php"


def _mode_value(mode) -> str:
    """off／dry／live；看不懂一律 off（§6.1 寫入類 mode）。"""
    v = str(getattr(mode, "value", mode)).strip().lower()
    return v if v in ("off", "dry", "live") else "off"


def _label(t: BuildTarget) -> str:
    return f"{t.name} L{t.to_level}（aid {t.aid}）"


def _url_ok(url: str, t: BuildTarget) -> bool:
    m = _UPGRADE_URL_RE.fullmatch(url or "") or _CLICK_TOKEN_RE.fullmatch(url or "")
    return bool(m) and int(m.group(1)) == t.aid and int(m.group(2)) == t.gid


def _page_facts(html: str, t: BuildTarget) -> Tuple[Optional[str], Optional[Tuple[int, ...]], str, bool]:
    """(網址, 頁面成本, 備註, 是否空地頁)。網址 None＝沒有可按的綠色按鈕。解析失敗丟 ParseError。
    有建造清單（`contract_building<gid>`）＝空地頁：只取 gid 相符的一筆（頁面可能只剩一個選項，
    所以不能靠「有多個 upgradeBuilding」判斷）；否則是既有建築頁。
    空地頁上沒有這個 gid 時，備註以 _NOT_LISTED 開頭（呼叫端可改抓別的分頁再試）。"""
    try:
        options = parse_build_options(html)
    except ParseError:
        options = ()                     # 沒有 #build：不是空地頁
    if options:
        for o in options:
            if o.gid == t.gid:
                return (o.url if o.buildable else None), (tuple(o.cost) if o.cost else None), "", True
        return None, None, f"{_NOT_LISTED} {t.gid} 的建造選項", True
    url = find_upgrade_url(html)
    if url is None:
        return None, None, "", False
    return url, tuple(parse_building_cost(html).cost), "", False


def _category_order(gid: int) -> Tuple[int, ...]:
    """先試提示的分頁，再試其餘（1、2、3）。"""
    first = _CATEGORY_HINT.get(gid)
    rest = tuple(c for c in (1, 2, 3) if c != first)
    return ((first,) + rest) if first else rest


def submit_upgrade(gw: Gateway, did: int, target: BuildTarget, mode: Mode) -> ExecResult:
    m = _mode_value(mode)
    if m == "off":
        return ExecResult("skipped", "mode=off，不動作", 0, None)

    n0 = gw.request_count()
    what = _label(target)

    def res(result: str, detail: str, verified: Optional[bool] = None) -> ExecResult:
        return ExecResult(result, detail, gw.request_count() - n0, verified)

    # 0) live：先讀 dorf1 當基準（之後要停在建築頁上點按鈕，所以不能放在讀建築頁之後）
    before = None
    if m == "live":
        try:
            before = parse_dorf1(gw.get(_DORF1, did=did))
        except (GatewayError, ParseError) as e:
            return res("failed", f"{what}：送出前讀 dorf1 失敗，未送出：{e}")

    # 1) 讀建築頁、取網址與成本（唯讀）
    try:
        path = f"build.php?id={target.aid}"
        hint = _CATEGORY_HINT.get(target.gid)
        if target.to_level == 1 and hint:        # 新蓋：直接抓該建築所在的分頁，少一次請求
            path = _CATEGORY_PATH.format(aid=target.aid, cat=hint)
        html = gw.get(path, did=did)
        url, page_cost, note, empty = _page_facts(html, target)
        if empty and note.startswith(_NOT_LISTED):          # 這一頁沒列 → 其餘分頁逐頁試（最後一次抓的頁就是要點的頁）
            for cat in _category_order(target.gid):
                p = _CATEGORY_PATH.format(aid=target.aid, cat=cat)
                if p == path:
                    continue
                path = p
                html = gw.get(path, did=did)
                url, page_cost, note, empty = _page_facts(html, target)
                if not (empty and note.startswith(_NOT_LISTED)):
                    break
    except (GatewayError, ParseError) as e:
        return res("failed", f"{what}：讀建築頁失敗，未送出：{e}")
    if url is None:
        return res("skipped", f"{what}：找不到綠色按鈕（資源不足、佇列滿或前置條件未達）" + (f"；{note}" if note else ""))

    # 2) 送出前核對
    if not _url_ok(url, target):
        return res("failed", f"{what}：按鈕網址不是這棟建築的升級連結，未送出")
    if page_cost is None:
        return res("failed", f"{what}：讀不到頁面成本，無法核對，未送出")
    if page_cost != tuple(target.cost):
        return res("skipped", f"{what}：頁面成本 {list(page_cost)} 與決策時 {list(target.cost)} 不同，未送出")

    if m == "dry":
        return res("dry", f"{what}：會送出（乾跑，沒有真的送出）")

    # 3) live：送出（不重試）→ 重讀驗證
    try:
        if _CLICK_TOKEN_RE.fullmatch(url):
            gw.click(_CLICK_SELECTOR_SLOT.format(gid=target.gid) if empty else _CLICK_SELECTOR)   # 目前頁面就是剛讀的頁
        else:
            gw.submit(url)
    except GatewayError as e:
        return res("failed", f"{what}：送出時出錯（可能已送達，不重送）：{e}")
    try:
        after = parse_dorf1(gw.get(_DORF1, did=did))
    except (GatewayError, ParseError) as e:
        return res("failed", f"{what}：已送出，但重讀 dorf1 失敗，無法驗證（不重送）：{e}")

    spent = sum(before.stock) - sum(after.stock)
    queue_up = len(after.queue) > len(before.queue)
    if queue_up or spent > 0.5 * sum(target.cost):
        return res("ok", f"{what}：已送出並驗證（佇列 {len(before.queue)}→{len(after.queue)}，庫存合計減少 {spent}）", True)
    return res("failed", f"{what}：送出後沒看到資源被扣或佇列增加（不重試）", False)
