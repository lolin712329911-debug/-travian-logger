#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/item_transfer.py（dm-05）
版本：v0.1（A3b）
用途：decide_item_transfer(need, state, queue_busy, attack_eta_s, settings) → ItemTransferDecision。
      英雄道具庫 → 村莊的資源轉移：轉哪幾種、各轉多少（只轉缺口）。純函式。
依賴：cm-02（ItemTransferDecision、TransferLine）、cm-09（TransferState）。
部署狀態：未部署（GA 前不 live）。

來源 travian_transfer.py v1.2 的 decide_transfer（✓ 已讀）。重新規劃（A3b）：
  1. 村莊現量、倉容、道具庫都取自同一次 graphql 讀回（TransferState），不用 snapshot（避免兩次讀取的時間差）。
  2. need＝升級成本（木磚鐵穀「總量」，不是缺口）；來源（next_target.cost 或建築頁 fillUp）由 stage 決定，
     parse_target_amounts 不屬於 domain。
  3. attack_eta_s 由呼叫端傳（C2 沒有攻擊 ETA；來源 Dorf1.attack_eta_s）。queue_busy 由 stage 以 queue_free_in_s > 0 判斷。
  4. mode（off／dry／live）不進 domain；舊 incoming_only／always → settings.only_on_incoming。
  5. 舊 Plan.decision 七種結果 → ItemTransferDecision.kind（cm-02 v0.4 的 TRANSFER_KINDS）。
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from ..common.decisions import ItemTransferDecision, TransferLine
from ..common.parsed import TransferState

__all__ = ["TransferSettings", "decide_item_transfer"]

_RES_NAME = ("木", "磚", "鐵", "穀")


@dataclass(frozen=True)
class TransferSettings:
    min_inventory: int = 20000      # Config hero_transfer_min：每一種要轉的資源，道具庫都要 ≥ 此值
    max_gap: int = 1000             # Config hero_transfer_max_gap：缺口加總 > 此值不轉
    eta_min: int = 45               # Config hero_transfer_eta_min：最快來襲 ETA ≤ 此分鐘才處理
    only_on_incoming: bool = True   # 舊 incoming_only（True）／always（False）


def _no(kind: str, reason: str) -> ItemTransferDecision:
    return ItemTransferDecision(False, reason, kind=kind)


def decide_item_transfer(
    need: Optional[Tuple[int, int, int, int]],
    state: Optional[TransferState],
    queue_busy: bool,
    attack_eta_s: Optional[int],
    settings: TransferSettings = TransferSettings(),
) -> ItemTransferDecision:
    if settings.only_on_incoming:
        if attack_eta_s is None or attack_eta_s > settings.eta_min * 60:
            return _no("not_needed", "無來襲或最快 ETA 超過門檻")
    if queue_busy:
        return _no("queue_busy", "施工佇列已占用，不轉（轉進來會留在村莊被搶）")
    if not need or state is None or len(need) != 4:
        return _no("no_data", "讀不到目標成本或村莊／道具庫狀態")
    gaps = tuple(max(0, need[i] - state.stock[i]) for i in range(4))
    total = sum(gaps)
    if total == 0:
        return _no("affordable", "村莊付得起，不動道具庫")
    if total > settings.max_gap:
        return _no("gap_too_big", f"缺口加總 {total} > {settings.max_gap}")
    for i, g in enumerate(gaps):
        if g and need[i] > state.capacity[i]:
            return _no("over_capacity", f"{_RES_NAME[i]} 目標 {need[i]} 超過倉容 {state.capacity[i]}")
    lines = []
    for i, g in enumerate(gaps):
        if not g:
            continue
        it = state.inventory[i]
        if it is None:
            return _no("inventory_low", f"道具庫沒有{_RES_NAME[i]}")
        if it.amount < settings.min_inventory or it.amount < g:
            return _no("inventory_low", f"{_RES_NAME[i]}庫存 {it.amount} < 門檻 {settings.min_inventory}")
        lines.append(TransferLine(resource=i, item_id=it.id, amount=g))
    return ItemTransferDecision(True, f"缺口 {total}，從道具庫轉 {len(lines)} 種", tuple(lines),
                                state.village_id, tuple(need), "transfer")
