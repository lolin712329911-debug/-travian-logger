#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本機一次性執行：手動登入 Travian，匯出 storage_state.json 當作
GitHub Actions 的「種子」（第一輪 cache miss 時的救援用檔）。

跟舊的「複製整串 Cookie」不同：storage_state 是 Playwright 官方支援的
序列化格式（cookies + localStorage），之後在無頭瀏覽器裡還原它時，
頁面上任何 Travian 前端會跑的背景 refresh/keep-alive JS 都會真的被
執行到 —— 這是純 requests.Session() 版本做不到的事，也是 cookie
「用幾小時就死」跟「登入 session 可以撐幾天到幾週」的根本差異。

用法：
    pip install playwright
    playwright install chromium
    python seed_login.py

流程：
    1. 開一個「有畫面」的 Chromium
    2. 你自己在裡面手動登入 Travian（帳密不會被腳本碰、也不會存檔）
    3. 看到資源田畫面後回到終端機按 Enter
    4. 腳本把當下的 cookies/localStorage 存成 travian_state.json
    5. 印出下一步該做什麼
"""
import base64
import json
import sys
from pathlib import Path

BASE = "https://ts11.x1.international.travian.com"   # 改成你的伺服器網址
OUT_FILE = Path("travian_state.json")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("缺少 playwright，請先執行：pip install playwright && playwright install chromium")
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{BASE}/dorf1.php")

        input("請在跳出的瀏覽器視窗手動登入，看到資源田畫面後回這裡按 Enter ... ")

        if page.locator("#stockBar").count() == 0:
            print("目前頁面上找不到 #stockBar，看起來還沒登入成功，請重新執行。")
            browser.close()
            return 1

        context.storage_state(path=str(OUT_FILE))
        browser.close()

    size_kb = OUT_FILE.stat().st_size / 1024
    print(f"\n已寫入 {OUT_FILE}（約 {size_kb:.1f} KB）")

    b64 = base64.b64encode(OUT_FILE.read_bytes()).decode()
    print(f"\nBase64 編碼後長度：約 {len(b64) / 1024:.1f} KB")
    print("\n下一步：")
    print("  1. 把上面這串長度的 base64 內容存進 GitHub Secret，名稱設為")
    print("     TRAVIAN_SEED_STATE")
    print("     （不要貼在這裡的終端機截圖或任何公開地方；下面幫你寫進")
    print(f"      本機檔案 {OUT_FILE.name}.b64.txt，複製那個檔案內容即可）")
    Path(f"{OUT_FILE.name}.b64.txt").write_text(b64, encoding="utf-8")
    print(f"  2. 已另外寫出 {OUT_FILE.name}.b64.txt，複製它整份內容貼進 Secret")
    print("  3. 之後就不需要再跑這支腳本了 —— CI 會靠 actions/cache 自己延續")
    print("     session；TRAVIAN_SEED_STATE 只在 cache 失效/第一次跑時當救援用")
    print(f"  4. 記得刪除或妥善保管本機的 {OUT_FILE} 與 {OUT_FILE.name}.b64.txt，")
    print("     兩者都等同於你的登入憑證")
    return 0


if __name__ == "__main__":
    sys.exit(main())
