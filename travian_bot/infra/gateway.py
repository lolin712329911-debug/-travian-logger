#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/gateway.py（if-02）
版本：v0.2（A5a 追加 Response.headers、base_url、click；既有行為不變）｜v0.1（A4a；B1 才加 did／newdid）
用途：對遊戲伺服器的唯一出口：抓頁（瀏覽器渲染或純 HTTP）、送出網址、API 呼叫、URL 白名單、
      請求計數與耗時。網址一律由 ServerProfile.base_url 組出。**不驗證頁面內容**（§6.6）。
依賴：cm-01（ServerProfile，只用 base_url）、cm-03（A4a 沒有實際 import）。
部署狀態：未部署（GA 前不 live）。

與舊 travian_ci_run.py（✓ 已讀）的差異（交接區塊有列）
  1. 舊 get_html 的 need_cost 備援會呼叫 parse_dorf1；infra 不能 import parsers，所以改成
     raw_if：由呼叫端（app）傳判斷函式，gateway 對回來的 html 呼叫它，回 True 就改用純 HTTP 再抓一次。
  2. 預設仍是瀏覽器渲染（render），與舊 get_html 一致；raw=True 才是純 HTTP、不執行 JS。
     （卡片原寫 render=False 預設，與舊預設相反，已更正。）
  3. session 用 Protocol 描述（只要有 context、page 屬性），不 import infra/session（§4.1：infra 互相獨立）。
  4. 舊碼沒有隨機等待與重試；機制做好、預設值全部 0（行為不變），數值留給 B3 時間預算。
     只有 GET 的傳輸錯誤會重試；POST 與 submit 永不重送（可能已送達）。
  5. 所有請求都過 safe_url：必須是 base_url 同源的 https 網址（或相對路徑）。
  6. did 參數保留但不使用（B1 才加）。

v0.2（A5a）追加，既有簽名與行為不變：
  - Response.headers：回應標頭（鍵一律小寫；預設空 dict）。轉移的 PUT 要讀回應標頭的 x-nonce（transfer_io v1.2 ✓）。
    標頭可能含 token，呼叫端不得寫進 log／Actions。
  - Gateway.base_url：唯讀（無結尾斜線），給需要 origin／referer 標頭的 API 呼叫。
  - Gateway.click(selector, *, index=0, settle_ms=3000)：在「目前頁面」點一個元素（先用 get 渲染該頁）。
    目前頁面網址必須通過 safe_url；不重試（可能已送達）；失敗丟 GatewayError。計入 request_count。
"""
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Protocol
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from ..common.models import ServerProfile

RAW_METHODS = ("GET", "POST", "PUT", "DELETE")
_FORBIDDEN_HEADERS = frozenset({"cookie", "authorization"})   # 登入狀態只由 session 的 context 帶


class GatewayError(RuntimeError):
    """請求失敗或網址不合法。訊息只含路徑（不含查詢字串），避免 checksum／token 外洩。"""


class SessionLike(Protocol):
    @property
    def context(self) -> Any: ...

    @property
    def page(self) -> Any: ...


@dataclass(frozen=True)
class GatewayLimits:
    """等待與重試。預設全 0＝與舊行為相同（無等待、不重試）。"""
    wait_min_s: float = 0.0       # 每個請求前隨機等待 [wait_min_s, wait_max_s] 秒
    wait_max_s: float = 0.0
    get_retries: int = 0          # GET 傳輸錯誤的重試次數（不含第一次）
    retry_wait_s: float = 0.0     # 重試前固定等待

    def __post_init__(self):
        for name in ("wait_min_s", "wait_max_s", "retry_wait_s"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                raise ValueError(f"{name} 需為 ≥ 0 的數字")
        if self.wait_max_s < self.wait_min_s:
            raise ValueError("wait_max_s 不可小於 wait_min_s")
        if isinstance(self.get_retries, bool) or not isinstance(self.get_retries, int) or self.get_retries < 0:
            raise ValueError("get_retries 需為 ≥ 0 的整數")


@dataclass(frozen=True)
class Response:
    status: int
    ok: bool
    text: str
    headers: Mapping[str, str] = field(default_factory=dict)   # v0.2：鍵小寫


# ---------------------------------------------------------------- URL 白名單
def safe_url(url: Any, base_url: str) -> bool:
    """相對路徑（單一 / 開頭）或與 base_url 同源的 https 網址才算安全。
    拒絕：空白／控制字元／反斜線、帳密（@）、`..` 路徑段、其他主機或 http。"""
    if not isinstance(url, str) or not url:
        return False
    if any(ch.isspace() or ord(ch) < 32 or ch == "\\" for ch in url):
        return False
    try:
        parts = urlsplit(url)
        base = urlsplit(base_url)
    except ValueError:
        return False
    if ".." in parts.path.split("/"):
        return False
    if not parts.scheme and not parts.netloc:
        return url.startswith("/") and not url.startswith("//")
    if parts.scheme != "https" or "@" in parts.netloc:
        return False
    return parts.netloc.lower() == base.netloc.lower()


def _path_only(url: str) -> str:
    try:
        return urlsplit(url).path or "/"
    except ValueError:
        return "?"


class Gateway:
    def __init__(self, session: SessionLike, profile: "ServerProfile",
                 limits: Optional[GatewayLimits] = None, *,
                 sleep: Callable[[float], None] = time.sleep,
                 uniform: Callable[[float, float], float] = random.uniform,
                 clock: Callable[[], float] = time.monotonic):
        self._session = session
        self._base = profile.base_url.rstrip("/")
        self._limits = limits or GatewayLimits()
        self._sleep = sleep
        self._uniform = uniform
        self._clock = clock
        self._t0 = clock()
        self._count = 0

    # ------------------------------------------------------------ 計數
    def request_count(self) -> int:
        """已發出的網路請求數（含重試與 raw_if 備援那一次）。"""
        return self._count

    @property
    def base_url(self) -> str:
        """v0.2：ServerProfile.base_url（無結尾斜線）。"""
        return self._base

    def elapsed(self) -> float:
        """從建立 Gateway 起經過的秒數。"""
        return self._clock() - self._t0

    def safe_url(self, url: Any) -> bool:
        return safe_url(url, self._base)

    # ------------------------------------------------------------ 抓頁
    def get(self, path: str, *, raw: bool = False,
            raw_if: Optional[Callable[[str], bool]] = None, did: Optional[int] = None) -> str:
        """抓一頁，回 html。
        預設用瀏覽器渲染（page.goto＋page.content，等 networkidle）；raw=True 改純 HTTP（不執行 JS）。
        raw_if(html) 回 True 時，再用純 HTTP 抓同一頁並回傳那份（取代舊 need_cost 備援）。
        did：B1 才用，A4a 忽略。"""
        url = self._url(path)
        if raw:
            return self._retry_get(url, lambda: self._ctx().request.get(url).text())
        html = self._retry_get(url, lambda: self._render(url))
        if raw_if is not None and raw_if(html):
            html = self._retry_get(url, lambda: self._ctx().request.get(url).text())
        return html

    def submit(self, url: str) -> None:
        """瀏覽器開啟一個網址（升級按鈕等）。過 safe_url；不重試（可能已送達）。"""
        full = self._url(url)
        self._wait()
        self._count += 1
        try:
            self._session.page.goto(full, wait_until="networkidle")
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(f"開啟 {_path_only(full)} 失敗：{type(exc).__name__}") from exc

    def click(self, selector: str, *, index: int = 0, settle_ms: int = 3000) -> None:
        """v0.2：在目前頁面點 selector 的第 index 個元素，之後等 settle_ms 毫秒。
        目前頁面不在白名單內不點；不重試；失敗丟 GatewayError（訊息不含頁面內容）。"""
        if not isinstance(selector, str) or not selector.strip():
            raise ValueError("selector 不可為空")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError("index 需為 ≥ 0 的整數")
        if isinstance(settle_ms, bool) or not isinstance(settle_ms, int) or settle_ms < 0:
            raise ValueError("settle_ms 需為 ≥ 0 的整數")
        page = self._session.page
        cur = getattr(page, "url", "")
        if not self.safe_url(cur):
            raise GatewayError("目前頁面不在白名單內，不點擊")
        self._wait()
        self._count += 1
        try:
            page.locator(selector).nth(index).click()
            if settle_ms > 0:
                page.wait_for_timeout(settle_ms)
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(f"點擊失敗：{type(exc).__name__}") from exc

    def request(self, method: str, path: str, *, headers: Optional[Mapping[str, str]] = None,
                data: Any = None) -> Response:
        """純 HTTP API 呼叫（use-item、hero_focus 等），沿用同一組登入狀態。
        只有 GET 會在傳輸錯誤時重試；POST／PUT／DELETE 不重送。HTTP 狀態碼不丟例外，看 Response.ok。"""
        m = method.upper() if isinstance(method, str) else ""
        if m not in RAW_METHODS:
            raise ValueError("method 只能是 GET／POST／PUT／DELETE")
        hdrs = dict(headers) if headers else None
        if hdrs and any(k.lower() in _FORBIDDEN_HEADERS for k in hdrs):
            raise ValueError("不得手動指定 Cookie／Authorization（登入狀態由 session 帶）")
        url = self._url(path)

        def call() -> Response:
            kwargs = {"method": m}
            if hdrs:
                kwargs["headers"] = hdrs
            if data is not None:
                kwargs["data"] = data
            resp = self._ctx().request.fetch(url, **kwargs)
            resp_headers = {str(k).lower(): str(v) for k, v in (getattr(resp, "headers", None) or {}).items()}
            return Response(status=int(resp.status), ok=bool(resp.ok), text=resp.text(), headers=resp_headers)

        if m == "GET":
            return self._retry_get(url, call)
        self._wait()
        self._count += 1
        try:
            return call()
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(f"{m} {_path_only(url)} 失敗：{type(exc).__name__}") from exc

    # ------------------------------------------------------------ 內部
    def _ctx(self) -> Any:
        return self._session.context      # 每次現取：session.recover() 後仍是最新的

    def _render(self, url: str) -> str:
        page = self._session.page
        page.goto(url, wait_until="networkidle")
        return page.content()

    def _url(self, path: str) -> str:
        if not isinstance(path, str) or not path.strip():
            raise GatewayError("路徑不可為空")
        if path.startswith(("http://", "https://")):
            url = path
        else:
            url = f"{self._base}/{path.lstrip('/')}"
        if not self.safe_url(url):
            raise GatewayError(f"網址不在白名單內：{_path_only(url)}")
        return url

    def _wait(self) -> None:
        lim = self._limits
        if lim.wait_max_s > 0:
            self._sleep(self._uniform(lim.wait_min_s, lim.wait_max_s))

    def _retry_get(self, url: str, fn: Callable[[], Any]) -> Any:
        attempts = 1 + self._limits.get_retries
        for attempt in range(1, attempts + 1):
            self._wait()
            self._count += 1
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                if attempt >= attempts:
                    raise GatewayError(
                        f"GET {_path_only(url)} 失敗（共試 {attempts} 次）：{type(exc).__name__}") from exc
                if self._limits.retry_wait_s > 0:
                    self._sleep(self._limits.retry_wait_s)
