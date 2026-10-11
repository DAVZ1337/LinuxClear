#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LinuxClear v1.1.1
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

VERSION = "1.1.1"

TEMP_DIRS = (
    Path("/tmp"),
    Path("/var/tmp"),
)

# Raíz del sistema a limpiar
ROOT_FILESYSTEM = Path("/")


@dataclass
class CleanupStats:
    """Estadísticas de limpieza."""
    estimated_size: int = 0
    actual_removed_size: int = 0
    files_removed: int = 0
    dirs_removed: int = 0
    failed_operations: int = 0
    skipped_operations: int = 0
    failed_items: list = field(default_factory=list)
    disk_space_before: int = 0
    disk_space_after: int = 0


def is_root():
    """Comprueba si el programa se ejecuta como administrador."""
    return hasattr(os, "geteuid") and os.geteuid() == 0


def target_home():
    """Intenta identificar el directorio del usuario que ejecutó sudo."""
    sudo_user = os.environ.get("SUDO_USER")

    if sudo_user and sudo_user != "root":
        try:
            import pwd
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except (ImportError, KeyError):
            pass

    return Path.home()


def format_size(size_bytes):
    """Convierte bytes a formato legible (B, KB, MB, GB, TB)."""
    if size_bytes < 0:
        return "0 B"
    
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def get_disk_usage(path=None):
    """
    Obtiene el uso de disco de forma fiable con shutil.disk_usage.
    Retorna (total, usado, libre) en bytes.
    """
    if path is None:
        path = ROOT_FILESYSTEM
    
    try:
        usage = shutil.disk_usage(str(path))
        return (usage.total, usage.used, usage.free)
    except OSError as exc:
        print(f"[WARN] No se pudo consultar el espacio en disco: {exc}")
        return None


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
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )

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
    Comprueba que target está dentro de base y no es un enlace simbólico.
    Previene seguir enlaces fuera de la ruta prevista.
    """
    try:
        target = target.resolve()
        base = base.resolve()
        return target.is_relative_to(base) and not target.is_symlink()
    except (OSError, ValueError):
        return False


def get_path_size(path):
    """
    Calcula el tamaño total de una ruta (archivo o directorio).
    No sigue enlaces simbólicos.
    """
    try:
        if path.is_symlink():
            return 0
        
        if path.is_file():
            return path.stat().st_size
        
        if path.is_dir():
            total = 0
            try:
                for entry in path.rglob("*"):
                    try:
                        if entry.is_file() and not entry.is_symlink():
                            total += entry.stat().st_size
                    except OSError:
                        continue
            except (OSError, RecursionError):
                pass
            return total
    except OSError:
        pass
    
    return 0


def remove_path(path, apply=False, stats=None):
    """
    Elimina una ruta concreta únicamente al activar --apply.
    Retorna True si se eliminó correctamente, False en caso contrario.
    """
    if stats is None:
        stats = CleanupStats()
    
    size = get_path_size(path)
    stats.estimated_size += size
    
    if not apply:
        print(f"[DRY-RUN] Se limpiaría: {path} ({format_size(size)})")
        return True
    
    try:
        if path.is_symlink():
            path.unlink()
            stats.files_removed += 1
        elif path.is_file():
            path.unlink()
            stats.files_removed += 1
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=False)
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
    """
    Limpia las entradas de la caché del usuario.
    No elimina el directorio .cache en sí, solo su contenido.
    """
    if stats is None:
        stats = CleanupStats()
    
    cache = home / ".cache"

    print("\n[INFO] Caché del usuario")

    if not cache.is_dir():
        print(f"[INFO] No existe: {cache}")
        return stats

    if not is_safe_path(cache, home):
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
        remove_path(entry, apply=apply, stats=stats)
    
    return stats


def clean_old_temp_files(days=7, apply=False, stats=None):
    """
    Propone limpiar archivos normales antiguos en /tmp y /var/tmp.
    No elimina directorios completos ni sigue enlaces simbólicos.
    Nota: Un archivo antiguo no garantiza que esté libre de uso.
    """
    if stats is None:
        stats = CleanupStats()
    
    cutoff = time.time() - (days * 24 * 60 * 60)

    print(f"\n[INFO] Archivos temporales con más de {days} días")
    print("[AVISO] Archivos antiguos pueden estar en uso.")

    for directory in TEMP_DIRS:
        if not directory.is_dir():
            continue

        try:
            for root, dirs, files in os.walk(
                directory,
                followlinks=False,
            ):
                # Evita recorrer directorios que sean enlaces simbólicos.
                dirs[:] = [
                    name
                    for name in dirs
                    if not (Path(root) / name).is_symlink()
                ]

                for name in files:
                    path = Path(root) / name

                    try:
                        if path.is_symlink() or not path.is_file():
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
    """
    Limpia la caché de paquetes APT, sin desinstalar paquetes.
    No usa autoremove ni modifica paquetes instalados.
    """
    if stats is None:
        stats = CleanupStats()
    
    if not shutil.which("apt-get"):
        print("\n[INFO] APT no está disponible. Se omite esta tarea.")
        stats.skipped_operations += 1
        return stats

    print("\n[INFO] Limpieza de caché APT")

    # apt-get clean
    ret1 = run(["apt-get", "clean"], apply=apply)
    if apply and ret1 != 0:
        stats.failed_operations += 1
    elif apply:
        print("[OK] apt-get clean completado.")
    
    # apt-get autoclean
    ret2 = run(["apt-get", "autoclean"], apply=apply)
    if apply and ret2 != 0:
        stats.failed_operations += 1
    elif apply:
        print("[OK] apt-get autoclean completado.")
    
    return stats


def journal_cleanup(apply=False, stats=None):
    """
    Reduce el journal de systemd a los registros recientes (14 días).
    Esto elimina registros antiguos, no todos.
    """
    if stats is None:
        stats = CleanupStats()
    
    if not shutil.which("journalctl"):
        print("\n[INFO] journalctl no está disponible.")
        stats.skipped_operations += 1
        return stats

    print("\n[INFO] Conservación del journal: últimos 14 días")
    print("[INFO] Se eliminarán registros anteriores a 14 días.")

    ret = run(
        ["journalctl", "--vacuum-time=14d"],
        apply=apply,
    )
    
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
        print("\nNota: Se requieren permisos de administrador para limpiar")
        print("cachés de sistema y archivos en /tmp y /var/tmp.")
        return False

    return True


def print_summary(stats, apply=False, level="quick"):
    """Imprime un resumen detallado de la limpieza."""
    print("\n" + "=" * 50)
    print("RESUMEN DE LIMPIEZA")
    print("=" * 50)

    # Información antes
    if stats.disk_space_before > 0:
        total, used_before, free_before = stats.disk_space_before, None, None
        disk_info = get_disk_usage()
        if disk_info:
            total, used_before, free_before = disk_info
        
        print(f"\n[ANTES]")
        print(f"  Espacio total:    {format_size(total)}")
        if used_before is not None:
            print(f"  Espacio usado:    {format_size(used_before)}")
            print(f"  Espacio libre:    {format_size(free_before)}")
            percent = (used_before / total * 100) if total > 0 else 0
            print(f"  Ocupación:        {percent:.1f}%")

    # Estimaciones
    print(f"\n[ESTIMACIONES]")
    print(f"  Tamaño estimado:  {format_size(stats.estimated_size)}")

    # Operaciones realizadas
    if apply:
        print(f"\n[OPERACIONES COMPLETADAS]")
        print(f"  Archivos eliminados:     {stats.files_removed}")
        print(f"  Directorios eliminados:  {stats.dirs_removed}")
        print(f"  Espacio eliminado real:  {format_size(stats.actual_removed_size)}")
        
        if stats.failed_operations > 0:
            print(f"  Operaciones fallidas:    {stats.failed_operations}")
            if stats.failed_items:
                print("\n[ERRORES]")
                for item, error in stats.failed_items[:10]:  # Mostrar máx 10
                    print(f"    - {item}")
                    print(f"      {error}")
                if len(stats.failed_items) > 10:
                    print(f"    ... y {len(stats.failed_items) - 10} errores más")
        
        if stats.skipped_operations > 0:
            print(f"  Operaciones omitidas:    {stats.skipped_operations}")

        # Información después
        disk_info_after = get_disk_usage()
        if disk_info_after:
            total, used_after, free_after = disk_info_after
            print(f"\n[DESPUÉS]")
            print(f"  Espacio total:    {format_size(total)}")
            print(f"  Espacio usado:    {format_size(used_after)}")
            print(f"  Espacio libre:    {format_size(free_after)}")
            percent_after = (used_after / total * 100) if total > 0 else 0
            print(f"  Ocupación:        {percent_after:.1f}%")

            # Diferencia real
            if stats.disk_space_before > 0:
                real_freed = stats.disk_space_before - (total - free_after)
                print(f"\n[DIFERENCIA REAL]")
                print(f"  Espacio liberado: {format_size(real_freed)}")
                print(f"  Nota: Esta medida puede variar por actividad")
                print(f"  concurrente, archivos abiertos o del sistema.")
    else:
        print(f"\n[MODO VISTA PREVIA]")
        print(f"  No se ha eliminado nada.")
        print(f"  Revisa las cantidades antes de usar --apply.")
        if stats.skipped_operations > 0:
            print(f"  Tareas omitidas: {stats.skipped_operations}")

    # Notas finales
    print(f"\n[INFORMACIÓN]")
    print(f"  Nivel de limpieza: {level}")
    print(f"  Kernel y servicios: Sin cambios")
    print(f"  Paquetes instalados: Sin cambios")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "LinuxClear v1.1.1: limpieza conservadora de cachés "
            "y archivos temporales en Linux."
        )
    )

    parser.add_argument(
        "--level",
        choices=["quick", "deep"],
        default="quick",
        help=(
            "quick: caché del usuario y APT (por defecto). "
            "deep: añade temporales antiguos y journal."
        ),
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios. Sin esta opción solo hay vista previa.",
    )

    parser.add_argument(
        "--yes",
        action="store_true",
        help="Omite la confirmación interactiva. Requiere --apply.",
    )

    parser.add_argument(
        "--temp-days",
        type=int,
        default=7,
        metavar="DIAS",
        help="Antigüedad mínima de archivos temporales en nivel deep (por defecto 7).",
    )

    args = parser.parse_args()

    if args.temp_days < 1:
        parser.error("--temp-days debe ser al menos 1.")

    if args.yes and not args.apply:
        parser.error("--yes requiere --apply.")

    print_banner()

    if not validate_compatibility():
        return 1

    # Inicializar estadísticas
    stats = CleanupStats()
    
    # Medir espacio antes
    disk_before = get_disk_usage()
    if disk_before:
        stats.disk_space_before = disk_before[2]  # Espacio libre

    home = target_home()

    print(f"[INFO] Usuario objetivo: {home}")
    print(f"[INFO] Nivel seleccionado: {args.level}")
    print(
        "[INFO] Modo: "
        + ("APLICAR CAMBIOS" if args.apply else "VISTA PREVIA")
    )

    system_info()

    if args.apply and not args.yes:
        try:
            answer = input(
                "\nSe pueden borrar datos de caché y registros antiguos.\n"
                "Escribe SI para continuar: "
            )
        except (EOFError, KeyboardInterrupt):
            print("\n[INFO] Operación cancelada.")
            return 1

        if answer.strip() != "SI":
            print("[INFO] Operación cancelada. No se han aplicado cambios.")
            return 0

    # Limpieza de caché del usuario
    clean_user_cache(home, apply=args.apply, stats=stats)

    # Limpieza de caché de paquetes APT
    apt_cleanup(apply=args.apply, stats=stats)

    # Limpieza profunda si se solicita
    if args.level == "deep":
        clean_old_temp_files(
            days=args.temp_days,
            apply=args.apply,
            stats=stats,
        )
        journal_cleanup(apply=args.apply, stats=stats)

    # Resumen final
    print_summary(stats, apply=args.apply, level=args.level)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
