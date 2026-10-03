#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 用的「Playwright 版」自動升級資源田（v2.2：安靜時段改為 keep-alive）。

v2.1：修正 title 被前端 JS 清空導致成本解析失敗的問題。get_html() 會在「這一頁抓到的
所有田成本都是空的」時，改用 context.request.get() 發一個不經過瀏覽器渲染、不執行任何
JS 的純 HTTP 請求去拿同一頁的原始 HTML（沿用同一組 session/cookie）。Travian 的某個 JS
tooltip 套件會在頁面載入後把 <a> 標籤的 title 讀走再清空，純 HTTP 請求拿得到伺服器端
原始吐出、title 還完整的 HTML。

v2.2：安靜時段（QUIET_UTC）不再直接離開。原本整段時間完全沒有請求，session 會因為閒置
太久被伺服器端過期（實測：跳過 UTC 17~23 之後 cache 與種子 Cookie 都失效）。現在安靜時段
仍然會載入一次 dorf1 確認 session 活著、把最新狀態存回 travian_state.json，但不建造、
不寫 Sheet。session 真的失效時照舊走 disable()（sheets_writer）。

這支只負責「Playwright 的 session（cache / 種子 Cookie）、怎麼抓頁面、怎麼送出網址」；
決策、build_order、送出與驗證、Config / Actions 分頁都在 runner.py。

環境變數：跟 v2 完全相同，見 SETUP.md
"""
import os
import sys
from pathlib import Path

import runner as R
import travian_pages as P
from notify import notify
from sheets_writer import disable

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
    quiet = R.in_quiet_hours()      # 安靜時段：只做 keep-alive，不建造（見下方）
    if not BASE:
        print("缺少 TRAVIAN_BASE_URL")
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("缺少 playwright，請確認 requirements.txt 與 workflow 有安裝")
        return 1

    cfg, code = R.get_cfg()
    if cfg is None:
        return code
    dry = os.getenv("DRY_RUN", "1") != "0"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        seed_cookie = os.getenv("TRAVIAN_SEED_COOKIE", "")

        def new_context_from_seed():
            ctx = browser.new_context()
            ctx.add_cookies(parse_cookie_header(seed_cookie, BASE))
            return ctx

        used_cache = STATE_PATH.exists()
        if used_cache:
            print(f"找到既有 session 狀態：{STATE_PATH}（來自 actions/cache）")
            context = browser.new_context(storage_state=str(STATE_PATH))
        else:
            if not seed_cookie:
                print("找不到 cache，也沒有 TRAVIAN_SEED_COOKIE 可用救援。")
                print("請從瀏覽器複製登入後的 Cookie header，存進這個 Secret。")
                browser.close()
                return 1
            print("cache 沒中，改用 TRAVIAN_SEED_COOKIE 這個救援種子建立 session")
            context = new_context_from_seed()

        page = context.new_page()

        def get_html(path: str, need_cost: bool = False) -> str:
            """load 這一頁；need_cost=True 時，若解析出來所有田的成本
            都是空的（title 被前端 JS 拿掉），改發一次純 HTTP 請求
            （不執行 JS），沿用同一組 session 取得未被 JS 動過的原始 HTML。"""
            url = f"{BASE}/{path.lstrip('/')}"
            page.goto(url, wait_until="networkidle")
            html = page.content()

            if need_cost and 'id="stockBar"' in html:
                probe = P.parse_dorf1(html)
                if probe.fields and not any(f.cost for f in probe.fields):
                    print(f"  [備援] {path} 的 title 被前端 JS 清空，"
                          f"改用純 HTTP 請求重抓一次（不執行 JS）")
                    resp = context.request.get(url)
                    html = resp.text()
            return html

        def submit(url: str) -> None:
            page.goto(url if url.startswith("http") else f"{BASE}/{url.lstrip('/')}",
                      wait_until="networkidle")

        # 安靜時段只是確認 session 還活著，不需要田的成本，省掉備援那次額外請求
        d1 = get_html("dorf1.php", need_cost=not quiet)

        # cache 裡的 session 失效了：丟掉它，改用種子 Cookie 重試一次。
        # （context/page 在這個函式作用域內重新指定，上面的 get_html() 等
        #  closure 會自動用到新的物件。）
        if 'id="stockBar"' not in d1 and used_cache and seed_cookie:
            print("cache 的 session 已失效，改用 TRAVIAN_SEED_COOKIE 重新建立 session")
            context.close()
            try:
                STATE_PATH.unlink()
            except OSError:
                pass
            context = new_context_from_seed()
            page = context.new_page()
            d1 = get_html("dorf1.php", need_cost=not quiet)

        if 'id="stockBar"' not in d1:
            if used_cache and not seed_cookie:
                msg = "cache 的 session 已失效，且沒有設定 TRAVIAN_SEED_COOKIE 可以救援，請設定後重跑"
            else:
                msg = "抓到的不是村莊頁：種子 Cookie 也已失效，請重新登入複製 Cookie 更新 TRAVIAN_SEED_COOKIE"
            if dry:
                # DRY（測試用）不動共用 Sheet 的 Config：否則分支上的測試失敗會把正式排程一起停掉
                notify(msg + "（DRY 模式：不修改 Config 的 enabled）")
            else:
                disable(msg)
            browser.close()
            return 1

        if quiet:
            # session 是活的：把最新狀態存回去讓下一輪 actions/cache 接續，然後離開，不建造
            print("安靜時段：session 正常，只做 keep-alive，不建造")
            context.storage_state(path=str(STATE_PATH))
            browser.close()
            return 0

        code = R.run_build_cycle(
            cfg, get=get_html, get_dorf1=lambda: get_html("dorf1.php", need_cost=True),
            submit=submit, dry=dry, first_dorf1=d1)

        # 不管這輪做了什麼，只要一開始 session 是活的，就把最新狀態存回去，
        # 讓下一輪 actions/cache 可以接續使用
        context.storage_state(path=str(STATE_PATH))
        browser.close()

    return code


if __name__ == "__main__":
    sys.exit(main())
