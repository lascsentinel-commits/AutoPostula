@echo off
chcp 65001 > nul
title AutoPostula - Asistente de Postulaciones (Windows 11)
cls

echo =====================================================================
echo          🚀 AUTOPOSTULA v4.0 - EJECUTOR PARA WINDOWS 11 🚀
echo =====================================================================
echo.

:: 1. Verificar si Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se encontro Python en tu sistema.
    echo Por favor instala Python 3.10 o superior marcando la casilla 'Add python.exe to PATH':
    echo    Opción rápida: winget install Python.Python.3.11
    echo    O descárgalo desde: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [✓] Python detectado correctamente.

:: 2. Crear entorno virtual si no existe
if not exist "venv" (
    echo [i] Creando entorno virtual 'venv'...
    python -m venv venv
)

:: 3. Activar entorno virtual
call venv\Scripts\activate.bat
set PATH=%~dp0bin;%PATH%

:: 4. Instalar o actualizar dependencias
echo [i] Verificando dependencias...
pip install -r requirements.txt >nul 2>&1
python -m playwright install-deps >nul 2>&1

:: 5. Detectar y lanzar Navegador con CDP (puerto 9222)
set BROWSER_EXE=
if exist "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" set "BROWSER_EXE=C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
if not defined BROWSER_EXE if exist "%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe" set "BROWSER_EXE=%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
if not defined BROWSER_EXE if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "BROWSER_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not defined BROWSER_EXE if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "BROWSER_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER_EXE if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set "BROWSER_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

if defined BROWSER_EXE (
    echo [✓] Navegador detectado: "%BROWSER_EXE%"
    echo [i] Levantando navegador en modo depuración (puerto 9222)...
    start "" "%BROWSER_EXE%" --remote-debugging-port=9222 --remote-allow-origins=*
    timeout /t 3 >nul
) else (
    echo [!] Aviso: No se detectó la ruta de Brave/Chrome automáticamente.
    echo Asegúrate de abrir tu navegador manualmente con el comando:
    echo chrome.exe --remote-debugging-port=9222 --remote-allow-origins=*
    echo.
)

:: 6. Verificar archivo de perfil
if not exist "perfil_alumno.json" (
    if exist "perfil_alumno_template.json" (
        echo [!] Aviso: No se encontró 'perfil_alumno.json'.
        echo     Se utilizará el perfil base o puedes copiar 'perfil_alumno_template.json'
        echo     a 'perfil_alumno.json' con tus propios datos académicos.
    )
)

:: 7. Ejecutar bucle interactivo de postulación
echo.
echo =====================================================================
echo   Iniciando bucle de postulación con panel interactivo de control...
echo =====================================================================
echo.

python bucle_pantalla_interactivo.py

echo.
echo Sesión finalizada.
pause

