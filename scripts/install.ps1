# Tether OS Installer -- Windows (PowerShell)
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1
# Auto-downloads Tor Expert Bundle + installs Tether OS

param(
    [switch]$NoTor
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  TETHER OS v2.0.0rc1 -- Windows Installer" -ForegroundColor Cyan
Write-Host "  by Trapzzy" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Project root is one level up from scripts/
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TetherRoot = "$env:USERPROFILE\.tether"
$TorTarget = "$TetherRoot\tor"

Write-Host "[TETHER] Project root: $ProjectRoot" -ForegroundColor Gray
Write-Host "[TETHER] Install target: $TetherRoot" -ForegroundColor Gray
Write-Host ""

# 1. Create directory structure
New-Item -ItemType Directory -Path "$TetherRoot\bin" -Force | Out-Null
New-Item -ItemType Directory -Path "$TetherRoot\etc" -Force | Out-Null
New-Item -ItemType Directory -Path "$TetherRoot\log" -Force | Out-Null
New-Item -ItemType Directory -Path "$TorTarget" -Force | Out-Null

# 2. Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[FAIL] Python 3.7+ is required." -ForegroundColor Red
    Write-Host "       Download from: https://python.org" -ForegroundColor Yellow
    exit 1
}
$pythonVersion = & $python.Source --version 2>&1
Write-Host "[OK] $pythonVersion" -ForegroundColor Green

# 3. Install Tor Expert Bundle (unless --NoTor)
if (-not $NoTor) {
    $torExe = "$TorTarget\tor.exe"
    if (-not (Test-Path $torExe)) {
        Write-Host "[TETHER] Downloading Tor Expert Bundle for Windows x86_64..." -ForegroundColor Yellow
        $url = "https://archive.torproject.org/tor-package-archive/torbrowser/15.0.17/tor-expert-bundle-windows-x86_64-15.0.17.tar.gz"
        $tmp = "$env:TEMP\tor-expert.tar.gz"
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Write-Host "[TETHER] Downloading from: $url" -ForegroundColor Gray
            Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -TimeoutSec 60
            Write-Host "[TETHER] Extracting..."
            tar -xzf $tmp -C $TorTarget 2>&1 | Out-Null
            # Find tor.exe in the extracted tree (might be nested)
            $foundExe = Get-ChildItem -Path $TorTarget -Recurse -Filter "tor.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($foundExe) {
                Copy-Item $foundExe.FullName "$TorTarget\tor.exe" -Force
                Write-Host "[OK] Tor binary extracted" -ForegroundColor Green
            } else {
                Write-Host "[WARN] tor.exe not found in archive." -ForegroundColor Yellow
            }
            Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Host "[WARN] Could not auto-download Tor Expert Bundle: $_" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "       Download manually:" -ForegroundColor Yellow
            Write-Host "       1. Go to: https://www.torproject.org/download/tor/" -ForegroundColor Cyan
            Write-Host "       2. Download 'Windows (x86_64)' Expert Bundle" -ForegroundColor Cyan
            Write-Host "       3. Extract tor.exe to: $TorTarget" -ForegroundColor Cyan
            Write-Host ""
        }
    }

    if (Test-Path "$TorTarget\tor.exe") {
        Write-Host "[OK] Tor binary at: $TorTarget\tor.exe" -ForegroundColor Green

        # Add to PATH (user level)
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($currentPath -notlike "*$TorTarget*") {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$TorTarget", "User")
            $env:Path = "$env:Path;$TorTarget"
            Write-Host "[OK] Added Tor to user PATH" -ForegroundColor Green
        }

        # Create torrc
        $torrc = "$TorTarget\torrc"
        if (-not (Test-Path $torrc)) {
@"
SOCKSPort 127.0.0.1:9050
ControlPort 127.0.0.1:9051
Log notice file $TetherRoot\log\tor.log
DataDirectory $TetherRoot\data
"@ | Out-File -FilePath $torrc -Encoding ASCII
            Write-Host "[OK] Created torrc at: $torrc" -ForegroundColor Green
        }

        # Create convenience start/stop scripts
@"
@echo off
title Tor Daemon (Tether OS)
start /B "" "$TorTarget\tor.exe" -f "$TorTarget\torrc"
echo [TETHER] Tor started on ports 9050 (SOCKS) and 9051 (Control)
echo [TETHER] Tether OS is ready. Run: tetherd
"@ | Out-File -FilePath "$TorTarget\start-tor.cmd" -Encoding ASCII

@"
@echo off
taskkill /f /im tor.exe >nul 2>&1
echo [TETHER] Tor stopped.
"@ | Out-File -FilePath "$TorTarget\stop-tor.cmd" -Encoding ASCII

        Write-Host ""
        Write-Host "[TETHER] Created convenience scripts:" -ForegroundColor Cyan
        Write-Host "        Start Tor:  $TorTarget\start-tor.cmd" -ForegroundColor Cyan
        Write-Host "        Stop Tor:   $TorTarget\stop-tor.cmd" -ForegroundColor Cyan
    }
}

# 4. Install Tether OS via pip (editable install from project root)
Write-Host "[TETHER] Installing Tether OS from: $ProjectRoot" -ForegroundColor Yellow
try {
    $pipOutput = & $python.Source -m pip install --user -e "$ProjectRoot" 2>&1
    $pipExit = $LASTEXITCODE
    if ($pipExit -ne 0) {
        Write-Host "[WARN] pip install had issues, but trying direct usage..." -ForegroundColor Yellow
    } else {
        Write-Host "[OK] Tether OS installed successfully" -ForegroundColor Green
    }
} catch {
    Write-Host "[WARN] pip install failed: $_" -ForegroundColor Yellow
    Write-Host "[TETHER] You can still run Tether OS directly from: $ProjectRoot" -ForegroundColor Cyan
}

# 5. Create convenience launcher
$launcher = "$TetherRoot\bin\tether.cmd"
@"
@echo off
python "$ProjectRoot\bin\tether" %*
"@ | Out-File -FilePath "$TetherRoot\bin\tether.cmd" -Encoding ASCII

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  INSTALLATION SUMMARY" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if (Test-Path "$TorTarget\tor.exe") {
    Write-Host "  Tor binary:      READY at $TorTarget\tor.exe" -ForegroundColor Green
} else {
    Write-Host "  Tor binary:      NOT INSTALLED (see manual steps above)" -ForegroundColor Yellow
}

Write-Host "  Tether OS:       $ProjectRoot" -ForegroundColor Green
Write-Host "  Config:          $TetherRoot\etc" -ForegroundColor Gray
Write-Host "  Logs:            $TetherRoot\log" -ForegroundColor Gray
Write-Host ""
Write-Host "  QUICK START:" -ForegroundColor Cyan
Write-Host "  1. $TorTarget\start-tor.cmd       (start Tor daemon)" -ForegroundColor White
Write-Host "  2. tether check                   (verify everything)" -ForegroundColor White
Write-Host "  3. tetherd                        (start IP rotation)" -ForegroundColor White
Write-Host ""
Write-Host "  COMMANDS:" -ForegroundColor Cyan
Write-Host "    tether status     tether rotate    tether ip" -ForegroundColor White
Write-Host "    tether stop       tether check     tether info" -ForegroundColor White
Write-Host ""
Write-Host "  Or run directly:" -ForegroundColor Cyan
Write-Host "    python $ProjectRoot\bin\tether check" -ForegroundColor White
Write-Host "    python $ProjectRoot\bin\tetherd" -ForegroundColor White
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
