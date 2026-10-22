#!/usr/bin/env python3
"""Menú interactivo, ordenado por categorías, de aplicaciones instaladas."""

import configparser
import fcntl
import itertools
import os
import pty
import re
import select
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
    ("Más usados", set()),
    ("Internet", {"Network", "WebBrowser", "Email", "Chat", "IRCClient", "InstantMessaging", "P2P"}),
    ("Oficina", {"Office", "WordProcessor", "Spreadsheet", "Presentation"}),
    ("Multimedia", {"AudioVideo", "Audio", "Video", "Player", "Recorder", "Music", "Mixer", "AudioVideoEditing"}),
    ("Gráficos", {"Graphics", "2DGraphics", "3DGraphics", "Photography", "RasterGraphics", "VectorGraphics", "Scanning"}),
    ("Desarrollo", {"Development", "IDE", "Debugger"}),
    ("Juegos", {"Game", "ActionGame", "AdventureGame", "Simulation"}),
    ("Plataformas", set()),
    ("Configuración", {"Settings", "DesktopSettings", "HardwareSettings", "X-XFCE-HardwareSettings", "X-XFCE-SettingsDialog"}),
    ("Archivos", {"FileManager", "FileTools", "Archiving", "Compression", "FileTransfer"}),
    ("Sistema", {"System", "Monitor", "Filesystem", "Security", "Printing", "PackageManager"}),
    ("Utilidades", {"Utility", "Utilities", "Calculator", "TextEditor", "Accessibility", "Core", "X-GNOME-Utilities", "X-KDE-Utilities"}),
    ("Otras", set()),
]
HIDEABLE_SYSTEM_SECTIONS = {"Configuración", "Sistema", "Gráficos"}


def restart_matrix_group(launcher=None):
    """Cierra las ventanas de esta matriz y, si se indica, la vuelve a abrir."""
    cleanup = r'''
import json
import os
import shutil
import subprocess
import sys
import time

launcher = sys.argv[1]
time.sleep(0.5)
managed_titles = {
    "Menú de aplicaciones",
    "Neofetch · solo visual",
    "Aurora viva",
    "Campo estelar",
}
hyprctl = shutil.which("hyprctl")
if hyprctl:
    result = subprocess.run([hyprctl, "-j", "clients"], capture_output=True, text=True)
    if result.returncode == 0:
        try:
            clients = json.loads(result.stdout)
        except (ValueError, TypeError):
            clients = []
        for client in clients:
            window_class = client.get("class", "").casefold()
            is_matrix = window_class == "matrix4"
            has_managed_title = client.get("title") in managed_titles
            if (is_matrix or has_managed_title) and client.get("address"):
                subprocess.run(
                    [hyprctl, "dispatch", "closewindow", f"address:{client['address']}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
if shutil.which("pkill"):
    subprocess.run(
        ["pkill", "-u", str(os.getuid()), "-x", "cosmic-term"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
if launcher:
    time.sleep(0.5)
    os.environ["MATRIX4_INTERNAL_RESTART"] = "1"
    os.execv(launcher, [launcher])
'''
    subprocess.Popen(
        [sys.executable, "-c", cleanup, str(launcher) if launcher else ""],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


SECTION_OVERRIDES = {
    "com.spotify.Client": "Más usados",
    "discord": "Más usados",
    "steam": "Más usados",
    "com.ktechpit.whatsie": "Más usados",
    "FreeTube": "Más usados",
    "io.github.benjamimgois.goverlay": "Configuración",
    "com.pokemmo.PokeMMO.Settings": "Configuración",
    "io.github.Faugus.faugus-launcher": "Plataformas",
    "com.heroicgameslauncher.hgl": "Plataformas",
    "net.lutris.Lutris": "Plataformas",
    "org.prismlauncher.PrismLauncher": "Plataformas",
    "io.github.ilya_zlobintsev.LACT": "Configuración",
    "org.coolercontrol.CoolerControl": "Configuración",
    "curseforge-latest-linux": "Plataformas",
    "org.kde.ark": "Archivos",
    "backintime-qt": "Archivos",
    "backintime-qt-root": "Archivos",
    "org.kde.dolphin": "Archivos",
    "Alacritty": "Utilidades",
    "kitty": "Utilidades",
    "org.pulseaudio.pavucontrol": "Configuración",
    "jconsole-java-openjdk": "Sistema",
    "jshell-java-openjdk": "Sistema",
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


def run_system_action(choice, rain_context=None):
    """Ejecuta las acciones de mantenimiento sin cambiar la geometría del menú."""
    choice = choice.casefold()
    power_actions = {
        "q": ("poweroff", "apagar el PC"),
        "y": ("reboot", "reiniciar el PC"),
        "z": ("suspend", "poner el PC en reposo"),
    }
    if choice in power_actions:
        command, description = power_actions[choice]
        terminal = shutil.get_terminal_size((80, 24))
        terminal_height = max(1, terminal.lines)
        rain_columns = []
        if rain_context:
            terminal_height, rain_columns = rain_context
        answer = read_option(
            f"¿Confirmas {description}? [s/N]: ",
            max(1, terminal.columns),
            terminal_height,
            rain_columns,
        ).strip().casefold()
        if answer != "s":
            print("Acción cancelada.")
            wait_key("Pulsa una tecla para volver…", rain_context)
            return True
        result = subprocess.run(["systemctl", command], check=False)
        if result.returncode:
            print(f"No se pudo {description}. Comprueba los permisos del sistema.")
            wait_key("Pulsa una tecla para volver…", rain_context)
        elif command == "suspend":
            print("El equipo volvió del reposo.")
            wait_key("Pulsa una tecla para volver…", rain_context)
        return True
    if choice == "r":
        # Reinicia este menú dentro de la ventana actual. El limpiador anterior
        # cerraba la ventana de forma asíncrona y podía dejarla abierta al relanzar.
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
            wait_key("Pulsa una tecla para volver…", rain_context)
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
            wait_key("Pulsa una tecla para volver…", rain_context)
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
        wait_key("Pulsa una tecla para volver…", rain_context)
        return True
    if choice == "e":
        usage = shutil.disk_usage(HOME)
        used_percent = usage.used / usage.total * 100 if usage.total else 0
        gib = 1024 ** 3
        print(f"Disco de inicio: {usage.free / gib:.1f} GiB libres de {usage.total / gib:.1f} GiB.")
        print(f"Uso: {used_percent:.1f}% ({usage.used / gib:.1f} GiB ocupados).")
        wait_key("Pulsa una tecla para volver…", rain_context)
        return True
    if choice == "h":
        mount_point = Path("/mnt/backup")
        mounted = subprocess.run(
            ["findmnt", "--mountpoint", str(mount_point)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if mounted:
            print(f"El HDD ya está montado en {mount_point}.")
        elif not shutil.which("pkexec"):
            print("No se encontró pkexec para solicitar autorización de montaje.")
        else:
            print("Autoriza el montaje del HDD en el diálogo de contraseña…")
            result = subprocess.run(
                ["pkexec", "mount", str(mount_point)],
                check=False,
            )
            mounted = result.returncode == 0 and subprocess.run(
                ["findmnt", "--mountpoint", str(mount_point)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode == 0
            if mounted:
                print(f"HDD montado y listo en {mount_point}.")
            else:
                print("No se pudo montar el HDD. Revisa la autorización y el estado del disco.")
        if mounted and shutil.which("xdg-open"):
            subprocess.Popen(
                ["xdg-open", str(mount_point)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        wait_key("Pulsa una tecla para volver…", rain_context)
        return True
    if choice == "p":
        monitor = next((name for name in ("btop", "htop", "top") if shutil.which(name)), None)
        if monitor:
            if monitor == "btop":
                # Usa una copia temporal de la configuración para poner la
                # indicación en el reloj superior de btop sin cambiar ajustes
                # personales permanentes.
                config_path = HOME / ".config/btop/btop.conf"
                try:
                    config_text = config_path.read_text(encoding="utf-8")
                except OSError:
                    defaults = subprocess.run(
                        [monitor, "--default-config"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    config_text = defaults.stdout if defaults.returncode == 0 else ""
                config_text, replacements = re.subn(
                    r"(?m)^\s*clock_format\s*=.*$",
                    'clock_format = "q/Q: volver"',
                    config_text,
                    count=1,
                )
                if not replacements:
                    config_text += '\nclock_format = "q/Q: volver"\n'
                temporary_config = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w", encoding="utf-8", prefix="btop-centro-",
                        suffix=".conf", delete=False,
                    ) as config_file:
                        config_file.write(config_text)
                        temporary_config = config_file.name
                    run_btop([monitor, "--config", temporary_config])
                finally:
                    if temporary_config:
                        Path(temporary_config).unlink(missing_ok=True)
            else:
                subprocess.run([monitor], check=False)
        else:
            print("No se encontró btop, htop ni top para mostrar los procesos.")
            wait_key("Pulsa una tecla para volver…", rain_context)
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
        wait_key("Pulsa una tecla para volver…", rain_context)
        return True
    if choice in {"d", "36"}:
        for command in (["resolvectl", "flush-caches"], ["systemd-resolve", "--flush-caches"]):
            if shutil.which(command[0]):
                result = subprocess.run(command, capture_output=True, text=True)
                if result.returncode == 0:
                    print("Caché DNS vaciada; el sistema consultará de nuevo sus servidores DNS.")
                else:
                    print("No se pudo vaciar la caché DNS. Comprueba el servicio de resolución del sistema.")
                wait_key("Pulsa una tecla para volver…", rain_context)
                return True
        print("No se encontró resolvectl ni systemd-resolve; no se cambió la configuración DNS.")
        wait_key("Pulsa una tecla para volver…", rain_context)
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


def wait_key(prompt, rain_context=None):
    """Espera una sola tecla sin imprimir entrada ni salida de la app."""
    print(prompt, end="", flush=True)
    try:
        fd = os.open("/dev/tty", os.O_RDONLY)
        try:
            previous = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                if rain_context and rain_context[1]:
                    terminal_height, rain_columns = rain_context
                    frame = 0
                    while True:
                        draw_code_rain(terminal_height, frame, rain_columns)
                        frame += 1
                        readable, _, _ = select.select([fd], [], [], 0.14)
                        if readable and os.read(fd, 1):
                            break
                else:
                    os.read(fd, 1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        finally:
            os.close(fd)
        print()
    except (OSError, termios.error):
        input()


def run_btop(command):
    """Ejecuta btop en una pseudo-terminal y acepta q o Q para salir."""
    input_fd = sys.stdin.fileno()
    output_fd = sys.stdout.fileno()
    original_attrs = termios.tcgetattr(input_fd)
    original_resize_handler = signal.getsignal(signal.SIGWINCH)
    child_pid, master_fd = pty.fork()
    if child_pid == 0:
        try:
            os.execvp(command[0], command)
        except OSError:
            os._exit(127)

    def forward_resize(_signum, _frame):
        try:
            size = fcntl.ioctl(input_fd, termios.TIOCGWINSZ, b"\0" * 8)
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, size)
        except OSError:
            pass

    def write_all(fd, data):
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]

    signal.signal(signal.SIGWINCH, forward_resize)
    forward_resize(None, None)
    tty.setraw(input_fd)
    child_status = None
    try:
        while child_status is None:
            readable, _, _ = select.select([input_fd, master_fd], [], [], 0.1)
            if master_fd in readable:
                try:
                    output = os.read(master_fd, 65536)
                except OSError:
                    output = b""
                if output:
                    write_all(output_fd, output)
            if input_fd in readable:
                try:
                    keys = os.read(input_fd, 4096)
                except OSError:
                    keys = b""
                if keys:
                    try:
                        write_all(master_fd, keys.replace(b"Q", b"q"))
                    except OSError:
                        pass
            waited_pid, status = os.waitpid(child_pid, os.WNOHANG)
            if waited_pid:
                child_status = status
    finally:
        termios.tcsetattr(input_fd, termios.TCSADRAIN, original_attrs)
        signal.signal(signal.SIGWINCH, original_resize_handler)
        os.close(master_fd)
        if child_status is None:
            os.waitpid(child_pid, 0)


def draw_code_rain(terminal_height, frame, columns):
    """Dibuja un fotograma discreto de lluvia en los márgenes del menú."""
    if not columns or terminal_height < 16:
        return
    symbols = "01アイλ"
    first_row = 4
    row_count = max(1, terminal_height - 7)
    output = ["\033[s"]
    for index, column in enumerate(columns):
        previous_head = first_row + ((frame - 1 + index * 7) % row_count)
        for trail in range(4):
            row = previous_head - trail
            if first_row <= row < terminal_height - 3:
                output.append(f"\033[{row};{column}H ")
    for index, column in enumerate(columns):
        head = first_row + ((frame + index * 7) % row_count)
        for trail in range(4):
            row = head - trail
            if first_row <= row < terminal_height - 3:
                symbol = symbols[(frame + index * 2 + trail) % len(symbols)]
                color = "1;36" if trail == 0 and index % 4 == 0 else (
                    "1;32" if trail == 0 else "2;32"
                )
                output.append(f"\033[{row};{column}H\033[{color}m{symbol}\033[0m")
    output.append("\033[u")
    sys.stdout.write("".join(output))
    sys.stdout.flush()


def read_option(prompt, terminal_width, terminal_height, rain_columns):
    """Lee una línea sencilla mientras anima el margen sin cruzarse con el texto."""
    input_fd = sys.stdin.fileno()
    previous = termios.tcgetattr(input_fd)
    typed = []
    frame = 0
    rain_enabled = bool(rain_columns) and terminal_height >= 16
    print(prompt, end="", flush=True)
    tty.setraw(input_fd)
    try:
        while True:
            if rain_enabled:
                draw_code_rain(terminal_height, frame, rain_columns)
                frame += 1
            readable, _, _ = select.select(
                [input_fd], [], [], 0.14 if rain_enabled else None
            )
            if not readable:
                continue
            data = os.read(input_fd, 64)
            for value in data:
                if value in (10, 13):
                    print()
                    return "".join(typed)
                if value == 3:
                    raise KeyboardInterrupt
                if value == 4:
                    print()
                    return "".join(typed)
                if value in (8, 127):
                    if typed:
                        typed.pop()
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                    continue
                if value == 21:
                    if typed:
                        sys.stdout.write("\b \b" * len(typed))
                        sys.stdout.flush()
                        typed.clear()
                    continue
                if 32 <= value < 127 and len(typed) < 2:
                    typed.append(chr(value))
                    sys.stdout.write(chr(value))
                    sys.stdout.flush()
    finally:
        termios.tcsetattr(input_fd, termios.TCSADRAIN, previous)


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


def show_menu(
    show_system_settings=False,
    show_office=False,
    show_utilities=False,
    show_multimedia=False,
    show_graphics=False,
    show_files=False,
    animate=False,
):
    print("\033[2J\033[H", end="", flush=True)
    items = launchers()
    if not items:
        print("No encontré aplicaciones instaladas.")
        return False, show_system_settings, show_office, show_utilities, show_multimedia, show_graphics, show_files

    all_groups = grouped_items(items)
    system_settings_entries = sum(
        len(entries)
        for title, entries in all_groups
        if title in HIDEABLE_SYSTEM_SECTIONS
    )
    active_view = next(
        (
            view
            for enabled, view in (
                (show_system_settings, "sistema"),
                (show_office, "oficina"),
                (show_utilities, "utilidades"),
                (show_multimedia, "multimedia"),
                (show_files, "archivos"),
            )
            if enabled
        ),
        None,
    )
    if active_view == "sistema":
        visible_titles = HIDEABLE_SYSTEM_SECTIONS
    elif active_view == "oficina":
        visible_titles = {"Oficina"}
    elif active_view == "utilidades":
        visible_titles = {"Utilidades"}
    elif active_view == "multimedia":
        visible_titles = {"Multimedia"}
    elif active_view == "archivos":
        visible_titles = {"Archivos"}
    else:
        visible_titles = None
    groups = [
        (title, entries)
        for title, entries in all_groups
        if (
            title in visible_titles
            if visible_titles is not None
            else title not in HIDEABLE_SYSTEM_SECTIONS or show_system_settings
        )
        if visible_titles is not None
        or title != "Oficina" or show_office
        if visible_titles is not None
        or title != "Utilidades" or show_utilities
        if visible_titles is not None
        or title != "Multimedia" or show_multimedia
        if visible_titles is not None
        or title != "Archivos" or show_files
    ]
    if not groups:
        print("No hay aplicaciones disponibles en las categorías visibles.")
        return False, show_system_settings, show_office, show_utilities, show_multimedia, show_graphics, show_files

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
    panel_count = min(3, max_columns, len(visible_groups))
    panels = arrange_groups(visible_groups, panel_count)

    office_count = sum(len(entries) for title, entries in all_groups if title == "Oficina")
    utilities_count = sum(len(entries) for title, entries in all_groups if title == "Utilidades")
    multimedia_count = sum(len(entries) for title, entries in all_groups if title == "Multimedia")
    files_count = sum(len(entries) for title, entries in all_groups if title == "Archivos")
    view_buttons = []
    active_view_button = next(
        (
            (key, label)
            for enabled, key, label in (
                (show_system_settings, "G", "Sist./Config."),
                (show_office, "O", "Office"),
                (show_utilities, "U", "Utilidades"),
                (show_multimedia, "M", "Multimedia"),
                (show_files, "F", "Archivos"),
            )
            if enabled
        ),
        None,
    )
    if active_view_button:
        view_buttons.append((active_view_button[0], f"Ocultar {active_view_button[1]}"))
    else:
        if system_settings_entries:
            view_buttons.append(("G", "Mostrar Sist./Config."))
        if office_count:
            view_buttons.append(("O", "Mostrar Office"))
        if utilities_count:
            view_buttons.append(("U", "Mostrar Utilidades"))
        if multimedia_count:
            view_buttons.append(("M", "Mostrar Multimedia"))
        if files_count:
            view_buttons.append(("F", "Mostrar Archivos"))
    if active_view_button:
        action_groups = [("VISTAS", view_buttons)]
    else:
        action_groups = [
            ("CARPETAS", [("A", "Inicio"), ("B", "Descargas"), ("S", "Sistema")]),
            ("HERRAMIENTAS", [("T", "Temporales"), ("D", "DNS"), ("E", "Almacenamiento"), ("H", "Montar HDD"), ("P", "Procesos"), ("C", "Codex")]),
            ("VISTAS", view_buttons),
            ("SESIÓN", [("R", "Reiniciar menú"), ("Q", "Apagar PC"), ("Y", "Reiniciar PC"), ("Z", "Reposo"), ("Enter", "Salir")]),
        ]
    action_groups = [(title, buttons) for title, buttons in action_groups if buttons]
    action_grid = not compact_layout and content_width >= 112
    if action_grid:
        action_lines = [""] * (1 + max(len(buttons) for _, buttons in action_groups))
    else:
        action_lines = []
        for group_index, (title, buttons) in enumerate(action_groups):
            controls = "  ·  ".join(f"[{key}] {label}" for key, label in buttons)
            action_lines.extend(textwrap.wrap(
                f"{title}   {controls}",
                width=max(1, content_width - 2),
                break_long_words=True,
            ))
            if group_index + 1 < len(action_groups):
                action_lines.append("")
    if not compact_layout:
        action_lines.insert(0, "")
    action_lines.append("")
    watermark_text = fit_text("Software creado por Dreasy", content_width)
    shortcut_hint = fit_text("Super + Shift + A · abrir", content_width)
    corner_line_count = (
        1
        if display_width(watermark_text) + display_width(shortcut_hint) + 2 <= content_width
        else 2
    )
    reserved_rows = (7 if compact_layout else 8) + corner_line_count - 1

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
            heading_padding = max(0, (panel_width - display_width(heading)) // 2)
            panel_lines[panel_index].append(
                f"\033[1;36m{' ' * heading_padding}{heading}\033[0m"
            )
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
    if action_grid:
        footer_column_widths = [
            max(
                display_width(title),
                max(display_width(f"[{key}] {label}") for key, label in buttons),
            ) + 2
            for title, buttons in action_groups
        ]
        footer_width = sum(footer_column_widths) + 3 * (len(action_groups) - 1)
    else:
        footer_width = max(
            (display_width(line) for line in action_lines),
            default=0,
        )
    center_block_width = min(
        content_width,
        max(
            total_panel_width,
            footer_width,
            display_width("CENTRO DE APLICACIONES"),
            min(24, content_width),
        ),
    )
    center_block_left = side_padding + max(
        0, (content_width - center_block_width) // 2
    )
    center_block_right = center_block_left + center_block_width
    # La marca de agua solo ocupa la primera línea; la lluvia empieza bastante
    # más abajo, así que puede aprovechar también el margen izquierdo completo.
    left_rain_start = side_padding + 4
    left_rain_end = center_block_left - 2
    right_rain_start = center_block_right + 3
    right_rain_end = terminal_width - side_padding - 2
    rain_columns = []
    for start, end in (
        (left_rain_start, left_rain_end),
        (right_rain_start, right_rain_end),
    ):
        if end - start >= 6:
            rain_columns.extend(range(start + 1, end, 6))
    # Reserva las filas reales del pie para que el espacio vertical se vuelva
    # a calcular con las categorías que estén visibles en esta renderización.
    available_rows = max(1, terminal_height - len(action_lines) - reserved_rows)
    max_scroll = max(0, widest_panel - available_rows)
    if max_scroll:
        action_lines.extend(textwrap.wrap("[J/K] Desplazar", width=content_width))
        available_rows = max(1, terminal_height - len(action_lines) - reserved_rows)
        max_scroll = max(0, widest_panel - available_rows)
    scroll_offset = 0
    visible_rows = min(widest_panel, available_rows)
    body_rows = visible_rows + len(action_lines) + reserved_rows - 1
    # El espacio se reparte entre el inicio de las aplicaciones y el separador.
    # Ambos huecos cuentan en el cálculo para que el pie no quede apretado ni
    # desborde al mostrar Office, Utilidades, Multimedia o Sistema.
    free_rows = max(0, terminal_height - 1 - body_rows) if not max_scroll else 0
    options_top_padding = free_rows // 3
    separator_gap = max(0, free_rows - options_top_padding)
    shortcut_lift = min(2, max(0, separator_gap - 2))
    separator_gap -= shortcut_lift

    while True:
        print("\033[2J\033[H", end="", flush=True)
        animate_shortcuts = animate
        hint_padding = side_padding + max(
            0, content_width - display_width(shortcut_hint)
        )
        watermark = f"\033[2;36m{watermark_text}\033[0m"
        hint = f"\033[2;33m{shortcut_hint}\033[0m"
        if corner_line_count == 1:
            middle_padding = max(
                2,
                content_width - display_width(watermark_text) - display_width(shortcut_hint),
            )
            print(" " * side_padding + watermark + " " * middle_padding + hint)
        else:
            print(" " * side_padding + watermark)
            print(" " * hint_padding + hint)
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
        if animate_shortcuts:
            for visible_width in range(1, len(rule) + 1):
                visible_rule = "─" * visible_width
                visible_padding = side_padding + max(
                    0, (content_width - display_width(visible_rule)) // 2
                )
                print(
                    "\r" + " " * visible_padding
                    + f"\033[2;36m{visible_rule}\033[0m",
                    end="",
                    flush=True,
                )
                time.sleep(0.008)
            print()
        else:
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
            if animate_shortcuts:
                time.sleep(0.022)
        if separator_gap:
            print("\n" * separator_gap, end="")
        print()
        print(" " * side_padding + f"\033[2m{'─' * content_width}\033[0m")
        print()
        if not compact_layout:
            heading = fit_text("ATAJOS DE TECLADO", max(1, content_width - 8))
            decorated_heading = f"─── {heading} ───"
            heading_padding = side_padding + max(
                0, (content_width - display_width(decorated_heading)) // 2
            )
            if animate_shortcuts:
                print(" " * heading_padding + f"\033[2;36m─── \033[0m\033[1;36m", end="", flush=True)
                for character in heading:
                    print(character, end="", flush=True)
                    time.sleep(0.018)
                print("\033[0m\033[2;36m ───\033[0m")
            else:
                print(
                    " " * heading_padding
                    + f"\033[2;36m─── \033[0m\033[1;36m{heading}\033[0m\033[2;36m ───\033[0m"
                )
            print()
        if action_grid:
            column_gap = 3
            column_widths = [
                max(
                    display_width(title),
                    max(display_width(f"[{key}] {label}") for key, label in buttons),
                ) + 2
                for title, buttons in action_groups
            ]
            grid_width = sum(column_widths) + column_gap * (len(action_groups) - 1)
            grid_padding = side_padding + max(0, (content_width - grid_width) // 2)

            def align_cell(text, width):
                right_padding = max(0, width - display_width(text))
                return text + " " * right_padding

            headings = [f"\033[1;36m{title}\033[0m" for title, _ in action_groups]

            def center_cell(text, width):
                left_padding = max(0, (width - display_width(text)) // 2)
                right_padding = max(0, width - display_width(text) - left_padding)
                return " " * left_padding + text + " " * right_padding

            print(
                " " * grid_padding
                + (" " * column_gap).join(
                    center_cell(title, width)
                    for title, width in zip(headings, column_widths)
                )
            )
            if animate_shortcuts:
                time.sleep(0.06)
            for row_index in range(max(len(buttons) for _, buttons in action_groups)):
                cells = []
                for (_, buttons), width in zip(action_groups, column_widths):
                    if row_index < len(buttons):
                        key, label = buttons[row_index]
                        cell = f"\033[1;33m[{key}]\033[0m {label}"
                    else:
                        cell = ""
                    cells.append(align_cell(cell, width))
                print(" " * grid_padding + (" " * column_gap).join(cells))
                if animate_shortcuts:
                    time.sleep(0.055)
            print()
        else:
            for line in action_lines:
                if not line:
                    print()
                    continue
                line = re.sub(
                    r"^(CARPETAS|HERRAMIENTAS|VISTAS|SESIÓN)",
                    r"\033[1;36m\1\033[0m",
                    line,
                )
                line = re.sub(r"\[([A-Za-z0-9]+)\]", r"\033[1;33m[\1]\033[0m", line)
                line_padding = side_padding + max(
                    0, (content_width - display_width(line)) // 2
                )
                print(" " * line_padding + line)
                if animate_shortcuts:
                    time.sleep(0.045)

        prompt = "› Opción: " if terminal_width >= 16 else "› "
        prompt_padding = side_padding + max(0, (content_width - display_width(prompt)) // 2)
        try:
            choice = read_option(
                " " * prompt_padding + f"\033[1;36m{prompt}\033[0m",
                terminal_width,
                terminal_height,
                rain_columns,
            ).strip().casefold()
        except TerminalResized:
            return True, show_system_settings, show_office, show_utilities, show_multimedia, show_graphics, show_files
        if not choice:
            return False, show_system_settings, show_office, show_utilities, show_multimedia, show_graphics, show_files
        if choice == "g" and system_settings_entries:
            opening = not show_system_settings
            return True, opening, False, False, False, False, False
        if choice == "o" and office_count:
            opening = not show_office
            return True, False, opening, False, False, False, False
        if choice == "u" and utilities_count:
            opening = not show_utilities
            return True, False, False, opening, False, False, False
        if choice == "m" and multimedia_count:
            opening = not show_multimedia
            return True, False, False, False, opening, False, False
        if choice == "f" and files_count:
            opening = not show_files
            return True, False, False, False, False, False, opening
        if choice == "j" and scroll_offset < max_scroll:
            scroll_offset += 1
            continue
        if choice == "k" and scroll_offset > 0:
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
                        draw_code_rain(terminal_height, frame, rain_columns)
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
                        wait_key("Pulsa una tecla para volver…", (terminal_height, rain_columns))
                    else:
                        wait_key(
                            f"{name} iniciado. Oprime una tecla para volver…",
                            (terminal_height, rain_columns),
                        )
                except OSError as error:
                    print(f"No se pudo abrir {name}: {error}")
                    wait_key("Pulsa una tecla para volver…", (terminal_height, rain_columns))
            return True, show_system_settings, show_office, show_utilities, show_multimedia, show_graphics, show_files

        rain_context = (terminal_height, rain_columns)
        action_result = run_system_action(choice, rain_context)
        if action_result is not None:
            return action_result, show_system_settings, show_office, show_utilities, show_multimedia, show_graphics, show_files
        navigation = "J/K para desplazar, " if max_scroll else ""
        print(f"Opción inválida; elige una aplicación, {navigation}o una acción.")
        wait_key("Pulsa una tecla para continuar…", rain_context)


def main():
    instance_lock = acquire_single_instance()
    if instance_lock is None:
        return
    previous_resize_handler = signal.signal(signal.SIGWINCH, handle_terminal_resize)
    print("\033[?1049h", end="", flush=True)
    try:
        show_system_settings = False
        show_office = False
        show_utilities = False
        show_multimedia = False
        show_graphics = False
        show_files = False
        animate = True
        while True:
            try:
                (
                    keep_running,
                    show_system_settings,
                    show_office,
                    show_utilities,
                    show_multimedia,
                    show_graphics,
                    show_files,
                ) = show_menu(
                    show_system_settings,
                    show_office,
                    show_utilities,
                    show_multimedia,
                    show_graphics,
                    show_files,
                    animate=animate,
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
