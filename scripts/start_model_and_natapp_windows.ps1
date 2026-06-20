param(
    [string]$RepoRoot = "D:\项目经验\芳华小说\毕业设计\系统\multi-stage-creation-model-end",
    [string]$ModelPath = "D:\models\Qwen3.5-4B",
    [string]$NatappExe = "C:\Users\wxwhs\Desktop\natapp.exe",
    [string]$NatappAuthToken = "65150d8ebbd4a622",
    [string]$PublicBaseUrl = "http://isla.nat100.top",
    [int]$Port = 54862,
    [int]$NatappLocalPort = 80,
    [int]$MaxNewTokens = 1536,
    [switch]$LocalModel
)

$ErrorActionPreference = "Stop"

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($rawLine in Get-Content -LiteralPath $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            continue
        }
        if ($line.StartsWith("export ")) {
            $line = $line.Substring(7).Trim()
        }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) {
            continue
        }
        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
        if ($name -and -not [string]::IsNullOrWhiteSpace($value) -and [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

Import-DotEnv -Path (Join-Path $RepoRoot ".env")

$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$serverScript = Join-Path $RepoRoot "deploy\openai_compat_server.py"
$logsDir = Join-Path $RepoRoot "logs"
$runtimeDir = Join-Path $logsDir "runtime"

$modelOut = Join-Path $logsDir "local_openai_server.out.log"
$modelErr = Join-Path $logsDir "local_openai_server.err.log"
$proxyOut = Join-Path $logsDir "local_port_proxy.out.log"
$proxyErr = Join-Path $logsDir "local_port_proxy.err.log"
$natappOut = Join-Path $logsDir "natapp.client.out.log"
$natappErr = Join-Path $logsDir "natapp.client.err.log"
$modelPidFile = Join-Path $runtimeDir "model_server.pid"
$proxyPidFile = Join-Path $runtimeDir "local_port_proxy.pid"
$natappPidFile = Join-Path $runtimeDir "natapp.pid"
$startupInfoFile = Join-Path $logsDir "model_service_access.txt"
$trainingStatusFile = Join-Path $logsDir "managed_novel_training_status.json"

$pythonArgPrefix = @()
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if (-not $pyCommand) { throw "python not found: $pythonExe, and py.exe is not available in PATH" }
    $pythonExe = $pyCommand.Source
    $pythonArgPrefix = @("-3")
}
if ($LocalModel -and -not (Test-Path -LiteralPath $ModelPath)) {
    throw "model path not found: $ModelPath"
}
if (-not $LocalModel -and [string]::IsNullOrWhiteSpace($env:TOKENHUB_API_KEY)) {
    throw "TOKENHUB_API_KEY is empty. Set it in this PowerShell session before starting online model mode."
}

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$textNonfirstAdapterPath = $null
if (Test-Path $trainingStatusFile) {
    try {
        $statusJson = Get-Content $trainingStatusFile -Raw | ConvertFrom-Json
        $candidate = $statusJson.tasks.text_nonfirst.selected_final_dir
        if ($candidate -and (Test-Path $candidate)) {
            $textNonfirstAdapterPath = [string]$candidate
        }
    } catch {
    }
}

function Stop-ManagedProcess {
    param(
        [string]$Name,
        [string]$Filter
    )

    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq $Name -and $_.CommandLine -like $Filter } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
            } catch {
            }
        }
}

Stop-ManagedProcess -Name "python.exe" -Filter "*openai_compat_server.py*"
Stop-ManagedProcess -Name "python.exe" -Filter "*local_http_reverse_proxy.py*"
Stop-ManagedProcess -Name "natapp.exe" -Filter "*-authtoken=$NatappAuthToken*"

foreach ($target in @($modelOut, $modelErr, $proxyOut, $proxyErr, $natappOut, $natappErr)) {
    if (Test-Path $target) {
        try {
            Remove-Item $target -Force -ErrorAction Stop
        } catch {
        }
    }
}

$modelArgs = @()
$modelArgs += $pythonArgPrefix
$modelArgs += @(
    $serverScript,
    "--served-model-name", "ChiYong-MoE-Novel-18B-A6B",
    "--host", "0.0.0.0",
    "--port", "$Port",
    "--max-new-tokens", "$MaxNewTokens",
    "--include-done-marker"
)
if ($LocalModel) {
    $env:NOVEL_USE_ONLINE_MODEL = "false"
    $modelArgs += @("--local-model", "--model-path", $ModelPath, "--dtype", "float16")
} else {
    $env:NOVEL_USE_ONLINE_MODEL = "true"
    if ([string]::IsNullOrWhiteSpace($env:TOKENHUB_BASE_URL)) {
        $env:TOKENHUB_BASE_URL = "https://tokenhub.tencentmaas.com/v1"
    }
    $modelArgs += @("--online-model")
}
if ($LocalModel -and $textNonfirstAdapterPath) {
    $modelArgs += @("--text-nonfirst-adapter-path", $textNonfirstAdapterPath)
}

$modelProc = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList $modelArgs `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $modelOut `
    -RedirectStandardError $modelErr `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $modelPidFile -Value $modelProc.Id -Encoding ASCII

$healthOk = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:{0}/health" -f $Port) -TimeoutSec 5
        if ($resp.StatusCode -eq 200) {
            $healthOk = $true
            break
        }
    } catch {
    }
    Start-Sleep -Seconds 2
}

if (-not $healthOk) {
    throw "Model server did not become healthy on port $Port."
}

$proxyProc = $null
if ($NatappLocalPort -ne $Port) {
    $proxyScript = Join-Path $RepoRoot "scripts\local_http_reverse_proxy.py"
    $proxyProc = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @($proxyScript, "--listen-host", "127.0.0.1", "--listen-port", "$NatappLocalPort", "--target-host", "127.0.0.1", "--target-port", "$Port") `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $proxyOut `
        -RedirectStandardError $proxyErr `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -Path $proxyPidFile -Value $proxyProc.Id -Encoding ASCII

    $proxyOk = $false
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $proxyResp = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:{0}/health" -f $NatappLocalPort) -TimeoutSec 5
            if ($proxyResp.StatusCode -eq 200) {
                $proxyOk = $true
                break
            }
        } catch {
        }
        Start-Sleep -Seconds 1
    }

    if (-not $proxyOk) {
        throw "Local port proxy did not become healthy on port $NatappLocalPort."
    }
}

$natappProc = Start-Process `
    -FilePath $NatappExe `
    -ArgumentList @("-log=stdout", "-authtoken=$NatappAuthToken") `
    -WorkingDirectory (Split-Path $NatappExe -Parent) `
    -RedirectStandardOutput $natappOut `
    -RedirectStandardError $natappErr `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $natappPidFile -Value $natappProc.Id -Encoding ASCII

$startupInfo = @(
    "model_pid=$($modelProc.Id)"
    "proxy_pid=$($proxyProc.Id)"
    "natapp_pid=$($natappProc.Id)"
    "local_health=http://127.0.0.1:$Port/health"
    "natapp_local_health=http://127.0.0.1:$NatappLocalPort/health"
    "local_docs=http://127.0.0.1:$Port/docs"
    "public_health=$PublicBaseUrl/health"
    "public_docs=$PublicBaseUrl/docs"
    "public_chat=$PublicBaseUrl/v1/chat/completions"
    "text_nonfirst_adapter=$textNonfirstAdapterPath"
)

Set-Content -Path $startupInfoFile -Value $startupInfo -Encoding UTF8

Write-Host "Model server started. PID: $($modelProc.Id)"
Write-Host "Local proxy started. PID: $($proxyProc.Id)"
Write-Host "natapp started. PID: $($natappProc.Id)"
Write-Host "Local health: http://127.0.0.1:$Port/health"
Write-Host "Natapp local health: http://127.0.0.1:$NatappLocalPort/health"
Write-Host "Public health: $PublicBaseUrl/health"
Write-Host "Public chat: $PublicBaseUrl/v1/chat/completions"
