"""
Configuración del sistema Factusol-MySQL
========================================

Este archivo contiene las constantes y configuración no sensible del programa.
Las constantes sensibles (passwords, claves, etc.) se mantienen en el archivo .env
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Directorio base del proyecto (carpeta donde está este config.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==============================================
# CONFIGURACIÓN GENERAL DEL SISTEMA
# ==============================================

# Año del ejercicio de Factusol
ANIO = os.getenv('ANIO')

# Único modelo de operación: producción.
MODELO = (os.getenv('MODELO') or 'PROD').upper()
if MODELO != 'PROD':
    raise ValueError("MODELO debe ser 'PROD'.")
IP = os.getenv('IP_SERVIDOR_PROD') or '192.168.100.104'

# Directorios y archivos del sistema
PATH_MAIN = BASE_DIR
PROG_PY = f'"{os.path.join(PATH_MAIN, ".venv", "Scripts", "python.exe")}" '
LOG_ARCHIVO = os.path.join('logs', 'monitor.log')

# ==============================================
# BASE DE DATOS
# ==============================================

# DSN de sistema que apunta a la unica copia local mantenida por el servicio.
DSN_DB = (os.getenv('ACCESS_WEB_DSN') or 'aim{ANIO}web').replace('{ANIO}', ANIO or '')

# Datos de MySQL de producción para metadatos y trazabilidad en SQL.
DB_HOST_MYSQL = os.getenv('DB_HOST_PROD') or 'desconocido'
DB_NAME_MYSQL = os.getenv('DB_NAME_PROD') or 'desconocida'

# ==============================================
# ARCHIVOS DE CONFIGURACIÓN Y ESTADO
# ==============================================

SQL_FILE_PATH = 'tablas_aim_incremental.sql'
ESTADO_FILE_PATH = 'estado_sincronizacion.json'

# ==============================================
# RUTAS DE ARCHIVOS ACCESS
# ==============================================

# Copia temporal local mantenida por otra aplicacion. El servicio no accede a SMB.
ACCDB_SOURCE_PATH = (os.getenv('ACCDB_SOURCE_PATH') or r'C:\Python\bd_factusol\aim{ANIO}.accdb').replace(
    '{ANIO}', ANIO or ''
)
ACCDB_SOURCE_LOCK_PATH = os.path.splitext(ACCDB_SOURCE_PATH)[0] + '.laccdb'
LOCAL_ACCDB_DIRECTORY = os.getenv('ACCDB_LOCAL_DIRECTORY') or os.path.join(BASE_DIR, 'data')
LOCAL_ACCDB_PATH = os.path.join(LOCAL_ACCDB_DIRECTORY, f'AIM{ANIO}_web.accdb')

# Monitor autonomo: el servicio espera este tiempo sin cambios antes de copiar.
ACCDB_STABILITY_SECONDS = int(os.getenv('ACCDB_STABILITY_SECONDS') or '300')
ACCDB_CHECK_INTERVAL_SECONDS = int(os.getenv('ACCDB_CHECK_INTERVAL_SECONDS') or '60')
ACCDB_COPY_RETRY_SECONDS = int(os.getenv('ACCDB_COPY_RETRY_SECONDS') or '60')
ACCDB_MONITOR_STATE_FILE = 'estado_monitor_accdb.json'

# ==============================================
# CONFIGURACIÓN FTP/SFTP
# ==============================================

FTP_HOST_PROD = os.getenv('FTP_HOST_PROD')
FTP_USER_PROD = os.getenv('FTP_USER_PROD')
FTP_PASSWORD_PROD = os.getenv('FTP_PASSWORD_PROD')

# Credenciales FTP del modelo PROD.
FTP_HOST = FTP_HOST_PROD
FTP_USER = FTP_USER_PROD
FTP_PASSWORD = FTP_PASSWORD_PROD

# ==============================================
# AUTENTICACIÓN (solo referencia, valor real en .env)
# ==============================================

PALABRA_CLAVE = os.getenv('PALABRA_CLAVE')

# ==============================================
# URL DEL SERVIDOR
# ==============================================

URL_IONOS_PROD = os.getenv('URL_IONOS_PROD')
URL_IONOS = URL_IONOS_PROD

# ==============================================
# CONFIGURACIÓN DE TABLAS
# ==============================================

# Prefijo para las tablas en MySQL
TABLE_PREFIX = f'F{ANIO} '

# Definir las tablas y sus índices
TABLAS = [
    {"tabla": "F_ART", "indices": ["CODART"]},
    {"tabla": "F_PRO", "indices": ["CODPRO"]},
    {"tabla": "F_FAM", "indices": ["CODFAM"]},
    {"tabla": "F_TCL", "indices": ["CODTCL"]},
    {"tabla": "F_TAR", "indices": ["CODTAR"]},
    {"tabla": "F_STO", "indices": ["ARTSTO", "ALMSTO"]},
    {"tabla": "F_RUT", "indices": ["CODRUT"]},
    {"tabla": "F_PRE", "indices": ["TIPPRE", "CODPRE"]},
    {"tabla": "F_PPR", "indices": ["TIPPPR", "CODPPR"]},
    {"tabla": "F_PCL", "indices": ["TIPPCL", "CODPCL"]},
    {"tabla": "F_OBR", "indices": ["CLIOBR", "CODOBR"]},
    {"tabla": "F_LTA", "indices": ["TARLTA", "ARTLTA"]},
    {"tabla": "F_LRU", "indices": ["CODLRU", "POSLRU"]},
    {"tabla": "F_LPS", "indices": ["TIPLPS", "CODLPS", "POSLPS"]},
    {"tabla": "F_LPP", "indices": ["TIPLPP", "CODLPP", "POSLPP"]},
    {"tabla": "F_LPC", "indices": ["TIPLPC", "CODLPC", "POSLPC"]},
    {"tabla": "F_LPA", "indices": ["ARTLPA", "PROLPA"]},
    {"tabla": "F_LFR", "indices": ["TIPLFR", "CODLFR", "POSLFR"]},
    {"tabla": "F_LFD", "indices": ["TIPLFD", "CODLFD", "POSLFD"]},
    {"tabla": "F_LFB", "indices": ["TIPLFB", "CODLFB", "POSLFB"]},
    {"tabla": "F_LFA", "indices": ["TIPLFA", "CODLFA", "POSLFA"]},
    {"tabla": "F_LEN", "indices": ["TIPLEN", "CODLEN", "POSLEN"]},
    {"tabla": "F_LAL", "indices": ["TIPLAL", "CODLAL", "POSLAL"]},
    {"tabla": "F_FRE", "indices": ["TIPFRE", "CODFRE"]},
    {"tabla": "F_FRD", "indices": ["TIPFRD", "CODFRD"]},
    {"tabla": "F_FPA", "indices": ["CODFPA"]},
    {"tabla": "F_FAC", "indices": ["TIPFAC", "CODFAC"]},
    {"tabla": "F_FAB", "indices": ["TIPFAB", "CODFAB"]},
    {"tabla": "F_ENT", "indices": ["TIPENT", "CODENT"]},
    {"tabla": "F_EMP", "indices": ["CODEMP"]},
    {"tabla": "F_CNS", "indices": ["ALMCNS", "FECCNS", "ARTCNS", "NSECNS"]},
    {"tabla": "F_CLI", "indices": ["CODCLI"]},
    {"tabla": "F_CIN", "indices": ["ALMCIN", "ARTCIN", "CE1CIN", "CE2CIN", "FECCIN"]},
    {"tabla": "F_CGA", "indices": ["CODCGA"]},
    {"tabla": "F_BAN", "indices": ["CODBAN"]},
    {"tabla": "F_ALM", "indices": ["CODALM"]},
    {"tabla": "F_ALB", "indices": ["TIPALB", "CODALB"]},
    {"tabla": "F_AGE", "indices": ["CODAGE"]},
    {"tabla": "F_FTE", "indices": ["CODFTE"]},
    {"tabla": "F_SLA", "indices": ["TIPSLA", "CODSLA", "POSSLA", "NSESLA"]},
    {"tabla": "F_SLB", "indices": ["TIPSLB", "CODSLB", "POSSLB", "NSESLB"]},
    {"tabla": "F_SLD", "indices": ["TIPSLD", "CODSLD", "POSSLD", "NSESLD"]},
    {"tabla": "F_SLE", "indices": ["TIPSLE", "CODSLE", "POSSLE", "NSESLE"]},
    {"tabla": "F_SLF", "indices": ["TIPSLF", "CODSLF", "POSSLF", "NSESLF"]},
    {"tabla": "F_SLR", "indices": ["TIPSLR", "CODSLR", "POSSLR", "NSESLR"]}
]

# ==============================================
# PLANTILLAS SQL
# ==============================================

# Preparar cabecera del archivo SQL
SQL_CABECERA = """
-- phpMyAdmin SQL Dump - Actualización Incremental
-- version 4.9.7
-- https://www.phpmyadmin.net/
--
-- Servidor: {mysql_host}
-- Tiempo de generación: {timestamp}
-- Versión del servidor: 5.7.30-log
-- Versión de PHP: 7.0.33-0+deb9u10

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";

 /*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
 /*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
 /*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
 /*!40101 SET NAMES utf8mb4 */;

--
-- Base de datos: `{mysql_db}`
-- Actualización incremental de tablas
--

-- --------------------------------------------------------
"""

SQL_FIN = """
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
"""
