#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/session.py（if-01）
版本：v0.1（A4a）
用途：Playwright 的 browser／context／page 與登入狀態（session 快取檔、種子 Cookie）。
      只有這個模組讀寫 session 檔（§4.1 補充規則 7）。
依賴：cm-01（ServerProfile，只用 server_id、base_url）、cm-10（serialize）。
部署狀態：未部署（GA 前不 live）。

與舊 travian_ci_run.py（✓ 已讀）的差異（交接區塊有列）
  1. 舊流程全寫在 main()，靠巢狀函式共用 context／page（失效時重新指定）；改成 Session 物件，
     context／page 是屬性，recover() 重建後 gateway 取到的永遠是最新的。
  2. BASE、狀態檔路徑不再讀環境變數，全部由參數傳入（網址來自 ServerProfile.base_url）。
  3. cache 檔格式不同：舊版是 Playwright storage_state 整份；新版有 schema_version／saved_utc／
     server_id／cookies／origins，server_id 不符整份丟棄（§6.5）。檔名由呼叫端給，建議
     travian_session.json（舊 bot 的 travian_state.json 不會被覆蓋）。
  4. 沒有 validate_session()／keep_alive()：驗證要多打一個請求，會繞過 gateway 的計數。
     流程由 app 組：gateway.get("dorf1.php") → Session.is_village_html() → 失效就 recover()；
     keep_alive 就是 save_state()。
  5. 不 import playwright：launch() 吃已啟動的 sync_playwright 物件（呼叫端在函式內才 import）。

cache 含憑證：不入 git、log、artifact。本檔所有 log 與例外訊息都不含 Cookie 值。
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from ..common import serialize

if TYPE_CHECKING:  # 只當型別參考；執行時只用 profile.server_id、profile.base_url
    from ..common.models import ServerProfile

CACHE_SCHEMA_VERSION = 1
CACHE_SCHEMA_NAME = "session_cache"
VILLAGE_MARKER = 'id="stockBar"'      # 舊判斷村莊頁的標記（✓ 舊 travian_ci_run）

Logger = Callable[[str], None]


class SessionLost(RuntimeError):
    """沒有可用的登入狀態（cache 與種子 Cookie 都沒有，或無法重建）。訊息不含 Cookie。"""


def parse_cookie_header(header: str, url: str) -> List[Dict[str, str]]:
    """'name1=value1; name2=value2' → Playwright context.add_cookies() 吃的格式（沿用舊簽名與行為）。"""
    cookies = []
    for part in header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies.append({"name": name.strip(), "value": value.strip(), "url": url})
    return cookies


def _default_log(msg: str) -> None:
    print(serialize.redact(msg))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Session:
    """一個 Playwright browser＋context＋page。用 Session.launch() 建立。"""

    def __init__(self, browser: Any, context: Any, profile: "ServerProfile", state_path: Any,
                 seed_cookie: str, used_cache: bool, *, log: Logger = _default_log,
                 now_fn: Callable[[], datetime] = _now_utc):
        self._browser = browser
        self._context = context
        self._page = context.new_page()
        self._profile = profile
        self._state_path = Path(state_path)
        self._seed = seed_cookie or ""
        self._used_cache = bool(used_cache)
        self._log = log
        self._now = now_fn
        self._closed = False

    def __repr__(self) -> str:        # 不印種子 Cookie
        return f"<Session server_id={self._profile.server_id!r} used_cache={self._used_cache}>"

    # ------------------------------------------------------------ 建立
    @classmethod
    def launch(cls, playwright: Any, profile: "ServerProfile", state_path: Any,
               seed_cookie: Optional[str] = None, *, log: Logger = _default_log,
               now_fn: Callable[[], datetime] = _now_utc) -> "Session":
        """啟動 chromium；先讀 cache，cache 沒有（或不合法／server_id 不符）才用種子 Cookie；
        兩者都沒有丟 SessionLost。playwright 是已啟動的 sync_playwright() 物件。"""
        path = Path(state_path)
        seed = (seed_cookie or "").strip()
        state = _load_cache(path, profile.server_id, log)
        if state is None and not seed:
            raise SessionLost("找不到可用的 session cache，也沒有種子 Cookie 可以救援")
        browser = playwright.chromium.launch(headless=True)
        try:
            if state is not None:
                log(f"找到既有 session 狀態：{path.name}（來自 actions/cache）")
                context = browser.new_context(storage_state=state)
                used_cache = True
            else:
                log("cache 沒中，改用種子 Cookie 建立 session")
                context = _context_from_seed(browser, seed, profile.base_url)
                used_cache = False
            return cls(browser, context, profile, path, seed, used_cache, log=log, now_fn=now_fn)
        except Exception:
            browser.close()
            raise

    # ------------------------------------------------------------ 屬性
    @property
    def context(self) -> Any:
        return self._context

    @property
    def page(self) -> Any:
        return self._page

    @property
    def used_cache(self) -> bool:
        return self._used_cache

    @property
    def can_recover(self) -> bool:
        """目前是 cache 建立的、且有種子 Cookie 可重建。已是種子 session 時重建沒有意義。"""
        return self._used_cache and bool(self._seed)

    @staticmethod
    def is_village_html(html: Any) -> bool:
        """是不是登入後的村莊頁（沿用舊的 stockBar 標記）。"""
        return isinstance(html, str) and VILLAGE_MARKER in html

    # ------------------------------------------------------------ 動作
    def recover(self) -> None:
        """cache 失效：丟掉 cache 檔，改用種子 Cookie 重建 context 與 page。
        不能重建（不是 cache 建立的、或沒有種子）丟 SessionLost。"""
        if self._closed:
            raise SessionLost("session 已關閉")
        if not self.can_recover:
            raise SessionLost("無法重建 session：目前不是 cache 建立的，或沒有種子 Cookie")
        self._log("cache 的 session 已失效，改用種子 Cookie 重新建立 session")
        self._context.close()
        try:
            self._state_path.unlink()
        except OSError:
            pass
        self._context = _context_from_seed(self._browser, self._seed, self._profile.base_url)
        self._page = self._context.new_page()
        self._used_cache = False

    def save_state(self) -> None:
        """把目前 context 的登入狀態寫成契約格式（§6.5）：先寫暫存檔、再原子替換。"""
        raw = self._context.storage_state()
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "saved_utc": serialize.to_utc_str(self._now()),
            "server_id": self._profile.server_id,
            "cookies": list(raw.get("cookies", [])),
            "origins": list(raw.get("origins", [])),
        }
        text = serialize.dumps_stable(payload)
        tmp = self._state_path.with_name(self._state_path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self._state_path)

    def close(self) -> None:
        """關閉 browser（可重複呼叫）。"""
        if self._closed:
            return
        self._closed = True
        self._browser.close()

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# ---------------------------------------------------------------- 內部
def _context_from_seed(browser: Any, seed: str, base_url: str) -> Any:
    cookies = parse_cookie_header(seed, base_url.rstrip("/"))
    if not cookies:
        raise SessionLost("種子 Cookie 格式不合法（沒有任何 name=value）")
    ctx = browser.new_context()
    ctx.add_cookies(cookies)
    return ctx


def _load_cache(path: Path, server_id: str, log: Logger) -> Optional[Dict[str, Any]]:
    """讀 cache；任何問題（不存在、壞檔、版本太新、server_id 不符）回 None，不丟例外。
    server_id 不符時整份丟棄並刪檔（新伺服器不誤用舊 Cookie）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        log("session cache 讀取失敗，忽略")
        return None
    try:
        data = serialize.loads_checked(text, CACHE_SCHEMA_NAME, max_version=CACHE_SCHEMA_VERSION)
    except serialize.SerializeError as exc:
        log(f"session cache 不合法，忽略（{exc}）")
        return None
    if data.get("server_id") != server_id:
        log("session cache 的 server_id 與目前伺服器不符，整份丟棄")
        try:
            path.unlink()
        except OSError:
            pass
        return None
    cookies, origins = data.get("cookies"), data.get("origins", [])
    ok = (isinstance(cookies, list) and cookies and isinstance(origins, list)
          and all(isinstance(c, dict) and isinstance(c.get("name"), str)
                  and isinstance(c.get("value"), str) for c in cookies))
    if not ok:
        log("session cache 的 cookies 欄位不合法，忽略")
        return None
    return {"cookies": cookies, "origins": origins}
