"""Fault notifier: surfaces faults to the operator.

Connected to ``FaultBus.faultRaised``. Recoverable faults are shown briefly in
the status bar (non-modal — they must not block the operator from acting),
while CRITICAL/non-recoverable faults raise a modal dialog with details. This
is the visible end of the fault-handling pipeline that begins in
:mod:`hmi.core.fault`.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox, QWidget

from hmi.core.exceptions import Severity
from hmi.core.fault import Fault, FaultBus
from hmi.core.safe_slot import safe_slot


class FaultNotifier(QWidget):
    """Invisible widget that turns faults into user-facing notifications."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setVisible(False)
        FaultBus.instance().faultRaised.connect(self.on_fault)

    @safe_slot(source="FaultNotifier", reraise=False)
    def on_fault(self, fault: Fault) -> None:
        # Critical / non-recoverable: demand acknowledgement.
        if fault.severity is Severity.CRITICAL or not fault.recoverable:
            box = QMessageBox(self.parentWidget() or self)
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle("Critical Fault")
            box.setText(fault.message)
            box.setInformativeText(f"Source: {fault.source}")
            if fault.traceback_text:
                box.setDetailedText(fault.traceback_text)
            box.exec()
        # Lesser faults are surfaced via the status bar (see MainWindow), so
        # we deliberately do nothing intrusive here.
