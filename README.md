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
4. 安装 Windows 计划任务（每周日/周四 06:28 自动运行，自带睡眠自动唤醒；双击后允许 UAC 提权）：
   ```bat
   install_task.bat
   ```
5. 结束。之后每周 06:29:57 自动开抢。电脑保持**睡眠**即可被自动唤醒；习惯彻底关机或担心网络未就绪，请看下方「自动开机引导」与「网络就绪指引」。

## 自动开机引导

报名在清晨 06:29:57 开抢，电脑此时未必醒着。整条时间链：**开机/唤醒（≤06:25）→ 网络就绪（见下一节）→ 计划任务 06:28 启动 → 06:29:57 开抢**。按电脑过夜状态选方案：

| 电脑过夜状态 | 方案 |
|---|---|
| 睡眠/休眠（屏幕灭了但没关机） | 方案A：睡眠自动唤醒（推荐，装完任务即生效） |
| 彻底关机 | 方案B：BIOS RTC 定时开机 |
| 笔记本 | 基本只有方案A（多数笔记本 BIOS 无 RTC 定时开机） |

### 方案A：睡眠/休眠自动唤醒（推荐）

`install_task.bat` 注册的任务已自带「唤醒计算机运行此任务」+「不管用户是否登录都运行」+「错过补跑」，无需进 BIOS。还需两步核对：

1. 确认电源计划允许「唤醒计时器」（笔记本用电池时默认关闭；插电的台式机通常已开启）：
   ```bat
   powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
   powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
   powercfg /setactive SCHEME_CURRENT
   ```
2. 自测一次——临时把触发时间改到 2 分钟后，睡眠观察是否自动唤醒并运行（非报名日只记一行「无 open_day 命中目标」即正常）；测完重跑 `install_task.bat` 恢复 06:28：
   ```powershell
   Set-ScheduledTask -TaskName LegymSUN -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2))
   ```
   醒来后用 `powercfg /lastwake` 查看唤醒源（应显示计划任务），`logs\run.out` 看运行输出。

   > 报名日当天（如周四）自测会额外走一遍登录并因已过放弃时刻而记「放弃」/推送一条失败通知，**并未真正报名**，属正常；非报名日自测最干净。

> [!NOTE]
> 睡眠 ≠ 关机：唤醒能力对「彻底关机」及 Windows「快速启动」无效，那种场景用方案B。夜间 Windows 更新自动重启后任务仍会补跑，不受影响。笔记本睡前插上电源最稳。

### 方案B：BIOS RTC 定时开机（彻底关机也能开）

1. 先照常运行 `install_task.bat`——开机后由计划任务接手，任务按「不管用户是否登录都运行」注册，**无需设置 Windows 自动登录**
2. 开机进 BIOS 开启 RTC 定时上电，时间设为**每天 06:15**（BIOS 多数只支持「每天」或「单次」；宽带拨号要留 1-2 分钟，见下一节。非报名日开机后无人操作，建议把 Windows 电源选项的睡眠时间设短，让它自己睡回去）

   | 主板/整机品牌 | BIOS 常见路径 |
   |---|---|
   | 华硕 ASUS | Advanced → APM（高级电源管理） → RTC 自动开机 |
   | 微星 MSI | Settings → 高级 → Wake Up Event Setup → Resume By RTC Alarm |
   | 技嘉 GIGABYTE | Power → Resume by Alarm / RTC Alarm |
   | 联想 Lenovo | Power → Automatic Power On → Wake Up on RTC（部分机型在 Security 菜单） |
   | 戴尔 Dell | Power Management → RTC Wake（通常仅每天/工作日等固定模式） |
   | 惠普 HP | Power → Hardware Power Management → RTC (Real Time Clock) Alarm |

   > 具体菜单位置因机型/BIOS 版本差异较大，找不到就搜「品牌 + 主板型号 + RTC 定时开机」。
3. 可选加固：BIOS 里把「Restore AC Power Loss / AC Power Recovery」设为 `Power On`，停电后来电自动开机。

## 网络就绪指引（开机后网络怎么来）

自动开机只解决「电脑醒着」，06:28 前还需要网络就绪。按上网方式对照：

| 上网方式 | 要做什么 |
|---|---|
| 有线网线直连 | 插好即通，无需设置 |
| WiFi | 开机/唤醒后自动重连，无需设置；确认处于「自动连接」即可（见下） |
| 手机热点 | **前一晚提前打开热点并保持充电**，电脑到点自动连上（见下） |
| 宽带连接 PPPoE | **多一步**：注册开机自动拨号任务（见下） |

- **WiFi**：联网一次后 Windows 会记住并自动重连。检查/补设自动连接：
  ```bat
  netsh wlan show profiles
  netsh wlan set profileparameter name="你的WiFi名" connectionmode=auto
  ```
- **手机热点**：电脑侧与 WiFi 相同、自动连上。热点本身要先存在——部分手机「长时间无设备连接自动关闭热点」，请在手机热点设置里关闭该行为；前一晚开好热点、插上电源睡下即可。
- **宽带连接（PPPoE 拨号）**：开机/唤醒后**不会自动拨号**，管理员运行一次以下命令注册开机拨号任务（名称/账号/密码换成自己的）：
  ```bat
  schtasks /Create /F /TN "LegymDial" /SC ONSTART /RU SYSTEM /TR "rasdial 宽带连接 宽带账号 宽带密码"
  ```
  - 创建宽带连接时建议勾选「允许所有用户使用此连接」，否则 SYSTEM 身份读不到拨号配置
  - 不想把密码写进任务：宽带连接属性里勾选「记住密码」后，把 `/TR` 换成 `rasdial 宽带连接`
  - 验证：`schtasks /Run /TN LegymDial` 后执行 `rasdial`，应显示已连接
  - 宽带 + 方案A睡眠组合：唤醒后宽带可能不会自动重拨，此类用户建议优先 WiFi/有线；确要用的，在宽带连接属性 → 选项里把「挂断前的空闲时间」设为「从不」，并自测一次唤醒后的网络

## 卸载与痕迹清除

不再使用时，三步彻底清除，不留自启动项、服务或后台进程：

1. 双击 `uninstall_task.bat`（UAC 提权，删除 LegymSUN / LegymTHU / LegymDial 全部计划任务）
2. 清除凭据与会话缓存（Windows 凭据管理器里的手机号/密码 + session.json）：
   ```bat
   py register.py cred-clear --purge-session
   ```
3. 删除项目文件夹本身（config.json 含手机号密码，随文件夹一起删除；logs 亦在其中）

可选：连 Python 依赖一并移除 `py -m pip uninstall -r requirements.txt`（其他项目共用这些依赖就跳过）。
若用过方案B（BIOS RTC 定时开机），请在 BIOS 里手动关闭 RTC——软件无法代劳，否则每天仍会定时开机。

### 本项目会留下哪些系统痕迹（也即卸载后全部消失的东西）

- 两个计划任务：LegymSUN / LegymTHU，**只在周日/周四 06:28 触发一次**，运行报名脚本，06:35 前必自行退出；无服务、无注册表自启项、无常驻进程、不装任何全局软件
- Windows 凭据管理器里的 phone / password（+可选 pushplus_token）
- 项目文件夹内的 config.json / session.json / logs
- （仅宽带用户）LegymDial 开机自动拨号任务

### 会不会影响日常使用

- 不会：任务只在周日/周四 06:28 触发，唤醒电脑也只发生在这一次；其余时间零活动
- 若 06:28 时电脑处于关机状态，开机后任务会**补跑一次**报名流程（已报名的活动自动跳过 isRegister=true，不会重复报名）；不想让补跑发生，删除任务即可
- 非报名日的开机（BIOS RTC 每天 06:15）属于方案B 的 BIOS 行为，与本项目无关；用方案A 睡眠唤醒则完全没有日常打扰

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
| 睡眠中没被唤醒 | 检查「允许唤醒计时器」并按方案A自测，见「自动开机引导」 |
| 关机后没有自动开机 | 唤醒能力只对睡眠/休眠有效；彻底关机请用 BIOS RTC 定时开机（方案B） |
| 到点跑了但日志全是网络错误 | 网络未就绪，见「网络就绪指引」：宽带需注册 LegymDial 开机拨号任务，热点前一晚提前打开 |

## 协议要点（备查）
- 登录 URL `POST https://cpes.legym.cn/authorization/user/v2/manage/login`
- 请求体 `{"t":<毫秒>,"pyd":"<AES(b64)>"}`，key = DeriveKey(t)[:16]
- DeriveKey：`s=str(t毫秒); x=(abs(int(s[2:5])-int(s[4:8]))<<int(s[-1]))&0xFFFFFFFF; key前缀="%d%s"%(x,"402881ea7c39c5d5017c39d143a8062b")`
- `signDigital` 留空 = 服务器不校验签名（填错反而返回 50004）
- 活动列表/报名均为**明文 JSON + Bearer token**，无加密
- 登录接口本身**不携带 Authorization 头**（2026-11 起网关拒绝空 Bearer，报 401 invalid_token）
- v1 明文登录接口已被服务端停用（返回 40012），必须走 v2 加密通道

## 已验证里程碑
- [x] v2 加密登录（真机账号全链路跑通）
- [x] 活动列表拉取与关键词匹配
- [x] 真实报名成功（`{"code":0,"data":{"success":true,"reason":"报名成功"}}`）
- [x] 多目标 + Windows 计划任务自动开抢

## License
以 [GPL-3.0](LICENSE) 协议开源。修改/分发请遵守协议条款并保留本声明。
