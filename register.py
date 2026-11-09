# -*- coding: utf-8 -*-
"""乐健体育 每周自动报名机器人 — CLI 入口。

业务实现在 src/legym/ 包内（协议加密、HTTP 客户端、活动筛选、调度、通知、配置）。
用法: py register.py [wait|dry|now|cred-set|cred-migrate|cred-clear|cred-status]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from legym.main import crash_notify, log, main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        tb = traceback.format_exc()
        try:
            log("FATAL: " + tb)
        except Exception:
            pass
        try:
            crash_notify("程序崩溃:\n" + tb[:1500])
        except Exception:
            pass
        sys.exit(3)
