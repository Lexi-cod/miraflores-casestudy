$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$workpaperPython = (& py -3 -c 'import sys; print(sys.executable)').Trim()
if (-not $workpaperPython) { throw 'Python 3 is required.' }
$workpaperPort = if ($env:PORT) { [int]$env:PORT } else { 8765 }
$workpaperUrl = "http://127.0.0.1:$workpaperPort"
try {
    $workpaperExisting = Invoke-RestMethod -Uri "$workpaperUrl/api/bootstrap" -TimeoutSec 2
    if ($workpaperExisting.mode -eq 'local-demo') {
        Write-Output "Workpaper already running: $workpaperUrl"
        exit 0
    }
} catch { }
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot 'data') | Out-Null
$workpaperProcess = Start-Process -FilePath $workpaperPython -ArgumentList 'app.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'data/server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'data/server-error.log') -PassThru
$workpaperProcess.Id | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'data/server.pid')
Write-Output "Workpaper started: $workpaperUrl (PID $($workpaperProcess.Id))"
