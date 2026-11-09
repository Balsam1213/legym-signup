# -*- coding: utf-8 -*-
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from legym.crypto import (build_login_body, decode_envelope, decrypt_pyd,
                          derive_key, encrypt_pyd, pad5, unpad5)

GOLD_KEY = b"600402881ea7c39c"
GOLD_HELLO = "uAAnP95HqC4irCro8c5lbw==\n"


class TestCrypto(unittest.TestCase):
    def test_derive_key_golden(self):
        # t=1760000000000 → 原生 getDyKey 实测样本
        self.assertEqual(derive_key(1760000000000), GOLD_KEY)

    def test_encrypt_pyd_golden(self):
        self.assertEqual(encrypt_pyd(b"hello", 1760000000000), GOLD_HELLO)

    def test_pad_unpad_roundtrip(self):
        for n in range(1, 40):
            raw = bytes(range(n % 256)) * 2 or b"x"
            self.assertEqual(unpad5(pad5(raw)), raw)
        raw = b"abc" * 5
        self.assertEqual(unpad5(pad5(raw)), raw)

    def test_envelope_roundtrip(self):
        ms = 1760000000000
        pyd = encrypt_pyd(json.dumps({"k": "值", "n": 7}).encode(), ms)
        env = {"t": ms, "pyd": pyd}
        plain = json.dumps(env, ensure_ascii=False)
        back = decode_envelope(plain)
        self.assertEqual(back, {"k": "值", "n": 7})

    def test_login_body_shape(self):
        body = build_login_body({"userName": "a", "password": "b", "entrance": "1"})
        s = body.decode()
        # pyd 内嵌换行（与服务端字节级对齐的设计）→ 不用严格 json.loads，宽松解析
        m = re.match(r'^\{"t":(\d+),"pyd":"([\s\S]+)"\}$', s)
        self.assertIsNotNone(m, "body 必须是 {t,pyd} 结构")
        self.assertTrue(int(m.group(1)) > 0)
        self.assertIn("\n", m.group(2))  # app 字节对齐: base64.encodebytes 自带换行

    def test_decrypt_pyd_bad_pad_tolerated(self):
        # 非法 padding 不抛异常（宽松语义）
        data = decrypt_pyd("AAAAAAAAAAAAAAAAAAAAAA==", 1760000000000)
        self.assertIsInstance(data, bytes)


if __name__ == "__main__":
    unittest.main()
