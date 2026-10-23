$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appDir = Join-Path $env:LOCALAPPDATA 'CentroAplicaciones'
$startupDir = [Environment]::GetFolderPath('Startup')
$destination = Join-Path $appDir 'menu-inicio-windows.py'
$shortcutPath = Join-Path $startupDir 'Centro de aplicaciones.lnk'

if (-not (Get-Command pythonw.exe -ErrorAction SilentlyContinue)) {
    throw 'No se encontró Python para Windows. Instala Python 3 y vuelve a ejecutar este instalador.'
}

New-Item -ItemType Directory -Force -Path $appDir | Out-Null
Copy-Item (Join-Path $scriptDir 'menu-inicio-windows.py') $destination -Force

$pythonw = (Get-Command pythonw.exe).Source
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "`"$destination`""
$shortcut.WorkingDirectory = $appDir
$shortcut.Description = 'Centro de aplicaciones'
$shortcut.Save()

Write-Host "Instalado en: $appDir"
Write-Host 'Se abrirá automáticamente al iniciar sesión. También puedes abrir menu-inicio-windows.py desde esa carpeta.'
