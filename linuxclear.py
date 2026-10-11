#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LinuxClear v1.1.0
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

VERSION = "1.1.0"

TEMP_DIRS = (
    Path("/tmp"),
    Path("/var/tmp"),
)

# Variable global para rastrear el espacio eliminado
cleaned_size = 0


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
    """Convierte bytes a formato legible (B, KB, MB, GB)."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


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
        result = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"[ERROR] No se pudo ejecutar el comando: {exc}")
        return 127

    if result.returncode != 0:
        print(
            f"[WARN] El comando terminó con código "
            f"{result.returncode}."
        )

    return result.returncode


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


def get_path_size(path):
    """Calcula el tamaño total de una ruta (archivo o directorio)."""
    try:
        if path.is_symlink() or path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            total = 0
            for entry in path.rglob("*"):
                try:
                    if entry.is_file() and not entry.is_symlink():
                        total += entry.stat().st_size
                except OSError:
                    continue
            return total
    except OSError:
        return 0
    return 0


def remove_path(path, apply=False):
    """Elimina una ruta concreta únicamente al activar --apply."""
    global cleaned_size
    
    if not apply:
        size = get_path_size(path)
        print(f"[DRY-RUN] Se limpiaría: {path} ({format_size(size)})")
        cleaned_size += size
        return

    size = get_path_size(path)
    
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            return

        print(f"[OK] Limpiado: {path} ({format_size(size)})")
        cleaned_size += size

    except OSError as exc:
        print(f"[WARN] No se pudo limpiar {path}: {exc}")


def clean_user_cache(home, apply=False):
    """Limpia las entradas de la caché del usuario."""
    cache = home / ".cache"

    print("\n[INFO] Caché del usuario")

    if not cache.is_dir():
        print(f"[INFO] No existe: {cache}")
        return

    print(f"[INFO] Directorio: {cache}")
    print("[AVISO] Cierra tus aplicaciones antes de aplicar la limpieza.")

    try:
        entries = list(cache.iterdir())
    except OSError as exc:
        print(f"[WARN] No se pudo leer la caché: {exc}")
        return

    for entry in entries:
        remove_path(entry, apply=apply)


def clean_old_temp_files(days=7, apply=False):
    """
    Propone limpiar archivos normales antiguos en /tmp y /var/tmp.
    No elimina directorios completos ni sigue enlaces simbólicos.
    """
    cutoff = time.time() - (days * 24 * 60 * 60)

    print(
        f"\n[INFO] Archivos temporales con más de {days} días"
    )

    for directory in TEMP_DIRS:
        if not directory.is_dir():
            continue

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
                        remove_path(path, apply=apply)

                except OSError as exc:
                    print(f"[WARN] No se pudo revisar {path}: {exc}")


def apt_cleanup(apply=False):
    """Limpia la caché de paquetes APT, sin desinstalar paquetes."""
    if not shutil.which("apt-get"):
        print("\n[INFO] APT no está disponible. Se omite esta tarea.")
        return

    print("\n[INFO] Limpieza de caché APT")

    run(["apt-get", "clean"], apply=apply)
    run(["apt-get", "autoclean"], apply=apply)


def journal_cleanup(apply=False):
    """Reduce el journal de systemd a los registros recientes."""
    if not shutil.which("journalctl"):
        print("\n[INFO] journalctl no está disponible.")
        return

    print("\n[INFO] Conservación del journal: últimos 14 días")

    run(
        ["journalctl", "--vacuum-time=14d"],
        apply=apply,
    )


def validate_compatibility():
    """Comprueba el sistema y los permisos necesarios."""
    if not sys.platform.startswith("linux"):
        print("[ERROR] LinuxClear está diseñado para Linux.")
        return False

    if not is_root():
        print("[ERROR] Ejecuta el programa con sudo.")
        print("Ejemplo: sudo python3 linuxclear.py")
        return False

    return True


def main():
    global cleaned_size
    
    parser = argparse.ArgumentParser(
        description=(
            "LinuxClear: limpieza conservadora de cachés "
            "y archivos temporales en Linux."
        )
    )

    parser.add_argument(
        "--level",
        choices=["quick", "deep"],
        default="quick",
        help=(
            "quick: caché del usuario y APT. "
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
        help="Antigüedad mínima de archivos temporales en nivel deep.",
    )

    args = parser.parse_args()

    if args.temp_days < 1:
        parser.error("--temp-days debe ser al menos 1.")

    if args.yes and not args.apply:
        parser.error("--yes requiere --apply.")

    print_banner()

    if not validate_compatibility():
        return 1

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

    # Limpieza de caché del usuario.
    clean_user_cache(home, apply=args.apply)

    # Limpieza de caché de paquetes.
    apt_cleanup(apply=args.apply)

    if args.level == "deep":
        clean_old_temp_files(
            days=args.temp_days,
            apply=args.apply,
        )

        journal_cleanup(apply=args.apply)

    print("\n========================================")

    if args.apply:
        print("[FIN] Operación de limpieza completada.")
    else:
        print("[FIN] Vista previa completada.")
        print("No se ha borrado nada.")
        print("Revisa la lista antes de utilizar --apply.")

    print(f"\n[RESUMEN] Espacio liberado: {format_size(cleaned_size)}")
    print("LinuxClear no elimina kernels ni desactiva servicios.")
    print("========================================")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
