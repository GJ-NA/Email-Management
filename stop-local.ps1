$ErrorActionPreference = 'Stop'

$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$entrypoint = [regex]::Escape((Join-Path $root 'email_management.py'))

# The normal launcher runs in the foreground and should be stopped with Ctrl+C.
# This fallback is useful when the process was started from another terminal.
$matches = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '^python(?:w)?\.exe$' -and $_.CommandLine -match $entrypoint
}

if (-not $matches) {
    Write-Host '没有找到 Email Management 进程；前台运行时请在服务终端按 Ctrl+C。'
    exit 0
}

foreach ($item in $matches) {
    Stop-Process -Id ([int]$item.ProcessId) -Force
    Write-Host "已停止 Email Management (PID $($item.ProcessId))。"
}
