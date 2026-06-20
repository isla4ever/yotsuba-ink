param(
    [string]$ModelRepo = "D:\项目经验\芳华小说\毕业设计\系统\multi-stage-creation-model-end",
    [string]$BackendRepo = "D:\项目经验\芳华小说\毕业设计\系统\new_novel_back",
    [string]$FrontendRepo = "D:\项目经验\芳华小说\毕业设计\系统\new_fanghua-novel (2)",
    [string]$ModelPath = "D:\models\Qwen3.5-4B",
    [string]$JavaHome = "C:\Program Files\jdks\LibericaJDK-21",
    [int]$ModelPort = 54862,
    [int]$BackendPort = 8090,
    [int]$FrontendPort = 3000,
    [int]$ModelMaxNewTokens = 2304,
    [string]$NatappExe = "C:\Users\wxwhs\Desktop\natapp.exe",
    [string]$NatappAuthToken = "65150d8ebbd4a622",
    [string]$PublicBaseUrl = "http://isla.nat100.top",
    [int]$NatappLocalPort = 80,
    [switch]$DisableNatapp,
    [switch]$StopExisting,
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

Import-DotEnv -Path (Join-Path $ModelRepo ".env")

function Write-Step {
    param([string]$Message)
    Write-Host "[three-services] $Message"
}

function Stop-ByPort {
    param([int[]]$Ports)
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in $Ports } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction Stop
                Write-Step "stopped process $($_.OwningProcess) on port $($_.LocalPort)"
            } catch {
            }
        }
}

function Stop-ByCommandLine {
    $patterns = @(
        "openai_compat_server.py",
        "local_http_reverse_proxy.py",
        "app-start-1.0-SNAPSHOT.jar",
        "vite --host",
        "npm.*run.*dev",
        "natapp.exe.*-authtoken=$NatappAuthToken"
    )
    $escapedSelf = [Regex]::Escape($PSCommandPath)
    Get-CimInstance Win32_Process |
        Where-Object {
            $cmd = $_.CommandLine
            if (-not $cmd) { return $false }
            if ($cmd -match $escapedSelf) { return $false }
            foreach ($pattern in $patterns) {
                if ($cmd -match $pattern) { return $true }
            }
            return $false
        } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                Write-Step "stopped matching process $($_.ProcessId)"
            } catch {
            }
        }
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$Seconds = 120
    )
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Start-HiddenProcess {
    param(
        [string]$FilePath,
        [object]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$OutLog,
        [string]$ErrLog,
        [string]$PidFile
    )
    New-Item -ItemType Directory -Force -Path (Split-Path $OutLog -Parent) | Out-Null
    Remove-Item -LiteralPath $OutLog,$ErrLog -Force -ErrorAction SilentlyContinue
    $proc = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -Path $PidFile -Value $proc.Id -Encoding ASCII
    return $proc
}

if ($StopExisting) {
    Write-Step "stopping existing services"
    Stop-ByCommandLine
    Stop-ByPort -Ports @($ModelPort, $BackendPort, $FrontendPort)
    Start-Sleep -Seconds 8
}

$modelPython = Join-Path $ModelRepo ".venv\Scripts\python.exe"
$modelScript = Join-Path $ModelRepo "deploy\openai_compat_server.py"
$modelLogs = Join-Path $ModelRepo "logs"
$modelOut = Join-Path $modelLogs "three_services_model.out.log"
$modelErr = Join-Path $modelLogs "three_services_model.err.log"
$modelPid = Join-Path $modelLogs "three_services_model.pid"
$proxyOut = Join-Path $modelLogs "three_services_proxy.out.log"
$proxyErr = Join-Path $modelLogs "three_services_proxy.err.log"
$proxyPid = Join-Path $modelLogs "three_services_proxy.pid"
$natappOut = Join-Path $modelLogs "three_services_natapp.out.log"
$natappErr = Join-Path $modelLogs "three_services_natapp.err.log"
$natappPid = Join-Path $modelLogs "three_services_natapp.pid"

if (-not (Test-Path -LiteralPath $modelScript)) { throw "model server not found: $modelScript" }
if ($LocalModel -and -not (Test-Path -LiteralPath $ModelPath)) { throw "model path not found: $ModelPath" }
if (-not $DisableNatapp -and -not (Test-Path -LiteralPath $NatappExe)) { throw "natapp.exe not found: $NatappExe" }
if (-not $LocalModel -and [string]::IsNullOrWhiteSpace($env:TOKENHUB_API_KEY)) {
    throw "TOKENHUB_API_KEY is empty. Set it in this PowerShell session before starting online model mode."
}

$pythonExe = $modelPython
$pythonArgPrefix = @()
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if (-not $pyCommand) { throw "python not found: $modelPython, and py.exe is not available in PATH" }
    $pythonExe = $pyCommand.Source
    $pythonArgPrefix = @("-3")
}

Write-Step "starting model server on $ModelPort"
$modelArgs = @()
$modelArgs += $pythonArgPrefix
$modelArgs += @(
    $modelScript,
    "--served-model-name", "ChiYong-MoE-Novel-18B-A6B",
    "--host", "0.0.0.0",
    "--port", "$ModelPort",
    "--max-new-tokens", "$ModelMaxNewTokens",
    "--include-done-marker"
)
if ($LocalModel) {
    $env:NOVEL_USE_ONLINE_MODEL = "false"
    $modelArgs += @("--local-model", "--model-path", $ModelPath, "--device", "cuda", "--dtype", "float16")
} else {
    $env:NOVEL_USE_ONLINE_MODEL = "true"
    if ([string]::IsNullOrWhiteSpace($env:TOKENHUB_BASE_URL)) {
        $env:TOKENHUB_BASE_URL = "https://tokenhub.tencentmaas.com/v1"
    }
    $modelArgs += @("--online-model")
}
$modelProc = Start-HiddenProcess `
    -FilePath $pythonExe `
    -ArgumentList $modelArgs `
    -WorkingDirectory $ModelRepo `
    -OutLog $modelOut `
    -ErrLog $modelErr `
    -PidFile $modelPid
Write-Step "model pid=$($modelProc.Id)"

Write-Step "waiting for model health"
$modelOk = Wait-HttpOk -Url "http://127.0.0.1:$ModelPort/health" -Seconds 900
if (-not $modelOk) {
    Write-Step "model did not become healthy; see $modelErr"
    exit 2
}

$backendLogs = Join-Path $BackendRepo "logs"
$backendOut = Join-Path $backendLogs "three_services_backend.out.log"
$backendErr = Join-Path $backendLogs "three_services_backend.err.log"
$backendPid = Join-Path $backendLogs "three_services_backend.pid"
$backendJar = Join-Path $BackendRepo "app-start\target\app-start-1.0-SNAPSHOT.jar"
$javaExe = Join-Path $JavaHome "bin\java.exe"

if (-not (Test-Path -LiteralPath $javaExe)) { throw "java not found: $javaExe" }
if (-not (Test-Path -LiteralPath $backendJar)) { throw "backend jar not found: $backendJar" }

Write-Step "starting backend on $BackendPort"
$backendArgs = "-Dspring.profiles.active=dev -Dai.local.base-url=http://127.0.0.1:$ModelPort -jar `"$backendJar`""
$backendProc = Start-HiddenProcess `
    -FilePath $javaExe `
    -ArgumentList $backendArgs `
    -WorkingDirectory $BackendRepo `
    -OutLog $backendOut `
    -ErrLog $backendErr `
    -PidFile $backendPid
Write-Step "backend pid=$($backendProc.Id)"

$frontendLogs = Join-Path $FrontendRepo "run-logs"
$frontendOut = Join-Path $frontendLogs "three_services_frontend.out.log"
$frontendErr = Join-Path $frontendLogs "three_services_frontend.err.log"
$frontendPid = Join-Path $frontendLogs "three_services_frontend.pid"

Write-Step "starting frontend on $FrontendPort"
$frontendArgs = @("run", "dev", "--", "--host", "0.0.0.0", "--port", "$FrontendPort")
$frontendProc = Start-HiddenProcess `
    -FilePath "npm.cmd" `
    -ArgumentList $frontendArgs `
    -WorkingDirectory $FrontendRepo `
    -OutLog $frontendOut `
    -ErrLog $frontendErr `
    -PidFile $frontendPid
Write-Step "frontend pid=$($frontendProc.Id)"

if (-not $DisableNatapp) {
    $proxyScript = Join-Path $ModelRepo "scripts\local_http_reverse_proxy.py"
    if (-not (Test-Path -LiteralPath $proxyScript)) { throw "proxy script not found: $proxyScript" }

    Write-Step "starting local model proxy on $NatappLocalPort -> $ModelPort"
    $proxyArgs = @(
        $proxyScript,
        "--listen-host", "127.0.0.1",
        "--listen-port", "$NatappLocalPort",
        "--target-host", "127.0.0.1",
        "--target-port", "$ModelPort"
    )
    $proxyProc = Start-HiddenProcess `
        -FilePath $modelPython `
        -ArgumentList $proxyArgs `
        -WorkingDirectory $ModelRepo `
        -OutLog $proxyOut `
        -ErrLog $proxyErr `
        -PidFile $proxyPid
    Write-Step "proxy pid=$($proxyProc.Id)"

    Write-Step "starting natapp tunnel for $PublicBaseUrl"
    $natappArgs = @("-log=stdout", "-authtoken=$NatappAuthToken")
    $natappProc = Start-HiddenProcess `
        -FilePath $NatappExe `
        -ArgumentList $natappArgs `
        -WorkingDirectory (Split-Path $NatappExe -Parent) `
        -OutLog $natappOut `
        -ErrLog $natappErr `
        -PidFile $natappPid
    Write-Step "natapp pid=$($natappProc.Id)"
}

Write-Step "waiting for services"
$frontendOk = Wait-HttpOk -Url "http://127.0.0.1:$FrontendPort/" -Seconds 90
$backendOk = Wait-HttpOk -Url "http://127.0.0.1:$BackendPort/v3/api-docs" -Seconds 120
$proxyOk = $true
$publicOk = $true
if (-not $DisableNatapp) {
    $proxyOk = Wait-HttpOk -Url "http://127.0.0.1:$NatappLocalPort/health" -Seconds 120
    $publicOk = Wait-HttpOk -Url "$PublicBaseUrl/health" -Seconds 90
}

Write-Host ""
Write-Host "=== Service URLs ==="
Write-Host "Frontend:      http://localhost:$FrontendPort/"
Write-Host "Backend API:   http://localhost:$BackendPort/v3/api-docs"
Write-Host "Backend UI:    http://localhost:$BackendPort/swagger-ui/index.html"
Write-Host "Model health:  http://localhost:$ModelPort/health"
Write-Host "Model docs:    http://localhost:$ModelPort/docs"
if (-not $DisableNatapp) {
    Write-Host "Tunnel health: $PublicBaseUrl/health"
    Write-Host "Tunnel docs:   $PublicBaseUrl/docs"
    Write-Host "Tunnel chat:   $PublicBaseUrl/v1/chat/completions"
}
Write-Host ""
Write-Host "=== Status ==="
Write-Host "frontend_ok=$frontendOk"
Write-Host "backend_ok=$backendOk"
Write-Host "model_ok=$modelOk"
if (-not $DisableNatapp) {
    Write-Host "proxy_ok=$proxyOk"
    Write-Host "public_ok=$publicOk"
}
Write-Host ""
Write-Host "=== Logs ==="
Write-Host "model:    $modelErr"
Write-Host "backend:  $backendOut"
Write-Host "frontend: $frontendOut"
if (-not $DisableNatapp) {
    Write-Host "proxy:    $proxyOut"
    Write-Host "natapp:   $natappOut"
}

if (-not ($frontendOk -and $backendOk -and $modelOk -and $proxyOk -and $publicOk)) {
    exit 2
}
