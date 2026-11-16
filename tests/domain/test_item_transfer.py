"""dm-05 item_transfer 測試：與舊 travian_transfer.decide_transfer 的 800 組離線輸出逐案比對＋個別規則。"""
import json
import os
import unittest

from travian_bot.common.decisions import TRANSFER_KINDS, ItemTransferDecision, TransferLine
from travian_bot.common.parsed import TransferItem, TransferState
from travian_bot.domain.item_transfer import TransferSettings, decide_item_transfer

GOLDEN = os.path.join(os.path.dirname(__file__), "..", "golden", "domain", "transfer.cases.json")
OLD_TO_NEW = {"no_incoming": "not_needed"}      # 其餘同名；mode_off 不在 domain


def _load():
    with open(GOLDEN, encoding="utf-8") as f:
        return json.load(f)


def state(stock=(0, 0, 0, 0), cap=(4000,) * 4, inv=(30000,) * 4, did=77):
    items = tuple(TransferItem(1000 + i, a) if a is not None else None for i, a in enumerate(inv))
    return TransferState(did, tuple(stock), tuple(cap), items)


S = TransferSettings()


class TestGolden(unittest.TestCase):
    def test_matches_old_function(self):
        cases = _load()
        self.assertEqual(len(cases), 800)
        seen = set()
        for i, c in enumerate(cases):
            st = TransferState(77, tuple(c["stock"]), tuple(c["cap"]),
                               tuple(TransferItem(1000 + k, a) if a is not None else None for k, a in enumerate(c["inv"])))
            s = TransferSettings(c["min_inventory"], c["max_gap"], c["eta_min"], c["only_on_incoming"])
            d = decide_item_transfer(tuple(c["need"]), st, c["busy"], c["eta"], s)
            exp = c["expected"]
            kind = OLD_TO_NEW.get(exp["decision"], exp["decision"])
            seen.add(kind)
            with self.subTest(i=i):
                self.assertEqual(d.kind, kind)
                self.assertEqual(d.act, kind == "transfer")
                self.assertEqual([[l.item_id, l.amount] for l in d.lines], exp["items"])
                if d.act:
                    self.assertEqual(d.village_id, 77)
                    self.assertEqual(d.targets, tuple(c["need"]))
        self.assertEqual(seen, {"transfer", "affordable", "not_needed", "queue_busy", "gap_too_big", "over_capacity",
                                "inventory_low"})


class TestRules(unittest.TestCase):
    def test_kinds_are_registered(self):
        for stt in (state(), ):
            for eta in (None, 600):
                d = decide_item_transfer((500, 0, 0, 0), stt, False, eta, S)
                self.assertIn(d.kind, TRANSFER_KINDS)

    def test_transfer_only_gap(self):
        d = decide_item_transfer((1500, 800, 0, 0), state(stock=(1000, 800, 0, 0)), False, 600, S)
        self.assertIsInstance(d, ItemTransferDecision)
        self.assertTrue(d.act)
        self.assertEqual(d.lines, (TransferLine(0, 1000, 500),))
        self.assertEqual(d.targets, (1500, 800, 0, 0))

    def test_lines_have_unique_resources_in_order(self):
        d = decide_item_transfer((1100, 1200, 1300, 1400), state(stock=(1000, 1000, 1000, 1000)), False, 600, S)
        self.assertEqual([l.resource for l in d.lines], [0, 1, 2, 3])
        self.assertEqual([l.amount for l in d.lines], [100, 200, 300, 400])

    def test_affordable_does_not_touch_inventory(self):
        d = decide_item_transfer((100, 100, 100, 100), state(stock=(100, 200, 100, 100)), False, 600, S)
        self.assertEqual((d.act, d.kind, d.lines), (False, "affordable", ()))

    def test_exposure_always_ignores_eta(self):
        a = TransferSettings(only_on_incoming=False)
        self.assertEqual(decide_item_transfer((500, 0, 0, 0), state(), False, None, a).kind, "transfer")
        self.assertEqual(decide_item_transfer((500, 0, 0, 0), state(), False, None, S).kind, "not_needed")

    def test_eta_boundary(self):
        st = state()
        self.assertEqual(decide_item_transfer((500, 0, 0, 0), st, False, 45 * 60, S).kind, "transfer")
        self.assertEqual(decide_item_transfer((500, 0, 0, 0), st, False, 45 * 60 + 1, S).kind, "not_needed")

    def test_queue_busy_before_data_checks(self):
        self.assertEqual(decide_item_transfer(None, None, True, 600, S).kind, "queue_busy")

    def test_no_data(self):
        self.assertEqual(decide_item_transfer(None, state(), False, 600, S).kind, "no_data")
        self.assertEqual(decide_item_transfer((1, 2, 3, 4), None, False, 600, S).kind, "no_data")
        self.assertEqual(decide_item_transfer((1, 2, 3), state(), False, 600, S).kind, "no_data")

    def test_gap_too_big_boundary(self):
        st = state()
        self.assertEqual(decide_item_transfer((1000, 0, 0, 0), st, False, 600, S).kind, "transfer")
        self.assertEqual(decide_item_transfer((1001, 0, 0, 0), st, False, 600, S).kind, "gap_too_big")

    def test_over_capacity_only_for_gap_resources(self):
        st = state(stock=(0, 5000, 0, 0), cap=(4000, 4000, 4000, 4000))
        self.assertEqual(decide_item_transfer((500, 4500, 0, 0), st, False, 600, S).kind, "transfer")
        self.assertEqual(decide_item_transfer((4500, 0, 0, 0), st, False, 600, TransferSettings(max_gap=9999)).kind,
                         "over_capacity")

    def test_inventory_missing_or_low(self):
        self.assertEqual(decide_item_transfer((500, 0, 0, 0), state(inv=(None, 30000, 30000, 30000)), False, 600, S).kind,
                         "inventory_low")
        self.assertEqual(decide_item_transfer((500, 0, 0, 0), state(inv=(19999, 0, 0, 0)), False, 600, S).kind,
                         "inventory_low")
        self.assertEqual(decide_item_transfer((500, 0, 0, 0), state(inv=(20000, 0, 0, 0)), False, 600, S).kind,
                         "transfer")

    def test_inventory_of_unneeded_resource_is_ignored(self):
        d = decide_item_transfer((500, 0, 0, 0), state(inv=(30000, None, None, None)), False, 600, S)
        self.assertTrue(d.act)

    def test_inventory_smaller_than_gap_blocks_even_if_min_zero(self):
        d = decide_item_transfer((900, 0, 0, 0), state(inv=(500, 0, 0, 0)), False, 600, TransferSettings(min_inventory=0))
        self.assertEqual(d.kind, "inventory_low")

    def test_non_transfer_decisions_carry_no_lines(self):
        d = decide_item_transfer((5000, 0, 0, 0), state(), False, 600, S)
        self.assertEqual((d.lines, d.village_id, d.targets), ((), None, None))


if __name__ == "__main__":
    unittest.main()


class TestDecisionsV04(unittest.TestCase):
    def test_kind_defaults_to_empty_and_old_construction_still_works(self):
        d = ItemTransferDecision(False, "x")
        self.assertEqual((d.kind, d.lines, d.village_id, d.targets), ("", (), None, None))

    def test_transfer_kinds_is_tuple_not_exported(self):
        import travian_bot.common.decisions as dec
        self.assertIsInstance(dec.TRANSFER_KINDS, tuple)
        self.assertEqual(len(set(dec.TRANSFER_KINDS)), len(dec.TRANSFER_KINDS))
        self.assertNotIn("TRANSFER_KINDS", dec.__all__)
