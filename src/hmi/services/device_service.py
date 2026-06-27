"""Example device service: a simulated PLC poller.

This stands in for a real fieldbus driver (Modbus, OPC-UA, serial, …). It
demonstrates the full robustness pattern you'd reuse for a real device:

* polling happens on a background thread (:class:`PeriodicWorker`);
* each poll can fail (``failure_rate``), and failures are reported as faults
  *without* stopping the poll loop;
* the service translates a run of failures into a connection state
  (CONNECTED → DEGRADED → FAULTED) and recovers automatically.

To wire a real device, replace :meth:`_DevicePoller.step`'s body with your
driver calls and raise :class:`DeviceError` on communication failure.
"""

from __future__ import annotations

import logging
import math
import random
import time

from PyQt6.QtCore import QObject, pyqtSignal

from hmi.core.exceptions import DeviceError
from hmi.core.settings import DeviceConfig
from hmi.core.worker import PeriodicWorker
from hmi.models.tag import Quality, TagStore
from hmi.services.base import ConnectionState, Service

log = logging.getLogger(__name__)

# Consecutive poll failures before we declare the connection FAULTED.
_FAULT_THRESHOLD = 5


class _DevicePoller(PeriodicWorker):
    """Background worker that reads simulated device values on a timer."""

    reading = pyqtSignal(str, float)  # tag name, value
    pollOk = pyqtSignal()

    def __init__(self, config: DeviceConfig) -> None:
        super().__init__(interval_ms=config.poll_interval_ms, name=f"{config.name}-poller")
        self._config = config
        self._t0 = time.monotonic()

    def step(self) -> None:
        # Simulate an unreliable link. A real driver would raise here on
        # timeout / CRC error / disconnect instead.
        if random.random() < self._config.failure_rate:
            raise DeviceError(
                f"Lost contact with {self._config.name}", context=self._config.name
            )

        elapsed = time.monotonic() - self._t0
        # A couple of plausible-looking process values.
        level = 50.0 + 40.0 * math.sin(elapsed / 5.0)
        temperature = 70.0 + 15.0 * math.sin(elapsed / 11.0) + random.uniform(-1, 1)
        self.reading.emit("tank.level", round(level, 2))
        self.reading.emit("reactor.temperature", round(temperature, 2))
        self.pollOk.emit()


class DeviceService(Service):
    """Owns a :class:`_DevicePoller` and maps poll results to tag/state updates.

    All the slots below run on the GUI thread (the signals are queued across
    the thread boundary), so they can safely touch the :class:`TagStore`.
    """

    def __init__(self, config: DeviceConfig, store: TagStore) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._store = store
        self._consecutive_failures = 0

    def create_worker(self) -> QObject:
        poller = _DevicePoller(self._config)
        poller.reading.connect(self._on_reading)
        poller.pollOk.connect(self._on_poll_ok)
        poller.failed.connect(self._on_poll_failed)
        poller.started.connect(lambda: self.set_state(ConnectionState.CONNECTED))
        return poller

    # ------------------------------------------------------------- slots #
    def _on_reading(self, name: str, value: float) -> None:
        self._store.update(name, value, quality=Quality.GOOD)

    def _on_poll_ok(self) -> None:
        self._consecutive_failures = 0
        if self.state in (ConnectionState.DEGRADED, ConnectionState.FAULTED):
            self.set_state(ConnectionState.CONNECTED)

    def _on_poll_failed(self, fault: object) -> None:
        # The poll loop keeps running; we just track the health here.
        self._consecutive_failures += 1
        self._store.mark_stale()
        if self._consecutive_failures >= _FAULT_THRESHOLD:
            self.set_state(ConnectionState.FAULTED)
        else:
            self.set_state(ConnectionState.DEGRADED)
