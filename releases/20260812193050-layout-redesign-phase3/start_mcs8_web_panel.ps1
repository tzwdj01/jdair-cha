$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "C:\Users\jiajianpeng\AppData\Local\Programs\Python\Python314\python.exe"
$Launcher = Join-Path $ScriptDir "start_server.py"
$Panel = Join-Path $ScriptDir "mcs8_web_panel.py"

if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

Write-Host "Starting MCS8 web panel on http://0.0.0.0:8788/"
Write-Host "Local URL: http://127.0.0.1:8788/"
& $Python $Launcher
Write-Host "Server started in background."