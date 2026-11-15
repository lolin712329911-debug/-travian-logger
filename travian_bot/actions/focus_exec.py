#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/actions/focus_exec.py（ac-04）
版本：v0.1（A5a）
用途：英雄資源產量加成的讀取與切換：read_focus(gw) → HeroFocus；set_focus(gw, decision, mode) → ExecResult。
依賴：if-02（Gateway，含 v0.2 的 base_url）、ps-05（parse_hero_attributes、parse_focus_set）、cm-02、cm-04、cm-09（HeroFocus）、cm-11（ParseError）（後兩者為 v0.1 補）。
部署狀態：未部署（GA 前不 live）。

來源 hero_focus.py v0.3.1（△→✓ 已讀）的 make_focus_io（拆：決策 decide_focus 歸 domain A3b，解析歸 ps-05）。
API（✓ 使用者實測）：
  讀：GET  /api/v1/hero/v2/screen/attributes → hero.productionType／productionTypes
  改：POST /api/v1/hero/v2/attributes，body {"resource":N}，回 {"productionType":N,…}
  沒有 x-nonce、沒有 PUT 預備步驟；冒險中也能改；改完產量立刻變。
set_focus 流程：off／不動作→skipped；值域不合→failed（不送）；dry→dry（不送、不發請求）；
  live→POST（不重試）→ 核對回應 productionType＝送出值 → 重讀屬性頁，current＝送出值才算 verified。
  「產量是否如預期」要看 dorf1 與決策時的缺口，屬 stage（A6a2），本層不做。
差異：舊碼只回字串、失敗丟例外；本層回 ExecResult，失敗不丟例外（read_focus 例外照舊往外丟）。
  請求標頭 content-type／accept／origin／referer 與舊碼相同（origin＝gw.base_url）。
  body 用字串組出（只含整數），不經序列化函式（格式出口規則：JSON 輸出只在 serialize）。
"""
from typing import Optional

from ..common.decisions import FOCUS_NAMES, ExecResult, FocusDecision
from ..common.modes import Mode
from ..common.parsed import HeroFocus
from ..common.schema import ParseError
from ..infra.gateway import Gateway, GatewayError
from ..parsers.hero import parse_focus_set, parse_hero_attributes

__all__ = ["read_focus", "set_focus"]

ATTR_PATH = "/api/v1/hero/v2/attributes"
SCREEN_PATH = "/api/v1/hero/v2/screen/attributes"


def _mode_value(mode) -> str:
    v = str(getattr(mode, "value", mode)).strip().lower()
    return v if v in ("off", "dry", "live") else "off"


def _headers(gw: Gateway) -> dict:
    base = gw.base_url
    return {"content-type": "application/json; charset=UTF-8", "accept": "*/*", "origin": base,
            "referer": base + "/hero/attributes"}


def read_focus(gw: Gateway) -> HeroFocus:
    """唯讀。HTTP 不成功丟 GatewayError，格式不符丟 ParseError。"""
    r = gw.request("GET", SCREEN_PATH, headers=_headers(gw))
    if not r.ok:
        raise GatewayError(f"GET screen/attributes HTTP {r.status}")
    return parse_hero_attributes(r.text)


def set_focus(gw: Gateway, decision: FocusDecision, mode: Mode) -> ExecResult:
    m = _mode_value(mode)
    if m == "off":
        return ExecResult("skipped", "mode=off，不動作", 0, None)
    if not decision.act:
        return ExecResult("skipped", f"決策不動作：{decision.reason}", 0, None)
    if decision.focus not in FOCUS_NAMES:
        return ExecResult("failed", f"加成值不合法（{decision.focus!r}），未送出", 0, None)
    code = FOCUS_NAMES.index(decision.focus)
    name = decision.focus
    if m == "dry":
        return ExecResult("dry", f"會改成 {name}（resource={code}）（乾跑，沒有真的送出）", 0, None)

    n0 = gw.request_count()

    def res(result: str, detail: str, verified: Optional[bool] = None) -> ExecResult:
        return ExecResult(result, detail, gw.request_count() - n0, verified)

    try:
        r = gw.request("POST", ATTR_PATH, headers=_headers(gw), data='{"resource":%d}' % code)
    except GatewayError as e:
        return res("failed", f"改成 {name}：送出時出錯（可能已送達，不重送）：{e}")
    if not r.ok:
        return res("failed", f"改成 {name}：POST attributes HTTP {r.status}（不重試）；回應={r.text[:200]!r}")
    try:
        got = parse_focus_set(r.text)
    except ParseError as e:
        return res("failed", f"改成 {name}：POST {r.status} 但回應讀不懂（{e}）（不重試）")
    if got != code:
        return res("failed", f"改成 {name}：POST {r.status} 但回應 productionType={got} ≠ 送出 {code}（不重試）", False)
    try:
        cur = read_focus(gw).current
    except (GatewayError, ParseError) as e:
        return res("ok", f"已改成 {name}（POST 回應已核對）；送出後重讀屬性頁失敗，未驗證：{e}", None)
    if cur != code:
        return res("failed", f"改成 {name}：POST 回應相符，但重讀屬性頁 productionType={cur}（不重試）", False)
    return res("ok", f"已改成 {name} 並驗證（POST {r.status}）", True)
