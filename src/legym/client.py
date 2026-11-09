# -*- coding: utf-8 -*-
"""乐健体育 HTTP 客户端 — 统一的网络接口与类型化异常。

- NetworkError: 连接层失败(超时/断网)
- HttpError:    HTTP 状态码异常(401/403/5xx…)
- BadBodyError: 响应不符合协议(非 envelope/字段缺失)
- ListIncomplete: activity_list 某些 state 在重试后仍失败(完整性门禁)
"""
import json
import time
from datetime import datetime, timezone

import requests

from .crypto import build_login_body, decode_envelope

BASE = "https://cpes.legym.cn/"
TIMEOUT = 15


class NetworkError(Exception):
    pass


class HttpError(Exception):
    def __init__(self, status, body=""):
        super().__init__("HTTP %s %s" % (status, str(body)[:160]))
        self.status = status


class BadBodyError(Exception):
    pass


class ListIncomplete(Exception):
    def __init__(self, results):
        super().__init__("活动列表不完整: %s" % results)
        self.results = results


class LegymClient:
    """一个客户端实例对应一条会话。login 后 token 可复用。"""

    def __init__(self):
        self.token = None
        self.server_off = 0.0
        self.phone = None
        self.password = None
        self._http = requests.Session()

    # ---------- 内部 ----------
    def _headers(self, extra=None):
        h = {"Authorization": "Bearer %s" % (self.token or "")}
        if extra:
            h.update(extra)
        return h

    def _post(self, path, body):
        try:
            r = self._http.post(BASE + path, data=body, headers=self._headers(
                {"Content-Type": "application/json; charset=UTF-8"}), timeout=TIMEOUT)
        except requests.RequestException as e:
            raise NetworkError(str(e))
        return r

    def _outer(self, path, body):
        r = self._post(path, body)
        if r.status_code >= 400:
            raise HttpError(r.status_code, r.text[:200])
        try:
            outer = r.json()
        except ValueError as e:
            raise BadBodyError("非 JSON 响应: %s" % str(e))
        if not isinstance(outer, dict) or "code" not in outer:
            raise BadBodyError("响应缺少 code: %s" % str(outer)[:160])
        return outer

    # ---------- 登录 ----------
    def login(self, phone, password, sign_digital=""):
        """v2 envelope 登录。返回用户对象(accessToken 在内)。"""
        self.phone, self.password = phone, password
        plain = {
            "userName": phone, "password": password, "signDigital": sign_digital,
            "entrance": "1", "authType": "", "baseUrl": "", "page": "", "type": "",
        }
        outer = self._outer("authorization/user/v2/manage/login",
                            build_login_body(plain))
        data = outer.get("data") or {}
        if not data.get("pyd"):
            raise BadBodyError("登录非 envelope 响应 code=%s msg=%s" % (
                outer.get("code"), outer.get("message")))
        user = decode_envelope(json.dumps(data, ensure_ascii=False))
        if isinstance(user, dict) and "code" in user and "data" in user and "accessToken" not in user:
            user = user.get("data") or {}
        if not user.get("accessToken"):
            raise BadBodyError("登录响应缺 accessToken")
        self.token = user["accessToken"]
        return user

    # ---------- 活动列表 ----------
    def _list_once(self, state, page, size):
        body = json.dumps({"state": state, "page": page, "size": size},
                          separators=(",", ":")).encode()
        r = self._http.post(BASE + "education/app/activity/getActivityList",
                            data=body,
                            headers=self._headers({"Content-Type": "application/json"}),
                            timeout=TIMEOUT)
        if r.status_code >= 400:
            raise HttpError(r.status_code, r.text[:200])
        d = r.json()
        if d.get("code") != 0:
            raise BadBodyError("code=%s msg=%s" % (d.get("code"), d.get("message")))
        data = d.get("data") or {}
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise BadBodyError("data.items 缺失")
        return items

    def activity_list(self, states=(0, 1, 3), page=0, size=200, retry=3):
        """抓取多个 state 并按 id 去重(后遍历的覆盖前者)。

        完整性门禁: 某个 state 重试耗尽后抛 ListIncomplete(携带各 state 结果)。
        """
        items = {}
        results = {}
        for st in states:
            batch = None
            last_err = None
            for attempt in range(1, retry + 1):
                try:
                    batch = self._list_once(st, page, size)
                    results[st] = "ok(%d)" % len(batch)
                    last_err = None
                    break
                except (NetworkError, HttpError, BadBodyError, ValueError,
                        KeyError) as e:
                    last_err = "%s:%s" % (type(e).__name__, str(e)[:80])
                    if attempt < retry:
                        time.sleep(1.5)
            if batch is None:
                raise ListIncomplete(results | {st: "FAIL(%s)" % (last_err or "?")})
            for it in batch:
                aid = it.get("id")
                if aid:
                    items[aid] = it
        return list(items.values()), results

    # ---------- 报名 ----------
    def sign_up(self, activity_id):
        body = json.dumps({"activityId": activity_id}, separators=(",", ":")).encode()
        r = self._post("education/app/activity/signUp", body)
        if r.status_code >= 400:
            raise HttpError(r.status_code, r.text[:200])
        try:
            d = r.json()
        except ValueError as e:
            raise BadBodyError("非 JSON 响应: %s" % str(e))
        if d.get("code") != 0:
            raise BadBodyError("code=%s msg=%s" % (d.get("code"), d.get("message")))
        return d.get("data") or {}

    # ---------- 时钟 ----------
    def refresh_server_offset(self):
        """以 HTTP Date 头校准与服务器时钟偏差(秒)。"""
        try:
            r = self._http.head(BASE, timeout=TIMEOUT)
            ds = r.headers.get("Date")
            if not ds:
                return self.server_off
            srv = datetime.strptime(ds, "%a, %d %b %Y %H:%M:%S GMT").replace(
                tzinfo=timezone.utc).timestamp()
            self.server_off = srv - time.time()
        except Exception:
            pass
        return self.server_off
