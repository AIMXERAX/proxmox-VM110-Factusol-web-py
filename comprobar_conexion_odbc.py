"""Comprueba la disponibilidad de la conexión ODBC a Factusol."""

from venv_bootstrap import ensure_venv

ensure_venv()

from service_logging import setup_print_log

setup_print_log(__file__)

import sys

import pyodbc

import config
from access_odbc import access_connection_string


def main() -> int:
    try:
        with pyodbc.connect(access_connection_string(config.LOCAL_ACCDB_PATH), timeout=30) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT 1 AS conexion")
            resultado = cursor.fetchone()
    except pyodbc.Error as error:
        print(f"ERROR: No se pudo conectar a la copia local '{config.LOCAL_ACCDB_PATH}'.")
        print(f"Detalle ODBC: {error}")
        return 1

    print(f"OK: Conexion ODBC disponible para la copia local '{config.LOCAL_ACCDB_PATH}'.")
    print(f"Consulta de prueba: {resultado[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
