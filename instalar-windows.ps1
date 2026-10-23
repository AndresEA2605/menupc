$ErrorActionPreference = 'Stop'

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'Este instalador solo se puede ejecutar en Windows.'
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $scriptDir 'menu-inicio-windows.ps1'
$appData = $env:LOCALAPPDATA
$startup = [Environment]::GetFolderPath('Startup')
$powershell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'

if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw 'No se encontró menu-inicio-windows.ps1. Asegúrate de extraer todos los archivos del proyecto.'
}
if ([string]::IsNullOrWhiteSpace($appData) -or -not (Test-Path -LiteralPath $appData -PathType Container)) {
    throw 'Windows no proporcionó una carpeta de usuario válida (LOCALAPPDATA).'
}
if ([string]::IsNullOrWhiteSpace($startup)) {
    throw 'Windows no proporcionó la carpeta de inicio de sesión.'
}
if (-not (Test-Path -LiteralPath $powershell -PathType Leaf)) {
    throw 'No se encontró Windows PowerShell, necesario para abrir la interfaz.'
}

# Comprueba antes de instalar que la interfaz gráfica de Windows esté disponible.
try {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
    Add-Type -AssemblyName System.Drawing -ErrorAction Stop
} catch {
    throw "Windows no pudo cargar los componentes gráficos requeridos: $($_.Exception.Message)"
}

$appDir = Join-Path $appData 'CentroAplicaciones'
$destination = Join-Path $appDir 'menu-inicio-windows.ps1'
$shortcutPath = Join-Path $startup 'Centro de aplicaciones.lnk'

try {
    New-Item -ItemType Directory -Force -Path $appDir | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $powershell
    $shortcut.Arguments = "-NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$destination`""
    $shortcut.WorkingDirectory = $appDir
    $shortcut.Description = 'Centro de aplicaciones'
    $shortcut.Save()
} catch {
    throw "No se pudo instalar el Centro de aplicaciones. Comprueba los permisos de tu perfil de Windows. Detalle: $($_.Exception.Message)"
}

Write-Host 'Centro de aplicaciones instalado correctamente.' -ForegroundColor Green
Write-Host "Archivos: $appDir"
Write-Host 'Se abrirá automáticamente al iniciar sesión.'
Write-Host 'Puedes cerrar esta ventana.'
