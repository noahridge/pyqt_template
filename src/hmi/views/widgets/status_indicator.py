"""Connection-state indicator for the status bar.

A coloured pill + label that reflects a service's :class:`ConnectionState`.
Reusable across any number of services in a multi-device panel.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from hmi.core.safe_slot import safe_slot
from hmi.services.base import ConnectionState

_COLORS = {
    ConnectionState.DISCONNECTED: "#888888",
    ConnectionState.CONNECTING: "#e0a800",
    ConnectionState.CONNECTED: "#2ea043",
    ConnectionState.DEGRADED: "#e0a800",
    ConnectionState.FAULTED: "#d73a49",
}


class StatusIndicator(QWidget):
    """Shows ``<name>: <state>`` with a colour-coded dot."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label_text = label

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        self._dot = QLabel("●")  # ●
        self._text = QLabel(f"{label}: —")
        layout.addWidget(self._dot)
        layout.addWidget(self._text)

        self.set_state(ConnectionState.DISCONNECTED)

    @safe_slot(source="StatusIndicator")
    def set_state(self, state: ConnectionState) -> None:
        color = _COLORS.get(state, "#888888")
        self._dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self._text.setText(f"{self._label_text}: {state.value}")
