"""Monitoriza la copia temporal de Access y lanza el incremental local."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

import config
from access_odbc import comprobar_base_access, configurar_dsn_web
from service_logging import log_event


SERVICE_NAME = "factusol_web"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _firma_archivo(path: str) -> dict[str, int]:
    stat = os.stat(path)
    return {"tamano": stat.st_size, "modificado_ns": stat.st_mtime_ns}


def _hash_archivo(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cargar_estado() -> dict:
    path = Path(config.PATH_MAIN) / config.ACCDB_MONITOR_STATE_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _guardar_estado(estado: dict) -> None:
    path = Path(config.PATH_MAIN) / config.ACCDB_MONITOR_STATE_FILE
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(estado, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def _registrar(level: str, message: str, detail: str | None = None) -> None:
    log_event(SERVICE_NAME, level, message, detail)


def _copiar_base_estable(firma_origen: dict[str, int]) -> str | None:
    local_path = Path(config.LOCAL_ACCDB_PATH)
    temporary_path = local_path.with_suffix(".tmp.accdb")
    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if os.path.exists(config.ACCDB_SOURCE_LOCK_PATH):
            _registrar("INFO", "La copia temporal de Access esta en uso; copia pospuesta")
            return None

        shutil.copyfile(config.ACCDB_SOURCE_PATH, temporary_path)
        if _firma_archivo(config.ACCDB_SOURCE_PATH) != firma_origen or os.path.exists(config.ACCDB_SOURCE_LOCK_PATH):
            _registrar("WARNING", "La copia temporal cambio durante la copia; se descartara el temporal")
            return None

        comprobar_base_access(str(temporary_path))
        content_hash = _hash_archivo(str(temporary_path))
        os.replace(temporary_path, local_path)
        return content_hash
    except Exception as error:
        _registrar("ERROR", "No se pudo crear o validar la copia local de Access", str(error))
        return None
    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def ejecutar_una_vez() -> bool:
    """Process one monitoring cycle. Returns True only after an incremental run."""
    try:
        firma_actual = _firma_archivo(config.ACCDB_SOURCE_PATH)
    except OSError as error:
        _registrar("ERROR", "No se puede acceder a la copia temporal local de Access", str(error))
        return False

    estado = _cargar_estado()
    if estado.get("firma_observada") != firma_actual:
        _guardar_estado({"firma_observada": firma_actual, "estable_desde": _ahora()})
        _registrar("INFO", "Cambio detectado en Access; iniciada espera de estabilidad")
        return False

    if estado.get("firma_procesada") == firma_actual:
        return False

    try:
        estable_desde = datetime.fromisoformat(estado["estable_desde"])
    except (KeyError, ValueError):
        _guardar_estado({"firma_observada": firma_actual, "estable_desde": _ahora()})
        return False

    if time.time() - estable_desde.timestamp() < config.ACCDB_STABILITY_SECONDS:
        return False

    content_hash = _copiar_base_estable(firma_actual)
    if content_hash is None:
        return False

    if estado.get("hash_procesado") == content_hash:
        estado.update({"firma_procesada": firma_actual, "hash_procesado": content_hash})
        _guardar_estado(estado)
        _registrar("INFO", "La copia local no contiene cambios de datos")
        return False

    _registrar("INFO", "Copia local estable y modificada; iniciando sincronizacion incremental")
    python_executable = os.path.join(config.PATH_MAIN, ".venv", "Scripts", "python.exe")
    result = subprocess.run(
        [python_executable, os.path.join(config.PATH_MAIN, "aim_datos_accdb_incremental.py")],
        cwd=config.PATH_MAIN,
        check=False,
    )
    if result.returncode != 0:
        _registrar("ERROR", "La sincronizacion incremental ha fallado", f"codigo={result.returncode}")
        return False

    estado.update({"firma_procesada": firma_actual, "hash_procesado": content_hash})
    _guardar_estado(estado)
    _registrar("INFO", "Sincronizacion incremental completada")
    return True


def ejecutar_bucle(stop_event: Event) -> None:
    """Run monitoring until the Windows service signals shutdown."""
    while not stop_event.is_set():
        try:
            Path(config.LOCAL_ACCDB_DIRECTORY).mkdir(parents=True, exist_ok=True)
            configurar_dsn_web()
            _registrar("INFO", "DSN web configurado", config.DSN_DB)
            break
        except Exception as error:
            _registrar("ERROR", "No se pudo configurar el DSN web", str(error))
            stop_event.wait(config.ACCDB_COPY_RETRY_SECONDS)

    if stop_event.is_set():
        return

    while not stop_event.is_set():
        try:
            ejecutar_una_vez()
        except Exception as error:
            _registrar("ERROR", "Error no controlado en el monitor Access", str(error))
        stop_event.wait(config.ACCDB_CHECK_INTERVAL_SECONDS)
