# LinuxClear

**Herramienta conservadora de limpieza para Linux, desarrollada en Python 3.**

LinuxClear ayuda a gestionar cachés y archivos temporales para liberar espacio en disco. Está diseñada con una prioridad: permitir al usuario revisar las operaciones antes de aplicar cambios.

> **Estado:** desarrollo. La versión 1.1.6 se considerará estable únicamente después de superar las pruebas automatizadas y las comprobaciones documentadas.

## Características

- Vista previa por defecto.
- Limpieza de entradas de la caché del usuario.
- Limpieza de la caché de paquetes APT.
- Limpieza opcional de archivos temporales antiguos.
- Limpieza opcional de registros antiguos de systemd.
- Comprobaciones de rutas y enlaces simbólicos.
- Estadísticas de archivos, directorios, errores y operaciones omitidas.
- Mediciones del espacio libre antes y después de la limpieza.
- Informe final con limitaciones y advertencias.
- Pruebas automatizadas para verificar las operaciones críticas.

## Requisitos

- Una distribución Linux compatible.
- Python 3.
- Permisos de administrador para ejecutar las funciones de limpieza.
- APT para las tareas relacionadas con la caché de paquetes.
- `journalctl` para la limpieza opcional del journal de systemd.

LinuxClear está orientado principalmente a distribuciones basadas en Debian, como Debian, Ubuntu y Parrot OS. La compatibilidad concreta debe comprobarse en cada sistema.

## Instalación

Clona el repositorio oficial:

```bash
git clone https://github.com/DAVZ1337/LinuxClear.git
cd LinuxClear
```

Comprueba la versión de Python:

```bash
python3 --version
```

## Uso

### 1. Vista previa rápida

```bash
sudo python3 linuxclear.py
```

Muestra las operaciones propuestas sin aplicar la limpieza.

### 2. Vista previa profunda

```bash
sudo python3 linuxclear.py --level deep
```

Incluye las tareas adicionales de archivos temporales antiguos y journal, según las funciones implementadas.

### 3. Aplicar limpieza rápida

```bash
sudo python3 linuxclear.py --level quick --apply
```

Solicita confirmación antes de realizar cambios, salvo que se use la opción de confirmación automática.

### 4. Aplicar limpieza profunda

```bash
sudo python3 linuxclear.py --level deep --apply
```

**Precaución:** la limpieza profunda puede eliminar archivos temporales antiguos y registros del sistema que no se podrán recuperar.

### 5. Configurar la antigüedad de los temporales

Ejemplo para revisar archivos con más de 14 días:

```bash
sudo python3 linuxclear.py --level deep --temp-days 14
```

Para aplicar la operación:

```bash
sudo python3 linuxclear.py --level deep --temp-days 14 --apply
```

El valor mínimo permitido debe ser de un día.

### 6. Ejecución sin confirmación interactiva

```bash
sudo python3 linuxclear.py --level deep --apply --yes
```

`--yes` omite la confirmación interactiva y requiere `--apply`. Utilízalo únicamente después de revisar las operaciones y comprender sus consecuencias.

## Niveles de limpieza

| Nivel | Operaciones previstas |
|---|---|
| `quick` | Caché del usuario y caché APT. |
| `deep` | Operaciones de `quick`, temporales antiguos y journal de systemd. |

La vista previa debe mantenerse como comportamiento predeterminado en ambos niveles.

## Estadísticas

LinuxClear debe distinguir entre:

- **Tamaño estimado:** tamaño calculado antes de aplicar la limpieza.
- **Archivos eliminados:** archivos cuya eliminación se ha completado correctamente, según la definición del contador.
- **Directorios eliminados:** directorios eliminados correctamente.
- **Tamaño registrado de elementos eliminados:** tamaño contabilizado antes de eliminar los elementos.
- **Cambio medido del espacio libre:** diferencia entre las mediciones inicial y final del sistema de archivos.

Estas cantidades no son equivalentes.

El tamaño de los archivos no representa necesariamente la cantidad exacta de espacio físico recuperado. Los enlaces duros, archivos dispersos, metadatos, archivos abiertos y actividad concurrente del sistema pueden influir en el resultado.

Una diferencia positiva de espacio libre tampoco demuestra por sí sola que todo el espacio haya sido liberado por LinuxClear.

Cuando no sea posible medir un valor, debe indicarse como no disponible.

## Seguridad y limitaciones

- Revisa la vista previa antes de aplicar cambios.
- Cierra las aplicaciones cuya caché quieras limpiar.
- No se deben seguir enlaces simbólicos durante el recorrido o la eliminación.
- Las operaciones deben limitarse a rutas autorizadas y verificadas.
- Los archivos temporales antiguos pueden seguir utilizándose.
- La limpieza del journal puede eliminar registros antiguos de forma irreversible.
- No se deben desinstalar paquetes ni eliminar kernels automáticamente.
- No se deben desactivar servicios del sistema.
- No se deben modificar permisos recursivamente como parte de la limpieza.
- Si una operación no puede verificarse como segura, debe omitirse y explicarse el motivo.

Ninguna comprobación de rutas puede garantizar por sí sola la ausencia absoluta de condiciones de carrera. Las operaciones destructivas deben aplicar medidas de protección adecuadas al sistema operativo.

LinuxClear no garantiza una mejora del rendimiento. Limpiar una caché puede hacer que una aplicación tarde más en reconstruir sus datos.

## Pruebas automatizadas

Las pruebas deben ejecutarse en directorios temporales y utilizar mocks para simular comandos del sistema.

Cuando se implemente la suite de pruebas, su ejecución deberá documentarse aquí con el comando real y los resultados obtenidos.

No se debe afirmar que las pruebas han pasado si no se han ejecutado.

## Desarrollo y versiones

LinuxClear está desarrollado en Python 3. Las versiones deben actualizarse únicamente cuando el código, la documentación y las pruebas estén sincronizados.

La versión 1.1.6 solo debe marcarse como estable después de comprobar:

1. Que la vista previa no elimina ni modifica archivos.
2. Que las rutas inseguras se rechazan.
3. Que las estadísticas se calculan correctamente.
4. Que los errores y las operaciones omitidas se notifican.
5. Que las pruebas automatizadas pasan.
6. Que la documentación coincide con el comportamiento real.

## Licencia

Consulta los archivos del repositorio para conocer las condiciones de distribución. Si el proyecto no contiene una licencia, no debe suponerse que el código puede redistribuirse libremente.
