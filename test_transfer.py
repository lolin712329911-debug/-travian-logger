import unittest
from travian_transfer import *

# 由使用者貼的真實 graphql 回應縮減（只留需要的欄位；數字與 id 皆為實測值）
RESP = {"data": {"ownPlayer": {
    "hero": {"inventory": [
        {"id": 879843, "amount": 38279, "typeId": 145}, {"id": 879844, "amount": 43928, "typeId": 146},
        {"id": 879845, "amount": 41033, "typeId": 147}, {"id": 879846, "amount": 42435, "typeId": 148},
        {"id": 985121, "amount": 80, "typeId": 106}]},
    "village": {"id": 65222, "name": "x", "resources": {
        "lumberStock": 74, "clayStock": 217, "ironStock": 255, "cropStock": 327,
        "maxStorageCapacity": 4000, "maxCropStorageCapacity": 3100}}}}}
HTML = "onclick=\"window.Travian.React.Hero.openResourceTransfer({\n targetResourceAmount: {\n lumber: 910, clay: 1170,\n iron: 910, crop: 260\n },"
INC = dict(mode="incoming_only")


class T(unittest.TestCase):
    def setUp(self):
        self.st = parse_state(RESP)
        self.cfg = TransferConfig(mode="incoming_only")

    def test_parse(self):
        self.assertEqual(self.st.village_id, 65222)
        self.assertEqual(self.st.inventory["crop"]["id"], 879846)
        self.assertEqual(self.st.capacity["crop"], 3100)
        self.assertEqual(parse_target_amounts(HTML), dict(lumber=910, clay=1170, iron=910, crop=260))
        self.assertIsNone(parse_target_amounts("<html></html>"))
        self.assertEqual(parse_state(RESP["data"]).village_id, 65222)
        with self.assertRaises(ValueError):
            parse_state({"data": {}})

    def test_config(self):
        self.assertEqual(parse_config({}).mode, "off")
        self.assertEqual(parse_config({"hero_transfer_mode": " Incoming_Only "}).mode, "incoming_only")
        self.assertEqual(parse_config({"hero_transfer_mode": "true"}).mode, "off")
        self.assertEqual(parse_config({"hero_transfer_min": "abc"}).min_inventory, 20000)

    def test_gates(self):
        t = dict(lumber=100, clay=100, iron=100, crop=100)
        self.assertEqual(decide_transfer(TransferConfig(), 60, False, t, self.st).decision, "mode_off")
        self.assertEqual(decide_transfer(self.cfg, None, False, t, self.st).decision, "no_incoming")
        self.assertEqual(decide_transfer(self.cfg, 46 * 60, False, t, self.st).decision, "no_incoming")
        self.assertEqual(decide_transfer(self.cfg, 45 * 60, True, t, self.st).decision, "queue_busy")
        self.assertEqual(decide_transfer(self.cfg, 60, False, None, self.st).decision, "no_data")
        always = TransferConfig(mode="always")
        self.assertNotEqual(decide_transfer(always, None, False, t, self.st).decision, "no_incoming")

    def test_affordable(self):
        t = dict(lumber=74, clay=100, iron=255, crop=300)
        self.assertEqual(decide_transfer(self.cfg, 60, False, t, self.st).decision, "affordable")

    def test_transfer_gap_le_1000(self):  # 缺口 26+0+45+0 = 71
        t = dict(lumber=100, clay=100, iron=300, crop=300)
        p = decide_transfer(self.cfg, 60, False, t, self.st)
        self.assertEqual(p.decision, "transfer")
        self.assertEqual([(i["itemId"], i["amount"]) for i in p.items], [(879843, 26), (879845, 45)])
        self.assertTrue(all(i["action"] == "inventory" and i["villageId"] == 65222 for i in p.items))

    def test_gap_too_big(self):  # 農場 L5->L6：缺口 836+953+655+0 > 1000
        t = dict(lumber=910, clay=1170, iron=910, crop=260)
        self.assertEqual(decide_transfer(self.cfg, 60, False, t, self.st).decision, "gap_too_big")
        loose = TransferConfig(mode="incoming_only", max_gap=5000)
        self.assertEqual(decide_transfer(loose, 60, False, t, self.st).decision, "transfer")

    def test_inventory_low_and_capacity(self):
        t = dict(lumber=100, clay=100, iron=300, crop=300)
        low = TransferConfig(mode="incoming_only", min_inventory=50000)
        self.assertEqual(decide_transfer(low, 60, False, t, self.st).decision, "inventory_low")
        big = dict(lumber=4500, clay=100, iron=100, crop=100)
        self.assertEqual(decide_transfer(TransferConfig(mode="incoming_only", max_gap=99999), 60, False, big, self.st).decision, "over_capacity")

    def test_only_needed_resources_checked(self):  # 不缺的資源庫存再低也不影響
        st = parse_state(RESP); st.inventory["clay"]["amount"] = 5
        t = dict(lumber=100, clay=100, iron=300, crop=300)
        self.assertEqual(decide_transfer(self.cfg, 60, False, t, st).decision, "transfer")

    def test_execute(self):
        t = dict(lumber=100, clay=100, iron=300, crop=300)
        p = decide_transfer(self.cfg, 60, False, t, self.st)
        calls = []
        after = parse_state(RESP); after.stock.update(lumber=100, iron=300)
        r = execute_transfer(p, t, calls.append, lambda: after)
        self.assertTrue(r.ok); self.assertEqual(len(calls), 2)
        r2 = execute_transfer(p, t, lambda x: None, lambda: self.st)   # 沒到位
        self.assertFalse(r2.ok)
        def boom(x): raise RuntimeError("500")
        r3 = execute_transfer(p, t, boom, lambda: after)
        self.assertFalse(r3.ok); self.assertEqual(r3.sent, [])
        self.assertFalse(execute_transfer(Plan("gap_too_big"), t, calls.append, lambda: after).ok)

if __name__ == "__main__":
    unittest.main(verbosity=1)
