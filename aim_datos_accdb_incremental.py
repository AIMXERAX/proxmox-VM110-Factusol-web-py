from venv_bootstrap import ensure_venv
ensure_venv()

# Redirigir print al archivo de log del script
from service_logging import setup_print_log
setup_print_log(__file__)

#Constantes y rutinas comunes.
from genericpath import exists
import paramiko
import pandas as pd
import pyodbc
import warnings
from os import getcwd
import time
import requests
import bcrypt
import urllib.parse
import os
from datetime import datetime
import hashlib
import json

# Importar configuración del sistema
import config
from access_odbc import access_connection_string

#Variables globales
tiempo_inicio = time.time()


def configurar_salida_unicode():
    """Evita errores de codificación al imprimir caracteres Unicode en Windows."""
    import sys

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            # Si no se puede reconfigurar, continuar con la configuración actual
            pass

def calcular_hash_fila(row):
    """Calcula un hash MD5 de una fila para detectar cambios excluyendo campos TRZ"""
    # Filtrar columnas que empiecen por 'TRZ' antes de calcular el hash
    filtered_row = []
    for col in row.index:
        if not col.upper().startswith('TRZ'):
            val = row[col]
            filtered_row.append(str(val) if pd.notna(val) else 'NULL')
    
    # Convertir la fila filtrada a string y calcular hash
    row_str = ''.join(filtered_row)
    return hashlib.md5(row_str.encode('utf-8')).hexdigest()

def cargar_estado_sincronizacion():
    """Carga el estado de la última sincronización"""
    estado_path = os.path.join(config.PATH_MAIN, config.ESTADO_FILE_PATH)
    if os.path.exists(estado_path):
        try:
            with open(estado_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def guardar_estado_sincronizacion(estado):
    """Guarda el estado actual de sincronización"""
    estado_path = os.path.join(config.PATH_MAIN, config.ESTADO_FILE_PATH)
    with open(estado_path, 'w', encoding='utf-8') as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)

def verificar_copia_local():
    """Comprueba que el servicio haya creado la copia local de Access."""
    if not os.path.isfile(config.LOCAL_ACCDB_PATH):
        print("No existe una copia local de Access para sincronizar.")
        print(f"Ruta esperada: {config.LOCAL_ACCDB_PATH}")
        return False

    print(f"Usando copia local de Access: {config.LOCAL_ACCDB_PATH}")
    return True

def log_add(dato):
    log = os.path.join(config.PATH_MAIN, config.LOG_ARCHIVO)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    ahora = time.strftime("%d/%m/%y %H:%M:%S")
    texto = ahora + "   " + dato + '\n'

    # Leer última línea del log si existe
    ultima_linea = ""
    if os.path.exists(log):
        with open(log, "rb") as f:
            try:
                f.seek(-2, os.SEEK_END)
                while f.read(1) != b'\n':
                    f.seek(-2, os.SEEK_CUR)
            except OSError:
                f.seek(0)
            ultima_linea = f.readline().decode(errors="ignore").strip()

    # Comparar solo el contenido del mensaje (ignorando la fecha)
    if ultima_linea.endswith(dato):
        return  # No escribir si es igual

    # Escribir nuevo mensaje con codificación correcta
    with open(log, "a", encoding="utf-8") as f:
        f.write(texto)

def export_sftp(archivo):
    def rutas_candidatas(nombre):
        return [f"/{nombre}", nombre]

    # Validar que las credenciales FTP estén configuradas
    if not config.FTP_HOST or not config.FTP_USER or not config.FTP_PASSWORD:
        print("Error: Credenciales FTP no configuradas en el archivo .env")
        print("Asegúrate de tener FTP_HOST, FTP_USER y FTP_PASSWORD configurados")
        return False
    
    # Crear cliente SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Intentando conectar a {config.FTP_HOST}...")
        # Conectar via SSH con timeout
        ssh.connect(hostname=config.FTP_HOST, 
                   username=config.FTP_USER, 
                   password=config.FTP_PASSWORD,
                   timeout=30)
        
        # Crear cliente SFTP
        sftp = ssh.open_sftp()
        print("Conexión establecida con la SFTP ... ")
        
        localFilePath = os.path.join(config.PATH_MAIN, archivo)
        print(f"Archivo a subir: {archivo}")
        
        # Verificar que el archivo local existe
        if not os.path.exists(localFilePath):
            print(f"Error: El archivo local {localFilePath} no existe")
            return False

        # Probar rutas absolutas/relativas existentes sin crear directorios
        ultimo_error = None
        for remoteFilePath in rutas_candidatas(archivo):
            remoteDirPath = os.path.dirname(remoteFilePath).replace('\\', '/') or '.'
            print(f"Intentando ruta remota: {remoteFilePath}")
            try:
                sftp.stat(remoteDirPath)
            except Exception as e:
                print(f"  - Directorio no accesible: {remoteDirPath} ({e})")
                ultimo_error = e
                continue

            try:
                sftp.put(localFilePath, remoteFilePath)
                print("Terminada la transferencia del archivo.")
                log_add(f"SFTP upload OK: {archivo} -> {remoteFilePath}")
                return True
            except Exception as e:
                print(f"  - Fallo al subir en {remoteFilePath}: {e}")
                ultimo_error = e
        
        print(f"Error en transferencia SFTP: {ultimo_error}")
        return False
        
    except paramiko.AuthenticationException:
        print(f"Error de autenticación SFTP: Usuario o contraseña incorrectos")
        return False
    except paramiko.SSHException as e:
        print(f"Error de conexión SSH: {e}")
        return False
    except Exception as e:
        print(f"Error en transferencia SFTP: {e}")
        return False
    finally:
        # Cerrar conexiones
        if 'sftp' in locals():
            sftp.close()
        if ssh:
            ssh.close()
    
    return

def formatear_valor_mysql(value):
    """
    Formatea un valor para MySQL manejando correctamente tipos especiales
    """
    import pandas as pd
    from datetime import datetime, date
    import numpy as np
    
    # Si es NaN o None, devolver NULL
    if pd.isna(value) or value is None:
        return 'NULL'
    
    # Si es un tipo datetime/timestamp
    if isinstance(value, (datetime, pd.Timestamp)):
        try:
            # Convertir a formato MySQL YYYY-MM-DD HH:MM:SS
            formatted_date = value.strftime('%Y-%m-%d %H:%M:%S')
            return f"'{formatted_date}'"
        except:
            return 'NULL'
    
    # Si es un tipo date
    if isinstance(value, date):
        try:
            # Convertir a formato MySQL YYYY-MM-DD
            formatted_date = value.strftime('%Y-%m-%d')
            return f"'{formatted_date}'"
        except:
            return 'NULL'
    
    # Si es un número (int, float, etc.)
    if isinstance(value, (int, float, np.integer, np.floating)):
        # Verificar si es NaN
        if pd.isna(value):
            return 'NULL'
        return str(value)
    
    # Si es boolean
    if isinstance(value, (bool, np.bool_)):
        return '1' if value else '0'
    
    # Para strings y otros tipos, convertir a string y escapar
    try:
        value_str = str(value)
        
        # Solo intentar conversión de fecha si es muy probable que sea una fecha
        # Verificar que tiene exactamente 3 partes numéricas separadas por /
        if '/' in value_str and len(value_str.split('/')) == 3:
            parts = value_str.split('/')
            # Solo procesar como fecha si TODAS las partes son números
            try:
                month_int = int(parts[0])
                day_int = int(parts[1])
                year_int = int(parts[2])
                
                # Validar que sean rangos razonables para fechas
                if (1 <= month_int <= 12 and 
                    1 <= day_int <= 31 and 
                    (year_int >= 0 and year_int <= 99) or (year_int >= 1900 and year_int <= 2099)):
                    
                    # Interpretar como MM/DD/YY
                    month, day, year = parts
                    
                    # Si el año es de 2 dígitos, assumir 20XX para años 00-30, 19XX para 31-99
                    if len(year) == 2:
                        year_int = int(year)
                        if year_int <= 30:
                            year = f"20{year}"
                        else:
                            year = f"19{year}"
                    elif len(year) == 1:
                        # Si es un solo dígito, assumir 200X
                        year = f"200{year}"
                    
                    # Crear fecha en formato MySQL
                    formatted_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    return f"'{formatted_date}'"
            except (ValueError, IndexError):
                # Si falla la conversión a números, tratar como string normal
                pass
        
        # Escapar caracteres especiales para MySQL
        value_str = value_str.replace('\\', '\\\\').replace('\'', '\\\'').replace('\"', '\\\"')
        return f"'{value_str}'"
        
    except:
        return 'NULL'

def generar_clave_fila(tabla_info, row):
    """Genera una clave única para una fila basada en sus índices (excluyendo TRZ)"""
    indices = tabla_info["indices"]
    if not indices:
        # Si no hay índices definidos, usar todas las columnas excepto las TRZ
        filtered_values = []
        for col in row.index:
            if not col.upper().startswith('TRZ'):
                filtered_values.append(row[col])
        return str(hash(tuple(filtered_values)))
    
    key_parts = []
    for indice in indices:
        # Excluir índices que empiecen por 'TRZ' (aunque es poco probable)
        if indice.upper().startswith('TRZ'):
            continue
            
        if indice in row.index:
            key_parts.append(str(row[indice]) if pd.notna(row[indice]) else 'NULL')
    return '|'.join(key_parts)

def analizar_cambios_tabla(tabla_info, df_actual, estado_anterior):
    """Analiza los cambios en una tabla comparando con el estado anterior"""
    tabla_nombre = tabla_info["tabla"]
    
    # Estado anterior de esta tabla
    tabla_estado_anterior = estado_anterior.get(tabla_nombre, {})
    hashes_anteriores = tabla_estado_anterior.get('hashes', {})
    
    # Calcular estado actual
    hashes_actuales = {}
    filas_nuevas = []
    filas_modificadas = []
    filas_eliminadas = set(hashes_anteriores.keys())
    
    print(f"Analizando tabla {tabla_nombre}: {len(df_actual)} filas actuales, {len(hashes_anteriores)} filas anteriores")
    
    for index, row in df_actual.iterrows():
        # Generar clave única para la fila
        clave_fila = generar_clave_fila(tabla_info, row)
        
        # Calcular hash de la fila actual
        hash_actual = calcular_hash_fila(row)
        hashes_actuales[clave_fila] = hash_actual
        
        # Verificar si la fila existe en el estado anterior
        if clave_fila in hashes_anteriores:
            filas_eliminadas.discard(clave_fila)  # La fila no fue eliminada
            
            # Verificar si fue modificada
            if hashes_anteriores[clave_fila] != hash_actual:
                filas_modificadas.append((clave_fila, row))
        else:
            # Es una fila nueva
            filas_nuevas.append((clave_fila, row))
    
    return {
        'hashes_actuales': hashes_actuales,
        'filas_nuevas': filas_nuevas,
        'filas_modificadas': filas_modificadas,
        'filas_eliminadas': list(filas_eliminadas),
        'total_filas': len(df_actual)
    }

def generar_sql_insert_update(tabla_info, fila, es_update=False):
    """Genera SQL para INSERT o UPDATE de una fila"""
    tabla_nombre = tabla_info["tabla"]
    dest_table = f"{config.TABLE_PREFIX}{tabla_nombre}"
    clave_fila, row = fila
    
    # Preparar columnas y valores excluyendo campos que empiecen por 'TRZ'
    columns = []
    values = []
    
    for col in row.index:
        # Excluir columnas que empiecen por 'TRZ'
        if col.upper().startswith('TRZ'):
            continue
            
        columns.append(f"`{col}`")
        value = row[col]
        if pd.notna(value):
            # Formatear según el tipo de dato
            formatted_value = formatear_valor_mysql(value)
            values.append(formatted_value)
        else:
            values.append('NULL')
    
    if es_update:
        # Para UPDATE, generar un UPDATE tradicional con WHERE basado en los índices
        indices = tabla_info["indices"]
        where_conditions = []
        
        if indices:
            for indice in indices:
                # También excluir índices que empiecen por 'TRZ' (aunque es poco probable)
                if indice.upper().startswith('TRZ'):
                    continue
                    
                if indice in row.index:
                    value = row[indice]
                    if pd.notna(value):
                        formatted_value = formatear_valor_mysql(value)
                        where_conditions.append(f"`{indice}` = {formatted_value}")
                    else:
                        where_conditions.append(f"`{indice}` IS NULL")
        
        if where_conditions:
            # Generar UPDATE tradicional que actualiza el registro existente
            update_parts = []
            for col, val in zip(columns, values):
                update_parts.append(f"{col} = {val}")
            
            where_clause = ' AND '.join(where_conditions)
            sql = f"UPDATE `{dest_table}` SET {', '.join(update_parts)} WHERE {where_clause};\n"
        else:
            # Sin índices definidos, no se puede hacer UPDATE seguro
            # Generar comentario de advertencia
            columns_str = ', '.join(columns)
            values_str = ', '.join(values)
            sql = f"-- ADVERTENCIA: No se puede generar UPDATE sin índices definidos para tabla {tabla_nombre}\n"
            sql += f"INSERT INTO `{dest_table}` ({columns_str}) VALUES ({values_str});\n"
    else:
        # INSERT normal
        columns_str = ', '.join(columns)
        values_str = ', '.join(values)
        sql = f"INSERT INTO `{dest_table}` ({columns_str}) VALUES ({values_str});\n"
    
    return sql

def generar_sql_delete(tabla_info, clave_fila, estado_anterior):
    """Genera SQL para DELETE de una fila eliminada"""
    tabla_nombre = tabla_info["tabla"]
    dest_table = f"{config.TABLE_PREFIX}{tabla_nombre}"
    indices = tabla_info["indices"]
    
    if not indices:
        # Sin índices, no podemos generar DELETE seguro
        return f"-- No se puede eliminar fila sin índices definidos: {clave_fila}\n"
    
    # Reconstruir la condición WHERE desde la clave
    where_conditions = []
    clave_parts = clave_fila.split('|')
    
    if len(clave_parts) == len(indices):
        for indice, valor in zip(indices, clave_parts):
            if valor == 'NULL':
                where_conditions.append(f"`{indice}` IS NULL")
            else:
                valor_escaped = valor.replace('\\', '\\\\').replace('\'', '\\\'').replace('\"', '\\\"')
                where_conditions.append(f"`{indice}` = '{valor_escaped}'")
        
        if where_conditions:
            sql = f"DELETE FROM `{dest_table}` WHERE {' AND '.join(where_conditions)};\n"
            return sql
    
    return f"-- No se pudo generar DELETE para: {clave_fila}\n"

def ejecutar_transferencia_incremental():
    """Ejecuta la transferencia incremental optimizada"""
    print('Inicio de la conversión incremental...')
    log_add("#################################################################")
    log_add("Iniciada conversión INCREMENTAL de Factusol a MySql del servidor web.")
    tiempo_inicio = time.time()

    # Cargar estado anterior
    estado_anterior = cargar_estado_sincronizacion()
    estado_nuevo = {}

    # Suprimir la advertencia específica de pandas sobre DBAPI2
    warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy connectable")

    total_cambios = 0
    total_nuevas = 0
    total_modificadas = 0
    total_eliminadas = 0
    errores_generacion = 0
    tablas_con_error = []

    # Usar la conexión directa con pyodbc
    try:
        # Determinar si es una sincronización completa (sin estado anterior)
        es_sincronizacion_completa = len(estado_anterior) == 0
        # La copia local ya fue validada por el monitor; evitar el DSN de Windows.
        connection_string = access_connection_string(config.LOCAL_ACCDB_PATH)
        connection = None
        try:
            connection = pyodbc.connect(connection_string, timeout=30)
        except pyodbc.Error as e:
            print("\n❌ Error al conectar con Access (ODBC).")
            print(f"   Copia local: {config.LOCAL_ACCDB_PATH}")
            print(f"   Detalle ODBC: {e}")
            log_add(f"Error ODBC al conectar con la copia local={config.LOCAL_ACCDB_PATH}. Error={e}")
            return False
        else:
            print("\n" + "=" * 70)
            print("GENERANDO ARCHIVO SQL INCREMENTAL")
            print("=" * 70)
        
        print(f"\nAnalizando {len(config.TABLAS)} tablas...\n")
        
        # Crear un archivo SQL para escribir las instrucciones
        sql_output_path = os.path.join(config.PATH_MAIN, config.SQL_FILE_PATH)
        with open(sql_output_path, 'w', encoding='utf-8') as f:
            f.write(
                config.SQL_CABECERA.format(
                    timestamp=datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
                    mysql_host=config.DB_HOST_MYSQL,
                    mysql_db=config.DB_NAME_MYSQL,
                )
            )
            
            for idx, tabla in enumerate(config.TABLAS, 1):
                tabla_nombre = tabla['tabla']
                print(f"[{idx}/{len(config.TABLAS)}] Procesando {tabla_nombre}...", end=" ")
                
                try:
                    # Leer tabla de MDB a DataFrame
                    df = pd.read_sql(f"SELECT * FROM {tabla_nombre}", connection)
                
                    # Analizar cambios
                    analisis = analizar_cambios_tabla(tabla, df, estado_anterior)
                    
                    # Guardar estado nuevo
                    estado_nuevo[tabla_nombre] = {
                        'hashes': analisis['hashes_actuales'],
                        'total_filas': analisis['total_filas'],
                        'ultima_actualizacion': datetime.now().isoformat()
                    }
                    
                    # Contar cambios
                    num_nuevas = len(analisis['filas_nuevas'])
                    num_modificadas = len(analisis['filas_modificadas'])
                    num_eliminadas = len(analisis['filas_eliminadas'])
                    
                    total_nuevas += num_nuevas
                    total_modificadas += num_modificadas
                    total_eliminadas += num_eliminadas
                    
                    cambios_tabla = num_nuevas + num_modificadas + num_eliminadas
                    total_cambios += cambios_tabla
                    
                    if cambios_tabla > 0:
                        # Si es sincronización completa, truncar SOLO esta tabla antes de insertar
                        if es_sincronizacion_completa:
                            dest_table = f"{config.TABLE_PREFIX}{tabla_nombre}"
                            f.write(f"\n\n-- ================================================================\n")
                            f.write(f"-- Tabla {tabla_nombre}: Truncando y recargando ({num_nuevas} registros)\n")
                            f.write(f"-- ================================================================\n")
                            f.write(f"TRUNCATE TABLE `{dest_table}`;\n\n")
                        else:
                            # Sincronización incremental normal
                            f.write(f"\n\n-- Tabla {tabla_nombre}: {num_nuevas} nuevas, {num_modificadas} modificadas, {num_eliminadas} eliminadas\n")
                        
                        # Procesar filas eliminadas (solo en modo incremental)
                        if not es_sincronizacion_completa:
                            for clave_fila in analisis['filas_eliminadas']:
                                sql_delete = generar_sql_delete(tabla, clave_fila, estado_anterior)
                                f.write(sql_delete)
                        
                        # Procesar filas nuevas
                        for fila in analisis['filas_nuevas']:
                            sql_insert = generar_sql_insert_update(tabla, fila, es_update=False)
                            f.write(sql_insert)
                        
                        # Procesar filas modificadas (solo en modo incremental)
                        if not es_sincronizacion_completa:
                            for fila in analisis['filas_modificadas']:
                                sql_update = generar_sql_insert_update(tabla, fila, es_update=True)
                                f.write(sql_update)
                        
                        print(f"✓ {cambios_tabla:,} cambios (+{num_nuevas} ~{num_modificadas} -{num_eliminadas})")
                        log_add(f"Tabla {tabla_nombre}: {num_nuevas} nuevas, {num_modificadas} modificadas, {num_eliminadas} eliminadas")
                    else:
                        print("✓ Sin cambios")
                
                except Exception as e:
                    errores_generacion += 1
                    tablas_con_error.append(tabla_nombre)
                    print(f"✗ ERROR: {e}")
                    log_add(f"Error en tabla {tabla_nombre}: {str(e)}")
                    
                    # En modo force-full, abortar si hay errores
                    if es_sincronizacion_completa:
                        print("\n" + "!" * 70)
                        print("❌ ABORTANDO: Error durante sincronización completa")
                        print(f"   Tabla con error: {tabla_nombre}")
                        print(f"   Error: {str(e)}")
                        print("   No se truncará ninguna tabla para evitar pérdida de datos")
                        print("!" * 70)
                        log_add(f"SINCRONIZACION ABORTADA: Error en {tabla_nombre}")
                        raise Exception(f"Sincronización completa abortada por error en tabla {tabla_nombre}")
            
            f.write(config.SQL_FIN)

        # Resumen de generación
        print("\n" + "-" * 70)
        print("RESUMEN DE GENERACIÓN:")
        print(f"  • Total de cambios: {total_cambios:,}")
        print(f"  • Nuevas: {total_nuevas:,}")
        print(f"  • Modificadas: {total_modificadas:,}")
        print(f"  • Eliminadas: {total_eliminadas:,}")
        
        if errores_generacion > 0:
            print(f"  • ❌ Errores: {errores_generacion}")
            print(f"  • Tablas con error: {', '.join(tablas_con_error)}")
            if es_sincronizacion_completa:
                print(f"  • ⚠️  SINCRONIZACIÓN ABORTADA - No se actualizará el servidor")
        else:
            print(f"  • ✓ Errores: 0")

        print("-" * 70)
    
    finally:
        # Cerrar la conexión a Access
        if connection is not None:
            connection.close()
            print("Conexión a Access cerrada.")

    # Si hubo errores en sincronización completa, no guardar estado ni continuar
    if es_sincronizacion_completa and errores_generacion > 0:
        print("\n❌ No se guardará el estado ni se subirá al servidor debido a errores")
        log_add(f"Sincronización abortada: {errores_generacion} errores en tablas: {', '.join(tablas_con_error)}")
        return False
    
    # Guardar nuevo estado solo si no hubo errores críticos
    guardar_estado_sincronizacion(estado_nuevo)

    if total_cambios > 0:
        log_add(f"Creado el archivo 'tablas_aim_incremental.sql' con {total_cambios} cambios")
        
        # exportar sftp solo si hay cambios
        print("\n" + "=" * 70)
        print("EXPORTANDO ARCHIVO AL SERVIDOR VIA SFTP")
        print("=" * 70)
        print(f"\nArchivo: {config.SQL_FILE_PATH}")
        print(f"Destino: {config.FTP_HOST}\n")
        
        log_add("Iniciada la exportación SFTP del archivo 'tablas_aim_incremental.sql'.")
        
        if export_sftp(config.SQL_FILE_PATH):
            print("\n✓ Exportación SFTP completada exitosamente")
            log_add("Finalizada la exportación SFTP con éxito.")
        else:
            print("\n⚠️  Error en transferencia SFTP")
            print("Continuando con actualización web directa...")
            log_add("Error en la exportación SFTP. Continuando con actualización web...")
        
        # Ejecuta una actualización de la base de datos en el servidor
        print("\n" + "=" * 70)
        print("ACTUALIZANDO BASE DE DATOS EN SERVIDOR")
        print("=" * 70)
        
        log_add("Iniciada la actualización de MySql en servidor.")
        
        # Generar código de autorización
        print("\n1. Generando código de autorización...")
        sal = bcrypt.gensalt()
        hash_pass = bcrypt.hashpw(config.PALABRA_CLAVE.encode('utf-8'), sal)
        hash_str = hash_pass.decode()
        print(f"   ✓ Código generado: {hash_str[:40]}...")
        
        # Convertir HTTPS a HTTP para evitar problemas SSL
        url_base = config.URL_IONOS
        if url_base.startswith('https://'):
            url_base = url_base.replace('https://', 'http://')
            log_add("Convertido HTTPS a HTTP para evitar problemas SSL")
        
        url_ionos = url_base + "?code=" + urllib.parse.quote(hash_str)
        
        print(f"\n2. Conectando al servidor...")
        print(f"   URL: {url_base}")
        
        try:
            print(f"\n3. Enviando petición (timeout: 600 segundos)...")
            inicio_actualizacion = time.time()
            
            # Timeout de 10 minutos (600 segundos) para permitir procesamiento completo
            r = requests.get(url_ionos, timeout=600, stream=True)
            
            print(f"   ✓ Respuesta recibida (Código HTTP: {r.status_code})")
            
            if r.status_code == 200:
                print(f"\n4. Respuesta del servidor:")
                print("-" * 70)
                
                # Leer respuesta línea por línea para ver progreso en tiempo real
                for line in r.iter_lines(decode_unicode=True):
                    if line:
                        print(line)
                        # Solo registrar líneas importantes en el log
                        if any(palabra in line for palabra in ['Procesando', 'Checkpoint', 'completada', 'Error', 'error']):
                            log_add(f"Servidor: {line}")
                
                print("-" * 70)
                
                tiempo_actualizacion = time.time() - inicio_actualizacion
                print(f"\n5. Resultado:")
                print(f"   ✓ Actualización completada en {tiempo_actualizacion:.2f}s")
                log_add(f"Actualización del servidor completada en {tiempo_actualizacion:.2f}s")
            else:
                print(f"\n⚠️  Código HTTP inesperado: {r.status_code}")
                respuesta = r.text
                print(f"Respuesta: {respuesta}")
                log_add(f"Error HTTP {r.status_code}: {respuesta}")
            
            r.close()
            
        except requests.exceptions.Timeout:
            tiempo_transcurrido = time.time() - inicio_actualizacion
            print(f"\n⚠️  TIMEOUT después de {tiempo_transcurrido:.2f}s")
            print("   El servidor puede estar procesando aún.")
            print("   Verifica el log del servidor para confirmar el estado.")
            log_add(f"Timeout en petición HTTP después de {tiempo_transcurrido:.2f}s")
            
        except requests.exceptions.RequestException as e:
            print(f"\n❌ ERROR DE RED: {e}")
            log_add(f"Error en petición HTTP: {e}")
            
        except Exception as e:
            print(f"\n❌ ERROR INESPERADO: {e}")
            log_add(f"Error inesperado durante actualización: {e}")
    else:
        print("\n" + "=" * 70)
        print("SIN CAMBIOS PARA SINCRONIZAR")
        print("=" * 70)
        print("\nNo hay cambios nuevos desde la última sincronización.")
        log_add("No hay cambios que sincronizar.")

    # Resumen final
    tiempo = time.time() - tiempo_inicio
    tm = int(tiempo / 60)
    ts = int(tiempo - tm * 60)
    ti = '{:0>2}:{:0>2}'.format(tm, ts)
    
    print("\n" + "=" * 70)
    if errores_generacion > 0 and es_sincronizacion_completa:
        print("PROCESO ABORTADO POR ERRORES")
    else:
        print("PROCESO DE SINCRONIZACIÓN COMPLETADO")
    print("=" * 70)
    print(f"\nTiempo total: {ti} (minutos:segundos)")
    if total_cambios > 0:
        print(f"Cambios procesados: {total_cambios:,}")
    if errores_generacion > 0:
        print(f"⚠️  Errores encontrados: {errores_generacion}")
        print(f"   Tablas afectadas: {', '.join(tablas_con_error)}")
    print("\n" + "=" * 70 + "\n")
    
    if errores_generacion > 0 and es_sincronizacion_completa:
        log_add(f"Proceso ABORTADO - {errores_generacion} errores en tablas: {', '.join(tablas_con_error)}")
    else:
        log_add("Finalizada la copia incremental de base de datos Factusol a la WEB.")
    log_add(f"Tiempo empleado: {ti}")
    log_add("################################################################# \n")
    
    # Retornar True solo si fue exitoso
    return True

def forzar_sincronizacion_completa():
    """Fuerza una sincronización completa eliminando el estado anterior"""
    estado_path = os.path.join(config.PATH_MAIN, config.ESTADO_FILE_PATH)
    if os.path.exists(estado_path):
        os.remove(estado_path)
        print("\n" + "=" * 70)
        print("FORZAR SINCRONIZACION COMPLETA ACTIVADO")
        print("=" * 70)
        print("\n✓ Estado de sincronización eliminado.")
        print("✓ Se generarán instrucciones TRUNCATE TABLE para todas las tablas.")
        print("✓ Se insertarán todos los datos desde cero.\n")
        log_add("Forzada sincronización completa - Estado anterior eliminado - Se truncarán tablas")
    else:
        print("\n" + "=" * 70)
        print("SINCRONIZACION COMPLETA (PRIMERA VEZ)")
        print("=" * 70)
        print("\n✓ No existe estado anterior.")
        print("✓ Se generarán instrucciones TRUNCATE TABLE para todas las tablas.")
        print("✓ Se insertarán todos los datos desde cero.\n")
        log_add("Primera sincronización completa - No existe estado anterior")

if __name__ == "__main__":
    import sys

    configurar_salida_unicode()
    
    # Verificar argumentos de línea de comandos
    # Aceptar cualquiera de: "--force-full", "force-full" o "-- force-full" (por robustez)
    es_force_full = any(arg == "--force-full" or arg == "force-full" for arg in sys.argv[1:])
    
    if es_force_full:
        forzar_sincronizacion_completa()
    
    # Configuración de reintentos (solo para force-full)
    MAX_INTENTOS = 5
    TIEMPO_ESPERA = 300  # 5 minutos en segundos
    intento_actual = 1
    
    # El monitor autonomo valida y actualiza la unica copia local antes de llamar
    # al incremental. Este proceso nunca accede a la copia temporal de origen.
    resultado = verificar_copia_local()
    if not resultado:
        print("No se pudo validar la copia local de Access.")
        log_add("No se pudo validar la copia local de Access.")
        sys.exit(1)
    
    # Bucle de reintentos (solo para force-full)
    while intento_actual <= MAX_INTENTOS:
        if intento_actual > 1:
            print("\n" + "=" * 70)
            print(f"REINTENTO {intento_actual}/{MAX_INTENTOS}")
            print("=" * 70)
            log_add(f"Iniciando reintento {intento_actual}/{MAX_INTENTOS}")
        
        # Ejecutar sincronización
        try:
            resultado_sincronizacion = ejecutar_transferencia_incremental()
        except Exception as e:
            print(f"\n❌ ERROR INESPERADO EN SINCRONIZACIÓN: {e}")
            log_add(f"Error inesperado no controlado: {e}")
            log_add("################################################################# \n")
            resultado_sincronizacion = False
        
        # Si fue exitoso, terminar
        if resultado_sincronizacion is not False:
            print("\n" + "=" * 70)
            print("✅ PROCESO COMPLETADO EXITOSAMENTE")
            print("=" * 70)
            if intento_actual > 1:
                print(f"\n✓ Completado en el intento {intento_actual}/{MAX_INTENTOS}")
                log_add(f"Sincronización exitosa en el intento {intento_actual}/{MAX_INTENTOS}")
            sys.exit(0)
        
        # Si falló y NO es force-full, salir inmediatamente
        if not es_force_full:
            print("\n" + "!" * 70)
            print("PROCESO FINALIZADO CON ERRORES")
            print("!" * 70)
            print(f"\nRevisa el log para más detalles: {config.LOG_ARCHIVO}")
            sys.exit(1)
        
        # Si es force-full y aún hay intentos disponibles
        if intento_actual < MAX_INTENTOS:
            print("\n" + "⏳" * 35)
            print(f"ESPERANDO {TIEMPO_ESPERA//60} MINUTOS ANTES DE REINTENTAR")
            print("⏳" * 35)
            print(f"\nIntento {intento_actual}/{MAX_INTENTOS} falló.")
            print(f"Esperando {TIEMPO_ESPERA//60} minutos para que el sistema libere recursos...")
            print("(Puedes cancelar con Ctrl+C si deseas corregir manualmente)")
            
            log_add(f"Intento {intento_actual}/{MAX_INTENTOS} falló. Esperando {TIEMPO_ESPERA}s antes de reintentar.")
            
            try:
                # Mostrar cuenta regresiva
                for segundos_restantes in range(TIEMPO_ESPERA, 0, -30):
                    minutos = segundos_restantes // 60
                    segundos = segundos_restantes % 60
                    print(f"\r⏱️  Tiempo restante: {minutos:02d}:{segundos:02d} ", end="", flush=True)
                    time.sleep(30)
                
                print("\r✓ Tiempo de espera completado. Reintentando...                    ")
                intento_actual += 1
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Reintentos cancelados por el usuario.")
                log_add("Reintentos cancelados por el usuario")
                sys.exit(1)
        else:
            # Se agotaron los intentos
            print("\n" + "!" * 70)
            print("❌ PROCESO FINALIZADO CON ERRORES")
            print("!" * 70)
            print(f"\nSe agotaron los {MAX_INTENTOS} intentos.")
            print(f"Revisa el log para más detalles: {config.LOG_ARCHIVO}")
            print("\nPosibles causas:")
            print("  • Memoria insuficiente en el sistema")
            print("  • Problema de conexión con Access")
            print("  • Datos corruptos en alguna tabla")
            print("\nSugerencias:")
            print("  • Cierra otras aplicaciones para liberar memoria")
            print("  • Verifica que nadie esté usando la base de datos Access")
            print("  • Revisa el log para identificar qué tabla falla consistentemente")
            
            log_add(f"FALLO DEFINITIVO después de {MAX_INTENTOS} intentos")
            sys.exit(1)
