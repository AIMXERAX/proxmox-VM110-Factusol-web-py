"""
Reusable service logging module.

Stores service events in logs/{servicio}.log and the SQLite database configured
by SERVICIOS_DB_PATH in the project .env file.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
import atexit
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DEFAULT_DB_PATH = BASE_DIR / "db" / "Servicios.db"
DB_PATH = Path(os.getenv("SERVICIOS_DB_PATH", str(DEFAULT_DB_PATH))).resolve()
DB_DIR = DB_PATH.parent
LOGS_DIR = BASE_DIR / "logs"

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
VALID_LEVELS = {"INFO", "WARNING", "ERROR"}
VALID_STATES = {"running", "stopped", "error"}

_LOGGER_LOCK = threading.Lock()
_CONFIGURED_LOGGERS: set[str] = set()
_PRINT_LOGS_LOCK = threading.Lock()
_PRINT_LOGS_CONFIGURED: set[str] = set()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat(sep=" ")


def _safe_service_name(servicio: str) -> str:
    name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in servicio.strip())
    return name or "servicio"


def _get_logger(servicio: str) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_service_name(servicio)
    logger_name = f"servicio.{safe_name}"
    logger = logging.getLogger(logger_name)

    with _LOGGER_LOCK:
        if logger_name in _CONFIGURED_LOGGERS:
            return logger

        logger.setLevel(logging.INFO)
        logger.propagate = False

        handler = logging.FileHandler(LOGS_DIR / f"{safe_name}.log", encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(handler)

        _CONFIGURED_LOGGERS.add(logger_name)

    return logger


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the SQLite database and required tables if they do not exist."""
    try:
        with _connect() as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS servicios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nombre TEXT UNIQUE,
                        estado TEXT,
                        pid INTEGER,
                        ultima_ejecucion DATETIME,
                        ultimo_ok DATETIME,
                        ultimo_error DATETIME,
                        activo BOOLEAN
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eventos_servicio (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        servicio TEXT,
                        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                        nivel TEXT,
                        mensaje TEXT,
                        detalle TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ejecuciones (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        servicio TEXT,
                        inicio DATETIME,
                        fin DATETIME,
                        resultado TEXT,
                        duracion INTEGER
                    )
                    """
                )
    except Exception:
        logging.getLogger(__name__).exception("Could not initialize service logging database")


def _register_service(conn: sqlite3.Connection, servicio: str) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT OR IGNORE INTO servicios (
            nombre, estado, pid, ultima_ejecucion, ultimo_ok, ultimo_error, activo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (servicio, "stopped", None, now, None, None, 1),
    )


def log_event(servicio: str, nivel: str, mensaje: str, detalle: str | None = None) -> None:
    """Write an event to logs/{servicio}.log and eventos_servicio."""
    logger = _get_logger(servicio)
    normalized_level = (nivel or "INFO").upper()
    if normalized_level not in VALID_LEVELS:
        normalized_level = "INFO"

    try:
        log_method = getattr(logger, normalized_level.lower(), logger.info)
        if detalle:
            log_method("%s | %s", mensaje, detalle)
        else:
            log_method("%s", mensaje)

        init_db()
        with _connect() as conn:
            with conn:
                _register_service(conn, servicio)
                conn.execute(
                    """
                    INSERT INTO eventos_servicio (servicio, nivel, mensaje, detalle)
                    VALUES (?, ?, ?, ?)
                    """,
                    (servicio, normalized_level, mensaje, detalle),
                )
    except Exception:
        logger.exception("Could not persist service event")


def update_service_status(servicio: str, estado: str, pid: int | None = None) -> None:
    """Register the service if needed and update its current status."""
    logger = _get_logger(servicio)
    normalized_state = (estado or "error").lower()
    if normalized_state not in VALID_STATES:
        normalized_state = "error"

    now = _utc_now()
    ultimo_ok = now if normalized_state == "stopped" else None
    ultimo_error = now if normalized_state == "error" else None
    active = 1 if normalized_state == "running" else 0

    try:
        init_db()
        with _connect() as conn:
            with conn:
                _register_service(conn, servicio)
                conn.execute(
                    """
                    UPDATE servicios
                    SET estado = ?,
                        pid = ?,
                        ultima_ejecucion = ?,
                        ultimo_ok = COALESCE(?, ultimo_ok),
                        ultimo_error = COALESCE(?, ultimo_error),
                        activo = ?
                    WHERE nombre = ?
                    """,
                    (normalized_state, pid, now, ultimo_ok, ultimo_error, active, servicio),
                )
    except Exception:
        logger.exception("Could not update service status")


def log_execution_start(servicio: str) -> int | None:
    """Create an execution row and mark the service as running."""
    logger = _get_logger(servicio)
    now = _utc_now()

    try:
        init_db()
        with _connect() as conn:
            with conn:
                _register_service(conn, servicio)
                cursor = conn.execute(
                    """
                    INSERT INTO ejecuciones (servicio, inicio, fin, resultado, duracion)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (servicio, now, None, None, None),
                )
                conn.execute(
                    """
                    UPDATE servicios
                    SET estado = ?, pid = ?, ultima_ejecucion = ?, activo = ?
                    WHERE nombre = ?
                    """,
                    ("running", os.getpid(), now, 1, servicio),
                )
                execution_id = int(cursor.lastrowid)

        log_event(servicio, "INFO", "Execution started", f"execution_id={execution_id}")
        return execution_id
    except Exception:
        logger.exception("Could not start service execution")
        return None


def log_execution_end(servicio: str, resultado: str) -> None:
    """Close the latest open execution row for the service and update service status."""
    logger = _get_logger(servicio)
    now = _utc_now()
    normalized_result = (resultado or "error").lower()
    final_state = "stopped" if normalized_result in {"ok", "success", "successful"} else "error"

    try:
        init_db()
        with _connect() as conn:
            with conn:
                _register_service(conn, servicio)
                row = conn.execute(
                    """
                    SELECT id, inicio
                    FROM ejecuciones
                    WHERE servicio = ? AND fin IS NULL
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (servicio,),
                ).fetchone()

                if row is not None:
                    inicio = datetime.fromisoformat(row["inicio"])
                    fin = datetime.fromisoformat(now)
                    duracion = max(0, int((fin - inicio).total_seconds()))
                    conn.execute(
                        """
                        UPDATE ejecuciones
                        SET fin = ?, resultado = ?, duracion = ?
                        WHERE id = ?
                        """,
                        (now, resultado, duracion, row["id"]),
                    )

                conn.execute(
                    """
                    UPDATE servicios
                    SET estado = ?,
                        pid = ?,
                        ultima_ejecucion = ?,
                        ultimo_ok = COALESCE(?, ultimo_ok),
                        ultimo_error = COALESCE(?, ultimo_error),
                        activo = ?
                    WHERE nombre = ?
                    """,
                    (
                        final_state,
                        None,
                        now,
                        now if final_state == "stopped" else None,
                        now if final_state == "error" else None,
                        0,
                        servicio,
                    ),
                )

        level = "INFO" if final_state == "stopped" else "ERROR"
        log_event(servicio, level, "Execution finished", f"resultado={resultado}")
    except Exception:
        logger.exception("Could not finish service execution")


class _TeeStream:
    """Escribe simultáneamente en el stream original y en un archivo de log."""

    def __init__(self, original, log_file):
        self._original = original
        self._log_file = log_file

    def write(self, data: str) -> int:
        try:
            self._original.write(data)
        except UnicodeEncodeError:
            enc = getattr(self._original, "encoding", "utf-8") or "utf-8"
            safe = data.encode(enc, errors="replace").decode(enc, errors="replace")
            self._original.write(safe)
        self._original.flush()
        try:
            self._log_file.write(data)
            self._log_file.flush()
        except Exception:
            pass
        return len(data)

    def flush(self) -> None:
        self._original.flush()
        try:
            self._log_file.flush()
        except Exception:
            pass

    def __getattr__(self, name: str):
        return getattr(self._original, name)


def setup_print_log(script_path: str | None = None) -> None:
    """Redirige stdout y stderr al archivo logs/<nombre_script>.log además de la consola.

    Args:
        script_path: Ruta del script (normalmente ``__file__``). Si es ``None``
                     se intenta detectar automáticamente desde el stack de llamadas.
    """
    import sys
    import inspect

    if script_path is None:
        frame = inspect.stack()[1]
        script_path = frame.filename

    script_name = Path(script_path).stem

    log_name = script_name
    argv = list(sys.argv[1:])

    # Alias legibles para logs de scripts con variantes de ejecución.
    if script_name == "aim_datos_accdb_incremental":
        log_name = "incremental_full" if "--force-full" in argv else "incremental"
    elif script_name == "reconstruir_estructura_bd":
        log_name = "reconstruccion"

    # Permite sobrescribir el nombre con --name o --name=<valor>.
    for idx, arg in enumerate(argv):
        if arg.startswith("--name="):
            candidate = arg.split("=", 1)[1].strip()
            if candidate:
                log_name = _safe_service_name(candidate)
            break
        if arg == "--name" and idx + 1 < len(argv):
            candidate = argv[idx + 1].strip()
            if candidate:
                log_name = _safe_service_name(candidate)
            break

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"{log_name}.log"

    with _PRINT_LOGS_LOCK:
        if str(log_path) in _PRINT_LOGS_CONFIGURED:
            return
        _PRINT_LOGS_CONFIGURED.add(str(log_path))

    log_file = open(log_path, "a", encoding="utf-8", errors="replace")

    # Escribir cabecera de sesión
    separator = "-" * 60
    timestamp = datetime.now().strftime(DATE_FORMAT)
    log_file.write(f"\n{separator}\n")
    log_file.write(f"INICIO EJECUCIÓN: {timestamp}\n")
    log_file.write(f"Script: {script_name}\n")
    log_file.write(f"Argumentos: {' '.join(argv) or '(sin argumentos)'}\n")
    log_file.write(f"{separator}\n")
    log_file.flush()

    sys.stdout = _TeeStream(sys.__stdout__, log_file)
    sys.stderr = _TeeStream(sys.__stderr__, log_file)

    def close_log() -> None:
        end_timestamp = datetime.now().strftime(DATE_FORMAT)
        try:
            log_file.write(f"FIN EJECUCIÓN: {end_timestamp}\n{separator}\n")
            log_file.flush()
        finally:
            log_file.close()

    atexit.register(close_log)


if __name__ == "__main__":
    service_name = "example_service"

    init_db()
    log_execution_start(service_name)
    update_service_status(service_name, "running", os.getpid())
    log_event(service_name, "INFO", "Service initialized")
    log_event(service_name, "WARNING", "Example warning", "This is optional detail")
    log_execution_end(service_name, "ok")
