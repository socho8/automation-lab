"""
Files Organizer
--------------------
Interfaz gráfica simple que permite:
1. Seleccionar una carpeta a organizar.
2. Ver una VISTA PREVIA de cómo quedaría, sin mover nada todavía.
3. Confirmar o cancelar antes de mover un solo archivo.

Requiere: solo librería estándar (tkinter incluido con Python).
"""

import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Reglas de clasificación: extensión -> carpeta destino
CLASSIFICATION_RULES = {
    ".pdf": "Documentos",
    ".doc": "Documentos",
    ".docx": "Documentos",
    ".txt": "Documentos",
    ".xls": "Documentos",
    ".xlsx": "Documentos",
    ".jpg": "Imagenes",
    ".jpeg": "Imagenes",
    ".png": "Imagenes",
    ".gif": "Imagenes",
    ".webp": "Imagenes",
    ".mp4": "Videos",
    ".mov": "Videos",
    ".avi": "Videos",
    ".mkv": "Videos",
    ".mp3": "Audio",
    ".wav": "Audio",
    ".zip": "Comprimidos",
    ".rar": "Comprimidos",
    ".7z": "Comprimidos",
    ".exe": "Programas",
    ".msi": "Programas",
}

DEFAULT_FOLDER = "Otros"


def classify_file(path: Path) -> str:
    """Devuelve el nombre de la carpeta destino según la extensión."""
    return CLASSIFICATION_RULES.get(path.suffix.lower(), DEFAULT_FOLDER)


def build_preview(root: Path) -> list[tuple[Path, str]]:
    """
    Escanea la carpeta (sin subcarpetas, solo el nivel superior) y devuelve
    una lista de (archivo, carpeta_destino), sin mover nada todavía.
    """
    preview = []
    for path in sorted(root.iterdir()):
        if path.is_file():
            destino = classify_file(path)
            preview.append((path, destino))
    return preview


def apply_organization(preview: list[tuple[Path, str]], root: Path) -> int:
    """Mueve los archivos según el preview ya calculado. Devuelve cuántos movió."""
    moved = 0
    for path, destino_nombre in preview:
        destino_carpeta = root / destino_nombre
        destino_carpeta.mkdir(exist_ok=True)

        destino_final = destino_carpeta / path.name
        # Evita sobrescribir si ya existe un archivo con ese nombre
        counter = 1
        while destino_final.exists():
            destino_final = destino_carpeta / f"{path.stem}_{counter}{path.suffix}"
            counter += 1

        shutil.move(str(path), str(destino_final))
        moved += 1
    return moved


class OrganizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Organizador de Descargas")
        self.geometry("640x480")
        self.selected_folder: Path | None = None
        self.current_preview: list[tuple[Path, str]] = []

        self._build_widgets()

    def _build_widgets(self):
        # --- Selección de carpeta ---
        top_frame = tk.Frame(self, pady=10)
        top_frame.pack(fill="x")

        self.folder_label = tk.Label(
            top_frame, text="Ninguna carpeta seleccionada", anchor="w"
        )
        self.folder_label.pack(side="left", padx=10, fill="x", expand=True)

        select_btn = tk.Button(
            top_frame, text="📁 Seleccionar carpeta", command=self.select_folder
        )
        select_btn.pack(side="right", padx=10)

        # --- Tabla de preview ---
        columns = ("archivo", "destino")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("archivo", text="Archivo")
        self.tree.heading("destino", text="Se moverá a")
        self.tree.column("archivo", width=380)
        self.tree.column("destino", width=200)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Botones de acción ---
        bottom_frame = tk.Frame(self, pady=10)
        bottom_frame.pack(fill="x")

        self.status_label = tk.Label(bottom_frame, text="")
        self.status_label.pack(side="left", padx=10)

        self.cancel_btn = tk.Button(
            bottom_frame, text="Cancelar", command=self.cancel, state="disabled"
        )
        self.cancel_btn.pack(side="right", padx=10)

        self.accept_btn = tk.Button(
            bottom_frame, text="✅ Aceptar y organizar",
            command=self.accept, state="disabled"
        )
        self.accept_btn.pack(side="right")

    def select_folder(self):
        folder = filedialog.askdirectory(title="Elegí la carpeta a organizar")
        if not folder:
            return

        self.selected_folder = Path(folder)
        self.folder_label.config(text=str(self.selected_folder))

        self.current_preview = build_preview(self.selected_folder)

        # Limpiar tabla anterior
        for row in self.tree.get_children():
            self.tree.delete(row)

        if not self.current_preview:
            self.status_label.config(text="No hay archivos para organizar en esta carpeta.")
            self.accept_btn.config(state="disabled")
            self.cancel_btn.config(state="disabled")
            return

        for path, destino in self.current_preview:
            self.tree.insert("", "end", values=(path.name, destino))

        self.status_label.config(
            text=f"{len(self.current_preview)} archivo(s) listos para organizar."
        )
        self.accept_btn.config(state="normal")
        self.cancel_btn.config(state="normal")

    def accept(self):
        if not self.current_preview:
            return

        confirm = messagebox.askyesno(
            "Confirmar",
            f"¿Mover {len(self.current_preview)} archivo(s) según la vista previa?"
        )
        if not confirm:
            return

        moved = apply_organization(self.current_preview, self.selected_folder)
        messagebox.showinfo("Listo", f"Se organizaron {moved} archivo(s) correctamente.")

        # Reset
        self.current_preview = []
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.status_label.config(text="")
        self.accept_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")

    def cancel(self):
        self.current_preview = []
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.status_label.config(text="Cancelado. No se movió nada.")
        self.accept_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")


if __name__ == "__main__":
    app = OrganizerApp()
    app.mainloop()