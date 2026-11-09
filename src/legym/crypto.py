# -*- coding: utf-8 -*-
"""乐健体育 v2 登录加密 — 已与 app native 实现位对位验证。

app 侧 NativeLib.getDyKey: keyStr = "%d%s" % (x, MAGIC_APP)
其中 x = (abs(int(s[2:5]) - int(s[4:8])) << int(s[-1])) & 0xFFFFFFFF, s = str(毫秒时间戳)

登录请求 (SecurityRequestBodyConverter):
  body = {"t": <毫秒 number>, "pyd": "<base64(AES-128-ECB-PKCS5(gson_json, key[:16]))>"}
  pyd  = android Base64.DEFAULT 风格: 76 字符折行 + 尾部 \n (python base64.encodebytes 一致)
"""
import base64
import json
import time

from Crypto.Cipher import AES

MAGIC_KERNEL = "cee1833ccb83418092ebd3f113cbd9c8"  # f.m.f.j.c retrofit 链(getDyKey 前身,登录不走它)
MAGIC_APP = "402881ea7c39c5d5017c39d143a8062b"     # com.legym.security 链(实际登录用)


def pad5(data: bytes) -> bytes:
    """PKCS5Padding 填充。"""
    n = 16 - len(data) % 16
    return data + bytes([n]) * n


def unpad5(data: bytes) -> bytes:
    """PKCS5Padding 去填充(宽松:越界/非法值按原文返回)。"""
    if not data or len(data) % 16:
        return data
    n = data[-1]
    if not (1 <= n <= 16) or data[-n:] != bytes([n]) * n:
        return data
    return data[:-n]


def derive_key(ms: int, magic: str = MAGIC_APP) -> bytes:
    s = str(ms)
    a, b, last = int(s[2:5]), int(s[4:8]), int(s[-1])
    x = (abs(a - b) << last) & 0xFFFFFFFF
    return ("%d%s" % (x, magic)).encode()[:16]


def aes_ecb(key: bytes):
    return AES.new(key, AES.MODE_ECB)


def encrypt_pyd(plain: bytes, ms: int, magic: str = MAGIC_APP) -> str:
    c = aes_ecb(derive_key(ms, magic))
    return base64.encodebytes(c.encrypt(pad5(plain))).decode()  # android Base64.DEFAULT 等价


def decrypt_pyd(b64: str, ms: int, magic: str = MAGIC_APP):
    c = aes_ecb(derive_key(ms, magic))
    return unpad5(c.decrypt(base64.b64decode(b64)))


def build_login_body(plain_obj: dict, magic: str = MAGIC_APP) -> bytes:
    """plain_obj -> v2 envelope body。t 为毫秒数字，pyd 为密文 b64。"""
    ms = int(time.time() * 1000)
    pyd = encrypt_pyd(json.dumps(plain_obj, separators=(",", ":")).encode(), ms, magic)
    return ('{"t":%d,"pyd":"%s"}' % (ms, pyd)).encode()


def decode_envelope(plain: str):
    """解服务端 envelope {"t":ms,"pyd":b64} (响应层用 data.t 作为密钥种子)。"""
    o = json.loads(plain)
    t, pyd = o.get("t"), o.get("pyd")
    if t is None or not pyd:
        raise ValueError("envelope missing t/pyd: %s" % plain[:120])
    return json.loads(decrypt_pyd(pyd, int(t)).decode("utf-8", "replace"))
