# -*- coding: utf-8 -*-
"""乐健体育 API 客户端 — 协议已破解并位对位验证。

登录:  POST /authorization/user/v2/manage/login
       body  = {"t": <毫秒>, "pyd": "<b64(AES-128-ECB-PKCS5(gson_json, dykey(t)[:16]))>"}
       dykey = "%d%s" % ((abs(s[2:5]-s[4:8])<<s[-1]) & 0xFFFFFFFF, MAGIC_APP)   (s=str(t))
       headers 仅需 Content-Type: application/json; charset=UTF-8（无需 UA/Authorization）
       signDigital 留空即可；非空必须正确否则 50004
响应:  {"code":0,"data":{"pyd":...,"t":...}} → pyd 用 dykey(data.t)[:16] 解出 JSON
token: Bearer <accessToken>
"""
import base64
import json
import sys
import time

import requests

from legym_crypto import MAGIC_APP, derive_key

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

BASE = "https://cpes.legym.cn/"
UA = "Android/14 version/3.10.3:0 browserVersion/23 platform/Google Pixel"


def _aes_decrypt(b64_text: str, key: bytes) -> bytes:
    raw = base64.b64decode(b64_text)
    c = AES_ECB(key)
    out = c.decrypt(raw)
    return strip_pk5(out)


def AES_ECB(key):
    from Crypto.Cipher import AES
    return AES.new(key, AES.MODE_ECB)


def strip_pk5(data: bytes) -> bytes:
    if data and 1 <= data[-1] <= 16:
        n = data[-1]
        if data[-n:] == bytes([n]) * n:
            return data[:-n]
    return data


def encrypt_aes_pk5(data: bytes, key: bytes) -> bytes:
    pad = 16 - len(data) % 16
    data = data + bytes([pad]) * pad
    return AES_ECB(key).encrypt(data)


def dykey_from_ms(ms: int) -> bytes:
    return derive_key(ms, MAGIC_APP)


def decode_resp(resp_json: dict):
    """解 SecurityResponse：data.pyd + data.t → 明文 JSON。"""
    d = resp_json.get("data")
    if not isinstance(d, dict) or "pyd" not in d:
        return resp_json
    t = d.get("t")
    if t is None:
        return {"_decode_error": "no t field", "_orig": resp_json}
    key = dykey_from_ms(int(t))
    if len(key) < 16:
        key = key.ljust(16, b"\x00")
    plain = _aes_decrypt(d["pyd"], key)
    try:
        return json.loads(plain.decode("utf-8"))
    except Exception as e:
        return {"_decode_error": str(e), "_plain": plain[:400], "_orig": resp_json}


def build_login_body(phone: str, password: str, sd: str = "") -> bytes:
    ms = int(time.time() * 1000)
    plain_json = json.dumps({
        "entrance": "1", "password": password, "signDigital": sd, "userName": phone,
        "authType": "", "baseUrl": "", "page": "", "type": "",
    }, separators=(",", ":"))
    pyd = base64.encodebytes(encrypt_aes_pk5(plain_json.encode(), dykey_from_ms(ms))).decode()
    return ('{"t":%d,"pyd":"%s"}' % (ms, pyd)).encode()


def login(phone: str, password: str) -> dict:
    r = requests.post(BASE + "authorization/user/v2/manage/login",
                      data=build_login_body(phone, password),
                      headers={"Content-Type": "application/json; charset=UTF-8"}, timeout=20)
    body = r.json()
    plain = decode_resp(body)
    return {"http": r.status_code, "outer": body, "plain": plain}


def auth_headers(token: str, extra: dict = None) -> dict:
    h = {"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=UTF-8"}
    if extra:
        h.update(extra)
    return h


if __name__ == "__main__":
    conf = json.load(open("config.json", encoding="utf-8"))
    res = login(conf["phone"], conf["password"])
    print("http:", res["http"])
    p = res["plain"]
    if isinstance(p, dict) and p.get("code") == 0:
        d = p.get("data") or {}
        keep = {k: d.get(k) for k in ("accessToken", "refreshToken", "userId", "organizationId",
                                      "schoolId", "schoolName", "realName", "nickName",
                                      "accessTokenExpires", "tokenType", "uuasId")}
        print(keep)
        json.dump(d, open("session.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("session saved -> session.json")
    else:
        print("PLAIN:", json.dumps(p, ensure_ascii=False)[:800])
