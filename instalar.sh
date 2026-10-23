#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/centro-aplicaciones"
BIN_DIR="${HOME}/.local/bin"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

for file in menu-inicio.py abrir-centro-aplicaciones.sh; do
    [[ -f "$SCRIPT_DIR/$file" ]] || { printf 'Falta el archivo: %s\n' "$file" >&2; exit 1; }
done

mkdir -p "$APP_DIR" "$BIN_DIR" "$AUTOSTART_DIR"
install -m 644 "$SCRIPT_DIR/menu-inicio.py" "$APP_DIR/menu-inicio.py"
install -m 755 "$SCRIPT_DIR/abrir-centro-aplicaciones.sh" "$APP_DIR/abrir-centro-aplicaciones.sh"

# Elimina los lanzadores duplicados de versiones anteriores de este paquete.
rm -f "$APP_DIR/iniciar-matrix-4.sh" "$APP_DIR/aurora-terminal.py" \
    "$BIN_DIR/abrir-centro-aplicaciones.sh" "$BIN_DIR/iniciar-matrix-4.sh" \
    "$BIN_DIR/iniciar-matrix-4-autostart.sh" "$BIN_DIR/centro-aplicaciones-inicio" \
    "$AUTOSTART_DIR/iniciar-matrix-4.desktop"

ln -sfn "$APP_DIR/abrir-centro-aplicaciones.sh" "$BIN_DIR/centro-aplicaciones"

cat > "$AUTOSTART_DIR/centro-aplicaciones.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Centro de aplicaciones
Comment=Abre el centro de aplicaciones al iniciar sesión
Exec=$BIN_DIR/centro-aplicaciones --inicio
TryExec=$BIN_DIR/centro-aplicaciones
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
X-Cosmic-Autostart-enabled=true
EOF

cat > "$APP_DIR/atajo-hyprland.conf" <<'EOF'
# Añade esta línea a tu configuración de Hyprland y cambia SUPER+A si lo prefieres:
$mainMod, A, exec, centro-aplicaciones
EOF

printf 'Instalado en: %s\n' "$APP_DIR"
printf 'Inicio automático configurado. Para el atajo, añade a ~/.config/hypr/hyprland.conf:\n'
printf '  $mainMod, A, exec, %s\n' "$BIN_DIR/centro-aplicaciones"
printf 'Luego recarga Hyprland con: hyprctl reload\n'
