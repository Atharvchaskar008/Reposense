# RepoSense local launcher (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    Write-Host "ERROR: Create a .env file in the project root with GITHUB_TOKEN, GEMINI_API_KEY, OPENAI_API_KEY" -ForegroundColor Red
    Write-Host "See README.md for details."
    exit 1
}

if (Test-Path ".venv\Scripts\Activate.ps1") {
    .\.venv\Scripts\Activate.ps1
}

Write-Host "Installing dependencies..."
pip install -q -r requirements.txt

Write-Host "Starting RepoSense at http://localhost:8000"
python server.py
