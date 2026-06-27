"""Control page — the MVVM example view.

Deliberately "dumb": it renders the :class:`PumpControlViewModel`'s state and
forwards button presses. It owns **no** rules — preconditions, validation, and
command handling all live in the VM. Contrast with ``dashboard_page.py``,
which binds to the model directly (no VM) because it has no logic to test.

The view *does* own UI concerns the VM should not: the start-confirmation
dialog and turning rejection messages into a message box.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from hmi.core.safe_slot import safe_slot
from hmi.views.base_page import BasePage
from hmi.views.viewmodels.base import bind
from hmi.views.viewmodels.pump_control import PumpControlViewModel


class ControlPage(BasePage):
    page_title = "Control"
    page_key = "control"

    def __init__(self, viewmodel: PumpControlViewModel) -> None:
        self._vm = viewmodel
        super().__init__()
        self._wire_viewmodel()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        header = QLabel(self.page_title)
        header.setObjectName("pageHeader")
        root.addWidget(header)

        self._status = QLabel("—")
        self._status.setObjectName("cardValue")
        root.addWidget(self._status)

        buttons = QHBoxLayout()
        self._start_btn = QPushButton("Start pump")
        self._stop_btn = QPushButton("Stop pump")
        self._start_btn.clicked.connect(self._on_start_clicked)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        buttons.addWidget(self._start_btn)
        buttons.addWidget(self._stop_btn)
        buttons.addStretch(1)
        root.addLayout(buttons)
        root.addStretch(1)

    def _wire_viewmodel(self) -> None:
        # Declarative-ish binding: VM property -> widget, kept in sync by the
        # VM's notify signals. This is the whole "binding" cost in widget MVVM.
        bind(self._vm.statusChanged, lambda: self._vm.status_text, self._status.setText)
        bind(self._vm.canStartChanged, lambda: self._vm.can_start, self._start_btn.setEnabled)
        bind(self._vm.runningChanged, lambda: self._vm.is_running, self._stop_btn.setEnabled)
        self._vm.commandRejected.connect(self._on_rejected)

    # --------------------------------------------------------------- slots #
    @safe_slot(source="ControlPage")
    def _on_start_clicked(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Confirm",
            "Start the pump?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm is QMessageBox.StandardButton.Yes:
            self._vm.start()  # VM re-checks preconditions defensively

    @safe_slot(source="ControlPage")
    def _on_stop_clicked(self) -> None:
        self._vm.stop()

    @safe_slot(source="ControlPage")
    def _on_rejected(self, reason: str) -> None:
        QMessageBox.warning(self, "Command rejected", f"Cannot start pump: {reason}")
