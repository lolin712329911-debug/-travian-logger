#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/actions/item_transfer_exec.py（ac-03）
版本：v0.1（A5a）
用途：英雄道具庫 → 村莊的資源轉移：execute_item_transfer(gw, decision, mode) → ExecResult。不可逆；失敗不重送。
依賴：if-02（Gateway，含 v0.2 的 Response.headers、base_url）、ps-05（parse_transfer_state）、cm-02、cm-04、cm-09（TransferState）、cm-11（ParseError）（後兩者為 v0.1 補）。
部署狀態：未部署（GA 前不 live）。

來源 transfer_io.py v1.2（✓ 已讀）＋ travian_transfer.py v1.2 的 execute_transfer（✓ 已讀）。拆法：決策 decide_transfer 歸 domain（A3c／A6a2）；
解析歸 ps-05；本層只管送出、驗證。

API（✓ 使用者 10-15 手動轉移對照）：
  POST /api/v1/graphql                         讀村莊現量與道具庫（body {"query": STATE_QUERY}，外層格式 △ 推定）
  PUT  /api/v1/hero/v2/inventory/use-item      每個缺的資源一筆（預期 204）；回應標頭給 x-nonce
  POST /api/v1/hero/v2/inventory/use-item      每個資源一筆（預期 200）；請求標頭帶該 itemId 那次 PUT 的 x-nonce
  PUT 與 POST 的 Payload 相同：{"action":"inventory","itemId":…,"amount":…,"villageId":…}；庫存只扣一次
  前端順序：先把所有資源 PUT，再把所有資源 POST。
  △ 未實測：只送其中一種是否有效；nonce 是否一次性／有效多久；POST 回應是否也給新 nonce（忽略）。
流程：off／不動作→skipped；決策不合法→failed（不送）；dry→dry（不發請求）；
  live→讀基準（失敗不阻擋）→ PUT 全部 → POST 全部（任一筆失敗就停；不重試、不送後面階段）→ 重讀：
  每筆 line 的資源，村莊現量 ≥ targets 才算 ok（verified=True）；否則 failed（verified=False，不重試）。
  PUT 沒給 x-nonce→當作失敗、不送 POST；POST 前找不到 nonce→不送。nonce 只用一次，不進 detail。
差異：舊碼的 State／Plan／Result 改為 TransferState／ItemTransferDecision／ExecResult；舊碼 send／read_state 注入改直接用 Gateway；
  body 用字串組出（只含整數與固定查詢），不經序列化函式（格式出口規則：JSON 輸出只在 serialize）。
"""
from typing import Dict, Optional

from ..common.decisions import ExecResult, ItemTransferDecision
from ..common.modes import Mode
from ..common.parsed import TransferState
from ..common.schema import ParseError
from ..infra.gateway import Gateway, GatewayError
from ..parsers.hero import parse_transfer_state

__all__ = ["execute_item_transfer", "read_transfer_state"]

USE_ITEM_PATH = "/api/v1/hero/v2/inventory/use-item"
GRAPHQL_PATH = "/api/v1/graphql"
PHASES = ("PUT", "POST")    # ✓ 前端實際順序
RES_NAMES = ("lumber", "clay", "iron", "crop")

# ✓ 使用者提供的實際 query（原樣；travian_transfer.STATE_QUERY）
STATE_QUERY = (
    "{lumber:item(typeId:145 rarity:none){...itemFields}clay:item(typeId:146 rarity:none){...itemFields}i"
    "ron:item(typeId:147 rarity:none){...itemFields}crop:item(typeId:148 rarity:none){...itemFields}ownPl"
    "ayer{hero{inventory{...heroInventoryItemFields}}village{id name resources{lumberStock clayStock iron"
    "Stock cropStock maxStorageCapacity maxCropStorageCapacity}}}}fragment itemFields on Item{typeId name"
    " isConsumable isUsableIfDead attributes{description descriptionDetails}slot quality rarity possibleA"
    "mountsToSell}fragment heroInventoryItemFields on HeroInventoryItem{id amount placeId name typeId isC"
    "onsumable isUsableIfDead attributes{description descriptionDetails}slot quality rarity possibleAmoun"
    "tsToSell}"
)
assert not any(c in STATE_QUERY for c in '"\\\n'), "STATE_QUERY 含需要跳脫的字元，不能直接組成 JSON 字串"
_GRAPHQL_BODY = '{"query":"' + STATE_QUERY + '"}'


def _mode_value(mode) -> str:
    v = str(getattr(mode, "value", mode)).strip().lower()
    return v if v in ("off", "dry", "live") else "off"


def _headers(gw: Gateway) -> dict:
    base = gw.base_url
    return {"content-type": "application/json; charset=UTF-8", "accept": "*/*", "origin": base,
            "referer": base + "/dorf1.php"}


def _is_pos_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def _check(d: ItemTransferDecision) -> Optional[str]:
    """不合法的原因；合法回 None。"""
    if not d.lines:
        return "lines 是空的"
    if not _is_pos_int(d.village_id):
        return "village_id 不合法"
    t = d.targets
    if not (isinstance(t, tuple) and len(t) == 4 and all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in t)):
        return "targets 需為 4 個整數（木磚鐵穀）"
    seen_r, seen_i = set(), set()
    for ln in d.lines:
        if ln.resource not in range(4) or isinstance(ln.resource, bool):
            return f"resource {ln.resource!r} 不在 0..3"
        if not (_is_pos_int(ln.item_id) and _is_pos_int(ln.amount)):
            return "item_id／amount 需為正整數"
        if ln.resource in seen_r or ln.item_id in seen_i:
            return "resource 或 item_id 重複"
        seen_r.add(ln.resource)
        seen_i.add(ln.item_id)
    return None


def read_transfer_state(gw: Gateway) -> TransferState:
    """唯讀：graphql。HTTP 不成功丟 GatewayError，格式不符丟 ParseError。"""
    r = gw.request("POST", GRAPHQL_PATH, headers=_headers(gw), data=_GRAPHQL_BODY)
    if not r.ok:
        raise GatewayError(f"graphql HTTP {r.status}")
    return parse_transfer_state(r.text)


def _body(village_id: int, item_id: int, amount: int) -> str:
    return '{"action":"inventory","itemId":%d,"amount":%d,"villageId":%d}' % (item_id, amount, village_id)


def _diag(d: ItemTransferDecision, before: Optional[TransferState], now: Optional[TransferState]) -> str:
    """前後對照：村莊現量與道具庫庫存（沒有基準或讀不到就說明）。"""
    if now is None:
        return "｜（送出後重讀失敗，無法對照）"
    parts = []
    for ln in d.lines:
        r = ln.resource
        inv_b = before.inventory[r].amount if before is not None and before.inventory[r] else None
        inv_n = now.inventory[r].amount if now.inventory[r] else None
        vil = f"{before.stock[r]}→{now.stock[r]}" if before is not None else f"?→{now.stock[r]}"
        parts.append(f"{RES_NAMES[r]}: 村莊 {vil}（目標 {d.targets[r]}）｜庫存 {inv_b if inv_b is not None else '?'}→"
                     f"{inv_n if inv_n is not None else '?'}（預計轉 {ln.amount}）")
    return "｜前後對照 " + "；".join(parts)


def execute_item_transfer(gw: Gateway, decision: ItemTransferDecision, mode: Mode) -> ExecResult:
    m = _mode_value(mode)
    if m == "off":
        return ExecResult("skipped", "mode=off，不動作", 0, None)
    if not decision.act:
        return ExecResult("skipped", f"決策不動作：{decision.reason}", 0, None)
    bad = _check(decision)
    if bad:
        return ExecResult("failed", f"轉移決策不合法（{bad}），未送出", 0, None)
    summary = "、".join(f"{RES_NAMES[ln.resource]} {ln.amount}" for ln in decision.lines)
    if m == "dry":
        return ExecResult("dry", f"會轉移 {summary} 到村 {decision.village_id}（乾跑，沒有真的送 use-item）", 0, None)

    n0 = gw.request_count()

    def res(result: str, detail: str, verified: Optional[bool] = None) -> ExecResult:
        return ExecResult(result, detail, gw.request_count() - n0, verified)

    try:
        before: Optional[TransferState] = read_transfer_state(gw)
    except (GatewayError, ParseError):
        before = None                      # 讀不到基準不阻擋轉移，只是少了前後對照

    def after_diag() -> str:
        try:
            return _diag(decision, before, read_transfer_state(gw))
        except (GatewayError, ParseError):
            return _diag(decision, before, None)

    headers = _headers(gw)
    nonces: Dict[int, str] = {}
    for method in PHASES:
        for ln in decision.lines:
            hdrs = dict(headers)
            if method == "POST":
                nonce = nonces.pop(ln.item_id, None)          # 只用一次
                if not nonce:
                    return res("failed", f"POST 前沒有 itemId={ln.item_id} 的 x-nonce，不送出（不重試）" + after_diag())
                hdrs["x-nonce"] = nonce
            try:
                r = gw.request(method, USE_ITEM_PATH, headers=hdrs, data=_body(decision.village_id, ln.item_id, ln.amount))
            except GatewayError as e:
                return res("failed", f"{method} {RES_NAMES[ln.resource]} 送出時出錯：{e}（不重試、不送後面的階段）" + after_diag())
            if not r.ok:
                return res("failed", f"{method} {RES_NAMES[ln.resource]} HTTP {r.status} 回應={r.text[:200]!r}"
                                     f"（不重試、不送後面的階段）" + after_diag())
            if method == "PUT":
                n = r.headers.get("x-nonce")
                if not n:
                    return res("failed", f"PUT {RES_NAMES[ln.resource]} HTTP {r.status} 但回應標頭沒有 x-nonce，不送 POST"
                                         f"（不重試）" + after_diag())
                nonces[ln.item_id] = n

    try:
        now = read_transfer_state(gw)
    except (GatewayError, ParseError) as e:
        return res("failed", f"已送出 PUT／POST，但重讀狀態失敗，無法驗證（不重試）：{e}", None)
    short = {RES_NAMES[ln.resource]: (now.stock[ln.resource], decision.targets[ln.resource])
             for ln in decision.lines if now.stock[ln.resource] < decision.targets[ln.resource]}
    if short:
        return res("failed", f"轉移後村莊仍不足 {short}（可能方法錯誤；不重試）" + _diag(decision, before, now), False)
    return res("ok", f"已轉移 {summary} 並驗證" + _diag(decision, before, now), True)
