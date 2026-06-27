"""Main window: shell that hosts navigation, pages, and status.

Layout:

    +------------------------------------------------+
    |  [ Nav buttons ]                               |
    +----------+-------------------------------------+
    |  side    |                                     |
    |  nav     |          Navigator (pages)          |
    |          |                                     |
    +----------+-------------------------------------+
    |  status bar: connection indicators | messages  |
    +------------------------------------------------+

The window owns no business logic — it wires together components built in
:meth:`hmi.app.HmiApplication`. That separation is what lets the same shell
host a 3-page demo or a 50-page plant HMI.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from hmi.core.exceptions import Severity
from hmi.core.fault import Fault, FaultBus
from hmi.core.safe_slot import safe_slot
from hmi.core.signals import bus
from hmi.views.base_page import BasePage
from hmi.views.navigation import Navigator
from hmi.views.widgets.fault_dialog import FaultNotifier
from hmi.views.widgets.status_indicator import StatusIndicator


class MainWindow(QMainWindow):
    def __init__(self, app_name: str) -> None:
        super().__init__()
        self.setWindowTitle(app_name)
        self.resize(960, 600)

        self._navigator = Navigator()
        self._nav_buttons: dict[str, QPushButton] = {}
        self._indicators: dict[str, StatusIndicator] = {}
        self._fault_notifier = FaultNotifier(self)

        self._build_ui()

        bus().connectionStateChanged.connect(self._on_connection_state)
        FaultBus.instance().faultRaised.connect(self._on_fault)

    # --------------------------------------------------------------- build #
    def _build_ui(self) -> None:
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Side navigation column.
        self._side = QWidget()
        self._side.setObjectName("sideNav")
        self._side_layout = QVBoxLayout(self._side)
        self._side_layout.setContentsMargins(8, 16, 8, 16)
        self._side_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._side.setFixedWidth(160)

        outer.addWidget(self._side)
        outer.addWidget(self._navigator, 1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())

    def add_page(self, page: BasePage) -> None:
        """Register a page and create its nav button."""
        self._navigator.add_page(page)
        button = QPushButton(page.page_title)
        button.setCheckable(True)
        button.setObjectName("navButton")
        button.clicked.connect(lambda _checked, key=page.page_key: self._go(key))
        self._side_layout.addWidget(button)
        self._nav_buttons[page.page_key] = button
        self._sync_nav_buttons()

    def add_status_indicator(self, name: str, label: str) -> None:
        indicator = StatusIndicator(label)
        self._indicators[name] = indicator
        self.statusBar().addPermanentWidget(indicator)

    # ---------------------------------------------------------------- slots #
    @safe_slot(source="MainWindow")
    def _go(self, key: str) -> None:
        bus().navigationRequested.emit(key)
        self._sync_nav_buttons()

    def _sync_nav_buttons(self) -> None:
        current = self._navigator.current_key
        for key, button in self._nav_buttons.items():
            button.setChecked(key == current)

    @safe_slot(source="MainWindow")
    def _on_connection_state(self, name: str, state: object) -> None:
        indicator = self._indicators.get(name)
        if indicator is not None:
            indicator.set_state(state)  # type: ignore[arg-type]

    @safe_slot(source="MainWindow")
    def _on_fault(self, fault: Fault) -> None:
        # Recoverable faults: transient status-bar message (non-blocking).
        if fault.recoverable and fault.severity is not Severity.CRITICAL:
            self.statusBar().showMessage(f"⚠ {fault.source}: {fault.message}", 5000)
