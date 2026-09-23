#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 用的「Playwright 版」自動升級資源田。

取代原本 auto_build.py 的純 requests.Session() + 靜態 TRAVIAN_COOKIE 做法。
差異只有一個，但很關鍵：這支腳本用真的無頭瀏覽器載入頁面，讓 Travian
前端任何會跑的 JS（包含可能的 session refresh/keep-alive 邏輯）真的被
執行到，理論上可以讓登入狀態撐得跟你自己用瀏覽器玩差不多久，而不是
卡在固定的 JWT exp 時間就死。

沿用 auto_build.py 既有的 travian_agent.parse_dorf1() / plan() 決策邏輯
與 sheets_writer 的紀錄邏輯，只把「怎麼發送請求」換成「怎麼操作瀏覽器」。

環境變數：
  TRAVIAN_BASE_URL                              必填（伺服器網址）
  TRAVIAN_STATE_PATH                            選填，預設 travian_state.json
  TRAVIAN_SEED_STATE_B64                        選填，cache miss 時的救援種子
                                                 （seed_login.py 產出的 base64）
  GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID  選填（沿用 auto_build.py）
  TG_TOKEN / TG_CHAT_ID                         選填（Telegram 通知）
  DRY_RUN        預設 1：只印出「會怎麼做」，不真的點擊
  QUIET_UTC      不運作的 UTC 小時區間 "起,迄"，預設 "17,23"（台灣 01:00~07:00）
"""
import base64
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 直接沿用既有邏輯，不重寫一份
import travian_agent as T
import auto_build as AB  # 重用它的 load_config() / log_action() / find_upgrade_url()

BASE = os.getenv("TRAVIAN_BASE_URL", "").rstrip("/")
STATE_PATH = Path(os.getenv("TRAVIAN_STATE_PATH", "travian_state.json"))


def ensure_state_file() -> bool:
    """cache 沒還原到檔案時，用 Secret 裡的種子救援一次。回傳是否有可用的 state 檔。"""
    if STATE_PATH.exists():
        print(f"找到既有 session 狀態：{STATE_PATH}（來自 actions/cache）")
        return True

    seed_b64 = os.getenv("TRAVIAN_SEED_STATE_B64", "")
    if not seed_b64:
        print("找不到 session 狀態檔，也沒有 TRAVIAN_SEED_STATE_B64 可用救援。")
        print("請先在本機跑 seed_login.py 產生種子，存進這個 Secret。")
        return False

    STATE_PATH.write_bytes(base64.b64decode(seed_b64))
    print(f"cache 沒中，已用 TRAVIAN_SEED_STATE_B64 救援寫出 {STATE_PATH}")
    return True


def main() -> int:
    q0, q1 = (int(x) for x in os.getenv("QUIET_UTC", "17,23").split(","))
    if q0 <= datetime.now(timezone.utc).hour < q1:
        print("安靜時段，本輪不動作")
        return 0
    if not BASE:
        print("缺少 TRAVIAN_BASE_URL")
        return 1
    if not ensure_state_file():
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
        context = browser.new_context(storage_state=str(STATE_PATH))
        page = context.new_page()

        def get_html(path: str) -> str:
            page.goto(f"{BASE}/{path.lstrip('/')}", wait_until="networkidle")
            return page.content()

        d1 = get_html("dorf1.php")
        if 'id="stockBar"' not in d1:
            T.notify("抓到的不是村莊頁：session 可能已失效，請重新跑 seed_login.py")
            # session 死了就不要把壞掉的 state 存回 cache，直接結束
            browser.close()
            return 1

        for _ in range(cfg["max_builds"]):
            html = get_html("dorf1.php") if _ else d1
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
            # 用真的瀏覽器導航（等同「點擊」），讓頁面 JS 正常執行
            page.goto(f"{BASE}/{url.lstrip('/')}" if not url.startswith("http") else url,
                       wait_until="networkidle")
            time.sleep(random.uniform(2, 5))
            after_html = get_html("dorf1.php")
            after = T.parse_dorf1(after_html)
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

        # 不管這輪做了什麼，只要 session 一開始是活的，就把最新狀態（可能已被
        # 伺服器續期）存回去，讓下一輪 actions/cache 可以接續使用
        context.storage_state(path=str(STATE_PATH))
        browser.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
