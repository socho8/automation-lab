"""
Duplicate Finder
-----------------
Escanea una carpeta (y subcarpetas) en busca de archivos duplicados
basándose en su contenido real (hash SHA-256), no en el nombre.

Por seguridad, por defecto SOLO reporta los duplicados encontrados
(modo dry-run). Para moverlos a una carpeta de cuarentena hay que
pasar explícitamente --move-duplicates, y para borrarlos de forma
permanente hay que pasar --delete (no recomendado sin revisar antes).

Requiere: tqdm (pip install tqdm)

Uso:
    python app.py /ruta/a/la/carpeta
    python app.py /ruta/a/la/carpeta --move-duplicates
    python app.py /ruta/a/la/carpeta --delete
"""

import argparse
import hashlib
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

from tqdm import tqdm

CHUNK_SIZE = 65536  # 64 KB por bloque de lectura


def human_readable_size(num_bytes: float) -> str:
    """Convierte bytes a un formato legible (KB, MB, GB...)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} PB"


def file_hash(path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo leyéndolo en bloques."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_duplicates(root: Path) -> tuple[dict[str, list[Path]], int]:
    """
    Encuentra archivos duplicados dentro de `root`.

    Optimización: primero agrupa por tamaño (comparar tamaños es gratis).
    Solo se calcula el hash real cuando hay 2+ archivos del mismo tamaño,
    evitando leer todos los archivos byte a byte innecesariamente.

    Devuelve (duplicados, cantidad_total_de_archivos_escaneados).
    """
    all_files = [p for p in root.rglob("*") if p.is_file()]
    files_scanned = len(all_files)

    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in tqdm(all_files, desc="🔍 Escaneando archivos", unit="archivo"):
        try:
            by_size[path.stat().st_size].append(path)
        except OSError:
            # Archivo inaccesible (permisos, enlace roto, etc.)
            continue

    candidates = [group for group in by_size.values() if len(group) > 1]
    total_candidates = sum(len(group) for group in candidates)

    duplicates: dict[str, list[Path]] = defaultdict(list)
    with tqdm(total=total_candidates, desc="🧬 Calculando hashes", unit="archivo") as pbar:
        for group in candidates:
            for path in group:
                try:
                    digest = file_hash(path)
                    duplicates[digest].append(path)
                except OSError:
                    pass
                pbar.update(1)

    # Nos quedamos solo con los hashes que realmente tienen 2+ archivos
    result = {h: paths for h, paths in duplicates.items() if len(paths) > 1}
    return result, files_scanned


def report(duplicates: dict[str, list[Path]]) -> int:
    """Imprime el reporte de duplicados y devuelve el espacio recuperable en bytes."""
    if not duplicates:
        print("\n✅ No se encontraron archivos duplicados.")
        return 0

    total_wasted = 0
    group_num = 1

    for digest, paths in duplicates.items():
        original, *repeated = sorted(paths, key=lambda p: p.stat().st_mtime)
        size = original.stat().st_size
        wasted = size * len(repeated)
        total_wasted += wasted

        print(f"\n📁 Grupo {group_num} — {human_readable_size(size)} cada uno")
        print(f"   Original (más antiguo): {original}")
        for dup in repeated:
            print(f"   Duplicado:              {dup}")

        group_num += 1

    return total_wasted


def print_summary(files_scanned: int, duplicates: dict[str, list[Path]],
                   recoverable_bytes: int, elapsed_seconds: float) -> None:
    """Muestra el resumen final de la ejecución."""
    duplicate_groups = len(duplicates)
    duplicate_files = sum(len(paths) - 1 for paths in duplicates.values())

    print("\n" + "─" * 40)
    print("📊 RESUMEN")
    print("─" * 40)
    print(f"Files scanned:       {files_scanned}")
    print(f"Duplicate groups:    {duplicate_groups}")
    print(f"Duplicate files:     {duplicate_files}")
    print(f"Recoverable space:   {human_readable_size(recoverable_bytes)}")
    print(f"Execution time:      {elapsed_seconds:.2f}s")
    print("─" * 40)


def move_to_quarantine(duplicates: dict[str, list[Path]], root: Path) -> None:
    """Mueve los duplicados (no el original) a una carpeta de cuarentena."""
    quarantine = root / "duplicados"
    quarantine.mkdir(exist_ok=True)

    for paths in duplicates.values():
        original, *repeated = sorted(paths, key=lambda p: p.stat().st_mtime)
        for dup in repeated:
            destination = quarantine / dup.name
            # Evita sobrescribir si ya existe un archivo con ese nombre
            counter = 1
            while destination.exists():
                destination = quarantine / f"{dup.stem}_{counter}{dup.suffix}"
                counter += 1
            shutil.move(str(dup), str(destination))
            print(f"📦 Movido a cuarentena: {dup} -> {destination}")

    print(f"\nLos duplicados fueron movidos a: {quarantine}")
    print("Revisalos y borralos manualmente cuando estés seguro.")


def delete_duplicates(duplicates: dict[str, list[Path]]) -> None:
    """Borra los duplicados de forma permanente. Usar con cuidado."""
    for paths in duplicates.values():
        original, *repeated = sorted(paths, key=lambda p: p.stat().st_mtime)
        for dup in repeated:
            dup.unlink()
            print(f"🗑️  Borrado: {dup}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Encuentra (y opcionalmente elimina) archivos duplicados por contenido."
    )
    parser.add_argument("directory", type=str, help="Carpeta a escanear")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--move-duplicates",
        action="store_true",
        help="Mueve los duplicados a una carpeta de cuarentena (recomendado)",
    )
    action.add_argument(
        "--delete",
        action="store_true",
        help="Borra los duplicados de forma permanente (irreversible)",
    )
    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    if not root.is_dir():
        print(f"❌ La carpeta no existe: {root}")
        sys.exit(1)

    print(f"🔍 Escaneando: {root}")
    start_time = time.time()

    duplicates, files_scanned = find_duplicates(root)
    total_wasted = report(duplicates)
    elapsed = time.time() - start_time

    print_summary(files_scanned, duplicates, total_wasted, elapsed)

    if not duplicates:
        return

    if args.delete:
        confirm = input(
            f"\n⚠️  Esto borrará PERMANENTEMENTE los duplicados "
            f"({human_readable_size(total_wasted)}). Escribí 'si' para confirmar: "
        )
        if confirm.strip().lower() == "si":
            delete_duplicates(duplicates)
        else:
            print("Cancelado. No se borró nada.")
    elif args.move_duplicates:
        move_to_quarantine(duplicates, root)
    else:
        print("\nℹ️  Este fue un reporte (dry-run). No se movió ni borró nada.")
        print("   Usá --move-duplicates para moverlos a cuarentena,")
        print("   o --delete para borrarlos de forma permanente.")


if __name__ == "__main__":
    main()