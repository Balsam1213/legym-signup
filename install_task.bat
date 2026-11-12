@echo off
chcp 65001 >nul
rem 安装每周日/周四 06:28 的计划任务（按"提前4天"规则，请与你 config.json 的 open_day 对应增删）
rem 任务自带"睡眠自动唤醒/错过补跑/未登录可运行"能力，由 install_task.ps1 注册
rem （schtasks 命令行设置不了这些选项）；"不管用户是否登录都运行"需要管理员权限，
rem 无权限时会弹 UAC 提权窗口重新执行本脚本
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限，请在 UAC 弹窗选择"是"...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_task.ps1"
pause
