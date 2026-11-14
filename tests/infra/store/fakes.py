"""A4b-1 測試共用的假 gspread 物件（不連網）。bool／None 之外的值一律以字串存，模擬 get_all_values 讀回的樣子。"""
import sys
import types
from unittest import mock


class WorksheetNotFound(Exception):
    pass


def fake_gspread_modules():
    gspread = types.ModuleType("gspread")
    exc = types.ModuleType("gspread.exceptions")
    exc.WorksheetNotFound = WorksheetNotFound
    gspread.exceptions = exc
    return {"gspread": gspread, "gspread.exceptions": exc}


def patch_gspread():
    """用法：setUpModule 裡 `_p = patch_gspread(); _p.start()`，tearDownModule 裡 `_p.stop()`。"""
    return mock.patch.dict(sys.modules, fake_gspread_modules())


def _letters_to_n(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n


def _split_a1(a1):
    i = 0
    while a1[i].isalpha():
        i += 1
    return int(a1[i:]), _letters_to_n(a1[:i])


class FakeWS:
    def __init__(self, title="ws", rows=None, row_count=1000, col_count=10, fail_on=None):
        self.title = title
        self.rows = [list(map(str, r)) for r in (rows or [])]
        self.row_count, self.col_count = row_count, col_count
        self.calls = []
        self.fail_on = fail_on or {}

    def _hook(self, name):
        self.calls.append(name)
        if name in self.fail_on:
            raise self.fail_on[name]

    # ---- 讀
    def get_all_values(self):
        self._hook("get_all_values")
        rows = [list(r) for r in self.rows]
        while rows and all(c == "" for c in rows[-1]):
            rows.pop()
        width = max((len(r) for r in rows), default=0)
        return [r + [""] * (width - len(r)) for r in rows]

    def row_values(self, n):
        self._hook("row_values")
        row = self.rows[n - 1] if n - 1 < len(self.rows) else []
        while row and row[-1] == "":
            row = row[:-1]
        return list(row)

    def batch_get(self, ranges):
        self._hook("batch_get")
        out = []
        for rg in ranges:
            col = _letters_to_n(rg.split(":")[0]) - 1
            vr = [[r[col]] if col < len(r) and r[col] != "" else [] for r in self.rows]
            while vr and not vr[-1]:
                vr.pop()
            out.append(vr)
        return out

    # ---- 寫
    def _put(self, r, c, value):
        while len(self.rows) < r:
            self.rows.append([])
        row = self.rows[r - 1]
        while len(row) < c:
            row.append("")
        row[c - 1] = "" if value is None else str(value)

    def update(self, range_name=None, values=None, value_input_option=None):
        self._hook("update")
        self.last_update = (range_name, [list(r) for r in values], value_input_option)
        r0, c0 = _split_a1(range_name)
        for i, row in enumerate(values):
            for j, v in enumerate(row):
                self._put(r0 + i, c0 + j, v)

    def append_rows(self, data, value_input_option=None):
        self._hook("append_rows")
        self.last_append = ([list(r) for r in data], value_input_option)
        last = 0
        for i, r in enumerate(self.rows, start=1):
            if any(c != "" for c in r):
                last = i
        for k, row in enumerate(data, start=1):
            for j, v in enumerate(row, start=1):
                self._put(last + k, j, v)

    def add_rows(self, n):
        self._hook("add_rows")
        self.row_count += n

    def add_cols(self, n):
        self._hook("add_cols")
        self.col_count += n

    def n_calls(self, name):
        return self.calls.count(name)


class FakeSheet:
    def __init__(self, tabs=None):
        self.tabs = dict(tabs or {})
        self.worksheet_calls = 0

    def worksheet(self, title):
        self.worksheet_calls += 1
        if title not in self.tabs:
            raise WorksheetNotFound(title)
        return self.tabs[title]

    def add_worksheet(self, title, rows, cols):
        ws = FakeWS(title, row_count=rows, col_count=cols)
        self.tabs[title] = ws
        return ws
