"""Dashboard page: live process values.

Reads from the :class:`TagStore` and updates on ``tagUpdated`` from the bus.
Note it never touches the device or threads directly — the unidirectional
data flow (device → service → store → bus → view) is what keeps a large HMI
maintainable.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from hmi.core.safe_slot import safe_slot
from hmi.core.signals import bus
from hmi.models.tag import TagStore
from hmi.views.base_page import BasePage


class _ValueCard(QFrame):
    """A single labelled value tile."""

    def __init__(self, title: str, unit: str) -> None:
        super().__init__()
        self.setObjectName("valueCard")
        self._unit = unit
        layout = QVBoxLayout(self)
        self._title = QLabel(title)
        self._title.setObjectName("cardTitle")
        self._value = QLabel("—")
        self._value.setObjectName("cardValue")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_value(self, value: object) -> None:
        self._value.setText(f"{value} {self._unit}".strip())


class DashboardPage(BasePage):
    page_title = "Dashboard"
    page_key = "dashboard"

    def __init__(self, store: TagStore) -> None:
        self._store = store
        self._cards: dict[str, _ValueCard] = {}
        super().__init__()
        bus().tagUpdated.connect(self._on_tag_updated)

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        header = QLabel(self.page_title)
        header.setObjectName("pageHeader")
        root.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(16)
        specs = [
            ("tank.level", "Tank Level", "%"),
            ("reactor.temperature", "Reactor Temp", "°C"),
        ]
        for i, (key, title, unit) in enumerate(specs):
            card = _ValueCard(title, unit)
            self._cards[key] = card
            grid.addWidget(card, 0, i)
        root.addLayout(grid)
        root.addStretch(1)

    @safe_slot(source="DashboardPage")
    def _on_tag_updated(self, name: str, value: object) -> None:
        card = self._cards.get(name)
        if card is not None:
            card.set_value(value)
