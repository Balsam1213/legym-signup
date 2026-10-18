# -*- coding: utf-8 -*-
"""乐健体育 每周自动报名机器人（多目标版）。

协议（已位对位破解，纯 python 无需 app）:
  登录  POST /authorization/user/v2/manage/login
        body {"t":<ms>,"pyd":"<b64 AES-128-ECB-PKCS5(gson_json, dykey(t)[:16])>"}
        dykey = "%d%s" % ((abs(s[2:5]-s[4:8])<<s[-1]) & 0xFFFFFFFF, MAGIC_APP)   s=str(t)
        解码响应 data.pyd 用 dykey(data.t)[:16]；明文即用户对象（含 accessToken）
  列表  POST /education/app/activity/getActivityList  {"state":0|1|3,"page":0,"size":200}
  报名  POST /education/app/activity/signUp  {"activityId":"<id>"} → data.success=true

调度（config.json targets[]）:
  open_day = 报名开放日（SUN→周日开报周四活动；THU→周四开报周一活动）
  wait 模式只跑『今天=open_day』的目标；now/dry 模式跑全部目标

用法:
  py register.py dry    干跑：登录+匹配+展示全部目标，不提交
  py register.py now    立即对全部目标真实报名（人工补报用）
  py register.py        按周几等待对应目标到点开抢（计划任务用）
"""
import base64
import datetime
import email.utils
import json
import os
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

BASE = "https://cpes.legym.cn/"
CONF = json.load(open("config.json", encoding="utf-8"))
WEEKDAY = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

_logfh = None


def _fh():
    global _logfh
    if _logfh is None:
        os.makedirs("logs", exist_ok=True)
        _logfh = open("logs/%s.log" % datetime.date.today().strftime("%Y%m%d"), "a", encoding="utf-8")
    return _logfh


def log(msg, console=True):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    if console:
        print(line)
    try:
        _fh().write(line + "\n")
        _fh().flush()
    except Exception:
        pass


# ---------------- 协议层 ----------------

def aes_ecb(key):
    from Crypto.Cipher import AES
    return AES.new(key, AES.MODE_ECB)


def pad5(d: bytes) -> bytes:
    n = 16 - len(d) % 16
    return d + bytes([n]) * n


def unpad5(d: bytes) -> bytes:
    if d and 1 <= d[-1] <= 16 and d[-d[-1]:] == bytes([d[-1]]) * d[-1]:
        return d[:-d[-1]]
    return d


def derive_key(ms: int) -> bytes:
    from legym_crypto import MAGIC_APP
    s = str(ms)
    x = (abs(int(s[2:5]) - int(s[4:8])) << int(s[-1])) & 0xFFFFFFFF
    return ("%d%s" % (x, MAGIC_APP)).encode()[:16]


def login_body(phone: str, password: str) -> bytes:
    ms = int(time.time() * 1000)
    plain = json.dumps({
        "entrance": "1", "password": password, "signDigital": "", "userName": phone,
        "authType": "", "baseUrl": "", "page": "", "type": "",
    }, separators=(",", ":"))
    pyd = base64.encodebytes(aes_ecb(derive_key(ms)).encrypt(pad5(plain.encode()))).decode()
    return ('{"t":%d,"pyd":"%s"}' % (ms, pyd)).encode()


def login():
    r = requests.post(BASE + "authorization/user/v2/manage/login", data=login_body(CONF["phone"], CONF["password"]),
                      headers={"Content-Type": "application/json; charset=UTF-8"}, timeout=20)
    outer = r.json()
    d = outer.get("data") or {}
    if not isinstance(d, dict) or "pyd" not in d:
        raise RuntimeError("login non-envelope: %s" % json.dumps(outer, ensure_ascii=False)[:200])
    key = derive_key(int(d["t"]))
    plain = json.loads(unpad5(aes_ecb(key).decrypt(base64.b64decode(d["pyd"]))).decode("utf-8"))
    if not isinstance(plain, dict) or not plain.get("accessToken"):
        raise RuntimeError("login fail: %s" % json.dumps(plain, ensure_ascii=False)[:300])
    return plain


def h(token, extra=None):
    hd = {"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=UTF-8"}
    if extra:
        hd.update(extra)
    return hd


def activity_list(token, states=(0, 1, 3)):
    seen = {}
    for st in states:
        try:
            r = requests.post(BASE + "education/app/activity/getActivityList",
                              data=json.dumps({"state": st, "page": 0, "size": 200}, separators=(",", ":")).encode(),
                              headers=h(token), timeout=20)
            for it in ((r.json().get("data") or {}).get("items") or []):
                seen[it["id"]] = it
        except Exception as e:
            log("list state=%d err: %s" % (st, e))
    return list(seen.values())


TOKEN = None


def hammer(aid, tc):
    global TOKEN
    interval = float(tc.get("hammer_interval_seconds", 0.45))
    give = datetime.datetime.strptime(tc["give_up_time"], "%H:%M").time()
    n = 0
    while True:
        if datetime.datetime.now().time() > give:
            return False, "超时未成功（至 %s 共 %d 次）" % (tc["give_up_time"], n), n
        n += 1
        try:
            res = requests.post(BASE + "education/app/activity/signUp",
                                data=json.dumps({"activityId": aid}, separators=(",", ":")).encode(),
                                headers=h(TOKEN), timeout=20)
            j = res.json()
            d = j.get("data") or {}
            if j.get("code") == 0 and isinstance(d, dict) and d.get("success"):
                log("报名成功! id=%s [%s]" % (aid, tc.get("name")))
                return True, "报名成功（第%d次提交）" % n, n
            reason = (d.get("reason") if isinstance(d, dict) else None) or j.get("message") or json.dumps(j, ensure_ascii=False)[:120]
            if any(k in str(reason) for k in ("已报名", "已经报名", "重复", "已参加")):
                log("视作成功（%s）" % reason)
                return True, "已报名（%s）" % reason, n
            if res.status_code in (401, 403):
                log("token 失效（http=%d），重新登录..." % res.status_code)
                TOKEN = login()["accessToken"]
                continue
            if n <= 3 or n % 20 == 0:
                log("try#%d -> %s" % (n, reason))
        except Exception as e:
            if n <= 3 or n % 20 == 0:
                log("try#%d 异常 %s" % (n, e))
        time.sleep(interval)


def hhmm(ms):
    try:
        return datetime.datetime.fromtimestamp(int(str(ms)[:13]) / 1000).strftime("%H:%M")
    except Exception:
        return "?"


def server_offset():
    try:
        r = requests.head(BASE, timeout=10)
        ds = r.headers.get("Date")
        if ds:
            srv = email.utils.parsedate_to_datetime(ds).timestamp()
            return round(srv - time.time(), 1)
    except Exception:
        pass
    return 0.0


def push(title, content):
    tok = CONF.get("pushplus_token") or ""
    if not tok:
        log("PUSH(未配置) %s | %s" % (title, content), console=False)
        return
    try:
        r = requests.post("https://www.pushplus.plus/send", json={
            "token": tok, "title": title, "content": content,
            "topic": CONF.get("pushplus_topic") or "",
        }, timeout=15)
        code = ""
        try:
            code = str(r.json().get("code"))
        except Exception:
            pass
        log("PUSH sent: %s (pushplus code=%s)" % (title, code))
    except Exception as e:
        log("PUSH err: %s" % e)


def fmt_item(it):
    return "%s | id=%s | 报名窗%s~%s | %s | %s/%s | isRegister=%s" % (
        it.get("name"), it.get("id"), hhmm(it.get("startRegisterTime")), hhmm(it.get("endRegisterTime")),
        it.get("address"), it.get("registerPeople"), it.get("limitPeopleNumber"), it.get("isRegister"))


def pick(tc, items):
    kws = tc.get("activity_keywords") or []
    tstr = (tc.get("start_time_hhmm") or "").strip()
    cands = [it for it in items
             if all(k in (it.get("name") or "") for k in kws)
             and (not tstr or hhmm(it.get("startTime")) == tstr)]
    log("[%s] 候选 %d:" % (tc.get("name"), len(cands)))
    for it in cands:
        log("  * " + fmt_item(it))
    if not cands:
        log("!! 无匹配。全天含关键词但时间/状态不符的：")
        for it in items:
            if any(k in (it.get("name") or "") for k in kws):
                log("  - " + fmt_item(it))
    return cands[0] if cands else None


def run_target(tc, mode, items, now_off):
    target = pick(tc, items)
    if target is None:
        push("乐健报名失败: 未匹配[%s]" % tc.get("name"),
             "关键词=%s 时间=%s" % (tc.get("activity_keywords"), tc.get("start_time_hhmm")))
        return 1
    log("目标: %s" % fmt_item(target))

    if mode == "dry":
        log("DRY[%s]: 不提交。" % tc.get("name"))
        return 0
    if target.get("isRegister"):
        log("[%s] 已报名（isRegister=true）" % tc.get("name"))
        push("乐健已报名 ✅ [" + tc.get("name") + "]", fmt_item(target))
        return 0

    pre = float(tc.get("start_hammer_seconds_before", 3))
    open_d = datetime.datetime.combine(datetime.date.today(),
                                       datetime.datetime.strptime(tc["open_time"], "%H:%M").time())
    if mode != "now":
        w = (open_d - datetime.timedelta(seconds=pre) - datetime.datetime.fromtimestamp(time.time() + now_off)).total_seconds()
        if w > 0:
            off_s = " ;服务器时差%+.1fs" % now_off
            log("[%s] 等待 %.1f s 到提交窗口%s" % (tc.get("name"), w, off_s))
            time.sleep(w)
    ok, msg, n = hammer(target["id"], tc)
    log("[%s] 结果: %s" % (tc.get("name"), msg))
    if ok:
        push("乐健报名成功 ✅ [" + tc.get("name") + "]", "%s\n%s" % (target.get("name"), msg))
    else:
        push("乐健报名失败 ❌ [" + tc.get("name") + "]", "%s\n%s" % (target.get("name"), msg))
    return 0 if ok else 2


def main():
    global TOKEN
    mode = sys.argv[1] if len(sys.argv) > 1 else "wait"
    today = WEEKDAY[datetime.date.today().weekday()]
    log("==== register mode=%s today=%s ====" % (mode, today))

    tok = None
    for a in range(5):
        try:
            ui = login()
            tok = ui["accessToken"]
            TOKEN = tok
            break
        except Exception as e:
            log("登录失败#%d: %s" % (a + 1, str(e)[:180]))
            time.sleep(2)
    if tok is None:
        raise RuntimeError("登录重试耗尽")
    log("登录 OK: %s|%s|tok=%.8s" % (ui.get("realName"), ui.get("schoolName"), tok))

    items = activity_list(tok)
    log("活动总数(去重): %d" % len(items))
    off = server_offset()

    tcs = CONF["targets"]
    if mode in ("now", "dry"):
        todo = tcs
    else:
        todo = [tc for tc in tcs if tc.get("open_day", "SUN").upper() == today]
        if not todo:
            log("今天(%s)无排程目标；排程日=%s" % (today, [tc.get("open_day") for tc in tcs]))
            return 0

    rc = [run_target(tc, mode, items, off) for tc in todo]
    return max(rc or [0])


if __name__ == "__main__":
    try:
        code = main() or 0
    except Exception:
        import traceback
        log("FATAL: " + traceback.format_exc())
        push("乐健脚本崩溃", traceback.format_exc()[:1500])
        code = 3
    sys.exit(code)
