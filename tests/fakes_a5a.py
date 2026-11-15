# -*- coding: utf-8 -*-
"""tests/fakes_a5a.py（A5a）：actions／gateway 測試共用的替身。只在測試用，不在 bot 執行路徑上。

FakeResp     模擬 Playwright APIResponse：status／ok／headers 屬性，text() 方法。
Router       模擬 context.request：fetch(url, method=, headers=, data=)、get(url)。
             以 (METHOD, 路徑) 為鍵，依序回應；沒有登記的請求回 404 並記在 unexpected（測試要檢查它是空的）。
FakePage     模擬 page：goto／content／url／locator(sel).nth(i).click()／wait_for_timeout。
make_gateway 組出真的 Gateway（用替身 session）。
"""
from types import SimpleNamespace as NS
from urllib.parse import urlsplit

from travian_bot.infra.gateway import Gateway, GatewayLimits

BASE = "https://ts1.example.com"


class FakeResp:
    def __init__(self, status=200, text="", headers=None):
        self.status = status
        self.ok = 200 <= status < 300
        self.headers = headers if headers is not None else {}
        self._text = text

    def text(self):
        return self._text


class Router:
    """routes: {(METHOD, "/path"): [回應, …]}；回應可為 FakeResp、Exception、或 callable(call)→FakeResp／Exception。
    同一鍵的回應依序取用；用完後重複最後一個（要測「不會再送」請看 calls，不是靠耗盡）。"""

    def __init__(self, routes=None):
        self.routes = {k: list(v) if isinstance(v, (list, tuple)) else [v] for k, v in (routes or {}).items()}
        self.calls = []
        self.unexpected = []
        self._used = {}

    def _answer(self, method, url, kw):
        path = urlsplit(url).path
        call = {"method": method, "path": path, "url": url, "headers": kw.get("headers"), "data": kw.get("data")}
        self.calls.append(call)
        key = (method, path)
        if key not in self.routes:
            self.unexpected.append(key)
            return FakeResp(404, "")
        seq = self.routes[key]
        i = self._used.get(key, 0)
        self._used[key] = i + 1
        item = seq[min(i, len(seq) - 1)]
        if callable(item) and not isinstance(item, (FakeResp, Exception)):
            item = item(call)
        if isinstance(item, Exception):
            raise item
        return item

    # Playwright APIRequestContext
    def fetch(self, url, **kw):
        return self._answer(kw.get("method", "GET"), url, kw)

    def get(self, url, **kw):
        return self._answer("GET", url, kw)

    def seq(self):
        """請求順序：[(METHOD, path), …]"""
        return [(c["method"], c["path"]) for c in self.calls]

    def of(self, method, path=None):
        return [c for c in self.calls if c["method"] == method and (path is None or c["path"] == path)]


class _Locator:
    def __init__(self, page, selector):
        self._page, self._sel, self._i = page, selector, 0

    def nth(self, i):
        self._i = i
        return self

    def click(self):
        self._page.clicks.append((self._sel, self._i))
        if self._page.click_error is not None:
            raise self._page.click_error
        if self._page.on_click is not None:
            self._page.on_click()


class FakePage:
    """pages: {"/path?query": html 或 Exception}（鍵不含 BASE）。goto 之後 url 變成該網址。"""

    def __init__(self, pages=None, click_error=None, on_click=None):
        self.pages = dict(pages or {})
        self.visited, self.clicks, self.waits = [], [], []
        self.url = ""
        self.click_error, self.on_click = click_error, on_click

    def goto(self, url, wait_until=None):
        self.visited.append(url)
        v = self.pages.get(url[len(BASE):], "")
        if isinstance(v, Exception):
            raise v
        self.url = url

    def content(self):
        return self.pages.get(self.url[len(BASE):], "")

    def locator(self, selector):
        return _Locator(self, selector)

    def wait_for_timeout(self, ms):
        self.waits.append(ms)


def make_gateway(pages=None, routes=None, limits=None, base=BASE, page=None, **gw_kw):
    """回傳 (gw, page, router)。"""
    page = page if page is not None else FakePage(pages)
    router = Router(routes)
    session = NS(context=NS(request=router), page=page)
    gw = Gateway(session, NS(base_url=base), limits, **gw_kw)    # Gateway 只讀 profile.base_url；不建真的 ServerProfile（欄位多、會變）
    return gw, page, router
