# AutoPostula v4.0 - Lanzador PowerShell para Windows 11
$ErrorActionPreference = "Stop"

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "          🚀 AUTOPOSTULA v4.0 - POWERSHELL WINDOWS 11 🚀             " -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan

# 1. Comprobar Python
try {
    $pyVer = python --version
    Write-Host "[✓] Python detectado: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python no está instalado en el sistema." -ForegroundColor Red
    Write-Host "Ejecuta: winget install Python.Python.3.11" -ForegroundColor Yellow
    exit 1
}

# 2. Entorno virtual
if (-not (Test-Path "venv")) {
    Write-Host "[i] Creando entorno virtual 'venv'..." -ForegroundColor Gray
    python -m venv venv
}

& "venv\Scripts\Activate.ps1"

# 3. Dependencias
Write-Host "[i] Verificando dependencias..." -ForegroundColor Gray
pip install -r requirements.txt | Out-Null

# 4. Navegador con CDP (puerto 9222)
$browserPaths = @(
    "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe",
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)

$browserExe = $browserPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($browserExe) {
    Write-Host "[✓] Navegador encontrado: $browserExe" -ForegroundColor Green
    Start-Process -FilePath $browserExe -ArgumentList "--remote-debugging-port=9222", "--remote-allow-origins=*"
    Start-Sleep -Seconds 3
} else {
    Write-Host "[!] No se detectó navegador automático. Ábrelo con: chrome.exe --remote-debugging-port=9222" -ForegroundColor Yellow
}

# 5. Ejecutar
Write-Host "[🚀] Iniciando AutoPostula..." -ForegroundColor Cyan
python bucle_pantalla_interactivo.py
