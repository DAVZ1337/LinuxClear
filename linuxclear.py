#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LinuxClear v1.1.6
Herramienta conservadora de limpieza para Linux.
La vista previa está activada por defecto.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field

VERSION = "1.1.6"

TEMP_DIRS = (
    Path("/tmp"),
    Path("/var/tmp"),
)

ROOT_FILESYSTEM = Path("/")


@dataclass
class DiskSnapshot:
    """Captura el estado del disco en un momento."""
    total: int = 0
    used: int = 0
    free: int = 0
    available: bool = False

    def is_valid(self):
        """Comprueba si la captura es válida."""
        return self.available and self.total > 0


@dataclass
class CleanupStats:
    """Estadísticas de limpieza con mediciones fiables."""
    estimated_size: int = 0
    files_removed: int = 0
    dirs_removed: int = 0
    actual_removed_size: int = 0
    failed_operations: int = 0
    skipped_operations: int = 0
    failed_items: list = field(default_factory=list)
    disk_before: DiskSnapshot = field(default_factory=DiskSnapshot)
    disk_after: DiskSnapshot = field(default_factory=DiskSnapshot)


def is_root():
    """Comprueba si el programa se ejecuta como administrador."""
    return hasattr(os, "geteuid") and os.geteuid() == 0


def target_home():
    """Intenta identificar el directorio del usuario que ejecutó sudo."""
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user and sudo_user != "root":
        try:
            import pwd
            home = pwd.getpwnam(sudo_user).pw_dir
            if home:
                return Path(home)
        except (ImportError, KeyError, TypeError, OSError):
            pass
    return Path.home()


def format_size(size_bytes, signed=False):
    """Convierte bytes a un formato legible respetando el signo si se solicita."""
    if size_bytes is None:
        return "0 B"

    negative = size_bytes < 0
    value = abs(size_bytes)
    if value == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    scaled = float(value)
    unit = units[0]
    for unit in units:
        if scaled < 1024 or unit == units[-1]:
            break
        scaled /= 1024

    text = f"{scaled:.2f} {unit}"
    if signed and negative:
        text = "-" + text
    return text


def capture_disk_usage(path=None):
    """Captura el uso del disco de un filesystem."""
    if path is None:
        path = ROOT_FILESYSTEM
    snapshot = DiskSnapshot()
    try:
        usage = shutil.disk_usage(str(path))
        snapshot.total = usage.total
        snapshot.used = usage.used
        snapshot.free = usage.free
        snapshot.available = True
    except OSError as exc:
        print(f"[WARN] No se pudo consultar el espacio en disco: {exc}")
        snapshot.available = False
    return snapshot


def print_banner():
    print(f"""
========================================
        LinuxClear v{VERSION}
   Limpieza conservadora para Linux
========================================

Modo predeterminado: VISTA PREVIA
No se borrará nada sin utilizar --apply.
""")


def run(command, apply=False):
    """Muestra un comando y solo lo ejecuta si se solicita."""
    print("\n[CMD]", " ".join(command))
    if not apply:
        print("[DRY-RUN] No se ha ejecutado.")
        return 0
    try:
        result = subprocess.run(command, check=False, capture_output=False)
        if result.returncode != 0:
            print(f"[WARN] El comando terminó con código {result.returncode}.")
        return result.returncode
    except OSError as exc:
        print(f"[ERROR] No se pudo ejecutar el comando: {exc}")
        return 127


def system_info():
    """Muestra información básica del sistema."""
    print("\n[INFO] Información del sistema")
    commands = [
        ["uname", "-a"],
        ["df", "-h", "/"],
        ["free", "-h"],
    ]
    for command in commands:
        print("\n[CMD]", " ".join(command))
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip())
        except OSError as exc:
            print(f"[WARN] No se pudo ejecutar el comando: {exc}")
    try:
        load = Path("/proc/loadavg").read_text().strip()
        print("\nCarga del sistema:", load)
    except OSError:
        print("[INFO] No se pudo consultar la carga del sistema.")


def is_safe_path(target, base):
    """
    Comprueba si la ruta está dentro de la base autorizada y no es un enlace.
    Evita seguir enlaces simbólicos antes de resolver y valida la contención.
    """
    try:
        target = Path(target)
        base = Path(base)
    except TypeError:
        return False

    try:
        if target.exists() is False:
            return False
        if target.is_symlink():
            return False
        target_resolved = target.resolve(strict=True)
        base_resolved = base.resolve(strict=True)
        if target_resolved.is_symlink():
            return False
        target_resolved.relative_to(base_resolved)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def get_path_size(path):
    """Calcula el tamaño total de un archivo o directorio sin seguir enlaces."""
    try:
        path = Path(path)
    except TypeError:
        return 0

    try:
        if not path.exists():
            return 0
        if path.is_symlink():
            return 0
        if path.is_file():
            try:
                return path.stat().st_size
            except OSError:
                return 0
        if path.is_dir():
            total = 0
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        if entry.is_symlink():
                            continue
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                total += get_path_size(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                total += entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            continue
            except OSError:
                return 0
            return total
    except (OSError, RuntimeError, ValueError):
        return 0
    return 0


def remove_path(path, apply=False, stats=None):
    """Elimina un archivo o directorio solo con --apply."""
    if stats is None:
        stats = CleanupStats()

    try:
        path = Path(path)
    except TypeError:
        stats.failed_operations += 1
        stats.failed_items.append((str(path), "Ruta no válida"))
        return False

    if not path.exists():
        print(f"[WARN] Ruta desaparecida: {path}")
        stats.skipped_operations += 1
        return False

    size = get_path_size(path)
    stats.estimated_size += size

    if not apply:
        print(f"[DRY-RUN] Se limpiaría: {path} ({format_size(size)})")
        return True

    try:
        if path.is_symlink():
            stats.failed_operations += 1
            stats.failed_items.append((str(path), "Es un enlace simbólico"))
            print(f"[WARN] Se rechazó {path}: es un enlace simbólico")
            return False

        current_size = get_path_size(path)
        if current_size != size:
            stats.estimated_size -= size
            stats.estimated_size += current_size
            size = current_size

        if path.is_file():
            path.unlink()
            stats.files_removed += 1
        elif path.is_dir():
            shutil.rmtree(path)
            stats.dirs_removed += 1
        else:
            stats.skipped_operations += 1
            return False

        stats.actual_removed_size += size
        print(f"[OK] Limpiado: {path} ({format_size(size)})")
        return True
    except OSError as exc:
        stats.failed_operations += 1
        stats.failed_items.append((str(path), str(exc)))
        print(f"[WARN] No se pudo limpiar {path}: {exc}")
        return False


def clean_user_cache(home, apply=False, stats=None):
    """Limpia el contenido de ~/.cache sin eliminar el directorio principal."""
    if stats is None:
        stats = CleanupStats()

    cache = Path(home) / ".cache"
    print("\n[INFO] Caché del usuario")

    if not cache.exists():
        print(f"[INFO] No existe: {cache}")
        return stats

    if not is_safe_path(cache, Path(home)):
        print(f"[ERROR] La ruta de caché no es segura: {cache}")
        stats.failed_operations += 1
        return stats

    print(f"[INFO] Directorio: {cache}")
    print("[AVISO] Cierra tus aplicaciones antes de aplicar la limpieza.")

    try:
        entries = list(cache.iterdir())
    except OSError as exc:
        print(f"[WARN] No se pudo leer la caché: {exc}")
        stats.failed_operations += 1
        return stats

    for entry in entries:
        if entry.is_symlink():
            print(f"[WARN] Se omite enlace en caché: {entry}")
            stats.skipped_operations += 1
            continue
        if not is_safe_path(entry, cache):
            print(f"[WARN] Ruta insegura omitida: {entry}")
            stats.skipped_operations += 1
            continue
        remove_path(entry, apply=apply, stats=stats)
    return stats


def clean_old_temp_files(days=7, apply=False, stats=None, roots=None):
    """Limpia archivos antiguos en /tmp y /var/tmp sin recorrer enlaces simbólicos."""
    if stats is None:
        stats = CleanupStats()
    if roots is None:
        roots = TEMP_DIRS
    roots = [Path(root) for root in roots]
    cutoff = time.time() - (days * 24 * 60 * 60)

    print(f"\n[INFO] Archivos temporales con más de {days} días")
    print("[AVISO] Archivos antiguos pueden estar en uso deliberadamente.")

    for directory in roots:
        if not directory.is_dir():
            continue
        try:
            for root, dirs, files in os.walk(directory, followlinks=False):
                root_path = Path(root)
                dirs[:] = [name for name in dirs if not (root_path / name).is_symlink()]
                for name in files:
                    path = root_path / name
                    try:
                        if path.is_symlink() or not path.is_file():
                            continue
                        if not is_safe_path(path, directory):
                            print(f"[WARN] Ruta omitida fuera de la ubicación autorizada: {path}")
                            stats.skipped_operations += 1
                            continue
                        if path.stat().st_mtime < cutoff:
                            remove_path(path, apply=apply, stats=stats)
                    except OSError as exc:
                        print(f"[WARN] No se pudo revisar {path}: {exc}")
                        stats.failed_operations += 1
        except OSError as exc:
            print(f"[WARN] Error al recorrer {directory}: {exc}")
            stats.failed_operations += 1
    return stats


def apt_cleanup(apply=False, stats=None):
    """Limpia la caché de paquetes APT sin desinstalar paquetes."""
    if stats is None:
        stats = CleanupStats()

    if not shutil.which("apt-get"):
        print("\n[INFO] APT no está disponible. Se omite esta tarea.")
        stats.skipped_operations += 1
        return stats

    print("\n[INFO] Limpieza de caché APT")

    ret1 = run(["apt-get", "clean"], apply=apply)
    if apply and ret1 != 0:
        stats.failed_operations += 1
    elif apply:
        print("[OK] apt-get clean completado.")

    ret2 = run(["apt-get", "autoclean"], apply=apply)
    if apply and ret2 != 0:
        stats.failed_operations += 1
    elif apply:
        print("[OK] apt-get autoclean completado.")

    return stats


def journal_cleanup(apply=False, stats=None):
    """Reduce el journal de systemd conservando solo los 14 días recientes."""
    if stats is None:
        stats = CleanupStats()

    if not shutil.which("journalctl"):
        print("\n[INFO] journalctl no está disponible.")
        stats.skipped_operations += 1
        return stats

    print("\n[INFO] Conservación del journal: últimos 14 días")
    print("[AVISO] Se eliminarán PERMANENTEMENTE registros anteriores a 14 días.")

    ret = run(["journalctl", "--vacuum-time=14d"], apply=apply)
    if apply:
        if ret == 0:
            print("[OK] Journal reducido correctamente.")
        else:
            print(f"[WARN] El journal no se pudo reducir (código {ret}).")
            stats.failed_operations += 1
    return stats


def validate_compatibility():
    """Comprueba el sistema y los permisos necesarios."""
    if not sys.platform.startswith("linux"):
        print("[ERROR] LinuxClear está diseñado para Linux.")
        return False
    if not is_root():
        print("[ERROR] Ejecuta el programa con sudo.")
        print("Ejemplo: sudo python3 linuxclear.py")
        print("\nNota: Se requieren permisos de administrador para:")
        print("  - Acceder a cachés de sistema.")
        print("  - Limpiar archivos en /tmp y /var/tmp.")
        print("  - Gestionar el journal de systemd.")
        return False
    return True


def print_summary(stats, apply=False, level="quick"):
    """Imprime un resumen detallado de la limpieza."""
    print("\n" + "=" * 60)
    print("RESUMEN DE LIMPIEZA - LinuxClear v" + VERSION)
    print("=" * 60)

    if stats.disk_before.is_valid():
        print(f"\n[ESTADO ANTES]")
        print(f"  Espacio total:    {format_size(stats.disk_before.total)}")
        print(f"  Espacio usado:    {format_size(stats.disk_before.used)}")
        print(f"  Espacio libre:    {format_size(stats.disk_before.free)}")
        percent = (stats.disk_before.used / stats.disk_before.total * 100) if stats.disk_before.total > 0 else 0
        print(f"  Porcentaje usado: {percent:.1f}%")
    else:
        print(f"\n[ESTADO ANTES]")
        print(f"  No disponible")

    print(f"\n[RESULTADO DE LA LIMPIEZA]")
    print(f"  Tamaño estimado:          {format_size(stats.estimated_size)}")
    print(f"  Archivos eliminados:      {stats.files_removed}")
    print(f"  Directorios eliminados:   {stats.dirs_removed}")
    print(f"  Tamaño registrado elim.:  {format_size(stats.actual_removed_size)}")

    if stats.failed_operations > 0:
        print(f"  Operaciones fallidas:     {stats.failed_operations}")
        if stats.failed_items:
            print(f"\n[DETALLES DE ERRORES]")
            for item, error in stats.failed_items[:5]:
                print(f"    ✗ {item}")
                print(f"      → {error}")
            if len(stats.failed_items) > 5:
                print(f"    ... y {len(stats.failed_items) - 5} errores más")

    if stats.skipped_operations > 0:
        print(f"  Operaciones omitidas:     {stats.skipped_operations}")

    if apply:
        if stats.disk_after.is_valid():
            print(f"\n[ESTADO DESPUÉS]")
            print(f"  Espacio total:    {format_size(stats.disk_after.total)}")
            print(f"  Espacio usado:    {format_size(stats.disk_after.used)}")
            print(f"  Espacio libre:    {format_size(stats.disk_after.free)}")
            percent_after = (stats.disk_after.used / stats.disk_after.total * 100) if stats.disk_after.total > 0 else 0
            print(f"  Porcentaje usado: {percent_after:.1f}%")
            if stats.disk_before.is_valid():
                free_change = stats.disk_after.free - stats.disk_before.free
                print(f"\n[CAMBIO MEDIDO DEL ESPACIO LIBRE]")
                print(f"  Diferencia:       {format_size(free_change, signed=True)}")
                if free_change < 0:
                    print(f"  Estado:           El espacio libre DISMINUYÓ")
                    print(f"  Posible causa:    El sistema generó nuevos archivos")
                    print(f"                    durante la limpieza, o hay caché")
                    print(f"                    del sistema que se regenera.")
                elif free_change == 0:
                    print(f"  Estado:           Sin cambios en espacio libre")
                else:
                    print(f"  Estado:           Espacio liberado correctamente")
                print(f"\n  ⓘ NOTA IMPORTANTE:")
                print(f"    • Esta medida incluye cambios concurrentes del SO")
                print(f"    • Archivos abiertos pueden impedir su eliminación")
                print(f"    • El espacio fragmentado y metadatos pueden variar")
                print(f"    • No toda la diferencia es atribuible a LinuxClear")
        else:
            print(f"\n[ESTADO DESPUÉS]")
            print(f"  No disponible")
    else:
        print(f"\n[MODO VISTA PREVIA]")
        print(f"  ✓ No se ha eliminado nada")
        print(f"  • Los tamaños mostrados arriba son ESTIMACIONES")
        print(f"  • Para aplicar la limpieza, usa: --apply")
        print(f"  • Revisa los elementos antes de usar --apply")
        if stats.skipped_operations > 0:
            print(f"  • Tareas omitidas: {stats.skipped_operations}")

    print(f"\n[INFORMACIÓN DEL PROGRAMA]")
    print(f"  Versión:                  LinuxClear {VERSION}")
    print(f"  Modo de ejecución:        {'APLICAR CAMBIOS' if apply else 'VISTA PREVIA'}")
    print(f"  Nivel de limpieza:        {level.upper()}")
    print(f"  Permisos del administrador: {'Sí' if is_root() else 'No'}")
    print(f"\n[LÍMITES Y GARANTÍAS]")
    print(f"  ✓ No se han desinstalado paquetes")
    print(f"  ✓ No se ha modificado el kernel")
    print(f"  ✓ No se han desactivado servicios")
    print(f"  ✓ No se han modificado permisos recursivos")
    print(f"  ✓ No se han seguido enlaces simbólicos")

    print("=" * 60)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            f"LinuxClear v{VERSION}: limpieza conservadora de cachés "
            "y archivos temporales en Linux. Vista previa por defecto."
        )
    )
    parser.add_argument("--level", choices=["quick", "deep"], default="quick",
                        help="quick (por defecto): caché del usuario y APT. deep: añade temporales antiguos y journal de systemd.")
    parser.add_argument("--apply", action="store_true",
                        help="Aplica los cambios. Sin esta opción solo hay vista previa.")
    parser.add_argument("--yes", action="store_true",
                        help="Omite la confirmación interactiva. Requiere --apply.")
    parser.add_argument("--temp-days", type=int, default=7, metavar="DIAS",
                        help="Antigüedad mínima de archivos temporales en nivel deep (mínimo: 1, por defecto: 7).")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.temp_days < 1:
        parser.error("--temp-days debe ser al menos 1 día.")
    if args.yes and not args.apply:
        parser.error("--yes requiere --apply.")

    print_banner()

    if not validate_compatibility():
        return 1

    stats = CleanupStats()
    stats.disk_before = capture_disk_usage()
    if not stats.disk_before.is_valid():
        print("[WARN] No se pudo medir el espacio del disco.")

    home = target_home()
    print(f"[INFO] Usuario objetivo: {home}")
    print(f"[INFO] Nivel seleccionado: {args.level}")
    print("[INFO] Modo: " + ("APLICAR CAMBIOS" if args.apply else "VISTA PREVIA"))

    system_info()

    if args.apply and not args.yes:
        try:
            answer = input("\nSe pueden borrar datos de caché y registros antiguos.\nEscribe SI para continuar: ")
        except (EOFError, KeyboardInterrupt):
            print("\n[INFO] Operación cancelada por el usuario.")
            return 1
        if answer.strip() != "SI":
            print("[INFO] Operación cancelada. No se han aplicado cambios.")
            return 0

    clean_user_cache(home, apply=args.apply, stats=stats)
    apt_cleanup(apply=args.apply, stats=stats)

    if args.level == "deep":
        clean_old_temp_files(days=args.temp_days, apply=args.apply, stats=stats)
        journal_cleanup(apply=args.apply, stats=stats)

    if args.apply:
        stats.disk_after = capture_disk_usage()
        if not stats.disk_after.is_valid():
            print("[WARN] No se pudo medir el espacio del disco después de la limpieza.")

    print_summary(stats, apply=args.apply, level=args.level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
