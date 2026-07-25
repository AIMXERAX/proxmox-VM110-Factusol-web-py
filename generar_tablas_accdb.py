from venv_bootstrap import ensure_venv
ensure_venv()

# Redirigir print al archivo de log del script
from service_logging import setup_print_log
setup_print_log(__file__)

import os
import sys
import pandas as pd
import pyodbc
import warnings
import config
from access_odbc import access_connection_string

# Configuración de las rutas
anio = config.ANIO

# Definir las tablas y sus índices
tablas = [
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

cabecera = """
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO"; 
        SET AUTOCOMMIT = 0; 
        START TRANSACTION; 
        SET time_zone = "+00:00"; 
        
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */; 
        /*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */; 
        /*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */; 
        /*!40101 SET NAMES latin1 */; 
        
"""

fin = """
COMMIT; 
    
    /*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */; 
    /*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */; 
    /*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */; 

"""


# Obtiene el directorio de trabajo actual
current_dir = os.getcwd()
# Define la carpeta 'inicio_tablas' dentro del directorio actual
sql_subfolder = 'inicio_tablas'
sql_dir = os.path.join(current_dir, sql_subfolder)
sql_file_path = os.path.join(sql_dir, f'iniciar_tablas_{anio}.sql')
table_prefix = f'F{anio} '
sql_dir = os.path.dirname(sql_file_path)
if sql_dir and not os.path.exists(sql_dir):
    os.makedirs(sql_dir, exist_ok=True)
    print(f"Directorio creado: {sql_dir}")

if not os.path.exists(sql_file_path):
    with open(sql_file_path, 'w') as f:
        pass
    print(f"Archivo creado: {sql_file_path}")

# Suprimir la advertencia específica de pandas sobre DBAPI2
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy connectable")

# Crear conexión directa a la copia local de Access con pyodbc.
try:
    connection_string = access_connection_string(config.LOCAL_ACCDB_PATH)
    connection = pyodbc.connect(connection_string, timeout=30)
    print("Conexión a Access establecida correctamente.")
except Exception as e:
    print(f"Error al conectar a Access: {e}")
    sys.exit(1)

# Generar archivo SQL
try:
    with open(sql_file_path, 'w', encoding='utf-8') as f:
        f.write(cabecera)
        for tabla in tablas:
            table_name = tabla['tabla']
            dest_table = f"{table_prefix}{table_name}"
            indices_tabla = set(tabla['indices'])
            print(table_name)
            # Cargar la tabla desde Access
            query = f"SELECT * FROM {table_name}"
            df = pd.read_sql(query, connection)

            # Crear definición de tabla SQL
            f.write(f"DROP TABLE IF EXISTS `{dest_table}`;\n")
            f.write(f"CREATE TABLE `{dest_table}` (\n")

            column_definitions = []
            col_types = {}
            for col_name, dtype in zip(df.columns, df.dtypes):
                if "int" in str(dtype):
                    sql_type = "INT"
                elif "float" in str(dtype):
                    sql_type = "DECIMAL(15,2)"
                elif "datetime" in str(dtype):
                    sql_type = "DATE"
                elif df[col_name].dtype == "object":
                    # Usar TEXT evita que cambios en la longitud de Access
                    # obliguen a reconstruir el tipo VARCHAR generado.
                    sql_type = "TEXT"
                else:
                    # Caso genérico: fallback
                    sql_type = "TEXT"

                col_types[col_name] = sql_type
                column_definitions.append(f"    `{col_name}` {sql_type}")

            f.write(",\n".join(column_definitions))
            f.write("\n);\n")

            # Agregar índices
            for index in tabla['indices']:
                index_col_type = str(col_types.get(index, "")).upper()

                # MySQL requiere longitud de prefijo para índices sobre TEXT/BLOB.
                # Para columnas de texto largas usamos prefijo 191 (compatible con utf8mb4).
                if index_col_type.startswith("TEXT"):
                    f.write(f"CREATE INDEX `{index}` ON `{dest_table}` (`{index}`(191));\n")
                else:
                    f.write(f"CREATE INDEX `{index}` ON `{dest_table}` (`{index}`);\n")
        f.write(fin)        

    print(f"Archivo SQL generado en {sql_file_path} con éxito.")
except Exception as e:
    print(f"Error al generar el archivo SQL: {e}")
finally:
    # Cerrar la conexión a Access
    if 'connection' in locals():
        connection.close()
        print("Conexión a Access cerrada.")
