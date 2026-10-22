#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
titulo="Centro de aplicaciones"
comando="python3 '$SCRIPT_DIR/menu-inicio.py'"
shell_command="printf '\\033]0;${titulo}\\007'; exec ${comando}"
terminal_pid_file="${TMPDIR:-/tmp}/centro-app-terminal-${UID}.pid"

close_previous_terminal() {
    [[ -r "$terminal_pid_file" ]] || return 0
    read -r previous_pid < "$terminal_pid_file" || return 0
    [[ "$previous_pid" =~ ^[0-9]+$ ]] || return 0

    previous_name="$(ps -p "$previous_pid" -o comm= 2>/dev/null | tr -d '[:space:]' || true)"
    # Solo terminaciones que corresponden a una ventana propia. No terminar
    # servidores compartidos como GNOME Terminal, Kitty, XFCE Terminal o Konsole.
    case "$previous_name" in
        cosmic-term|alacritty|xterm)
            kill -TERM "$previous_pid" 2>/dev/null || true
            for _attempt in {1..20}; do
                kill -0 "$previous_pid" 2>/dev/null || break
                sleep 0.05
            done
            if kill -0 "$previous_pid" 2>/dev/null; then
                kill -KILL "$previous_pid" 2>/dev/null || true
            fi
            ;;
    esac
    rm -f "$terminal_pid_file"
}

close_source_terminal() {
    [[ -t 0 || -t 1 || -t 2 ]] || return 0

    ancestor="$PPID"
    for _attempt in {1..8}; do
        ancestor_name="$(ps -p "$ancestor" -o comm= 2>/dev/null | tr -d '[:space:]' || true)"
        case "$ancestor_name" in
            cosmic-term|alacritty|xterm)
                kill -TERM "$ancestor" 2>/dev/null || true
                return 0
                ;;
        esac
        next_ancestor="$(ps -p "$ancestor" -o ppid= 2>/dev/null | tr -d '[:space:]' || true)"
        [[ "$next_ancestor" =~ ^[0-9]+$ && "$next_ancestor" != 1 ]] || break
        ancestor="$next_ancestor"
    done

    # Si la terminal no aparece en la cadena de procesos, salir de la shell
    # que ejecutó el comando evita dejarla en un prompt vacío.
    parent_shell="$(ps -p "$PPID" -o comm= 2>/dev/null | tr -d '[:space:]' || true)"
    case "$parent_shell" in
        bash|zsh|fish|sh) kill -HUP "$PPID" 2>/dev/null || true ;;
    esac
}

launch_terminal() {
    close_previous_terminal
    nohup "$@" </dev/null >/dev/null 2>&1 &
    terminal_pid=$!
    printf '%s\n' "$terminal_pid" > "$terminal_pid_file"

    close_source_terminal
    exit 0
}

if command -v cosmic-term >/dev/null 2>&1; then
    launch_terminal cosmic-term --no-daemon -- bash -lc "$shell_command"
elif command -v kitty >/dev/null 2>&1; then
    launch_terminal kitty --title "$titulo" bash -lc "$shell_command"
elif command -v alacritty >/dev/null 2>&1; then
    launch_terminal alacritty --title "$titulo" -e bash -lc "$shell_command"
elif command -v gnome-terminal >/dev/null 2>&1; then
    launch_terminal gnome-terminal --title="$titulo" -- bash -lc "$shell_command"
elif command -v xfce4-terminal >/dev/null 2>&1; then
    launch_terminal xfce4-terminal --title="$titulo" --command="bash -lc \"$shell_command\""
elif command -v konsole >/dev/null 2>&1; then
    launch_terminal konsole --title "$titulo" -e bash -lc "$shell_command"
elif command -v xterm >/dev/null 2>&1; then
    launch_terminal xterm -T "$titulo" -e bash -lc "$shell_command"
else
    printf 'No se encontró una terminal compatible (COSMIC Terminal, Kitty, Alacritty, GNOME Terminal, XFCE Terminal, Konsole o xterm).\n' >&2
    exit 127
fi
