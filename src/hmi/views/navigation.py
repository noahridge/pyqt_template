"""Page navigator: a router over a ``QStackedWidget``.

Decouples "which screen is showing" from the widgets themselves. Pages
register by key; anything in the app can request navigation by emitting
``navigationRequested`` on the signal bus (e.g. an alarm banner that jumps to
the Alarms page when clicked). This scales far better than wiring every button
directly to every page.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QStackedWidget, QWidget

from hmi.core.safe_slot import safe_slot
from hmi.core.signals import bus
from hmi.views.base_page import BasePage

log = logging.getLogger(__name__)


class Navigator(QStackedWidget):
    """Holds the registered pages and switches between them by key."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pages: dict[str, BasePage] = {}
        self._current_key: str | None = None
        bus().navigationRequested.connect(self.navigate_to)

    def add_page(self, page: BasePage) -> None:
        if page.page_key in self._pages:
            raise ValueError(f"Duplicate page key: {page.page_key}")
        self._pages[page.page_key] = page
        self.addWidget(page)
        if self._current_key is None:
            self._activate(page.page_key)

    def page_keys(self) -> list[str]:
        return list(self._pages)

    def page_title(self, key: str) -> str:
        return self._pages[key].page_title

    @property
    def current_key(self) -> str | None:
        return self._current_key

    @safe_slot(source="Navigator")
    def navigate_to(self, key: str) -> None:
        if key not in self._pages:
            log.warning("Navigation to unknown page '%s' ignored", key)
            return
        if key == self._current_key:
            return
        self._activate(key)

    def _activate(self, key: str) -> None:
        if self._current_key is not None:
            self._pages[self._current_key].on_hide()
        page = self._pages[key]
        self.setCurrentWidget(page)
        self._current_key = key
        page.on_show()
        log.debug("Navigated to '%s'", key)
