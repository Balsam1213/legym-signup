# -*- coding: utf-8 -*-
"""日期/时刻计算 — 纯逻辑（可单测）。服务器偏差由 client.refresh_server_offset 提供。"""
import time
from datetime import datetime

WEEKDAY = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def today_name():
    return WEEKDAY[datetime.now().weekday()]


def hhmm_to_min(s):
    """'06:30' -> 390。非法/空返回 None。"""
    try:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def now_local():
    return datetime.now()


def now_min(server_off=0.0):
    """本地'当天分钟数'，可加服务器偏差。"""
    n = datetime.now()
    return n.hour * 60 + n.minute + n.second / 60.0 + server_off / 60.0


def wait_seconds(server_off=0.0):
    """距服务器下一个整秒的等待秒数(发送时刻对齐用)。"""
    return (1.0 - (time.time() + server_off) % 1.0) % 1.0


def targets_for_today(conf):
    """按 open_day 过滤出的今日目标列表。"""
    td = today_name()
    return [t for t in (conf.get("targets") or []) if t.get("open_day") == td]
