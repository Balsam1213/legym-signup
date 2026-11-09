# -*- coding: utf-8 -*-
"""PushPlus 微信推送 — token/topic 由调用方注入(凭据不进本模块)。"""
import requests

from .config import sanitize_err as san


def push(title, content, token, topic="", log=None):
    """发送推送。token 为空时仅记日志(不发送)。返回是否成功。"""

    def _lg(msg):
        if log:
            log(msg)

    if not token:
        _lg("PUSH(未配置) %s | %s" % (title, content))
        return False
    try:
        r = requests.post("https://www.pushplus.plus/send", json={
            "token": token, "title": title, "content": content,
            "topic": topic or "",
        }, timeout=15)
        code = ""
        try:
            code = str(r.json().get("code"))
        except Exception:
            pass
        _lg("PUSH sent: %s (pushplus code=%s)" % (title, code))
        return code == "200"
    except Exception as e:
        _lg("PUSH err: %s" % san(str(e)))
        return False
