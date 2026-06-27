"""Example ViewModel: pump control with preconditions and validation.

This is the kind of screen where MVVM earns its keep — there's genuine
presentation logic to keep out of the widget and to unit-test in isolation:

* a **command** (``start``) that is only valid under preconditions
  (device connected, process value fresh, tank not already at its high limit),
* **derived state** (``can_start``, ``status_text``) that the view binds to,
* explicit **rejection** feedback when a command is refused.

The view ([`control_page.py`](../pages/control_page.py)) only renders this
state and forwards button clicks; all the rules live here and are covered by
``tests/test_viewmodel.py`` with no widgets involved.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from hmi.core.signals import bus
from hmi.models.tag import Quality, TagStore
from hmi.services.base import ConnectionState, Service
from hmi.views.viewmodels.base import ViewModel

log = logging.getLogger(__name__)


class PumpControlViewModel(ViewModel):
    """Presentation logic for a 'start/stop pump' control screen.

    Observes the tag store and a service's connection state via the signal
    bus; exposes bindable properties and start/stop commands.
    """

    # Notify signals for bindable properties.
    runningChanged = pyqtSignal()
    canStartChanged = pyqtSignal()
    statusChanged = pyqtSignal()

    # Command feedback (the view turns these into dialogs / status messages).
    commandRejected = pyqtSignal(str)
    commandAccepted = pyqtSignal(str)

    def __init__(
        self,
        store: TagStore,
        service: Service,
        *,
        interlock_tag: str = "tank.level",
        parent: ViewModel | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._service = service
        self._interlock_tag = interlock_tag
        self._running = False
        self._conn_state = service.state

        bus().connectionStateChanged.connect(self._on_connection_state)
        bus().tagUpdated.connect(self._on_tag_updated)

    # --------------------------------------------------- bindable state #
    @pyqtProperty(bool, notify=runningChanged)
    def is_running(self) -> bool:
        return self._running

    @pyqtProperty(bool, notify=canStartChanged)
    def can_start(self) -> bool:
        return self._check_preconditions()[0]

    @pyqtProperty(str, notify=statusChanged)
    def status_text(self) -> str:
        if self._running:
            return "Pump: RUNNING"
        ok, reason = self._check_preconditions()
        return "Pump: READY" if ok else f"Pump: BLOCKED — {reason}"

    # --------------------------------------------------------- commands #
    @pyqtSlot()
    def start(self) -> None:
        """Attempt to start the pump; refuse (with reason) if not permitted."""
        ok, reason = self._check_preconditions()
        if not ok:
            log.info("Pump start rejected: %s", reason)
            self.commandRejected.emit(reason)
            return
        # A real implementation would issue a write to the device here, e.g.
        #   self._service.write("pump.run", True)
        self._running = True
        log.info("Pump started")
        self._emit_all()
        self.commandAccepted.emit("Pump started")

    @pyqtSlot()
    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        log.info("Pump stopped")
        self._emit_all()
        self.commandAccepted.emit("Pump stopped")

    # ----------------------------------------------------------- logic #
    def _check_preconditions(self) -> tuple[bool, str]:
        """The testable heart of the VM. Returns (allowed, reason-if-not)."""
        if self._running:
            return False, "already running"
        if self._conn_state is not ConnectionState.CONNECTED:
            return False, "device not connected"
        tag = self._store.get(self._interlock_tag)
        if tag is None or tag.quality is not Quality.GOOD:
            return False, "interlock value unavailable or stale"
        if (
            isinstance(tag.value, (int, float))
            and tag.high_limit is not None
            and tag.value >= tag.high_limit
        ):
            return False, f"{self._interlock_tag} at/above high limit"
        return True, ""

    # ------------------------------------------------------------ slots #
    def _on_connection_state(self, name: str, state: object) -> None:
        if name != self._service.name:
            return
        self._conn_state = state  # type: ignore[assignment]
        self._revalidate()

    def _on_tag_updated(self, name: str, _value: object) -> None:
        if name == self._interlock_tag:
            self._revalidate()

    def _revalidate(self) -> None:
        self.canStartChanged.emit()
        self.statusChanged.emit()

    def _emit_all(self) -> None:
        self.runningChanged.emit()
        self.canStartChanged.emit()
        self.statusChanged.emit()
