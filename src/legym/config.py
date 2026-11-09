# -*- coding: utf-8 -*-
"""配置/凭据/会话缓存 — 统一入口（原 legym_creds.py + api.py 会话部分）。

- 凭据: Windows Credential Manager (keyring) 优先, config.json 兜底
- 脱敏: mask_phone / mask_token / sanitize_err
- 会话: session.json 白名单瘦身 v2 (TTL 30 天, 绝不存 refreshToken)
"""
import json
import os
import re
import time

SERVICE = "legym-signup"
FIELDS = ("phone", "password", "pushplus_token")

# 支持脚本位于 <root>/src/legym/config.py → 根目录上溯 3 层
APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SESSION_TTL_MS = 30 * 24 * 3600 * 1000  # 30 天强制重登

# accessToken / refreshToken 为标准 UUID 格式（带连字符）；活动 id 为 32 位无连字符 hex，不受影响
_RE_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_RE_PHONE = re.compile(r"\b(1[3-9]\d)\d{4}(\d{4})\b")
_RE_PASSWORD = re.compile(r'(["\']?password["\']?\s*[:=]\s*["\'])([^"\']{1,80})(["\'])', re.I)
_RE_BEARER = re.compile(r"(Bearer\s+)[!-~]{16,}")


def mask_phone(v):
    v = str(v or "").strip()
    m = re.match(r"^(1[3-9]\d)\d{4}(\d{4})$", v)
    return (m.group(1) + "****" + m.group(2)) if m else (v[:3] + "****" if v else "")


def mask_token(v):
    return str(v or "")[:8]


def sanitize_err(msg):
    """日志/异常信息脱敏：密码、Bearer/UUID token、手机号。"""
    s = str(msg)
    s = _RE_PASSWORD.sub(lambda m: m.group(1) + "******" + m.group(3), s)
    s = _RE_BEARER.sub(r"\1<masked>", s)
    s = _RE_UUID.sub("<tok-masked>", s)
    s = _RE_PHONE.sub(r"\1****\2", s)
    return s


# ---------------- keyring (Windows Credential Manager) ----------------

def backend_ok():
    try:
        import keyring
        kr = keyring.get_keyring()
        return "fail" not in type(kr).__name__.lower() and getattr(kr, "priority", 0) > 0
    except Exception:
        return False


def set_cred(name, value):
    import keyring
    keyring.set_password(SERVICE, name, value)


def get_cred(name):
    if not backend_ok():
        return None
    try:
        import keyring
        return keyring.get_password(SERVICE, name) or None
    except Exception:
        return None


def del_cred(name):
    try:
        import keyring
        keyring.delete_password(SERVICE, name)
        return True
    except Exception:
        return False


def resolve_conf_secrets(conf, warn=None):
    """凭据解析：keyring 优先 → config.json 后备（打掩码警告）。就地填充 conf。"""
    okb = backend_ok()
    for f in FIELDS:
        kv = get_cred(f) if okb else None
        cv = str(conf.get(f) or "").strip()
        if kv:
            conf[f] = kv
            if cv and warn:
                warn("凭据管理器已有 %s；config.json 中残留旧值建议运行 cred-migrate 清理" % f)
        else:
            conf[f] = cv
            if cv and warn:
                warn("凭据管理器中无 %s，暂用 config.json 值（提示：建议尽快运行 cred-migrate）" % f)
    if not okb and warn:
        warn("keyring 后端不可用：本轮凭据仅来自 config.json（如存在）")
    return conf


# ---------------- config.json ----------------

def conf_path():
    return os.path.join(APP_DIR, "config.json")


def read_config():
    with open(conf_path(), encoding="utf-8") as f:
        return json.load(f)


# ---------------- session.json 缓存 (v2 瘦身) ----------------

def session_path():
    return os.path.join(APP_DIR, "session.json")


def load_session(path=None):
    p = path or session_path()
    try:
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict) or d.get("v") != 2:
            return None  # v1 全量会话不再受信任
        return d
    except Exception:
        return None


def session_valid(s):
    if not s:
        return False
    if not s.get("accessToken") or not s.get("phone_mask"):
        return False
    now = int(time.time() * 1000)
    exp = min(int(s.get("expires_ms") or 0),
              int(s.get("saved_at") or 0) + SESSION_TTL_MS)
    return exp > now


def save_session(user, phone, path=None):
    s = {
        "v": 2,
        "accessToken": user.get("accessToken"),
        "expires_ms": int(user.get("accessTokenExpires") or 0),
        "org": user.get("organizationId"),
        "school": user.get("schoolId"),
        "phone_mask": mask_phone(phone),
        "saved_at": int(time.time() * 1000),
    }
    with open(path or session_path(), "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False)
    return s


# ---------------- CLI ----------------

def cred_set():
    import getpass
    print("写入 Windows 凭据管理器（service=%s），输入不回显。" % SERVICE)
    phone = input("phone(手机号): ").strip()
    pwd = getpass.getpass("password: ")
    ppt = getpass.getpass("pushplus_token(可留空): ").strip() or ""
    written = []
    if phone:
        set_cred("phone", phone)
        written.append("phone")
    if pwd:
        set_cred("password", pwd)
        written.append("password")
    if ppt:
        set_cred("pushplus_token", ppt)
        written.append("pushplus_token")
    print("已写入:", ", ".join(written) if written else "(无)")


def cred_migrate():
    conf = json.load(open(conf_path(), encoding="utf-8"))
    moved = []
    for f in FIELDS:
        v = str(conf.get(f) or "").strip()
        if v:
            set_cred(f, v)
            conf[f] = ""
            moved.append(f)
    if moved:
        json.dump(conf, open(conf_path(), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("已迁入凭据管理器并清空 config.json 字段:", ", ".join(moved))
    else:
        print("config.json 无可迁移字段（可能已迁移过）")
    try:
        old = json.load(open(session_path(), encoding="utf-8"))
        if isinstance(old, dict) and old.get("v") != 2:
            os.remove(session_path())
            print("已清除旧版全量 session.json（下次登录将重建 v2 瘦身缓存）")
    except Exception:
        pass
    cred_status()


def cred_clear(purge_session=False):
    for f in FIELDS:
        print("  %-14s %s" % (f, "已删除" if del_cred(f) else "无此条目"))
    if purge_session:
        try:
            os.remove(session_path())
            print("已删除 session.json")
        except OSError:
            print("session.json 不存在")


def cred_status():
    print("凭据后端:", "Windows Credential Manager (keyring)" if backend_ok() else "不可用 → 退回 config.json")
    for f in FIELDS:
        v = get_cred(f)
        print("  %-14s %s" % (f, ("已存储 len=%d" % len(v)) if v else "无"))


def cli(cmd, args=None):
    args = args or []
    if cmd == "cred-set":
        cred_set()
    elif cmd == "cred-migrate":
        cred_migrate()
    elif cmd == "cred-clear":
        cred_clear(purge_session=("--purge-session" in args))
    elif cmd == "cred-status":
        cred_status()
    else:
        raise SystemExit("未知子命令: %s" % cmd)
