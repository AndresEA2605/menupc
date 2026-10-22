#!/usr/bin/env python3
"""Menú interactivo, ordenado por categorías, de aplicaciones instaladas."""

import configparser
import fcntl
import itertools
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import termios
import time
import tty
import unicodedata
from pathlib import Path


HOME = Path.home()
APP_DIRS = [
    Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "applications",
    Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "flatpak/exports/share/applications",
    Path("/var/lib/flatpak/exports/share/applications"),
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
]
SECTIONS = [
    ("Juegos", {"Game"}),
    ("Plataformas", set()),
    ("Internet", {"Network", "WebBrowser", "Email", "Chat", "IRCClient", "InstantMessaging", "Feed", "News"}),
    ("Oficina", {"Office", "WordProcessor", "Spreadsheet", "Presentation"}),
    ("Multimedia", {"AudioVideo", "Audio", "Video", "Player", "Recorder", "Music"}),
    ("Gráficos", {"Graphics", "2DGraphics", "3DGraphics", "Photography", "RasterGraphics", "VectorGraphics", "Scanning"}),
    ("Desarrollo", {"Development", "IDE", "Debugger"}),
    ("Sistema", {"System", "Monitor", "FileManager", "Filesystem", "Archiving", "Compression", "Security", "TerminalEmulator"}),
    ("Utilidades", {"Utility", "Utilities", "Calculator", "TextEditor", "Accessibility", "Core", "X-GNOME-Utilities", "X-KDE-Utilities"}),
    ("Configuración", {"Settings", "DesktopSettings", "HardwareSettings", "PackageManager"}),
    ("Otras", set()),
]
SECTION_OVERRIDES = {
    "com.spotify.Client": "Multimedia",
    "discord": "Internet",
    "steam": "Plataformas",
    "com.ktechpit.whatsie": "Internet",
    "FreeTube": "Multimedia",
    "io.github.benjamimgois.goverlay": "Configuración",
    "com.pokemmo.PokeMMO.Settings": "Configuración",
}
FLATPAK_LAUNCHERS = {
    "com.spotify.Client": [
        "flatpak", "run", "--branch=stable", "--arch=x86_64",
        "--command=spotify", "com.spotify.Client",
    ],
    "com.pokemmo.PokeMMO": [
        "flatpak", "run", "--branch=stable", "--arch=x86_64",
        "--command=pokemmo.sh", "com.pokemmo.PokeMMO", "--launch",
    ],
}
DISPLAY_NAME_OVERRIDES = {
    "archipelago": "Pokémon Esmeralda",
}
ICON_HINTS = (
    (("spotify",), "♫", "32"),
    (("discord", "whatsie"), "◉", "36"),
    (("steam",), "◆", "34"),
    (("firefox", "chrome", "chromium", "browser", "freetube"), "◎", "36"),
    (("game", "pokemon", "pokemmo", "bizhawk"), "♟", "33"),
    (("code", "codex", "studio", "editor"), "⌘", "35"),
    (("mail", "email", "thunderbird"), "✉", "31"),
    (("settings", "config", "control"), "⚙", "33"),
)


class TerminalResized(Exception):
    """Indica que el menú debe recalcular su distribución."""


def handle_terminal_resize(_signum, _frame):
    raise TerminalResized


def run_system_action(choice):
    """Ejecuta las acciones de mantenimiento sin cambiar la geometría del menú."""
    choice = choice.casefold()
    if choice == "r":
        # Reinicia el catálogo en la misma terminal; abrir otra ventana deja
        # la anterior en una shell vacía en emuladores que no se pueden cerrar
        # de forma portable.
        print("\033[?1049l", end="", flush=True)
        script = str(Path(__file__).resolve())
        os.execv(sys.executable, [sys.executable, script])
    if choice == "c":
        codex_path = shutil.which("codex")
        codex_env = os.environ.copy()
        if codex_path is None:
            nvm_codex = sorted(
                (HOME / ".nvm/versions/node").glob("*/bin/codex"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if nvm_codex:
                codex_path = str(nvm_codex[0])
                codex_env["PATH"] = (
                    f"{nvm_codex[0].parent}{os.pathsep}{codex_env.get('PATH', '')}"
                )

        if codex_path is None:
            print("No se encontró el comando codex en PATH.")
            wait_key("Pulsa una tecla para volver…")
        else:
            subprocess.run([codex_path], env=codex_env, check=False)
        return True
    locations = {
        "a": (HOME, "Inicio"),
        "b": (HOME / "Downloads", "Descargas"),
        "s": (Path("/"), "Sistema"),
    }
    if choice in locations:
        path, label = locations[choice]
        if not path.is_dir():
            print(f"No existe la carpeta {label}: {path}")
            wait_key("Pulsa una tecla para volver…")
            return True
        if not shutil.which("xdg-open"):
            print("No se encontró xdg-open para abrir carpetas.")
        else:
            subprocess.Popen(
                ["xdg-open", str(path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print(f"Abriendo {label}: {path}")
        wait_key("Pulsa una tecla para volver…")
        return True
    if choice == "e":
        usage = shutil.disk_usage(HOME)
        used_percent = usage.used / usage.total * 100 if usage.total else 0
        gib = 1024 ** 3
        print(f"Disco de inicio: {usage.free / gib:.1f} GiB libres de {usage.total / gib:.1f} GiB.")
        print(f"Uso: {used_percent:.1f}% ({usage.used / gib:.1f} GiB ocupados).")
        wait_key("Pulsa una tecla para volver…")
        return True
    if choice == "m":
        monitor = next((name for name in ("btop", "htop", "top") if shutil.which(name)), None)
        if monitor:
            subprocess.run([monitor], check=False)
        else:
            print("No se encontró btop, htop ni top para mostrar los procesos.")
            wait_key("Pulsa una tecla para volver…")
        return True
    if choice in {"t", "35"}:
        confirmation = input(
            "¿Eliminar archivos propios de /tmp con más de 24 horas? [s/N]: "
        ).strip().casefold()
        if confirmation not in {"s", "si", "sí"}:
            print("Limpieza cancelada.")
            wait_key("Pulsa una tecla para volver…")
            return True
        cutoff = time.time() - 24 * 60 * 60
        removed = 0
        for entry in Path(tempfile.gettempdir()).iterdir():
            try:
                info = entry.lstat()
                if info.st_uid != os.getuid() or info.st_mtime >= cutoff or not entry.is_file():
                    continue
                entry.unlink()
                removed += 1
            except (OSError, PermissionError):
                continue
        print(f"Se eliminaron {removed} archivos temporales antiguos (más de 24 horas).")
        wait_key("Pulsa una tecla para volver…")
        return True
    if choice in {"d", "36"}:
        for command in (["resolvectl", "flush-caches"], ["systemd-resolve", "--flush-caches"]):
            if shutil.which(command[0]):
                result = subprocess.run(command, capture_output=True, text=True)
                if result.returncode == 0:
                    print("Caché DNS vaciada; el sistema consultará de nuevo sus servidores DNS.")
                else:
                    print("No se pudo vaciar la caché DNS. Comprueba el servicio de resolución del sistema.")
                wait_key("Pulsa una tecla para volver…")
                return True
        print("No se encontró resolvectl ni systemd-resolve; no se cambió la configuración DNS.")
        wait_key("Pulsa una tecla para volver…")
        return True
    return None


def acquire_single_instance():
    """Reemplaza una instancia anterior para que solo quede un menú activo."""
    lock_path = Path(tempfile.gettempdir()) / f"menu-inicio-{os.getuid()}.lock"
    lock_file = lock_path.open("a+")
    for _attempt in range(30):
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_file.seek(0)
            try:
                previous_pid = int(lock_file.readline().strip())
                if previous_pid != os.getpid():
                    os.kill(previous_pid, signal.SIGTERM)
            except (ValueError, ProcessLookupError):
                pass
            time.sleep(0.1)
            continue

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(f"{os.getpid()}\n")
        lock_file.flush()
        return lock_file

    lock_file.close()
    print("No se pudo cerrar la instancia anterior del centro de aplicaciones.")
    return None


def wait_key(prompt):
    """Espera una sola tecla sin imprimir entrada ni salida de la app."""
    print(prompt, end="", flush=True)
    try:
        fd = os.open("/dev/tty", os.O_RDONLY)
        try:
            previous = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                os.read(fd, 1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        finally:
            os.close(fd)
        print()
    except (OSError, termios.error):
        input()


def launchers():
    found = {}
    # Algunas instalaciones Flatpak no crean el directorio de exportación
    # habitual; en ese caso, leemos los .desktop de sus despliegues activos.
    flatpak_exports = (
        base.glob("*/*/*/*/export/share/applications")
        for base in (
            HOME / ".local/share/flatpak/app",
            Path("/var/lib/flatpak/app"),
        )
    )
    for directory in [*APP_DIRS, *(path for paths in flatpak_exports for path in paths)]:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.desktop")):
            # BizHawk se abre desde el lanzador de Pokémon Esmeralda; no lo
            # mostramos como un tercer juego independiente en este menú.
            if path.stem == "bizhawk":
                continue
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
                entry = parser["Desktop Entry"]
            except (OSError, KeyError, configparser.Error):
                continue
            if entry.get("Type") != "Application" or entry.getboolean("NoDisplay", fallback=False) or entry.getboolean("Hidden", fallback=False):
                continue
            executable = entry.get("TryExec", "").strip()
            if not executable:
                try:
                    executable = shlex.split(entry.get("Exec", ""))[0]
                except (IndexError, ValueError):
                    executable = ""
            if executable and not (
                Path(executable).is_file()
                if "/" in executable else shutil.which(executable)
            ):
                # Los lanzadores D-Bus pueden no declarar Exec, pero en ese
                # caso no hay un binario que podamos comprobar aquí.
                if entry.getboolean("DBusActivatable", fallback=False):
                    executable = ""
                else:
                    continue
            if not executable and not entry.getboolean("DBusActivatable", fallback=False):
                continue
            name = DISPLAY_NAME_OVERRIDES.get(
                path.stem, entry.get("Name", "").strip()
            )
            if name:
                found.setdefault(path.stem, (name, set(entry.get("Categories", "").split(";"))))
    return sorted(found.items(), key=lambda item: item[1][0].casefold())


def grouped_items(items):
    groups = [(title, []) for title, _ in SECTIONS]
    for desktop_id, (name, categories) in items:
        preferred_section = SECTION_OVERRIDES.get(desktop_id)
        if preferred_section:
            for title, entries in groups:
                if title == preferred_section:
                    entries.append((desktop_id, name))
                    break
            continue
        placed = False
        for index, (_, accepted) in enumerate(SECTIONS):
            if accepted and accepted.intersection(categories):
                groups[index][1].append((desktop_id, name))
                placed = True
                break
        if not placed:
            groups[-1][1].append((desktop_id, name))
    return [(title, entries) for title, entries in groups if entries]


def display_width(text):
    """Ancho visible aproximado en celdas de terminal (sin contar ANSI)."""
    text = re.sub(r"\033\[[0-9;]*m", "", text)
    width = 0
    for char in text:
        category = unicodedata.category(char)
        if category.startswith("M") or category in {"Cc", "Cf"}:
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


def fit_text(text, width):
    if display_width(text) <= width:
        return text
    if width <= 1:
        return "…"[:width]
    result = ""
    for char in text:
        if display_width(result + char + "…") > width:
            break
        result += char
    return result + "…"


def application_icon(desktop_id, name):
    identity = f"{desktop_id} {name}".casefold()
    for hints, icon, color in ICON_HINTS:
        if any(hint in identity for hint in hints):
            return icon, color
    return "●", "36"


def arrange_groups(groups, column_count):
    """Divide en columnas contiguas y equilibradas sin separar categorías."""
    blocks = [(title, entries, len(entries) + 1) for title, entries in groups]
    if not blocks:
        return []
    column_count = min(column_count, len(blocks))
    best = None
    for cuts in itertools.combinations(range(1, len(blocks)), column_count - 1):
        bounds = (0, *cuts, len(blocks))
        columns = [blocks[bounds[i]:bounds[i + 1]] for i in range(column_count)]
        heights = [sum(block[2] for block in column) for column in columns]
        score = (max(heights), max(heights) - min(heights))
        if best is None or score < best[0]:
            best = (score, columns)
    return [[(title, entries) for title, entries, _ in column] for column in best[1]]


def show_menu():
    """Catálogo interactivo: encontrar una aplicación y abrirla."""
    items = launchers()
    if not items:
        print("No encontré aplicaciones disponibles en el sistema.")
        wait_key("Pulsa una tecla para salir…")
        return False

    groups = grouped_items(items)
    query = ""
    category = "Todas"
    scroll = 0

    while True:
        visible_groups = []
        for title, entries in groups:
            if category != "Todas" and title != category:
                continue
            matches = [
                (app_id, name) for app_id, name in entries
                if query.casefold() in f"{name} {app_id}".casefold()
            ]
            if matches:
                visible_groups.append((title, matches))
        ordered = [app for _, entries in visible_groups for app in entries]
        indexes = {app_id: index for index, (app_id, _) in enumerate(ordered, 1)}
        terminal = shutil.get_terminal_size((80, 24))
        width, height = max(1, terminal.columns), max(1, terminal.lines)
        content_width = max(1, width - 4)
        compact = width < 56
        panel_count = 1 if compact else min(4, max(1, content_width // 48))
        panels = arrange_groups(visible_groups, panel_count)
        panel_width = max(1, (content_width - 3 * (len(panels) - 1)) // max(1, len(panels)))
        panel_lines = [[] for _ in panels]
        for panel_index, panel in enumerate(panels):
            for section, entries in panel:
                panel_lines[panel_index].append(("heading", f"{section}  ·  {len(entries)}"))
                for app_id, name in entries:
                    icon, color = application_icon(app_id, name)
                    label = fit_text(f"{indexes[app_id]:>2}  {icon}  {name}", panel_width)
                    panel_lines[panel_index].append(("app", (label, color)))

        line_count = max((len(lines) for lines in panel_lines), default=0)
        controls = "Número abrir · G configuración · / buscar · : categoría · h herramientas · ? ayuda · 0 salir"
        if compact:
            controls = "n abrir · G configuración · / buscar · : categoría · h herramientas · ? ayuda · 0 salir"
        footer = textwrap.wrap(controls, width=content_width, break_long_words=True)
        list_height = max(1, height - 8 - len(footer))
        max_scroll = max(0, line_count - list_height)
        scroll = min(scroll, max_scroll)

        print("\033[2J\033[H", end="", flush=True)
        print(f"\033[1;36m{fit_text('CENTRO DE APLICACIONES', content_width):^{content_width}}\033[0m")
        print(f"\033[2m{'─' * content_width}\033[0m")
        status = f"{len(ordered)} aplicaciones  ·  {category}"
        if query:
            status += f"  ·  búsqueda: {query}"
        print(fit_text(status, content_width))
        category_line = "Categorías: " + " · ".join(title for title, _ in groups)
        print(fit_text(category_line, content_width))
        print()

        end = min(line_count, scroll + list_height)
        for row in range(scroll, end):
            cells = []
            for index, lines in enumerate(panel_lines):
                if row >= len(lines):
                    cells.append(" " * panel_width)
                    continue
                kind, value = lines[row]
                if kind == "heading":
                    cell = f"\033[1;36m{fit_text(value, panel_width)}\033[0m"
                else:
                    label, color = value
                    icon_at = label.find("  ") + 2
                    cell = (
                        f"\033[2m{label[:2]}\033[0m{label[2:icon_at]}"
                        f"\033[{color}m{label[icon_at:icon_at + 1]}\033[0m"
                        f"{label[icon_at + 1:]}"
                    )
                cells.append(cell)
            print("   ".join(cells).rstrip())
        if not ordered:
            print(f"\033[2m{fit_text('Sin coincidencias. Usa / para buscar o :todas para limpiar el filtro.', content_width)}\033[0m")
        if max_scroll:
            print(f"\033[2mJ/K desplazar · {scroll + 1}–{end} de {line_count}\033[0m")
        print(f"\033[2m{'─' * content_width}\033[0m")
        for line in footer:
            print(fit_text(line.center(content_width), content_width))

        try:
            choice = input("\033[1;36m› \033[0m").strip()
        except TerminalResized:
            return True
        if not choice or choice == "0":
            return False
        command = choice.casefold()
        if command == "g":
            category = "Todas" if category == "Configuración" else "Configuración"
            query = ""
            scroll = 0
            continue
        if command.startswith("/"):
            query = choice[1:].strip()
            scroll = 0
            continue
        if command.startswith(":"):
            requested = choice[1:].strip().casefold()
            categories = [title for title, _ in groups]
            if requested in {"", "todas", "all"}:
                category = "Todas"
            else:
                exact = next((name for name in categories if name.casefold() == requested), None)
                partial = [name for name in categories if requested in name.casefold()]
                if exact or len(partial) == 1:
                    category = exact or partial[0]
                else:
                    print("Categorías: " + ", ".join(categories))
                    wait_key("Usa : seguido del nombre de una categoría. Pulsa una tecla…")
            scroll = 0
            continue
        if command in {"j", "k"}:
            scroll = min(max_scroll, max(0, scroll + (1 if command == "j" else -1)))
            continue
        if command in {"?", "ayuda", "help"}:
            print("\nAYUDA")
            print("  número   Abrir una aplicación")
            print("  /texto   Buscar por nombre o identificador; / limpia la búsqueda")
            print("  :nombre  Filtrar por categoría; :todas muestra todas")
            print("  g        Mostrar/ocultar aplicaciones de configuración")
            print("  j / k    Desplazar la lista")
            print("  h        Ver herramientas")
            print("  0 / Enter  Salir y cerrar el menú")
            wait_key("Pulsa una tecla para volver…")
            continue
        if command == "h":
            print("\nHERRAMIENTAS")
            print("  [A] Inicio  [B] Descargas  [S] Sistema  [C] Codex")
            print("  [E] Espacio  [M] Procesos  [T] Temporales  [D] DNS")
            print("  [R] Recargar  [Enter] Volver")
            try:
                tool_choice = input("› Herramienta: ").strip().casefold()
            except TerminalResized:
                return True
            if tool_choice:
                result = run_system_action(tool_choice)
                if result is not None:
                    return result
            continue
        if command.isdigit() and 1 <= int(command) <= len(ordered):
            app_id, name = ordered[int(command) - 1]
            print(f"\nAbriendo {name}…")
            launch_command = FLATPAK_LAUNCHERS.get(app_id, ["gtk-launch", app_id])
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                try:
                    process = subprocess.Popen(launch_command, stdout=stdout, stderr=stderr)
                    spinner = "|/-\\"
                    frame = 0
                    while process.poll() is None:
                        print(f"\r  {spinner[frame % len(spinner)]} Iniciando…", end="", flush=True)
                        frame += 1
                        time.sleep(0.12)
                    print("\r" + " " * width + "\r", end="", flush=True)
                    if process.returncode:
                        stderr.seek(0)
                        details = stderr.read().decode("utf-8", errors="replace").strip()
                        print(f"No se pudo abrir {name} (código {process.returncode}).")
                        if details:
                            print(details)
                    else:
                        print(f"{name} se inició.")
                except OSError as error:
                    print(f"No se pudo abrir {name}: {error}")
                wait_key("Pulsa una tecla para volver al catálogo…")
            continue
        print("Opción no reconocida. Pulsa ? para ver los controles.")
        wait_key("Pulsa una tecla para continuar…")


def main():
    instance_lock = acquire_single_instance()
    if instance_lock is None:
        return
    previous_term_handler = signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(0))
    previous_resize_handler = signal.signal(signal.SIGWINCH, handle_terminal_resize)
    print("\033[?1049h", end="", flush=True)
    try:
        while True:
            try:
                keep_running = show_menu()
            except TerminalResized:
                continue
            if not keep_running:
                break
    finally:
        print("\033[?1049l", end="", flush=True)
        signal.signal(signal.SIGTERM, previous_term_handler)
        signal.signal(signal.SIGWINCH, previous_resize_handler)


if __name__ == "__main__":
    main()
