#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Abre primero el menú para que COSMIC le asigne el mosaico más grande.
titulos=(
    "Menú de aplicaciones"
    "Neofetch · solo visual"
    "Aurora viva"
    "Campo estelar"
)
comandos=(
    "python3 '$SCRIPT_DIR/menu-inicio.py'"
    "neofetch --config off; exec </dev/null; exec sleep infinity"
    "python3 '$SCRIPT_DIR/aurora-terminal.py'"
    "python3 '$SCRIPT_DIR/aurora-terminal.py' --stars"
)

if [[ -t 0 ]]; then
    read -r -p "Pon el puntero en la pantalla secundaria y pulsa Enter para abrir el menú: " _
fi

for i in "${!comandos[@]}"; do
    titulo=${titulos[$i]}
    comando=${comandos[$i]}
    cosmic-term --no-daemon -- bash -lc \
        "printf '\\033]0;${titulo}\\007'; ${comando}; exec bash" &
    if [[ $i -eq 0 && -t 0 ]]; then
        read -r -p "Menú abierto. Mueve el puntero a la pantalla deseada y pulsa Enter para abrir las otras terminales: " _
    fi
    sleep 0.8
done

wait
