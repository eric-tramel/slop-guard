# Pull latest slop-guard and regenerate the bundle.
# Usage: .\update.ps1 [-Repo <path>]

param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = Join-Path $env:TEMP "slop-guard-latest"
    Write-Host "Cloning latest slop-guard into $Repo ..."
    if (Test-Path $Repo) { Remove-Item -Recurse -Force $Repo }
    git clone --depth 1 https://github.com/eric-tramel/slop-guard.git $Repo
    if ($LASTEXITCODE -ne 0) {
        Write-Error "git clone failed. Is git installed and on PATH?"
        exit 1
    }
}

python "$PSScriptRoot\bundle.py" $Repo
if ($LASTEXITCODE -ne 0) {
    Write-Error "bundle.py failed. Is Python 3 installed and on PATH?"
    exit 1
}

$manifestPath = Join-Path $PSScriptRoot "manifest.json"
if (-not (Test-Path $manifestPath)) {
    Write-Host ""
    Write-Host "WARNING: No manifest.json found. First-time setup:" -ForegroundColor Yellow
    Write-Host "  Chrome:  Copy-Item manifest.chrome.json manifest.json"
    Write-Host "  Firefox: Copy-Item manifest.firefox.json manifest.json"
}

Write-Host ""
Write-Host "Reload the extension in your browser:"
Write-Host "  Chrome:  chrome://extensions -> reload Slop Guard"
Write-Host "  Firefox: about:debugging -> This Firefox -> Reload"
