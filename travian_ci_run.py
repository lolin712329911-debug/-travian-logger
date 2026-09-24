#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 用的「Playwright 版」自動升級資源田（v2.1：修正 title 被前端 JS
清空導致成本解析失敗的問題）。

跟 v2 的差異只有一處：get_html() 現在會在「這一頁抓到的所有田成本都是空的」
時，改用 context.request.get() 發一個不經過瀏覽器渲染、不執行任何 JS 的純
HTTP 請求去拿同一頁的原始 HTML（沿用同一組 session/cookie）。這正是原始
travian_agent.py 的 run() 函式裡本來就寫好的備案，只是先前整合進這支 CI
腳本時漏接了——診斷結果證實：Travian 的某個 JS tooltip 套件會在頁面載入
後把 <a> 標籤的 title 屬性內容讀走、轉成自訂 tooltip，然後把原生 title
屬性清空，導致 Playwright 等頁面完整渲染完才讀到的 title 永遠是空字串；
純 HTTP 請求因為不執行任何 JS，能拿到伺服器端原始吐出來、title 還完整
保留的 HTML。

環境變數：跟 v2 完全相同，見 SETUP.md
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
    轉成 Playwright context.add_cookies() 吃的格式。"""
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

        def get_html(path: str, need_cost: bool = False) -> str:
            """load 這一頁；need_cost=True 時，若解析出來所有田的成本
            都是空的（title 被前端 JS 拿掉），改發一次純 HTTP 請求
            （不執行 JS），沿用同一組 session 取得未被 JS 動過的原始 HTML。"""
            url = f"{BASE}/{path.lstrip('/')}"
            page.goto(url, wait_until="networkidle")
            html = page.content()

            if need_cost and 'id="stockBar"' in html:
                probe = T.parse_dorf1(html)
                if probe.fields and not any(f.cost for f in probe.fields):
                    print(f"  [備援] {path} 的 title 被前端 JS 清空，"
                          f"改用純 HTTP 請求重抓一次（不執行 JS）")
                    resp = context.request.get(url)
                    html = resp.text()
            return html

        def get_building_candidates(target_level: int) -> list:
            """跟 auto_build.py 的同名函式邏輯一致，只是改用這支腳本的
            get_html()（走瀏覽器/session）而不是 requests。target_level<=0
            時停用，不多打任何請求。"""
            if target_level <= 0:
                return []
            slots = T.parse_dorf2(get_html("dorf2.php"))
            out = []
            for gid, (aid, level) in slots.items():
                if level >= target_level or aid in touched:
                    continue
                cost, secs = T.parse_building_cost(get_html(f"build.php?id={aid}"))
                if not cost:
                    print(f"警告：{T.BUILDING_GIDS.get(gid, gid)} (aid={aid}) 的 build.php 解析不到成本，跳過")
                    continue
                out.append(T.Field(aid=aid, gid=gid, level=level, cost=cost, secs=secs, building=False))
            return out

        d1 = get_html("dorf1.php", need_cost=True)
        if 'id="stockBar"' not in d1:
            T.notify("抓到的不是村莊頁：session 可能已失效，請重新複製 Cookie 更新 TRAVIAN_SEED_COOKIE")
            browser.close()
            return 1

        for i in range(cfg["max_builds"]):
            html = get_html("dorf1.php", need_cost=True) if i else d1
            st = T.parse_dorf1(html)
            for f in st.fields:
                if f.aid in touched:
                    f.building = True

            st.fields += get_building_candidates(cfg["target_building_level"])

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
        # 讓下一輪 actions/cache 可以接續使用
        context.storage_state(path=str(STATE_PATH))
        browser.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
