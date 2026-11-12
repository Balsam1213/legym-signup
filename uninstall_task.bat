@echo off
chcp 65001 >nul
rem 卸载：删除本项目的全部计划任务（LegymSUN / LegymTHU / LegymDial），不留任何自启动项
rem 注：若用过 BIOS RTC 定时开机（方案B），请在 BIOS 里手动关闭，软件无法代劳
rem 需要管理员权限（任务是提权注册的）；无权限时会弹 UAC 提权窗口重新执行本脚本
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限，请在 UAC 弹窗选择"是"...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
echo 正在删除计划任务...
schtasks /Delete /TN "LegymSUN" /F
schtasks /Delete /TN "LegymTHU" /F
rem LegymDial 仅宽带用户注册过，不存在则忽略报错
schtasks /Delete /TN "LegymDial" /F 2>nul
echo.
echo 确认（提示"找不到...任务"即已删除干净）：
schtasks /Query /TN "LegymSUN"
schtasks /Query /TN "LegymTHU"
echo.
echo 如需连凭据/会话一并清除：py register.py cred-clear --purge-session
pause
