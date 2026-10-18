# -*- coding: utf-8 -*-
"""乐健体育 v2 登录加密模块 — 已与 app native 实现位对位验证。

两层 magic:
- kernel f.m.b.h.a.c(long):  "%d%s" % (x, MAGIC_KERNEL)   ← f.m.f.j.c retrofit 链 (getDyKey 前身)
- app   NativeLib.getDyKey:  "%d%s" % (x, MAGIC_APP)      ← com.legym.security 链 (实际登录用!)
其中 x = (abs(int(s[2:5]) - int(s[4:8])) << int(s[-1])) & 0xFFFFFFFF, s = str(毫秒时间戳)

登录请求 (SecurityRequestBodyConverter):
  body = {"t": <毫秒 number>, "pyd": "<base64(AES-128-ECB-PKCS5(gson_json, key[:16]))>"}
  key   = getDyKey(str(t))[:16] 的 UTF-8 字节
  pyd   = android Base64.DEFAULT 风格: 76 字符折行 + 尾部 \n (python base64.encodebytes 一致)
"""
import base64
import json
import time

from Crypto.Cipher import AES

MAGIC_KERNEL = "cee1833ccb83418092ebd3f113cbd9c8"
MAGIC_APP = "402881ea7c39c5d5017c39d143a8062b"


def derive_key(ms: int, magic: str = MAGIC_APP) -> bytes:
    s = str(ms)
    a, b, last = int(s[2:5]), int(s[4:8]), int(s[-1])
    x = (abs(a - b) << last) & 0xFFFFFFFF
    return ("%d%s" % (x, magic)).encode()[:16]


def encrypt_pyd(plain: bytes, ms: int, magic: str = MAGIC_APP) -> str:
    key = derive_key(ms, magic)
    c = AES.new(key, AES.MODE_ECB)
    pad = 16 - len(plain) % 16
    data = plain + bytes([pad]) * pad
    out = c.encrypt(data)
    return base64.encodebytes(out).decode()          # android Base64.DEFAULT 等价


def build_login_body(plain_obj: dict, magic: str = MAGIC_APP) -> bytes:
    """plain_obj -> v2 envelope body. t 为毫秒数字, pyd 为密文 b64。"""
    ms = int(time.time() * 1000)
    pyd = encrypt_pyd(json.dumps(plain_obj, separators=(",", ":")).encode(), ms, magic)
    return ('{"t":%d,"pyd":"%s"}' % (ms, pyd)).encode()


if __name__ == "__main__":
    # 自检：来自 native 的位对位样本
    ms = 1760000000000
    plain = b"hello"
    assert encrypt_pyd(plain, ms) == "uAAnP95HqC4irCro8c5lbw==\n", encrypt_pyd(plain, ms)
    print("selfcheck OK")
