$ErrorActionPreference = 'Stop'

$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $root

function Import-DotEnv([string] $path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return
    }

    foreach ($rawLine in Get-Content -LiteralPath $path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith('#')) {
            continue
        }
        if ($line.StartsWith('export ')) {
            $line = $line.Substring(7).TrimStart()
        }
        $parts = $line.Split('=', 2)
        if ($parts.Count -ne 2) {
            continue
        }
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (-not $key -or [Environment]::GetEnvironmentVariable($key)) {
            continue
        }
        $doubleQuote = [string][char]34
        $singleQuote = [string][char]39
        if ($value.Length -ge 2 -and (($value.StartsWith($doubleQuote) -and $value.EndsWith($doubleQuote)) -or ($value.StartsWith($singleQuote) -and $value.EndsWith($singleQuote)))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($key, $value, 'Process')
    }
}

Import-DotEnv (Join-Path $root '.env')

$pythonCandidates = @(
    (Join-Path $root '.venv\Scripts\python.exe'),
    (Join-Path $root 'venv\Scripts\python.exe')
)
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $python) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $python = $pythonCommand.Source
    }
}
if (-not $python) {
    throw '未找到 Python。当前脚本不会自动下载依赖，请准备 Python 或根目录 .venv。'
}

$runtimeValue = ($env:EMAIL_MANAGEMENT_HOME | Out-String).Trim()
if (-not $runtimeValue) {
    $runtimeValue = 'runtime'
    $env:EMAIL_MANAGEMENT_HOME = $runtimeValue
}
$runtime = if ([System.IO.Path]::IsPathRooted($runtimeValue)) {
    [System.IO.Path]::GetFullPath($runtimeValue)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $root $runtimeValue))
}
$data = Join-Path $runtime 'data'
$logs = Join-Path $runtime 'logs'
$secretPath = Join-Path $runtime 'secret_key.txt'
$adminPath = Join-Path $runtime 'admin_password.txt'
$defaultDatabase = Join-Path $data 'outlook_accounts.db'

New-Item -ItemType Directory -Force -Path $data, $logs | Out-Null

$secretValue = ($env:SECRET_KEY | Out-String).Trim()
if (-not $secretValue -or $secretValue -like 'replace-with-*' -or $secretValue -eq 'your-secret-key-here') {
    if (Test-Path -LiteralPath $secretPath -PathType Leaf) {
        $secretValue = (Get-Content -LiteralPath $secretPath -Raw).Trim()
    }
    if (-not $secretValue) {
        $bytes = New-Object byte[] 32
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        $rng.GetBytes($bytes)
        $rng.Dispose()
        $secretValue = (($bytes | ForEach-Object { $_.ToString('x2') }) -join '')
    }
    Set-Content -LiteralPath $secretPath -Value $secretValue -Encoding ascii -NoNewline
    $env:SECRET_KEY = $secretValue
}

$adminValue = ($env:LOGIN_PASSWORD | Out-String).Trim()
if (-not $adminValue -or $adminValue -like 'replace-with-*' -or $adminValue -eq 'admin123') {
    if (Test-Path -LiteralPath $adminPath -PathType Leaf) {
        $adminValue = (Get-Content -LiteralPath $adminPath -Raw).Trim()
    }
    if (-not $adminValue) {
        $adminValue = 'MailAdmin-' + [guid]::NewGuid().ToString('N').Substring(0, 20)
    }
    Set-Content -LiteralPath $adminPath -Value $adminValue -Encoding ascii -NoNewline
    $env:LOGIN_PASSWORD = $adminValue
}

if (-not $env:DATABASE_PATH) {
    $env:DATABASE_PATH = $defaultDatabase
}
$env:HOST = if ($env:HOST) { $env:HOST } else { '127.0.0.1' }
$env:PORT = if ($env:PORT) { $env:PORT } else { '5000' }
$env:FLASK_ENV = if ($env:FLASK_ENV) { $env:FLASK_ENV } else { 'production' }
$env:LOG_LEVEL = if ($env:LOG_LEVEL) { $env:LOG_LEVEL } else { 'WARNING' }
$env:DOCKER_UPDATE_ENABLED = if ($env:DOCKER_UPDATE_ENABLED) { $env:DOCKER_UPDATE_ENABLED } else { 'false' }

$url = "http://127.0.0.1:$($env:PORT)"
Write-Host '=====================================' -ForegroundColor Cyan
Write-Host 'Email Management' -ForegroundColor Cyan
Write-Host '=====================================' -ForegroundColor Cyan
Write-Host "URL: $url" -ForegroundColor Green
Write-Host '按 Ctrl+C 停止服务' -ForegroundColor Yellow
Write-Host "管理员密码: $adminValue" -ForegroundColor Yellow
Write-Host "数据目录: $data" -ForegroundColor Cyan
Write-Host '=====================================' -ForegroundColor Cyan

Start-Process $url
try {
    & $python 'email_management.py'
    if ($LASTEXITCODE -ne 0) {
        throw "服务已退出，返回码：$LASTEXITCODE"
    }
} finally {
    Write-Host 'Email Management 已停止。' -ForegroundColor Yellow
}
