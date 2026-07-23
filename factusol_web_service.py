"""Servicio Windows autonomo para sincronizar cambios de Factusol."""

from __future__ import annotations

import sys
from threading import Event, Thread

import win32event
import win32service
import win32serviceutil

from accdb_monitor import SERVICE_NAME, ejecutar_bucle
from service_logging import log_event, log_execution_end, log_execution_start


class FactusolWebService(win32serviceutil.ServiceFramework):
    _svc_name_ = "AIMXERAX_FACTUSOL_WEB"
    _svc_display_name_ = "AIMXERAX_FACTUSOL_WEB"
    _svc_description_ = "Monitoriza la copia temporal de Access y sincroniza cambios estables con la web."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = Event()
        self.stop_handle = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        log_event(SERVICE_NAME, "INFO", "Solicitud de detencion del servicio recibida")
        self.stop_event.set()
        win32event.SetEvent(self.stop_handle)

    def SvcDoRun(self):
        log_execution_start(SERVICE_NAME)
        try:
            log_event(SERVICE_NAME, "INFO", "Servicio de monitorizacion iniciado")
            worker = Thread(target=ejecutar_bucle, args=(self.stop_event,), daemon=True)
            worker.start()
            win32event.WaitForSingleObject(self.stop_handle, win32event.INFINITE)
            worker.join(timeout=30)
            log_event(SERVICE_NAME, "INFO", "Servicio de monitorizacion detenido")
        except BaseException as error:
            log_event(SERVICE_NAME, "ERROR", "El servicio de monitorizacion finalizo con error", str(error))
            log_execution_end(SERVICE_NAME, "error")
            raise
        else:
            log_execution_end(SERVICE_NAME, "ok")


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(FactusolWebService)
