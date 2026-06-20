param(
    [ValidateSet("info_recommend", "summary", "outline", "detail_outline", "text_first", "text_nonfirst")]
    [string]$Task = "summary",
    [string]$ModelPath = "D:\models\Qwen3.5-4B",
    [string]$TrainData = "",
    [string]$OutputRoot = "",
    [string]$LogsDir = "logs",
    [string]$Preset = "rtx3080_qwen35_4b_safe",
    [string]$Dtype = "float16",
    [int]$NumEpochs = 1,
    [int]$Seed = 2026,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
[System.Console]::InputEncoding = [System.Text.UTF8Encoding]::new()

if (!(Test-Path $ModelPath)) {
    throw "Model path not found: $ModelPath"
}
if (-not $TrainData) {
    throw "TrainData is required."
}
if ([System.IO.Path]::IsPathRooted($TrainData)) {
    if (!(Test-Path $TrainData)) {
        throw "Train data not found: $TrainData"
    }
} else {
    $ResolvedTrainData = Join-Path $ProjectRoot $TrainData
    if (!(Test-Path $ResolvedTrainData)) {
        throw "Train data not found: $TrainData"
    }
}

if (-not $OutputRoot) {
    $OutputRoot = "outputs\$Task`_resilient"
}

$ReportPath = if ([System.IO.Path]::IsPathRooted($LogsDir)) {
    Join-Path $LogsDir "train_$Task`_resilient_report.json"
} else {
    Join-Path $LogsDir "train_$Task`_resilient_report.json"
}
$pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $pythonExe)) {
    $pythonExe = "python"
}

$argsList = @(
    "scripts/run_novel_resilient_train.py",
    "--task", $Task,
    "--preset", $Preset,
    "--model-path", $ModelPath,
    "--data", $TrainData,
    "--output-root", $OutputRoot,
    "--logs-dir", $LogsDir,
    "--report", $ReportPath,
    "--dtype", $Dtype,
    "--num-epochs", "$NumEpochs",
    "--seed", "$Seed"
)

if ($DryRun) {
    $argsList += "--dry-run"
}

Write-Host "============================================"
Write-Host "Novel Task SFT (RTX 3080 Preset)"
Write-Host "============================================"
Write-Host "Task:       $Task"
Write-Host "Model:      $ModelPath"
Write-Host "Train data: $TrainData"
Write-Host "Output:     $OutputRoot"
Write-Host "Report:     $ReportPath"
Write-Host "Preset:     $Preset"
Write-Host "Dtype:      $Dtype"
Write-Host "============================================"

Push-Location $ProjectRoot
try {
    & $pythonExe @argsList
} finally {
    Pop-Location
}
