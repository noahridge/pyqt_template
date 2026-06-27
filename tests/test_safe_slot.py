"""Tests for the safe-slot guard and the fault bus it reports to."""

from __future__ import annotations

from hmi.core.exceptions import Severity
from hmi.core.fault import Fault, FaultBus
from hmi.core.safe_slot import safe_slot


def _collect_faults() -> list[Fault]:
    faults: list[Fault] = []
    FaultBus.instance().faultRaised.connect(faults.append)
    return faults


def test_safe_slot_swallows_and_reports(qtbot):
    faults = _collect_faults()

    class Widget:
        @safe_slot(default=-1)
        def boom(self) -> int:
            raise ValueError("kaboom")

    result = Widget().boom()

    assert result == -1  # default returned instead of propagating
    assert len(faults) == 1
    assert "kaboom" in faults[0].message
    assert faults[0].source == "Widget.boom"


def test_safe_slot_passes_through_return_value(qtbot):
    class Widget:
        @safe_slot
        def add(self, a: int, b: int) -> int:
            return a + b

    assert Widget().add(2, 3) == 5


def test_safe_slot_reraise(qtbot):
    faults = _collect_faults()

    class Widget:
        @safe_slot(reraise=True)
        def boom(self) -> None:
            raise RuntimeError("nope")

    try:
        Widget().boom()
        raised = False
    except RuntimeError:
        raised = True

    assert raised  # re-raised after reporting
    assert len(faults) == 1


def test_fault_from_app_error_keeps_severity(qtbot):
    from hmi.core.exceptions import DeviceError

    fault = Fault.from_exception(DeviceError("link down", context="plc"))
    assert fault.severity is Severity.WARNING
    assert fault.recoverable is True
    assert fault.source == "plc"
