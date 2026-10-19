# Inicio en cuatro terminales

Lanzador para COSMIC Terminal que abre cuatro mosaicos: menú de aplicaciones,
Neofetch, aurora animada y campo estelar. El menú incluye acciones y accesos a
aplicaciones disponibles en el sistema del usuario.

## Requisitos

- Linux con COSMIC Terminal (`cosmic-term`)
- Bash y Python 3 con el módulo `curses`
- `neofetch` para el segundo mosaico
- `xdg-open` y las aplicaciones que se quieran mostrar en el menú (opcionales)

## Instalar

Clona este repositorio y copia los tres archivos a `~/.local/bin`:

```bash
mkdir -p ~/.local/bin
cp iniciar-matrix-4.sh menu-inicio.py aurora-terminal.py ~/.local/bin/
chmod +x ~/.local/bin/iniciar-matrix-4.sh
```

Desde el directorio del repositorio, también puedes ejecutar directamente:

```bash
./iniciar-matrix-4.sh
```

El lanzador abre primero el menú. Si se ejecuta desde una terminal interactiva,
pide colocar el puntero en la pantalla deseada antes de abrir las demás ventanas.
