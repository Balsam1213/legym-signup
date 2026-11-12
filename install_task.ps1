# 安装每周日/周四 06:28 的计划任务（按"提前4天"规则，请与你 config.json 的 open_day 对应增删）
# 由 install_task.bat 提权后调用。用 ScheduledTasks 模块而非 schtasks，因为 schtasks 命令行
# 设置不了"唤醒计算机"等选项。这里开启的关键能力：
#   WakeToRun           睡眠/休眠中自动唤醒电脑运行任务（README「自动开机引导」方案A）
#   StartWhenAvailable  错过的任务（如夜间 Windows 更新重启）在下次有机会时尽快补跑
#   S4U 登录类型        "不管用户是否登录都要运行"且免存密码，BIOS 开机停在登录界面也能执行

$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'run_register.bat'
if (-not (Test-Path $script)) {
    Write-Error "找不到 $script，请在项目根目录运行"
}

# S4U 需要完整账户名（本机账户或 域\用户）
$userId    = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$settings  = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable `
               -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType S4U

# 两个任务对应两种 open_day，要增删请同步改这里
$days = [ordered]@{ 'LegymSUN' = 'Sunday'; 'LegymTHU' = 'Thursday' }

foreach ($name in $days.Keys) {
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days[$name] -At '06:28'
    $action  = New-ScheduledTaskAction -Execute $script
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "已注册 $name（每周 $($days[$name]) 06:28，睡眠自动唤醒）"
}

Write-Host ""
Write-Host "核对（唤醒计算机=True / 登录类型=S4U 即正常）："
foreach ($name in $days.Keys) {
    $task = Get-ScheduledTask -TaskName $name
    $next = (Get-ScheduledTaskInfo -TaskName $name).NextRunTime
    Write-Host ("  {0}: 唤醒计算机={1}, 登录类型={2}, 下次运行={3}" -f `
        $name, $task.Settings.WakeToRun, $task.Principal.LogonType, $next)
}
Write-Host ""
Write-Host "建议：手动跑一次验证无人值守链路 -> schtasks /Run /TN LegymSUN，然后看 logs\run.out"
