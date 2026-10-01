#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【舊版】本機 Playwright 持久登入 + 迴圈（原 travian_agent.run()）。
Actions 不使用它（實際入口是 travian_ci_run.py + runner.py）；留在這裡只當本機手動登入的備用工具。
確認沒人需要後可以整個刪除。

用法（要在倉庫根目錄執行，才找得到 travian_agent）：
    PYTHONPATH=. python tools/legacy/agent_run.py
安裝: pip install playwright beautifulsoup4 && playwright install chromium
"""
import random
import time
from datetime import datetime

from travian_agent import notify, parse_dorf1, plan

# ---------------- 設定（原 travian_agent.py）----------------
BASE = "https://ts11.x1.international.travian.com"
DRY_RUN = True            # 確認決策正確後才改 False
QUIET_HOURS = (2, 7)      # 這段本機時間不運作
UPGRADE_BUTTON = "button.textButtonV1.green.build"   # ← 未驗證，需用 build.php 頁面確認
PROFILE_DIR = "./travian_profile"


# ---------------- 執行 ----------------
def run():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE_DIR, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"{BASE}/dorf1.php")
        input("第一次請在瀏覽器手動登入，看到資源田畫面後按 Enter ... ")

        last_attacks = 0
        while True:
            if QUIET_HOURS[0] <= datetime.now().hour < QUIET_HOURS[1]:   # 注意：這是本機時間
                time.sleep(random.uniform(900, 1500))
                continue

            page.goto(f"{BASE}/dorf1.php")
            page.wait_for_load_state("networkidle")
            if page.locator("#stockBar").count() == 0:                    # 被登出/驗證碼/改版
                notify("找不到 #stockBar：可能被登出或出現驗證碼，已停止")
                return

            html = page.content()
            st = parse_dorf1(html)
            if not any(f.cost for f in st.fields):                        # title 被前端 JS 拿掉時的備案
                html = ctx.request.get(f"{BASE}/dorf1.php").text()
                st = parse_dorf1(html)

            if st.attacks and st.attacks != last_attacks:
                notify(f"偵測到來襲 {st.attacks} 波！請手動處理")
            last_attacks = st.attacks

            action = plan(st)
            sleep_s = 600
            if action[0] == "build":
                f = action[1]
                notify(f"{'[DRY] ' if DRY_RUN else ''}升級 slot {f.aid} (gid {f.gid}) L{f.level}->L{f.level + 1} 成本 {f.cost}")
                if not DRY_RUN:
                    page.goto(f"{BASE}/build.php?id={f.aid}")
                    page.locator(UPGRADE_BUTTON).first.click()
                    page.wait_for_load_state("networkidle")
                sleep_s = random.uniform(20, 60)
            elif action[0] in ("wait_res", "wait_queue"):
                sleep_s = action[1]
            elif action[0] == "need_storage":
                notify(f"slot {action[1].aid} 的成本超過倉庫容量 {st.cap}，請先升倉庫/糧倉")
                return
            elif action[0] == "done":
                notify("資源田都到目標等級了")
                return

            # 新手保護期間不需要密集查來襲；結束後改成最多 10 分鐘一輪
            cap = 1800 if (st.protection_s or 0) > 0 else 600
            sleep_s = min(max(sleep_s, 60), cap) * random.uniform(0.9, 1.3)
            print(f"下一輪約 {int(sleep_s)} 秒後")
            time.sleep(sleep_s)


if __name__ == "__main__":
    run()
