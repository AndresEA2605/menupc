@echo off
setlocal
set "APP=%LOCALAPPDATA%\CentroAplicaciones\menu-inicio-windows.ps1"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%APP%" (
    set "APP=%~dp0menu-inicio-windows.ps1"
)

if not exist "%APP%" (
    echo No se encontro menu-inicio-windows.ps1.
    echo Extrae todos los archivos del proyecto antes de abrirlo.
    pause
    exit /b 1
)

start "" "%POWERSHELL%" -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File "%APP%"
