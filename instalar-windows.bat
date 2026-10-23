@echo off
setlocal
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%POWERSHELL%" (
    echo No se encontro Windows PowerShell, requerido por el instalador.
    pause
    exit /b 1
)

"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar-windows.ps1"
if errorlevel 1 pause
