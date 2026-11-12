#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/fill_in.py（dm-02）
版本：v0.1（A3a）
用途：build_order 嚴格照順序時，主目標等資源的空檔「插隊」做後面付得起的項目（純函式）。
依賴：cm-01（models）、cm-02（decisions）。
部署狀態：未部署（GA 前不 live）。

來源：舊 fill_in.py v0.1（✓ 已讀；演算法完全沿用）。
標準：插隊之後，主目標「可以開工」的時間不能比不插隊更晚（可用 slack_h 放寬）。
  主目標開工時間＝max(湊齊成本的時間, 施工佇列出現空位的時間)。插隊項目 F 會：① 扣掉 F 的成本；② 佔一格佇列直到 F 完工。
來襲放寬：有來襲、且來襲會在主目標湊齊之前抵達（或不知道 ETA）時，超過山洞隱藏量的存量反正會被搶，
  主目標的存量只算 min(存量, hidden)。△ 假設超出的部分會「全部」被搶（實際有載重上限）→ 放寬偏樂觀。
與舊版差異：
  1. should_fill 回傳 FillCheck（frozen）取代 (bool, dict)；數字 t0／t1／tq 在 FillCheck，說明併入 why。
  2. hidden 改為每種資源一個值（Res4，來自 VillageSnapshot.hidden）；舊版是單一數字，傳 4 個相同值結果相同。
  3. 新增 pick_fill_in：吃 build_planner.fill_in_candidates 的候選，回傳 FillInDecision（act＝是否插隊）。
     候選的列舉（舊 plan_fill_ins）在 build_planner：domain 之間不能互相 import（§4.1）。
  4. incoming_attacks＝None（未知）視為沒有來襲（舊版 attacks=0 同義）。
"""
from dataclasses import dataclass
from typing import Optional, Sequence

from ..common.decisions import FillCandidate, FillInDecision
from ..common.models import BuildTarget, VillageSnapshot

__all__ = ["INF", "FillCheck", "start_hours", "queue_free_hours", "should_fill", "pick_fill_in"]

INF = float("inf")


@dataclass(frozen=True)
class FillCheck:
    ok: bool
    why: str
    t0: Optional[float] = None
    t1: Optional[float] = None
    tq: Optional[float] = None
    relaxed: bool = False


def start_hours(stock, prod, cost, hidden=None) -> float:
    """湊齊 cost 需要幾小時（0＝現在就夠）；某種缺的資源產量 ≤ 0 → inf。
    hidden 不是 None（4 個值）：存量只算 min(存量, hidden)（來襲後倖存的部分）。"""
    worst = 0.0
    for i, (s, p, c) in enumerate(zip(stock, prod, cost)):
        if hidden is not None:
            s = min(s, hidden[i])
        short = c - s
        if short <= 0:
            continue
        if p <= 0:
            return INF
        worst = max(worst, short / p)
    return worst


def queue_free_hours(queue_secs, slots: int, f_secs: float) -> float:
    """放進 F 之後，施工佇列要幾小時才有空位（0＝還有空位）。queue_secs＝目前各項剩餘秒數。"""
    items = list(queue_secs) + [f_secs]
    if len(items) < slots:
        return 0.0
    return min(items) / 3600.0


def should_fill(stock, prod, main_cost, f_cost, f_secs, queue_secs, slots: int, hidden=None,
                attacks: Optional[int] = 0, attack_eta_s=None, slack_h: float = 0.0) -> FillCheck:
    if any(c > s for c, s in zip(f_cost, stock)):
        return FillCheck(False, "插隊項目現在付不起")
    t_plain = start_hours(stock, prod, main_cost)
    relaxed = bool(attacks) and hidden is not None and (attack_eta_s is None or attack_eta_s / 3600.0 <= t_plain)
    h = hidden if relaxed else None
    t0 = start_hours(stock, prod, main_cost, h)
    if t0 == INF:
        return FillCheck(False, "主目標有資源產量 ≤ 0，算不出開工時間", relaxed=relaxed)
    after = [s - c for s, c in zip(stock, f_cost)]
    t_res = start_hours(after, prod, main_cost, h)
    tq = queue_free_hours(queue_secs, slots, f_secs)
    t1 = max(t_res, tq)
    ok = t1 <= t0 + slack_h + 1e-9
    why = (f"主目標開工 {t0:.2f}h → {t1:.2f}h（湊資源 {t_res:.2f}h、佇列 {tq:.2f}h）"
           + ("，來襲放寬（超出隱藏量的存量視為已被搶）" if relaxed else "")
           + ("" if ok else "：會拖慢主目標，不插隊"))
    return FillCheck(ok, why, t0, t1, tq, relaxed)


def pick_fill_in(main: BuildTarget, candidates: Sequence[FillCandidate], snapshot: VillageSnapshot,
                 queue_secs: Sequence[int], slots: int, *, attack_eta_s: Optional[int] = None,
                 slack_h: float = 0.0) -> FillInDecision:
    """依 build_order 順序逐一檢查候選，第一個通過的就是插隊對象（act＝True）；都不行 act＝False，
    reason 列出每個候選的結論。fill_mode＝dry 的處理（只記錄不送出）在 stage。"""
    if not candidates:
        return FillInDecision(False, None, "沒有付得起的後續目標可以插隊")
    notes = []
    for c in candidates:
        t = c.target
        label = f"{t.name} {t.to_level} 級"
        if c.build_time_s is None:
            notes.append(f"{label}：工期未知，不判斷")
            continue
        chk = should_fill(snapshot.stock, snapshot.prod, main.cost, t.cost, c.build_time_s, queue_secs, slots,
                          hidden=snapshot.hidden, attacks=snapshot.incoming_attacks, attack_eta_s=attack_eta_s,
                          slack_h=slack_h)
        notes.append(f"{label}：{chk.why}")
        if chk.ok:
            return FillInDecision(True, t, "；".join(notes))
    return FillInDecision(False, None, "；".join(notes))
