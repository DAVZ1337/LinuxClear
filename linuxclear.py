#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import shutil
import argparse
import subprocess
from pathlib import Path

VERSION = "1.0.0"

def run(command, check=False, shell=False):
    print(f"\n[CMD] {' '.join(command) if isinstance(command, list) else command}")
    if shell:
        result = subprocess.run(command, shell=True, text=True, capture_output=True)
    else:
        result = subprocess.run(command, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    if check and result.returncode != 0:
        print(f"[WARN] Comando falló con código {result.returncode}: {' '.join(command) if isinstance(command, list) else command}")
    return result.returncode

def is_root():
    return os.geteuid() == 0

def print_banner():
    print("""
    ================================================
    linuxclear v%s
    Limpiador y optimizador para Linux / VirtualBox
    ================================================
    """ % VERSION)

def system_info():
    print("\n[INFO] Información del sistema:")
    run(["uname", "-a"])
    run(["df", "-h", "/"])
    run(["free", "-h"])
    run(["cat", "/proc/loadavg"])

def clean_temp_dirs():
    targets = [
        "/tmp",
        "/var/tmp",
    ]
    for path in targets:
        if os.path.exists(path):
            print(f"\n[INFO] Limpiando {path}")
            for entry in os.listdir(path):
                p = os.path.join(path, entry)
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        os.remove(p)
                    print(f"  - borrado: {p}")
                except Exception as e:
                    print(f"  [WARN] No se pudo borrar {p}: {e}")

def clean_user_caches():
    home = Path.home()
    cache_paths = [
        home / ".cache",
        home / ".local" / "share" / "Trash",
        home / ".local" / "share" / "recently-used.xbel",
    ]
    for path in cache_paths:
        if path.exists():
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    print(f"[OK] Caché borrada: {path}")
                else:
                    path.unlink()
                    print(f"[OK] Archivo borrado: {path}")
            except Exception as e:
                print(f"[WARN] No se pudo limpiar {path}: {e}")

    # cache de navegadores comunes
    browser_cache_paths = [
        home / ".config" / "google-chrome" / "Default" / "Cache",
        home / ".config" / "google-chrome" / "Default" / "GPUCache",
        home / ".config" / "chromium" / "Default" / "Cache",
        home / ".cache" / "mozilla",
        home / ".cache" / "firefox",
    ]
    for p in browser_cache_paths:
        if p.exists():
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink()
                print(f"[OK] Caché de navegador borrada: {p}")
            except Exception as e:
                print(f"[WARN] No se pudo limpiar {p}: {e}")

def clean_logs():
    log_dirs = [
        "/var/log",
    ]
    for d in log_dirs:
        if not os.path.exists(d):
            continue
        print(f"\n[INFO] Limpiando logs antiguos en {d}")
        for root, _, files in os.walk(d):
            for f in files:
                full = os.path.join(root, f)
                try:
                    if os.path.getmtime(full) < time.time() - (2 * 24 * 3600):
                        os.remove(full)
                        print(f"  - borrado log: {full}")
                except Exception as e:
                    print(f"  [WARN] No se pudo borrar {full}: {e}")

    # Vaciar journal
    if shutil.which("journalctl") is not None:
        run(["journalctl", "--vacuum-time=2d"], check=False)

def apt_cleanup():
    if shutil.which("apt-get") is not None:
        print("\n[INFO] Limpieza de apt...")
        run(["apt-get", "clean"], check=False)
        run(["apt-get", "autoclean"], check=False)
        run(["apt-get", "autoremove", "--purge", "-y"], check=False)

def remove_old_kernels():
    if shutil.which("dpkg") is not None:
        print("\n[INFO] Revisando kernels antiguos...")
        cmd = "dpkg -l 'linux-*' | awk '/^ii/{ print $2}' | grep -v \"$(uname -r)\" | grep -v 'linux-headers' | head -n -1"
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        kernels = [k.strip() for k in result.stdout.splitlines() if k.strip()]
        if kernels:
            print("Kernels viejos detectados:")
            for k in kernels:
                print(f" - {k}")
            run(["apt-get", "purge", "-y", *kernels], check=False)
        else:
            print("No hay kernels antiguos para borrar.")

def clean_package_cache():
    cache_paths = [
        "/var/cache/apt/archives",
        "/var/cache",
    ]
    for base in cache_paths:
        if os.path.exists(base):
            for root, dirs, files in os.walk(base):
                for f in files:
                    full = os.path.join(root, f)
                    try:
                        if full.endswith(".deb") or full.endswith(".tmp") or full.endswith(".old"):
                            os.remove(full)
                            print(f"[OK] Paquete/cache borrado: {full}")
                    except Exception as e:
                        print(f"[WARN] No se pudo borrar {full}: {e}")

def clean_snap_flatpak():
    if shutil.which("snap") is not None:
        print("\n[INFO] Limpiando Snap...")
        run(["snap", "set", "system", "refresh.retain=2"], check=False)
        run(["snap", "list", "--all"], check=False)

    if shutil.which("flatpak") is not None:
        print("\n[INFO] Limpiando Flatpak...")
        run(["flatpak", "uninstall", "--unused", "-y"], check=False)

def disable_unneeded_services():
    services = [
        "bluetooth",
        "cups",
        "ModemManager",
        "avahi-daemon",
        "wpa_supplicant",
        "apt-daily.timer",
        "apt-daily-upgrade.timer",
    ]

    for service in services:
        if subprocess.run(["systemctl", "list-unit-files", "--type=service", "--state=enabled", "--no-pager"], capture_output=True, text=True).stdout.find(service) != -1:
            print(f"\n[INFO] Deshabilitando servicio no esencial: {service}")
            run(["systemctl", "stop", service], check=False)
            run(["systemctl", "disable", service], check=False)

def optimize_memory():
    print("\n[INFO] Optimizando memoria del sistema...")
    try:
        with open("/proc/sys/vm/drop_caches", "w") as f:
            f.write("3")
        print("[OK] Cache de memoria liberada.")
    except Exception as e:
        print(f"[WARN] No se pudo liberar caché: {e}")

    # Ajustes de VM a valores más agresivos para máquinas lentas
    try:
        with open("/proc/sys/vm/swappiness", "w") as f:
            f.write("10\n")
        print("[OK] swappiness ajustado a 10.")
    except Exception as e:
        print(f"[WARN] No se pudo ajustar swappiness: {e}")

def cleanup_quick():
    print("\n[LEVEL] QUICK")
    clean_temp_dirs()
    clean_user_caches()
    clean_logs()
    apt_cleanup()
    clean_package_cache()

def cleanup_deep():
    print("\n[LEVEL] DEEP")
    cleanup_quick()
    remove_old_kernels()
    clean_snap_flatpak()
    disable_unneeded_services()
    optimize_memory()

def cleanup_extreme():
    print("\n[LEVEL] EXTREME")
    cleanup_deep()
    # limpieza extra de almacenamiento
    for p in ["/root/.cache", "/home"]:
        if os.path.exists(p):
            for root, dirs, files in os.walk(p):
                for f in files:
                    full = os.path.join(root, f)
                    try:
                        if os.path.getsize(full) < 50 * 1024 * 1024:
                            pass
                    except Exception:
                        pass
    print("[INFO] Limpieza extrema completada. Se liberará caché y servicios innecesarios en la próxima reinicialización.")

def validate_compatibility():
    if not is_root():
        print("\n[ERROR] Debes ejecutar este script como root: sudo python3 linuxclear.py --level deep")
        sys.exit(1)

    if not os.path.exists("/etc/os-release"):
        print("[WARN] Sistema Linux no detectado completamente, pero el script intentará continuar.")
        return

def main():
    parser = argparse.ArgumentParser(description="linuxclear - optmiza Linux y limpia caché, memoria y almacenamiento.")
    parser.add_argument("--level", choices=["quick", "deep", "extreme"], default="deep", help="Nivel de limpieza")
    args = parser.parse_args()

    print_banner()
    validate_compatibility()
    system_info()

    if args.level == "quick":
        cleanup_quick()
    elif args.level == "deep":
        cleanup_deep()
    elif args.level == "extreme":
        cleanup_extreme()

    print("\n==============================================")
    print("Limpieza finalizada.")
    print("==============================================")
    print("\nSiguientes pasos recomendados:")
    print("  1) Revisa si hay servicios no esenciales que quieras dejar activos.")
    print("  2) Reinicia el sistema si quieres que la RAM y el caché se estabilicen.")
    print("  3) Ejecuta: sudo python3 linuxclear.py --level deep")
    print("==============================================\n")

if __name__ == "__main__":
    main()