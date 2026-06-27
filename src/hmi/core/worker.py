"""Threading infrastructure for background work.

HMI apps spend most of their time talking to slow, unreliable things (PLCs,
serial buses, network sockets). All of that *must* happen off the GUI thread,
or the UI freezes and the operator can't hit the e-stop button.

This module gives two reusable pieces built on the *worker-object* pattern
(a ``QObject`` moved onto a ``QThread``), which is the idiom Qt recommends
over subclassing ``QThread``:

* :class:`Worker` — base class for a one-shot job. Override :meth:`work`.
* :class:`PeriodicWorker` — runs :meth:`step` on a timer inside its thread,
  ideal for polling a device.
* :class:`WorkerThread` — owns the ``QThread`` + worker pair and manages a
  clean start/stop lifecycle so threads never leak or get destroyed while
  running (a common source of hard crashes).

Every override is wrapped so exceptions become :class:`Fault` reports on the
GUI thread rather than killing the thread silently.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import (
    QMetaObject,
    QObject,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)

from hmi.core.fault import Fault, report_fault

log = logging.getLogger(__name__)


class Worker(QObject):
    """Base one-shot worker. Override :meth:`work`.

    Signals are emitted from the worker thread; connect them with the default
    (auto) connection type and Qt will queue delivery onto the GUI thread.
    """

    started = pyqtSignal()
    finished = pyqtSignal()
    failed = pyqtSignal(object)  # emits Fault

    def __init__(self, *, name: str = "worker") -> None:
        super().__init__()
        self._name = name

    @pyqtSlot()
    def run(self) -> None:
        """Entry point invoked when the owning thread starts."""
        self.started.emit()
        try:
            self.work()
        except Exception as exc:  # noqa: BLE001 - convert to fault, keep thread tidy
            fault = report_fault(exc, source=self._name)
            self.failed.emit(fault)
        finally:
            self.finished.emit()

    def work(self) -> None:  # pragma: no cover - overridden
        """Do the job. Override me."""
        raise NotImplementedError


class PeriodicWorker(QObject):
    """Runs :meth:`step` repeatedly on an interval, inside its own thread.

    The timer lives in the worker thread, so ticks never block the GUI. A
    failure in one ``step`` is reported as a fault but does **not** stop the
    timer — transient device errors shouldn't end polling.
    """

    started = pyqtSignal()
    stopped = pyqtSignal()
    failed = pyqtSignal(object)  # emits Fault

    def __init__(self, *, interval_ms: int, name: str = "periodic") -> None:
        super().__init__()
        self._interval_ms = interval_ms
        self._name = name
        self._timer: QTimer | None = None

    @pyqtSlot()
    def run(self) -> None:
        # Created here, parented to self, so the QTimer is owned by — and only
        # ever touched on — this worker thread. Stopping/destroying a timer
        # from another thread is a fatal Qt error.
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.started.emit()

    @pyqtSlot()
    def stop(self) -> None:
        # Must run on the worker thread (WorkerThread.stop guarantees this via
        # a blocking-queued call) so the timer is stopped where it lives.
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        self.stopped.emit()

    def set_interval(self, interval_ms: int) -> None:
        self._interval_ms = interval_ms
        if self._timer is not None:
            self._timer.setInterval(interval_ms)

    def _tick(self) -> None:
        try:
            self.step()
        except Exception as exc:  # noqa: BLE001 - keep polling alive
            fault = report_fault(exc, source=self._name)
            self.failed.emit(fault)

    def step(self) -> None:  # pragma: no cover - overridden
        """One iteration of work. Override me."""
        raise NotImplementedError


class WorkerThread(QObject):
    """Owns a worker + its ``QThread`` and manages a safe lifecycle.

    Keeps a Python reference to both objects (Qt will crash if a running
    QThread is garbage-collected) and guarantees an orderly shutdown:
    ``stop`` → ``quit`` → ``wait``.
    """

    def __init__(self, worker: QObject, *, name: str = "worker") -> None:
        super().__init__()
        self._worker = worker
        self._thread = QThread()
        self._thread.setObjectName(name)
        worker.moveToThread(self._thread)
        # 'run' must be a slot so the cross-thread invocation is queued.
        self._thread.started.connect(worker.run)  # type: ignore[attr-defined]

    @property
    def worker(self) -> QObject:
        return self._worker

    def start(self) -> None:
        if not self._thread.isRunning():
            self._thread.start()

    def stop(self, *, wait_ms: int = 5000) -> None:
        """Stop the worker and join the thread. Safe to call repeatedly."""
        if not self._thread.isRunning():
            return
        # Ask the worker to stop *on its own thread* and block until it has,
        # so any thread-affine resources (timers, sockets) are torn down on
        # the correct thread before we quit the event loop. 'stop' must be a
        # registered slot for invokeMethod-by-name to find it.
        if hasattr(self._worker, "stop"):
            QMetaObject.invokeMethod(
                self._worker, "stop", Qt.ConnectionType.BlockingQueuedConnection
            )
        self._thread.quit()
        if not self._thread.wait(wait_ms):
            log.warning("Thread %s did not stop in %dms; terminating", self._thread.objectName(), wait_ms)
            self._thread.terminate()
            self._thread.wait()
