"""Alarms page: live list of active alarms.

Subscribes to ``alarmRaised`` / ``alarmCleared`` on the bus. The list is the
operator's view of the :class:`AlarmManager` state.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from hmi.alarms.manager import Alarm
from hmi.core.safe_slot import safe_slot
from hmi.core.signals import bus
from hmi.views.base_page import BasePage


class AlarmsPage(BasePage):
    page_title = "Alarms"
    page_key = "alarms"

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        header = QLabel(self.page_title)
        header.setObjectName("pageHeader")
        root.addWidget(header)

        self._list = QListWidget()
        self._list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self._list)

        self._empty = QLabel("No active alarms.")
        self._empty.setObjectName("muted")
        root.addWidget(self._empty)

        bus().alarmRaised.connect(self._on_alarm_raised)
        bus().alarmCleared.connect(self._on_alarm_cleared)

    @safe_slot(source="AlarmsPage")
    def _on_alarm_raised(self, alarm: Alarm) -> None:
        item = QListWidgetItem(f"⚠  {alarm.message}")
        item.setData(256, alarm.key)  # Qt.ItemDataRole.UserRole == 256
        self._list.addItem(item)
        self._refresh_empty()

    @safe_slot(source="AlarmsPage")
    def _on_alarm_cleared(self, alarm: Alarm) -> None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is not None and item.data(256) == alarm.key:
                self._list.takeItem(row)
                break
        self._refresh_empty()

    def _refresh_empty(self) -> None:
        self._empty.setVisible(self._list.count() == 0)
