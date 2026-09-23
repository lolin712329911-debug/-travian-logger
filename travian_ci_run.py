#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 用的「Playwright 版」自動升級資源田（v2：不需要本機執行）。

跟 v1 的差異：不再需要你在本機跑 seed_login.py 產生 storage_state.json。
改成第一次執行時，直接讀 TRAVIAN_SEED_COOKIE 這個 Secret（內容就是你從
瀏覽器開發者工具複製的那串 "a=b; c=d; JWT=xxx" cookie header，跟你原本
設定 TRAVIAN_COOKIE 的方式完全一樣），在無頭瀏覽器裡把它還原成 session。

之後每一輪執行完，會把當下瀏覽器的完整 cookies/localStorage 狀態存進
GitHub Actions 的 cache，下一輪優先用 cache 裡的（可能已被伺服器續期過），
TRAVIAN_SEED_COOKIE 只在 cache 沒中的時候當救援用，正常情況下只有「第一次
執行」那一輪會真的用到它。

環境變數：
  TRAVIAN_BASE_URL                              必填（伺服器網址）
  TRAVIAN_STATE_PATH                            選填，預設 travian_state.json
  TRAVIAN_SEED_COOKIE                           選填，cache miss 時的救援種子
                                                 （從瀏覽器複製的原始 Cookie 字串）
  GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID  選填（沿用 auto_build.py）
  TG_TOKEN / TG_CHAT_ID                         選填（Telegram 通知）
  DRY_RUN        預設 1：只印出「會怎麼做」，不真的點擊
  QUIET_UTC      不運作的 UTC 小時區間 "起,迄"，預設 "17,23"（台灣 01:00~07:00）
"""
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import travian_agent as T
import auto_build as AB  # 重用它的 load_config() / log_action() / find_upgrade_url()

BASE = os.getenv("TRAVIAN_BASE_URL", "").rstrip("/")
STATE_PATH = Path(os.getenv("TRAVIAN_STATE_PATH", "travian_state.json"))


def parse_cookie_header(header: str, url: str) -> list:
    """把 'name1=value1; name2=value2' 這種原始 Cookie header 字串，
    轉成 Playwright context.add_cookies() 吃的格式。
    只給 url，Playwright 會自動從 url 推導 domain/path，不需要你額外提供。"""
    cookies = []
    for part in header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies.append({"name": name.strip(), "value": value.strip(), "url": url})
    return cookies


def main() -> int:
    q0, q1 = (int(x) for x in os.getenv("QUIET_UTC", "17,23").split(","))
    if q0 <= datetime.now(timezone.utc).hour < q1:
        print("安靜時段，本輪不動作")
        return 0
    if not BASE:
        print("缺少 TRAVIAN_BASE_URL")
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("缺少 playwright，請確認 requirements.txt 與 workflow 有安裝")
        return 1

    try:
        cfg = AB.load_config()
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
    exit_code = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        if STATE_PATH.exists():
            print(f"找到既有 session 狀態：{STATE_PATH}（來自 actions/cache）")
            context = browser.new_context(storage_state=str(STATE_PATH))
        else:
            seed_cookie = os.getenv("TRAVIAN_SEED_COOKIE", "")
            if not seed_cookie:
                print("找不到 cache，也沒有 TRAVIAN_SEED_COOKIE 可用救援。")
                print("請從瀏覽器複製登入後的 Cookie header，存進這個 Secret。")
                browser.close()
                return 1
            print("cache 沒中，改用 TRAVIAN_SEED_COOKIE 這個救援種子建立 session")
            context = browser.new_context()
            context.add_cookies(parse_cookie_header(seed_cookie, BASE))

        page = context.new_page()

        def get_html(path: str) -> str:
            page.goto(f"{BASE}/{path.lstrip('/')}", wait_until="networkidle")
            return page.content()

        d1 = get_html("dorf1.php")
        if 'id="stockBar"' not in d1:
            T.notify("抓到的不是村莊頁：session 可能已失效，請重新複製 Cookie 更新 TRAVIAN_SEED_COOKIE")
            browser.close()
            return 1

        for i in range(cfg["max_builds"]):
            html = get_html("dorf1.php") if i else d1
            st = T.parse_dorf1(html)
            for f in st.fields:
                if f.aid in touched:
                    f.building = True

            action = T.plan(st)
            print(f"[{mode}] 決策: {action[0]}  佇列={st.queue}  存量={st.stock}  來襲={st.attacks}")
            if st.attacks:
                T.notify(f"偵測到來襲 {st.attacks} 波！請手動處理")
            if action[0] == "need_storage":
                T.notify(f"slot {action[1].aid} 的成本超過倉庫容量 {st.cap}，請先升倉庫/糧倉")
                break
            if action[0] != "build":
                break

            f = action[1]
            cost = "/".join(map(str, f.cost))
            build_html = get_html(f"build.php?id={f.aid}")
            url = AB.find_upgrade_url(build_html)
            if not url:
                print(f"slot {f.aid}: 找不到綠色擴建按鈕（資源不足、佇列滿或前置條件未達）")
                AB.log_action([datetime.now(timezone.utc).strftime("%F %T"),
                                "升級", f.aid, f.gid, f.level, cost, mode, "找不到按鈕"])
                break
            touched.add(f.aid)

            if dry:
                print(f"[DRY] slot {f.aid} (gid {f.gid}) L{f.level}->L{f.level + 1}，會前往: {url}")
                AB.log_action([datetime.now(timezone.utc).strftime("%F %T"),
                                "升級", f.aid, f.gid, f.level, cost, mode, "未送出"])
                continue

            time.sleep(random.uniform(2, 6))
            page.goto(f"{BASE}/{url.lstrip('/')}" if not url.startswith("http") else url,
                       wait_until="networkidle")
            time.sleep(random.uniform(2, 5))
            after = T.parse_dorf1(get_html("dorf1.php"))
            ok = len(after.queue) > len(st.queue) or sum(after.stock) < sum(st.stock) - 0.5 * sum(f.cost)
            AB.log_action([datetime.now(timezone.utc).strftime("%F %T"),
                            "升級", f.aid, f.gid, f.level, cost, mode,
                            "成功" if ok else "沒看到變化"])
            if not ok:
                T.notify(f"送出 slot {f.aid} 的升級後沒看到資源被扣或佇列增加，已停止")
                exit_code = 1
                break
            T.notify(f"已升級 slot {f.aid} (gid {f.gid}) L{f.level}->L{f.level + 1}，成本 {cost}")
            time.sleep(random.uniform(3, 8))

        # 不管這輪做了什麼，只要一開始 session 是活的，就把最新狀態存回去，
        # 讓下一輪 actions/cache 可以接續使用（之後就不再需要 TRAVIAN_SEED_COOKIE 了）
        context.storage_state(path=str(STATE_PATH))
        browser.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
