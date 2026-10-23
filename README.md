# Centro de aplicaciones

Centro para buscar y abrir aplicaciones instaladas en Linux y Windows. En
Linux ofrece un menú de terminal que lee lanzadores `.desktop` de usuario,
sistema y Flatpak. En Windows usa una ventana gráfica y detecta los accesos
directos del menú Inicio. Ambos organizan las aplicaciones por categorías.

## Instalación rápida

Descarga/clona este repositorio en el equipo destino y ejecuta desde su carpeta:

```bash
./instalar.sh
```

El instalador copia los dos archivos necesarios a
`~/.local/share/centro-aplicaciones`, crea el comando `centro-aplicaciones` en
`~/.local/bin` y configura el inicio automático al entrar en la sesión gráfica.
No necesita permisos de administrador.
Si `~/.local/bin` no está en `PATH`, usa la ruta completa en el atajo.

Para añadir el atajo en Hyprland, agrega a `~/.config/hypr/hyprland.conf`:

```ini
$mainMod, A, exec, ~/.local/bin/centro-aplicaciones
```

Puedes cambiar `A` por otra tecla. Después recarga la configuración:

```bash
hyprctl reload
```

El instalador deja también la línea en
`~/.local/share/centro-aplicaciones/atajo-hyprland.conf`.

## Windows

En Windows, abre PowerShell desde la carpeta del proyecto y ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\instalar-windows.ps1
```

El instalador copia el centro a `%LOCALAPPDATA%\CentroAplicaciones` y crea un
acceso directo en la carpeta de inicio de sesión. También puedes ejecutar
`menu-inicio-windows.py` directamente con Python 3. La ventana busca
aplicaciones por nombre y categoría; descubre los accesos directos `.lnk` de
los menús Inicio del usuario y del sistema.

Requisitos: Windows 10 u 11 y Python 3 con Tkinter. Para el inicio automático,
`pythonw.exe` debe estar disponible en `PATH`.

## Requisitos

- Linux con una sesión gráfica y Python 3, o Windows 10/11 con Python 3 y Tkinter.
- Una terminal compatible: Kitty, COSMIC Terminal, Alacritty, GNOME Terminal,
  XFCE Terminal, Konsole o xterm.
- `gtk-launch` para abrir las aplicaciones desde sus lanzadores `.desktop`.
- Hyprland y Kitty son opcionales; juntos permiten mover el centro al monitor
  enfocado al iniciarlo.

`xdg-open` es opcional y se usa para abrir carpetas. En otras sesiones de
escritorio el inicio automático se configura, pero la selección del monitor
depende del comportamiento de la terminal y del gestor de ventanas.

## Controles

- Escribe el número de una aplicación para abrirla.
- Escribe `/texto` para buscar por nombre o identificador. Usa `/` para limpiar.
- Escribe `:categoría` para filtrar, o `:todas` para volver al catálogo completo.
- Usa J y K para desplazar la lista si no cabe en pantalla.
- Pulsa G para mostrar solo las aplicaciones de Configuración; vuelve a pulsar G para mostrar todas.
- Pulsa H para abrir la vista de herramientas y `?` para ver la ayuda.
- Pulsa 0 o Enter para salir y cerrar el menú.
