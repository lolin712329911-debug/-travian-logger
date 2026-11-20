#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/actions/village_switch.py（ac-01）
版本：v0.1（A5b；B1 才實際切村）
用途：switch_to(gw, did) → ExecResult；assert_active(gw, did, *, map_half=None) → bool。
依賴：if-02（Gateway）、ps-02（parse_active_village）、cm-03（PATH_DORF1）、cm-02（ExecResult；卡片原未列，v0.1 補）。
部署狀態：未部署（GA 前不 live）。

來源：無（新寫，§4.2 卡片）。
  switch_to：單村期間是無操作，回 ExecResult("skipped", …, 0)，不送任何請求；B1 加 did／newdid 後才實際切村。
    回 skipped 而不是 ok：沒有切換就不能宣稱成功（C5 的 result 語意）。呼叫端（stage）不得把它當失敗。
  assert_active：抓 dorf1 原始 HTML（純 HTTP，不渲染），用 parse_active_village 核對目前選中的村是否為 did。
    讀不到、兩處來源不一致（parser 回 None）→ False（不猜）。
    **抓頁失敗（GatewayError）不吞掉、往上丟**：讀不到頁面不等於「村不符」，由呼叫端決定（C8 的「村莊跳過」只在確定不符時才寫）。
"""
from ..common.constants import PATH_DORF1
from ..common.decisions import ExecResult
from ..infra.gateway import Gateway
from ..parsers.village_list import parse_active_village

__all__ = ["switch_to", "assert_active"]


def _check_did(did) -> None:
    if isinstance(did, bool) or not isinstance(did, int) or did < 1:
        raise ValueError("did 需為 int ≥ 1")


def switch_to(gw: Gateway, did: int) -> ExecResult:
    """單村模式：無操作（不送請求）。B1 起改成實際切村。"""
    _check_did(did)
    return ExecResult("skipped", "單村模式：不切村（B1 起才實際切換）", 0, None)


def assert_active(gw: Gateway, did: int, *, map_half=None) -> bool:
    """目前選中的村莊是否為 did。抓頁失敗丟 GatewayError（不當成不符）。"""
    _check_did(did)
    html = gw.get(PATH_DORF1, raw=True)
    return parse_active_village(html, map_half) == did
