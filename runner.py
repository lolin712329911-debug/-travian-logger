#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共用主流程：讀 Config、決策（build_order 或舊流程）、送出升級、驗證、記錄到 Sheet。

auto_build.py（純 requests）和 travian_ci_run.py（Playwright）只負責「怎麼抓頁面、怎麼送出網址」，
把這三個小函式傳進 run_build_cycle()：

  get(path)      -> str   抓一個頁面的 HTML（例如 "dorf2.php"、"build.php?id=26"）
  get_dorf1()    -> str   抓 dorf1 的 HTML（Playwright 版要在這裡處理 title 被 JS 清空的備援）
  submit(url)    -> None  送出升級（url 已通過白名單，例如 "/dorf2.php?id=31&gid=11&action=build&checksum=76c9cd"）

環境變數：
  GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID   選填（有的話讀 Config、寫 Actions）
  QUIET_UTC   不運作的 UTC 小時區間 "起,迄"，預設 "17,23"（台灣 01:00~07:00）

Sheet 的「Config」分頁：A 欄名稱、B 欄值，例如
  enabled       TRUE       <- 改成 FALSE 就是緊急停止開關
  target_level  2
  queue_slots   2          <- Plus 到期後改 1
  max_builds    2          <- 每輪最多送出幾個升級
  target_building_level 0  <- 舊流程：倉庫/糧倉升到幾級（0 = 停用）
  build_order   res:2,15:3 <- 建城順序（有填就用這個，舊流程的兩個目標等級不再使用）
"""
import os
import random
import time
from datetime import datetime, timezone

import travian_agent as T


# ---------------- Google Sheets ----------------
def _has_sheet() -> bool:
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and os.getenv("GOOGLE_SHEET_ID"))


def _sheet():
    from sheets_writer import _get_credentials
    return _get_credentials().open_by_key(os.environ["GOOGLE_SHEET_ID"])


def load_config() -> dict:
    """讀 Sheet 的 Config 分頁；沒有這個分頁就用預設值（不是錯誤）。
    真正的異常（憑證、網路等）會往外拋，讓呼叫端中止本輪。"""
    from gspread.exceptions import WorksheetNotFound

    cfg = {"enabled": True, "target_level": 2, "queue_slots": 2, "max_builds": 2,
           "target_building_level": T.TARGET_BUILDING_LEVEL, "build_order": ""}
    if not _has_sheet():
        return cfg
    try:
        rows = _sheet().worksheet("Config").get_all_values()
    except WorksheetNotFound:
        print("Sheet 裡沒有 Config 分頁，使用預設值")
        return cfg
    for row in rows:
        if len(row) < 2:
            continue
        k, v = row[0].strip().lower(), row[1].strip()
        if k == "enabled":
            cfg[k] = v.lower() not in ("false", "0", "no", "off", "否", "停")
        elif k == "build_order":
            cfg[k] = v
        elif k in ("target_level", "queue_slots", "max_builds", "target_building_level") and v.isdigit():
            cfg[k] = int(v)
    return cfg


def log_action(row: list):
    if not _has_sheet():
        return
    try:
        sh = _sheet()
        try:
            ws = sh.worksheet("Actions")
        except Exception:
            ws = sh.add_worksheet("Actions", 1000, 8)
            ws.append_row(["時間(UTC)", "動作", "slot", "gid", "目前等級", "成本", "模式", "結果"])
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"寫入 Actions 分頁失敗（不影響升級）: {e!r}")


# ---------------- 開頭的共用檢查 ----------------
def in_quiet_hours() -> bool:
    q0, q1 = (int(x) for x in os.getenv("QUIET_UTC", "17,23").split(","))
    return q0 <= datetime.now(timezone.utc).hour < q1


def get_cfg():
    """回傳 (cfg, 結束碼)。cfg 是 None 代表本輪不動作，結束碼就是該回傳的值。"""
    try:
        cfg = load_config()
    except Exception as e:
        print(f"讀取 Config 失敗，為安全起見本輪不動作: {e!r}")
        return None, 1
    if not cfg["enabled"]:
        print("Config 的 enabled 是 FALSE，本輪不動作")
        return None, 0
    return cfg, 0


# ---------------- 舊流程：資源田 + 倉庫/糧倉 ----------------
def _legacy_candidates(get, target_level: int, touched: set) -> list:
    """倉庫/糧倉裡等級 < target_level 的候選 Field（成本已填好）。target_level <= 0 = 停用，
    不多打任何請求。每個候選要多抓一次 build.php，所以只在真的啟用時才呼叫。"""
    if target_level <= 0:
        return []
    out = []
    for gid, (aid, level) in T.parse_dorf2(get("dorf2.php")).items():
        if level >= target_level or aid in touched:
            continue
        cost, secs = T.parse_building_cost(get(f"build.php?id={aid}"))
        if not cost:
            print(f"警告：{T.BUILDING_GIDS.get(gid, gid)} (aid={aid}) 的 build.php 解析不到成本，跳過")
            continue
        out.append(T.Field(aid=aid, gid=gid, level=level, cost=cost, secs=secs, building=False))
    return out


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%F %T")


# ---------------- 主迴圈 ----------------
def run_build_cycle(cfg: dict, *, get, get_dorf1, submit, dry: bool,
                    first_dorf1: str = None, sleep=time.sleep) -> int:
    """跑一輪：最多送出 cfg["max_builds"] 個升級。回傳結束碼（0 正常、1 需要人看）。"""
    T.TARGET_LEVEL, T.QUEUE_SLOTS = cfg["target_level"], cfg["queue_slots"]

    order = []
    if cfg.get("build_order"):
        try:
            order = T.parse_build_order(cfg["build_order"])
        except ValueError as e:
            T.notify(f"Config 的 build_order 格式錯誤，本輪不動作：{e}")
            return 1
        print(f"使用建城順序（{len(order)} 個目標）：{cfg['build_order']}")

    mode = "DRY" if dry else "LIVE"
    touched = set()

    for i in range(cfg["max_builds"]):
        d1 = first_dorf1 if (i == 0 and first_dorf1 is not None) else get_dorf1()
        if 'id="stockBar"' not in d1:
            T.notify("抓到的不是村莊頁：session / Cookie 可能已失效，請重新複製 Cookie 更新 Secret")
            return 1
        st = T.parse_dorf1(d1)
        for f in st.fields:                       # 本輪已送出的田，不要重複選
            if f.aid in touched:
                f.building = True
        if dry and touched:                       # 乾跑沒真的送出，佇列不會變：
            st.queue = st.queue + [1800] * len(touched)   # 把本輪「已送出」的也算進佇列長度

        if order:                                 # 有設 build_order：照順序建城
            action = T.plan_with_order(st, order, get, touched)
        else:                                     # 沒設：資源田 + 倉庫/糧倉
            st.fields += _legacy_candidates(get, cfg["target_building_level"], touched)
            action = T.plan(st)

        print(f"[{mode}] 決策: {action[0]}  佇列={st.queue}  存量={st.stock}  來襲={st.attacks}")
        if st.attacks:
            T.notify(f"偵測到來襲 {st.attacks} 波！請手動處理")   # 目前只寫 log，見 README
        if action[0] == "need_storage":
            T.notify(f"slot {action[1].aid} 的成本超過倉庫容量 {st.cap}，請先升倉庫/糧倉")
            break
        if action[0] == "blocked":
            T.notify(f"建城計畫卡住了：{action[1]}")
            break
        if action[0] == "no_slot":
            T.notify(f"要蓋新建築（gid {action[1]}）但村莊沒有空地了")
            break
        if action[0] != "build":
            break

        f = action[1]
        cost = "/".join(map(str, f.cost))
        url = f.url or T.find_upgrade_url(get(f"build.php?id={f.aid}"))
        if not url:
            print(f"slot {f.aid}: 找不到綠色擴建按鈕（資源不足、佇列滿或前置條件未達）")
            log_action([_now(), "升級", f.aid, f.gid, f.level, cost, mode, "找不到按鈕"])
            break
        touched.add(f.aid)

        if dry:
            print(f"[DRY] slot {f.aid} (gid {f.gid}) L{f.level}->L{f.level + 1}，會送出: {url}")
            log_action([_now(), "升級", f.aid, f.gid, f.level, cost, mode, "未送出"])
            continue

        sleep(random.uniform(2, 6))
        submit(url)
        sleep(random.uniform(2, 5))
        after = T.parse_dorf1(get("dorf1.php"))
        ok = len(after.queue) > len(st.queue) or sum(after.stock) < sum(st.stock) - 0.5 * sum(f.cost)
        log_action([_now(), "升級", f.aid, f.gid, f.level, cost, mode, "成功" if ok else "沒看到變化"])
        if not ok:
            T.notify(f"送出 slot {f.aid} 的升級後沒看到資源被扣或佇列增加，已停止")
            return 1
        T.notify(f"已升級 slot {f.aid} (gid {f.gid}) L{f.level}->L{f.level + 1}，成本 {cost}")
        sleep(random.uniform(3, 8))
    return 0
