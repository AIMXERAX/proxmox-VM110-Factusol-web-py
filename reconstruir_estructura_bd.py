"""
Sistema de Reconstrucción de Estructura de Base de Datos
=========================================================

Este script realiza una reconstrucción completa de la estructura de las tablas
MySQL cuando hay cambios en la estructura de las tablas de Access.

PROCESO:
1. Genera SQL con estructura actualizada de las tablas (DROP + CREATE)
2. Sube el archivo al servidor via SFTP
3. Ejecuta el PHP de reconstrucción de estructura
4. Ejecuta sincronización completa de datos (--force-full)

USO:
    python reconstruir_estructura_bd.py

CUÁNDO USAR:
- Cuando Access agregó/eliminó/modificó columnas
- Cuando hay errores de "columna no existe" en MySQL
- Cuando los tipos de datos cambiaron
- Como mantenimiento preventivo periódico

"""

from venv_bootstrap import ensure_venv
ensure_venv()

# Redirigir print al archivo de log del script
from service_logging import setup_print_log
setup_print_log(__file__)

import os
import sys
import time
import requests
import bcrypt
import urllib.parse
import subprocess
from datetime import datetime
import config

def log_add(mensaje):
    """Registra un mensaje en el log"""
    log_path = os.path.join(config.PATH_MAIN, config.LOG_ARCHIVO)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    timestamp = time.strftime("%d/%m/%y %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{timestamp}   {mensaje}\n")

def ejecutar_generar_tablas():
    """Ejecuta el script de generación de estructura SQL"""
    print("\n" + "=" * 80)
    print("PASO 1: GENERANDO SQL DE ESTRUCTURA DE TABLAS")
    print("=" * 80)
    
    script_path = os.path.join(config.PATH_MAIN, "generar_tablas_accdb.py")
    python_exe = os.path.join(config.PATH_MAIN, ".venv", "Scripts", "python.exe")
    
    try:
        # Ejecutar script de generación
        resultado = subprocess.run(
            [python_exe, script_path],
            capture_output=True,
            text=True,
            cwd=config.PATH_MAIN
        )
        
        print(resultado.stdout)
        if resultado.stderr:
            print("Advertencias:", resultado.stderr)
        
        if resultado.returncode != 0:
            print(f"❌ Error al generar estructura SQL (código: {resultado.returncode})")
            log_add(f"Error al generar estructura SQL: {resultado.stderr}")
            return False
        
        # Verificar que se creó el archivo
        sql_file = os.path.join(config.PATH_MAIN, "inicio_tablas", f"iniciar_tablas_{config.ANIO}.sql")
        if not os.path.exists(sql_file):
            print(f"❌ No se encontró el archivo generado: {sql_file}")
            return False
        
        file_size = os.path.getsize(sql_file) / 1024  # KB
        print(f"\n✅ Archivo SQL de estructura generado correctamente")
        print(f"   Ubicación: {sql_file}")
        print(f"   Tamaño: {file_size:.2f} KB")
        log_add(f"Generado SQL de estructura: iniciar_tablas_{config.ANIO}.sql ({file_size:.2f} KB)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al ejecutar generación de estructura: {e}")
        log_add(f"Error al ejecutar generar_tablas_accdb.py: {e}")
        return False

def subir_estructura_sftp():
    """Sube el archivo SQL de estructura al servidor"""
    def rutas_candidatas(nombre):
        return [f"/{nombre}", nombre]

    def rutas_candidatas_php(nombre):
        return [f"/php/{nombre}", f"php/{nombre}"]

    print("\n" + "=" * 80)
    print("PASO 2: SUBIENDO SQL DE ESTRUCTURA AL SERVIDOR (SFTP)")
    print("=" * 80)
    
    import paramiko
    
    sql_file_name = f"iniciar_tablas_{config.ANIO}.sql"
    local_path = os.path.join(config.PATH_MAIN, "inicio_tablas", sql_file_name)
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Conectando a {config.FTP_HOST}...")
        ssh.connect(
            hostname=config.FTP_HOST,
            username=config.FTP_USER,
            password=config.FTP_PASSWORD,
            timeout=30
        )
        
        sftp = ssh.open_sftp()
        print("✅ Conexión SFTP establecida")
        
        print(f"Archivo a subir: {sql_file_name}")
        print(f"Transfiriendo archivo principal...")

        remote_path_root_ok = None
        ultimo_error = None
        for remote_path_root in rutas_candidatas(sql_file_name):
            remote_dir_root = os.path.dirname(remote_path_root).replace('\\', '/') or '.'
            print(f"Intentando ruta principal: {remote_path_root}")
            try:
                sftp.stat(remote_dir_root)
            except Exception as e:
                print(f"  - Directorio no accesible: {remote_dir_root} ({e})")
                ultimo_error = e
                continue

            try:
                sftp.put(local_path, remote_path_root)
                remote_path_root_ok = remote_path_root
                break
            except Exception as e:
                print(f"  - Fallo al subir en {remote_path_root}: {e}")
                ultimo_error = e

        if not remote_path_root_ok:
            raise Exception(f"No se pudo subir el archivo principal. Último error: {ultimo_error}")

        # Compatibilidad: si los scripts PHP están en /php, también dejar copia allí
        try:
            for remote_path_php in rutas_candidatas_php(sql_file_name):
                remote_dir_php = os.path.dirname(remote_path_php).replace('\\', '/') or '.'
                try:
                    sftp.stat(remote_dir_php)
                    sftp.put(local_path, remote_path_php)
                    print(f"✅ Copia adicional: {remote_path_php}")
                    break
                except Exception:
                    continue
        except Exception:
            # No todos los hostings exponen /php por SFTP, no bloquear el proceso.
            print("⚠️  No se pudo copiar en /php (continuando con la copia en raíz)")
        
        print(f"✅ Archivo subido correctamente: {sql_file_name}")
        log_add(f"SFTP upload estructura OK: {sql_file_name} -> {remote_path_root_ok}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en transferencia SFTP: {e}")
        log_add(f"Error SFTP al subir estructura: {e}")
        return False
        
    finally:
        if 'sftp' in locals():
            sftp.close()
        if ssh:
            ssh.close()

def ejecutar_reconstruccion_servidor():
    """Ejecuta el script PHP de reconstrucción en el servidor"""
    print("\n" + "=" * 80)
    print("PASO 3: EJECUTANDO RECONSTRUCCIÓN DE ESTRUCTURA EN SERVIDOR")
    print("=" * 80)
    print("\n⚠️  ADVERTENCIA: Este proceso DROP y CREATE todas las tablas")
    print("   Los datos actuales se perderán (se recargarán en el paso 4)")
    
    # Generar código de autorización
    print("\nGenerando código de autorización...")
    sal = bcrypt.gensalt()
    hash_pass = bcrypt.hashpw(config.PALABRA_CLAVE.encode('utf-8'), sal)
    hash_str = hash_pass.decode()
    
    # URL del PHP de reconstrucción (con fallback sin tocar scripts PHP)
    url_base = config.URL_IONOS.replace('actualizar_bd_incremental.php', 'reconstruir_estructura.php')
    if url_base.startswith('https://'):
        url_base = url_base.replace('https://', 'http://')

    urls_a_probar = [url_base]
    if '/php/' not in url_base:
        alt = url_base.replace('/reconstruir_estructura.php', '/php/reconstruir_estructura.php')
        if alt != url_base:
            urls_a_probar.append(alt)

    print(f"Conectando al servidor...")
    print(f"URL principal: {url_base}")

    try:
        print(f"\nEnviando petición (timeout: 600 segundos)...")
        inicio = time.time()
        r = None
        url_completa = None
        for url_intento in urls_a_probar:
            url_completa = url_intento + "?code=" + urllib.parse.quote(hash_str)
            print(f"Probando: {url_intento}")
            r = requests.get(url_completa, timeout=600, stream=True)
            if r.status_code == 200:
                break
            print(f"⚠️  HTTP {r.status_code} en {url_intento}")
        
        print(f"✅ Respuesta recibida (HTTP {r.status_code})")
        
        if r.status_code == 200:
            print("\n" + "-" * 80)
            print("RESPUESTA DEL SERVIDOR:")
            print("-" * 80)
            hay_error_servidor = False
            
            for line in r.iter_lines(decode_unicode=True):
                if line:
                    print(line)
                    if any(palabra in line for palabra in ['Error crítico', 'Error interno', 'Error en reconstrucción', 'No se encontró archivo de estructura']):
                        hay_error_servidor = True
                    if any(palabra in line for palabra in ['ERROR', 'Error', 'error', 'completada', 'Completada']):
                        log_add(f"Servidor: {line}")
            
            print("-" * 80)
            
            tiempo_total = time.time() - inicio
            if hay_error_servidor:
                print(f"\n❌ La reconstrucción devolvió errores en {tiempo_total:.2f}s")
                log_add(f"Reconstrucción de estructura con errores en {tiempo_total:.2f}s")
                return False

            print(f"\n✅ Reconstrucción completada en {tiempo_total:.2f}s")
            log_add(f"Reconstrucción de estructura completada en {tiempo_total:.2f}s")
            return True
        else:
            print(f"❌ Error HTTP {r.status_code}")
            print(f"Respuesta: {r.text}")
            log_add(f"Error HTTP {r.status_code} en reconstrucción de estructura")
            return False
            
    except requests.exceptions.Timeout:
        tiempo_transcurrido = time.time() - inicio
        print(f"⚠️  TIMEOUT después de {tiempo_transcurrido:.2f}s")
        print("El servidor puede estar procesando aún. Verifica el log del servidor.")
        log_add(f"Timeout en reconstrucción de estructura después de {tiempo_transcurrido:.2f}s")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        log_add(f"Error en reconstrucción de estructura: {e}")
        return False

def ejecutar_carga_completa_datos():
    """Ejecuta la carga completa de datos usando --force-full"""
    print("\n" + "=" * 80)
    print("PASO 4: CARGANDO DATOS COMPLETOS")
    print("=" * 80)
    print("\nEjecutando sincronización completa con --force-full...")
    
    python_exe = os.path.join(config.PATH_MAIN, ".venv", "Scripts", "python.exe")
    script_path = os.path.join(config.PATH_MAIN, "aim_datos_accdb_incremental.py")
    
    try:
        # Ejecutar el script Python directamente con --force-full
        resultado = subprocess.run(
            [python_exe, script_path, "--force-full"],
            cwd=config.PATH_MAIN,
            capture_output=False,  # Mostrar output en tiempo real
            text=True
        )
        
        if resultado.returncode == 0:
            print("\n✅ Carga completa de datos finalizada")
            log_add("Carga completa de datos finalizada exitosamente")
            return True
        else:
            print(f"\n⚠️  Proceso terminó con código: {resultado.returncode}")
            log_add(f"Carga completa terminó con código: {resultado.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Error al ejecutar carga completa: {e}")
        log_add(f"Error en carga completa de datos: {e}")
        return False

def main():
    """Función principal"""
    print("\n" + "=" * 80)
    print("SISTEMA DE RECONSTRUCCIÓN DE ESTRUCTURA DE BASE DE DATOS")
    print("=" * 80)
    print(f"\nAño: {config.ANIO}")
    print(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("\n⚠️  PROCESO AUTOMATICO: Reconstruyendo estructura completa")
    print("   1. Generando SQL de estructura desde Access")
    print("   2. Subiendo al servidor via SFTP")
    print("   3. Ejecutando DROP + CREATE de todas las tablas")
    print("   4. Recargando todos los datos desde Access")
    print("\n" + "=" * 80)
    
    log_add("=" * 80)
    log_add("INICIADA RECONSTRUCCIÓN DE ESTRUCTURA DE BASE DE DATOS")
    log_add("=" * 80)
    
    tiempo_inicio = time.time()
    errores = []
    
    # Paso 1: Generar SQL de estructura
    if not ejecutar_generar_tablas():
        errores.append("Generación de SQL de estructura")
        print("\n❌ Error en Paso 1. Abortando proceso.")
        return
    
    time.sleep(2)  # Pausa entre pasos
    
    # Paso 2: Subir archivo al servidor
    if not subir_estructura_sftp():
        errores.append("Subida SFTP")
        print("\n❌ Error en Paso 2. Abortando proceso.")
        return
    
    time.sleep(2)
    
    # Paso 3: Ejecutar reconstrucción en servidor
    if not ejecutar_reconstruccion_servidor():
        errores.append("Reconstrucción en servidor")
        print("\n⚠️  Error en Paso 3. Las tablas pueden estar vacías.")
        print("   Continuando con Paso 4 para recargar datos...")
        # No abortamos, intentamos recargar datos de todas formas
    
    time.sleep(2)
    
    # Paso 4: Cargar datos completos
    if not ejecutar_carga_completa_datos():
        errores.append("Carga de datos")
        print("\n❌ Error en Paso 4.")
    
    # Resumen final
    tiempo_total = time.time() - tiempo_inicio
    minutos = int(tiempo_total / 60)
    segundos = int(tiempo_total % 60)
    
    print("\n" + "=" * 80)
    print("PROCESO DE RECONSTRUCCIÓN COMPLETADO")
    print("=" * 80)
    print(f"\nTiempo total: {minutos}m {segundos}s")
    
    if errores:
        print(f"\n⚠️  Se encontraron errores en los siguientes pasos:")
        for error in errores:
            print(f"   - {error}")
        log_add(f"Reconstrucción completada CON ERRORES: {', '.join(errores)}")
    else:
        print("\n✅ Todos los pasos completados exitosamente")
        print("   La estructura de las tablas ha sido actualizada")
        print("   Los datos han sido recargados completamente")
        log_add("Reconstrucción de estructura completada EXITOSAMENTE")
    
    print("\n" + "=" * 80)
    log_add(f"Tiempo total: {minutos}m {segundos}s")
    log_add("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Proceso interrumpido por el usuario")
        log_add("Proceso de reconstrucción interrumpido por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error crítico: {e}")
        log_add(f"Error crítico en reconstrucción: {e}")
        raise
