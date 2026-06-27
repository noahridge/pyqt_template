"""Process data model: tags and a tag store.

In HMI/SCADA terminology a *tag* is a single named process value (a tank
level, a motor speed, a valve state). The :class:`TagStore` is the single
source of truth for current values; views observe it via the signal bus
rather than polling devices directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable

from hmi.core.signals import bus

log = logging.getLogger(__name__)


class Quality(Enum):
    """OPC-style data quality — operators must distinguish 'zero' from 'stale'."""

    GOOD = "good"
    BAD = "bad"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass
class Tag:
    """A single named process value with metadata."""

    name: str
    value: Any = None
    unit: str = ""
    quality: Quality = Quality.UNKNOWN
    timestamp: datetime = field(default_factory=datetime.now)
    # Optional engineering limits, used by the alarm engine.
    low_limit: float | None = None
    high_limit: float | None = None


class TagStore:
    """In-memory registry of current tag values.

    Updates flow in from services (on the GUI thread, via queued signals) and
    are broadcast on the bus so any number of widgets can react. This is the
    classic single-writer / many-reader pattern that keeps a large UI
    consistent.
    """

    def __init__(self) -> None:
        self._tags: dict[str, Tag] = {}

    def define(self, tag: Tag) -> None:
        """Register a tag (typically at startup from config)."""
        self._tags[tag.name] = tag

    def define_many(self, tags: Iterable[Tag]) -> None:
        for tag in tags:
            self.define(tag)

    def get(self, name: str) -> Tag | None:
        return self._tags.get(name)

    def names(self) -> list[str]:
        return list(self._tags)

    def update(
        self,
        name: str,
        value: Any,
        *,
        quality: Quality = Quality.GOOD,
    ) -> Tag:
        """Update a tag's value and broadcast the change.

        Auto-defines unknown tags so services can publish freely.
        """
        tag = self._tags.get(name)
        if tag is None:
            tag = Tag(name=name)
            self._tags[name] = tag
        tag.value = value
        tag.quality = quality
        tag.timestamp = datetime.now()
        bus().tagUpdated.emit(name, value)
        return tag

    def mark_stale(self) -> None:
        """Flag every tag stale — e.g. when the device connection drops."""
        for tag in self._tags.values():
            tag.quality = Quality.STALE
