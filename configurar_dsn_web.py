"""Configura el DSN de sistema usado por la sincronizacion Factusol Web."""

from venv_bootstrap import ensure_venv

ensure_venv()

from service_logging import setup_print_log

setup_print_log(__file__)

import sys

import config
from access_odbc import configurar_dsn_web


def main() -> int:
    print(f"Configurando el DSN de sistema '{config.DSN_DB}'...")
    print(f"Base de datos Access: {config.LOCAL_ACCDB_PATH}")

    try:
        configurar_dsn_web()
    except Exception as error:
        print(f"ERROR: No se pudo configurar el DSN '{config.DSN_DB}'.")
        print(f"Detalle: {error}")
        return 1

    print(f"OK: DSN '{config.DSN_DB}' configurado correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
