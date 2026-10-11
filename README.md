# LinuxClear

# LinuxClear

Herramienta de limpieza conservadora para Linux, desarrollada en Python 3.

LinuxClear ayuda a liberar espacio mediante la limpieza de cachés y archivos temporales. Su prioridad es evitar cambios innecesarios en el sistema.

**Por seguridad, funciona en modo de vista previa por defecto.**

## Características

- Información del sistema: kernel, memoria y espacio en disco.
- Limpieza de la caché del usuario.
- Limpieza de la caché de paquetes APT.
- Detección de archivos temporales antiguos.
- Limpieza opcional del journal de systemd.
- Vista previa antes de borrar.
- Confirmación antes de aplicar cambios.
- No desactiva servicios ni elimina kernels automáticamente.

## Requisitos

- Linux.
- Python 3.
- Permisos de administrador.
- APT para las funciones de limpieza de paquetes APT.

El proyecto está pensado principalmente para distribuciones basadas en Debian y Ubuntu.

## Instalación

Clona el repositorio:

```bash
git clone https://github.com/DAVZ1337/LinuxClear.git
cd LinuxClear
```

## Uso

### Vista previa rápida

No borra nada:

```bash
sudo python3 linuxclear.py
```

### Vista previa profunda

```bash
sudo python3 linuxclear.py --level deep
```

### Aplicar limpieza rápida

```bash
sudo python3 linuxclear.py --level quick --apply
```

El programa pedirá confirmación antes de continuar.

### Aplicar limpieza profunda

```bash
sudo python3 linuxclear.py --level deep --apply
```

### Configurar la antigüedad de los temporales

Por ejemplo, revisar archivos de más de 14 días:

```bash
sudo python3 linuxclear.py --level deep --temp-days 14
```

Para aplicar esa limpieza:

```bash
sudo python3 linuxclear.py --level deep --temp-days 14 --apply
```

### Automatización

La opción `--yes` evita la confirmación interactiva. Úsala únicamente si entiendes las consecuencias:

```bash
sudo python3 linuxclear.py --level deep --apply --yes
```

## Niveles

| Nivel | Funciones |
|---|---|
| `quick` | Caché del usuario y caché APT. |
| `deep` | Lo anterior, archivos temporales antiguos y journal de systemd. |

Todos los niveles funcionan en modo de vista previa salvo que se añada `--apply`.

## Seguridad

- Revisa la vista previa antes de aplicar cambios.
- Cierra los navegadores y aplicaciones antes de limpiar sus cachés.
- La limpieza de caché puede provocar que algunas aplicaciones reconstruyan datos temporales.
- La limpieza profunda puede eliminar archivos temporales antiguos y registros del sistema.
- No se eliminan kernels automáticamente.
- No se desactivan servicios de red ni servicios del sistema.
- No se modifica `swappiness` ni se vacía la caché de RAM.
- Limpiar cachés no garantiza una mejora del rendimiento.

Prueba el programa en una máquina virtual antes de utilizarlo en un equipo importante.

## Estado del proyecto

LinuxClear está en desarrollo. Las funciones y la compatibilidad deben probarse en cada distribución.

## Licencia

El repositorio todavía no especifica una licencia. No debe asumirse que el código se puede redistribuir libremente hasta que se añada una.
