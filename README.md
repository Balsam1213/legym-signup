# 乐健体育 每周自动报名

每周**周日 06:30**（周四活动提前4天）自动抢报指定活动的 Windows 脚本。纯 Python 协议对接，无需手机/模拟器。

## 已达成
- [x] 协议破解：v2 加密登录（AES-128-ECB，key 由时间戳推导，app 数值“402881ea7c39c5d5017c39d143a8062b”）
- [x] 真机账号登录成功（黄承业 / 西南交通大学）
- [x] 活动列表拉取（education/app/activity/getActivityList）
- [x] 真实报名成功（2026-10-18 已报 周四 19:00 南区健身跑 `{"success":true,"reason":"报名成功"}`）

## 每周自动执行（推荐）
1. 双击 `install_task.bat`（创建 Windows 计划任务：每周日 06:28 运行 `run_register.bat`）
2. 结束。之后每周日 06:29:57 自动开抢，会连发请求直到成功或 06:35 放弃。

## 手动运行
```bat
py register.py dry    干跑：登录+匹配活动，不提交
py register.py now    立即真实报名（不等 06:30，适合补报）
py register.py        等待到 06:29:57 再抢（计划任务用）
```

## 目标活动配置（config.json）
> 本文件含手机号+密码，**不入 git 仓库**（见 .gitignore）。从仓库克隆部署时：`copy config.example.json config.json` 后填入真实凭据。本机已有 config.json 正常使用。
| 键 | 值 | 说明 |
|---|---|---|
| activity_keywords | `["健身跑-周四-犀浦南区"]` | 活动名需包含的关键词（全匹配） |
| start_time_hhmm | `19:00` | 同一天的多个场次按活动开始时间区分 |
| open_time / give_up_time | `06:30` / `06:35` | 开放时刻 / 放弃时刻 |
| hammer_interval_seconds | `0.45` | 请求间隔 ≈ 2.2次/秒 |
| pushplus_token | 空 | 填了则报名结果微信推送（www.pushplus.plus） |

## 日志
- `logs\YYYYMMDD.log` 每日一份：登录、候选活动、每次提交结果
- `logs\run.out` 计划任务的综合输出

## 排错提示
| 现象 | 处理 |
|---|---|
| log 无候选活动 | 活动 naming 有调整 → 到 logs 查脚本打印的全天含关键词活动列表，改 `activity_keywords` |
| 换密码/换账号失效 | 改 `config.json` 的 phone/password |
| token 401/过期 | 每次运行都会重新登录，无需手动处理 |
| 服务器时间偏差 | 脚本已用 HTTP Date 头自动校准 |

## 协议要点（备查）
- 登录 URL `POST https://cpes.legym.cn/authorization/user/v2/manage/login`
- 请求体 `{"t":<毫秒>,"pyd":"<AES(b64)>"}`，key=DeriveKey(t)[:16]
- DeriveKey: `x=(abs(s[2:5]-s[4:8])<<s[-1])&0xFFFFFFFF; "%d%s"%(x,"402881ea7c39c5d5017c39d143a8062b")` 前 16 字节
- signDigital 留空 = 服务器不校验签名（填错反而 50004）
- 活动列表/报名均为**明文 JSON + Bearer token**，无加密；`getActivityList` `{"state":0|1|3,"page":0,"size":200}`，`signUp` `{"activityId":"<id>"}` → `data.success=true`

## 交互与测试历史文件（可删）
probe_v5/v6/v7/v8.py、probe_real/list/list2/list3/signup.py、hook_*.py、tools\、decomp_out\、apk_extract\ — 均为逆向过程产物，生产链路只依赖 api.py、register.py、legym_crypto.py、config.json。
