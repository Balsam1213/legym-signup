# 乐健体育（乐健App）每周自动报名

每周固定时段自动抢报"超市活动"（如健身跑、篮球超市等）的 Windows 脚本。纯 Python 协议对接，无需手机/模拟器持续在线。

> [!WARNING]
> ### 免责声明
> 本项目仅供**学习交流与个人自动化**使用，与乐健体育官方没有任何关联。使用本脚本请自行确保遵守所在学校/平台的相关规定与 App 使用条款，高风险设置（高频请求）请自行权衡并承担相应后果。脚本按"现状"提供，不附带任何担保。

## 工作原理
- **登录**：复刻 App 的 v2 加密登录（`AES-128-ECB`，密钥由时间戳按固定算法推导，具体见下方"协议要点"）
- **活动列表**：`education/app/activity/getActivityList`（明文 JSON + Bearer token）
- **抢报**：在报名开放时刻前 3 秒（默认 06:29:57）起以约 2.2 次/秒的频率提交 `signUp`，直到成功或放弃时刻
- **服务器时间校准**：每次运行用 HTTP Date 头自动校准本机与服务器的时间偏差
- **通知（可选）**：PushPlus 微信推送报名结果

## 快速开始
1. 安装依赖（Python 3.10+）：
   ```bat
   py -m pip install -r requirements.txt
   ```
2. 凭据存入 Windows 凭据管理器（推荐，config.json 里 phone/password 可留空）：
   ```bat
   py register.py cred-set phone
   py register.py cred-set password
   py register.py cred-status
   ```
3. 复制配置模板并填入自己的目标活动：
   ```bat
   copy config.example.json config.json
   notepad config.json
   ```
4. 安装 Windows 计划任务（每周日/周四 06:28 自动运行）：
   ```bat
   install_task.bat
   ```
5. 结束。之后每周 06:29:57 自动开抢。

## 手动运行
```bat
py register.py dry          干跑：登录+匹配活动+展示候选，不提交
py register.py now          立即真实报名（不等 06:30，适合补报）
py register.py              等待到 06:29:57 再抢（计划任务用）
py register.py cred-status  查看已存凭据
py register.py cred-set phone / cred-set password   写入凭据
py register.py cred-clear [--purge-session]         清除凭据
```

## 目标活动配置（config.json）
> config.json 含账号密码，**不入 git 仓库**（见 .gitignore）。克隆部署请用上方的模板复制步骤。

| 键 | 值 | 说明 |
|---|---|---|
| targets | 目标数组 | 支持同时盯多个活动 |
| activity_keywords | `["篮球超市-周一-犀浦-张立新"]` | 活动名需包含的每个关键词（全匹配） |
| start_time_hhmm | `"18:00"` | 同报名窗多场次时按活动开始时间精确锁定 |
| address_keywords | 可选 `["北区篮球场"]` | 仍命中多个同名候选时用地点关键词收窄；缺省=多候选时“需人工确认”（日志+推送提醒，不盲选） |
| open_day | `SUN` / `THU` / … | 报名开放日（依"提前4天"规则对应活动日） |
| start_hammer_seconds_before | `3` | 开放前多少秒开始连发 |
| give_up_time | `"06:35"` | 超过该时刻未成功则放弃 |
| hammer_interval_seconds | `0.45` | 请求间隔（秒） |
| pushplus_token | 空 | 填了则报名结果微信推送（www.pushplus.plus） |

## 项目结构
```
register.py              入口薄壳（src 加进 sys.path 后调 legym.main）
src/legym/crypto.py      登录 envelope 加解密（时间戳推导密钥）
src/legym/client.py      LegymClient：登录/列表/报名/时间校准，类型化异常
src/legym/activity.py    关键词+场次+地点筛选，pick() 三态：none/ok/ambiguous
src/legym/scheduler.py   周历与时刻计算（服务器时钟校准后的等待）
src/legym/notifier.py    PushPlus 推送（token 注入，未配置=空操作）
src/legym/config.py      配置读取 + 凭据(keyring) + 会话缓存(v2白名单) + 日志脱敏
src/legym/main.py        CLI 编排：wait/dry/now/cred-*，完整性门禁，需人工确认分支
tests/                   单元测试：py -m unittest discover tests
```

## 日志
- `logs\YYYYMMDD.log` 每日一份：登录、候选活动、每次提交结果
- `logs\run.out` 计划任务的综合输出

## 排错提示
| 现象 | 处理 |
|---|---|
| log 无候选活动 | 活动命名有调整 → 看 logs 里打印的全天候选，改 `activity_keywords` |
| 换密码/换账号 | 重新 `cred-set phone/password`（或改 `config.json`） |
| token 401/过期 | 每次运行都会重新登录，无需手动处理 |
| 服务器时间偏差 | 脚本已用 HTTP Date 头自动校准 |
| PushPlus 推送失败 | 返回 905 = 账号未实名认证（PushPlus 新规），实名后即可 |

## 协议要点（备查）
- 登录 URL `POST https://cpes.legym.cn/authorization/user/v2/manage/login`
- 请求体 `{"t":<毫秒>,"pyd":"<AES(b64)>"}`，key = DeriveKey(t)[:16]
- DeriveKey：`s=str(t毫秒); x=(abs(int(s[2:5])-int(s[4:8]))<<int(s[-1]))&0xFFFFFFFF; key前缀="%d%s"%(x,"402881ea7c39c5d5017c39d143a8062b")`
- `signDigital` 留空 = 服务器不校验签名（填错反而返回 50004）
- 活动列表/报名均为**明文 JSON + Bearer token**，无加密
- v1 明文登录接口已被服务端停用（返回 40012），必须走 v2 加密通道

## 已验证里程碑
- [x] v2 加密登录（真机账号全链路跑通）
- [x] 活动列表拉取与关键词匹配
- [x] 真实报名成功（`{"code":0,"data":{"success":true,"reason":"报名成功"}}`）
- [x] 多目标 + Windows 计划任务自动开抢

## License
以 [GPL-3.0](LICENSE) 协议开源。修改/分发请遵守协议条款并保留本声明。
