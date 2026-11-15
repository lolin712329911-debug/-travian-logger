#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/formatting.py（ap-06）
版本：v0.1（A6a1）
用途：把決策轉成人看得懂的文字（只供 Actions.detail 與 log），以及 Actions 動作名稱常數、log 行格式。
依賴：cm-01（models）、cm-02（decisions）、cm-03（constants）、cm-10（serialize）。
部署狀態：未部署（GA 前不 live）。

處置：重新規劃（舊 runner.describe 讀全域 T.QUEUE_SLOTS、吃舊 action tuple 與舊 Field，_now 輸出 `%F %T`；
      a、b、e 不成立）。文字沿用舊 describe 的句子，能對上的情況輸出與舊函式逐字相同（golden：
      tests/golden/app/formatting/describe_old.expected.json，由舊 runner.py 離線產生）。
規則：中文只放 detail；Actions.result 一律用 C5 列舉（本檔不產生 result）。

與舊版的差異
  - describe 吃 BuildDecision（涵蓋 BUILD_DECISION_KINDS 的 9 個值）＋VillageSnapshot＋佇列長度；舊版吃 tuple 與 Field。
  - no_affordable、need_facts 舊碼沒有，新寫說明文字；no_free_slot 的 gid 在新決策裡只剩 reason 文字，直接用 reason。
  - with_queue：C2 沒有佇列項目名稱，只剩「已用格數」與「最早空出秒數」，文字不同於舊版（舊版列出項目名稱）。
  - now_str 走 serialize.to_utc_str（舊版 `%F %T`）。
"""
from datetime import datetime
from typing import Any, Optional, Tuple

from ..common import serialize
from ..common.constants import RES_NAMES, gid_name
from ..common.decisions import BUILD_DECISION_KINDS, BuildDecision
from ..common.models import BuildTarget, VillageSnapshot

__all__ = ["ACTION_BUILD", "ACTION_BUILD_WAIT", "KIND_LABELS", "LOG_LEVELS", "describe", "with_queue", "mins",
           "fname", "flv", "now_str", "log_line"]

# Actions.action 常數（D-33；cm-03 不動）。≤40 字。
ACTION_BUILD = "升級"             # 真的升級（或乾跑）
ACTION_BUILD_WAIT = "建城等待"    # 建城決策不是 build：等資源、等佇列、倉容不足…（具體原因在 detail）

# 決策種類 → 中文顯示名（只供 detail／log）。舊標籤取自 §6.7；no_affordable、need_facts 為新寫。
KIND_LABELS = {
    "build": "升級",
    "wait_resources": "等待資源",
    "wait_queue": "等待佇列",
    "storage_too_small": "倉容不足",
    "plan_stuck": "計畫卡住",
    "no_free_slot": "無空地",
    "done": "已完成",
    "no_affordable": "沒有付得起的目標",
    "need_facts": "缺頁面資料",
}
LOG_LEVELS = ("INFO", "WARN", "ERROR")


def fname(target: BuildTarget) -> str:
    n = gid_name(target.gid)
    return f"{n}(slot {target.aid})" if target.gid in (1, 2, 3, 4) else n


def flv(level: int, gid: Optional[int]) -> str:
    """level＝目前等級（升到 level+1）。非資源田且等級 0＝新建。"""
    return f"L{level}→L{level + 1}" if level > 0 or gid in (1, 2, 3, 4) else "新建→L1"


def mins(secs: Any) -> str:
    m = max(1, round(secs / 60))
    return f"{m // 60}小時{m % 60}分" if m >= 60 else f"{m}分"


def now_str(now: datetime) -> str:
    return serialize.to_utc_str(now)


def with_queue(detail: str, snap: VillageSnapshot) -> str:
    if snap.queue_slots_used <= 0:
        return detail + "｜目前沒有施工中的項目"
    return detail + f"｜施工中 {snap.queue_slots_used} 項，最早約 {mins(snap.queue_free_in_s)} 後空出"


def _wait_text(d: BuildDecision, fallback: Optional[int] = None) -> Optional[int]:
    return d.wait_s if d.wait_s is not None else fallback


def describe(decision: BuildDecision, snap: VillageSnapshot, queue_slots: int) -> Tuple[str, Optional[BuildTarget], str]:
    """回傳 (動作標籤, BuildTarget 或 None, 說明)。說明要寫清楚「在等什麼、缺什麼」。"""
    kind = decision.kind
    if kind not in BUILD_DECISION_KINDS:
        raise ValueError(f"未知的建城決策種類：{kind}")
    label = KIND_LABELS[kind]
    t = decision.target
    if kind == "build":
        if t is None:
            return label, None, decision.reason
        return label, t, f"升級 {fname(t)} {flv(t.to_level - 1, t.gid)}"
    if kind == "wait_resources":
        if t is None:
            return label, None, decision.reason
        short = [f"{RES_NAMES[i]}缺{c - s}" for i, (c, s) in enumerate(zip(t.cost, snap.stock)) if c > s]
        wait = _wait_text(decision, t.ready_in_s or None)   # ready_in_s=0＝現在就夠，不當估計
        tail = f"，預計約 {mins(wait)} 後足夠" if wait is not None else ""
        return label, t, (f"下一個要升級 {fname(t)} {flv(t.to_level - 1, t.gid)}，"
                          f"資源不夠：{'、'.join(short) or '（差一點）'}{tail}")
    if kind == "wait_queue":
        if snap.queue_slots_used >= queue_slots:
            why = f"施工佇列已滿（{snap.queue_slots_used}/{queue_slots}），等有空位再升級"
        else:
            why = "目標建築（或它的前置建築）正在施工，等施工完成"
        tail = f"，約 {mins(decision.wait_s)} 後再試" if decision.wait_s is not None else ""
        return label, None, why + tail
    if kind == "storage_too_small":
        if t is None:
            return label, None, decision.reason
        caps = (snap.cap_wh, snap.cap_wh, snap.cap_wh, snap.cap_gr)
        over = [f"{RES_NAMES[i]}成本{c}>容量{m}" for i, (c, m) in enumerate(zip(t.cost, caps)) if c > m]
        return label, t, (f"{fname(t)} {flv(t.to_level - 1, t.gid)} 的成本超過倉庫/糧倉容量（{'、'.join(over)}），"
                          f"需先升倉庫/糧倉")
    if kind == "plan_stuck":
        return label, None, f"需要人處理：{decision.reason}"
    if kind == "no_free_slot":
        return label, None, decision.reason
    if kind == "done":
        return label, None, "設定的目標都已達成，沒有需要升級的項目"
    if kind == "no_affordable":
        return label, None, "目前資源沒有任何候選付得起，本輪不動"
    # need_facts
    need = decision.need
    what = f"（{need.kind}" + (f" aid={need.aid}" if need.aid is not None else "") + "）" if need else ""
    return label, None, f"決策缺少頁面資料{what}，要先抓完再判斷"


def log_line(now: datetime, level: str, stage: str, did: Optional[int], msg: Any) -> str:
    """§6.5：`{ts_utc} {LEVEL} {stage} {did或-} {msg}`；msg 先 redact、換行換成空白。"""
    if level not in LOG_LEVELS:
        raise ValueError(f"level 只能是 {LOG_LEVELS}")
    text = serialize.redact(msg).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return f"{now_str(now)} {level} {stage} {did if did is not None else '-'} {text}"
