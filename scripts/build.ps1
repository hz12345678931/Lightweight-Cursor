param([string]$Python = 'python', [string]$ISCC = 'ISCC.exe')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & $Python scripts/bootstrap_assets.py
    if ($LASTEXITCODE -ne 0) { throw 'Asset setup failed' }
    & $Python scripts/make_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Icon build failed' }
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    & $Python -m PyInstaller --noconfirm PyPilot.spec
    if ($LASTEXITCODE -ne 0) { throw 'Application build failed' }
    & $ISCC scripts/installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
    Get-FileHash -Algorithm SHA256 dist/installer/*.exe
} finally { Pop-Location }
