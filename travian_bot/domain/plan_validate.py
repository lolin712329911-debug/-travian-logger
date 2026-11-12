#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/plan_validate.py（dm-12）
版本：v0.1（A3a）
用途：build_order 的驗證（C12 PlanVerdict；純函式）。LLM／人寫的順序一律先過這裡，不過就 hold、不照做（v0.10 決定）。
依賴：cm-01（models）、cm-02（decisions）、cm-03（constants）、cm-09（parsed）、cm-12（game_rules）。
部署狀態：未部署（GA 前不 live）。

來源：新寫。舊 travian_agent.parse_build_order 只做格式檢查（錯就丟 ValueError）；plan_with_order 只有執行期的
      blocked 回傳，沒有事前驗證，所以沒有可併入的內建檢查。parse_build_order 的格式（'res:2,15:3,…'）沿用，
      但不丟例外：看不懂的記號保留成 RawStep（level＝None），交給 check_step 判 bad_format。
驗證項目：①格式 ②gid 存在於 constants.GID_NAMES ③等級上限（資源田依 game_rules.resource_field_cap；
      其他建築最高 20 級）④前置條件：下一步若要「蓋新建築」，建造清單上不能有未達成或被禁止的條件。
      「只判定下一步要執行的那一步」：下一步＝順序中第一個還沒達成的步驟；被拒的是下一步才 hold，
      其他被拒的步驟只記錄在 rejected（輪到它們時會再驗一次）。
決定（A3a，列入 §10）：
  · ④ 採嚴格：新建築缺前置條件就 hold，不像 plan_with_order 那樣自動補。順序要把前置條件排在前面。
  · ④ 需要空地建造清單；缺資料時略過 ④（①②③ 照做），並由 validation_need() 告訴 stage 要先抓什麼。
  · 全部步驟都已達成：verdict＝proceed、next_seq＝最後一步的序號（planner 會回 done）。
  · RawBuildOrder 欄位（✗ 待 A4b）：seq（1 起算）、key（'res' 或 gid）、level。None 或空＝missing_order（hold）。
"""
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

from ..common.constants import FREE_SLOT_RANGE, GID_NAMES, gid_name
from ..common.decisions import BuildFacts, FactsNeed
from ..common.game_rules import resource_field_cap
from ..common.models import PlanRejection, PlanVerdict
from ..common.parsed import Dorf1

__all__ = ["RawStep", "StepVerdict", "MAX_BUILDING_LEVEL", "parse_build_order", "check_step", "usable_order",
           "validate_order", "validation_need"]

MAX_BUILDING_LEVEL = 20
_TOKEN = re.compile(r"(res|資源田|\d+)\s*[:：]\s*(\d+)", re.I)
_SPLIT = re.compile(r"[,\s，;；]+")


@dataclass(frozen=True)
class RawStep:
    seq: int            # 1 起算
    key: Any            # 'res' 或 gid（int）；讀不懂時是原始記號
    level: Any          # int；讀不懂時 None


@dataclass(frozen=True)
class StepVerdict:
    seq: int
    ok: bool
    rule: Optional[str]     # ok＝False 時：bad_format／unknown_building／level_over_cap／prereq_unmet
    reason: str


def parse_build_order(text: Optional[str]) -> Tuple[RawStep, ...]:
    """'res:2,15:3' → (RawStep(1,'res',2), RawStep(2,15,3))。不丟例外；空白或 None → 空 tuple。"""
    steps = []
    for tok in _SPLIT.split((text or "").strip()):
        if not tok:
            continue
        m = _TOKEN.fullmatch(tok)
        if not m:
            steps.append(RawStep(len(steps) + 1, tok, None))
            continue
        k = m.group(1)
        steps.append(RawStep(len(steps) + 1, int(k) if k.isdigit() else "res", int(m.group(2))))
    return tuple(steps)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def check_step(step: RawStep, is_capital: bool) -> StepVerdict:
    """①②③（只看這一步本身，不看村莊狀態）。"""
    k, lv = step.key, step.level
    if not ((k == "res") or (_is_int(k) and k >= 1)) or not _is_int(lv) or lv < 1:
        return StepVerdict(step.seq, False, "bad_format", f"第 {step.seq} 步看不懂（{k!r}:{lv!r}），格式應為 res:2 或 15:3")
    if k != "res" and k not in GID_NAMES:
        return StepVerdict(step.seq, False, "unknown_building", f"第 {step.seq} 步的 gid {k} 不在已知建築表")
    if k == "res" or k in (1, 2, 3, 4):
        cap = resource_field_cap(is_capital)
        if cap is not None and lv > cap:
            return StepVerdict(step.seq, False, "level_over_cap", f"第 {step.seq} 步：資源田最高 {cap} 級，寫了 {lv}")
    elif lv > MAX_BUILDING_LEVEL:
        return StepVerdict(step.seq, False, "level_over_cap",
                           f"第 {step.seq} 步：{gid_name(k)} 最高 {MAX_BUILDING_LEVEL} 級，寫了 {lv}")
    return StepVerdict(step.seq, True, None, "")


def usable_order(raw: Sequence[RawStep], is_capital: bool) -> List[Tuple[Any, int]]:
    """通過 ①②③ 的步驟，轉成 build_planner 吃的 [('res', 2), (15, 3), …]（順序不變）。"""
    return [(s.key, s.level) for s in raw if check_step(s, is_capital).ok]


def _achieved(step: RawStep, dorf1: Dorf1, facts: BuildFacts, is_capital: bool) -> Optional[bool]:
    """該步是否已達成；None＝缺 dorf2（建築步驟需要）。"""
    k, lv = step.key, step.level
    if k == "res" or k in (1, 2, 3, 4):
        gids = (1, 2, 3, 4) if k == "res" else (k,)
        cap = resource_field_cap(is_capital)
        if k == "res" and cap is not None:
            lv = min(lv, cap)
        return all(f.level >= lv for f in dorf1.fields if f.gid in gids)
    if facts.dorf2 is None:
        return None
    return max((s.level for s in facts.dorf2.slots if s.gid == k), default=0) >= lv


def _empty_aid(facts: BuildFacts) -> Optional[int]:
    lo, hi = FREE_SLOT_RANGE
    empty = sorted(s.aid for s in facts.dorf2.slots if s.gid is None and lo <= s.aid <= hi)
    return empty[0] if empty else None


def _walk(raw, dorf1, facts, is_capital):
    """回傳 (rejected: list[(seq, rule, reason)], next_step or None, need or None)。"""
    rejected, verdicts = [], {}
    for s in raw:
        v = check_step(s, is_capital)
        verdicts[s.seq] = v
        if not v.ok:
            rejected.append((v.seq, v.rule, v.reason))
    nxt, need = None, None
    for s in raw:
        if not verdicts[s.seq].ok:
            nxt = s
            break
        a = _achieved(s, dorf1, facts, is_capital)
        if a is None:
            nxt, need = s, FactsNeed("dorf2")
            break
        if not a:
            nxt = s
            break
    if nxt is not None and verdicts[nxt.seq].ok and need is None and nxt.key != "res" and nxt.key not in (1, 2, 3, 4):
        if not any(sl.gid == nxt.key for sl in facts.dorf2.slots):          # 要蓋新建築
            aid = _empty_aid(facts)
            if aid is not None:
                if aid not in facts.options:
                    need = FactsNeed("build_options", aid)
                else:
                    entry = next((o for o in facts.options[aid] if o.gid == nxt.key), None)
                    if entry is not None and not entry.buildable:
                        for c in entry.conditions:
                            if c.met:
                                continue
                            why = (f"{gid_name(nxt.key)} 被 {c.name} 擋住（村莊裡不能已經有它）" if c.forbidden else
                                   f"{gid_name(nxt.key)} 的前置條件「{c.name} {c.level} 級」還沒達成，要排在這步之前")
                            rejected.append((nxt.seq, "prereq_unmet", why))
                            break
    return rejected, nxt, need


def validation_need(raw: Optional[Sequence[RawStep]], dorf1: Dorf1, facts: BuildFacts,
                    is_capital: bool) -> Optional[FactsNeed]:
    """要做完整驗證（含 ④）還缺什麼頁面；None＝不缺。stage 先抓再呼叫 validate_order。"""
    if not raw:
        return None
    return _walk(raw, dorf1, facts, is_capital)[2]


def validate_order(raw: Optional[Sequence[RawStep]], dorf1: Dorf1, facts: BuildFacts, is_capital: bool,
                   did: int, checked_utc: str) -> PlanVerdict:
    """回傳 PlanVerdict（C12）。缺資料時略過 ④（見檔頭）。"""
    if not raw:
        return PlanVerdict(did, checked_utc, "hold", None,
                           (PlanRejection(1, "missing_order", "沒有讀到 build_order"),))
    rejected, nxt, _ = _walk(raw, dorf1, facts, is_capital)
    rej = tuple(PlanRejection(q, rule, reason[:200]) for q, rule, reason in sorted(rejected, key=lambda x: x[0]))
    if nxt is None:
        return PlanVerdict(did, checked_utc, "proceed", raw[-1].seq, rej)
    hold = any(q == nxt.seq for q, _, _ in rejected)
    return PlanVerdict(did, checked_utc, "hold" if hold else "proceed", nxt.seq, rej)
