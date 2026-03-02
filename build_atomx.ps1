param(
    [string]$Name = "AtomX",
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$DistPath = "dist"
)

$ErrorActionPreference = "Stop"
$rootDir = (Resolve-Path ".").Path

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

Write-Host "Stopping running $Name processes (if any)..."
Get-Process -Name $Name -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Cleaning previous build folders..."
$buildDir = Join-Path "build" $Name
$distDir = Join-Path $DistPath $Name
$specDir = "build"
if (Test-Path $buildDir) { Remove-Item -Recurse -Force $buildDir }
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
if (-not (Test-Path $specDir)) { New-Item -ItemType Directory -Path $specDir | Out-Null }

Write-Host "Building $Name..."
& $PythonExe -m PyInstaller `
    --clean `
    --noconfirm `
    --onedir `
    --name $Name `
    --specpath $specDir `
    --console `
    --icon "$rootDir\ui\app_logo.ico" `
    --add-data "$rootDir\VERSION;." `
    --add-data "$rootDir\DBC;DBC" `
    --add-data "$rootDir\CAN Configuration;CAN Configuration" `
    --add-data "$rootDir\Test Sequence;Test Sequence" `
    --add-data "$rootDir\docs;docs" `
    --add-data "$rootDir\config_profiles;config_profiles" `
    --add-data "$rootDir\ui\app_logo.ico;ui" `
    --add-data "$rootDir\ui\app logo.png;ui" `
    --hidden-import serial `
    --hidden-import serial.tools.list_ports `
    --hidden-import pyvisa_py `
    --hidden-import can.interfaces.pcan `
    --hidden-import PyQt6.QtWebEngineWidgets `
    --hidden-import PyQt6.QtWebEngineCore `
    --hidden-import PyQt6.QtWebChannel `
    --hidden-import ui.TraceXTab `
    --hidden-import ui.TraceXView `
    --hidden-import core.tracex.live_can `
    --hidden-import core.tracex.trace_parser `
    --distpath $DistPath `
    main.py

$exePath = Join-Path $distDir "$Name.exe"
if (-not (Test-Path $exePath)) {
    throw "Build failed. EXE not found: $exePath"
}

Write-Host "Build completed successfully: $exePath"
Write-Host "Run: $exePath"
