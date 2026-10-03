#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""離線測試 village_log.py：用假的 Google Sheet（記憶體）+ 範例頁面 dorf1/dorf2/build1~3.txt。
用法：python test_village_log.py    （不需要網路、不需要 Google 憑據）"""
import copy
import re
from datetime import datetime, timedelta, timezone

import travian_pages as P
import village_log as V


class WorksheetNotFound(Exception):
    pass


class FakeWS:
    def __init__(self, title):
        self.title, self.rows, self.row_count, self.col_count = title, [], 100, 12
        self.writes = 0

    def get_all_values(self):
        return [[("" if c is None else str(c)) for c in r] for r in self.rows]

    def row_values(self, i):
        return self.get_all_values()[i - 1] if len(self.rows) >= i else []

    def add_rows(self, n): self.row_count += n
    def add_cols(self, n): self.col_count += n
    def clear(self): self.rows = []

    def update(self, range_name, values, raw=False):
        assert range_name == "A1"
        self.rows = [list(r) for r in values]
        self.writes += 1

    def append_row(self, row): self.rows.append(list(row)); self.writes += 1

    def append_rows(self, rows, value_input_option=None):
        self.rows.extend(list(r) for r in rows); self.writes += 1


class FakeSheet:
    def __init__(self): self.tabs = {}

    def worksheet(self, name):
        if name not in self.tabs:
            raise WorksheetNotFound(name)
        return self.tabs[name]

    def add_worksheet(self, title, rows, cols):
        self.tabs[title] = FakeWS(title)
        return self.tabs[title]


def read(f):
    return open(f, encoding="utf-8", errors="replace").read()


D1, D2 = read("dorf1.txt"), read("dorf2.txt")
calls = []


def get(path):
    calls.append(path)
    m = re.search(r"category=(\d)", path)
    return read(f"build{m.group(1)}.txt")


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    assert cond, msg


def show(sh, name, n=None):
    for r in sh.tabs[name].rows[:n]:
        print("   ", r)


sh = FakeSheet()
st = P.parse_dorf1(D1)
T0 = "2026-09-30 15:00:00"

print("\n[1] 第一輪：全部初始化")
ch = V.log_structure(sh, D2, get, st, now=T0)
check(set(sh.tabs) == {"Fields", "Buildings", "Buildable", "Changes"}, "建立 4 個分頁")
check(len(sh.tabs["Fields"].rows) == 19, "Fields = 表頭 + 18 塊")
check(len(sh.tabs["Buildings"].rows) == 23, "Buildings = 表頭 + 22 位（石墻不重複）")
check(len(calls) == 3 and all("category=" in c for c in calls), f"可蓋清單抓 3 個分頁：{calls}")
nb = len(sh.tabs["Buildable"].rows) - 1
check(nb == 23, f"Buildable = 23 種（11+7+5）：{nb}")
check([c[1] for c in ch] == ["初始化"] * 3, "Changes 只有 3 筆『初始化』，沒有假變動")
show(sh, "Fields", 3); show(sh, "Buildings", 4); show(sh, "Buildable", 4); show(sh, "Changes")

print("\n[2] 第二輪：頁面完全沒變 → 完全不寫入、不重抓")
calls.clear()
w = {k: v.writes for k, v in sh.tabs.items()}
ch = V.log_structure(sh, D2, get, st, now="2026-09-30 15:30:00")
check(ch == [], "沒有新變動")
check({k: v.writes for k, v in sh.tabs.items()} == w, "所有分頁寫入次數都沒增加")
check(calls == [], "沒有重抓可蓋清單")

print("\n[3] 第三輪：資源田升級、空地蓋了建築、石墻完工 → 記變動 + 重抓可蓋清單")
st3 = copy.deepcopy(st)
st3.fields[0].level += 1
st3.fields[1].building = True
real_parse = P.parse_dorf2_slots
slots = real_parse(D2)
empty = next(s for s in slots if s.gid == 0 and 19 <= s.aid <= 38)
empty.gid, empty.name, empty.level, empty.building = 17, "市場", 0, True
wall = [s for s in slots if s.aid == 40]
for s in wall:
    s.level, s.building = 1, False
P.parse_dorf2_slots = lambda html: slots
try:
    ch = V.log_structure(sh, D2, get, st3, now="2026-09-30 16:00:00")
finally:
    P.parse_dorf2_slots = real_parse
for c in ch: print("   ", c)
kinds = [c[1] for c in ch]
check("資源田等級" in kinds and "資源田開始施工" in kinds, "資源田：等級變化 + 開始施工")
check("新建築" in kinds and "建築等級" in kinds, "建築：新建築 + 石墻等級")
check(len(calls) == 3, "Buildings 有變動 → 重抓 3 個分頁")
f = sh.tabs["Fields"].rows
check(f[1][-1] == "2026-09-30 16:00:00" and f[5][-1] == T0, "只有變動的列更新『最後變動』，其他列保留舊時間")

print("\n[4] 24 小時保底：超過 24 小時才重抓，且只更新『最後確認』")
calls.clear()
old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime(V.TS_FMT)
for r in sh.tabs["Buildable"].rows[1:]:
    r[-1] = old_ts
ch = V.log_structure(sh, D2, get, st3, now="2026-10-01 10:00:00")
check(len(calls) == 3, "超過 24 小時 → 重抓")
check(all(c[1] != "可蓋清單新增" and c[1] != "可蓋清單移除" for c in ch), "內容沒變 → 不記變動")
check(sh.tabs["Buildable"].rows[1][-1] == "2026-10-01 10:00:00", "『最後確認』已更新")

print("\n[5] 成本被 JS 清空：等級沒變時沿用舊成本，不記變動")
st5 = copy.deepcopy(st3)
for x in st5.fields:
    x.cost, x.secs = None, 0
before = copy.deepcopy(sh.tabs["Fields"].rows)
ch = V.log_structure(sh, D2, get, st5, now="2026-10-01 10:30:00")
check(sh.tabs["Fields"].rows == before, "Fields 內容完全不變（成本沒被清成空白）")
check(all(c[1] not in ("資源田等級",) for c in ch), "沒有假變動")

print("\n[6] 村莊沒有空地 → 略過可蓋清單")
calls.clear()
full = [s for s in real_parse(D2)]
for s in full:
    if s.gid == 0:
        s.gid, s.name, s.level = 17, "市場", 1
P.parse_dorf2_slots = lambda html: full
try:
    V.log_structure(sh, D2, get, st3, now="2026-10-01 11:00:00")
finally:
    P.parse_dorf2_slots = real_parse
check(calls == [], "沒空地 → 不抓可蓋清單")

print("\n[7] 這輪沒有 dorf2（抓取失敗）→ 只記資源田，不會清空建築分頁")
n_before = len(sh.tabs["Buildings"].rows)
V.log_structure(sh, None, get, st3, now="2026-10-01 11:30:00")
check(len(sh.tabs["Buildings"].rows) == n_before, "Buildings 沒被動到")

print("\n[8] 某個分頁寫入失敗不影響其他步驟")
class BoomSheet(FakeSheet):
    def worksheet(self, name):
        if name == "Buildings":
            raise RuntimeError("boom")
        return super().worksheet(name)
bs = BoomSheet()
ch = V.log_structure(bs, D2, get, st, now=T0)
check("Fields" in bs.tabs and "Buildable" in bs.tabs and "Changes" in bs.tabs, "Buildings 失敗，其餘照常完成")

print("\n全部通過")
