# Procedimiento de ejecucion

## Objetivo

La aplicacion sincroniza las tablas de Factusol, almacenadas en una base de datos Access (`.accdb`), con una base MySQL remota.

El flujo normal es:

1. Leer la copia local de Access mediante ODBC.
2. Comparar sus filas con `estado_sincronizacion.json`.
3. Generar `tablas_aim_incremental.sql` con los cambios.
4. Subir el SQL al servidor mediante SFTP.
5. Llamar al endpoint remoto que aplica el SQL en MySQL.
6. Registrar la ejecucion en `logs/`.

## Requisitos

- Windows con Python 3 instalado.
- Driver ODBC de Microsoft Access instalado y operativo.
- Acceso a la copia local de la base Access.
- Conectividad con el servidor SFTP y el endpoint remoto.
- Archivo `.env` configurado con los datos del entorno.

## Preparacion inicial

1. Crear el archivo `.env` a partir de `.env.example` y rellenar los valores reales.
2. Configurar, como minimo, el ejercicio (`ANIO`), las credenciales SFTP, `PALABRA_CLAVE`, la URL remota y las rutas de Access.
3. Ejecutar el instalador de dependencias:

```cmd
requirements.bat
```

El script crea el entorno virtual `.venv` si no existe e instala las dependencias de `requirements.txt`.

4. Crear o actualizar el DSN ODBC de sistema como administrador:

```cmd
.\.venv\Scripts\python.exe configurar_dsn_web.py
```

El DSN utilizado se llama `aim{ANIO}web` por defecto, por ejemplo `aim2026web`.

5. Verificar la conexion ODBC:

```cmd
.\.venv\Scripts\python.exe comprobar_conexion_odbc.py
```

Esta comprobacion valida el DSN y ejecuta `SELECT 1`; no modifica datos.

## Sincronizacion incremental

Es el modo de operacion habitual y debe ejecutarse diariamente:

```cmd
aim_incremental.bat
```

La sincronizacion requiere que exista la copia local de Access configurada. Si no hay cambios respecto al estado anterior, el proceso no sube ni aplica SQL.

Los resultados se registran principalmente en `logs/incremental.log` y `logs/monitor.log`.

## Carga completa

Usar cuando el estado local y el remoto puedan estar desalineados o se necesite recargar todos los datos:

```cmd
aim_incremental.bat --force-full
```

Este modo elimina `estado_sincronizacion.json`, genera sentencias `TRUNCATE` para las tablas afectadas y vuelve a insertar todos los registros. Si falla, puede realizar hasta cinco intentos con cinco minutos de espera entre ellos.

Tambien puede ejecutarse mediante:

```cmd
aim_incremental_force_full.bat
```

## Reconstruccion de estructura

Usar cuando Factusol haya cambiado columnas o tipos de datos, o ante errores como `Unknown column` o incompatibilidades de tipos:

```cmd
reconstruir_estructura.bat
```

El proceso genera la estructura actual desde Access, sube el SQL al servidor, reconstruye las tablas remotas y ejecuta una carga completa.

Antes de iniciarlo:

- Confirmar una copia de seguridad.
- Cerrar Factusol y comprobar que no exista un archivo `.laccdb` activo.
- Ejecutarlo fuera de horario operativo.

La reconstruccion puede durar entre 10 y 30 minutos y deja una ventana temporal sin datos remotos.

## Servicio Windows

Para automatizar la sincronizacion, ejecutar como administrador:

```cmd
instalar_servicio_factusol_web.bat
```

El servicio `AIMXERAX_FACTUSOL_WEB` se inicia automaticamente. Vigila la copia temporal configurada por `ACCDB_SOURCE_PATH`, espera a que este estable y sin bloqueo, la copia a `ACCDB_LOCAL_DIRECTORY`, actualiza el DSN y ejecuta el incremental solo si detecta cambios.

Parametros configurables en `.env`:

- `ACCDB_CHECK_INTERVAL_SECONDS`: intervalo de comprobacion; por defecto, 60 segundos.
- `ACCDB_STABILITY_SECONDS`: tiempo minimo sin cambios; por defecto, 300 segundos.
- `ACCDB_COPY_RETRY_SECONDS`: espera tras un error de copia o configuracion; por defecto, 60 segundos.

Para desinstalarlo, ejecutar como administrador:

```cmd
desinstalar_servicio_factusol_web.bat
```

## Revision de incidencias

- Revisar los archivos de `logs/` tras cada error.
- Comprobar el DSN y la conectividad con `comprobar_conexion_odbc.py`.
- Verificar que la cuenta que ejecuta el servicio pueda leer `ACCDB_SOURCE_PATH`.
- Confirmar las credenciales SFTP y la URL remota configuradas en `.env`.
- No publicar el archivo `.env`, ya que contiene secretos.
