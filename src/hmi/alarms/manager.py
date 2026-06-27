"""Alarm engine.

Evaluates tag updates against engineering limits and maintains the set of
*active* alarms. Alarms are first-class in HMI: they drive operator attention,
audible annunciators, and event logs. This minimal engine supports high/low
limit alarms and latching (an alarm stays active until the value returns into
range), which covers the common case and is easy to extend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from PyQt6.QtCore import QObject

from hmi.core.exceptions import Severity
from hmi.core.safe_slot import safe_slot
from hmi.core.signals import bus
from hmi.models.tag import TagStore

log = logging.getLogger(__name__)


class AlarmType(Enum):
    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True)
class Alarm:
    """An active alarm condition on a tag."""

    tag_name: str
    alarm_type: AlarmType
    limit: float
    value: float
    severity: Severity = Severity.WARNING
    raised_at: datetime = field(default_factory=datetime.now)

    @property
    def key(self) -> str:
        return f"{self.tag_name}:{self.alarm_type.value}"

    @property
    def message(self) -> str:
        word = "above high" if self.alarm_type is AlarmType.HIGH else "below low"
        return f"{self.tag_name} = {self.value} {word} limit {self.limit}"


class AlarmManager(QObject):
    """Evaluates tag updates and tracks active alarms.

    Subscribes to ``tagUpdated`` on the bus; emits ``alarmRaised`` /
    ``alarmCleared`` on the bus so the alarms page, status bar, and any
    annunciator can react without coupling to this class.
    """

    def __init__(self, store: TagStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._active: dict[str, Alarm] = {}
        bus().tagUpdated.connect(self._on_tag_updated)

    @property
    def active(self) -> list[Alarm]:
        return list(self._active.values())

    @safe_slot(source="AlarmManager")
    def _on_tag_updated(self, name: str, value: object) -> None:
        tag = self._store.get(name)
        if tag is None or not isinstance(value, (int, float)):
            return

        self._evaluate(name, float(value), AlarmType.HIGH, tag.high_limit)
        self._evaluate(name, float(value), AlarmType.LOW, tag.low_limit)

    def _evaluate(
        self, name: str, value: float, alarm_type: AlarmType, limit: float | None
    ) -> None:
        if limit is None:
            return
        in_alarm = value > limit if alarm_type is AlarmType.HIGH else value < limit
        key = f"{name}:{alarm_type.value}"

        if in_alarm and key not in self._active:
            alarm = Alarm(name, alarm_type, limit, value)
            self._active[key] = alarm
            log.warning("ALARM raised: %s", alarm.message)
            bus().alarmRaised.emit(alarm)
        elif not in_alarm and key in self._active:
            alarm = self._active.pop(key)
            log.info("ALARM cleared: %s", alarm.tag_name)
            bus().alarmCleared.emit(alarm)
