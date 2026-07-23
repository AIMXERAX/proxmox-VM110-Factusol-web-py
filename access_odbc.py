"""Configuracion y comprobaciones ODBC para la copia local de Access."""

from __future__ import annotations

import os

import pyodbc

import config


ACCESS_DRIVER_NAME = "Microsoft Access Driver (*.mdb, *.accdb)"


def access_connection_string(database_path: str) -> str:
    """Return a DSN-less connection string for an Access database."""
    return f"DRIVER={{{ACCESS_DRIVER_NAME}}};DBQ={database_path};"


def comprobar_base_access(database_path: str) -> None:
    """Open an Access database and execute a read-only health query."""
    with pyodbc.connect(access_connection_string(database_path), timeout=30) as connection:
        connection.execute("SELECT 1 AS conexion").fetchone()


def configurar_dsn_web() -> None:
    """Create or update the system DSN used by the synchronization service."""
    if os.name != "nt":
        raise RuntimeError("El DSN de Access solo puede configurarse en Windows.")
    if ACCESS_DRIVER_NAME not in pyodbc.drivers():
        raise RuntimeError(
            f"No esta instalado el controlador ODBC requerido: {ACCESS_DRIVER_NAME}."
        )

    import winreg

    driver_key = rf"SOFTWARE\ODBC\ODBCINST.INI\{ACCESS_DRIVER_NAME}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, driver_key) as key:
            driver_path = winreg.QueryValueEx(key, "Driver")[0]
    except FileNotFoundError as error:
        raise RuntimeError("No se pudo localizar el archivo del controlador ODBC de Access.") from error

    dsn_key = rf"SOFTWARE\ODBC\ODBC.INI\{config.DSN_DB}"
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, dsn_key, 0, winreg.KEY_WRITE) as key:
        winreg.SetValueEx(key, "DBQ", 0, winreg.REG_SZ, config.LOCAL_ACCDB_PATH)
        winreg.SetValueEx(key, "Driver", 0, winreg.REG_SZ, driver_path)
        winreg.SetValueEx(key, "Description", 0, winreg.REG_SZ, "Factusol Web local copy")
        winreg.SetValueEx(key, "FIL", 0, winreg.REG_SZ, "MS Access")

    sources_key = r"SOFTWARE\ODBC\ODBC.INI\ODBC Data Sources"
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, sources_key, 0, winreg.KEY_WRITE) as key:
        winreg.SetValueEx(key, config.DSN_DB, 0, winreg.REG_SZ, ACCESS_DRIVER_NAME)
