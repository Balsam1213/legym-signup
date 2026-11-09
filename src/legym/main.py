# -*- coding: utf-8 -*-
"""乐健体育 每周自动报名机器人 — CLI 业务入口。

用法(经根目录 register.py 分发):
  py register.py wait | dry | now | cred-set | cred-migrate | cred-clear | cred-status
"""
import os
import re
import sys
import time

from . import activity as act
from . import config as cred
from . import scheduler as sch
from .client import (BadBodyError, HttpError, LegymClient, ListIncomplete,
                     NetworkError)
from .config import (load_session, mask_phone, read_config,
                     resolve_conf_secrets, sanitize_err, session_valid,
                     save_session)
from .notifier import push

CONF = {}
CLIENT = None
_LOGFH = None


# ---------------- 日志 ----------------
def _fh():
    global _LOGFH
    if _LOGFH is None:
        os.makedirs(os.path.join(cred.APP_DIR, "logs"), exist_ok=True)
        _LOGFH = open(os.path.join(cred.APP_DIR, "logs",
                                   time.strftime("%Y%m%d") + ".log"),
                      "a", encoding="utf-8")
    return _LOGFH


def log(msg, console=True):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), sanitize_err(msg))
    _fh().write(line + "\n")
    _fh().flush()
    if console:
        print(line, flush=True)


def crash_notify(content, title="乐健报名-异常"):
    push(title, content, CONF.get("pushplus_token") or "",
         CONF.get("pushplus_topic") or "", log=log)


def notify(title, content):
    push(title, content, CONF.get("pushplus_token") or "",
         CONF.get("pushplus_topic") or "", log=log)


# ---------------- 登录 ----------------
def _login(retries=5):
    phone = str(CONF.get("phone") or "").strip()
    pwd = str(CONF.get("password") or "").strip()
    if not phone or not pwd:
        log("缺少凭据(py register.py cred-set 登记后重试),退出")
        return False
    global CLIENT
    cache = load_session()
    if cache and session_valid(cache) and cache.get("phone_mask") == mask_phone(phone):
        CLIENT = LegymClient()
        CLIENT.token = cache["accessToken"]
        try:
            CLIENT.refresh_server_offset()
        except Exception:
            pass
        log("登录: 会话缓存复用 %s tok=%s" % (mask_phone(phone), cred.mask_token(cache["accessToken"])))
        return True
    CLIENT = LegymClient()
    last = None
    for i in range(1, retries + 1):
        try:
            user = CLIENT.login(phone, pwd)
            save_session(user, phone)
            log("登录 OK: %s tok=%s" % (mask_phone(phone), mask_phone(user["accessToken"])))
            try:
                CLIENT.refresh_server_offset()
            except Exception:
                pass
            return True
        except (NetworkError, HttpError, BadBodyError) as e:
            last = e
            log("登录失败(%d/%d): %s" % (i, retries, e))
            time.sleep(2)
    log("登录彻底失败: %s" % last)
    crash_notify("登录彻底失败，本周抢报放弃。\n最后错误: %s" % sanitize_err(str(last)))
    return False


def _relogin(retries=3):
    phone = str(CONF.get("phone") or "").strip()
    pwd = str(CONF.get("password") or "").strip()
    global CLIENT
    CLIENT = LegymClient()
    for i in range(1, retries + 1):
        try:
            user = CLIENT.login(phone, pwd)
            save_session(user, phone)
            log("重登成功 tok=%s" % cred.mask_token(user["accessToken"]))
            return True
        except (NetworkError, HttpError, BadBodyError) as e:
            if i == retries:
                log("重登失败: %s" % e)
            time.sleep(1.5)
    return False


# ---------------- 列表 ----------------
def _fetch_items():
    try:
        items, results = CLIENT.activity_list(states=(0, 1, 3))
    except ListIncomplete as e:
        log("活动列表不完整: %s" % e)
        crash_notify("活动列表不完整，本轮放弃(避免盲选)。\n%s" % sanitize_err(str(e)))
        return None
    except (NetworkError, HttpError, BadBodyError) as e:
        log("活动列表失败: %s" % e)
        crash_notify("活动列表拉取失败，本轮放弃。\n%s" % sanitize_err(str(e)))
        return None
    log("活动总数(去重): %d | state=%s" % (
        len(items), ",".join("%s:%s" % (k, v) for k, v in sorted(results.items()))))
    return items


def _summarize_results(results):
    return ",".join("%s:%s" % (k, v) for k, v in sorted(results.items()))


# ---------------- 单目标执行 ----------------
def _pick_status(tgt, items):
    cands = act.filter_items(items, tgt.get("activity_keywords") or [],
                             tgt.get("start_time_hhmm", ""),
                             tgt.get("address_keywords"))
    return act.pick(cands)


def _ambig_report(tgt, cands):
    log("[%s] 候选多个(%d)，需人工确认(不盲选):" % (tgt["name"], len(cands)))
    for it in cands:
        log("   * %s" % act.fmt_item(it))
    push("乐健报名-需人工确认", "目标[%s]匹配到 %d 个活动:\n%s"
         % (tgt["name"], len(cands),
            "\n".join(act.fmt_item(c) for c in cands[:5])),
         CONF.get("pushplus_token") or "", CONF.get("pushplus_topic") or "", log=log)


def _dry(tgt, status, picked):
    if status == "ok":
        log("[%s] DRY: 不提交。目标: %s" % (tgt["name"], act.fmt_item(picked)))
    elif status == "none":
        log("[%s] DRY: 无匹配候选。" % tgt["name"])
    else:
        log("[%s] DRY: 多候选待人工确认(见上方/推送)。" % tgt["name"])


def _hammer(tgt, aid):
    """连发报名直至 成功/已报名/放弃。"""
    iv = float(tgt.get("hammer_interval_seconds", 0.45))
    give_up_min = sch.hhmm_to_min(tgt.get("give_up_time", ""))
    attempts = 0
    while True:
        time.sleep(iv)
        if give_up_min is not None and sch.now_min(CLIENT.server_off) >= give_up_min:
            log("[%s] 超过 give_up %s 仍未成功,放弃" % (tgt["name"], tgt.get("give_up_time")))
            notify("乐健报名-失败", "[%s] 超过 %s 未成功，已放弃(错过名额)。"
                   % (tgt["name"], tgt.get("give_up_time")))
            return False
        attempts += 1
        try:
            d = CLIENT.sign_up(aid)
        except HttpError as e:
            if e.status in (401, 403):
                log("[%s] try#%d token 失效(%s),重登后继续" % (tgt["name"], attempts, e.status))
                if not _relogin():
                    notify("乐健报名-失败", "[%s] token 失效且重登失败，放弃。" % tgt["name"])
                    return False
                continue
            log("[%s] try#%d HTTP %s: %s" % (tgt["name"], attempts, e.status, str(e)[:80]))
            notify("乐健报名-失败", "[%s] HTTP %s 异常，已停。\n%s"
                   % (tgt["name"], e.status, sanitize_err(str(e))))
            return False
        except NetworkError as e:
            log("[%s] try#%d 网络故障,继续重试: %s" % (tgt["name"], attempts, str(e)[:80]))
            continue
        except BadBodyError as e:
            log("[%s] try#%d 协议异常: %s" % (tgt["name"], attempts, str(e)[:100]))
            notify("乐健报名-失败", "[%s] 协议异常，已停。\n%s" % (tgt["name"], sanitize_err(str(e))))
            return False
        success = bool(d.get("success"))
        reason = str(d.get("reason", ""))
        log("[%s] try#%d reason=%s" % (tgt["name"], attempts, reason))
        if success or re.search(r"已报名|已经报名|重复报名|已参加", reason):
            notify("乐健报名-成功", "[%s]\n%s\n尝试 %d 次。" % (tgt["name"], reason, attempts))
            return True


def run_target(tgt, mode):
    """执行一个目标。返回 True 表示『已成功(或已报名)/无需提交』。"""
    name = tgt.get("name", "未命名")
    kws = tgt.get("activity_keywords") or []
    tstr = tgt.get("start_time_hhmm", "")
    open_min = sch.hhmm_to_min(tgt.get("open_time", ""))
    pre = float(tgt.get("start_hammer_seconds_before", 3))

    if mode == "dry":
        items = _fetch_items()
        if items is None:
            return False
        status, picked = _pick_status(tgt, items)
        if status == "ambiguous":
            _ambig_report(tgt, picked)
        _dry(tgt, status, picked)
        return status == "ok"

    if mode == "now":
        items = _fetch_items()
        if items is None:
            return False
        status, picked = _pick_status(tgt, items)
        if status == "none":
            log("[%s] now: 无匹配候选,退出" % name)
            notify("乐健报名-失败", "[%s] 未找到匹配活动。" % name)
            return False
        if status == "ambiguous":
            _ambig_report(tgt, picked)
            return False
        log("[%s] now: 提交报名 %s" % (name, act.fmt_item(picked)))
        return _hammer(tgt, picked["id"])

    # wait 模式: 定点抢
    items = _fetch_items()
    if items is None:
        return False
    status, picked = _pick_status(tgt, items)
    if status == "ambiguous":
        _ambig_report(tgt, picked)
        return False
    aid = picked["id"] if status == "ok" else None
    if status == "ok" and picked.get("isRegister"):
        log("[%s] 已报名(isRegister=true),跳过" % name)
        return True
    if status == "none":
        log("[%s] wait: 首查无候选(等窗口刷新)" % name)
    elif status == "ok":
        log("[%s] 预锁定: %s" % (name, act.fmt_item(picked)))

    logged_min = -1
    while True:
        time.sleep(1)
        nw = sch.now_local()
        if give_up_min is not None and sch.now_min(CLIENT.server_off) >= give_up_min:
            log("[%s] 超过 give_up %s 放弃" % (name, tgt.get("give_up_time")))
            notify("乐健报名-失败", "[%s] 等待窗口超时(>%s)，放弃。" % (name, tgt.get("give_up_time")))
            return False
        cur = sch.now_min(CLIENT.server_off)
        # 开窗前 0.15 分钟: 刷新列表锁定候选
        if aid is None and open_min is not None and cur + 0.15 >= open_min:
            items = _fetch_items()
            if items is None:
                return False
            status, picked = _pick_status(tgt, items)
            if status == "ambiguous":
                _ambig_report(tgt, picked)
                return False
            if status == "none":
                log("[%s] 开窗在即仍无候选: %s (关键词/时段配置有误?)" % (name, kws))
                notify("乐健报名-失败", "[%s] 报名窗已开但无匹配活动。\n关键词: %s 时段: %s"
                       % (name, kws, tstr))
                return False
            aid = picked["id"]
            log("[%s] 锁定: %s" % (name, act.fmt_item(picked)))
            if picked.get("isRegister"):
                log("[%s] 已报名(isRegister=true),跳过" % name)
                return True
        if aid is None or open_min is None:
            continue
        if cur < open_min - pre / 60.0:
            continue
        if nw.second == 0:
            log("[%s] 等待开窗… %s" % (name, sch.now_local().strftime("%H:%M")))
        return _hammer(tgt, aid)


# ---------------- 模式 ----------------
def _targets_of(mode):
    tds = sch.targets_for_today(CONF)
    if mode == "wait":
        if not tds:
            log("今天(%s)无 open_day 命中目标,退出" % sch.today_name())
        return tds
    return CONF.get("targets") or []


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = argv[0] if argv else "wait"
    os.chdir(cred.APP_DIR)
    global CONF
    CONF = read_config()
    resolve_conf_secrets(CONF, warn=log)
    if mode.startswith("cred-"):
        cred.cli(mode, argv[1:])
        return 0
    if mode not in ("wait", "dry", "now"):
        print(__doc__)
        return 1
    log("==== register mode=%s today=%s ====" % (mode, sch.today_name()))
    tds = _targets_of(mode)
    if not tds:
        return 0
    if not _login():
        return 2
    oks = 0
    for tgt in tds:
        try:
            if run_target(tgt, mode):
                oks += 1
        except Exception:
            import traceback
            log("目标异常: " + traceback.format_exc())
            crash_notify("[%s] 执行异常:\n%s" % (tgt.get("name"), traceback.format_exc()[:1200]))
    log("==== 注册完成 ok=%s/%d ====" % (oks, len(tds)))
    return 0
