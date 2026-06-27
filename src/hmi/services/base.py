"""Service base class and connection state machine.

A *service* is a long-lived component that talks to the outside world (a
device, a database, a message broker). Services:

* run their I/O on a background thread (never the GUI thread),
* expose a small, explicit connection state machine, and
* report failures as faults rather than raising into the event loop.

Concrete services subclass :class:`Service` and provide a worker. The base
class handles the thread lifecycle and state broadcasting so every service in
a large app behaves consistently.
"""

from __future__ import annotations

import logging
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal

from hmi.core.signals import bus
from hmi.core.worker import WorkerThread

log = logging.getLogger(__name__)


class ConnectionState(Enum):
    """The lifecycle every external connection moves through."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"  # connected but errors are occurring
    FAULTED = "faulted"  # gave up; manual intervention may be needed


class Service(QObject):
    """Base class for threaded, stateful services.

    Subclasses implement :meth:`create_worker` returning a ``QObject`` worker
    (typically a :class:`hmi.core.worker.PeriodicWorker`). The worker runs on
    its own thread; the service object lives on the GUI thread and is the API
    other components talk to.
    """

    stateChanged = pyqtSignal(object)  # emits ConnectionState

    def __init__(self, name: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self._state = ConnectionState.DISCONNECTED
        self._thread: WorkerThread | None = None

    # ----------------------------------------------------------- lifecycle #
    def start(self) -> None:
        if self._thread is not None:
            return
        log.info("Starting service '%s'", self.name)
        self.set_state(ConnectionState.CONNECTING)
        worker = self.create_worker()
        self._thread = WorkerThread(worker, name=f"{self.name}-thread")
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        log.info("Stopping service '%s'", self.name)
        self._thread.stop()
        self._thread = None
        self.set_state(ConnectionState.DISCONNECTED)

    # --------------------------------------------------------------- state #
    @property
    def state(self) -> ConnectionState:
        return self._state

    def set_state(self, state: ConnectionState) -> None:
        if state == self._state:
            return
        log.info("Service '%s' state: %s -> %s", self.name, self._state.value, state.value)
        self._state = state
        self.stateChanged.emit(state)
        bus().connectionStateChanged.emit(self.name, state)

    # ------------------------------------------------------------ override #
    def create_worker(self) -> QObject:  # pragma: no cover - overridden
        """Return the worker object to run on the background thread."""
        raise NotImplementedError
