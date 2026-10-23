# Centro de aplicaciones

Centro de aplicaciones de escritorio para Linux y Windows. Permite consultar,
filtrar y abrir aplicaciones instaladas. La interfaz se adapta a cada sistema:

- **Linux:** menú interactivo en una terminal. Lee lanzadores `.desktop` del
  usuario, del sistema y de Flatpak; los agrupa usando sus categorías.
- **Windows:** ventana gráfica. Lee accesos directos `.lnk` de los menús Inicio
  del usuario y del sistema; permite buscar y filtrar por categoría.

Las dos versiones comparten el propósito y el nombre, pero sus instaladores y
sus controles son propios de cada sistema operativo.

## Requisitos

### Linux

- Una sesión gráfica y Python 3.
- Una terminal compatible: Kitty, COSMIC Terminal, Alacritty, GNOME Terminal,
  XFCE Terminal, Konsole o xterm.
- `gtk-launch` para abrir las aplicaciones registradas como lanzadores
  `.desktop`.
- `xdg-open` para abrir carpetas desde el menú.
- Opcional: Hyprland y Kitty. Si ambos están disponibles, el centro intenta
  abrirse en el monitor enfocado.

### Windows

- Windows 10 u 11.
- Windows PowerShell y Windows Forms, incluidos en Windows.
- Carpeta de inicio de sesión accesible para configurar el inicio automático.

## Instalación en Linux

Desde la carpeta del proyecto, ejecuta:

```bash
./instalar.sh
```

El instalador, sin requerir permisos de administrador:

1. Copia `menu-inicio.py` y `abrir-centro-aplicaciones.sh` a
   `~/.local/share/centro-aplicaciones`.
2. Crea el comando `centro-aplicaciones` en `~/.local/bin`.
3. Configura el inicio automático de la sesión gráfica.
4. Guarda una referencia para añadir el atajo de Hyprland en
   `~/.local/share/centro-aplicaciones/atajo-hyprland.conf`.

Si `~/.local/bin` no está en `PATH`, puedes ejecutar el centro con la ruta
completa: `~/.local/bin/centro-aplicaciones`.

### Atajo en Hyprland

Añade esta línea a `~/.config/hypr/hyprland.conf`:

```ini
$mainMod, A, exec, centro-aplicaciones
```

Puedes cambiar `A` por otra tecla y luego recargar la configuración:

```bash
hyprctl reload
```

El inicio automático se configura aparte; el atajo de Hyprland es opcional.
En otros entornos de escritorio, el instalador también configura el inicio
automático, pero la selección del monitor depende de la terminal y del gestor
de ventanas.

## Windows: abrir sin instalar

1. Descarga el proyecto y extrae todos sus archivos en una carpeta.
2. Haz doble clic en `abrir-centro-aplicaciones-windows.bat`.

El centro se ejecuta desde esa carpeta; no requiere instalar Python ni escribir
comandos. Conserva la carpeta mientras quieras seguir usándolo.

## Windows: inicio automático opcional

Haz doble clic en `instalar-windows.bat`. Esto copia el programa al perfil del
usuario actual y lo configura para abrirse al iniciar sesión. Puedes seguir
abriéndolo manualmente con `abrir-centro-aplicaciones-windows.bat`.
La interfaz usa Windows PowerShell y Windows Forms, incluidos en Windows.

El instalador comprueba que existan los archivos, las carpetas del perfil y los
componentes gráficos necesarios antes de crear el acceso directo. Si algo falla,
muestra el motivo en la consola del instalador.

## Uso en Linux

- Escribe el número de una aplicación y pulsa Enter para abrirla.
- Escribe `/texto` para buscar por nombre o identificador. Escribe `/` para
  borrar el filtro de búsqueda.
- Escribe `:categoría` para filtrar por una categoría y `:todas` para volver a
  mostrar todas.
- Pulsa **J** o **K** para desplazarte por la lista cuando no cabe en pantalla.
- Pulsa **G** para mostrar solo Sistema, Configuración y Gráficos; vuelve a pulsarla
  para regresar al catálogo. Las vistas **O** (Office), **U** (Utilidades),
  **M** (Multimedia) y **F** (Archivos) se muestran cuando hay aplicaciones
  disponibles en esas categorías. Pulsa la tecla de la vista activa para
  ocultarla y volver al catálogo.
- Las acciones inferiores permiten abrir Inicio (**A**), Descargas (**B**) o
  la raíz del sistema (**S**); ver espacio de almacenamiento (**E**); abrir el
  monitor de procesos (**P**); montar el disco en `/mnt/backup` (**H**); borrar
  archivos temporales propios de más de 24 horas (**T**); vaciar la caché DNS
  (**D**); o abrir Codex (**C**, si está instalado).
- **R** reinicia el menú. **Q** apaga el equipo, **Y** lo reinicia y **Z** lo
  pone en reposo; estas tres acciones piden confirmación. **Enter** o **0**
  cierra el menú.
Las herramientas que dependen de programas o servicios externos solo funcionan
si están instalados y disponibles en el sistema. Para montar `/mnt/backup` se
solicita autorización mediante `pkexec`.

## Uso en Windows

- Escribe en el campo de búsqueda para filtrar aplicaciones por nombre.
- Usa la lista desplegable para mostrar todas las aplicaciones, aplicaciones,
  juegos o utilidades.
- Selecciona una aplicación y pulsa **Abrir**, haz doble clic o pulsa Enter en
  la lista.

La versión actual descubre accesos directos `.lnk` ubicados en las carpetas
estándar de los menús Inicio del usuario y del sistema. Si una subcarpeta no se
puede leer, continúa con las demás y muestra un aviso en la ventana. Los accesos
directos se clasifican como juegos o utilidades si sus carpetas del menú Inicio
indican esas categorías; los demás aparecen como aplicaciones. Los programas
portables o instalados sin acceso directo en el menú Inicio no se detectan
automáticamente. Al abrir un acceso directo que haya sido eliminado o movido,
la ventana informa del error en lugar de cerrarse.

## Desinstalación

### Linux

Elimina los archivos y enlaces creados por el instalador:

```bash
rm -rf ~/.local/share/centro-aplicaciones
rm -f ~/.local/bin/centro-aplicaciones
rm -f ~/.config/autostart/centro-aplicaciones.desktop
```

Si añadiste un atajo de Hyprland, elimina también la línea correspondiente de
`~/.config/hypr/hyprland.conf` y recarga Hyprland.

### Windows

Elimina la carpeta `%LOCALAPPDATA%\CentroAplicaciones` y el acceso directo
`Centro de aplicaciones.lnk` de la carpeta Inicio de Windows. Esto desactiva
el inicio automático.
