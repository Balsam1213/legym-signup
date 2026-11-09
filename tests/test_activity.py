# -*- coding: utf-8 -*-
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from legym.activity import filter_items, fmt_item, hhmm, pick


def item(name, start_ms, address="A 场", isRegister=False, aid="id-1"):
    return {"id": aid, "name": name, "startTime": start_ms,
            "address": address, "isRegister": isRegister,
            "startRegisterTime": start_ms, "endRegisterTime": start_ms,
            "registerPeople": 1, "limitPeopleNumber": 2}


class TestPick(unittest.TestCase):
    def test_pick_none(self):
        self.assertEqual(pick([]), ("none", []))

    def test_pick_ok(self):
        st, v = pick([{"id": 1}])
        self.assertEqual(st, "ok")
        self.assertEqual(v["id"], 1)

    def test_pick_ambiguous(self):
        st, vs = pick([{"id": 1}, {"id": 2}])
        self.assertEqual(st, "ambiguous")
        self.assertEqual(len(vs), 2)

    def test_keywords_time_gate(self):
        a = item("篮球超市-周一-犀浦", 86400000)   # 本地时区 hhmm 未知→仅验证不匹配时的排除路径
        res = filter_items([a], ["篮球超市"], "99:99")
        self.assertEqual(res, [])

    def test_keywords_all_match(self):
        a = item("飞盘 ABC", 1760000000000)
        res = filter_items([a], ["飞盘", "A"], "")
        self.assertEqual(len(res), 1)

    def test_address_gate(self):
        a = item("飞盘超市", 1760000000000, address="南区田径场")
        b = item("飞盘超市", 1760000000000, address="北区足球场")
        res = filter_items([a, b], ["飞盘超市"], "", ["南区"])
        self.assertEqual([x["address"] for x in res], ["南区田径场"])

    def test_hhmm_bad(self):
        self.assertEqual(hhmm(None), "")
        self.assertEqual(hhmm("x"), "")

    def test_fmt_item_no_crash(self):
        s = fmt_item(item("n", 0))
        self.assertIn("id=id-1", s)


if __name__ == "__main__":
    unittest.main()
