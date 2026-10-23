# Centro de aplicaciones

Menú de terminal para buscar y abrir aplicaciones Linux instaladas. Lee
lanzadores `.desktop` de usuario, sistema y Flatpak, y las organiza por
categorías. En Hyprland con Kitty, abre la ventana en el monitor que estaba
enfocado al iniciarla.

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

## Requisitos

- Linux con una sesión gráfica y Python 3.
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
