#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/village_lock.py（dm-09）
版本：v0.1（A3c）
用途：C8 村莊鎖（單村期間 Config 的 main_did／main_did_set_utc）。第一次執行記錄、之後只讀；
      每輪核對 main_did 與目前 active 村，不符該村本輪跳過（寫「村莊跳過」），不 disable()。純函式，不碰網路與時鐘。
依賴：cm-01（VillageLock、ValidationError）、cm-02（LockDecision）。
部署狀態：未部署（GA 前不 live）。A6b 接入 village_cycle。

公開介面
  decide_lock(lock, active_did)               → LockDecision（ok／skip；ok 且 record＝True 表示鎖尚未記錄）
  record_main(active_did, now_utc, existing)  → VillageLock（existing 已有 main_did 就原樣回傳，絕不覆蓋）

新寫（卡片：舊源無）。與卡片差異：record_main 多 now_utc 參數（main_did_set_utc 要寫時間，domain 不讀時鐘，
由呼叫端傳 serialize 格式的 UTC 字串）與可選的 existing（用來保證「之後只讀」）。
"""
from typing import Optional

from ..common.decisions import LockDecision
from ..common.models import ValidationError, VillageLock

__all__ = ["decide_lock", "record_main"]


def _valid_did(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def decide_lock(lock: Optional[VillageLock], active_did: Optional[int]) -> LockDecision:
    """核對村莊鎖。
    ・目前村未知（None 或不是 ≥1 的 int）→ skip（不記錄；不能把未知寫成主村）。
    ・鎖還沒記錄（lock 為 None 或 main_did 為 None）→ ok＋record＝True（第一次執行）。
    ・main_did 等於目前村 → ok。
    ・不符 → skip，reason 含兩個 did（寫「村莊跳過」；不 disable）。"""
    if not _valid_did(active_did):
        return LockDecision("skip", "目前村莊未知，本輪跳過")
    main = None if lock is None else lock.main_did
    if main is None:
        return LockDecision("ok", "主村尚未記錄，記錄目前村為主村", record=True)
    if main == active_did:
        return LockDecision("ok", "目前村是主村")
    return LockDecision("skip", f"目前村 {active_did} 不是主村 {main}，本輪跳過")


def record_main(active_did: int, now_utc: str, existing: Optional[VillageLock] = None) -> VillageLock:
    """建立「第一次記錄」的鎖。existing 已有 main_did 時原樣回傳（只讀，不覆蓋）。
    active_did 不是 ≥1 的 int、或 now_utc 不是非空字串 → ValidationError（不靜默用預設值）。"""
    if existing is not None and existing.main_did is not None:
        return existing
    if not _valid_did(active_did):
        raise ValidationError("VillageLock", "main_did", active_did, "type")
    if not isinstance(now_utc, str) or not now_utc.strip():
        raise ValidationError("VillageLock", "main_did_set_utc", now_utc, "type")
    return VillageLock(main_did=active_did, main_did_set_utc=now_utc.strip())
