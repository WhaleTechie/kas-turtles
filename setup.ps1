# setup.ps1 - one-time setup for kas-turtles
# Run from the repo root:  .\setup.ps1
# ASCII-only on purpose: PowerShell on non-UTF8 Windows codepages misreads em-dashes
# and curly quotes, which breaks parsing.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== kas-turtles setup ===" -ForegroundColor Cyan
Write-Host ""

# Check python is on PATH
try {
    $pyVersion = python --version 2>&1
    Write-Host "Found: $pyVersion"
} catch {
    Write-Host "ERROR: 'python' is not on PATH." -ForegroundColor Red
    Write-Host "Install Python 3.10 or newer from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "Make sure 'Add Python to PATH' is checked during install, then retry." -ForegroundColor Red
    exit 1
}

# Create venv if missing
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment in .venv ..."
    python -m venv .venv
} else {
    Write-Host ".venv already exists - reusing it."
}

# Activate
Write-Host "Activating .venv ..."
& .\.venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip ..."
python -m pip install --upgrade pip --quiet

# Install requirements
Write-Host ""
Write-Host "Installing requirements (several minutes on first run - torch is large)..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. In any new terminal, activate the venv first:"
Write-Host "       .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "  2. Add sightings:    python bin\ingest.py <folder-of-photos>"
Write-Host "  3. Embed catalog:    python bin\embed.py"
Write-Host "  4. Match a photo:    python bin\match.py <photo.jpg>"
Write-Host ""
Write-Host "First run of embed.py or match.py downloads MegaDescriptor (~1GB) - be patient." -ForegroundColor Yellow
Write-Host ""
