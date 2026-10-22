# Centro de aplicaciones

Lanzador de terminal con una vista simple para encontrar y abrir aplicaciones
instaladas. Lee lanzadores .desktop de usuario, sistema y Flatpak; organiza
las apps por categoría y muestra en «Otras» las que no encajan en las secciones
conocidas. Las herramientas del sistema están agrupadas en una vista aparte.

## Controles

- Escribe el número de una aplicación para abrirla.
- Escribe /texto para buscar por nombre o identificador. Usa / para limpiar.
- Escribe :categoría para filtrar, o :todas para volver al catálogo completo.
- Usa J y K para desplazar la lista si no cabe en pantalla.
- Pulsa H para abrir la vista de herramientas y ? para ver la ayuda.
- Pulsa Enter para salir.

## Requisitos e instalación

Necesita Linux, Bash, Python 3, gtk-launch y una terminal compatible:
COSMIC Terminal, Kitty, Alacritty, GNOME Terminal, XFCE Terminal, Konsole o
xterm. xdg-open es opcional y se usa para abrir carpetas.

    mkdir -p ~/.local/bin
    cp iniciar-matrix-4.sh menu-inicio.py ~/.local/bin/
    chmod +x ~/.local/bin/iniciar-matrix-4.sh
    ~/.local/bin/iniciar-matrix-4.sh
