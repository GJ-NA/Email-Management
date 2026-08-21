[CmdletBinding()]
param(
    [switch]$InstallIfMissing,
    [switch]$NoClean,
    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location $root

function Resolve-Python([string] $requestedPath) {
    if ($requestedPath) {
        if (-not (Test-Path -LiteralPath $requestedPath -PathType Leaf)) {
            throw "Python executable not found: $requestedPath"
        }
        return (Get-Item -LiteralPath $requestedPath).FullName
    }

    $candidates = @(
        (Join-Path $root '.venv\Scripts\python.exe'),
        (Join-Path $root 'venv\Scripts\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Get-Item -LiteralPath $candidate).FullName
        }
    }

    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    throw 'Python was not found. Install Python 3.11+ or create a root .venv.'
}

$python = Resolve-Python $PythonPath
$probeResult = & $python -c "import importlib.util; print('yes' if importlib.util.find_spec('PyInstaller') else 'no')"
$hasPyInstaller = ($probeResult -contains 'yes')

if (-not $hasPyInstaller) {
    if (-not $InstallIfMissing) {
        throw "PyInstaller is not installed. Run this script with -InstallIfMissing or install requirements-dev.txt first."
    }

    Write-Host 'Installing PyInstaller...' -ForegroundColor Yellow
    & $python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller installation failed with exit code $LASTEXITCODE."
    }
}

$buildArguments = @('-m', 'PyInstaller', '--noconfirm')
if (-not $NoClean) {
    $buildArguments += '--clean'
}
$buildArguments += @('--distpath', $root)
$buildArguments += 'email_management.spec'

Write-Host 'Building EmailManagement.exe...' -ForegroundColor Cyan
& $python @buildArguments
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$exePath = Join-Path $root 'EmailManagement.exe'
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Build completed but the executable was not found: $exePath"
}

$localEnvPath = Join-Path $root '.env'
if (-not (Test-Path -LiteralPath $localEnvPath -PathType Leaf)) {
    @(
        '# Local packaged-build settings. This file contains no secrets.'
        'EMAIL_MANAGEMENT_HOME=runtime'
        'HOST=127.0.0.1'
        'PORT=5000'
        'FLASK_ENV=production'
    ) | Set-Content -LiteralPath $localEnvPath -Encoding utf8
    Write-Host "Created local runtime config: $localEnvPath" -ForegroundColor Cyan
} else {
    Write-Host "Keeping existing local runtime config: $localEnvPath" -ForegroundColor Cyan
}

$sizeMb = [Math]::Round((Get-Item -LiteralPath $exePath).Length / 1MB, 1)
Write-Host "Build complete: $exePath ($sizeMb MB)" -ForegroundColor Green
Write-Host 'Double-click EmailManagement.exe to start the desktop app.' -ForegroundColor Green
