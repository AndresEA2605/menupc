#!/usr/bin/env python3
"""Centro de aplicaciones para Windows, basado en accesos directos del menú Inicio."""

import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk


def start_menu_directories():
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    programdata = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    return [
        appdata / "Microsoft/Windows/Start Menu/Programs",
        programdata / "Microsoft/Windows/Start Menu/Programs",
    ]


def category_for(path):
    parts = [part.casefold() for part in path.parent.parts]
    if any(word in parts for word in ("games", "juegos")):
        return "Juegos"
    if any(word in parts for word in ("accessories", "accesorios", "system tools", "herramientas del sistema")):
        return "Utilidades"
    return "Aplicaciones"


def discover_apps():
    found = {}
    for directory in start_menu_directories():
        if not directory.is_dir():
            continue
        for shortcut in directory.rglob("*.lnk"):
            if shortcut.name.casefold() in {"uninstall.lnk", "uninstall.exe.lnk"}:
                continue
            found.setdefault(str(shortcut).casefold(), {
                "name": shortcut.stem.replace("_", " "),
                "category": category_for(shortcut),
                "path": shortcut,
            })
    return sorted(found.values(), key=lambda app: app["name"].casefold())


class AppCenter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Centro de aplicaciones")
        self.geometry("760x580")
        self.minsize(520, 380)
        self.configure(bg="#10131b")
        self.apps = discover_apps()
        self.query = tk.StringVar()
        self.category = tk.StringVar(value="Todas")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background="#191e2a", foreground="#edf0f7",
                        fieldbackground="#191e2a", rowheight=32, borderwidth=0)
        style.configure("Treeview.Heading", background="#252c3b", foreground="#aebbd1",
                        font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("Treeview", background=[("selected", "#355a8c")])

        header = tk.Frame(self, bg="#10131b", padx=24, pady=20)
        header.pack(fill="x")
        tk.Label(header, text="CENTRO DE APLICACIONES", bg="#10131b", fg="#f2f5fc",
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(header, text="Aplicaciones del menú Inicio de Windows", bg="#10131b",
                 fg="#929db2", font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 14))

        controls = tk.Frame(header, bg="#10131b")
        controls.pack(fill="x")
        search = ttk.Entry(controls, textvariable=self.query)
        search.pack(side="left", fill="x", expand=True, ipady=6)
        search.insert(0, "")
        self.categories = ttk.Combobox(controls, textvariable=self.category, state="readonly",
                                       values=("Todas", "Aplicaciones", "Juegos", "Utilidades"), width=18)
        self.categories.pack(side="left", padx=(10, 0), ipady=4)
        self.query.trace_add("write", lambda *_: self.refresh())
        self.category.trace_add("write", lambda *_: self.refresh())
        search.bind("<Return>", lambda _event: self.open_selected())

        body = tk.Frame(self, bg="#10131b", padx=24, pady=(0, 18))
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=("category",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Aplicación", anchor="w")
        self.tree.heading("category", text="Categoría", anchor="w")
        self.tree.column("#0", minwidth=180, width=460)
        self.tree.column("category", minwidth=110, width=180, stretch=False)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _event: self.open_selected())
        self.tree.bind("<Return>", lambda _event: self.open_selected())

        footer = tk.Frame(self, bg="#10131b", padx=24, pady=(0, 18))
        footer.pack(fill="x")
        self.status = tk.Label(footer, text="", bg="#10131b", fg="#929db2", anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        ttk.Button(footer, text="Abrir", command=self.open_selected).pack(side="right")
        self.refresh()
        search.focus_set()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        query = self.query.get().strip().casefold()
        category = self.category.get()
        matches = [app for app in self.apps
                   if (category == "Todas" or app["category"] == category)
                   and query in app["name"].casefold()]
        for index, app in enumerate(matches):
            self.tree.insert("", "end", iid=str(index), text=app["name"], values=(app["category"],))
        self.status.configure(text=f"{len(matches)} aplicaciones" if matches else "No se encontraron aplicaciones.")
        if matches:
            self.tree.selection_set("0")

    def open_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
        app = [entry for entry in self.apps
               if (self.category.get() == "Todas" or entry["category"] == self.category.get())
               and self.query.get().strip().casefold() in entry["name"].casefold()][int(selection[0])]
        try:
            os.startfile(str(app["path"]))
        except OSError as error:
            self.status.configure(text=f"No se pudo abrir {app['name']}: {error}")


if __name__ == "__main__":
    AppCenter().mainloop()
