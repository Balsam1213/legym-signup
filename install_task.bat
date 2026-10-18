@echo off
rem 安装每周日 06:28 的计划任务（需要管理员权限或当前用户可创建任务）
schtasks /Create /F /TN "LegymAutoRegister" /SC WEEKLY /D SUN /ST 06:28:00 /TR "\"C:\Users\Balsam\Documents\AI project\Zcode\乐健自动报名\run_register.bat\""
schtasks /Query /TN "LegymAutoRegister"
pause
