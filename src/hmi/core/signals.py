"""Application-wide signal bus for decoupled communication.

In a large HMI, the service layer, alarm engine, navigation, and many views
all need to react to the same events without holding references to each other.
A single ``SignalBus`` lets producers ``emit`` and consumers ``connect``
without knowing about one another — the key to keeping a big project's
dependency graph from turning into spaghetti.

Keep this bus small and intentional: it is for genuinely cross-cutting events.
Local, parent-child communication should use direct signals, not the bus.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class SignalBus(QObject):
    """Process-wide, cross-cutting application events."""

    # Navigation: request the main window to switch to a page by key.
    navigationRequested = pyqtSignal(str)

    # Service connection state changed: (service_name, ConnectionState).
    connectionStateChanged = pyqtSignal(str, object)

    # A device tag value updated: (tag_name, value).
    tagUpdated = pyqtSignal(str, object)

    # Alarm lifecycle: emits an Alarm object.
    alarmRaised = pyqtSignal(object)
    alarmCleared = pyqtSignal(object)

    _instance: "SignalBus | None" = None

    @classmethod
    def instance(cls) -> "SignalBus":
        if cls._instance is None:
            cls._instance = SignalBus()
        return cls._instance


def bus() -> SignalBus:
    """Shorthand accessor for the singleton bus."""
    return SignalBus.instance()
