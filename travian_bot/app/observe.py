#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/observe.py（ap-05）
版本：v0.1.4（GA-fix2：移除 [診斷 dorf1] 暫時診斷）｜v0.1.3（GA-fix1：快取的 dorf1 缺成本就純 HTTP 重抓；不論誰先抓）｜v0.1.2（GA-fix1 診斷：每輪印一行 [診斷 dorf1]，查出成本備援有沒有生效；查清後移除）｜v0.1.1（GA-fix1：dorf1 抓取改用 rc.dorf1_raw_if，成本被渲染清空時改抓原始 HTML）｜v0.1（A6a1）
用途：每村每輪的唯讀觀察：抓 dorf1／dorf2 → parsers → 組 C2 VillageSnapshot，並把資料記到 Sheet
      （Sheet1／Fields／Buildings／Buildable／Changes／state）。
依賴：ap-02、if-01（SessionLost）、if-02（GatewayError）、ps-01、ps-03、ps-04、ps-05（HeroState、parse_hero_status）、
      if-08、if-09、cm-01、cm-03、cm-06、cm-09、cm-10、cm-12（沿用卡片；本檔用不到，見交接區塊）。
部署狀態：未部署（GA 前不 live）。

處置：重新規劃（舊 log_village_snapshot／log_village_structure／log_player_state／build_state_rows／_setup_player／
      cp_summary 依賴 T.QUEUE_SLOTS、scrape_and_log、parse_village_page，並把「抓頁」「解析」「寫 Sheet」混在一起；
      舊 travian_parser.py 不搬，D-34）。

行為
  observe_village(rc, vc)：
    ①抓 dorf1（raw_if 判斷登入頁；不是村莊頁且 session.can_recover 就 recover() 重抓一次，仍失效丟 SessionLost；
      disable／通知交給 app/main）②抓 dorf2③parse_dorf1／parse_dorf2／parse_page_facts／parse_hero_status
      （英雄讀不到只 rc.warn；成功就更新 rc.hero）④組 C2 並驗證⑤Sheet 寫入（失敗只 rc.warn，不影響升級）。
    ①～④ 的 ParseError／GatewayError／SessionLost 不吞，往上丟（run_stage 轉成 failed）。
    ⑤ 全部 best-effort，包含 Buildable 的額外抓頁（✗ 對卡片「不吞」一句的解讀，見交接區塊）。
  C2 欄位：hidden＝None（D-32，山洞容量表沒有來源）；next_target／merchants＝None；incoming_res／outgoing_res＝空；
           units_home／units_away＝None（A6a1 不抓兵力）；queue_free_in_s 以 vc.build_settings.queue_slots 判斷滿不滿
           （Plus 的 +1 由 A6a2 建城 stage 以 snapshot_updates 修正 ✗）。
  人口、忠誠度、金幣、銀幣：None（D-34，A2a-3 才補）。
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..common import serialize
from ..common.constants import BUILD_CATEGORIES, FREE_SLOT_RANGE, RES_KEYS, RES_NAMES, gid_name
from ..common.models import VillageContext, VillageSnapshot
from ..common.parsed import BuildOption, Dorf1, Dorf2, HeroState, PageFacts, PlayerInfo
from ..common.schema import ParseError
from ..common.tribe_data import tribe_display_name
from ..infra.session import SessionLost
from ..infra.store.snapshot_repo import SnapshotLogRow
from ..parsers.buildings import parse_build_options
from ..parsers.hero import parse_hero_status
from ..parsers.player import parse_player_info
from ..parsers.village import dorf1_fields_lack_cost, parse_dorf1, parse_dorf2, parse_page_facts
from .run_context import RunContext

__all__ = ["observe_village", "fetch_build_options", "observe_player", "write_player_state",
           "build_snapshot_row", "build_state_rows", "cp_summary", "attack_eta_minutes", "hours_1dp"]

DORF1 = "dorf1.php"
DORF2 = "dorf2.php"


# ---------------------------------------------------------------- 純函式
def hours_1dp(secs: Optional[int]) -> Optional[float]:
    """秒 → 小時（取 1 位小數）；沿用舊 runner._hours。"""
    return round(secs / 3600, 1) if secs is not None else None


def attack_eta_minutes(secs: Optional[int]) -> Optional[int]:
    """來襲剩餘秒數 → 整數分鐘（無條件捨去，偏保守：不會比實際晚）。None→None。
    舊版是 round(秒/60, 1)（小數）；SnapshotLogRow.attack_eta_min 是 int，所以改取整。✗ 取整方式待你確認。"""
    if secs is None:
        return None
    return max(0, int(secs) // 60)


def _epoch_to_utc_str(ts: Optional[int]) -> Optional[str]:
    if ts is None or isinstance(ts, bool) or not isinstance(ts, int):
        return None
    return serialize.to_utc_str(datetime.fromtimestamp(ts, timezone.utc))


def build_snapshot_row(*, now: datetime, village_name: str, dorf1: Dorf1, facts: Optional[PageFacts],
                       hero: Optional[HeroState]) -> SnapshotLogRow:
    """Sheet1 一列。人口、忠誠度、金幣、銀幣一律 None（D-34）；讀不到的欄位 None（寫成空白）。"""
    return SnapshotLogRow(
        ts_utc=serialize.to_utc_str(now),
        server_time=_epoch_to_utc_str(facts.server_ts) if facts is not None else None,
        village_name=village_name,
        population=None, loyalty_pct=None, gold=None, silver=None,
        stock=dorf1.stock, prod=dorf1.prod, free_crop=dorf1.free_crop,
        hero_health_pct=hero.health_pct if hero is not None else None,
        hero_exp_pct=hero.exp_pct if hero is not None else None,
        hero_adventures=hero.adventures_count if hero is not None else None,
        queue=dorf1.queue,
        plus_hours=hours_1dp(dorf1.plus_s),
        protection_hours=hours_1dp(dorf1.protection_s),
        attacks=dorf1.incoming_attacks,
        attack_eta_min=attack_eta_minutes(dorf1.attack_eta_s),
    )


def build_state_rows(info: Optional[PlayerInfo], snap: Optional[VillageSnapshot],
                     queue_slots: int) -> List[Tuple[str, Any, str]]:
    """玩家／村莊狀態 → [(key, 值, 說明)]，給 state_repo.write_state。純函式。
    鍵與 §6.7 逐項相同；讀不到的不列，不猜。plus_active 以 bool 傳出（寫入時 state_repo 轉成 TRUE／FALSE）。"""
    rows: List[Tuple[str, Any, str]] = []

    def put(key, value, note):
        if value is not None:
            rows.append((key, value, note))

    if info is not None:
        if info.tribe_id is not None:
            put("tribe", tribe_display_name(info.tribe_id), "種族")
        if info.plus_active is not None:
            put("plus_active", bool(info.plus_active), "Plus 是否有效")
        have, need, per_day = info.cp_have, info.cp_need, info.cp_per_day
        if any(v is not None for v in (have, need, per_day, info.village_slots_used, info.village_slots_max)):
            put("cp_have", have, "目前文化點")
            put("cp_need", need, "下一個村莊名額需要的文化點")
            if have is not None and need is not None:
                gap = max(0, need - have)
                put("cp_gap", gap, "還缺多少文化點（0 = 已達標）")
                if gap == 0:
                    put("cp_eta_days", 0, "照目前每日產量估計還要幾天達標（不含慶典）")
                elif per_day and per_day > 0:
                    put("cp_eta_days", -(-gap // per_day), "照目前每日產量估計還要幾天達標（不含慶典）")
            put("cp_per_day", per_day, "文化點每日增加量（不含慶典）")
            put("village_slots_used", info.village_slots_used, "已用村莊名額")
            put("village_slots_max", info.village_slots_max, "目前文化點可擁有的村莊名額上限")
    put("queue_slots", queue_slots, "施工佇列長度（自動偵測或 Config 指定）")
    if snap is not None and (snap.cap_wh or snap.cap_gr):
        caps = (snap.cap_wh, snap.cap_wh, snap.cap_wh, snap.cap_gr)
        for i, key in enumerate(RES_KEYS):
            put(f"cap_{key}", caps[i], f"{RES_NAMES[i]}倉容量")
    return rows


def cp_summary(info: Optional[PlayerInfo]) -> Optional[str]:
    """文化點缺口整理成一行 log；讀不到（五欄任一為 None）回 None。"""
    if info is None:
        return None
    have, need, per_day = info.cp_have, info.cp_need, info.cp_per_day
    used, mx = info.village_slots_used, info.village_slots_max
    if None in (have, need, per_day, used, mx):
        return None
    slots = f"村莊名額 {used}/{mx}"
    gap = need - have
    if gap <= 0:
        return f"[文化點] {have}/{need}，已達標；{slots}"
    if per_day > 0:
        eta = f"，照目前每日 +{per_day} 約 {-(-gap // per_day)} 天（不含慶典）"
    else:
        eta = "，目前每日產量是 0"
    return f"[文化點] {have}/{need}，缺 {gap}{eta}；{slots}"


# ---------------------------------------------------------------- 抓頁
def _fetch_dorf1(rc: RunContext) -> str:
    """抓 dorf1。不是村莊頁：能 recover 就重建 session 重抓一次，仍失效丟 SessionLost。"""
    session = rc.session
    if DORF1 in rc.pages:
        cached = rc.pages[DORF1]
        if not dorf1_fields_lack_cost(cached):
            return cached
        # 別處（observe 之前）已用無備援方式抓過 dorf1，渲染後的頁面沒有資源田成本：純 HTTP 重抓一次，換掉快取。
        # 這只是備援：失敗或不是村莊頁就沿用原頁，讓下游 plan_stuck 處理（登入失效由後續流程判斷，不在這裡丟）。
        try:
            raw = rc.gateway.get(DORF1, raw=True)
        except SessionLost:
            raise
        except Exception as exc:  # noqa: BLE001
            rc.warn(f"dorf1 成本備援（純 HTTP 重抓）失敗：{type(exc).__name__}，沿用快取頁面")
            return cached
        if session.is_village_html(raw):
            rc.pages[DORF1] = raw
            return raw
        return cached
    html = rc.get_page(DORF1, raw_if=rc.dorf1_raw_if)      # 非村莊頁或成本被清空 → 純 HTTP 再抓
    if not session.is_village_html(html):
        if session.can_recover:
            session.recover()
            html = rc.get_page(DORF1, raw_if=rc.dorf1_raw_if, refresh=True)
        if not session.is_village_html(html):
            rc.pages.pop(DORF1, None)
            raise SessionLost("dorf1 不是村莊頁，登入狀態失效")
    return html


def _queue_free_in_s(d1: Dorf1, queue_slots: int) -> int:
    if len(d1.queue) < queue_slots:
        return 0
    return min(q.remaining_s for q in d1.queue)


def _make_snapshot(rc: RunContext, vc: VillageContext, d1: Dorf1) -> VillageSnapshot:
    snap = VillageSnapshot(
        did=vc.did, ts_utc=serialize.to_utc_str(rc.io.now()),
        stock=tuple(d1.stock), prod=tuple(d1.prod), cap_wh=d1.cap_wh, cap_gr=d1.cap_gr,
        hidden=None,
        queue_free_in_s=_queue_free_in_s(d1, vc.build_settings.queue_slots),
        queue_slots_used=len(d1.queue),
        next_target=None, merchants=None, incoming_res=(), outgoing_res=(),
        incoming_attacks=d1.incoming_attacks, units_home=None, units_away=None)
    snap.ensure_valid()
    return snap


def observe_village(rc: RunContext, vc: VillageContext) -> VillageSnapshot:
    """唯讀觀察一個村，回傳 C2 快照；並盡力把資料記到 Sheet（失敗只 rc.warn）。"""
    html1 = _fetch_dorf1(rc)
    html2 = rc.get_page(DORF2)
    d1 = parse_dorf1(html1)
    d2 = parse_dorf2(html2)
    facts = parse_page_facts(html1)
    try:
        hero = parse_hero_status(html1)
        rc.hero = hero
    except ParseError as exc:
        hero = rc.hero
        rc.warn(f"讀不到英雄狀態（{type(exc).__name__}），沿用上一次的值")
    snap = _make_snapshot(rc, vc, d1)
    _record_sheets(rc, vc, d1, d2, facts, hero)
    return snap


# ---------------------------------------------------------------- Sheet 寫入（best-effort）
def _names(*groups: Sequence[Any]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for g in groups:
        for item in g:
            gid = getattr(item, "gid", None)
            if isinstance(gid, int) and not isinstance(gid, bool):
                out[gid] = gid_name(gid)
    return out


def _first_free_aid(d2: Dorf2) -> Optional[int]:
    lo, hi = FREE_SLOT_RANGE
    free = [s.aid for s in d2.slots if s.gid is None and lo <= s.aid <= hi]
    return min(free) if free else None


def fetch_build_options(rc: RunContext, aid: int) -> Tuple[BuildOption, ...]:
    """（唯讀）依 BUILD_CATEGORIES 抓空地 aid 的 3 個分頁，以 gid 去重、保留頁面順序。
    不帶 category：BuildOption 與 Buildable 都沒有該欄。"""
    out: List[BuildOption] = []
    seen = set()
    for cat in BUILD_CATEGORIES:
        for opt in parse_build_options(rc.get_page(f"build.php?id={aid}&category={cat}")):
            if opt.gid in seen:
                continue
            seen.add(opt.gid)
            out.append(opt)
    return tuple(out)


def _record_sheets(rc: RunContext, vc: VillageContext, d1: Dorf1, d2: Dorf2,
                   facts: Optional[PageFacts], hero: Optional[HeroState]) -> None:
    """Sheet1＋結構分頁。任何失敗只 rc.warn（SessionLost 例外：登入失效要往上）。"""
    now = rc.io.now()
    now_s = serialize.to_utc_str(now)
    try:
        row = build_snapshot_row(now=now, village_name=vc.name, dorf1=d1, facts=facts, hero=hero)
        rc.io.append_snapshot(rc.sh, vc.did, row)
    except SessionLost:
        raise
    except Exception as exc:  # noqa: BLE001
        rc.warn(f"寫入 Sheet1 失敗（不影響升級）：{type(exc).__name__}")
    try:
        names = _names(d1.fields, d2.slots)
        res = rc.io.write_structure(rc.sh, vc.did, now=now_s, fields=d1.fields, buildings=d2.slots, names=names)
        aid = _first_free_aid(d2)
        if aid is None:
            return
        if res.buildings_changed or rc.io.buildable_due(rc.sh, vc.did, now=now_s):
            options = fetch_build_options(rc, aid)
            rc.io.write_structure(rc.sh, vc.did, now=now_s, buildable=options,
                                  names={**names, **_names(options)})
    except SessionLost:
        raise
    except Exception as exc:  # noqa: BLE001
        rc.warn(f"記錄村莊結構失敗（不影響升級）：{type(exc).__name__}")


# ---------------------------------------------------------------- 玩家
def observe_player(rc: RunContext) -> PlayerInfo:
    """讀種族／Plus／文化點。用 rc.pages 的 dorf1，沒有才抓；ParseError 時改讀 dorf2，仍失敗往上丟（不回 None）。"""
    html = rc.pages.get(DORF1) or rc.get_page(DORF1)
    try:
        return parse_player_info(html)
    except ParseError:
        return parse_player_info(rc.get_page(DORF2))


def write_player_state(rc: RunContext, vc: VillageContext, info: Optional[PlayerInfo],
                       snap: Optional[VillageSnapshot], queue_slots: int) -> bool:
    """state 分頁（best-effort）。成功 True；失敗只 rc.warn 並回 False。"""
    try:
        rows = build_state_rows(info, snap, queue_slots)
        rc.io.write_state(rc.sh, vc.did, rows, serialize.to_utc_str(rc.io.now()))
        return True
    except Exception as exc:  # noqa: BLE001
        rc.warn(f"記錄 state 失敗（不影響升級）：{type(exc).__name__}")
        return False
