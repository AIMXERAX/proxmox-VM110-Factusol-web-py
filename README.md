# Sistema Factusol a MySQL

Documentacion unica del proyecto. Ultima actualizacion: 2026-05-09.

## Objetivo

Sincronizar datos de Factusol (Access .accdb) hacia MySQL remoto.

Incluye 3 escenarios:
- Sincronizacion incremental (diaria).
- Carga completa force-full (recuperacion o recarga total).
- Reconstruccion de estructura (cuando cambia el esquema).

## Flujo operativo

1. Leer tablas Access desde el origen.
2. Comparar contra estado previo (`estado_sincronizacion.json`).
3. Generar SQL (`tablas_aim_incremental.sql`).
4. Subir SQL por SFTP.
5. Ejecutar aplicacion remota en PHP sobre MySQL.
6. Registrar resultados en logs.

## Comandos principales

### Incremental normal

```cmd
aim_incremental.bat
```

### Carga completa

```cmd
aim_incremental.bat --force-full
```

### Reconstruccion de estructura + carga completa

```cmd
reconstruir_estructura.bat
```

### Comprobar conexion ODBC a Access

```cmd
.\.venv\Scripts\python.exe comprobar_conexion_odbc.py
```

El comprobador valida que el DSN configurado (`aim{ANIO}web`) existe, abre la
conexion y ejecuta `SELECT 1`. No realiza backup, no lee tablas ni modifica datos.

### Configurar el DSN ODBC de Access

Ejecuta como administrador para crear o actualizar el DSN de sistema:

```cmd
.\.venv\Scripts\python.exe configurar_dsn_web.py
```

### Servicio autonomo de sincronizacion

```cmd
instalar_servicio_factusol_web.bat
```

Ejecuta el instalador una vez como administrador. Registra un servicio Windows de
inicio automatico, por lo que no necesita el Programador de tareas. La cuenta elegida
para el servicio debe tener permisos de lectura sobre `ACCDB_SOURCE_PATH`. El servicio
se instala inicialmente como `LocalSystem`; configura en `services.msc` otra cuenta si
esa cuenta no puede leer la copia temporal local.

El servicio:

- Lee la copia temporal local definida por `ACCDB_SOURCE_PATH` en `.env`.
- Espera a que esa base este estable y sin archivo `.laccdb`.
- Copia la base a `ACCDB_LOCAL_DIRECTORY` mediante un archivo temporal.
- Crea el DSN de sistema `ACCESS_WEB_DSN` (`aim{ANIO}web`) para esa copia local.
- Compara una huella SHA-256 con la ultima sincronizacion y solo ejecuta el
  incremental si los datos cambiaron.

Tiempos configurables en `.env`:

- `ACCDB_CHECK_INTERVAL_SECONDS`: frecuencia de comprobacion, por defecto `60`.
- `ACCDB_STABILITY_SECONDS`: tiempo minimo sin cambios, por defecto `300`.
- `ACCDB_COPY_RETRY_SECONDS`: espera tras un error de copia o configuracion, por defecto `60`.

Para desinstalar el servicio, ejecuta como administrador:

```cmd
desinstalar_servicio_factusol_web.bat
```

## Cuando usar cada modo

- Incremental: operacion diaria.
- Force-full: recarga total de datos cuando hay desalineacion de estado.
- Reconstruccion: cambios de columnas/tipos o errores de esquema.

Errores tipicos que piden reconstruccion:
- Unknown column ...
- Incorrect data type ...
- Fallos repetidos por cambios de estructura en Factusol.

## Archivos clave

- `aim_datos_accdb_incremental.py`: logica principal de sincronizacion.
- `accdb_monitor.py`: copia temporal local, validacion y deteccion de cambios.
- `factusol_web_service.py`: servicio Windows autonomo.
- `reconstruir_estructura_bd.py`: orquestacion de reconstruccion.
- `generar_tablas_accdb.py`: generacion SQL de estructura.
- `config.py`: rutas y configuracion del entorno.
- `php/actualizar_bd_incremental.php`: aplicacion de SQL incremental.
- `php/reconstruir_estructura.php`: reconstruccion de tablas remotas.
- `estado_sincronizacion.json`: estado para detectar cambios.
- `logs/`: trazas de ejecucion.

## Logs

Cada ejecucion escribe una traza en `logs/`, incluyendo hora de inicio y fin,
script y argumentos. Los procesos principales generan estos archivos:

- `logs/incremental.log`: sincronizacion incremental normal.
- `logs/incremental_full.log`: sincronizacion completa.
- `logs/reconstruccion.log`: reconstruccion de estructura.
- `logs/generar_tablas_accdb.log`: generacion del SQL de estructura.
- `logs/comprobar_conexion_odbc.log`: comprobacion de conectividad ODBC.
- `logs/factusol_web.log`: eventos del servicio Windows.

Los eventos y estados del servicio tambien se guardan en la base SQLite definida
por `SERVICIOS_DB_PATH` en `.env` (por defecto, `C:\Python\db\Servicios.db`).

## Configuracion anual

`ANIO` es el unico valor anual en `.env`. Las rutas de origen, el nombre de la
copia local y el DSN admiten la plantilla `{ANIO}` y se resuelven automaticamente.
Al cambiar el ejercicio, actualiza solo `ANIO`; por ejemplo, `aim{ANIO}web` pasa de
`aim2026web` a `aim2027web` y el origen pasa de `aim2026.accdb` a `aim2027.accdb`.

## Requisitos minimos

- Windows con Python 3.
- Driver ODBC de Access instalado y funcional.
- Conectividad al servidor Factusol.
- Credenciales SFTP y endpoint remoto configurados.
- Dependencias instaladas desde `requirements.txt`.

Instalacion rapida de dependencias:

```cmd
requirements.bat
```

## Reconstruccion de estructura (resumen)

`reconstruir_estructura.bat` ejecuta:
1. Generacion de SQL de estructura desde Access.
2. Subida por SFTP.
3. DROP y CREATE remoto de tablas.
4. Recarga completa de datos.

Impacto esperado:
- Duracion aproximada: 10 a 30 minutos.
- Ventana temporal sin datos durante el proceso.

Checklist previo:
- Factusol cerrado (sin archivo .laccdb activo).
- Backup confirmado.
- Ejecucion fuera de horario operativo.

## Automatizacion recomendada

Politica simple y segura:
- Tarea programada diaria para `aim_incremental.bat`.
- Ejecutar reconstruccion solo cuando haya cambios de esquema o errores estructurales.

## Exportar y restaurar proyecto

### Exportar

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\export_project.ps1
```

Opciones utiles:
- `-ProjectPath`
- `-ExportDirName`
- `-MaxExports`
- `-IncludeEnv` (solo en canal seguro)
- `-RefreshRequirements`

### Restaurar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Prompt base de mantenimiento (resumen)

Objetivo de mantenimiento tecnico:
- Usar `.venv` separado del codigo.
- Verificar `requirements.txt`.
- Forzar uso de `.venv\Scripts\python.exe` en `.bat`.
- Limpiar residuos de entornos viejos y caches.

Validaciones minimas:
1. `.\.venv\Scripts\python.exe --version`
2. `.\.venv\Scripts\python.exe -m pip check`
3. Compilacion de scripts con `py_compile`.

## Historial y notas

Los demas .md del raiz quedan reducidos para evitar duplicidad. Esta es la fuente unica de referencia.

No publicar secretos de `.env` en repositorios o canales no seguros.
