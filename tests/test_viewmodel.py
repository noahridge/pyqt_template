"""Tests for the example ViewModel.

The point of MVVM: this exercises real presentation logic — command
preconditions, validation, rejection — *without instantiating any widget*.
Only a QApplication (provided by the ``qtbot`` fixture, for signals) is needed.
"""

from __future__ import annotations

from hmi.core.settings import DeviceConfig
from hmi.models.tag import Quality, Tag, TagStore
from hmi.services.base import ConnectionState
from hmi.services.device_service import DeviceService
from hmi.views.viewmodels.pump_control import PumpControlViewModel


def _make(level: float = 50.0, *, connected: bool = False):
    store = TagStore()
    store.define(Tag("tank.level", unit="%", high_limit=85.0))
    store.update("tank.level", level, quality=Quality.GOOD)
    device = DeviceService(DeviceConfig(name="PLC-1"), store)
    vm = PumpControlViewModel(store, device)
    if connected:
        device.set_state(ConnectionState.CONNECTED)  # emits on the bus
    return store, device, vm


def test_blocked_when_disconnected(qtbot):
    _store, _device, vm = _make(connected=False)
    rejected: list[str] = []
    vm.commandRejected.connect(rejected.append)

    assert vm.can_start is False
    vm.start()

    assert vm.is_running is False
    assert rejected and "not connected" in rejected[0]


def test_starts_when_ready(qtbot):
    _store, _device, vm = _make(level=50.0, connected=True)

    assert vm.can_start is True
    accepted: list[str] = []
    vm.commandAccepted.connect(accepted.append)
    vm.start()

    assert vm.is_running is True
    assert vm.status_text == "Pump: RUNNING"
    assert accepted == ["Pump started"]


def test_refuses_above_high_limit(qtbot):
    _store, _device, vm = _make(level=90.0, connected=True)
    rejected: list[str] = []
    vm.commandRejected.connect(rejected.append)

    assert vm.can_start is False
    vm.start()

    assert vm.is_running is False
    assert rejected and "high limit" in rejected[0]


def test_can_start_revalidates_on_tag_update(qtbot):
    store, _device, vm = _make(level=90.0, connected=True)
    assert vm.can_start is False  # above high limit

    with qtbot.waitSignal(vm.canStartChanged, timeout=1000):
        store.update("tank.level", 40.0, quality=Quality.GOOD)

    assert vm.can_start is True


def test_stop_clears_running(qtbot):
    _store, _device, vm = _make(level=50.0, connected=True)
    vm.start()
    assert vm.is_running is True

    vm.stop()
    assert vm.is_running is False
    assert vm.status_text == "Pump: READY"
