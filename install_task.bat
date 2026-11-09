@echo off
rem 安装每周日/周四 06:28 的计划任务（按"提前4天"规则，请与你 config.json 的 open_day 对应增删）
schtasks /Create /F /TN "LegymSUN" /SC WEEKLY /D SUN /ST 06:28:00 /TR "\"%~dp0run_register.bat\""
schtasks /Create /F /TN "LegymTHU" /SC WEEKLY /D THU /ST 06:28:00 /TR "\"%~dp0run_register.bat\""
schtasks /Query /TN "LegymSUN"
schtasks /Query /TN "LegymTHU"
pause
