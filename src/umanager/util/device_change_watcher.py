from __future__ import annotations

import threading
import time
from typing import Optional

import pythoncom  # type: ignore
import wmi
from PySide6 import QtCore


class _WmiVolumeChangeWorker(QtCore.QObject):
    device_change_detected = QtCore.Signal()
    finished = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    @QtCore.Slot()
    def run(self) -> None:
        pythoncom.CoInitialize()
        try:
            provider = wmi.WMI()
            watcher = provider.watch_for(
                notification_type="Creation",
                wmi_class="Win32_VolumeChangeEvent",
            )

            while not self._stop_event.is_set():
                try:
                    _event = watcher(timeout_ms=1000)
                except wmi.x_wmi_timed_out:
                    continue
                except Exception:
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)
                    continue

                self.device_change_detected.emit()
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

            self.finished.emit()


class UsbDeviceChangeWatcher(QtCore.QObject):
    """WMI-based watcher that emits a signal when USB storage devices change.

    Runs WMI event listening on a dedicated QThread, then emits `deviceChangeDetected`
    on the Qt signal/slot system (queued back to the main thread when connected).
    """

    deviceChangeDetected = QtCore.Signal()

    def __init__(self, *, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._thread = QtCore.QThread(self)
        self._worker = _WmiVolumeChangeWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.device_change_detected.connect(self.deviceChangeDetected)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)

        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread.start()

    def stop(self) -> None:
        if not self._started:
            return
        self._worker.stop()
        self._thread.quit()
        self._thread.wait(2500)
        self._started = False
