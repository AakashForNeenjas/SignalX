param(
    [string]$Name = "AtomX",
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$DistPath = "dist",
    [switch]$Console
)

$ErrorActionPreference = "Stop"
$rootDir = (Resolve-Path ".").Path
$buildRoot = Join-Path $rootDir "build"
$distRoot = Join-Path $rootDir $DistPath
$buildDir = Join-Path $buildRoot $Name
$distDir = Join-Path $distRoot $Name
$specDir = $buildRoot

$iconPngPath = Join-Path $rootDir "ui\app logo.png"
$iconIcoPath = Join-Path $rootDir "ui\app_logo.ico"
$versionPath = Join-Path $rootDir "VERSION"
$versionFilePath = Join-Path $specDir ("version_info_{0}_{1}.txt" -f $Name, $PID)

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

if (-not (Test-Path $iconPngPath)) {
    throw "Brand icon source not found: $iconPngPath"
}

if (-not (Test-Path $versionPath)) {
    throw "Version file not found: $versionPath"
}

if (-not (Test-Path $specDir)) {
    New-Item -ItemType Directory -Path $specDir | Out-Null
}

$pythonPath = (Resolve-Path $PythonExe).Path

Write-Host "Generating ICO from source PNG..."
$env:ATOMX_ICON_PNG = $iconPngPath
$env:ATOMX_ICON_ICO = $iconIcoPath
$env:QT_DEBUG_PLUGINS = "0"
$iconGenScript = @'
import os
from PyQt6.QtGui import QImage
from PyQt6.QtCore import Qt

png_path = os.environ["ATOMX_ICON_PNG"]
ico_path = os.environ["ATOMX_ICON_ICO"]
image = QImage(png_path)
if image.isNull():
    raise SystemExit(f"Unable to read PNG icon source: {png_path}")
image = image.scaled(
    256,
    256,
    Qt.AspectRatioMode.KeepAspectRatio,
    Qt.TransformationMode.SmoothTransformation,
)
if not image.save(ico_path, "ICO"):
    raise SystemExit(f"Unable to write ICO file: {ico_path}")
print(f"Generated ICO: {ico_path}")
'@
$iconGenScript | & $pythonPath -
$iconGenExitCode = $LASTEXITCODE
Remove-Item Env:ATOMX_ICON_PNG -ErrorAction SilentlyContinue
Remove-Item Env:ATOMX_ICON_ICO -ErrorAction SilentlyContinue
Remove-Item Env:QT_DEBUG_PLUGINS -ErrorAction SilentlyContinue
if ($iconGenExitCode -ne 0) {
    throw "ICO generation failed"
}

if (-not (Test-Path $iconIcoPath)) {
    throw "Generated ICO file not found: $iconIcoPath"
}

$iconSizeBytes = (Get-Item $iconIcoPath).Length
if ($iconSizeBytes -lt 10KB) {
    throw "Generated ICO is unexpectedly small ($iconSizeBytes bytes). Check source PNG quality."
}
Write-Host "Icon ready: $iconIcoPath ($iconSizeBytes bytes)"

$rawVersion = (Get-Content -Path $versionPath -Raw).Trim()
if (-not $rawVersion) {
    throw "VERSION file is empty"
}

$versionMatches = [regex]::Matches($rawVersion, '\d+')
$versionParts = @(0, 0, 0, 0)
for ($i = 0; $i -lt [Math]::Min(4, $versionMatches.Count); $i++) {
    $versionParts[$i] = [int]$versionMatches[$i].Value
}
$versionString = "{0}.{1}.{2}.{3}" -f $versionParts[0], $versionParts[1], $versionParts[2], $versionParts[3]

$versionInfoText = @"
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($($versionParts[0]), $($versionParts[1]), $($versionParts[2]), $($versionParts[3])),
    prodvers=($($versionParts[0]), $($versionParts[1]), $($versionParts[2]), $($versionParts[3])),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'Neenjas'),
            StringStruct('FileDescription', 'AtomX Test Automation'),
            StringStruct('FileVersion', '$versionString'),
            StringStruct('InternalName', '$Name'),
            StringStruct('LegalCopyright', 'Copyright (C) Neenjas'),
            StringStruct('OriginalFilename', '$Name.exe'),
            StringStruct('ProductName', 'AtomX'),
            StringStruct('ProductVersion', '$versionString')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
Set-Content -Path $versionFilePath -Value $versionInfoText -Encoding UTF8
Write-Host "Version resource generated: $versionFilePath ($versionString)"

Write-Host "Stopping running $Name processes (if any)..."
$failedStopIds = @()
$runningProcesses = @(Get-Process -Name $Name -ErrorAction SilentlyContinue)
foreach ($proc in $runningProcesses) {
    try {
        Stop-Process -Id $proc.Id -Force -ErrorAction Stop
        Write-Host "Stopped $Name process id=$($proc.Id)"
    }
    catch {
        Write-Warning "Stop-Process failed for id=$($proc.Id): $($_.Exception.Message)"
        cmd /c "taskkill /F /PID $($proc.Id) >nul 2>&1" | Out-Null
        Start-Sleep -Milliseconds 250
        if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
            $failedStopIds += $proc.Id
        } else {
            Write-Host "Stopped $Name process via taskkill id=$($proc.Id)"
        }
    }
}
if ($failedStopIds.Count -gt 0) {
    Write-Warning "Could not stop process IDs: $($failedStopIds -join ', '). Build may fail if files are locked."
}

Write-Host "Cleaning previous build folders..."
if (Test-Path $buildDir) {
    try {
        Remove-Item -Recurse -Force $buildDir
    }
    catch {
        throw "Failed to clean build directory '$buildDir'. Close AtomX/python processes and retry. Error: $($_.Exception.Message)"
    }
}
if (Test-Path $distDir) {
    try {
        Remove-Item -Recurse -Force $distDir
    }
    catch {
        $stillRunning = @(Get-Process -Name $Name -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
        $runningInfo = if ($stillRunning.Count -gt 0) { " Running IDs: $($stillRunning -join ', ')." } else { "" }
        throw "Failed to clean dist directory '$distDir'. It is likely locked by AtomX.$runningInfo Close the app (or run terminal as Administrator) and retry."
    }
}
if (-not (Test-Path $specDir)) { New-Item -ItemType Directory -Path $specDir | Out-Null }

$uiModeFlag = if ($Console) { "--console" } else { "--noconsole" }
$uiModeLabel = if ($Console) { "console (debug)" } else { "noconsole (release)" }
Write-Host "Build mode: $uiModeLabel"

Write-Host "Building $Name..."
& $pythonPath -m PyInstaller `
    --clean `
    --noconfirm `
    --onedir `
    --name $Name `
    --specpath $specDir `
    $uiModeFlag `
    --icon $iconIcoPath `
    --version-file $versionFilePath `
    --add-data "$rootDir\VERSION;." `
    --add-data "$rootDir\DBC;DBC" `
    --add-data "$rootDir\CAN Configuration;CAN Configuration" `
    --add-data "$rootDir\Test Sequence;Test Sequence" `
    --add-data "$rootDir\docs;docs" `
    --add-data "$rootDir\config_profiles;config_profiles" `
    --add-data "$iconIcoPath;ui" `
    --add-data "$iconPngPath;ui" `
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
    --distpath $distRoot `
    main.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$exePath = Join-Path $distDir "$Name.exe"
if (-not (Test-Path $exePath)) {
    throw "Build failed. EXE not found: $exePath"
}

Write-Host "Build completed successfully: $exePath"
Write-Host "Run: $exePath"
