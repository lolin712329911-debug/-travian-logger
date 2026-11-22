#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/actions/hide_exec.py（ac-06）
版本：v0.1.2（A5b；近期佔領檢查改為可選，預設關閉；第一步失敗時附診斷）
用途：send_troops(gw, did, decision, mode, *, map_half, …) → ExecResult：照 domain 的 HideDecision 派兵躲避（搶奪空綠洲）。
      兩步驟＋確認頁核對＋送出後重讀概況確認。另有純函式 confirm_matches、confirm_ok、recent_occupy（舊 hide_troops 的核對邏輯）。
依賴：if-02（Gateway）、ps-06（parse_overview、parse_send_confirm）、cm-02（HideDecision、ExecResult）、cm-04（Mode）、
      cm-07（geo.map_id）、cm-09（SendConfirm、TileSafety）、cm-11（ParseError）。
      不 import ac-07：綠洲即時驗證由 stage（ap-15）以參數 verify 注入（actions 同層互不依賴，卡片 ac-06 沒有列 ac-07）；
      cm-04（Mode，型別；判斷用字串，同 hero_exec）。卡片列的 cm-05 在 v0.1 沒有 import（建議從卡片移除）。
部署狀態：未部署（GA 前不 live；✗ 未對真實遊戲跑過，只用假 Gateway＋S17d 實機確認頁離線核對）。

來源：舊 hide_troops.py v0.5 的 run_once／_open_confirm／_live_safe／confirm_matches／confirm_ok（✓ 已讀）。**重新規劃**（§5.1 b、e 不成立）：
  1. 舊流程全程用 Playwright page（goto／fill／click／wait_for_url）；Gateway 沒有 fill，且 HTTP 回應不會載進瀏覽器，
     所以**三步全走 gw.request（HTTP POST）**，不動 if-02：
       第一步 POST /build.php?gid=16&tt=2（欄位 troop[tN]、villagename、x、y、eventType、ok；✓ Asia 8 第一步表單：無 hidden、無 token）
       → 回應即確認頁（form#troopSendForm，ps-06 解析）
       第三步 POST 同網址，欄位＝確認頁 form 的 hidden 欄位（✓ S17d 確認頁；checksum 本來由按鈕 onclick 填進欄位再 submit）。
     第三步的欄位由 SendConfirm 重建（action＝troopsSend/<villageId>/<epoch－trip_s>、redeployHero 恆空）；離線對 S17d 逐欄比對一致（見交接）。
  2. 決策不在這裡：候選、順序、units、scope、full 都來自 HideDecision（A3c）；本層不算來襲、不選綠洲、不等歸來（等待由 ap-15 睡）。
  3. 舊 confirm_matches 的「標題含掠奪」中文字面核對不搬：類型只認 SendConfirm.event_type＝4；多核對 village_did＝did、
     scout／catapult 目標為空；兵種鍵 u1～u10／hero（舊 t1～t11），hero 必須是 0。
  4. 時間一律 epoch 秒：confirm_ok 的頁面時間＝SendConfirm.epoch－trip_s（舊 info["epoch"]）；現在＝頁面時間＋send_delay_s（舊 clicks_s＝45，
     為瀏覽器點擊耗時；HTTP 沒有這段，保留預設 45 當保守餘量，可調）。
  5. 近期佔領判斷（舊 oasis_check.recent_occupy_warning）放在這裡（A3c 留給 ap-16／ac-07；ac-07 只回事實）：
     TileSafety.occupy_events 含「今天／昨天／分鐘／小時」字樣 → 該候選不派。✗ 只有 zh-TW 樣本（S15a 實有「昨天, 15:39」）。
     **v0.1.1**：此檢查改為參數 check_recent_occupy，預設 False（只看即時驗證 safe＝未佔領且動物為 0）；
     原因：舊規則等於「近 48 小時內有任何佔領事件就不派」，實測（2026-11-22）把候選全擋、躲兵一直 skipped。要恢復舊行為傳 True。
     被擋時的 detail 會附命中的事件原文（前 30 字），方便診斷。
  6. 不重試：確認頁之前的任何失敗只回報該候選並換下一個（沒有送出）；第三步 POST 之後一律以重讀概況為準，重讀失敗標「結果不明」。
安全：英雄永遠不帶；checksum 是 token，只存在於記憶體中的 POST 本文，不進 detail／例外訊息。
"""
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

from ..common.decisions import ExecResult, HideCandidate, HideDecision
from ..common.geo import map_id as geo_map_id
from ..common.modes import Mode
from ..common.parsed import SendConfirm, TileSafety
from ..common.schema import ParseError
from ..infra.gateway import Gateway
from ..parsers.rally import parse_overview, parse_send_confirm

__all__ = ["SEND_PATH", "OVERVIEW_PATH", "RECENT_MARKERS", "confirm_matches", "confirm_ok", "recent_occupy", "send_troops"]

SEND_PATH = "build.php?gid=16&tt=2"          # ✓ Asia 8 第一步表單 action、S17d 確認頁 form action（同一網址）
OVERVIEW_PATH = "build.php?gid=16&tt=1"
RECENT_MARKERS = ("今天", "昨天", "分鐘", "小時")      # 舊 recent_occupy_warning；✗ 只見 zh-TW
_FORM_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}
_UNIT_KEYS = tuple(f"u{i}" for i in range(1, 11))
_EVENT_RAID = 4                                          # ✓ SendConfirm.event_type：搶奪


def _mode_value(mode: Any) -> str:
    v = str(getattr(mode, "value", mode)).strip().lower()
    return v if v in ("off", "dry", "live") else "off"


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


# ---------------------------------------------------------------- 純函式：核對
def recent_occupy(events: Iterable[str], markers: Sequence[str] = RECENT_MARKERS) -> bool:
    """附近有最近的佔領事件（相對時間字樣）→ True。"""
    return any(any(k in e for k in markers) for e in events)


def confirm_matches(info: SendConfirm, units: Dict[str, int], pos: Sequence[int], did: int) -> Tuple[bool, str]:
    """按確認前的核對：兵力、目標、類型、出發村都要和預期一致，英雄必須是 0。回傳 (ok, 說明)。
    units：預期派出的 {'u1': n, …}（不含英雄）；pos：預期目標 (x, y)；did：預期出發村。"""
    if not info.has_confirm:
        return False, "確認頁沒有確認鈕"
    if info.village_did != did:
        return False, f"出發村不符：確認頁 {info.village_did}、預期 {did}"
    if info.units.get("hero") != 0:
        return False, "確認頁的英雄欄不是 0（英雄永遠不帶）"
    for k in _UNIT_KEYS:
        want = units.get(k, 0)
        if info.units.get(k) != want:
            return False, f"兵力不符：{k} 確認頁 {info.units.get(k)}、預期 {want}"
    if info.event_type != _EVENT_RAID:
        return False, f"類型不是搶奪（eventType={info.event_type}）"
    if (info.x, info.y) != (pos[0], pos[1]):
        return False, f"目標不符：確認頁 ({info.x}|{info.y})、預期 ({pos[0]}|{pos[1]})"
    if info.scout_target or info.catapult_target1 or info.catapult_target2:
        return False, "確認頁有偵察／投石目標（搶奪不該有）"
    return True, "ok"


def confirm_ok(info: SendConfirm, scope: Sequence[int], *, margin: int = 30,
               send_delay_s: int = 45) -> Tuple[bool, int, str]:
    """以確認頁的單程秒數做最後核對。頁面時間＝epoch－trip_s；送出時間＝頁面時間＋send_delay_s。
    ① 送出時間要在範圍內第一波之前；② 返回時間（送出＋2×單程）要晚於第一波（至少撐過第一波）。
    回傳 (ok, 撐過幾波, 說明)。是否撐過全部由呼叫端比較。"""
    if info.trip_s <= 0 or not scope:
        return False, 0, "單程秒數或來襲範圍不合法"
    send = (info.epoch - info.trip_s) + send_delay_s
    back = send + 2 * info.trip_s
    arrivals = sorted(scope)
    if send >= arrivals[0]:
        return False, 0, "來不及：送出時第一波已到"
    n = sum(1 for a in arrivals if send < a < back - margin)
    if not (send < arrivals[0] < back - margin):
        return False, n, "返回前第一波就到了"
    return True, n, f"單程 {info.trip_s}s、返回 epoch {back}、撐過 {n}/{len(arrivals)} 波"


# ---------------------------------------------------------------- 表單
def _step1_body(units: Dict[str, int], pos: Sequence[int]) -> str:
    fields: List[Tuple[str, str]] = [(f"troop[t{k[1:]}]", str(n)) for k, n in units.items()]   # u3 → t3（舊鍵 t1～t10）
    fields += [("villagename", ""), ("x", str(pos[0])), ("y", str(pos[1])),
               ("eventType", str(_EVENT_RAID)), ("ok", "ok")]
    return urlencode(fields)


def _step3_body(info: SendConfirm) -> str:
    """確認頁 form#troopSendForm 的 hidden 欄位（✓ S17d 逐欄對照；順序同頁面）。"""
    page_ts = info.epoch - info.trip_s
    fields: List[Tuple[str, str]] = [
        ("action", f"troopsSend/{info.village_did}/{page_ts}"),
        ("eventType", str(info.event_type)),
        ("villagename", info.villagename or ""),
        ("x", str(info.x)), ("y", str(info.y)),
        ("redeployHero", ""),
        ("checksum", info.checksum),
    ]
    for i, k in enumerate(_UNIT_KEYS + ("hero",), start=1):
        fields.append((f"troops[0][t{i}]", str(info.units[k])))
    fields += [("troops[0][scoutTarget]", info.scout_target or ""),
               ("troops[0][catapultTarget1]", info.catapult_target1 or ""),
               ("troops[0][catapultTarget2]", info.catapult_target2 or ""),
               ("troops[0][villageId]", str(info.village_did))]
    return urlencode(fields)


# ---------------------------------------------------------------- 決策檢查
def _units_of(decision: HideDecision) -> Optional[Dict[str, int]]:
    units: Dict[str, int] = {}
    for item in decision.units:
        if not (isinstance(item, tuple) and len(item) == 2):
            return None
        k, n = item
        if k not in _UNIT_KEYS or not _is_int(n) or n < 1 or k in units:
            return None                                  # 不收英雄、未知鍵、非正數量、重複鍵
        units[k] = n
    return units or None


def _cand_map_id(c: HideCandidate, map_half: int) -> int:
    mid = geo_map_id(c.x, c.y, map_half)
    if c.map_id is not None and c.map_id != mid:
        raise ValueError("候選的 map_id 與座標不符")
    return mid


def _short(parts: List[str], limit: int = 280) -> str:
    s = "；".join(parts)
    return s if len(s) <= limit else s[:limit - 1] + "…"


# ---------------------------------------------------------------- 主流程
def send_troops(gw: Gateway, did: int, decision: HideDecision, mode: Mode, *, map_half: int,
                verify: Callable[[Gateway, HideCandidate], TileSafety],
                max_confirm: int = 4, max_checks: int = 12, margin: int = 30, send_delay_s: int = 45,
                check_recent_occupy: bool = False) -> ExecResult:
    """依 decision 派兵。off→skipped；dry 走到確認頁核對後不送出；live 核對通過才送出，並重讀概況確認。
    check_recent_occupy：True＝沿用舊規則（occupy_events 有相對時間字樣就不派）；預設 False，只看即時驗證 safe。
    max_confirm：最多開幾次確認頁（第一步 POST）；max_checks：最多即時驗證幾個綠洲（便宜，不吃確認頁額度）。
    verify(gw, 候選)→TileSafety：綠洲即時驗證，由 stage 傳入（例：functools.partial(oasis_exec.verify_oasis, map_half=…) 包成兩參數）。
    驗證、第一步、重讀概況的 GatewayError／ParseError／RuntimeError（含 OasisExecError）／ValueError 都轉成回報，不重試。"""
    m = _mode_value(mode)
    if m == "off":
        return ExecResult("skipped", "mode=off，不動作", 0, None)
    n0 = gw.request_count()

    def res(result: str, detail: str, verified: Optional[bool] = None) -> ExecResult:
        return ExecResult(result, _short([detail]), gw.request_count() - n0, verified)

    if not decision.act or decision.kind != "go" or not decision.candidates:
        return res("skipped", f"決策不是派兵（kind={decision.kind or '空'}）")
    if not _is_int(did) or did < 1 or not _is_int(map_half) or map_half < 1:
        return res("failed", "did 或 map_half 不合法，不送出")
    units = _units_of(decision)
    scope = tuple(decision.scope)
    if units is None or not scope or not all(_is_int(a) for a in scope):
        return res("failed", "決策的 units／scope 不合法（要有正數量的 u1～u10、不含英雄，且 scope 非空），不送出")
    full_n = len(scope)

    tried: List[str] = []
    checks = confirms = 0
    for cand in decision.candidates:
        if checks >= max_checks or confirms >= max_confirm:
            break
        tag = f"({cand.x}|{cand.y})"
        try:
            mid = _cand_map_id(cand, map_half)
        except ValueError as e:
            tried.append(f"{tag} {e}")
            continue
        # ① 即時驗證綠洲
        checks += 1
        try:
            info = verify(gw, cand)
        except (RuntimeError, ParseError, ValueError) as e:       # GatewayError／OasisExecError 都是 RuntimeError
            tried.append(f"{tag} 驗證失敗：{type(e).__name__}")
            continue
        if not info.safe:
            tried.append(f"{tag} 即時驗證不通過（有動物／被佔領／動物未知）")
            continue
        if check_recent_occupy and recent_occupy(info.occupy_events):
            hit = next((e for e in info.occupy_events if any(k in e for k in RECENT_MARKERS)), "")
            tried.append(f"{tag} 附近剛有佔領事件：{hit[:30]}")
            continue
        # ② 第一步：POST 派兵表單 → 確認頁（還沒送出；離開確認頁＝不出兵 ✓）
        confirms += 1
        r1 = None
        try:
            r1 = gw.request("POST", SEND_PATH, headers=_FORM_HEADERS, data=_step1_body(units, (cand.x, cand.y)))
            if not r1.ok:
                tried.append(f"{tag} 第一步 HTTP {r1.status}")
                continue
            conf = parse_send_confirm(r1.text)
        except (RuntimeError, ParseError) as e:
            # 診斷（不含 token）：例外訊息前 60 字＋回應長度＋是否有確認頁表單／確認鈕
            diag = ""
            if r1 is not None:
                t = getattr(r1, "text", "") or ""
                diag = (f"｜len={len(t)} form={'troopSendForm' in t} btn={'confirmSendTroops' in t}"
                        f" err={'error' in t.lower()}")
            tried.append(f"{tag} 第一步失敗：{type(e).__name__}：{str(e)[:60]}{diag}")
            continue
        same, why = confirm_matches(conf, units, (cand.x, cand.y), did)
        if not same:
            tried.append(f"{tag} 確認頁核對不符：{why}")
            continue
        good, n, msg = confirm_ok(conf, scope, margin=margin, send_delay_s=send_delay_s)
        if not good or (decision.full and n < full_n):
            tried.append(f"{tag} {msg if not good else f'只撐過 {n}/{full_n} 波，換下一個'}")
            continue
        if m == "dry":
            return res("dry", f"確認頁核對通過，未送出：{tag} {msg}")
        # ③ 第三步：送出（不重試）→ 以重讀概況為準
        post_err = ""
        try:
            r3 = gw.request("POST", SEND_PATH, headers=_FORM_HEADERS, data=_step3_body(conf))
            if not r3.ok:
                post_err = f"送出回應 HTTP {r3.status}"
        except RuntimeError as e:
            post_err = f"送出時出錯（可能已送達）：{e}"
        try:
            ov = parse_overview(gw.get(OVERVIEW_PATH, raw=True))
        except (RuntimeError, ParseError) as e:
            return res("failed", f"{tag} 已嘗試送出，但重讀概況失敗，結果不明，請人工確認（不重試）：{type(e).__name__}"
                       + (f"；{post_err}" if post_err else ""))
        sent = [mv for mv in ov.movements if "outRaid" in mv.kinds and mv.link_did == mid]
        if sent:
            back = (conf.epoch - conf.trip_s) + 2 * conf.trip_s
            return res("ok", f"已送出 {tag} map {mid}，約 epoch {back} 返回（撐過 {n}/{full_n} 波）", True)
        return res("failed", f"{tag} 送出後概況沒看到出擊，請人工確認（不重試）" + (f"；{post_err}" if post_err else ""), False)

    return res("skipped", "候選全部未通過，沒有派兵：" + (_short(tried[:4], 200) if tried else "沒有可試的候選"))
