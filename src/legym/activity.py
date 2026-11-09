# -*- coding: utf-8 -*-
"""活动筛选与选择 — 纯逻辑，不发请求（可单测）。

pick() 三态结果:
  ("ok", item)    唯一目标
  ("none", [])    一个候选都没有
  ("ambiguous", [item, ...])  >=2 候选，人工确认
"""
import time


def hhmm(ms):
    try:
        return time.strftime("%H:%M", time.localtime(int(ms) / 1000))
    except Exception:
        return ""


def keywords(item, kws, tstr, addr_kws=None):
    """item 是否包含全部关键词且开始时间(HH:MM)匹配。addr_kws 非空时还需全部命中 address。"""
    if kws and not all(k in item.get("name", "") for k in kws):
        return False
    if not tstr or hhmm(item.get("startTime")) == tstr:
        addr = item.get("address", "") or ""
        for ak in (addr_kws or []) if (addr_kws or []) else []:
            if ak not in addr:
                return False
        return True
    return False


def filter_items(items, kws, tstr, addr_kws=None):
    return [it for it in items if keywords(it, kws, tstr, addr_kws)]


def pick(cands):
    """三态判定。"""
    if not cands:
        return ("none", [])
    if len(cands) == 1:
        return ("ok", cands[0])
    return ("ambiguous", cands)


def fmt_item(it):
    return "%s | id=%s | 报名窗%s~%s | %s | %s/%s | isRegister=%s" % (
        it.get("name"), it.get("id"), hhmm(it.get("startRegisterTime")),
        hhmm(it.get("endRegisterTime")), it.get("address"),
        it.get("registerPeople"), it.get("limitPeopleNumber"), it.get("isRegister"))
