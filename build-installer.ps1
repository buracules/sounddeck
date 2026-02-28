param(
    [string]$Version = "0.1.0",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment not found at .venv. Create it first and install requirements."
}

if ($Clean) {
    Remove-Item -Recurse -Force "$root\build" -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force "$root\dist\SonarMixer" -ErrorAction SilentlyContinue
    Remove-Item -Force "$root\dist\SonarMixer-Portable-$Version.zip" -ErrorAction SilentlyContinue
}

Write-Host "Installing/Updating build dependencies..."
& $venvPython -m pip install --upgrade pyinstaller | Out-Host

Write-Host "Building executable with PyInstaller..."
& $venvPython -m PyInstaller `
    --noconfirm `
    --windowed `
    --name SonarMixer `
    --icon "$root\sonar_control\assets\app-icon.png" `
    --add-data "$root\sonar_control\assets;sonar_control\assets" `
    --collect-all PySide6 `
    --collect-all steelseries_sonar_py `
    "$root\app.py" | Out-Host

$portableZip = Join-Path $root "dist\SonarMixer-Portable-$Version.zip"
if (Test-Path $portableZip) {
    Remove-Item -Force $portableZip
}

Write-Host "Building portable zip..."
Compress-Archive -Path "$root\dist\SonarMixer\*" -DestinationPath $portableZip -CompressionLevel Optimal

$isccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "ISCC.exe not found. Install Inno Setup 6 first."
}

Write-Host "Building installer with Inno Setup..."
& $iscc "/DMyAppVersion=$Version" "$root\installer.iss" | Out-Host

Write-Host ""
Write-Host "Done."
Write-Host "Folder build output: $root\dist\SonarMixer"
Write-Host "Portable output:     $root\dist\SonarMixer-Portable-$Version.zip"
Write-Host "Installer output:    $root\dist\SonarMixer-Setup-$Version.exe"
