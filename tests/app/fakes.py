# -*- coding: utf-8 -*-
"""A6a1 測試共用的假物件（不連網、不碰 Sheet）。不是測試檔。"""
from datetime import datetime, timezone
from pathlib import Path

from travian_bot.app.run_context import RunContext, StageIO
from travian_bot.common.models import (BuildSettings, HideContext, ServerProfile, VillageContext)
from travian_bot.common.tribe_data import get_tribe

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
NOW = datetime(2026, 11, 15, 8, 0, 0, tzinfo=timezone.utc)
NOW_S = "2026-11-15T08:00:00Z"


def sample(sid, kind, date):
    return (SAMPLES / f"{sid}_{kind}_{date}.html").read_text(encoding="utf-8")


class FakeGateway:
    """pages：路徑 → html，或 list（依序回，最後一個重複）。同一路徑的 raw_if 為真時，多算一次請求並取下一份。"""

    def __init__(self, pages=None, fail=None):
        self.pages = dict(pages or {})
        self.fail = dict(fail or {})
        self.calls = []
        self._n = 0
        self._t = 0.0
        self._seen = {}

    def request_count(self):
        return self._n

    def elapsed(self):
        return self._t

    def tick(self, requests=0, seconds=0.0):
        self._n += requests
        self._t += seconds

    def _take(self, path):
        v = self.pages[path]
        if isinstance(v, list):
            i = min(self._seen.get(path, 0), len(v) - 1)
            self._seen[path] = self._seen.get(path, 0) + 1
            return v[i]
        return v

    def get(self, path, *, raw=False, raw_if=None, did=None):
        self.calls.append(path)
        self._n += 1
        self._t += 0.5
        if path in self.fail:
            raise self.fail[path]
        if path not in self.pages:
            raise KeyError(f"測試沒有準備頁面：{path}")
        html = self._take(path)
        if raw_if is not None and raw_if(html):
            self._n += 1
            html = self._take(path)
        return html


class FakeSession:
    def __init__(self, recoverable=False, recovers_to=None):
        self._recoverable = recoverable
        self.recovered = 0
        self.saved = 0

    def is_village_html(self, html):
        return isinstance(html, str) and 'id="stockBar"' in html

    @property
    def can_recover(self):
        return self._recoverable

    def recover(self):
        self.recovered += 1
        self._recoverable = False

    def save_state(self):
        self.saved += 1


class Recorder:
    """StageIO 的假實作：記下每次呼叫；可指定哪個函式要丟例外。"""

    def __init__(self, fail=None, buildable_due=True, structure_changed=False):
        self.calls = []
        self.fail = dict(fail or {})
        self.buildable_due_value = buildable_due
        self.structure_changed = structure_changed
        self.notes = []

    def _do(self, name, *a, **k):
        self.calls.append((name, a, k))
        if name in self.fail:
            raise self.fail[name]

    def names(self):
        return [c[0] for c in self.calls]

    def of(self, name):
        return [c for c in self.calls if c[0] == name]

    def io(self):
        rec = self

        def log_actions(sh, rows):
            rec._do("log_actions", sh, list(rows))
            return len(rows)

        def write_state(sh, did, rows, updated_utc):
            rec._do("write_state", sh, did, list(rows), updated_utc)
            return len(rows)

        def append_snapshot(sh, did, row):
            rec._do("append_snapshot", sh, did, row)
            return 1

        def write_structure(sh, did, **kw):
            rec._do("write_structure", sh, did, **kw)
            from types import SimpleNamespace
            return SimpleNamespace(buildings_changed=rec.structure_changed, changes=(), initialized=(), wrote=())

        def buildable_due(sh, did, *, now):
            rec._do("buildable_due", sh, did, now=now)
            return rec.buildable_due_value

        def last_age(sh, action, did=None, result="ok", *, now=None, warn=print):
            rec._do("last_action_age_hours", sh, action)
            return None

        def disable(sh, scope, did, reason):
            rec._do("disable", sh, scope, did, reason)
            return True

        return StageIO(
            log_actions=log_actions, write_state=write_state, append_snapshot=append_snapshot,
            write_structure=write_structure, buildable_due=buildable_due, last_action_age_hours=last_age,
            disable=disable, oasis_save=lambda *a, **k: 0, oasis_load=lambda *a, **k: [],
            notify=lambda m: rec.notes.append(m), sleep=lambda s: None, now=lambda: NOW)


def make_profile():
    return ServerProfile(server_id="test-s1", base_url="https://example.invalid", tribe="gaul",
                         start_utc="2026-11-01T00:00:00Z", server_tz="Europe/London")


def make_vc(did=101, name="測試村", queue_slots=1, modes=None):
    return VillageContext(
        did=did, name=name, x=0, y=0, is_capital=False, role="resource", enabled=True, priority=100,
        build_settings=BuildSettings(target_level=10, queue_slots=queue_slots, build_order=None),
        modes=dict(modes if modes is not None else {}),
        hide_context=HideContext(home_x=0, home_y=0, oases=(), blocked=(), tribe="gaul"))


def make_rc(gateway=None, session=None, recorder=None, cfg=None, dry_flag=True, modes=None):
    rec = recorder or Recorder()
    return RunContext(cfg=dict(cfg if cfg is not None else {"main_did": 101}), profile=make_profile(),
                      tribe=get_tribe("gaul"), gateway=gateway or FakeGateway(), session=session or FakeSession(),
                      sh=object(), io=rec.io(), dry_flag=dry_flag, modes=dict(modes or {})), rec
