param(
    [string]$ModelPath = "D:\models\Qwen3.5-4B",
    [string]$AdapterPath = "",
    [string]$ServedModelName = "ChiYong-MoE-Novel-18B-A6B",
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 54862,
    [string]$Dtype = "float16",
    [int]$MaxNewTokens = 1664,
    [bool]$IncludeDoneMarker = $true,
    [string]$UpstreamEndpoint = "",
    [string]$UpstreamModel = "",
    [string]$UpstreamApiKeyEnv = "DEEPSEEK_API_KEY",
    [int]$UpstreamTimeoutSeconds = 60,
    [string]$UpstreamNonstreamTasks = "info_recommend,summary,outline,detail_outline"
)

$ErrorActionPreference = "Stop"
[string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
[System.Console]::InputEncoding = [System.Text.UTF8Encoding]::new()

if (!(Test-Path $ModelPath)) {
    throw "Model path not found: $ModelPath"
}

$argsList = @(
    "deploy/openai_compat_server.py",
    "--model-path", $ModelPath,
    "--served-model-name", $ServedModelName,
    "--host", $BindHost,
    "--port", "$Port",
    "--dtype", $Dtype,
    "--max-new-tokens", "$MaxNewTokens"
)

if ($IncludeDoneMarker) {
    $argsList += @("--include-done-marker")
} else {
    $argsList += @("--no-done-marker")
}

if ($AdapterPath -and (Test-Path $AdapterPath)) {
    $argsList += @("--adapter-path", $AdapterPath)
}

if ($UpstreamEndpoint) {
    $argsList += @(
        "--upstream-endpoint", $UpstreamEndpoint,
        "--upstream-api-key-env", $UpstreamApiKeyEnv,
        "--upstream-timeout-seconds", "$UpstreamTimeoutSeconds",
        "--upstream-nonstream-tasks", $UpstreamNonstreamTasks
    )
    if ($UpstreamModel) {
        $argsList += @("--upstream-model", $UpstreamModel)
    }
}

Write-Host "============================================"
Write-Host "Local OpenAI-compatible Server"
Write-Host "============================================"
Write-Host "Model path:        $ModelPath"
Write-Host "Adapter path:      $AdapterPath"
Write-Host "Served model name: $ServedModelName"
Write-Host "Address:           http://$BindHost`:$Port"
Write-Host "Upstream endpoint: $UpstreamEndpoint"
Write-Host "Upstream model:    $UpstreamModel"
Write-Host "Upstream tasks:    $UpstreamNonstreamTasks"
Write-Host "============================================"

$pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $pythonExe) {
    Push-Location $ProjectRoot
    try {
        & $pythonExe @argsList
    } finally {
        Pop-Location
    }
} else {
    Push-Location $ProjectRoot
    try {
        python @argsList
    } finally {
        Pop-Location
    }
}
