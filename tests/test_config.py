# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from legym.config import (mask_phone, mask_token, sanitize_err,
                          load_session, save_session, session_valid)


class TestMasks(unittest.TestCase):
    def test_mask_phone(self):
        self.assertEqual(mask_phone("18234567447"), "182****7447")
        self.assertEqual(mask_phone("12"), "12****")

    def test_mask_token(self):
        self.assertEqual(mask_token("abcdefghij"), "abcdefgh")
        self.assertEqual(mask_token(""), "")

    def test_sanitize_password_json(self):
        s = sanitize_err('{"userName":"a","password":"SuperSecret1"}')
        self.assertNotIn("SuperSecret1", s)
        self.assertIn("******", s)

    def test_sanitize_uuid(self):
        s = sanitize_err("token 306030d2-1234-4584-9c3f-4d436c97758a end")
        self.assertNotIn("306030d2-1234", s)

    def test_sanitize_phone(self):
        s = sanitize_err("用户 18234567447 登录")
        self.assertNotIn("18234567447", s)
        self.assertIn("****", s)


class TestSessionV2(unittest.TestCase):
    def _user(self):
        return {"accessToken": "f0000000-0000-0000-0000-000000000000",
                "accessTokenExpires": 9999999999999,
                "organizationId": "org-x", "schoolId": "sch-y"}

    def test_save_load_valid(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            save_session(self._user(), "18234567447", path)
            s = load_session(path)
            self.assertEqual(s["v"], 2)
            self.assertEqual(s["phone_mask"], "182****7447")
            self.assertNotIn("refreshToken", s)
            self.assertTrue(session_valid(s))
        finally:
            os.remove(path)

    def test_v1_rejected(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"accessToken": "x", "refreshToken": "y"}, f)
        os.close(fd)
        try:
            self.assertIsNone(load_session(path))
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
