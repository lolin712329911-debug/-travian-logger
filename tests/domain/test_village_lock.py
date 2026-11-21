import unittest

from travian_bot.common.decisions import LOCK_KINDS, LockDecision
from travian_bot.common.models import ValidationError, VillageLock
from travian_bot.domain import village_lock as VL

T = "2026-11-18T08:15:30Z"


class DecideLock(unittest.TestCase):
    def test_first_run_records(self):
        for lock in (None, VillageLock(), VillageLock(None, None)):
            d = VL.decide_lock(lock, 7)
            self.assertEqual((d.kind, d.record), ("ok", True))

    def test_match_ok_no_record(self):
        d = VL.decide_lock(VillageLock(7, T), 7)
        self.assertEqual((d.kind, d.record), ("ok", False))

    def test_mismatch_skips_and_names_both(self):
        d = VL.decide_lock(VillageLock(7, T), 9)
        self.assertEqual((d.kind, d.record), ("skip", False))
        self.assertIn("7", d.reason)
        self.assertIn("9", d.reason)

    def test_unknown_active_never_records(self):
        for bad in (None, 0, -3, True, "7", 7.0):
            for lock in (None, VillageLock(7, T)):
                d = VL.decide_lock(lock, bad)
                self.assertEqual((d.kind, d.record), ("skip", False), (bad, lock))

    def test_kinds_in_domain(self):
        self.assertEqual(set(LOCK_KINDS), {"ok", "skip"})
        self.assertIsInstance(VL.decide_lock(None, 1), LockDecision)


class RecordMain(unittest.TestCase):
    def test_creates(self):
        self.assertEqual(VL.record_main(5, T), VillageLock(5, T))
        self.assertEqual(VL.record_main(5, f"  {T} "), VillageLock(5, T))
        self.assertEqual(VL.record_main(5, T, VillageLock()), VillageLock(5, T))

    def test_read_only_after_first(self):
        old = VillageLock(3, "2026-11-01T00:00:00Z")
        self.assertIs(VL.record_main(5, T, old), old)

    def test_rejects_bad_input(self):
        for did in (None, 0, -1, True, "5"):
            with self.assertRaises(ValidationError):
                VL.record_main(did, T)
        for t in (None, "", "  ", 123):
            with self.assertRaises(ValidationError):
                VL.record_main(5, t)

    def test_roundtrip_with_decide(self):
        lock = VL.record_main(5, T)
        self.assertEqual(VL.decide_lock(lock, 5).kind, "ok")
        self.assertEqual(VL.decide_lock(lock, 6).kind, "skip")


if __name__ == "__main__":
    unittest.main()
