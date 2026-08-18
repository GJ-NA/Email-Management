$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root 'start-local.ps1')
