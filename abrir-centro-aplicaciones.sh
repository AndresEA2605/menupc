#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TITLE="Centro de aplicaciones"
APP="python3 '$SCRIPT_DIR/menu-inicio.py'"
SHELL_COMMAND="printf '\\033]0;${TITLE}\\007'; exec ${APP}"

if [[ "${1:-}" == "--inicio" ]]; then
    sleep 10
fi

# En Hyprland, recuerda el monitor enfocado antes de iniciar la terminal.
monitor=""
if command -v hyprctl >/dev/null 2>&1; then
    monitor="$(hyprctl -j monitors 2>/dev/null | python3 -c '
import json, sys
try:
    print(next((m["name"] for m in json.load(sys.stdin) if m.get("focused")), ""))
except (ValueError, KeyError, TypeError):
    pass
' 2>/dev/null || true)"
fi

if command -v kitty >/dev/null 2>&1; then
    kitty --single-instance --instance-group=centro-aplicaciones \
        --wait-for-single-instance-window-close \
        --class centro-aplicaciones --title "$TITLE" \
        bash -lc "$SHELL_COMMAND" &
    terminal_pid=$!

    if [[ -n "$monitor" ]]; then
        for _attempt in {1..50}; do
            address="$(hyprctl -j clients 2>/dev/null | python3 -c '
import json, sys
try:
    clients = json.load(sys.stdin)
    window = next((c for c in clients if c.get("class") == "centro-aplicaciones"), None)
    print(window.get("address", "") if window else "")
except (ValueError, TypeError):
    pass
' 2>/dev/null || true)"
            if [[ -n "$address" ]]; then
                hyprctl dispatch focuswindow "address:$address" >/dev/null 2>&1 || true
                hyprctl dispatch movewindow "mon:$monitor" >/dev/null 2>&1 || true
                break
            fi
            sleep 0.1
        done
    fi
    wait "$terminal_pid"
elif command -v cosmic-term >/dev/null 2>&1; then
    exec cosmic-term --no-daemon -- bash -lc "$SHELL_COMMAND"
elif command -v alacritty >/dev/null 2>&1; then
    exec alacritty --title "$TITLE" -e bash -lc "$SHELL_COMMAND"
elif command -v gnome-terminal >/dev/null 2>&1; then
    exec gnome-terminal --title="$TITLE" -- bash -lc "$SHELL_COMMAND"
elif command -v xfce4-terminal >/dev/null 2>&1; then
    exec xfce4-terminal --title="$TITLE" --command="bash -lc \"$SHELL_COMMAND\""
elif command -v konsole >/dev/null 2>&1; then
    exec konsole --title "$TITLE" -e bash -lc "$SHELL_COMMAND"
elif command -v xterm >/dev/null 2>&1; then
    exec xterm -T "$TITLE" -e bash -lc "$SHELL_COMMAND"
else
    printf 'No se encontró una terminal compatible. Instala Kitty, COSMIC Terminal, Alacritty, GNOME Terminal, XFCE Terminal, Konsole o xterm.\n' >&2
    exit 127
fi
