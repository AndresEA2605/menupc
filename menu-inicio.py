#!/usr/bin/env python3
"""Menú interactivo, ordenado por categorías, de aplicaciones instaladas."""

import configparser
import fcntl
import itertools
import os
import re
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
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
]
SECTIONS = [
    ("Más usados", set()),
    ("Juegos", {"Game"}),
    ("Plataformas", set()),
    ("Internet", {"Network", "WebBrowser", "Email", "Chat", "IRCClient"}),
    ("Oficina", {"Office", "WordProcessor", "Spreadsheet", "Presentation"}),
    ("Desarrollo", {"Development", "IDE", "Debugger"}),
    ("Configuración", {"Settings"}),
]
SECTION_OVERRIDES = {
    "com.spotify.Client": "Más usados",
    "discord": "Más usados",
    "steam": "Más usados",
    "com.ktechpit.whatsie": "Más usados",
    "io.freetubeapp.FreeTube": "Más usados",
    "io.github.benjamimgois.goverlay": "Configuración",
    "com.pokemmo.PokeMMO.Settings": "Configuración",
}
# Oculta herramientas de mantenimiento y aplicaciones de apoyo que llenan el
# menú. Los accesos de configuración siguen visibles en su propia sección.
HIDDEN_CATEGORIES = {"System", "Utility", "Accessibility", "FileManager"}
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
        # Cierra las cuatro terminales y vuelve a iniciar el flujo desde su
        # lanzador, en vez de limitarse a recargar el menú actual.
        launcher = Path(__file__).with_name("iniciar-matrix-4.sh").resolve()
        subprocess.Popen(
            ["bash", "-lc", f"sleep 0.5; pkill -u {os.getuid()} -x cosmic-term >/dev/null 2>&1 || true; sleep 0.5; exec {launcher}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return False
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
    if choice == "0":
        # Cierra los terminales del usuario (incluido el que contiene el menú)
        # después de que este proceso termine.
        subprocess.Popen(
            ["bash", "-lc", "sleep 0.4; pkill -u \"$(id -u)\" -x cosmic-term >/dev/null 2>&1 || true"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return False
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
    """Evita que dos terminales de inicio dibujen el mismo menú a la vez."""
    lock_path = Path(tempfile.gettempdir()) / f"menu-inicio-{os.getuid()}.lock"
    lock_file = lock_path.open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("El centro de aplicaciones ya está abierto.")
        return None
    return lock_file


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
    flatpak_exports = (HOME / ".local/share/flatpak/app").glob(
        "*/*/*/*/export/share/applications"
    )
    for directory in [*APP_DIRS, *flatpak_exports]:
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
        if HIDDEN_CATEGORIES.intersection(categories):
            continue
        for index, (_, accepted) in enumerate(SECTIONS):
            if accepted.intersection(categories):
                groups[index][1].append((desktop_id, name))
                break
        # Deja fuera lanzadores sin categoría útil para que el menú siga
        # enfocado en aplicaciones de uso diario.
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


def show_menu(show_configuration=False, animate=False):
    print("\033[2J\033[H", end="", flush=True)
    items = launchers()
    if not items:
        print("No encontré aplicaciones instaladas.")
        return False, show_configuration

    all_groups = grouped_items(items)
    configuration_entries = next(
        (entries for title, entries in all_groups if title == "Configuración"),
        [],
    )
    groups = [
        (title, entries)
        for title, entries in all_groups
        if title != "Configuración" or show_configuration
    ]
    if not groups:
        print("No hay aplicaciones disponibles en las categorías visibles.")
        return False, show_configuration

    ordered = [item for _, entries in groups for item in entries]
    numbers = {desktop_id: index for index, (desktop_id, _) in enumerate(ordered, 1)}
    terminal = shutil.get_terminal_size((80, 24))
    terminal_width = max(1, terminal.columns)
    terminal_height = max(1, terminal.lines)
    side_padding = min(2, max(0, (terminal_width - 1) // 2))
    content_width = max(1, terminal_width - side_padding * 2)
    visible_groups = [(title, entries) for title, entries in groups if entries]
    compact_layout = terminal_width < 42 or terminal_height < 12
    max_columns = max(1, (content_width + 2) // 36)
    panel_count = min(2, max_columns, len(visible_groups))
    panels = arrange_groups(visible_groups, panel_count)

    action_rows = (
        (
            "A inicio · B descargas · S sistema",
            "T temporales · D DNS · E espacio · M procesos",
            "0 terminales · C Codex · R reinicio · Enter salir",
        )
        if compact_layout else (
            "[A] Inicio  [B] Descargas  [S] Sistema",
            "[T] Temporales  [D] DNS  [E] Espacio  [M] Procesos",
            "[0] Terminales  [C] Codex  [R] Reiniciar  [Enter] Salir",
        )
    )
    if configuration_entries:
        toggle_label = (
            f"[G] Ocultar configuración ({len(configuration_entries)})"
            if show_configuration else
            f"[G] Configuración ({len(configuration_entries)})"
        )
        action_rows += (toggle_label,)
    action_lines = [
        line
        for row in action_rows
        for line in textwrap.wrap(row, width=content_width, break_long_words=True)
    ]
    reserved_rows = 6 if compact_layout else 7

    panel_lines = [[] for _ in panels]
    panel_widths = []
    gap = min(4, max(0, (content_width - 12 * len(panels)) // max(1, len(panels) - 1)))
    max_panel_width = max(
        1,
        min(52, (content_width - gap * (len(panels) - 1)) // len(panels)),
    )
    number_width = len(str(len(ordered)))
    for panel_index, panel in enumerate(panels):
        panel_content_width = max(
            (display_width(
                f"{len(ordered):>{number_width}}  "
                f"{application_icon(desktop_id, name)[0]}  {name}"
            ) for _, entries in panel for desktop_id, name in entries),
            default=0,
        )
        heading_width = max(
            (display_width(f"{section} · {len(entries)}") for section, entries in panel),
            default=0,
        )
        panel_width = min(max_panel_width, max(1, panel_content_width, heading_width))
        panel_widths.append(panel_width)
        for section, entries in panel:
            heading = fit_text(f"{section} · {len(entries)}", panel_width)
            panel_lines[panel_index].append(f"\033[1;36m{heading}\033[0m")
            for desktop_id, name in entries:
                number_value = f"{numbers[desktop_id]:>{number_width}}"
                number = f"\033[2m{number_value}\033[0m"
                icon, icon_color = application_icon(desktop_id, name)
                if panel_width > number_width + 5:
                    label = fit_text(
                        f"{number_value}  {icon}  {name}", panel_width
                    )
                    label = (
                        f"{number}  \033[{icon_color}m{icon}\033[0m  "
                        f"{label[number_width + 5:]}"
                    )
                else:
                    label = fit_text(f"{number_value}  {name}", panel_width)
                    label = f"{number}  {label[number_width + 2:]}"
                panel_lines[panel_index].append(label)

    widest_panel = max(map(len, panel_lines), default=0)
    total_panel_width = sum(panel_widths) + gap * (len(panels) - 1)
    outer_padding = side_padding + max(0, (content_width - total_panel_width) // 2)
    available_rows = max(1, terminal_height - len(action_lines) - reserved_rows)
    max_scroll = max(0, widest_panel - available_rows)
    if max_scroll:
        action_lines.extend(textwrap.wrap("[J/K] Desplazar", width=content_width))
        available_rows = max(1, terminal_height - len(action_lines) - reserved_rows)
        max_scroll = max(0, widest_panel - available_rows)
    scroll_offset = 0
    visible_rows = min(widest_panel, available_rows)
    body_rows = visible_rows + len(action_lines) + reserved_rows - 1
    body_top_padding = max(0, (terminal_height - 1 - body_rows) // 2) if not max_scroll else 0
    options_top_padding = body_top_padding // 2
    separator_gap = max(0, options_top_padding - 1)

    while True:
        print("\033[2J\033[H", end="", flush=True)
        title = fit_text("CENTRO DE APLICACIONES", content_width)
        title_padding = side_padding + max(0, (content_width - display_width(title)) // 2)
        if animate:
            print(" " * title_padding + "\033[1;36m", end="", flush=True)
            for character in title:
                print(character, end="", flush=True)
                time.sleep(0.025)
            print("\033[0m")
        else:
            print(" " * title_padding + f"\033[1;36m{title}\033[0m")
        animate = False
        rule = "─" * min(24, content_width)
        rule_padding = side_padding + max(0, (content_width - display_width(rule)) // 2)
        print(" " * rule_padding + f"\033[2;36m{rule}\033[0m")
        if options_top_padding:
            print("\n" * options_top_padding, end="")
        first_row = scroll_offset
        last_row = min(first_row + available_rows, widest_panel)
        for row in range(first_row, last_row):
            cells = [lines[row] if row < len(lines) else "" for lines in panel_lines]
            padded = []
            for index, cell in enumerate(cells):
                padded.append(cell + " " * max(0, panel_widths[index] - display_width(cell)))
            print(" " * outer_padding + (" " * gap).join(padded).rstrip())
        if separator_gap:
            print("\n" * separator_gap, end="")
        print()
        print(" " * side_padding + f"\033[2m{'─' * content_width}\033[0m")
        print()
        if not compact_layout:
            heading = fit_text("ACCIONES", content_width)
            heading_padding = side_padding + max(0, (content_width - display_width(heading)) // 2)
            print(" " * heading_padding + heading)
        for line in action_lines:
            line_padding = side_padding + max(0, (content_width - display_width(line)) // 2)
            print(" " * line_padding + line)

        prompt = "› Opción: " if terminal_width >= 16 else "› "
        prompt_padding = side_padding + max(0, (content_width - display_width(prompt)) // 2)
        try:
            choice = input(" " * prompt_padding + f"\033[1;36m{prompt}\033[0m").strip()
        except TerminalResized:
            return True, show_configuration
        if not choice:
            return False, show_configuration
        if choice.casefold() == "g" and configuration_entries:
            return True, not show_configuration
        if choice.casefold() == "j" and scroll_offset < max_scroll:
            scroll_offset += 1
            continue
        if choice.casefold() == "k" and scroll_offset > 0:
            scroll_offset -= 1
            continue
        if choice.isdigit() and 1 <= int(choice) <= len(ordered):
            desktop_id, name = ordered[int(choice) - 1]
            print(f"\nAbriendo {name}…")
            command = FLATPAK_LAUNCHERS.get(desktop_id, ["gtk-launch", desktop_id])
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                try:
                    process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
                    spinner = "|/-\\"
                    frame = 0
                    while process.poll() is None:
                        print(f"\r  {spinner[frame % len(spinner)]} Cargando…", end="", flush=True)
                        frame += 1
                        time.sleep(0.12)
                    returncode = process.returncode
                    print("\r" + " " * terminal_width + "\r", end="", flush=True)
                    if returncode:
                        stderr.seek(0)
                        details = stderr.read().decode("utf-8", errors="replace").strip()
                        print(f"No se pudo abrir {name} (código {returncode}).")
                        if details:
                            print(details)
                        wait_key("Pulsa una tecla para volver…")
                    else:
                        wait_key(f"{name} iniciado. Oprime una tecla para volver…")
                except OSError as error:
                    print(f"No se pudo abrir {name}: {error}")
                    wait_key("Pulsa una tecla para volver…")
            return True, show_configuration

        action_result = run_system_action(choice)
        if action_result is not None:
            return action_result, show_configuration
        navigation = "J/K para desplazar, " if max_scroll else ""
        print(f"Opción inválida; elige una aplicación, {navigation}o una acción.")
        wait_key("Pulsa una tecla para continuar…")


def main():
    instance_lock = acquire_single_instance()
    if instance_lock is None:
        return
    previous_resize_handler = signal.signal(signal.SIGWINCH, handle_terminal_resize)
    print("\033[?1049h", end="", flush=True)
    try:
        show_configuration = False
        animate = True
        while True:
            try:
                keep_running, show_configuration = show_menu(
                    show_configuration, animate=animate
                )
                animate = False
            except TerminalResized:
                continue
            if not keep_running:
                break
    finally:
        print("\033[?1049l", end="", flush=True)
        signal.signal(signal.SIGWINCH, previous_resize_handler)


if __name__ == "__main__":
    main()
