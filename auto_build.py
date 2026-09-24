#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 用的「純 HTTP 版」自動升級資源田（不需要瀏覽器）。

流程：讀 Sheet 的 Config -> 抓 dorf1 -> travian_agent.plan() 決策
      -> 抓 build.php?id=N，找出綠色「擴建」按鈕的網址 -> 送出 -> 驗證 -> 記錄到 Sheet 的 Actions 分頁

環境變數：
  TRAVIAN_BASE_URL, TRAVIAN_COOKIE              必填
  GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID   選填（有的話讀 Config、寫 Actions）
  DRY_RUN     預設 1：只印出「會送出什麼」，不真的送出
  QUIET_UTC   不運作的 UTC 小時區間 "起,迄"，預設 "17,23"（台灣 01:00~07:00）
  TG_TOKEN / TG_CHAT_ID   選填，Telegram 通知（也可只靠 Actions 失敗時的 Email）

Sheet 的「Config」分頁：A 欄名稱、B 欄值，例如
  enabled       TRUE       <- 改成 FALSE 就是緊急停止開關
  target_level  2
  queue_slots   2          <- Plus 到期後改 1
  max_builds    2          <- 每輪最多送出幾個升級
"""
import html as _html
import os
import random
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

import travian_agent as T

BASE = os.getenv("TRAVIAN_BASE_URL", "").rstrip("/")
COOKIE = os.getenv("TRAVIAN_COOKIE", "")
UA = os.getenv("TRAVIAN_UA", "Mozilla/5.0 (compatible; PersonalVillageLogger/1.0)")
_session = requests.Session()


def get(path: str) -> str:
    r = _session.get(f"{BASE}/{path.lstrip('/')}",
                     headers={"User-Agent": UA, "Cookie": COOKIE}, timeout=20)
    r.raise_for_status()
    return r.text


# ---------------- Google Sheets ----------------
def _has_sheet() -> bool:
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and os.getenv("GOOGLE_SHEET_ID"))


def _sheet():
    from sheets_writer import _get_credentials
    return _get_credentials().open_by_key(os.environ["GOOGLE_SHEET_ID"])


def load_config() -> dict:
    """讀 Sheet 的 Config 分頁；沒有這個分頁就用預設值（不是錯誤）。
    只有「讀得到 Sheet 但格式有問題」以外的真正異常（憑證、網路等）
    才會往外拋，讓呼叫端中止本輪。"""
    from gspread.exceptions import WorksheetNotFound

    cfg = {"enabled": True, "target_level": 2, "queue_slots": 2, "max_builds": 2,
           "target_building_level": T.TARGET_BUILDING_LEVEL}
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


# ---------------- 找升級按鈕 ----------------
def find_upgrade_url(build_page_html: str):
    """只認綠色 build 按鈕；紫色的「建構25%更快」(看廣告加速) 一律不碰。"""
    soup = BeautifulSoup(build_page_html, "html.parser")
    for b in soup.select("button.green.build"):
        m = re.search(r"location\.href\s*=\s*'([^']+)'", b.get("onclick", ""))
        if m and "action=build" in m.group(1):
            return _html.unescape(m.group(1))
    return None


# ---------------- 村莊中心建築（倉庫/糧倉） ----------------
def get_building_candidates(target_level: int, touched: set) -> list:
    """回傳倉庫/糧倉裡等級 < target_level 的候選 Field（成本已填好）。
    target_level <= 0 時視為停用，直接回傳空清單，不多打任何請求。
    每個候選都要多抓一次 build.php（跟資源田不同，成本沒辦法從 dorf2 一次拿到），
    所以只在真的啟用時才呼叫，避免每輪平白多打好幾個請求。"""
    if target_level <= 0:
        return []
    slots = T.parse_dorf2(get("dorf2.php"))
    out = []
    for gid, (aid, level) in slots.items():
        if level >= target_level or aid in touched:
            continue
        cost, secs = T.parse_building_cost(get(f"build.php?id={aid}"))
        if not cost:
            print(f"警告：{T.BUILDING_GIDS.get(gid, gid)} (aid={aid}) 的 build.php 解析不到成本，跳過")
            continue
        out.append(T.Field(aid=aid, gid=gid, level=level, cost=cost, secs=secs, building=False))
    return out


# ---------------- 主流程 ----------------
def main() -> int:
    q0, q1 = (int(x) for x in os.getenv("QUIET_UTC", "17,23").split(","))
    if q0 <= datetime.now(timezone.utc).hour < q1:
        print("安靜時段，本輪不動作")
        return 0
    if not BASE or not COOKIE:
        print("缺少 TRAVIAN_BASE_URL / TRAVIAN_COOKIE")
        return 1

    try:
        cfg = load_config()
    except Exception as e:
        print(f"讀取 Config 失敗，為安全起見本輪不動作: {e!r}")
        return 1
    if not cfg["enabled"]:
        print("Config 的 enabled 是 FALSE，本輪不動作")
        return 0

    T.TARGET_LEVEL, T.QUEUE_SLOTS = cfg["target_level"], cfg["queue_slots"]
    dry = os.getenv("DRY_RUN", "1") != "0"
    mode = "DRY" if dry else "LIVE"
    touched = set()

    for _ in range(cfg["max_builds"]):
        d1 = get("dorf1.php")
        if 'id="stockBar"' not in d1:
            T.notify("抓到的不是村莊頁：Cookie 可能已過期，請重新複製並更新 Secret")
            return 1
        st = T.parse_dorf1(d1)
        for f in st.fields:                     # 本輪已送出的田，不要重複選
            if f.aid in touched:
                f.building = True

        st.fields += get_building_candidates(cfg["target_building_level"], touched)

        action = T.plan(st)
        print(f"[{mode}] 決策: {action[0]}  佇列={st.queue}  存量={st.stock}  來襲={st.attacks}")
        if st.attacks:
            T.notify(f"偵測到來襲 {st.attacks} 波！請手動處理")
        if action[0] == "need_storage":
            T.notify(f"slot {action[1].aid} 的成本超過倉庫容量 {st.cap}，請先升倉庫/糧倉")
            return 0
        if action[0] != "build":
            break

        f = action[1]
        cost = "/".join(map(str, f.cost))
        url = find_upgrade_url(get(f"build.php?id={f.aid}"))
        if not url:
            print(f"slot {f.aid}: 找不到綠色擴建按鈕（資源不足、佇列滿或前置條件未達）")
            log_action([datetime.now(timezone.utc).strftime("%F %T"), "升級", f.aid, f.gid, f.level, cost, mode, "找不到按鈕"])
            break
        touched.add(f.aid)

        if dry:
            print(f"[DRY] slot {f.aid} (gid {f.gid}) L{f.level}->L{f.level + 1}，會送出: {url}")
            log_action([datetime.now(timezone.utc).strftime("%F %T"), "升級", f.aid, f.gid, f.level, cost, mode, "未送出"])
            continue

        time.sleep(random.uniform(2, 6))
        get(url)
        time.sleep(random.uniform(2, 5))
        after = T.parse_dorf1(get("dorf1.php"))
        ok = len(after.queue) > len(st.queue) or sum(after.stock) < sum(st.stock) - 0.5 * sum(f.cost)
        log_action([datetime.now(timezone.utc).strftime("%F %T"), "升級", f.aid, f.gid, f.level, cost, mode, "成功" if ok else "沒看到變化"])
        if not ok:
            T.notify(f"送出 slot {f.aid} 的升級後沒看到資源被扣或佇列增加，已停止")
            return 1
        T.notify(f"已升級 slot {f.aid} (gid {f.gid}) L{f.level}->L{f.level + 1}，成本 {cost}")
        time.sleep(random.uniform(3, 8))
    return 0


if __name__ == "__main__":
    sys.exit(main())
