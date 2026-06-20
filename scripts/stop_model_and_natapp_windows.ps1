param(
    [string]$RepoRoot = "C:\Users\wxwhs\Desktop\nanochat-dgxspark-rl-main",
    [string]$BackendRepo = "C:\Users\wxwhs\Desktop\new_novel_back",
    [string]$FrontendRepo = "C:\Users\wxwhs\Desktop\new_fanghua-novel",
    [string]$NatappAuthToken = "65150d8ebbd4a622"
)

$ErrorActionPreference = "Stop"

$runtimeDir = Join-Path $RepoRoot "logs\runtime"
$modelPidFile = Join-Path $runtimeDir "model_server.pid"
$proxyPidFile = Join-Path $runtimeDir "local_port_proxy.pid"
$natappPidFile = Join-Path $runtimeDir "natapp.pid"
$threeServicePidFiles = @(
    (Join-Path $RepoRoot "logs\three_services_model.pid"),
    (Join-Path $RepoRoot "logs\three_services_proxy.pid"),
    (Join-Path $RepoRoot "logs\three_services_natapp.pid"),
    (Join-Path $BackendRepo "logs\three_services_backend.pid"),
    (Join-Path $FrontendRepo "run-logs\three_services_frontend.pid"),
    $modelPidFile,
    $proxyPidFile,
    $natappPidFile
)

function Stop-IfExists {
    param([int]$ProcessId)
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    } catch {
    }
}

foreach ($pidFile in $threeServicePidFiles) {
    if (-not (Test-Path $pidFile)) {
        continue
    }
    $pidValue = Get-Content -Raw $pidFile
    if ($pidValue -match '^\s*\d+\s*$') {
        Stop-IfExists -ProcessId ([int]$pidValue)
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Get-CimInstance Win32_Process |
    Where-Object {
        $cmd = $_.CommandLine
        if (-not $cmd) { return $false }
        return (
            ($_.Name -eq "python.exe" -and $cmd -like "*openai_compat_server.py*") -or
            ($_.Name -eq "python.exe" -and $cmd -like "*local_http_reverse_proxy.py*") -or
            ($_.Name -eq "natapp.exe" -and $cmd -like "*-authtoken=$NatappAuthToken*") -or
            ($cmd -like "*app-start-1.0-SNAPSHOT.jar*") -or
            ($cmd -like "*npm*run*dev*") -or
            ($cmd -like "*vite --host*")
        )
    } |
    ForEach-Object {
        try {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
        } catch {
        }
    }

Write-Host "Model, backend, frontend, local proxy, and natapp processes have been stopped."
