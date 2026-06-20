param(
    [string]$Input = "data\teacher_pairs.jsonl",
    [string]$Output = "data\novel_sft_train.jsonl"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $Input)) {
    throw "Input file not found: $Input"
}

python scripts/build_novel_sft_dataset.py `
    --input "$Input" `
    --output "$Output" `
    --dedupe

Write-Host "Converted dataset: $Output"
