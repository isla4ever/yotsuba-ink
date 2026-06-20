param(
    [string]$ModelPath = "D:\models\Qwen3.5-4B",
    [string]$Preset = "rtx3080_qwen35_4b_safe",
    [string]$Dtype = "float16",
    [int]$Seed = 2026,
    [int]$NumEpochs = 1,
    [ValidateSet("info_recommend", "summary", "outline", "detail_outline", "text_first", "text_nonfirst")]
    [string]$StartFrom = "info_recommend",
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
[System.Console]::InputEncoding = [System.Text.UTF8Encoding]::new()

if (!(Test-Path $ModelPath)) {
    throw "Model path not found: $ModelPath"
}

$pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $pythonExe)) {
    throw "Python env not found: $pythonExe"
}

$argsList = @(
    "scripts/run_managed_novel_training.py",
    "--project-root", $ProjectRoot,
    "--model-path", $ModelPath,
    "--preset", $Preset,
    "--dtype", $Dtype,
    "--seed", "$Seed",
    "--num-epochs", "$NumEpochs",
    "--python-exe", $pythonExe,
    "--start-from", $StartFrom
)

if ($Background) {
    $stdout = Join-Path $ProjectRoot "logs\managed_novel_training.out.log"
    $stderr = Join-Path $ProjectRoot "logs\managed_novel_training.err.log"
    $proc = Start-Process -FilePath $pythonExe -ArgumentList $argsList -WorkingDirectory $ProjectRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    Set-Content -Path (Join-Path $ProjectRoot "logs\managed_novel_training.pid") -Value $proc.Id
    Write-Host "Background PID: $($proc.Id)"
    Write-Host "Stdout:         $stdout"
    Write-Host "Stderr:         $stderr"
    Write-Host "Status file:    $(Join-Path $ProjectRoot 'logs\managed_novel_training_status.json')"
} else {
    Push-Location $ProjectRoot
    try {
        & $pythonExe @argsList
    } finally {
        Pop-Location
    }
}
