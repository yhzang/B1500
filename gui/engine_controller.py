"""EngineController · 唯一协调者:管 QThread + EngineWorker 生命周期,转发信号。

MainWindow 只与本控制器打交道:连一次本控制器的信号到各 panel,然后每次运行调
`start(req)`。控制器内部新建 QThread+worker、转发 worker 信号、跑完清理。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from .engine_worker import EngineWorker
from .models import RunRequest


class EngineController(QObject):
    # 转发自 worker(签名一致)
    progress = Signal(int, int)
    shot = Signal(str, int, object)
    logMsg = Signal(str, str, str)
    stageDone = Signal(object, object)
    stopGate = Signal(str, str, bool)
    errorOccurred = Signal(object, bool)
    planReady = Signal(object)
    runStarted = Signal()
    runFinished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: EngineWorker | None = None

    def is_busy(self) -> bool:
        return self._thread is not None

    def start(self, req: RunRequest) -> bool:
        if self.is_busy():
            return False
        thread = QThread()
        worker = EngineWorker(req)
        worker.moveToThread(thread)

        # 转发 worker → controller
        worker.progress.connect(self.progress)
        worker.shot.connect(self.shot)
        worker.logMsg.connect(self.logMsg)
        worker.stageDone.connect(self.stageDone)
        worker.stopGate.connect(self.stopGate)
        worker.errorOccurred.connect(self.errorOccurred)
        worker.planReady.connect(self.planReady)

        # 生命周期
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)

        self._thread = thread
        self._worker = worker
        thread.start()
        self.runStarted.emit()
        return True

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self.runFinished.emit()
