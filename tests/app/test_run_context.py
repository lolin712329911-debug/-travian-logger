# -*- coding: utf-8 -*-
"""ap-02 run_context（A6a1）。"""
import dataclasses
import unittest
from datetime import timezone

from travian_bot.app import run_context as RC
from travian_bot.infra.store import action_repo, config_repo, oasis_repo, snapshot_repo, state_repo

from .fakes import FakeGateway, FakeSession, Recorder, make_rc


class RealIoTest(unittest.TestCase):
    def test_real_io_binds_real_repo_functions(self):
        notes = []
        io = RC.real_io(notes.append)
        self.assertIs(io.log_actions, action_repo.log_actions)
        self.assertIs(io.write_state, state_repo.write_state)
        self.assertIs(io.append_snapshot, snapshot_repo.append_snapshot)
        self.assertIs(io.write_structure, snapshot_repo.write_structure)
        self.assertIs(io.buildable_due, snapshot_repo.buildable_due)
        self.assertIs(io.last_action_age_hours, action_repo.last_action_age_hours)
        self.assertIs(io.disable, config_repo.disable)
        self.assertIs(io.oasis_save, oasis_repo.save)
        self.assertIs(io.oasis_load, oasis_repo.load)
        io.notify("x")
        self.assertEqual(notes, ["x"])

    def test_real_now_is_aware_utc(self):
        now = RC.real_io(lambda m: None).now()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset(), timezone.utc.utcoffset(None))

    def test_stage_io_is_frozen_and_has_all_fields(self):
        io = RC.real_io(lambda m: None)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            io.notify = None
        self.assertEqual({f.name for f in dataclasses.fields(io)},
                         {"log_actions", "write_state", "append_snapshot", "write_structure", "buildable_due",
                          "last_action_age_hours", "disable", "oasis_save", "oasis_load", "notify", "sleep", "now"})


class RunContextTest(unittest.TestCase):
    def test_defaults(self):
        rc, _ = make_rc()
        self.assertTrue(rc.dry_flag)
        self.assertIsNone(rc.hero)
        self.assertEqual(rc.pages, {})
        self.assertEqual(rc.warnings, [])
        self.assertEqual(rc.modes, {})

    def test_warn_collects_without_printing_and_redacts(self):
        rc, _ = make_rc()
        rc.warn("Cookie: sessionid=SECRET123; path=/")
        self.assertEqual(len(rc.warnings), 1)
        self.assertNotIn("SECRET123", rc.warnings[0])

    def test_get_page_fetches_each_path_once(self):
        gw = FakeGateway({"dorf1.php": "A"})
        rc, _ = make_rc(gateway=gw)
        self.assertEqual(rc.get_page("dorf1.php"), "A")
        self.assertEqual(rc.get_page("dorf1.php"), "A")
        self.assertEqual(gw.calls, ["dorf1.php"])
        self.assertEqual(rc.pages["dorf1.php"], "A")

    def test_get_page_refresh_refetches(self):
        gw = FakeGateway({"dorf1.php": ["A", "B"]})
        rc, _ = make_rc(gateway=gw)
        rc.get_page("dorf1.php")
        self.assertEqual(rc.get_page("dorf1.php", refresh=True), "B")

    def test_session_like_is_satisfied_by_the_real_session_shape(self):
        from travian_bot.infra.session import Session
        for name in ("is_village_html", "can_recover", "recover", "save_state"):
            self.assertTrue(hasattr(Session, name), name)
        # staticmethod 經實例呼叫與一般方法相同
        self.assertTrue(Session.is_village_html('<div id="stockBar"></div>'))
        self.assertTrue(FakeSession().is_village_html('id="stockBar"'))


if __name__ == "__main__":
    unittest.main()
