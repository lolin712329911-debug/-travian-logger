"""test_transfer_io.py v1.0  用模擬伺服器測 transfer_io v1.2 與 travian_transfer v1.2 的搭配。
模擬規則（依 10-15 瀏覽器對照）：PUT 回 204＋回應標頭 x-nonce；POST 必須帶該 itemId 的 x-nonce，否則 400。
執行：python test_transfer_io.py   （與 transfer_io.py、travian_transfer.py 放同一資料夾）
"""
import json

import travian_transfer as TR
from transfer_io import make_io

ITEM = {879843: "lumber", 879844: "clay", 879845: "iron", 879846: "crop"}
TID = {"lumber": 145, "clay": 146, "iron": 147, "crop": 148}


class FakeResp:
    def __init__(self, status, headers=None, body="", js=None):
        self.status, self.headers, self._body, self._js = status, headers or {}, body, js
        self.ok = 200 <= status < 300

    def text(self):
        return self._body

    def json(self):
        return self._js


class FakeServer:
    def __init__(self, give_nonce=True, reject_post=False):
        self.stock = {"lumber": 1000, "clay": 900, "iron": 800, "crop": 700}
        self.inv = {r: 30000 for r in TR.RES}
        self.give_nonce, self.reject_post = give_nonce, reject_post
        self.calls, self.issued = [], {}
        self.request = self

    def graphql(self):
        res = {"lumberStock": self.stock["lumber"], "clayStock": self.stock["clay"],
               "ironStock": self.stock["iron"], "cropStock": self.stock["crop"],
               "maxStorageCapacity": 4000, "maxCropStorageCapacity": 3100}
        inv = [{"id": i, "typeId": TID[r], "amount": self.inv[r]} for i, r in ITEM.items()]
        return {"data": {"ownPlayer": {"village": {"id": 65222, "name": "v", "resources": res},
                                       "hero": {"inventory": inv}}}}

    def put(self, url, data, headers):
        p = json.loads(data)
        self.calls.append(("PUT", p, dict(headers)))
        n = f"nonce-{p['itemId']}-{len(self.calls)}"
        self.issued[p["itemId"]] = n
        return FakeResp(204, {"x-nonce": n} if self.give_nonce else {})

    def post(self, url, data, headers):
        if url.endswith(TR.GRAPHQL_PATH):
            return FakeResp(200, js=self.graphql())
        p = json.loads(data)
        self.calls.append(("POST", p, dict(headers)))
        if self.reject_post or headers.get("x-nonce") != self.issued.get(p["itemId"]):
            return FakeResp(400, body='{"error":"invalid nonce"}')
        r = ITEM[p["itemId"]]
        self.stock[r] += p["amount"]
        self.inv[r] -= p["amount"]
        return FakeResp(200, js=p["amount"])


TARGET = {"lumber": 1500, "clay": 1100, "iron": 500, "crop": 100}   # 缺口：木 500、磚 200


def run(server):
    send, read_state = make_io(server, "https://x.example")
    cfg = TR.TransferConfig(mode="always")
    plan = TR.decide_transfer(cfg, None, False, TARGET, read_state())
    assert plan.decision == "transfer", plan
    return TR.execute_transfer(plan, TARGET, send, read_state, phases=TR.FRONTEND_PHASES)


def test_full_flow():
    s = FakeServer()
    res = run(s)
    assert res.ok, res.detail
    assert [c[0] for c in s.calls] == ["PUT", "PUT", "POST", "POST"]
    for m, p, h in s.calls:
        if m == "PUT":
            assert "x-nonce" not in h
        else:
            assert h["x-nonce"] == s.issued[p["itemId"]]
    assert s.stock["lumber"] == 1500 and s.stock["clay"] == 1100
    assert s.inv["lumber"] == 29500 and s.inv["clay"] == 29800      # 只扣一次
    assert "庫存" in res.detail


def test_put_without_nonce_stops_before_post():
    s = FakeServer(give_nonce=False)
    res = run(s)
    assert not res.ok and "x-nonce" in res.detail
    assert [c[0] for c in s.calls] == ["PUT"]                       # 第一個 PUT 失敗就停


def test_post_without_put_not_sent():
    s = FakeServer()
    send, _ = make_io(s, "https://x.example")
    try:
        send({"action": "inventory", "itemId": 879843, "amount": 1, "villageId": 65222}, "POST")
        raise AssertionError("應該要 raise")
    except RuntimeError as e:
        assert "x-nonce" in str(e)
    assert s.calls == []


def test_post_400_shows_body_and_stops():
    s = FakeServer(reject_post=True)
    res = run(s)
    assert not res.ok and "400" in res.detail and "invalid nonce" in res.detail
    assert [c[0] for c in s.calls] == ["PUT", "PUT", "POST"]        # 第一筆 POST 失敗就停


def test_nonce_used_once():
    s = FakeServer()
    send, _ = make_io(s, "https://x.example")
    p = {"action": "inventory", "itemId": 879843, "amount": 1, "villageId": 65222}
    send(p, "PUT")
    send(p, "POST")
    try:
        send(p, "POST")                                             # 第二次沒有新 nonce
        raise AssertionError("應該要 raise")
    except RuntimeError:
        pass


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
