#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/_util.py（A6a2 共用小工具；卡片沒列，交接區塊要補記）
版本：v0.1（A6a2）
用途：A6a2 各 stage 共用的幾個函式：英雄所在村判斷、同一輪 stage 之間的旗標（rc.stage_notes）、Actions 列、
      need_facts 補資料迴圈（build_planner／plan_validate 缺頁面時由 stage 抓完再呼叫）。
部署狀態：未部署（GA 前不 live）。未實測（本機沒有整個 repo）。
"""
from typing import Any, Callable, Optional, Tuple

from ...common import serialize
from ...common.decisions import BuildDecision, BuildFacts, BuildTarget, FactsNeed
from ...common.models import ActionRow, VillageContext, clip_text
from ...common.modes import Mode
from ...common.schema import ParseError
from ...parsers.buildings import parse_build_options, parse_building_cost
from ...parsers.village import parse_dorf2
from ..run_context import RunContext

# Actions.action 名稱（沿用舊 runner；≤40 字）
ACTION_ITEM_TRANSFER = "轉移"
ACTION_FOCUS = "加成"
ACTION_GUARD = "防搶加成"
ACTION_FILL_IN = "插隊"
ACTION_HERO = "冒險"

MAX_FACT_FETCHES = 6          # 一輪最多補幾次頁面資料（build_planner 檔頭寫 3～5 次）
DETAIL_MAX = 300


# ---------------------------------------------------------------- 英雄所在村
def hero_here(rc: RunContext, vc: VillageContext) -> bool:
    """英雄是否在這個村。rc.hero 有村 id 就比對（in_village_did 優先，沒有用 home_did）；
    讀不到英雄時退回 main_did（單村期間）；main_did 也沒有就當作在這裡（不因為讀不到而整輪不動）。"""
    h = rc.hero
    if h is not None:
        did = h.in_village_did if h.in_village_did is not None else h.home_did
        if did is not None:
            return did == vc.did
    main = (rc.cfg or {}).get("main_did")
    return main is None or main == vc.did


# ---------------------------------------------------------------- 同一輪 stage 之間的旗標
def _key(did: int, name: str) -> str:
    return f"{did}:{name}"


def set_note(rc: RunContext, did: int, name: str) -> None:
    """focus_acted（focus 這輪切了／失敗，守衛不跑）、built（這輪已有建城動作，加成與守衛不跑）。"""
    rc.stage_notes[_key(did, name)] = True


def has_note(rc: RunContext, did: int, name: str) -> bool:
    return bool(rc.stage_notes.get(_key(did, name)))


# ---------------------------------------------------------------- Actions 列
def make_row(rc: RunContext, did: int, action: str, mode: Mode, result: str, detail: str,
             target: Optional[BuildTarget] = None) -> ActionRow:
    t = target
    return ActionRow(
        ts_utc=serialize.to_utc_str(rc.io.now()), action=action[:40],
        aid=t.aid if t else None, gid=t.gid if t else None, level=(t.to_level - 1) if t else None,
        cost=serialize.res_to_cost_str(t.cost) if t else None,
        mode=mode.value, result=result, detail=clip_text(serialize.redact(detail), DETAIL_MAX), did=did)


# ---------------------------------------------------------------- need_facts 迴圈
def decision_step(fn: Callable[[BuildFacts], BuildDecision]) -> Callable[[BuildFacts], Tuple[BuildDecision, Optional[FactsNeed]]]:
    """把「回 BuildDecision 的呼叫」包成 run_with_facts 要的 step：kind＝need_facts 時帶出 need。"""
    def step(facts: BuildFacts):
        d = fn(facts)
        return d, (d.need if d.kind == "need_facts" else None)
    return step


def run_with_facts(rc: RunContext, step: Callable[[BuildFacts], Tuple[Any, Optional[FactsNeed]]]) -> Tuple[Any, BuildFacts]:
    """反覆呼叫 step(facts) → (結果, need)；need 不是 None 就抓頁面補進 facts 再呼叫（每次都從頭算，安全）。
    抓取規則（decisions.BuildFacts 的說明）：dorf2 讀失敗往上丟；建築頁讀不到成本＝None；空地清單讀失敗＝空 tuple。
    抓頁走 rc.get_page（本輪同一路徑只抓一次）。超過 MAX_FACT_FETCHES 次仍缺資料丟 RuntimeError。"""
    dorf2 = None
    costs, options = {}, {}
    for _ in range(MAX_FACT_FETCHES + 1):
        facts = BuildFacts(dorf2=dorf2, upgrade_costs=costs, options=options)
        value, need = step(facts)
        if need is None:
            return value, facts
        if need.kind == "dorf2":
            dorf2 = parse_dorf2(rc.get_page("dorf2.php"))
        elif need.kind == "upgrade_cost":
            try:
                costs[need.aid] = parse_building_cost(rc.get_page(f"build.php?id={need.aid}"))
            except ParseError:
                costs[need.aid] = None
        elif need.kind == "build_options":
            try:
                options[need.aid] = parse_build_options(rc.get_page(f"build.php?id={need.aid}"))
            except ParseError:
                options[need.aid] = ()
        else:
            raise ValueError(f"未知的 need_facts 種類：{need.kind}")
    raise RuntimeError("補頁面資料超過上限仍不足")
